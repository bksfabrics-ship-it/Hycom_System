from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User

from .models import EmployeeProfile


class EmployeeRegistrationForm(forms.ModelForm):
    name = forms.CharField(max_length=150, required=True)
    username = forms.CharField(max_length=150, required=True)
    designation = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=30, required=True)
    employee_id = forms.CharField(max_length=50, required=False)

    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    class Meta:
        model = User
        fields = ["username", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Username already exists")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email already exists")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match")
        return cleaned

    def save(self, commit=True):
        name = self.cleaned_data["name"].strip()
        username = self.cleaned_data["username"].strip()
        designation = self.cleaned_data["designation"].strip()
        email = self.cleaned_data["email"].strip()
        phone_number = self.cleaned_data["phone_number"].strip()
        employee_id = self.cleaned_data.get("employee_id", "").strip()
        password = self.cleaned_data["password1"]

        user = User(
            username=username,
            email=email,
            is_active=False,  # approval by admin
        )
        user.set_password(password)
        if commit:
            user.save()

        EmployeeProfile.objects.update_or_create(
            user=user,
            defaults={
                "name": name,
                "designation": designation,
                "phone_number": phone_number,
                "employee_id": employee_id or None,
                "is_approved": False,
            },
        )
        return user


class EmployeePasswordChangeForm(PasswordChangeForm):
    """Used after approval to allow user to set/change password."""
    pass

