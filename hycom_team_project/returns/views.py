from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import ReturnItem


from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ReturnItemForm

def create_return(request):

    order_id = request.GET.get('order_id')

    if request.method == 'POST':
        form = ReturnItemForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Return recorded successfully")
            return redirect('/api/order_list/')

    else:
        form = ReturnItemForm()

        # ✅ Prefill order
        if order_id:
            form.fields['order'].initial = order_id

    return render(request, 'create_return.html', {'form': form})




def add_return_to_stock(request, return_id):

    return_item = get_object_or_404(ReturnItem, id=return_id)

    if return_item.condition != 'good':
        messages.error(request, "Item is not in good condition")
        return redirect('/api/order_list/')

    if return_item.is_stock_added:
        messages.warning(request, "Stock already added")
        return redirect('/api/order_list/')

    product = return_item.product
    product.stock += return_item.quantity
    product.save()

    return_item.is_stock_added = True
    return_item.save()

    messages.success(request, "Stock added successfully")

    return redirect('/api/order_list/')


from django.http import JsonResponse
from master.models import OrderItem

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