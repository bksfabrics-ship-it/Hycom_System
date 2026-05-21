from django.urls import path
from .views import (
    order_report,
    return_report,
    stock_report,
    export_order_report,
    export_return_report,
    export_stock_report,
    order_detail_view,
)

urlpatterns = [
    path('order_report/', order_report, name='order_report'),
    path('return_report/', return_report, name='return_report'),
    path('stock_report/', stock_report, name='stock_report'),
    path('export_order_report/', export_order_report, name='export_order_report'),
    path('export_return_report/', export_return_report, name='export_return_report'),
    path('export_stock_report/', export_stock_report, name='export_stock_report'),
    path('order_report/view/<int:order_id>/', order_detail_view, name='order_detail_view'),
]

