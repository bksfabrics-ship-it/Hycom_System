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
        super().save(*args, **kwargs)
            

class ReturnItem(models.Model):

    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    item_arrived_date = models.DateField(null=True, blank=True)
    customer_review = models.TextField(blank=True)

    quality_check = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('verified', 'Verified')
    ], default='pending')

    checked_by = models.CharField(max_length=100, blank=True)
    qc_date = models.DateField(null=True, blank=True)
    qc_review = models.TextField(blank=True)

    condition = models.CharField(max_length=20, choices=[
        ('good', 'Good'),
        ('damaged', 'Damaged')
    ])

    is_stock_added = models.BooleanField(default=False)