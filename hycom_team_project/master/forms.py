from django import forms
from .models import Order, OrderItem, Product


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order

        # ✅ ONLY include user-input fields
        exclude = ['amount', 'gst', 'cgst', 'sgst', 'igst', 'total_amount']

        widgets = {
            'portal': forms.Select(attrs={'class': 'form-control', 'required': True}),
            'invoice_number': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'order_number': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'invoice_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'ship_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()

        # Optional validation (only if needed)
        invoice = cleaned_data.get('invoice_number')

        if not invoice:
            self.add_error('invoice_number', "Invoice number is required")

        return cleaned_data



class OrderItemForm(forms.ModelForm):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), widget=forms.Select(attrs={'class': 'form-control product-dropdown'}))

    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'price']