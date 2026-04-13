from django.db import models

# Create your models here.
class Product(models.Model):

    # Basic Info
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, unique=True)
    material_code = models.CharField(max_length=100, null=True, blank=True)

    # Variants (important for apparel like yours)
    color = models.CharField(max_length=50)
    size = models.CharField(max_length=20)

    # Category (optional but useful)
    category = models.CharField(max_length=100, null=True, blank=True)

    # Stock
    stock = models.IntegerField(default=0)

    # Pricing (optional but useful)
    mrp_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.color} - {self.size}"
    class Meta:
        unique_together = ['name', 'color', 'size']