from django.shortcuts import render
from django.db.models import Q
from .models import Product
# Create your views here.
from django.shortcuts import render, redirect
from .forms import ProductForm


def create_product(request):

    if request.method == 'POST':
        form = ProductForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('/stock/product/add/')

    else:
        form = ProductForm()

    return render(request, 'create_product.html', {'form': form})



def product_list(request):
    query = request.GET.get('q')

    if query:
        products = Product.objects.filter(
            Q(sku__icontains=query) |
            Q(material_code__icontains=query) |
            Q(name__icontains=query)
        )
    else:
        products = Product.objects.all().order_by('-id')

    return render(request, 'product_list.html', {
        'products': products,
        'query': query
    })
    
    
    
def edit_product(request, pk):
    product = Product.objects.get(id=pk)

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect('/stock/products/')
    else:
        form = ProductForm(instance=product)

    return render(request, 'create_product.html', {'form': form})


def delete_product(request, pk):
    product = Product.objects.get(id=pk)
    product.delete()
    return redirect('/stock/products/')