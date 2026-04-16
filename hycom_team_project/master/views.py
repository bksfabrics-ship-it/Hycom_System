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
        
        



def get_product_by_sku(request):
    sku = request.GET.get('sku')

    try:
        product = Product.objects.get(sku=sku)

        return JsonResponse({"id": product.id, "name": product.name, "price": float(product.selling_price or 0)})

    except Product.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)
    


def create_order_ui(request):

    ItemFormSet = formset_factory(OrderItemForm, extra=3)

    if request.method == 'POST':
        order_form = OrderForm(request.POST)
        formset = ItemFormSet(request.POST)

        if order_form.is_valid() and formset.is_valid():

            with transaction.atomic():

                order = order_form.save()

                for form in formset:
                    if form.cleaned_data:
                        item = form.save(commit=False)
                        item.order = order
                        item.save()

            return redirect('/orders-ui/')

    else:
        order_form = OrderForm()
        formset = ItemFormSet()

    return render(request, 'create_order.html', {
        'order_form': order_form,
        'formset': formset
    })
    
    
    
from django.shortcuts import render
from stock.models import Product
from .models import Order


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
    
    
from django.db.models import Q
from .models import Order


def order_list(request):
    query = request.GET.get('q')

    if query:
        orders = Order.objects.filter(
            Q(order_number__icontains=query) |
            Q(customer_name__icontains=query) |
            Q(portal__icontains=query)
        ).order_by('-id')
    else:
        orders = Order.objects.all().order_by('-id')

    return render(request, 'order_list.html', {
        'orders': orders,
        'query': query
    })