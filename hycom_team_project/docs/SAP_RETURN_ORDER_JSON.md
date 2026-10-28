# SAP Return Order JSON API

Hycom provides a separate endpoint for returned items and replacement orders:

- Method: `POST`
- URL: `/api/sap/return-orders.json`
- Request body: not required
- Access: requires `Authorization: Bearer <SAP_API_KEY>`
- Response: `application/json`

The endpoint returns return records (`type=return`) using the quantity saved on
each `ReturnItem`. It also returns orders marked as replacements. Cancellation
records are excluded. The response is a JSON array, with one entry per return
record or replacement order.

Example response:

```json
[
  {
    "returnorderno": "1826800002",
    "saledoctype": "CBAR",
    "soldtoparty": "",
    "shiptoparty": "",
    "inovoicedate": "2026-10-24",
    "documentdate": "2026-10-24",
    "currency": "AED",
    "invoiceno": "INV-RET-1",
    "sap_inv_no": "",
    "customerreturn": "",
    "postingstatus": "",
    "postingremarks": "",
    "customer_name": "Return Customer",
    "returnid": "25",
    "is_replacement": false,
    "replacement_for": "",
    "portal": "own",
    "billingaddress": "Billing Address",
    "shippingaddress": "Shipping Address",
    "state": "Abu Dhabi",
    "statecode": "AD",
    "fulfillment": "self",
    "is_b2b": true,
    "gst_number": "GST-123",
    "amount": 300.0,
    "gst": 15.0,
    "cgst": 7.5,
    "sgst": 7.5,
    "igst": 0.0,
    "total_amount": 315.0,
    "discount": 30.0,
    "othercharge": 6.0,
    "_Items": [
      {
        "itemno": "000010",
        "sap_material": "000000000000001140",
        "customermaterial": "",
        "orderqty": 3,
        "orderunit": "ST",
        "itemcategory": "CBRN",
        "plant": "",
        "storagelocation": "",
        "baseprice": 100.0,
        "gst": 15.0,
        "cgst": 7.5,
        "sgst": 7.5,
        "igst": 0.0,
        "total_amount": 315.0,
        "currency": "AED"
      }
    ]
  }
]
```

Return quantities come from recorded return items; their unit price is taken
from the original order item. Replacement entries use the replacement order's
items and prices. The order-level taxable amount and GST totals are calculated
from the exported quantities, so partial returns do not report the full
original order totals. Customer, address, state, fulfilment, B2B, and GST
registration fields are copied from the associated order. Each item's
`total_amount` is its taxable returned/replacement line amount plus its GST.
Order-level `discount` and `othercharge` are prorated by the returned line
value; they are included in the header and not repeated on individual items.
`returnid` identifies a saved return record, while
`replacement_for` contains the linked order number for replacement orders.
SAP customer/party identifiers, plant, and storage location are not currently
stored in Hycom and are returned as empty strings.
