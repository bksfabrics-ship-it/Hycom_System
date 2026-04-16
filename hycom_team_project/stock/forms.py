from django import forms
from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'material_code', 'style', 'gender', 'color', 'size',
            'category', 'stock', 'selling_price', 'is_active'
        ]