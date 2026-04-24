from django.db import models
from stock.models import Product
from django.utils import timezone

class Order(models.Model):

    PORTAL_CHOICES = [
        ('amazon', 'Amazon'),
        ('flipkart', 'Flipkart'),
        ('own', 'Own Site'),
        ('ondc', 'ONDC'),
    ]

    FULFILMENT_CHOICES = [
        ('amazon', 'Amazon'),
        ('self', 'Self'),
        ('flipkart', 'Flipkart'),
    ]

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Shipped', 'Shipped'),
        ('Cancelled', 'Cancelled'),
        ('Return In Transit', 'Return In Transit'),
        ('Return Arrived', 'Return Arrived'),]

    # Basic Details
    portal = models.CharField(max_length=20, choices=PORTAL_CHOICES)
    order_number = models.CharField(max_length=100)
    customer_name = models.CharField(max_length=200)
    state = models.CharField(max_length=100, blank=True, null=True)
    state_code = models.CharField(max_length=10, blank=True, null=True)

    # Invoice Details
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    ship_date = models.DateField(null=True, blank=True)

    # Fulfilment
    fulfilment = models.CharField(max_length=20, choices=FULFILMENT_CHOICES)

    # B2B
    is_b2b = models.BooleanField(default=False)
    gst_number = models.CharField(max_length=20, null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_stock_updated = models.BooleanField(default=False)
    # Location
    state_code = models.CharField(max_length=10)

    # Financials
    amount = models.FloatField(null=True, blank=True)
    gst = models.FloatField(null=True, blank=True)
    cgst = models.FloatField(null=True, blank=True)
    sgst = models.FloatField(null=True, blank=True)
    igst = models.FloatField(null=True, blank=True) 
    total_amount = models.FloatField(null=True, blank=True)

    # Misc
    remarks = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Auto total calculation
        # self.total_amount = self.amount + self.gst
        if self.status == 'shipped' and not self.ship_date:
            self.ship_date = timezone.now().date()

        # Validation
        if self.is_b2b and not self.gst_number:
            raise ValueError("GST number required for B2B orders")

        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number
    
    
    
    

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):

        # Handle update case (avoid double deduction)
        if self.pk:
            old = OrderItem.objects.get(pk=self.pk)
            self.product.stock += old.quantity

        # Check stock
        if self.product.stock < self.quantity:
            raise ValueError("Not enough stock")

        # Reduce stock
        self.product.stock -= self.quantity
        self.product.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"
    
    def delete(self, *args, **kwargs):
        self.product.stock += self.quantity
        self.product.save()
        super().delete(*args, **kwargs)
        
    
    
    