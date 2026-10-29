from collections import defaultdict

from django.db import transaction

from stock.models import Product


@transaction.atomic
def deduct_order_stock(order):
    order = type(order).objects.select_for_update().get(pk=order.pk)
    if order.is_stock_updated:
        return

    required_quantities = defaultdict(int)
    for item in order.items.all():
        required_quantities[item.product_id] += item.quantity

    products = Product.objects.select_for_update().filter(
        pk__in=required_quantities
    ).order_by("pk")
    for product in products:
        required_quantity = required_quantities[product.pk]
        product.stock -= required_quantity
        product.save(update_fields=["stock"])

    order.is_stock_updated = True
    order.save(update_fields=["is_stock_updated"])
