import json

from django.contrib.auth import authenticate, login
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count, Sum
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import Package, Payment, Router, Subscription, User, Voucher
from .services import MpesaService, RouterService


def _read_json(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()


def _serialize_package(pkg):
    return {
        'id': pkg.id,
        'name': pkg.name,
        'description': pkg.description,
        'price': str(pkg.price),
        'duration_hours': pkg.duration_hours,
        'speed_limit_mbps': str(pkg.speed_limit_mbps),
        'data_allowance_gb': str(pkg.data_allowance_gb),
        'upload_speed_mbps': str(pkg.upload_speed_mbps),
        'download_speed_mbps': str(pkg.download_speed_mbps),
        'devices_allowed': pkg.devices_allowed,
        'status': pkg.status,
    }


def _serialize_payment(payment):
    return {
        'id': payment.id,
        'customer': payment.customer.get_full_name() or payment.customer.username,
        'package': payment.package.name if payment.package else None,
        'amount': str(payment.amount),
        'phone_number': payment.phone_number,
        'status': payment.status,
        'receipt_number': payment.receipt_number,
        'payment_method': payment.payment_method,
        'created_at': payment.created_at.isoformat(),
    }


def _serialize_subscription(subscription):
    return {
        'id': subscription.id,
        'customer': subscription.customer.get_full_name() or subscription.customer.username,
        'package': subscription.package.name,
        'status': subscription.status,
        'start_date': subscription.start_date.isoformat(),
        'expiry_date': subscription.expiry_date.isoformat() if subscription.expiry_date else None,
        'data_remaining': str(subscription.data_remaining),
        'auto_renew': subscription.auto_renew,
    }


def api_home(request):
    return JsonResponse({
        'app': 'Berto_satelite Wi-Fi Billing & Hotspot Management System',
        'version': '1.0.0',
        'status': 'ok',
    })


def admin_login(request):
    return LoginView.as_view(
        template_name='wifi_billing/admin_login.html',
        redirect_authenticated_user=True,
        next_page='/admin-dashboard/',
    )(request)


@staff_member_required(login_url='/admin-dashboard/login/')
def dashboard_page(request):
    return render(request, 'wifi_billing/dashboard.html')


def customer_page(request):
    return render(request, 'wifi_billing/customer.html')


@require_http_methods(['POST'])
def api_register(request):
    data = _read_json(request)
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()
    phone_number = (data.get('phone_number') or '').strip()

    if not username or not password:
        return HttpResponseBadRequest(json.dumps({'detail': 'Username and password are required'}), content_type='application/json')
    if User.objects.filter(username=username).exists():
        return HttpResponseBadRequest(json.dumps({'detail': 'User already exists'}), content_type='application/json')

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        role=User.ROLE_CUSTOMER,
    )
    return JsonResponse({'detail': 'Customer registered successfully', 'username': user.username, 'role': user.role}, status=201)


@require_http_methods(['POST'])
def api_login(request):
    data = _read_json(request)
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    user = authenticate(request, username=username, password=password)
    if user is None:
        return HttpResponseBadRequest(json.dumps({'detail': 'Invalid username or password'}), content_type='application/json')

    login(request, user)
    return JsonResponse({'detail': 'Login successful', 'username': user.username, 'role': user.role, 'token': f'token-{user.pk}-{user.username}'})


@require_http_methods(['GET'])
def api_packages(request):
    packages = Package.objects.filter(status=Package.STATUS_ACTIVE)
    return JsonResponse({'results': [_serialize_package(pkg) for pkg in packages]})


@require_http_methods(['GET'])
def api_customers(request):
    customers = User.objects.filter(role=User.ROLE_CUSTOMER)
    payload = [{
        'id': customer.id,
        'username': customer.username,
        'name': customer.get_full_name(),
        'phone_number': customer.phone_number,
        'email': customer.email,
        'status': customer.subscription_status or 'new',
    } for customer in customers]
    return JsonResponse({'results': payload})


@require_http_methods(['GET'])
def api_payments(request):
    payments = Payment.objects.select_related('customer', 'package')
    return JsonResponse({'results': [_serialize_payment(item) for item in payments]})


@require_http_methods(['GET'])
def api_subscriptions(request):
    subscriptions = Subscription.objects.select_related('customer', 'package')
    return JsonResponse({'results': [_serialize_subscription(item) for item in subscriptions]})


