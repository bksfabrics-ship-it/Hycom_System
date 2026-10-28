# SAP Invoice JSON API

Hycom returns saved invoices in the SAP header-and-items JSON format:

- Method: `POST`
- URL: `/api/sap/orders.json`
- Request body: not required; the endpoint exports all saved orders, oldest first
- Access: requires `Authorization: Bearer <SAP_API_KEY>`
- Response: `application/json`
- Currency: AED, as in the agreed SAP payload format

Set `SAP_API_KEY` in the private server environment and share it with the SAP
team securely. Never commit the key to source control. The endpoint returns
`401 Unauthorized` for a missing or invalid key and `503 Service Unavailable`
if the server key is not configured. Use HTTPS when connecting over the internet.

Example request:

```http
POST /api/sap/orders.json HTTP/1.1
Host: <your-api-host>
Authorization: Bearer <SAP_API_KEY>
Content-Length: 0
```

The response is a JSON array. Each element represents one invoice:

```json
[
  {
    "invoiceno": "hycom00387",
    "saledoctype": "OR",
    "soldtoparty": "",
    "shiptoparty": "",
    "inovoicedate": "2026-07-13",
    "documentdate": "2026-07-13",
    "currency": "AED",
    "salesorder": "",
    "deliverydocument": "",
    "billingdocument": "",
    "postingstatus": "",
    "postingremarks": "",
    "amount": 1950.48,
    "gst": 97.52,
    "cgst": 48.76,
    "sgst": 48.76,
    "igst": 0.0,
    "discount": 0.0,
    "shippingcharge": 50.0,
    "othercharge": 0.0,
    "total_amount": 2048.0,
    "_Items": [
      {
        "itemno": "000010",
        "sap_material": "000000000000001140",
        "customermaterial": "",
        "orderqty": 2,
        "orderunit": "ST",
        "itemcategory": "TAN",
        "plant": "1000",
        "storagelocation": "R018",
        "baseprice": 951.43,
        "currency": "AED",
        "gst": 95.14,
        "cgst": 47.57,
        "sgst": 47.57,
        "igst": 0.0,
        "total_amount": 1998.0
      }
    ]
  }
]
```

Invoice number and date come from the saved invoice. `sap_material` comes from
the product's SAP material code. `baseprice` is the item's taxable unit price;
`gst`, `cgst`, `sgst`, and `igst` are the corresponding item tax amounts.
Each item's `total_amount` is its taxable line amount plus its GST.
Order-level `amount` is taxable value, `gst` is total tax, and
`total_amount = amount + gst`. The order-level `shippingcharge` is reported
separately, so it is excluded from `othercharge` and is not counted twice.
SAP party and document identifiers not stored by Hycom are returned as empty
strings. Item number, unit, category, plant, and storage location use the
values shown in the agreed payload format.

Invoice PDFs can be uploaded at **Import Orders → Import Orders from Invoice PDF**.
The import supports searchable Amazon B2C/B2B, Flipkart, and Shopify PDFs matching
the supplied samples. It previews extracted fields, suggests products by SKU or
material code (with manual product selection when no match is found), rejects
duplicate orders/invoices, and checks stock before creating the order. Image-only
scanned PDFs are not supported.
