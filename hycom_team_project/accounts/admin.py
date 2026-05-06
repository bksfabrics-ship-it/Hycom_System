from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import EmployeeProfile

User = get_user_model()


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "designation", "is_approved", "employee_id", "created_at")
    list_filter = ("is_approved", "designation")
    search_fields = ("user__username", "user__email", "employee_id", "name")

    def has_change_permission(self, request, obj=None):
        return True

