from django import forms
from .models import Order, OrderItem


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'portal', 'order_number', 'customer_name',
            'invoice_number', 'invoice_date', 'ship_date',
            'fulfilment', 'is_b2b', 'gst_number',
            'state_code', 'amount', 'gst', 'remarks'
        ]


class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'price']