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
from .portal_imports.amazon_sp_api import order_adjustments_from_items
from .portal_imports.flipkart_api import order_adjustments
from .views import export_orders_json


class InvoiceParserTests(SimpleTestCase):
    def test_sample_amazon_invoice_keeps_item_tax_and_order_totals_in_balance(self):
        invoice = _parse_amazon(
            """
Order Number: 406-1922460-4293920 Invoice Number : MAA4-288
Invoice Date : 01.10.2026
HyCom Flexi Scrub (HY-FLEXI-W-WR-M_FBA)
HSN:62034200
1,427.62 1 1,427.62 5% IGST 71.38 1,499.00
HyCom Flexi Scrub (HY-FLEXI-W-GR-M_FBA)
HSN:62034200
1,427.62 1 1,427.62 5% IGST 71.38 1,499.00
TOTAL: 142.76 2,998.00
"""
        )

        self.assertEqual(invoice.order_number, "406-1922460-4293920")
        self.assertEqual(invoice.invoice_number, "MAA4-288")
        self.assertEqual(invoice.amount, Decimal("2855.24"))
        self.assertEqual(invoice.gst, Decimal("142.76"))
        self.assertEqual(invoice.total_amount, Decimal("2998.00"))
        self.assertEqual(
            [item.taxable_amount for item in invoice.items],
            [Decimal("1427.62"), Decimal("1427.62")],
        )
        self.assertEqual(
            [item.igst for item in invoice.items],
            [Decimal("71.38"), Decimal("71.38")],
        )

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
        self.assertEqual(invoice.items[0].taxable_amount, Decimal("1903.81"))
        self.assertEqual(invoice.items[0].igst, Decimal("95.19"))
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
Shipping Charge: 50.00
Discount: 5.00
TOTAL PRICE: 1,344.00
"""
        )

        self.assertEqual(invoice.order_number, "OD123456")
        self.assertEqual(invoice.items[0].sku, "HY-FLEXI-M-WR-L")
        self.assertEqual(invoice.amount, Decimal("1280.00"))
        self.assertEqual(invoice.igst, Decimal("64.00"))
        self.assertEqual(invoice.shipping_charge, Decimal("50.00"))
        self.assertEqual(invoice.discount, Decimal("5.00"))
        self.assertEqual(invoice.items[0].taxable_amount, Decimal("1280.00"))

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
Discount: 10.00
NET TOTAL (In Value) Rs. 2048.00
"""
        )

        self.assertEqual(invoice.portal, "own")
        self.assertEqual(invoice.order_number, "1107")
        self.assertEqual(invoice.state_code, "33")
        self.assertEqual(invoice.items[0].quantity, 2)
        self.assertEqual(invoice.gst, Decimal("97.52"))
        self.assertEqual(invoice.total_amount, Decimal("2048.00"))
        self.assertEqual(invoice.shipping_charge, Decimal("50.00"))
        self.assertEqual(invoice.discount, Decimal("10.00"))
        self.assertEqual(invoice.items[0].taxable_amount, Decimal("1902.86"))
        self.assertEqual(invoice.items[0].cgst, Decimal("47.57"))
        self.assertEqual(invoice.items[0].sgst, Decimal("47.57"))

    def test_sample_own_site_igst_invoice_totals_are_reconciled(self):
        invoice = _parse_shopify(
            """
INVOICE NO. : hycom00441
INVOICE DATE : 30/09/2026
ORDER NO. : 1159
CHANNEL : HyCom (Shopify)
SHIPPING ADDRESS: Customer
State Code : 24
SKU : HY-ETHOS-W-NB-2XL
1 Rs. 1903.81 0.00 1903.81 95.19 | 5.00 1999.00
Shipping Charges 50.00 0.00 | 0 50.00
NET TOTAL (In Value) Rs. 2049.00
"""
        )

        self.assertEqual(invoice.amount, Decimal("1953.81"))
        self.assertEqual(invoice.gst, Decimal("95.19"))
        self.assertEqual(invoice.igst, Decimal("95.19"))
        self.assertEqual(invoice.total_amount, Decimal("2049.00"))
        self.assertEqual(invoice.shipping_charge, Decimal("50.00"))
        self.assertEqual(invoice.items[0].taxable_amount, Decimal("1903.81"))
        self.assertEqual(invoice.items[0].igst, Decimal("95.19"))

    def test_sample_flipkart_intra_state_gst_is_split_between_cgst_and_sgst(self):
        invoice = _parse_flipkart_invoice(
            """
SKU ID | Description
QTY
1
HY-FLEXI-M-WR-M
Order Id: OD438816680997126100
Invoice No: NUA5V2O270000003
Invoice Date: 09-10-2026
HSN: 62034200
| CGST: 2.50%
| SGST: 2.50%
| CESS: 0.00%
1
1150.00
-0.00
1095.24
27.38
27.38
0.00
1150.00
Handling Fee
1
0.00
0
0.00
0.00
0.00
0.00
TOTAL QTY: 1
TOTAL PRICE: 1150.00
Shipping/Customer address: Name: Udayakumar
Shipping ADDRESS
Kallakurichi - 606213, IN-TN
"""
        )

        self.assertEqual(invoice.amount, Decimal("1095.24"))
        self.assertEqual(invoice.cgst, Decimal("27.38"))
        self.assertEqual(invoice.sgst, Decimal("27.38"))
        self.assertEqual(invoice.igst, Decimal("0.00"))
        self.assertEqual(invoice.total_amount, Decimal("1150.00"))
        self.assertEqual(invoice.state_code, "33")
        self.assertEqual(invoice.items[0].cgst, Decimal("27.38"))
        self.assertEqual(invoice.items[0].sgst, Decimal("27.38"))

    def test_marketplace_api_adjustments_are_extracted(self):
        amazon_shipping, amazon_discount = order_adjustments_from_items(
            [
                {
                    "proceeds": {
                        "breakdowns": [
                            {"type": "SHIPPING", "subtotal": {"amount": "25.00"}},
                            {"type": "DISCOUNT", "subtotal": {"amount": "-4.50"}},
                        ]
                    }
                }
            ]
        )
        flipkart_shipping, flipkart_discount = order_adjustments(
            [
                {
                    "priceComponents": {
                        "shippingCharge": "15.00",
                        "discount": "3.25",
                    }
                }
            ]
        )

        self.assertEqual(amazon_shipping, Decimal("25.00"))
        self.assertEqual(amazon_discount, Decimal("4.50"))
        self.assertEqual(flipkart_shipping, Decimal("15.00"))
        self.assertEqual(flipkart_discount, Decimal("3.25"))

    def test_amazon_invoice_extracts_shipping_charge_and_discount(self):
        invoice = _parse_amazon(
            """
Order Number: 402-1234567-1234567
Invoice Number : IN-88
Invoice Date : 13.08.2026
HyCom Ethos Scrub (HY-ETHOS-W-NB-M)
HSN:62034200
1,903.81 1 1,903.81 5% IGST 95.19 1,999.00
Shipping Charge: 40.00
Promotion Discount: -10.00
TOTAL: 95.19 2,029.00
"""
        )

        self.assertEqual(invoice.shipping_charge, Decimal("40.00"))
        self.assertEqual(invoice.discount, Decimal("10.00"))


