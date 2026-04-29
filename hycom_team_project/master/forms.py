from django import forms
from .models import Order, OrderItem, Product


class OrderForm(forms.ModelForm):
    fulfilment = forms.ChoiceField(choices=Order.FULFILMENT_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    replacement_for = forms.ModelChoiceField(queryset=Order.objects.all(), required=False)
    ship_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    class Meta:
        model = Order

        # ✅ ONLY include user-input fields
        exclude = ['amount', 'gst', 'cgst', 'sgst', 'igst', 'total_amount']

        widgets = {
            'portal': forms.Select(attrs={'class': 'form-control', 'required': True}),
            'fulfilment': forms.Select(attrs={'class': 'form-control'}),
            'invoice_number': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'order_number': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'invoice_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'ship_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes (internal use)'}),}

    def clean(self):
        cleaned_data = super().clean()

        # Optional validation (only if needed)
        invoice = cleaned_data.get('invoice_number')

        if not invoice:
            self.add_error('invoice_number', "Invoice number is required")

        return cleaned_data



class OrderItemForm(forms.ModelForm):
    product = forms.ModelChoiceField(queryset=Product.objects.all(), widget=forms.Select(attrs={'class': 'form-control product-dropdown'}))
    sku = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control sku-input'}))

    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'price']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ Populate SKU when editing
        if self.instance and self.instance.pk:
            self.fields['sku'].initial = self.instance.product.sku