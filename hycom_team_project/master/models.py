from django.db import models


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
        ('pending', 'Pending'),
        ('in_gate', 'In Gate'),
        ('dispatched', 'Dispatched'),
    ]
    
    portal = models.CharField(max_length=20, choices=PORTAL_CHOICES)
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    ship_date = models.DateField(null=True, blank=True)
    order_number = models.CharField(max_length=100)
    customer_name = models.CharField(max_length=200)
    fulfilment = models.CharField(max_length=20, choices=FULFILMENT_CHOICES)
    is_b2b = models.BooleanField()
    gst_number = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    state_code = models.CharField(max_length=10)
    unit_quantity = models.IntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gst = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
    remarks = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)