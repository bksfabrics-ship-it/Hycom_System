import gspread
from oauth2client.service_account import ServiceAccountCredentials


def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json", scope
    )

    client = gspread.authorize(creds)
    return client.open("Hycom Orders").sheet1


import datetime



def delete_order_rows(sheet, order_number):
    all_rows = sheet.get_all_values()

    rows_to_delete = []

    # Skip header (index 0)
    for i, row in enumerate(all_rows[1:], start=2):
        if row[5] == str(order_number):  # Order No column index = 5
            rows_to_delete.append(i)

    # Delete from bottom to avoid index shift
    for row_index in reversed(rows_to_delete):
        sheet.delete_rows(row_index)
        
        
def push_order_to_sheet(order):
    sheet = get_sheet()

    # ✅ STEP 1: REMOVE OLD DATA
    delete_order_rows(sheet, order.order_number)

    existing_rows = len(sheet.get_all_values())
    serial_no = existing_rows

    rows = []

    for item in order.items.all():

        qty = item.quantity or 0
        price = float(item.price or 0)

        total = qty * price
        taxable = round(total / 1.05, 2)
        tax = round(total - taxable, 2)

        rows.append([
            serial_no,
            f"{order.state_code or ''} - {order.state or ''}",
            order.invoice_date.strftime('%d-%m-%Y') if order.invoice_date else '',
            order.ship_date.strftime('%d-%m-%Y') if order.ship_date else '',
            order.invoice_number or '',
            order.order_number or '',
            order.customer_name or '',
            order.fulfilment or '',
            order.gst_number if order.is_b2b else '',
            order.status or '',
            item.product.sku or '',
            qty,
            taxable,
            tax,
            total,
            '',
            order.remarks or ''
        ])

        serial_no += 1

    if rows:
        sheet.append_rows(rows)