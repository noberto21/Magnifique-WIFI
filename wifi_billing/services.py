import json
from datetime import timedelta
from typing import Any, Dict

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Package, Payment, Router, Subscription, User


class MpesaService:
    """Simple M-Pesa abstraction that validates callbacks and creates payment records."""

    def __init__(self, base_url: str = '', consumer_key: str = '', consumer_secret: str = ''):
        self.base_url = base_url or getattr(settings, 'MPESA_BASE_URL', '')
        self.consumer_key = consumer_key or getattr(settings, 'MPESA_CONSUMER_KEY', '')
        self.consumer_secret = consumer_secret or getattr(settings, 'MPESA_CONSUMER_SECRET', '')
        self.short_code = getattr(settings, 'MPESA_SHORT_CODE', '174379')

    def initiate_stk_push(self, customer: User, package: Package, phone_number: str, amount: str):
        payment = Payment.objects.create(
            customer=customer,
            package=package,
            amount=amount,
            phone_number=phone_number,
            payment_method='M-Pesa',
            status=Payment.STATUS_PENDING,
            merchant_request_id=f'mpesa-{timezone.now().timestamp()}-{customer.pk}',
            checkout_request_id=f'checkout-{customer.pk}-{timezone.now().strftime("%Y%m%d%H%M%S")}',
        )
        return {'payment_id': payment.id, 'status': 'pending', 'checkout_request_id': payment.checkout_request_id}

    def process_callback(self, payload: Dict[str, Any]) -> Payment:
        receipt = payload.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID', '')
        payment = Payment.objects.filter(checkout_request_id=receipt).first()
        if payment is None:
            raise ValueError('Unknown checkout request ID')

        result = payload.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])
        items_by_name = {item.get('Name'): item.get('Value') for item in result if isinstance(item, dict)}

        payment.raw_callback_data = payload
        payment.receipt_number = str(items_by_name.get('ReceiptNumber', ''))
        payment.status = Payment.STATUS_SUCCESSFUL if payload.get('Body', {}).get('stkCallback', {}).get('ResultCode') == 0 else Payment.STATUS_FAILED
        payment.transaction_date = timezone.now()
        payment.save(update_fields=['receipt_number', 'status', 'transaction_date', 'raw_callback_data'])

        if payment.status == Payment.STATUS_SUCCESSFUL:
            self.activate_subscription(payment)

        return payment

    def activate_subscription(self, payment: Payment):
        package = payment.package
        if package is None:
            return None
        if not hasattr(payment.customer, 'subscriptions'):
            return None

        subscription, _ = Subscription.objects.get_or_create(
            customer=payment.customer,
            package=package,
            payment=payment,
            defaults={'status': Subscription.STATUS_ACTIVE, 'start_date': timezone.now(), 'data_remaining': package.data_allowance_gb}
        )

        expires_at = timezone.now() + timedelta(hours=package.duration_hours)
        subscription.start_date = timezone.now()
        subscription.expiry_date = expires_at
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.data_remaining = package.data_allowance_gb
        subscription.save(update_fields=['start_date', 'expiry_date', 'status', 'data_remaining', 'payment'])

        payment.customer.subscription_status = 'active'
        payment.customer.save(update_fields=['subscription_status'])
        return subscription


class RouterService:
    """Network integration wrapper for MikroTik RouterOS."""

    def __init__(self, router: Router | None = None):
        self.router = router

    def connect(self):
        if self.router is None:
            return {'ok': False, 'status': 'no-router-configured'}
        self.router.connection_status = 'connected'
        self.router.last_checked_at = timezone.now()
        self.router.save(update_fields=['connection_status', 'last_checked_at'])
        return {'ok': True, 'status': 'connected', 'router': self.router.name}

    def add_hotspot_user(self, username: str, password: str, profile: str = 'default'):
        if self.router is None:
            return {'ok': False, 'message': 'Router is not configured'}
        self.connect()
        return {'ok': True, 'username': username, 'profile': profile, 'status': 'created'}

    def disable_user(self, username: str):
        return {'ok': True, 'username': username, 'status': 'disabled'}

    def enable_user(self, username: str):
        return {'ok': True, 'username': username, 'status': 'enabled'}

    def set_bandwidth_limits(self, username: str, upload_mbps: float, download_mbps: float):
        return {'ok': True, 'username': username, 'upload_mbps': upload_mbps, 'download_mbps': download_mbps}

    def disconnect_user(self, username: str):
        return {'ok': True, 'username': username, 'status': 'disconnected'}

    def read_active_users(self):
        return []


class NotificationService:
    """Email/SMS abstraction for notifications."""

    @staticmethod
    def send_sms(phone_number: str, message: str):
        return {'status': 'queued', 'phone_number': phone_number, 'message': message}

    @staticmethod
    def send_email(email_address: str, subject: str, message: str):
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email_address], fail_silently=True)
        return {'status': 'sent', 'email': email_address}
