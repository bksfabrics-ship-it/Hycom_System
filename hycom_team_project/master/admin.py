from django.contrib import admin
from .models import InvoiceSetting, NotificationSetting, Order, OrderItem, State

admin.site.register(State)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(InvoiceSetting)
admin.site.register(NotificationSetting)
