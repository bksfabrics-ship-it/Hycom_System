import json
from decimal import Decimal
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase
from django.template.loader import get_template
from django.urls import reverse

from .invoice_import import _parse_amazon, _parse_flipkart_invoice, _parse_shopify
from .forms import OrderForm
from .views import export_orders_json


class InvoiceParserTests(SimpleTestCase):
    def test_amazon_b2b_invoice_preserves_buyer_gst_and_items(self):
        invoice = _parse_amazon(
            """
Order Number: 402-1234567-1234567
Invoice Number : IN-87
Invoice Date : 13.08.2026
HyCom Ethos Scrub (HY-ETHOS-W-NB-M)
HSN:62034200
1,903.81 1 1,903.81 5% IGST 95.19 1,999.00
TOTAL: 95.19 1,999.00
Billing Address:
Buyer
Buyer Street
GST Registration No: 27APRPG8315C1ZV
Shipping Address:
Buyer
Delivery Street
State/UT Code: 27
GST Registration No: 33AAJCB9299G1Z8
"""
        )

        self.assertEqual(invoice.portal, "amazon")
        self.assertTrue(invoice.is_b2b)
        self.assertEqual(invoice.gst_number, "27APRPG8315C1ZV")
        self.assertEqual(invoice.items[0].sku, "HY-ETHOS-W-NB-M")
        self.assertEqual(invoice.total_amount, Decimal("1999.00"))
        self.assertEqual(invoice.state_code, "27")
        self.assertIn("Delivery Street", invoice.shipping_address)

    def test_flipkart_invoice_extracts_taxable_value_and_sku(self):
        invoice = _parse_flipkart_invoice(
            """
SKU ID | Description
QTY
1
HY-FLEXI-M-WR-L
| HyCom FLEXI Scrub
Order Id:
OD123456
Invoice No:
INV123
Invoice Date:
08-09-2026
HY-FLEXI-M-WR-L
1
TOTAL QTY: 1
1,344.00
-0.00
1,280.00
64.00
0.00
1,344.00
TOTAL PRICE: 1,344.00
"""
        )

        self.assertEqual(invoice.order_number, "OD123456")
        self.assertEqual(invoice.items[0].sku, "HY-FLEXI-M-WR-L")
        self.assertEqual(invoice.amount, Decimal("1280.00"))
        self.assertEqual(invoice.igst, Decimal("64.00"))

    def test_shopify_invoice_includes_shipping_tax_and_charge(self):
        invoice = _parse_shopify(
            """
INVOICE NO. : hycom00387
INVOICE DATE : 13/07/2026
ORDER NO. : 1107
CHANNEL : HyCom (Shopify)
SHIPPING ADDRESS: Customer
State Code : 33
SKU : HY-CORE-M-GR-L
2 Rs. 951.43 0.00 1902.86 47.57 | 2.50 47.57 | 2.50 1998.00
Shipping Charges 47.62 1.19 | 2.50 1.19 | 2.50 50.00
NET TOTAL (In Value) Rs. 2048.00
"""
        )

        self.assertEqual(invoice.portal, "own")
        self.assertEqual(invoice.order_number, "1107")
        self.assertEqual(invoice.state_code, "33")
        self.assertEqual(invoice.items[0].quantity, 2)
        self.assertEqual(invoice.gst, Decimal("97.52"))
        self.assertEqual(invoice.total_amount, Decimal("2048.00"))


class OrderJsonExportTests(SimpleTestCase):
    def test_json_endpoint_and_import_template_are_available(self):
        self.assertEqual(reverse("sap_orders_json"), "/api/sap/orders.json")
        get_template("import_orders.html")
        self.assertNotIn("billing_address", OrderForm().fields)
        self.assertNotIn("shipping_address", OrderForm().fields)

    def test_export_returns_sap_invoice_json(self):
        product = SimpleNamespace(
            sku="HY-CORE-M-GR-L",
            material_code="MAT-123",
            name="Core & Scrub",
        )
        item = SimpleNamespace(
            product=product,
            quantity=2,
            price=Decimal("999.00"),
        )
        order = SimpleNamespace(
            order_number="1107",
            portal="own",
            status="Pending",
            fulfilment="self",
            customer_name="Customer",
            state_code="33",
            state=None,
            billing_address="Billing Street",
            shipping_address="Delivery Street",
            is_b2b=False,
            gst_number=None,
            invoice_number="hycom00387",
            invoice_date=date(2026, 7, 13),
            amount=1950.48,
            gst=97.52,
            cgst=48.76,
            sgst=48.76,
            igst=0,
            total_amount=2048,
            remarks="",
            items=SimpleNamespace(all=lambda: [item]),
        )
        manager = Mock()
        manager.select_related.return_value.prefetch_related.return_value.order_by.return_value = [order]
        request = RequestFactory().post(
            "/api/sap/orders.json",
            HTTP_AUTHORIZATION="Bearer sap-test-key",
        )

        with self.settings(SAP_API_KEY="sap-test-key"):
            with patch("master.views.Order.objects", manager):
                response = export_orders_json(request)

        self.assertEqual(response["Content-Type"], "application/json")
        invoice = json.loads(response.content)[0]
        self.assertEqual(
            list(invoice),
            [
                "invoiceno",
                "saledoctype",
                "soldtoparty",
                "shiptoparty",
                "inovoicedate",
                "documentdate",
                "currency",
                "salesorder",
                "deliverydocument",
                "billingdocument",
                "postingstatus",
                "postingremarks",
                "_Items",
            ],
        )
        self.assertEqual(invoice["invoiceno"], "hycom00387")
        self.assertEqual(invoice["inovoicedate"], "2026-07-13")
        self.assertEqual(
            invoice["_Items"],
            [{
                "itemno": "000010",
                "sap_material": "MAT-123",
                "customermaterial": "",
                "orderqty": 2,
                "orderunit": "ST",
                "itemcategory": "TAN",
                "plant": "1000",
                "storagelocation": "R018",
                "baseprice": 999.0,
                "discount": 0,
                "currency": "AED",
                "othercharge": 50.0,
            }],
        )

    def test_export_only_accepts_post_requests(self):
        request = RequestFactory().get(
            "/api/sap/orders.json",
            HTTP_AUTHORIZATION="Bearer sap-test-key",
        )
        with self.settings(SAP_API_KEY="sap-test-key"):
            response = export_orders_json(request)
        self.assertEqual(response.status_code, 405)

    def test_export_rejects_requests_without_api_key(self):
        request = RequestFactory().post("/api/sap/orders.json")
        with self.settings(SAP_API_KEY="sap-test-key"):
            response = export_orders_json(request)
        self.assertEqual(response.status_code, 401)

    def test_export_is_unavailable_when_api_key_is_not_configured(self):
        request = RequestFactory().post("/api/sap/orders.json")
        with self.settings(SAP_API_KEY=""):
            response = export_orders_json(request)
        self.assertEqual(response.status_code, 503)
