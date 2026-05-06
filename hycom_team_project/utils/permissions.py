from functools import wraps

from django.contrib.auth.decorators import user_passes_test


def has_group(user, group_name: str) -> bool:
    return user.is_authenticated and user.groups.filter(name=group_name).exists()


def can_access_area(user, area: str) -> bool:
    """area: orders|stock|returns|reports"""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    if area == "orders":
        return has_group(user, "Orders")
    if area == "stock":
        return has_group(user, "Stock")
    if area == "returns":
        return has_group(user, "Returns")
    if area == "reports":
        return has_group(user, "Reports")
    return False


def area_required(area: str, login_url: str = "/accounts/login/"):
    """Decorator for area-level authorization."""

    def predicate(user):
        return can_access_area(user, area)

    return user_passes_test(predicate, login_url=login_url)

