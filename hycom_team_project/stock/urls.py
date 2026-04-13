from django.urls import path
from . import views
from .views import product_list, edit_product, delete_product

urlpatterns = [
    path('products/', product_list),
    path('product/edit/<int:pk>/', edit_product),
    path('product/delete/<int:pk>/', delete_product),
]