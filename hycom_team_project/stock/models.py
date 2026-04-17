from django.db import models

# Create your models here.
class Product(models.Model):
    STYLE_CHOICES = [
    ('Core', 'Core'),
    ('Flexi', 'Flexi'),
    ('Ethos', 'Ethos'),
]

    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
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
        ('XXL', 'XXL'),
    ]

    CATEGORY_CHOICES = [
        ('Medical Scrubs', 'Medical Scrubs'),
        ('Labcoats', 'Labcoats'),
        ('Doctor Coats', 'Doctor Coats'),
        ('Inner Scrubs', 'Inner Scrubs'),
    ]

    # Basic Info
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, unique=True)
    material_code = models.CharField(max_length=100, null=True, blank=True)

    # Variants (important for apparel like yours)
    style = models.CharField(max_length=50)
    color = models.CharField(max_length=50)
    size = models.CharField(max_length=10)
    gender = models.CharField(max_length=20)  

    # Category (optional but useful)
    category = models.CharField(max_length=100)

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
        return f"{self.name} -{self.style} -{self.gender} - {self.color} - {self.size}"
    class Meta:
        unique_together = ['name', 'style', 'gender', 'color', 'size']