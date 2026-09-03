from django.contrib import admin

from .models import NetworkSession, Package, Payment, Router, Subscription, SystemLog, User, Voucher


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'phone_number', 'subscription_status')
    list_filter = ('role', 'subscription_status')
    search_fields = ('username', 'email', 'phone_number')


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_hours', 'status')
    list_filter = ('status',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('customer', 'package', 'amount', 'status', 'receipt_number')
    list_filter = ('status', 'payment_method')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'package', 'status', 'start_date', 'expiry_date')
    list_filter = ('status',)


@admin.register(Router)
class RouterAdmin(admin.ModelAdmin):
    list_display = ('name', 'ip_address', 'api_port', 'connection_status')
    list_filter = ('connection_status',)


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ('code', 'package', 'status', 'expiry_date')
    list_filter = ('status',)


@admin.register(NetworkSession)
class NetworkSessionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'router', 'status', 'ip_address', 'started_at')
    list_filter = ('status',)


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ('category', 'level', 'message', 'created_at')
    list_filter = ('level', 'category')
