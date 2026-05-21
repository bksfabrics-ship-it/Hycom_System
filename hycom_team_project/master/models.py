from django.db import models
from stock.models import Product
from django.utils import timezone
from django.core.exceptions import ValidationError

class State(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=5)

    def __str__(self):
        return f"{self.name} ({self.code})"


class InvoiceSetting(models.Model):
    company_name = models.CharField(max_length=200, default="Hycom")
    company_subtitle = models.CharField(max_length=200, blank=True, default="Management System")
    company_address = models.TextField(blank=True, default="")
    company_phone = models.CharField(max_length=50, blank=True, default="")
    company_email = models.EmailField(blank=True, default="")
    company_gstin = models.CharField(max_length=30, blank=True, default="")
    footer_note = models.TextField(blank=True, default="This is a system generated invoice.")
    signature_label = models.CharField(max_length=100, default="Authorised Signature")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class NotificationSetting(models.Model):
    CATEGORY_ORDER_UPDATE = 'ORDER_UPDATE'
    CATEGORY_INVOICE = 'INVOICE'

    CATEGORY_CHOICES = [
        (CATEGORY_ORDER_UPDATE, 'Order Update'),
        (CATEGORY_INVOICE, 'Invoice'),
    ]

    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    email = models.EmailField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('category', 'email')
        indexes = [
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self):
        status = 'active' if self.is_active else 'inactive'
        return f"{self.category} - {self.email} ({status})"

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
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)
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
    stock_restored = models.BooleanField(default=False)
    # Location
    amount = models.FloatField(null=True, blank=True)
    gst = models.FloatField(null=True, blank=True)
    cgst = models.FloatField(null=True, blank=True)
    sgst = models.FloatField(null=True, blank=True)
    igst = models.FloatField(null=True, blank=True) 
    total_amount = models.FloatField(null=True, blank=True)

    # Misc
    remarks = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_replacement = models.BooleanField(default=False)
    replacement_for = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)


    def clean(self):
        errors = {}

        # ✅ B2B validation
        if self.is_b2b and not self.gst_number:
            errors['gst_number'] = "GST number required for B2B orders"

        # ✅ Duplicate order number
        if Order.objects.filter(order_number=self.order_number).exclude(pk=self.pk).exists():
            errors['order_number'] = "Order number already exists"

        # ✅ Duplicate invoice number
        if Order.objects.filter(invoice_number=self.invoice_number).exclude(pk=self.pk).exists():
            errors['invoice_number'] = "Invoice number already exists"

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # ✅ Ensure clean() is always called
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number
    
    
    

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):

        # # Handle update case (avoid double deduction)
        # if self.pk:
        #     old = OrderItem.objects.get(pk=self.pk)
        #     self.product.stock += old.quantity

        # # Check stock
        # if self.product.stock < self.quantity:
        #     raise ValueError("Not enough stock")

        # # Reduce stock
        # self.product.stock -= self.quantity
        # self.product.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"
    
    def delete(self, *args, **kwargs):
        self.product.stock += self.quantity
        self.product.save()
        super().delete(*args, **kwargs)

    
    
