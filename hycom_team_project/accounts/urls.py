from django.urls import path, include
from django.contrib.auth import views as auth_views

from . import views

urlpatterns = [
    path("register/", views.employee_register, name="employee_register"),
    path(
        "password-change/",
        views.employee_password_change,
        name="employee_password_change",
    ),


    # Built-in Django password reset (forgot password)
    path(
        "forgot-password/",
        include(
            (
                [
                    path(
                        "",
                        auth_views.PasswordResetView.as_view(
                            template_name="registration/password_reset_form.html",
                            email_template_name="registration/password_reset_email.txt",
                            subject_template_name="registration/password_reset_subject.txt",
                            html_email_template_name="registration/password_reset_email.html",
                        ),
                        name="password_reset",
                    ),

                    path(
                        "done/",
                        auth_views.PasswordResetDoneView.as_view(
                            template_name="registration/password_reset_done.html"
                        ),
                        name="password_reset_done",
                    ),
                    path(
                        "confirm/<uidb64>/<token>/",
                        auth_views.PasswordResetConfirmView.as_view(
                            template_name="registration/password_reset_confirm.html"
                        ),
                        name="password_reset_confirm",
                    ),
                    path(
                        "complete/",
                        auth_views.PasswordResetCompleteView.as_view(
                            template_name="registration/password_reset_complete.html"
                        ),
                        name="password_reset_complete",
                    ),
                ],
                "django.contrib.auth.urls",
            )
        ),
    ),

]

