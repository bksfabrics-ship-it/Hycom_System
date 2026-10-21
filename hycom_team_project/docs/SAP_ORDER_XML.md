# SAP Order XML API

Hycom exposes saved orders as XML for the SAP integration:

- Method: `GET`
- URL: `/api/sap/orders.xml`
- Access: requires `Authorization: Bearer <SAP_API_KEY>`
- Response: `application/xml; charset=utf-8`
- Currency: INR
- Result: all orders, oldest first

Set a strong `SAP_API_KEY` in the private server environment file and share it
with the SAP team securely. Never commit the key to source control.

Example request:

```http
GET /api/sap/orders.xml HTTP/1.1
Host: <your-api-host>
Authorization: Bearer <SAP_API_KEY>
```

The endpoint returns `401 Unauthorized` for a missing or invalid key and `503
Service Unavailable` if the server key is not configured. Use HTTPS when
connecting over the internet.

The SAP integration can use this versioned structure:

```xml
<?xml version='1.0' encoding='utf-8'?>
<HycomOrderExport version="1.0">
  <Order>
    <OrderNumber>1107</OrderNumber>
    <Portal>own</Portal>
    <Status>Pending</Status>
    <Fulfilment>self</Fulfilment>
    <CustomerName>Customer Name</CustomerName>
    <BillingAddress>Billing address</BillingAddress>
    <ShippingAddress>Shipping address</ShippingAddress>
    <StateCode>33</StateCode>
    <IsB2B>false</IsB2B>
    <GSTNumber />
    <Invoice>
      <Number>hycom00387</Number>
      <Date>2026-07-13</Date>
    </Invoice>
    <Totals currency="INR">
      <TaxableAmount>1950.48</TaxableAmount>
      <GSTAmount>97.52</GSTAmount>
      <CGST>48.76</CGST>
      <SGST>48.76</SGST>
      <IGST>0.00</IGST>
      <OtherCharges>50.00</OtherCharges>
      <TotalAmount>2048.00</TotalAmount>
    </Totals>
    <Items>
      <Item>
        <SKU>HY-CORE-M-GR-L</SKU>
        <MaterialCode />
        <ProductName>Core Men Scrub Suit</ProductName>
        <Quantity>2</Quantity>
        <UnitPrice>999.00</UnitPrice>
        <LineTotal>1998.00</LineTotal>
      </Item>
    </Items>
  </Order>
</HycomOrderExport>
```

`UnitPrice` and `LineTotal` are the stored item prices (including GST). `TaxableAmount`
and tax fields are invoice totals. `OtherCharges` is the difference between the order
total and item line totals (for example, shipping).

Invoice PDFs can be uploaded at **Import Orders → Import Orders from Invoice PDF**.
The import supports searchable Amazon B2C/B2B, Flipkart, and Shopify PDFs matching
the supplied samples. It previews extracted fields, suggests products by SKU or
material code (with manual product selection when no match is found), rejects duplicate
orders/invoices, and checks stock before creating the order. Image-only scanned PDFs
are not supported.
