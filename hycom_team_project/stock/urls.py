from django.urls import path
from . import views
from .views import product_list, edit_product, delete_product, create_product, get_product_by_sku, bulk_upload_products, download_sample_products

urlpatterns = [
    path('api/get-product-by-sku/', get_product_by_sku),
    path('products/', product_list),
    path('product/add/', create_product),
    path('product/edit/<int:pk>/', edit_product),
    path('product/delete/<int:pk>/', delete_product),
    path('products/upload/', bulk_upload_products),
    path('products/sample/', download_sample_products),
]