@require_http_methods(['GET'])
def api_vouchers(request):
    vouchers = Voucher.objects.select_related('package')
    payload = [{
        'id': voucher.id,
        'code': voucher.code,
        'package': voucher.package.name,
        'status': voucher.status,
        'duration_hours': voucher.duration_hours,
        'data_allowance_gb': str(voucher.data_allowance_gb),
        'expiry_date': voucher.expiry_date.isoformat() if voucher.expiry_date else None,
    } for voucher in vouchers]
    return JsonResponse({'results': payload})


@require_http_methods(['GET'])
def api_routers(request):
    routers = Router.objects.all()
    payload = [{
        'id': router.id,
        'name': router.name,
        'ip_address': router.ip_address,
        'api_port': router.api_port,
        'connection_status': router.connection_status,
    } for router in routers]
    return JsonResponse({'results': payload})


@require_http_methods(['GET'])
def api_dashboard(request):
    customers = User.objects.filter(role=User.ROLE_CUSTOMER)
    active_customers = customers.filter(subscription_status='active').count()
    expired_customers = customers.filter(subscription_status='expired').count()
    total_vouchers = Voucher.objects.count()
    used_vouchers = Voucher.objects.filter(status=Voucher.STATUS_USED).count()
    unused_vouchers = Voucher.objects.filter(status=Voucher.STATUS_UNUSED).count()
    monthly_revenue = Payment.objects.filter(status=Payment.STATUS_SUCCESSFUL).aggregate(value=Sum('amount'))['value'] or 0
    today_revenue = Payment.objects.filter(status=Payment.STATUS_SUCCESSFUL).aggregate(value=Sum('amount'))['value'] or 0
    active_subscriptions = Subscription.objects.filter(status=Subscription.STATUS_ACTIVE).count()
    expiring_subscriptions = Subscription.objects.filter(status=Subscription.STATUS_ACTIVE).count()

    return JsonResponse({
        'total_customers': customers.count(),
        'active_customers': active_customers,
        'expired_customers': expired_customers,
        'today_revenue': str(today_revenue),
        'monthly_revenue': str(monthly_revenue),
        'active_subscriptions': active_subscriptions,
        'expiring_subscriptions': expiring_subscriptions,
        'total_vouchers': total_vouchers,
        'used_vouchers': used_vouchers,
        'unused_vouchers': unused_vouchers,
        'package_popularity': list(Package.objects.annotate(sold=Count('subscriptions')).values('name', 'sold')),
    })


@require_http_methods(['POST'])
def api_generate_payment(request):
    data = _read_json(request)
    username = data.get('username')
    package_id = data.get('package_id')
    phone_number = data.get('phone_number')
    amount = data.get('amount')

    user = User.objects.filter(username=username).first() if username else request.user if request.user.is_authenticated else None
    package = Package.objects.filter(id=package_id).first() if package_id else Package.objects.first()
    if user is None or package is None:
        return HttpResponseBadRequest(json.dumps({'detail': 'Customer and package are required'}), content_type='application/json')

    mpesa = MpesaService()
    result = mpesa.initiate_stk_push(user, package, phone_number or user.phone_number, amount or str(package.price))
    return JsonResponse({'detail': 'STK push initiated', **result}, status=201)


@require_http_methods(['POST'])
def api_mpesa_callback(request):
    payload = _read_json(request)
    mpesa = MpesaService()
    try:
        payment = mpesa.process_callback(payload)
    except ValueError as exc:
        return HttpResponseBadRequest(json.dumps({'detail': str(exc)}), content_type='application/json')
    return JsonResponse({'detail': 'Payment processed', 'payment_id': payment.id, 'status': payment.status})


@require_http_methods(['GET'])
def captive_portal(request):
    return JsonResponse({
        'business_name': 'Berto Wi-Fi',
        'logo': '/static/logo.svg',
        'customer_support': '+254700000000',
        'terms_and_conditions': 'Use of this network constitutes acceptance of the applicable terms and conditions.',
        'packages': [_serialize_package(pkg) for pkg in Package.objects.filter(status=Package.STATUS_ACTIVE)],
    })


@login_required
@require_http_methods(['GET'])
def protected_profile(request):
    return JsonResponse({'username': request.user.username, 'role': request.user.role, 'email': request.user.email})
