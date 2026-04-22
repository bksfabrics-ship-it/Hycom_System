from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import json
from .models import Order, OrderItem
from stock.models import Product
from django.shortcuts import render, redirect
from django.forms import formset_factory
from .forms import OrderForm, OrderItemForm
from django.db.models import Sum
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Q, Prefetch, Sum, F
import csv
from django.http import HttpResponse


def get_orders(request):
    if request.method == 'GET':

        orders_data = []

        orders = Order.objects.all().prefetch_related('items')

        for order in orders:
            items = []

            for item in order.items.all():
                items.append({
                    "product": item.product.name,
                    "sku": item.product.sku,
                    "quantity": item.quantity,
                    "price": float(item.price)
                })

            orders_data.append({
                "order_id": order.order_number,
                "customer": order.customer_name,
                "portal": order.portal,
                "status": order.status,
                "total_amount": float(order.total_amount),
                "items": items
            })

        return JsonResponse(orders_data, safe=False)



def create_order(request):

    if request.method == 'POST':
        order_form = OrderForm(request.POST)
        formset = OrderItemForm(request.POST)

        if order_form.is_valid() and formset.is_valid():

            try:
                with transaction.atomic():

                    order = order_form.save()

                    items = formset.save(commit=False)

                    for item in items:
                        product = item.product
                        qty = item.quantity

                        # ❌ VALIDATION: prevent negative stock
                        if product.stock < qty:
                            raise Exception(f"Not enough stock for {product.name}")

                        # ✅ Reduce stock
                        product.stock -= qty
                        product.save()

                        item.order = order
                        item.save()
                messages.success(request, "Order saved successfully")
                return redirect('/orders/')

            except Exception as e:
                messages.error(request, "Something went wrong")
                return render(request, 'create_order.html', {
                    'order_form': order_form,
                    'formset': formset,
                    'error': str(e)
                })

    else:
        order_form = OrderForm()
        formset = OrderItemForm()

    return render(request, 'create_order.html', {
        'order_form': order_form,
        'formset': formset
    })
        
        

def restore_old_stock(order):
    old_items = OrderItem.objects.filter(order=order)

    for item in old_items:
        product = item.product
        product.stock += item.quantity
        product.save()

    old_items.delete()


def edit_order(request, pk):

    order = get_object_or_404(Order, pk=pk)

    ItemFormSet = formset_factory(OrderItemForm, extra=0)

    if request.method == 'POST':

        order_form = OrderForm(request.POST, instance=order)
        formset = ItemFormSet(request.POST)

        if order_form.is_valid() and formset.is_valid():

            old_status = order.status

            with transaction.atomic():

                order = order_form.save()

                # ✅ CHECK STATUS CHANGE
                if old_status != 'return_arrived' and order.status == 'return_arrived':

                    for form in formset:
                        if form.cleaned_data:

                            product = form.cleaned_data['product']
                            qty = form.cleaned_data['quantity']

                            product.stock += qty
                            product.save()

            return redirect('/orders/')

    else:
        order_form = OrderForm(instance=order)
        formset = ItemFormSet()

    return render(request, 'create_order.html', {
        'order_form': order_form,
        'formset': formset
    })

def get_product_by_sku(request):
    sku = request.GET.get('sku', '').strip()

    try:
        product = Product.objects.get(sku__iexact=sku)  # ✅ case-insensitive

        return JsonResponse({
            'id': product.id,
            'name': product.name,
            'price': float(product.selling_price)
        })
        print("SKU RECEIVED:", sku)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'})
    


def create_order_ui(request):

    ItemFormSet = formset_factory(OrderItemForm, extra=3)

    if request.method == 'POST':
        order_form = OrderForm(request.POST)
        formset = ItemFormSet(request.POST)

        if order_form.is_valid() and formset.is_valid():

            with transaction.atomic():

                # 1) Save order
                order = order_form.save()

                # 2) Save items
                for form in formset:
                    data = form.cleaned_data
                    if not data or not data.get('product') or not data.get('quantity'):
                        continue

                    obj = form.save(commit=False)
                    obj.order = order
                    obj.save()

                # 3) Calculate totals (GST inclusive pricing)
                amount = 0
                gst_total = 0

                for it in order.orderitem_set.all():
                    total_price = it.quantity * it.price
                    base = total_price / 1.05
                    gst = total_price - base

                    amount += base
                    gst_total += gst

                # 4) Rounding
                order.amount = round(amount, 2)
                order.gst = round(gst_total, 2)

                # 5) GST split
                state = (order.state or '').strip().lower()
                if state in ['tamil nadu', 'tn']:
                    order.cgst = round(order.gst / 2, 2)
                    order.sgst = round(order.gst / 2, 2)
                    order.igst = 0
                else:
                    order.igst = round(order.gst, 2)
                    order.cgst = 0
                    order.sgst = 0

                # 6) Final total (inclusive)
                order.total_amount = round(order.amount + order.gst, 2)

                order.save()

                # 7) Return stock (create-time only; handle edit separately)
                if order.status == 'return_arrived':
                    for it in order.orderitem_set.all():
                        product = it.product
                        product.stock += it.quantity
                        product.save()

            return redirect('/order_list/')

    else:
        order_form = OrderForm()
        formset = ItemFormSet()

    return render(request, 'create_order.html', {
        'order_form': order_form,
        'formset': formset
    })
    
    
    



def dashboard(request):

    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    total_stock = Product.objects.aggregate(total=Sum('stock'))['total'] or 0

    low_stock_products = Product.objects.filter(stock__lte=5)

    recent_orders = Order.objects.all().order_by('-id')[:5]

    return render(request, 'dashboard.html', {
        'total_products': total_products,
        'total_orders': total_orders,
        'total_stock': total_stock,
        'low_stock_products': low_stock_products,
        'recent_orders': recent_orders
    })
    
    



def order_list(request):
    search  = request.GET.get('q')
    status = request.GET.get('status')
    portal = request.GET.get('portal')

    orders = Order.objects.all().order_by('-id').prefetch_related(Prefetch('orderitem_set', queryset=OrderItem.objects.select_related('product')))
    
    if status:
        orders = orders.filter(status=status)

    if portal:
        orders = orders.filter(portal=portal)

    if search:
        orders = orders.filter(order_number__icontains=search)

    return render(request, 'order_list.html', {
        'orders': orders,
    })
    
    

def delete_order(request, pk):

    order = get_object_or_404(Order, id=pk)

    # 🔁 restore stock
    items = OrderItem.objects.filter(order=order)

    for item in items:
        product = item.product
        product.stock += item.quantity
        product.save()

    order.delete()

    messages.success(request, "Order deleted successfully")
    return redirect('/orders/')



def export_orders(request):

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="orders.csv"'

    writer = csv.writer(response)

    # HEADER
    writer.writerow([
        'Order No', 'Customer', 'Invoice No', 'Invoice Date', 'Ship Date',
        'Portal', 'Status', 'State', 'State Code',
        'Qty', 'Amount', 'Fulfilment', 'B2B', 'GST',
        'SKU', 'Material Code'
    ])

    orders = Order.objects.all().prefetch_related('orderitem_set')

    for o in orders:
        for item in o.orderitem_set.all():
            writer.writerow([
                o.order_number,
                o.customer_name,
                o.invoice_number,
                o.invoice_date,
                o.ship_date,
                o.portal,
                o.status,
                o.state,
                o.state_code,
                item.quantity,
                item.price,
                o.fulfilment,
                o.is_b2b,
                o.gst_number,
                item.product.sku,
                item.product.material_code
            ])

    return response