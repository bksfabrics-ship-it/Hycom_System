from django import forms
from .models import ReturnItem
from master.models import Product
from django.forms import formset_factory
# class ReturnItemForm(forms.ModelForm):

#     class Meta:
#         model = ReturnItem
#         fields = ['order', 'product', 'quantity', 'condition']

#         widgets = {
#             'order': forms.Select(attrs={'class': 'form-control'}),
#             'product': forms.Select(attrs={'class': 'form-control'}),
#             'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
#             'condition': forms.Select(attrs={'class': 'form-control'}),
#         }
    
#     def __init__(self, *args, **kwargs):
#         order = kwargs.pop('order', None)
#         super().__init__(*args, **kwargs)

#         if order:
#             self.fields['product'].queryset = order.items.values_list('product', flat=True)



class ReturnItemForm(forms.ModelForm):
    class Meta:
        model = ReturnItem
        fields = ['product', 'quantity', 'condition', 'item_arrived_date']
        
    def __init__(self, *args, **kwargs):
        order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)

        if order:
            product_ids = order.items.values_list('product_id', flat=True)

            self.fields['product'].queryset = Product.objects.filter(id__in=product_ids)

            # OPTIONAL: better labels
            self.fields['product'].label_from_instance = lambda obj: (
                f"{obj.name} ({obj.sku}) - Ordered: "
                f"{order.items.get(product=obj).quantity}"
            )
            
    def clean(self):
        cleaned_data = super().clean()

        product = cleaned_data.get('product')
        qty = cleaned_data.get('quantity')

        if self.initial.get('order'):
            order = self.initial['order']

        if product and qty:
            ordered_qty = order.items.get(product=product).quantity

            if qty > ordered_qty:
                raise forms.ValidationError(f"Cannot return more than ordered ({ordered_qty})")

        return cleaned_data
            


ReturnItemFormSet = formset_factory(ReturnItemForm, extra=3)