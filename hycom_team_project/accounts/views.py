from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import EmployeeRegistrationForm, EmployeePasswordChangeForm
from .models import EmployeeProfile
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404
from .models import AreaPermission
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction


def superuser_required(view_func):
    return user_passes_test(
        lambda u: u.is_superuser
    )(view_func)


def employee_register(request):

    if request.method == "POST":
        form = EmployeeRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                "Registration submitted successfully. Wait for admin approval before login.",
            )
            # Do not login yet
            return redirect(reverse("login"))
    else:
        form = EmployeeRegistrationForm()

    # Render login template with registration form
    return render(request, "registration/login.html", {"registration_form": form})


def employee_approval_required_redirect(request):
    # If approved, redirect to update password
    profile = None
    try:
        profile = request.user.employeeprofile
    except EmployeeProfile.DoesNotExist:
        profile = None

    if profile and profile.is_approved:
        return redirect("employee_password_change")

    return redirect("login")


@login_required
def employee_password_change(request):
    try:
        profile = request.user.employeeprofile
    except EmployeeProfile.DoesNotExist:
        messages.error(request, "No employee profile found.")
        return redirect("login")

    if not profile.is_approved and not request.user.is_staff:
        messages.error(request, "Your account is pending admin approval.")
        return redirect("login")

    if request.method == "POST":
        form = EmployeePasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Password updated successfully.")
            return redirect("api/")
    else:
        form = EmployeePasswordChangeForm(request.user)

    return render(request, "registration/password_change.html", {"form": form})


from utils.permissions import can_access_area

@login_required
def user_management(request):


    # Permission is driven by accounts.AreaPermission(user, area='user_management')
    # (staff can also be allowed depending on can_access_area())
    if not request.user.is_authenticated:
        return redirect('login')
    
    # if not can_access_area(request.user, 'user_management'):
    #     return render(request, '403.html')

    if not can_access_area(request.user, 'user_management'):
        messages.error(request, 'You are not allowed to access User Management.')
        return redirect('api_dashboard')


    users = EmployeeProfile.objects.select_related('user').all().order_by('-created_at')

    return render(request, 'accounts/user_management.html', {
        'users': users
    })





@staff_member_required
def approve_user(request, user_id):

    profile = get_object_or_404(
        EmployeeProfile,
        user__id=user_id
    )

    profile.is_approved = True

    profile.user.is_active = True
    profile.user.save()

    profile.save()

    messages.success(
        request,
        'User approved successfully'
    )

    return redirect('user_management')


@staff_member_required
def deactivate_user(request, user_id):

    profile = get_object_or_404(
        EmployeeProfile,
        user__id=user_id
    )

    profile.user.is_active = False
    profile.user.save()

    messages.success(
        request,
        'User deactivated'
    )

    return redirect('user_management')


# @superuser_required
@login_required
def manage_permissions(request, user_id):

    user_obj = get_object_or_404(User, id=user_id)

    ALL_AREAS = [
        ('dashboard', 'Dashboard'),
        ('orders', 'Orders'),
        ('products', 'Products'),
        ('reports', 'Reports'),
        ('settings', 'Settings'),
        ('user_management', 'User Management'),
    ]

    existing_permissions = list(
        AreaPermission.objects.filter(
            user=user_obj
        ).values_list('area', flat=True)
    )

    if request.method == 'POST':

        selected_areas = request.POST.getlist('areas')

        
        with transaction.atomic():
            AreaPermission.objects.filter(user=user_obj).delete()


        for area in selected_areas:
            AreaPermission.objects.create(
                user=user_obj,
                area=area
            )

        messages.success(
            request,
            'Permissions updated successfully.'
        )

        return redirect('user_management')

    return render(
        request,
        'accounts/manage_permissions.html',
        {
            'user_obj': user_obj,
            'all_areas': ALL_AREAS,
            'existing_permissions': existing_permissions,
        }
    )
    
    
    
@staff_member_required
def user_list(request):

    users = User.objects.all().order_by('username')

    return render(request, 'accounts/user_list.html', {
        'users': users
    })
