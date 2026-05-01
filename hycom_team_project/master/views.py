from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import json
from .models import Order, OrderItem
from stock.models import Product
from django.shortcuts import render, redirect
from django.forms import formset_factory, modelformset_factory
from .forms import OrderForm, OrderItemForm
from django.db.models import Sum
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Q, Prefetch, Sum, F, Count
import csv
from django.http import HttpResponse
from decimal import Decimal
from returns.models import ReturnItem
from django.forms import modelformset_factory
from django.db import transaction
from datetime import date
from returns.models import Return
from utils.google_sheets import push_order_to_sheet
from utils.email_service import send_order_email
import threading
from django.db import transaction


def run_async(func, *args):
    thread = threading.Thread(target=func, args=args, daemon=True)
    thread.start()



def update_stock_for_order(order, reverse=False):
    """
    reverse=True → add stock back
    reverse=False → deduct stock
    """

    for item in order.items.all():
        product = item.product

        if reverse:
            product.stock += item.quantity
        else:
            if product.stock < item.quantity:
                raise Exception(f"Not enough stock for {product.name}")
            product.stock -= item.quantity

        product.save()



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



# def create_order(request):

#     if request.method == 'POST':
#         order_form = OrderForm(request.POST)
#         formset = OrderItemForm(request.POST)

#         if order_form.is_valid() and formset.is_valid():

#             try:
#                 with transaction.atomic():

#                     order = order_form.save()

#                     items = formset.save(commit=False)

#                     for item in items:
#                         product = item.product
#                         qty = item.quantity

#                         # ❌ VALIDATION: prevent negative stock
#                         if product.stock < qty:
#                             raise Exception(f"Not enough stock for {product.name}")

#                         # ✅ Reduce stock
#                         product.stock -= qty
#                         product.save()

#                         item.order = order
#                         item.save()
#                 messages.success(request, "Order saved successfully")
#                 return redirect('/orders/')

#             except Exception as e:
#                 messages.error(request, "Something went wrong")
#                 return render(request, 'create_order.html', {
#                     'order_form': order_form,
#                     'formset': formset,
#                     'error': str(e)
#                 })

#     else:
#         order_form = OrderForm()
#         formset = OrderItemForm()

#     return render(request, 'create_order.html', {
#         'order_form': order_form,
#         'formset': formset
#     })
        
        

def restore_old_stock(order):
    old_items = OrderItem.objects.filter(order=order)

    for item in old_items:
        product = item.product
        product.stock += item.quantity
        product.save()

    old_items.delete()



