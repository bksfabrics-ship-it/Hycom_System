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

