from django.contrib.auth import get_user_model
from django.contrib.auth.views import PasswordResetView

from .forms import UsernamePasswordResetForm


class UsernamePasswordResetView(PasswordResetView):
    """Password reset that accepts username instead of email."""

    form_class = UsernamePasswordResetForm

    # Use our custom professional templates for username-based forgot password
    template_name = "accounts/password_reset_form.html"
    success_url = "/accounts/custom/forgot-password/done/"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    html_email_template_name = "accounts/password_reset_email.html"


    def get_users(self, email):
        # PasswordResetView passes an "email" value; we ignore it and derive
        # the user from the provided username.
        form = getattr(self, "form", None)
        if form is None:
            return []

        user_obj = form.get_user()
        if not user_obj:
            return []

        # Your app sets is_active=False until admin approval.
        if not getattr(user_obj, "is_active", False):
            return []

        UserModel = get_user_model()
        try:
            user_obj = UserModel.objects.get(pk=user_obj.pk)
        except UserModel.DoesNotExist:
            return []

        return [user_obj]

    def form_valid(self, form):
        # Store form so get_users can use it.
        self.form = form
        return super().form_valid(form)


