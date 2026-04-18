from django.shortcuts import render
from django.db.models import Q
from .models import Product
# Create your views here.
from django.shortcuts import render, redirect
from .forms import ProductForm
from django.contrib import messages


def create_product(request):

    if request.method == 'POST':
        form = ProductForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Product saved successfully")
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
            messages.success(request, "Product updated")
            return redirect('/stock/products/')
    else:
        form = ProductForm(instance=product)

    return render(request, 'create_product.html', {'form': form})


def delete_product(request, pk):
    product = Product.objects.get(id=pk)
    product.delete()
    messages.success(request, "Product deleted")
    return redirect('/stock/products/')


from django.http import JsonResponse
from .models import Product


def get_product_by_sku(request):
    sku = request.GET.get('sku')

    try:
        product = Product.objects.get(sku=sku)

        data = {
            'material_code': product.material_code,
            'name': product.name,
            'price': product.selling_price,
        }

        return JsonResponse(data)

    except Product.DoesNotExist:
        return JsonResponse({'error': 'Not found'})
    
    
    
import pandas as pd
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Product

REQUIRED_COLUMNS = [
    'name', 'sku', 'material_code', 'style',
    'gender', 'color', 'size', 'category',
    'stock', 'selling_price'
]


def bulk_upload_products(request):

    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']

        try:
            # detect file type
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)

            # normalize columns
            df.columns = [c.strip().lower() for c in df.columns]

            # validate required columns
            missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
            if missing:
                messages.error(request, f"Missing columns: {', '.join(missing)}")
                return redirect('/stock/products/upload/')

            created, skipped, errors = 0, 0, []

            for idx, row in df.iterrows():
                try:
                    sku = str(row['sku']).strip()

                    # skip duplicates
                    if Product.objects.filter(sku=sku).exists():
                        skipped += 1
                        continue

                    Product.objects.create(
                        name=str(row['name']).strip(),
                        sku=sku,
                        material_code=str(row['material_code']).strip(),
                        style=str(row['style']).strip(),
                        gender=str(row['gender']).strip(),
                        color=str(row['color']).strip(),
                        size=str(row['size']).strip(),
                        category=str(row['category']).strip(),
                        stock=int(row['stock']) if pd.notna(row['stock']) else 0,
                        selling_price=float(row['selling_price']) if pd.notna(row['selling_price']) else 0,
                        is_active=True
                    )

                    created += 1

                except Exception as e:
                    errors.append(f"Row {idx+2}: {str(e)}")

            # messages
            if created:
                messages.success(request, f"{created} products uploaded successfully")
            if skipped:
                messages.warning(request, f"{skipped} duplicate SKUs skipped")
            if errors:
                messages.error(request, "Some rows failed. Check below.")

            return render(request, 'bulk_upload_products.html', {
                'errors': errors[:20]  # show first 20 errors
            })

        except Exception as e:
            messages.error(request, f"Upload failed: {str(e)}")
            return redirect('/stock/products/upload/')

    return render(request, 'bulk_upload_products.html')