class OrderJsonExportTests(SimpleTestCase):
    def test_json_endpoint_and_import_template_are_available(self):
        self.assertEqual(reverse("sap_orders_json"), "/api/sap/orders.json")
        get_template("import_orders.html")
        self.assertNotIn("billing_address", OrderForm().fields)
        self.assertNotIn("shipping_address", OrderForm().fields)
        self.assertNotIn("shipping_charge", OrderForm().fields)
        self.assertNotIn("discount", OrderForm().fields)

    def test_invoice_template_displays_shipping_and_discount_without_double_counting(self):
        order = SimpleNamespace(
            invoice_number="INV-1",
            invoice_date=date(2026, 10, 1),
            order_number="ORDER-1",
            customer_name="Customer",
            state=None,
            state_code="33",
            is_b2b=False,
            get_portal_display=lambda: "Own Site",
            get_fulfilment_display=lambda: "Self",
            status="Pending",
            ship_date=None,
            amount=100,
            cgst=2.5,
            sgst=2.5,
            igst=0,
            shipping_charge=50,
            discount=10,
            total_amount=105,
            remarks="",
        )
        invoice_settings = SimpleNamespace(
            company_name="Hycom",
            company_subtitle="",
            company_gstin="",
            company_address="",
            company_phone="",
            company_email="",
            footer_note="",
            signature_label="Authorised Signature",
        )

        rendered = get_template("invoice.html").render({
            "order": order,
            "invoice_items": [],
            "invoice_settings": invoice_settings,
        })

        self.assertIn("Shipping Charge", rendered)
        self.assertIn("Rs. 50.00", rendered)
        self.assertIn("Discount", rendered)
        self.assertIn("- Rs. 10.00", rendered)
        self.assertIn("Rs. 105.00", rendered)

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
            taxable_amount=Decimal("1902.86"),
            cgst=Decimal("47.57"),
            sgst=Decimal("47.57"),
            igst=Decimal("0.00"),
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
            shipping_charge=Decimal("50.00"),
            discount=Decimal("0.00"),
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
        self.assertEqual(invoice["invoiceno"], "hycom00387")
        self.assertEqual(invoice["inovoicedate"], "2026-07-13")
        self.assertEqual(invoice["amount"], 1950.48)
        self.assertEqual(invoice["gst"], 97.52)
        self.assertEqual(invoice["total_amount"], 2048)
        self.assertEqual(invoice["shippingcharge"], 50.0)
        self.assertEqual(invoice["othercharge"], 0.0)
        self.assertEqual(invoice["_Items"][0]["baseprice"], 951.43)
        self.assertEqual(invoice["_Items"][0]["gst"], 95.14)
        self.assertEqual(invoice["_Items"][0]["cgst"], 47.57)
        self.assertEqual(invoice["_Items"][0]["sgst"], 47.57)

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
