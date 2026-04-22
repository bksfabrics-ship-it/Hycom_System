from django.shortcuts import render
from django.db.models import Q
from .models import Product
# Create your views here.
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

    if request.method == 'POST':

        # =========================
        # STEP 1 — PREVIEW
        # =========================
        if 'preview' in request.POST and request.FILES.get('file'):

            file = request.FILES['file']

            try:
                # READ FILE
                if file.name.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)

                # CLEAN COLUMNS
                df.columns = [c.strip().lower() for c in df.columns]

                # VALIDATE COLUMNS
                missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
                if missing:
                    messages.error(request, f"Missing columns: {', '.join(missing)}")
                    return redirect('/stock/products/upload/')

                # SAVE IN SESSION (IMPORTANT)
                request.session['upload_data'] = df.to_json()

                # SEND PREVIEW (TOP 20 ROWS)
                return render(request, 'bulk_upload_products.html', {
                    'preview': df.head(20).to_dict(orient='records')
                })

            except Exception as e:
                messages.error(request, f"Preview failed: {str(e)}")
                return redirect('/stock/products/upload/')

        # =========================
        # STEP 2 — CONFIRM SAVE
        # =========================
        if 'confirm' in request.POST:

            try:
                df = pd.read_json(request.session.get('upload_data'))

                created = 0
                updated = 0
                errors = []

                for idx, row in df.iterrows():
                    try:
                        sku = str(row['sku']).strip()

                        product, created_flag = Product.objects.update_or_create(
                            sku=sku,
                            defaults={
                                'name': str(row['name']).strip(),
                                'material_code': str(row['material_code']).strip(),
                                'style': str(row['style']).strip(),
                                'gender': str(row['gender']).strip(),
                                'color': str(row['color']).strip(),
                                'size': str(row['size']).strip(),
                                'category': str(row['category']).strip(),
                                'stock': int(row['stock']) if pd.notna(row['stock']) else 0,
                                'selling_price': float(row['selling_price']) if pd.notna(row['selling_price']) else 0,
                                'is_active': True
                            }
                        )

                        if created_flag:
                            created += 1
                        else:
                            updated += 1

                    except Exception as e:
                        errors.append(f"Row {idx + 2}: {str(e)}")

                # SUCCESS MESSAGE
                messages.success(request, f"{created} created, {updated} updated")

                if errors:
                    messages.warning(request, f"{len(errors)} rows failed")

                # CLEAR SESSION (GOOD PRACTICE)
                request.session.pop('upload_data', None)

                return redirect('/stock/products/')

            except Exception as e:
                messages.error(request, f"Upload failed: {str(e)}")
                return redirect('/stock/products/upload/')

    # DEFAULT LOAD
    return render(request, 'bulk_upload_products.html')





def download_sample_products(request):

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="product_sample.csv"'

    writer = csv.writer(response)

    writer.writerow([
        'name','sku','material_code','style','gender',
        'color','size','category','stock','selling_price'
    ])

    writer.writerow([
        'Flexi Scrub Top','HY-FLEXI-W-BL-XS','MC001','Flexi',
        'Female','Blue','XS','Medical Scrubs','50','799'
    ])

    return response