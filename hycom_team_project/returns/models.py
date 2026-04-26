from django.db import models
from master.models import Order, Product
# Create your models here.
class Return(models.Model):

    RETURN_TYPE_CHOICES = [
        ('return', 'Return'),
        ('cancel', 'Cancellation'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=RETURN_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
            

class ReturnItem(models.Model):

    return_obj = models.ForeignKey(Return, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    item_arrived_date = models.DateField(null=True, blank=True)
    condition = models.CharField(max_length=20, choices=[('good', 'Good'), ('damaged', 'Damaged')])
    quality_check = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('verified', 'Verified')], default='pending')
    is_stock_added = models.BooleanField(default=False)
    customer_message = models.TextField(blank=True)
    qc_message = models.TextField(blank=True)
    qc_checked_by = models.CharField(max_length=100, blank=True)