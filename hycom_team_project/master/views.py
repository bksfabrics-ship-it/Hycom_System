from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import json
from .models import Order, OrderItem
from stock.models import Product
from django.shortcuts import render, redirect
from django.forms import formset_factory
from .forms import OrderForm, OrderItemForm



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



@csrf_exempt
def create_order(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            with transaction.atomic():  # 👈 ADD HERE

                # Create Order
                order = Order.objects.create(
                    portal=data['portal'],
                    order_number=data['order_number'],
                    customer_name=data['customer_name'],
                    invoice_number=data['invoice_number'],
                    invoice_date=data['invoice_date'],
                    fulfilment=data['fulfilment'],
                    is_b2b=data['is_b2b'],
                    gst_number=data.get('gst_number'),
                    state_code=data['state_code'],
                    amount=data['amount'],
                    gst=data['gst'],
                    remarks=data.get('remarks', '')
                )

                # Create Order Items
                for item in data['items']:
                    product = Product.objects.get(id=item['product_id'])

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=item['quantity'],
                        price=item['price']
                    )

            return JsonResponse({"message": "Order created successfully"})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
        
        



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