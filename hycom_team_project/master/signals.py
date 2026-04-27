from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import Order
from utils.google_sheets import get_sheet, delete_order_rows


@receiver(post_delete, sender=Order)
def delete_order_from_sheet(sender, instance, **kwargs):
    try:
        sheet = get_sheet()
        delete_order_rows(sheet, instance.order_number)
    except Exception as e:
        print("Google Sheet delete failed:", e)