def edit_order(request, pk):

    order_model = Order
    order = get_object_or_404(Order, pk=pk)

    ItemFormSet = modelformset_factory(
        OrderItem,
        form=OrderItemForm,
        extra=0,
        can_delete=True
    )

    queryset = OrderItem.objects.filter(order=order)

    if request.method == 'POST':

        order_form = OrderForm(request.POST, instance=order)
        formset = ItemFormSet(request.POST, queryset=queryset)

        if order_form.is_valid() and formset.is_valid():

            try:
                with transaction.atomic():

                    old_status = order_model.objects.filter(id=order.id).values_list('status', flat=True).first()
                    # old_ship_date = order.ship_date

                    # ✅ SAVE ORDER (commit=False)
                    order = order_form.save(commit=False)

                    # ✅ SHIP DATE FIX
                    # if not order.ship_date:
                    #     order.ship_date = old_ship_date

                    # if order.status == 'Shipped' and not old_ship_date:
                    #     order.ship_date = date.today()
                    if order.status == 'Shipped' and not order.ship_date:
                        messages.error(request, "Please select Ship Date when status is Shipped")
                        return redirect(request.path)

                    # if order.status == 'Return In Transit':
                        
                    # ✅ REPLACEMENT LOGIC
                    if order.status == 'Return Arrived':

                        is_replacement = (request.POST.get("is_replacement") or "").lower()

                        if is_replacement == "yes":

                            replacement_id = (request.POST.get("replacement_order_id") or "").strip()

                            if not replacement_id:
                                raise Exception("Replacement Order ID is required")

                            try:
                                replacement_order = Order.objects.get(order_number=replacement_id)
                            except Order.DoesNotExist:
                                raise Exception("Invalid Replacement Order ID")

                            if replacement_order.id == order.id:
                                raise Exception("Order cannot replace itself")

                            order.is_replacement = True
                            order.replacement_for = replacement_order

                        else:
                            order.is_replacement = False
                            order.replacement_for = None

                    else:
                        order.is_replacement = False
                        order.replacement_for = None

                    # ✅ SAVE ORDER ONCE
                    order.save()

                    # ✅ HANDLE ITEMS (NO STOCK LOGIC HERE)
                    items = formset.save(commit=False)

                    for obj in formset.deleted_objects:
                        obj.delete()

                    for item in items:
                        product = item.product
                        price = item.price or product.selling_price

                        item.order = order
                        item.price = price
                        item.save()
                    
                    if old_status != order.status:
                        try:
                            transaction.on_commit(lambda: run_async(send_order_email, order, True))
                        except Exception as e:
                            print("Email failed:", e)
                    
                    try:
                        transaction.on_commit(lambda: run_async(push_order_to_sheet, order))
                    except Exception as e:
                        import traceback
                        print("GOOGLE SYNC ERROR:")
                        traceback.print_exc()
                        
                    already_processed = Return.objects.filter(order=order).exists()
                    if order.status in ['Return Arrived', 'Cancelled']:
                        if already_processed:
                            messages.warning(request, "Return/Cancellation already processed")
                            return redirect('/api/order_list/')
                        return redirect(f'/returns/create/?order_id={order.id}')

                    messages.success(request, "Order updated successfully")
                    return redirect('/api/order_list/')

            except Exception as e:
                messages.error(request, str(e))

        else:
            print("ORDER ERR:", order_form.errors)
            print("FORMSET ERR:", formset.errors)
            messages.error(request, "Please fix form errors")

    else:
        order_form = OrderForm(instance=order)
        formset = ItemFormSet(queryset=queryset)

    return render(request, 'edit_order.html', {
        'order_form': order_form,
        'formset': formset,
        'order': order
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

    ItemFormSet = formset_factory(OrderItemForm, extra=1)

    if request.method == 'POST':
        order_form = OrderForm(request.POST)
        formset = ItemFormSet(request.POST)

        if order_form.is_valid() and formset.is_valid():

            try:
                with transaction.atomic():

                    # ✅ STEP 1: Create order (NOT saved fully yet)
                    order = order_form.save(commit=False)
                    order.amount = 0
                    order.gst = 0
                    order.cgst = 0
                    order.sgst = 0
                    order.igst = 0
                    order.total_amount = 0
                    order.save()   # MUST save before using FK

                    valid_items = 0

                    # ✅ STEP 2: Save items with validation
                    for form in formset:
                        data = form.cleaned_data

                        if not data or not data.get('product') or not data.get('quantity'):
                            continue

                        product = data['product']
                        qty = data['quantity']
                        price = data.get('price') or product.selling_price

                        # 🔴 STOCK VALIDATION
                        if not order.is_stock_updated:
                            if product.stock < qty:
                                raise Exception(f"Not enough stock for {product.name}")

                            # ✅ Reduce stock
                            product.stock -= qty
                            product.save()

                        item = form.save(commit=False)
                        item.order = order
                        item.price = price
                        item.save()

                        valid_items += 1

                    # ❌ No items
                    if valid_items == 0:
                        raise Exception("At least one valid item is required")

                    # ✅ STEP 3: Calculate totals
                    amount = Decimal('0')
                    gst_total = Decimal('0')

                    for it in order.items.all():
                        total = it.quantity * it.price  # already Decimal

                        base = total / Decimal('1.05')
                        gst = total - base

                        amount += base
                        gst_total += gst

                    order.amount = round(amount, 2)
                    order.gst = round(gst_total, 2)

                    # ✅ STEP 4: GST Split
                    print("STATE CODE:,,,,,,,", order.state.code if order.state else "NO STATE")
                    state_code = (order.state.code if order.state and order.state.code else "")
                    print("STATE CODE AFTER STRIP:,,,,,,,", state_code)
                    if state_code == '33':
                        print("INTRA-STATE ORDER - APPLYING CGST/SGST SPLIT")
                        order.cgst = round(order.gst / 2, 2)
                        order.sgst = round(order.gst / 2, 2)
                        order.igst = 0
                    else:
                        order.igst = round(order.gst, 2)
                        order.cgst = 0
                        order.sgst = 0

                    # ✅ STEP 5: Final total
                    order.total_amount = round(order.amount + order.gst, 2)

                    order.save()
                    
                    
                    # try:
                    #     transaction.on_commit(lambda: run_async(send_order_email, order, True))
                    # except Exception as e:
                    #     print("Email failed:", e)
                    
                    try:
                        transaction.on_commit(lambda: run_async(push_order_to_sheet, order))
                    except Exception as e:
                        import traceback
                        print("GOOGLE SYNC ERROR:")
                        traceback.print_exc()
                        
                messages.success(request, "Order saved successfully")
                return redirect('/api/order_list/')

            except Exception as e:
                messages.error(request, f"Error: {str(e)}")

        else:
            messages.error(request, "Please fill all required fields correctly")

            print("ORDER FORM ERRORS:", order_form.errors)
            print("FORMSET ERRORS:", formset.errors)

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

    orders = Order.objects.all().order_by('-id').prefetch_related(Prefetch('items', queryset=OrderItem.objects.select_related('product')))
    
    if status:
        orders = orders.filter(status=status)

    if portal:
        orders = orders.filter(portal=portal)

    if search:
        orders = orders.filter(order_number__icontains=search)

    returns_data = ReturnItem.objects.values('return_obj__order') \
        .annotate(
            return_count=Count('id'),
            return_qty=Sum('quantity')
        )

    returns_map = {
        r['return_obj__order']: r for r in returns_data
    }

    for order in orders:
        data = returns_map.get(order.id, {})
        order.return_count = data.get('return_count', 0)
        order.return_qty = data.get('return_qty', 0)

    return render(request, 'order_list.html', {
        'orders': orders,
    })
    
    

def delete_order(request, pk):

    order = get_object_or_404(Order, id=pk)

    # 🔁 restore stock
    items = OrderItem.objects.filter(order=order)

    already_restored = ReturnItem.objects.filter(return_obj__order=order).exists()

    if not already_restored:
        for item in items:
            product = item.product
            product.stock += item.quantity
            product.save()

    order.delete()

    messages.success(request, "Order deleted successfully")
    return redirect('/api/order_list/')



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

    orders = Order.objects.all().prefetch_related('items')

    for o in orders:
        for item in o.items.all():
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