from django.urls import path
from .views import create_return, get_order_products


urlpatterns = [
path('create/', create_return, name='create_return'),
path('api/get-order-products/', get_order_products),
]