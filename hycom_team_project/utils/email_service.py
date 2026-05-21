from django.core.mail import send_mail
from django.conf import settings
from django.db import DatabaseError
from master.models import NotificationSetting


def send_order_email(order, is_update=False):


    status = order.status

    # ✅ SUBJECT
    if status == "Shipped":
        subject = f"🚚 Order Shipped - {order.order_number}"
        header = "🚚 ORDER SHIPPED"

    elif status == "Cancelled":
        subject = f"❌ Order Cancelled - {order.order_number}"
        header = "❌ ORDER CANCELLED"

    elif status == "Return Arrived":
        subject = f"🔁 Return Arrived - {order.order_number}"
        header = "🔁 RETURN RECEIVED"

    else:
        subject = f"📦 Order Updated - {order.order_number}"
        header = "📦 ORDER UPDATE"

    # ✅ MESSAGE HEADER
    message = f"""
📦 ORDER DETAILS

Order No      : {order.order_number}
Invoice No    : {order.invoice_number or '-'}
Invoice Date  : {order.invoice_date.strftime('%d-%m-%Y') if order.invoice_date else '-'}
Ship Date     : {order.ship_date.strftime('%d-%m-%Y') if order.ship_date else '-'}
Status        : {order.status}
Customer      : {order.customer_name}
Portal        : {order.portal}
Fulfilment    : {order.fulfilment}
State         : {order.state} ({order.state_code})
B2B           : {'Yes' if order.is_b2b else 'No'}
GST No        : {order.gst_number if order.is_b2b else 'N/A'}
Total Amount  : ₹{order.total_amount}

-----------------------------------
🧾 ORDER ITEMS
-----------------------------------
"""

    for item in order.items.all():
        sku = item.product.sku or "-"
        material = getattr(item.product, "material_code", "-") or "-"

        message += (
            f"- {item.product.name} "
            f"(SKU: {sku}, Material: {material}) "
            f"| Qty: {item.quantity}\n"
        )

    message += "\n-----------------------------------\n"

    # ✅ EXTRA MESSAGE BASED ON STATUS
    if status == "Cancelled":
        message += "⚠️ This order has been cancelled.\n"
    elif status == "Return Arrived":
        message += "📦 Returned items received and under inspection.\n"
    elif status == "Shipped":
        message += "🚚 Order has been shipped successfully.\n"

    message += "\nThis is an auto-generated email."

    try:
        recipients = list(
            NotificationSetting.objects.filter(
                category=NotificationSetting.CATEGORY_ORDER_UPDATE,
                is_active=True
            ).values_list("email", flat=True)
        )
    except DatabaseError:
        recipients = [
            "ecom@hycomworkwear.in",
            "digitalmarketing@bksfabrics.in",
        ]

    if not recipients:
        return

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
    if not from_email:
        raise ValueError("DEFAULT_FROM_EMAIL (or EMAIL_HOST_USER) is not set; cannot send order email.")

    send_mail(subject, message.strip(), from_email, recipients, fail_silently=False)
