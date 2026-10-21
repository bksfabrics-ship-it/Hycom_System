import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pypdf import PdfReader


SKU_RE = re.compile(r"\bHY-[A-Z0-9_-]+\b", re.IGNORECASE)


@dataclass
class InvoiceItem:
    sku: str
    quantity: int
    unit_price: Decimal
    name: str = ""


@dataclass
class ParsedInvoice:
    portal: str
    order_number: str
    invoice_number: str
    invoice_date: date
    customer_name: str
    state_code: str
    is_b2b: bool
    gst_number: str
    amount: Decimal
    gst: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    total_amount: Decimal
    fulfilment: str
    items: list[InvoiceItem]
    billing_address: str = ""
    shipping_address: str = ""

    def as_dict(self):
        return {
            "portal": self.portal,
            "order_number": self.order_number,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date.isoformat(),
            "customer_name": self.customer_name,
            "billing_address": self.billing_address,
            "shipping_address": self.shipping_address,
            "state_code": self.state_code,
            "is_b2b": self.is_b2b,
            "gst_number": self.gst_number,
            "amount": str(self.amount),
            "gst": str(self.gst),
            "cgst": str(self.cgst),
            "sgst": str(self.sgst),
            "igst": str(self.igst),
            "total_amount": str(self.total_amount),
            "fulfilment": self.fulfilment,
            "items": [
                {
                    "sku": item.sku,
                    "quantity": item.quantity,
                    "unit_price": str(item.unit_price),
                    "name": item.name,
                }
                for item in self.items
            ],
        }


