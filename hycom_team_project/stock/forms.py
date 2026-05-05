from django import forms
from .models import Product


class ProductForm(forms.ModelForm):
    STYLE_CHOICES = [
    ('Core', 'Core'),
    ('Flexi', 'Flexi'),
    ('Ethos', 'Ethos'),
]
    GENDER_CHOICES = [
    ('Male', 'Male'),
    ('Female', 'Female')
]
    COLOR_CHOICES = [
    ('Wine Red', 'Wine Red'),
    ('Hunter Green', 'Hunter Green'),
    ('Ceil Blue', 'Ceil Blue'),
    ('Navy Blue', 'Navy Blue'),
]
    SIZE_CHOICES = [
    ('XS', 'XS'),
    ('S', 'S'),
    ('M', 'M'),
    ('L', 'L'),
    ('XL', 'XL'),
    ('XXL', 'XXL'),]

    WAREHOUSE_CHOICES = [
    ('Hycom', 'Hycom'),
    ('Amazon', 'Amazon'),
    ('Flipkart', 'Flipkart'),
    ]

    style = forms.ChoiceField(choices=STYLE_CHOICES)
    gender = forms.ChoiceField(choices=GENDER_CHOICES)
    color = forms.ChoiceField(choices=COLOR_CHOICES)
    size = forms.ChoiceField(choices=SIZE_CHOICES)
    warehouse = forms.ChoiceField(choices=WAREHOUSE_CHOICES)
    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'material_code', 'style', 'gender', 'color', 'size',
            'category', 'warehouse', 'stock', 'selling_price', 'is_active'
        ]
