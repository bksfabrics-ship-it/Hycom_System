"""
URL configuration for hycom_team_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Built-in auth
    path('accounts/', include('django.contrib.auth.urls')),

    # Custom employee registration + password change
    path('accounts/custom/', include('accounts.urls')),

    path('api/', include('master.urls')),
    path('stock/', include('stock.urls')),
    path('returns/', include('returns.urls')),
    path('reports/', include('reports.urls')),
]