def _money(value):
    try:
        return Decimal(value.replace(",", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError):
        raise ValueError(f"Invalid invoice amount: {value!r}")


def _first(pattern, text, label):
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if not match:
        raise ValueError(f"Could not find {label} in the invoice.")
    return match.group(1).strip()


def _date(value):
    value = value.strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported invoice date: {value!r}")


def _header_value(text, label):
    return _first(
        rf"{label}\s*:\s*([^\r\n]+)",
        text,
        label.replace(r"\s*", " ").replace("\\", ""),
    )


def _customer_state(text):
    shipping = re.search(
        r"Shipping Address\s*:(.*?)(?:Place of supply|Place of delivery|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    address_text = shipping.group(1) if shipping else text
    match = re.search(
        r"State/UT Code\s*:\s*(\d{2})",
        address_text,
        re.IGNORECASE,
    )
    return match.group(1) if match else ""


def _address_section(text, start_label, end_label):
    match = re.search(
        rf"{start_label}\s*:?\s*(.*?)(?=\n\s*(?:{end_label})\s*:?|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return "\n".join(line.strip() for line in match.group(1).splitlines() if line.strip())


def _buyer_gst(text):
    billing_address = _address_section(text, r"Billing Address", r"Shipping Address")
    match = re.search(
        r"(?:GSTIN|GST Registration No\.?)\s*:\s*([0-9A-Z]{15})",
        billing_address,
        re.IGNORECASE,
    )
    return match.group(1).upper() if match else ""


def _amazon_items(text):
    matches = list(SKU_RE.finditer(text))
    items = []
    for index, sku_match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        detail = text[sku_match.end():end]
        hsn = re.search(r"HSN\s*:\s*\d+", detail, re.IGNORECASE)
        if not hsn:
            continue
        amounts = detail[hsn.end():]
        amount_row = re.search(
            r"\d[\d,]*\.\d{2}\s+(\d+)\s+\d[\d,]*\.\d{2}\s+"
            r"\d+(?:\.\d+)?%\s+(?:IGST|CGST|SGST)\s+"
            r"\d[\d,]*\.\d{2}\s+(\d[\d,]*\.\d{2})",
            amounts,
            re.IGNORECASE,
        )
        if not amount_row:
            continue
        quantity = int(amount_row.group(1))
        line_total = _money(amount_row.group(2))
        if quantity < 1:
            raise ValueError(f"Invalid quantity for SKU {sku_match.group(0)}.")
        items.append(InvoiceItem(sku_match.group(0).upper(), quantity, line_total / quantity))
    if not items:
        raise ValueError("No Amazon product rows with recognized Hycom SKUs were found.")
    return items


def _parse_amazon(text):
    order_number = _header_value(text, r"Order Number")
    invoice_number = _header_value(text, r"Invoice Number")
    invoice_date = _date(_header_value(text, r"Invoice Date"))
    items = _amazon_items(text)
    gst_number = _buyer_gst(text)
    total_match = re.search(
        r"TOTAL\s*:\s*[\D]*([\d,]+\.\d{2})\s+[\D]*([\d,]+\.\d{2})",
        text,
        re.IGNORECASE,
    )
    if total_match:
        gst = _money(total_match.group(1))
        total = _money(total_match.group(2))
    else:
        total = sum(
            (item.unit_price * item.quantity for item in items),
            Decimal("0.00"),
        )
        gst = Decimal("0.00")
    billing_address = _address_section(text, r"Billing Address", r"Shipping Address")
    shipping_address = _address_section(
        text,
        r"Shipping Address",
        r"Place of supply|Place of delivery",
    )
    state_code = _customer_state(shipping_address)
    customer_name = " ".join(
        line for line in shipping_address.splitlines()[:2] if line.strip()
    )
    return ParsedInvoice(
        portal="amazon",
        order_number=order_number,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        customer_name=customer_name or "Amazon Customer",
        state_code=state_code,
        is_b2b=bool(gst_number),
        gst_number=gst_number,
        amount=total - gst,
        gst=gst,
        cgst=Decimal("0.00"),
        sgst=Decimal("0.00"),
        igst=gst,
        total_amount=total,
        fulfilment="amazon",
        items=items,
        billing_address=billing_address,
        shipping_address=shipping_address,
    )


def _parse_flipkart_invoice(text):
    order_number = _header_value(text, r"Order Id")
    invoice_number = _header_value(text, r"Invoice No")
    date_value = _header_value(text, r"Invoice Date")
    date_value = re.sub(r",.*$", "", date_value).strip()
    invoice_date = _date(date_value)
    sku_match = re.search(
        r"SKU ID\s*\|\s*Description\s*QTY\s+\d+\s+([A-Z0-9_-]+)",
        text,
        re.IGNORECASE,
    )
    if not sku_match:
        raise ValueError("No Flipkart product row with a recognized Hycom SKU was found.")

    quantity_match = re.search(r"TOTAL QTY\s*:\s*(\d+)", text, re.IGNORECASE)
    if not quantity_match or int(quantity_match.group(1)) < 1:
        raise ValueError("Could not read the Flipkart invoice quantity.")

    total = _money(_first(r"TOTAL PRICE\s*:\s*([\d,]+\.\d{2})", text, "total price"))
    taxable_values = re.findall(r"(?m)^\s*(-?\d[\d,]*\.\d{2})\s*$", text)
    if len(taxable_values) < 3:
        raise ValueError("Could not read the Flipkart taxable amount and GST.")
    taxable = _money(taxable_values[2])
    tax = total - taxable
    quantity = int(quantity_match.group(1))
    items = [InvoiceItem(sku_match.group(1).upper(), quantity, total / quantity)]
    customer_match = re.search(
        r"Shipping/Customer address\s*:\s*Name\s*:\s*([^\r\n]+)",
        text,
        re.IGNORECASE,
    )
    billing_address = _address_section(text, r"Billing Address", r"Shipping ADDRESS")
    shipping_address = _address_section(
        text,
        r"Shipping ADDRESS",
        r"FSSAI License number|Seller Registered Address",
    ) or _address_section(
        text,
        r"Shipping/Customer address",
        r"Not for resale|Sold By",
    )
    return ParsedInvoice(
        portal="flipkart",
        order_number=order_number,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        customer_name=customer_match.group(1).strip() if customer_match else "Flipkart Customer",
        state_code="",
        is_b2b=False,
        gst_number="",
        amount=taxable,
        gst=tax,
        cgst=Decimal("0.00"),
        sgst=Decimal("0.00"),
        igst=tax,
        total_amount=total,
        fulfilment="flipkart",
        items=items,
        billing_address=billing_address,
        shipping_address=shipping_address,
    )


def _parse_shopify(text):
    order_number = _header_value(text, r"ORDER NO\.")
    invoice_number = _header_value(text, r"INVOICE NO\.")
    invoice_date = _date(_header_value(text, r"INVOICE DATE"))
    sku_matches = list(SKU_RE.finditer(text))
    if not sku_matches:
        raise ValueError("No Shopify product row with a recognized Hycom SKU was found.")

    item_row_pattern = re.compile(
        r"(?m)^\s*(\d+)\s+Rs\.?\s*[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+"
        r"([\d,.]+)\s*\|\s*[\d,.]+\s+([\d,.]+)\s*\|\s*[\d,.]+\s+([\d,.]+)\s*$",
        re.IGNORECASE,
    )
    items = []
    cgst = Decimal("0.00")
    sgst = Decimal("0.00")
    for index, sku_match in enumerate(sku_matches):
        end = sku_matches[index + 1].start() if index + 1 < len(sku_matches) else len(text)
        item_row = item_row_pattern.search(text, sku_match.end(), end)
        if not item_row:
            continue
        quantity = int(item_row.group(1))
        if quantity < 1:
            raise ValueError(f"Invalid quantity for SKU {sku_match.group(0)}.")
        line_total = _money(item_row.group(4))
        cgst += _money(item_row.group(2))
        sgst += _money(item_row.group(3))
        items.append(
            InvoiceItem(
                sku_match.group(0).upper(),
                quantity,
                line_total / quantity,
            )
        )
    if not items:
        raise ValueError("Could not read the Shopify product quantity and line total.")

    total = _money(_first(r"NET TOTAL\s*\(IN VALUE\)\s*RS\.?\s*([\d,.]+)", text, "net total"))
    shipping_tax = re.search(
        r"Shipping Charges\s+[\d,.]+\s+([\d,.]+)\s*\|\s*[\d,.]+\s+"
        r"([\d,.]+)\s*\|\s*[\d,.]+",
        text,
        re.IGNORECASE,
    )
    if shipping_tax:
        cgst += _money(shipping_tax.group(1))
        sgst += _money(shipping_tax.group(2))
    gst = cgst + sgst
    state_match = re.search(r"State Code\s*:\s*(\d{2})", text, re.IGNORECASE)
    customer_match = re.search(
        r"SHIPPING ADDRESS\s*:\s*([^\r\n]+)",
        text,
        re.IGNORECASE,
    )
    shipping_address = _address_section(text, r"SHIPPING ADDRESS", r"SOLD BY")
    return ParsedInvoice(
        portal="own",
        order_number=order_number,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        customer_name=customer_match.group(1).strip() if customer_match else "Shopify Customer",
        state_code=state_match.group(1) if state_match else "",
        is_b2b=False,
        gst_number="",
        amount=total - gst,
        gst=gst,
        cgst=cgst,
        sgst=sgst,
        igst=Decimal("0.00"),
        total_amount=total,
        fulfilment="self",
        items=items,
        shipping_address=shipping_address,
    )


def parse_invoice_pdf(uploaded_file):
    """Extract one or more supported Amazon, Flipkart, or Shopify invoices."""
    try:
        reader = PdfReader(uploaded_file)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise ValueError("The uploaded file could not be read as a PDF invoice.") from exc

    text = text.replace("?", "").replace("₹", "")
    if not text.strip():
        raise ValueError("This PDF contains no selectable text. Searchable PDFs are required.")

    if re.search(r"CHANNEL\s*:\s*HyCom\s*\(Shopify\)", text, re.IGNORECASE):
        return [_parse_shopify(text)]
    if re.search(r"Invoice Id\s*:|SKU ID\s*\|\s*Description", text, re.IGNORECASE):
        blocks = re.split(
            r"(?=SKU ID\s*\|\s*Description)",
            text,
            flags=re.IGNORECASE,
        )
        invoices = [
            _parse_flipkart_invoice(block)
            for block in blocks
            if re.search(r"Order Id\s*:", block, re.IGNORECASE)
        ]
        if not invoices:
            raise ValueError("No Flipkart tax invoices were found in the PDF.")
        return invoices
    if re.search(r"Order Number\s*:", text, re.IGNORECASE):
        return [_parse_amazon(text)]
    raise ValueError("Invoice format not recognized. Supported formats: Amazon, Flipkart, and Shopify.")
