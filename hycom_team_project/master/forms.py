from django import forms
from .models import Order, OrderItem


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = '__all__'

        widgets = {
            'portal': forms.Select(attrs={'required': True}),
            'invoice_number': forms.TextInput(attrs={'required': True}),
            'order_number': forms.TextInput(attrs={'required': True}),
            'customer_name': forms.TextInput(attrs={'required': True}),
        }
    def clean(self):
        cleaned_data = super().clean()

        if not cleaned_data.get('invoice_number'):
            raise forms.ValidationError("Invoice number is required")

        return cleaned_data



class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'price']