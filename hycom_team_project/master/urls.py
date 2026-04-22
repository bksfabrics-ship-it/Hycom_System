from django.urls import path
from .views import create_order, get_orders, create_order_ui, get_product_by_sku, dashboard, order_list, edit_order, delete_order, export_orders

urlpatterns = [
    path('orders/create/', create_order),
    path('orders/edit/<int:pk>/', edit_order),
    path('orders/delete/<int:pk>/', delete_order),
    path('order_list/', order_list, name='order_list'),
    path('orders/', get_orders),
    path('orders-ui/', create_order_ui),
    path('get-product-by-sku/', get_product_by_sku),
    path('api/get-product-by-sku/', get_product_by_sku),
    path('', dashboard),
    path('order-export/', export_orders),

]