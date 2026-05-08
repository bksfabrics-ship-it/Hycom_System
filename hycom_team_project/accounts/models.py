from django.conf import settings
from django.db import models
from django.contrib.auth.models import User


class EmployeeProfile(models.Model):
    class Meta:
        app_label = "accounts"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    name = models.CharField(max_length=150)
    designation = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=30)

    employee_id = models.CharField(max_length=50, null=True, blank=True)

    # Admin approval flag
    is_approved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({'approved' if self.is_approved else 'pending'})"




class AreaPermission(models.Model):
    AREA_CHOICES = [
        ('dashboard', 'Dashboard'),
        ('orders', 'Orders'),
        ('products', 'Products'),
        ('reports', 'Reports'),
        ('user_management', 'User Management'),
    ]


    user = models.ForeignKey(User, on_delete=models.CASCADE)
    area = models.CharField(max_length=50, choices=AREA_CHOICES)

    class Meta:
        unique_together = ('user', 'area')

    def __str__(self):
        return f"{self.user.username} - {self.area}"
