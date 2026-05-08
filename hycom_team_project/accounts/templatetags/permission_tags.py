from django import template
from utils.permissions import can_access_area

register = template.Library()


@register.simple_tag
def has_permission(user, area):
    return can_access_area(user, area)