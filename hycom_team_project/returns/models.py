from django.db import models
from master.models import Order, Product
# Create your models here.
class Return(models.Model):

    CONDITION_CHOICES = [
        ('Good', 'Good'),
        ('Damaged', 'Damaged'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    quantity = models.PositiveIntegerField()
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.condition == 'Good':
            self.product.stock += self.quantity
            self.product.save()