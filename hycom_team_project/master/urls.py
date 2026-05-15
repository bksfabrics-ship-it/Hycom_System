from django.urls import path
from .views import (
    get_orders,
    create_order_ui,
    get_product_by_sku,
    dashboard,
    order_list,
    edit_order,
    delete_order,
    order_invoice,
    export_orders,
    export_dashboard_excel,
)
from django.contrib.auth import views as auth_views

urlpatterns = [
    # path('orders/create/', create_order),
    path('orders/edit/<int:pk>/', edit_order),
    path('orders/delete/<int:pk>/', delete_order),
    path('orders/invoice/<int:pk>/', order_invoice, name='order_invoice'),
    path('order_list/', order_list, name='order_list'),
    path('orders/', get_orders),
    path('orders-ui/', create_order_ui),
    path('get-product-by-sku/', get_product_by_sku),
    path('api/get-product-by-sku/', get_product_by_sku),
    path('', dashboard),
    path('order-export/', export_orders),
    path('dashboard_export/', export_dashboard_excel),
    
    # # Forgot password
    # path('password-reset/',auth_views.PasswordResetView.as_view(template_name='accounts/password_reset.html'),name='password_reset'),

    # # Email sent page
    # path('password-reset/done/',auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),name='password_reset_done'),

    # # Reset link page
    # path('reset/<uidb64>/<token>/',auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html'),name='password_reset_confirm'),

    # # Password reset complete
    # path('reset/done/',auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'),name='password_reset_complete'),

]