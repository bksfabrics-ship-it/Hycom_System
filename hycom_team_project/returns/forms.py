from django import forms
from .models import ReturnItem

class ReturnItemForm(forms.ModelForm):

    class Meta:
        model = ReturnItem
        fields = ['order', 'product', 'quantity', 'condition']

        widgets = {
            'order': forms.Select(attrs={'class': 'form-control'}),
            'product': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
        }