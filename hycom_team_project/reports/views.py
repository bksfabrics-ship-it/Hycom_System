from django.shortcuts import render
from master.models import OrderItem
from stock.models import Product
# Create your views here.
from django.db.models import Sum, Q, Count
from returns.models import ReturnItem
from django.db.models import F
import csv
from django.http import HttpResponse
from master.models import Order
from django.shortcuts import get_object_or_404
from django.db.models.functions import TruncDate
import json
from django.core.serializers.json import DjangoJSONEncoder
from utils.permissions import area_required, can_access_area
from django.contrib.auth.decorators import login_required

@area_required('reports')
def stock_report(request):
    products = Product.objects.annotate(
        ordered_qty=Sum('orderitem__quantity'),
        returned_qty=Sum('returnitem__quantity')
    )

    return render(request, 'stock_report.html', {'products': products})




@area_required('reports')
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

    return render(request, 'return_report.html', {'data': data})


@area_required('reports')
def export_return_report(request):
    qs = ReturnItem.objects.select_related('return_obj', 'product')


    # (Optional) filters via query params
    # - from_date/to_date apply to item_arrived_date
    # - search matches order number / sku / product name
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    search = request.GET.get('search')

    if start_date:
        qs = qs.filter(item_arrived_date__gte=start_date)
    if end_date:
        qs = qs.filter(item_arrived_date__lte=end_date)
    if search:
        qs = qs.filter(
            Q(return_obj__order__order_number__icontains=search) |
            Q(product__sku__icontains=search) |
            Q(product__name__icontains=search)
        )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="return_report.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Order No', 'Type',
        'SKU', 'Product',
        'Qty', 'Condition',
        'Customer Message', 'QC Checked By', 'QC Remarks',
        'Arrived Date'
    ])

    for row in qs.values(
        'return_obj__order__order_number',
        'return_obj__type',
        'product__sku',
        'product__name',
        'quantity',
        'condition',
        'customer_message',
        'qc_checked_by',
        'qc_message',
        'item_arrived_date'
    ):
        writer.writerow([
            row['return_obj__order__order_number'],
            row['return_obj__type'],
            row['product__sku'],
            row['product__name'],
            row['quantity'],
            row['condition'],
            row['customer_message'],
            row['qc_checked_by'],
            row['qc_message'],
            row['item_arrived_date']
        ])

    return response





@area_required('reports')
def order_report(request):
    qs = OrderItem.objects.select_related('order', 'product')

    # filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    status = request.GET.get('status')
    search = request.GET.get('search')
    
    if not can_access_area(request.user, 'reports'):
        return render(request, '403.html')

    if start_date:
        qs = qs.filter(order__invoice_date__gte=start_date)

    if end_date:
        qs = qs.filter(order__invoice_date__lte=end_date)

    if status:
        qs = qs.filter(order__status=status)

    if search:
        qs = qs.filter(
            Q(order__order_number__icontains=search) |
            Q(order__customer_name__icontains=search) |
            Q(product__sku__icontains=search)
        )

    data = qs.values(
        'order__id',
        'order__order_number',
        'order__invoice_number',
        'order__invoice_date',
        'order__ship_date',
        'order__fulfilment',
        'order__is_b2b',
        'order__gst_number',
        'order__status',
        'order__customer_name',
        'order__state__name',
        'product__sku',
        'product__name',
        'product__size',
        'product__color',
        'product__gender',
        'product__style',
        'quantity',
        'price',
        'order__remarks'
    )
    
     # 📈 SALES TREND
    sales_trend = qs.annotate(date=TruncDate('order__invoice_date')) \
        .values('date') \
        .annotate(total=Sum(F('quantity') * F('price'))) \
        .order_by('date')

    # 📊 STATUS COUNT
    status_data = qs.values('order__status') \
        .annotate(count=Count('id'))

    # 🏆 TOP PRODUCTS
    top_products = qs.values('order__portal') \
        .annotate(total_qty=Sum('quantity')) \
        .order_by('-total_qty')[:5]
        
    top_colors = qs.values('product__color') \
        .annotate(total_qty=Sum('quantity')) \
        .order_by('-total_qty')[:5]

    return render(request, 'order_report.html', {
    'data': data,
    'sales_trend': json.dumps(list(sales_trend), cls=DjangoJSONEncoder),
    'status_data': json.dumps(list(status_data), cls=DjangoJSONEncoder),
    'top_products': json.dumps(list(top_products), cls=DjangoJSONEncoder),
    'product_data': json.dumps(list(top_colors), cls=DjangoJSONEncoder)
})




@area_required('reports')
def export_stock_report(request):
    products = Product.objects.annotate(
        ordered_qty=Sum('orderitem__quantity'),
        returned_qty=Sum('returnitem__quantity')
    )

    # (Optional) filters via query params
    sku = request.GET.get('sku')
    name = request.GET.get('name')
    warehouse = request.GET.get('warehouse')

    if sku:
        products = products.filter(sku__icontains=sku)
    if name:
        products = products.filter(name__icontains=name)
    if warehouse:
        products = products.filter(warehouse__icontains=warehouse)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="stock_report.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'SKU', 'Product', 'Warehouse', 'Available Stock'
    ])

    for p in products:
        writer.writerow([
            p.sku,
            p.name,
            p.warehouse,
            p.stock,
        ])

    return response



def export_order_report(request):
    qs = OrderItem.objects.select_related('order', 'product')

    # same filters (reuse logic)
    if request.GET.get('start_date'):
        qs = qs.filter(order__invoice_date__gte=request.GET.get('start_date'))

    if request.GET.get('end_date'):
        qs = qs.filter(order__invoice_date__lte=request.GET.get('end_date'))

    if request.GET.get('status'):
        qs = qs.filter(order__status=request.GET.get('status'))

    if request.GET.get('search'):
        s = request.GET.get('search')
        qs = qs.filter(
            Q(order__order_number__icontains=s) |
            Q(order__customer_name__icontains=s) |
            Q(product__sku__icontains=s)
        )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="order_report.csv"'

    writer = csv.writer(response)

    writer.writerow([
        'Order No', 'Invoice No', 'Date', 'Status',
        'Customer', 'State', 'SKU', 'Product', 'Size', 'Color', 'Gender', 'Style',
        'Qty', 'Price', 'Ship Date', 'Fulfilment', 'B2B', 'GST Number', 'Remarks'
    ])

    for item in qs:
        writer.writerow([
            item.order.order_number,
            item.order.invoice_number,
            item.order.invoice_date,
            item.order.status,
            item.order.customer_name,
            item.order.state.name if item.order.state else '',
            item.product.sku,
            item.product.name,
            item.product.size,
            item.product.color,
            item.product.gender,
            item.product.style,
            item.quantity,
            item.price,
            item.order.ship_date,
            item.order.fulfilment,
            item.order.is_b2b,
            item.order.gst_number,
            item.order.remarks
        ])

    return response




def order_detail_view(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related('items__product'), id=order_id)

    return render(request, 'order_detail.html', {
        'order': order
    })