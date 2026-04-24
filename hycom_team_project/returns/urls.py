from django.urls import path
from .views import add_return_to_stock, create_return, get_order_products


urlpatterns = [
path('add-to-stock/<int:return_id>/', add_return_to_stock, name='add_return_stock'),
path('create/', create_return, name='create_return'),
path('api/get-order-products/', get_order_products),
]