from django.urls import path, include
from django.contrib.auth import views as auth_views

from . import views
from .views_password_reset import UsernamePasswordResetView


urlpatterns = [
    # path('users/', views.user_management, name='user_management'),
    path('approve-user/<int:user_id>/', views.approve_user, name='approve_user'),
    path('deactivate-user/<int:user_id>/', views.deactivate_user, name='deactivate_user'),
    path('users/', views.user_list, name='user_list'),

    path('manage-permissions/<int:user_id>/', views.manage_permissions, name='manage_permissions'),

    path("register/", views.employee_register, name="employee_register"),
    path("password-change/", views.employee_password_change, name="employee_password_change"),

    # User management page (was missing and causing 404)
    path('user-management/', views.user_management, name='user_management'),


    
    # Password reset (forgot password) - accepts username instead of email

    path(
        "forgot-password/",
        include(
            (
                [
                    path(
                        "",
                        UsernamePasswordResetView.as_view(
                            template_name="accounts/registration/password_reset_form.html",
                            email_template_name="accounts/registration/password_reset_email.txt",
                            subject_template_name="accounts/registration/password_reset_subject.txt",
                            html_email_template_name="accounts/registration/password_reset_email.html",
                            # After submitting username, redirect to our custom done page
                            success_url="/accounts/custom/forgot-password/done/",
                        ),
                        name="password_reset",
                    ),


                    path(
                        "done/",
                        auth_views.PasswordResetDoneView.as_view(
                            template_name="accounts/registration/password_reset_done.html"
                        ),

                        name="password_reset_done",
                    ),
                    path(
                        "confirm/<uidb64>/<token>/",
                        auth_views.PasswordResetConfirmView.as_view(
                            template_name="accounts/registration/password_reset_confirm.html"
                        ),

                        name="password_reset_confirm",
                    ),
                    path(
                        "complete/",
                        auth_views.PasswordResetCompleteView.as_view(
                            template_name="accounts/registration/password_reset_complete.html"
                        ),

                        name="password_reset_complete",
                    ),
                ],
                "django.contrib.auth.urls",
            )
        ),
    ),

]

