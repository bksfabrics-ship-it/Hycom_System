from django.urls import path
from .views import create_order, get_orders, create_order_ui, get_product_by_sku, dashboard

urlpatterns = [
    path('orders/create/', create_order),
    path('orders/', get_orders),
    path('orders-ui/', create_order_ui),
    path('get-product-by-sku/', get_product_by_sku),
    path('', dashboard),

]