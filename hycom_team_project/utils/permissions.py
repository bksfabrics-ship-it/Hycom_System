from functools import wraps

from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from functools import wraps

from accounts.models import AreaPermission


def has_group(user, group_name: str) -> bool:
    return user.is_authenticated and user.groups.filter(name=group_name).exists()


def can_access_area(user, area_name):

    # Super admin always allowed
    if user.is_superuser:
        return True

    # Staff always allowed
    if user.is_staff:
        return True

    return AreaPermission.objects.filter(
        user=user,
        area=area_name
    ).exists()


def area_required(area_name, login_url: str = '/accounts/login/'):


    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            if not request.user.is_authenticated:
                return redirect('/accounts/login/')

            if not can_access_area(request.user, area_name):
                return HttpResponseForbidden(
                    "You do not have permission to access this page."
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


