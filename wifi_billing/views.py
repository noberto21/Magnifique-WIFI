import json
import secrets
import string
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q, Sum
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Package, Payment, Router, Subscription, User, Voucher
from .services import MpesaService, RouterService


def admin_required(view_func):
    """Ensure user is logged in and is staff, superuser, or has an admin role."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/admin-dashboard/login/?next={request.path}')
        if not (request.user.is_staff or request.user.is_superuser or getattr(request.user, 'role', None) in (User.ROLE_SUPER_ADMIN, User.ROLE_ADMIN)):
            return redirect('/admin-dashboard/login/')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


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
        'app': 'Magnifique WiFi Billing & Hotspot Management System',
        'version': '1.0.0',
        'status': 'ok',
    })


def admin_login(request):
    return LoginView.as_view(
        template_name='wifi_billing/admin_login.html',
        redirect_authenticated_user=True,
        next_page='/admin-dashboard/',
    )(request)


def admin_logout(request):
    logout(request)
    return redirect('/admin-dashboard/login/')


def _get_dashboard_context(request, section='overview'):
    customers_qs = User.objects.filter(role=User.ROLE_CUSTOMER)
    total_customers = customers_qs.count()
    active_customers = customers_qs.filter(subscription_status='active').count()

    subs_qs = Subscription.objects.select_related('customer', 'package')
    active_subscriptions = subs_qs.filter(status=Subscription.STATUS_ACTIVE).count()

    payments_qs = Payment.objects.select_related('customer', 'package')
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_revenue = payments_qs.filter(status=Payment.STATUS_SUCCESSFUL, created_at__gte=today_start).aggregate(val=Sum('amount'))['val'] or 0
    all_time_revenue = payments_qs.filter(status=Payment.STATUS_SUCCESSFUL).aggregate(val=Sum('amount'))['val'] or 0

    vouchers_qs = Voucher.objects.select_related('package')
    total_vouchers = vouchers_qs.count()
    unused_vouchers = vouchers_qs.filter(status=Voucher.STATUS_UNUSED).count()

    routers_qs = Router.objects.all()
    packages_qs = Package.objects.all()

    q = (request.GET.get('q') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()

    context = {
        'active_section': section,
        'user': request.user,
        'metrics': {
            'total_customers': total_customers,
            'active_customers': active_customers,
            'active_subscriptions': active_subscriptions,
            'today_revenue': today_revenue,
            'all_time_revenue': all_time_revenue,
            'total_vouchers': total_vouchers,
            'unused_vouchers': unused_vouchers,
            'total_routers': routers_qs.count(),
            'online_routers': routers_qs.filter(connection_status='connected').count(),
        },
        'q': q,
        'status_filter': status_filter,
        'all_packages': packages_qs.filter(status=Package.STATUS_ACTIVE),
    }

    if section == 'overview':
        context['recent_payments'] = payments_qs.order_by('-created_at')[:6]
        context['recent_customers'] = customers_qs.order_by('-date_joined')[:5]
        context['package_popularity'] = packages_qs.annotate(sold=Count('subscriptions')).order_by('-sold')[:5]
        context['routers_list'] = routers_qs[:4]
    elif section == 'customers':
        c_list = customers_qs
        if q:
            c_list = c_list.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(phone_number__icontains=q) |
                Q(email__icontains=q)
            )
        if status_filter:
            c_list = c_list.filter(subscription_status=status_filter)
        context['customers_list'] = c_list.order_by('-date_joined')
    elif section == 'packages':
        context['packages_list'] = packages_qs.order_by('-created_at')
    elif section == 'subscriptions':
        s_list = subs_qs
        if q:
            s_list = s_list.filter(Q(customer__username__icontains=q) | Q(package__name__icontains=q))
        if status_filter:
            s_list = s_list.filter(status=status_filter)
        context['subscriptions_list'] = s_list.order_by('-start_date')
    elif section == 'payments':
        p_list = payments_qs
        if q:
            p_list = p_list.filter(
                Q(receipt_number__icontains=q) |
                Q(customer__username__icontains=q) |
                Q(phone_number__icontains=q)
            )
        if status_filter:
            p_list = p_list.filter(status=status_filter)
        context['payments_list'] = p_list.order_by('-created_at')
    elif section == 'vouchers':
        v_list = vouchers_qs
        if q:
            v_list = v_list.filter(Q(code__icontains=q) | Q(package__name__icontains=q))
        if status_filter:
            v_list = v_list.filter(status=status_filter)
        context['vouchers_list'] = v_list.order_by('-created_at')
    elif section == 'routers':
        context['routers_list'] = routers_qs.order_by('name')
    elif section == 'settings':
        context['settings_info'] = {
            'debug': settings.DEBUG,
            'allowed_hosts': settings.ALLOWED_HOSTS,
            'time_zone': settings.TIME_ZONE,
            'mpesa_shortcode': getattr(settings, 'MPESA_SHORT_CODE', '174379'),
            'mpesa_base_url': getattr(settings, 'MPESA_BASE_URL', 'https://sandbox.safaricom.co.ke'),
            'user_count': User.objects.count(),
            'total_payments': Payment.objects.count(),
            'total_subscriptions': Subscription.objects.count(),
        }

    return context


@admin_required
def dashboard_section(request, section='overview'):
    if request.method == 'POST':
        action = request.POST.get('action', '')

        # Action: Add Customer
        if action == 'add_customer':
            username = request.POST.get('username', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone_number = request.POST.get('phone_number', '').strip()
            password = request.POST.get('password', '').strip() or 'Customer123!'

            if not username:
                messages.error(request, 'Username is required.')
            elif User.objects.filter(username=username).exists():
                messages.error(request, f'Username "{username}" is already taken.')
            else:
                User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                    role=User.ROLE_CUSTOMER,
                    subscription_status='new',
                )
                messages.success(request, f'Customer "{username}" was added successfully!')
            return redirect(request.path)

        # Action: Create Package
        elif action == 'create_package':
            name = request.POST.get('name', '').strip()
            price = request.POST.get('price', '0').strip()
            duration_hours = int(request.POST.get('duration_hours') or 24)
            speed_limit = float(request.POST.get('speed_limit_mbps') or 5)
            data_allowance = float(request.POST.get('data_allowance_gb') or 1)
            upload_speed = float(request.POST.get('upload_speed_mbps') or 2)
            download_speed = float(request.POST.get('download_speed_mbps') or 5)
            devices = int(request.POST.get('devices_allowed') or 1)
            description = request.POST.get('description', '').strip()
            status = request.POST.get('status') or Package.STATUS_ACTIVE

            if not name:
                messages.error(request, 'Package name is required.')
            else:
                Package.objects.create(
                    name=name,
                    price=price,
                    duration_hours=duration_hours,
                    speed_limit_mbps=speed_limit,
                    data_allowance_gb=data_allowance,
                    upload_speed_mbps=upload_speed,
                    download_speed_mbps=download_speed,
                    devices_allowed=devices,
                    description=description,
                    status=status,
                )
                messages.success(request, f'Package "{name}" created successfully!')
            return redirect(request.path)

        # Action: Toggle Package Status
        elif action == 'toggle_package':
            pkg_id = request.POST.get('package_id')
            pkg = Package.objects.filter(id=pkg_id).first()
            if pkg:
                pkg.status = Package.STATUS_INACTIVE if pkg.status == Package.STATUS_ACTIVE else Package.STATUS_ACTIVE
                pkg.save(update_fields=['status'])
                messages.success(request, f'Package "{pkg.name}" status updated to {pkg.status}.')
            return redirect(request.path)

        # Action: Generate Vouchers
        elif action == 'generate_vouchers':
            pkg_id = request.POST.get('package_id')
            pkg = Package.objects.filter(id=pkg_id).first()
            try:
                count = max(1, min(int(request.POST.get('count') or 5), 50))
            except ValueError:
                count = 5

            if not pkg:
                messages.error(request, 'Please select a valid package for voucher generation.')
            else:
                chars = string.ascii_uppercase + string.digits
                generated = []
                for _ in range(count):
                    code = f'MV-{"".join(secrets.choice(chars) for _ in range(4))}-{"".join(secrets.choice(chars) for _ in range(4))}'
                    while Voucher.objects.filter(code=code).exists():
                        code = f'MV-{"".join(secrets.choice(chars) for _ in range(4))}-{"".join(secrets.choice(chars) for _ in range(4))}'
                    Voucher.objects.create(
                        code=code,
                        package=pkg,
                        duration_hours=pkg.duration_hours,
                        data_allowance_gb=pkg.data_allowance_gb,
                        status=Voucher.STATUS_UNUSED,
                    )
                    generated.append(code)
                messages.success(request, f'Successfully generated {len(generated)} vouchers for {pkg.name}.')
            return redirect(request.path)

        # Action: Add Router
        elif action == 'add_router':
            name = request.POST.get('name', '').strip()
            ip_address = request.POST.get('ip_address', '').strip()
            api_port = int(request.POST.get('api_port') or 8728)
            username = request.POST.get('username', '').strip() or 'admin'
            password = request.POST.get('password', '').strip() or ''

            if not name or not ip_address:
                messages.error(request, 'Router name and IP address are required.')
            else:
                Router.objects.create(
                    name=name,
                    ip_address=ip_address,
                    api_port=api_port,
                    username=username,
                    password=password,
                )
                messages.success(request, f'Router "{name}" added successfully!')
            return redirect(request.path)

        # Action: Test Router Connection
        elif action == 'test_router':
            router_id = request.POST.get('router_id')
            router = Router.objects.filter(id=router_id).first()
            if router:
                service = RouterService(router)
                res = service.connect()
                if res.get('ok'):
                    messages.success(request, f'Connected to router "{router.name}" successfully!')
                else:
                    messages.error(request, f'Connection test to "{router.name}" failed.')
            return redirect(request.path)

    context = _get_dashboard_context(request, section=section)
    return render(request, 'wifi_billing/dashboard.html', context)


@admin_required
def dashboard_page(request):
    return dashboard_section(request, section='overview')


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
        'business_name': 'Magnifique WiFi',
        'logo': '/static/wifi_billing/magnifique-wifi-logo.png',
        'customer_support': '+254700000000',
        'terms_and_conditions': 'Use of this network constitutes acceptance of the applicable terms and conditions.',
        'packages': [_serialize_package(pkg) for pkg in Package.objects.filter(status=Package.STATUS_ACTIVE)],
    })


@login_required
@require_http_methods(['GET'])
def protected_profile(request):
    return JsonResponse({'username': request.user.username, 'role': request.user.role, 'email': request.user.email})
