from django.shortcuts import render
from hycom_team_project.master.models import OrderItem
from stock.models import Product
# Create your views here.
from django.db.models import Sum
from returns.models import ReturnItem

def stock_report(request):
    products = Product.objects.annotate(
        ordered_qty=Sum('orderitem__quantity'),
        returned_qty=Sum('returnitem__quantity')
    )

    return render(request, 'reports/stock_report.html', {'products': products})





def return_report(request):
    data = ReturnItem.objects.select_related('return_obj', 'product').values(
        'return_obj__order__order_number',
        'return_obj__type',  # Return / Cancel / Replacement

        'product__sku',
        'product__name',

        'quantity',
        'condition',
        'customer_message',
        'qc_checked_by',
        'qc_message',
        'item_arrived_date'
    )

    return render(request, 'reports/return_report.html', {'data': data})





from django.db.models import F

def order_report(request):
    data = OrderItem.objects.select_related('order', 'product').values(
        'order__order_number',
        'order__invoice_number',
        'order__invoice_date',
        'order__status',
        'order__customer_name',
        'order__state__name',

        'product__sku',
        'product__size',
        'product__color',
        'product__gender',
        'product__style',

        'quantity',
        'price'
    )

    return render(request, 'reports/order_report.html', {'data': data})


