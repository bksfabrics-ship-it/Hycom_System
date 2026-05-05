import logging
from django.shortcuts import render
from django.db.models import Q
from .models import Product
# Create your views here.

logger = logging.getLogger(__name__)
from django.shortcuts import render, redirect
from .forms import ProductForm
from django.contrib import messages
from django.http import HttpResponse
import csv


def create_product(request):

    if request.method == 'POST':
        form = ProductForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Product saved successfully")
            user = getattr(request.user, 'username', 'Anonymous') if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous'
            logger.info(f"Product created: {form.instance.sku} ({form.instance.name}) by user {user}")
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
            messages.success(request, "Product updated successfully")
            user = getattr(request.user, 'username', 'Anonymous') if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous'
            logger.info(f"Product updated: {form.instance.sku} ({form.instance.name}) by user {user}")
            return redirect('/stock/products/')
        else:
            messages.error(request, "Please fix errors")
    else:
        form = ProductForm(instance=product)

    return render(request, 'create_product.html', {'form': form, 'product': product})


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
    
    
    
def export_products(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="products.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Name', 'SKU', 'Material Code', 'Style', 'Gender', 'Color', 'Size', 'Category', 'Warehouse', 'Stock', 'Selling Price', 'Status'])
    
    products = Product.objects.all().values_list(
        'name', 'sku', 'material_code', 'style', 'gender', 'color', 'size', 
        'category', 'warehouse', 'stock', 'selling_price', 'is_active'
    )
    
    writer.writerows(products)
    
    return response


import pandas as pd
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Product

REQUIRED_COLUMNS = [
    'name', 'sku', 'material_code', 'style',
    'gender', 'color', 'size', 'category', 'warehouse',
    'stock', 'selling_price'
]


def bulk_upload_products(request):

    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']

        try:
            # READ FILE
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)

            df.columns = [c.strip().lower() for c in df.columns]

            # VALIDATE
            missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
            if missing:
                messages.error(request, f"Missing columns: {', '.join(missing)}")
                return redirect('/stock/products/upload/')

            # ✅ PREVIEW MODE
            if 'preview' in request.POST:

                preview_data = df.head(50).to_dict(orient='records')

                # 🔴 FIND DUPLICATE SKUs
                duplicate_skus = df['sku'][df['sku'].duplicated()].unique().tolist()

                # 🟡 FIND MISSING DATA ROWS
                missing_rows = []
                for i, row in df.iterrows():
                    if row.isnull().any():
                        missing_rows.append(i)

                # SAVE DATA
                request.session['upload_data'] = df.to_dict(orient='records')

                return render(request, 'bulk_upload_products.html', {
                    'preview': preview_data,
                    'duplicate_skus': duplicate_skus,
                    'missing_rows': missing_rows
                })

            # ✅ FINAL UPLOAD
            data = request.session.get('upload_data')

            if not data:
                messages.error(request, "No preview data found. Please upload again.")
                return redirect('/stock/products/upload/')

            created, updated, errors = 0, 0, []

            for idx, row in enumerate(data):
                try:
                    product, created_flag = Product.objects.update_or_create(
                        sku=str(row['sku']).strip(),
                        defaults={
                            'name': str(row['name']).strip(),
                            'material_code': str(row['material_code']).strip(),
                            'style': str(row['style']).strip(),
                            'gender': str(row['gender']).strip(),
                            'color': str(row['color']).strip(),
                            'size': str(row['size']).strip(),
                            'category': str(row['category']).strip(),
                            'warehouse': str(row.get('warehouse', 'Hycom')).strip(),
                            'stock': int(row.get('stock', 0)),
                            'selling_price': float(row.get('selling_price', 0)),
                            'is_active': True
                        }
                    )

                    if created_flag:
                        created += 1
                    else:
                        updated += 1

                except Exception as e:
                    errors.append(f"Row {idx+2}: {str(e)}")

            messages.success(request, f"{created} created, {updated} updated")

            return render(request, 'bulk_upload_products.html', {
                'errors': errors[:20]
            })

        except Exception as e:
            messages.error(request, f"Upload failed: {str(e)}")
            return redirect('/stock/products/upload/')

    return render(request, 'bulk_upload_products.html')





def download_sample_products(request):

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="product_sample.csv"'

    writer = csv.writer(response)

    writer.writerow([
        'name','sku','material_code','style','gender',
        'color','size','category','warehouse','stock','selling_price'
    ])

    writer.writerow([
        'Flexi Scrub Top','HY-FLEXI-W-BL-XS','MC001','Flexi',
        'Female','Blue','XS','Medical Scrubs','Hycom','50','799'
    ])

    return response
