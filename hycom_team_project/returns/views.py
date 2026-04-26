from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import ReturnItem
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ReturnItemForm
from master.models import Order
from django.http import JsonResponse
from master.models import OrderItem
from .models import Return, ReturnItem
from django.forms import formset_factory
from django.core.exceptions import ValidationError


def create_return(request):

    order_id = request.GET.get('order_id')
    order = None

    if order_id:
        order = Order.objects.get(id=order_id)

    ReturnItemFormSet = formset_factory(ReturnItemForm, extra=3)

    if request.method == 'POST':
        formset = ReturnItemFormSet(request.POST, form_kwargs={'order': order})

        if formset.is_valid():

            # ✅ CREATE RETURN
            return_obj = Return.objects.create(
                order=order,
                type='cancel' if order.status == 'Cancelled' else 'return'
            )

            for form in formset:
                data = form.cleaned_data

                if not data:
                    continue

                product = data.get('product')
                qty = data.get('quantity')
                condition = data.get('condition')

                if not product or not qty:
                    continue

                # ❗ VALIDATION: prevent over-return
                ordered_qty = order.items.get(product=product).quantity

                already_returned = sum(
                    item.quantity for item in ReturnItem.objects.filter(
                        return_obj__order=order,
                        product=product
                    )
                )

                if qty + already_returned > ordered_qty:
                    messages.error(request, f"Return qty exceeds ordered for {product.name}")
                    return redirect(request.path)

                # ✅ SAVE ITEM
                item = form.save(commit=False)
                item.return_obj = return_obj
                item.save()

                # ✅ STOCK LOGIC
                if condition == 'good' and not item.is_stock_added:

                    product.stock += qty
                    product.save()

                    item.is_stock_added = True
                    item.save()

            messages.success(request, "Return/Cancellation processed successfully")
            return redirect('/api/order_list/')

    else:
        formset = ReturnItemFormSet(form_kwargs={'order': order})

    return render(request, 'create_return.html', {
        'formset': formset,
        'order': order
    })





def get_order_products(request):

    order_id = request.GET.get('order_id')

    items = OrderItem.objects.filter(order_id=order_id).select_related('product')

    data = []

    for item in items:
        data.append({
            'id': item.product.id,
            'name': f"{item.product.name} ({item.product.sku})"
        })

    return JsonResponse(data, safe=False)