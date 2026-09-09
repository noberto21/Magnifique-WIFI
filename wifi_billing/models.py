from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    ROLE_SUPER_ADMIN = 'super_admin'
    ROLE_ADMIN = 'admin'
    ROLE_CUSTOMER = 'customer'
    ROLE_CHOICES = [
        (ROLE_SUPER_ADMIN, 'Super Admin'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_CUSTOMER, 'Customer'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CUSTOMER)
    phone_number = models.CharField(max_length=20, blank=True, default='')
    address = models.TextField(blank=True, default='')
    customer_id = models.CharField(max_length=50, blank=True, default='')
    subscription_status = models.CharField(max_length=30, blank=True, default='')
    mac_address = models.CharField(max_length=50, blank=True, default='')
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    router_name = models.CharField(max_length=100, blank=True, default='')
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_admin_user(self):
        return self.role in (self.ROLE_SUPER_ADMIN, self.ROLE_ADMIN)

    def save(self, *args, **kwargs):
        if self.is_superuser and self.role == self.ROLE_CUSTOMER:
            self.role = self.ROLE_SUPER_ADMIN
        elif self.is_staff and self.role == self.ROLE_CUSTOMER:
            self.role = self.ROLE_ADMIN
        if self.role in (self.ROLE_SUPER_ADMIN, self.ROLE_ADMIN):
            self.is_staff = True
        super().save(*args, **kwargs)


class Package(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    ]

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration_hours = models.PositiveIntegerField(default=24)
    speed_limit_mbps = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    data_allowance_gb = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    upload_speed_mbps = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    download_speed_mbps = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    devices_allowed = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Payment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SUCCESSFUL = 'successful'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_TIMEOUT = 'timeout'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESSFUL, 'Successful'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_TIMEOUT, 'Timeout'),
    ]

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    phone_number = models.CharField(max_length=20, blank=True, default='')
    payment_method = models.CharField(max_length=30, default='M-Pesa')
    merchant_request_id = models.CharField(max_length=200, blank=True, default='')
    checkout_request_id = models.CharField(max_length=200, blank=True, default='')
    receipt_number = models.CharField(max_length=100, blank=True, default='')
    transaction_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    raw_callback_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.customer} - {self.amount}'


class Subscription(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_SUSPENDED, 'Suspended'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    package = models.ForeignKey(Package, on_delete=models.PROTECT, related_name='subscriptions')
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='subscriptions')
    start_date = models.DateTimeField(default=timezone.now)
    expiry_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    auto_renew = models.BooleanField(default=False)
    data_used = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    data_remaining = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.customer} - {self.package}'

    @property
    def is_expired(self):
        return self.expiry_date is not None and self.expiry_date <= timezone.now()


class Router(models.Model):
    name = models.CharField(max_length=120)
    ip_address = models.GenericIPAddressField()
    api_port = models.PositiveIntegerField(default=8728)
    username = models.CharField(max_length=80)
    password = models.CharField(max_length=200)
    connection_status = models.CharField(max_length=30, default='disconnected')
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Voucher(models.Model):
    STATUS_UNUSED = 'unused'
    STATUS_ACTIVE = 'active'
    STATUS_USED = 'used'
    STATUS_EXPIRED = 'expired'
    STATUS_DISABLED = 'disabled'
    STATUS_CHOICES = [
        (STATUS_UNUSED, 'Unused'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_USED, 'Used'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_DISABLED, 'Disabled'),
    ]

    code = models.CharField(max_length=80, unique=True)
    package = models.ForeignKey(Package, on_delete=models.PROTECT, related_name='vouchers')
    duration_hours = models.PositiveIntegerField(default=24)
    data_allowance_gb = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNUSED)
    created_at = models.DateTimeField(default=timezone.now)
    activated_at = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.code


class NetworkSession(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='network_sessions')
    router = models.ForeignKey(Router, on_delete=models.SET_NULL, null=True, blank=True)
    mac_address = models.CharField(max_length=50, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(max_length=30, default='connected')
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']


class SystemLog(models.Model):
    level = models.CharField(max_length=20, default='info')
    message = models.TextField()
    category = models.CharField(max_length=50, default='system')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
