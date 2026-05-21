from functools import wraps

from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from functools import wraps
from django.contrib import messages
from accounts.models import AreaPermission


def has_group(user, group_name: str) -> bool:
    return user.is_authenticated and user.groups.filter(name=group_name).exists()


def can_access_area(user, area):

    # Superuser gets everything
    if user.is_superuser:
        return True

    # Not logged in
    if not user.is_authenticated:
        return False

    # Check assigned permissions
    return AreaPermission.objects.filter(
        user=user,
        area=area
    ).exists()


def area_required(area_name):

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            # NOT LOGGED IN
            if not request.user.is_authenticated:

                messages.warning(
                    request,
                    "Please login to continue."
                )

                return redirect('/accounts/login/')

            # NO PERMISSION
            if not can_access_area(request.user, area_name):

                messages.error(
                    request,
                    "You do not have permission to access this module."
                )

                return redirect('/api/')

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


