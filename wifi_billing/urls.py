from django.urls import path

from . import views

urlpatterns = [
    path('', views.api_home, name='api-home'),
    path('register/', views.api_register, name='api-register'),
    path('login/', views.api_login, name='api-login'),
    path('profile/', views.protected_profile, name='api-profile'),
    path('packages/', views.api_packages, name='api-packages'),
    path('customers/', views.api_customers, name='api-customers'),
    path('payments/', views.api_payments, name='api-payments'),
    path('subscriptions/', views.api_subscriptions, name='api-subscriptions'),
    path('vouchers/', views.api_vouchers, name='api-vouchers'),
    path('routers/', views.api_routers, name='api-routers'),
    path('dashboard/', views.api_dashboard, name='api-dashboard'),
    path('payment/initiate/', views.api_generate_payment, name='api-payment-initiate'),
    path('payment/callback/', views.api_mpesa_callback, name='api-payment-callback'),
    path('portal/', views.captive_portal, name='captive-portal'),
]
