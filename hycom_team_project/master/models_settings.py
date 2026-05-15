from django.db import models


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
        return f"{self.category} - {self.email} ({'active' if self.is_active else 'inactive'})"

