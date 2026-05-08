from accounts.models import AreaPermission


def sidebar_permissions(request):

    permissions = []

    if request.user.is_authenticated:

        # SUPERUSER GETS EVERYTHING
        if request.user.is_superuser:

            permissions = [
                'dashboard',
                'orders',
                'products',
                'reports',
                'user_management',
            ]

        else:

            permissions = list(
                AreaPermission.objects.filter(
                    user=request.user
                ).values_list('area', flat=True)
            )

    return {
        'sidebar_permissions': permissions
    }