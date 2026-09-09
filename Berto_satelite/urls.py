"""
URL configuration for Berto_satelite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
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
from django.urls import include, path

from wifi_billing import views
from wifi_billing.views import admin_login, admin_logout, customer_page, dashboard_page

urlpatterns = [
    path('', customer_page, name='home'),
    path('admin-dashboard/login/', admin_login, name='admin-dashboard-login'),
    path('admin-dashboard/logout/', admin_logout, name='admin-dashboard-logout'),
    path('admin-dashboard/', dashboard_page, name='admin-dashboard'),
    path('admin-dashboard/customers/', views.dashboard_section, {'section': 'customers'}, name='admin-dashboard-customers'),
    path('admin-dashboard/packages/', views.dashboard_section, {'section': 'packages'}, name='admin-dashboard-packages'),
    path('admin-dashboard/subscriptions/', views.dashboard_section, {'section': 'subscriptions'}, name='admin-dashboard-subscriptions'),
    path('admin-dashboard/payments/', views.dashboard_section, {'section': 'payments'}, name='admin-dashboard-payments'),
    path('admin-dashboard/vouchers/', views.dashboard_section, {'section': 'vouchers'}, name='admin-dashboard-vouchers'),
    path('admin-dashboard/routers/', views.dashboard_section, {'section': 'routers'}, name='admin-dashboard-routers'),
    path('admin-dashboard/settings/', views.dashboard_section, {'section': 'settings'}, name='admin-dashboard-settings'),
    path('customer/', customer_page, name='customer-page'),
    path('admin/', admin.site.urls),
    path('api/', include('wifi_billing.urls')),
]
