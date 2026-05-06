from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.employee_register, name="employee_register"),
    path(
        "password-change/",
        views.employee_password_change,
        name="employee_password_change",
    ),
]

