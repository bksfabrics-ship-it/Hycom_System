from django.urls import path
from . import views
from .views import (
    bulk_upload_products,
    create_product,
    delete_product,
    download_sample_products,
    edit_product,
    export_products,
    get_product_by_sku,
    invoice_converter,
    product_list,
)

urlpatterns = [
    path('api/get-product-by-sku/', get_product_by_sku),
    path('products/', product_list),
    path('products/export/', export_products),
    path('product/add/', create_product),
    path('product/edit/<int:pk>/', edit_product),
    path('product/delete/<int:pk>/', delete_product),
    path('products/upload/', bulk_upload_products),
    path('products/sample/', download_sample_products),
    path('invoice-converter/', invoice_converter, name='invoice_converter'),
]
