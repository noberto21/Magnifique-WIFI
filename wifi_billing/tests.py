import json

from django.test import TestCase

from .models import Package, User


class WifiBillingApiTests(TestCase):
    def setUp(self):
        self.package = Package.objects.create(
            name='Daily',
            price=50,
            duration_hours=24,
            speed_limit_mbps=5,
            data_allowance_gb=1,
            upload_speed_mbps=2,
            download_speed_mbps=5,
            devices_allowed=2,
        )

    def test_customer_registration_and_login(self):
        response = self.client.post(
            '/api/register/',
            data=json.dumps({
                'username': 'jane',
                'password': 'securepass123',
                'email': 'jane@example.com',
                'phone_number': '0712345678',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='jane').exists())

        login_response = self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'jane', 'password': 'securepass123'}),
            content_type='application/json',
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn('token', login_response.json())

    def test_packages_listing(self):
        response = self.client.get('/api/packages/')
        self.assertEqual(response.status_code, 200)
        data = response.json()['results']
        self.assertTrue(any(item['name'] == 'Daily' for item in data))

    def test_customer_page_is_public_homepage(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose a package')

    def test_admin_dashboard_requires_staff_user(self):
        response = self.client.get('/admin-dashboard/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin-dashboard/login/', response.url)

        User.objects.create_user(
            username='staff',
            password='securepass123',
            is_staff=True,
        )
        login_response = self.client.post(
            '/admin-dashboard/login/',
            {'username': 'staff', 'password': 'securepass123'},
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.url, '/admin-dashboard/')
        response = self.client.get('/admin-dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Revenue overview')

    def test_admin_login_accepts_configured_browser_origin(self):
        User.objects.create_user(
            username='staff',
            password='securepass123',
            is_staff=True,
        )
        client = self.client_class(enforce_csrf_checks=True)
        login_page = client.get('/admin-dashboard/login/')
        csrf_token = login_page.cookies['csrftoken'].value

        response = client.post(
            '/admin-dashboard/login/',
            {
                'username': 'staff',
                'password': 'securepass123',
                'csrfmiddlewaretoken': csrf_token,
            },
            HTTP_HOST='testserver',
            HTTP_ORIGIN='http://192.168.18.7',
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/admin-dashboard/')

    def test_django_admin_remains_available(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)

    def test_admin_dashboard_sections_have_staff_only_urls(self):
        sections = ('customers', 'packages', 'subscriptions', 'payments', 'vouchers', 'routers', 'settings')
        for section in sections:
            response = self.client.get(f'/admin-dashboard/{section}/')
            self.assertEqual(response.status_code, 302)
            self.assertIn('/admin-dashboard/login/', response.url)

        User.objects.create_user(
            username='staff',
            password='securepass123',
            is_staff=True,
        )
        self.client.login(username='staff', password='securepass123')
        for section in sections:
            response = self.client.get(f'/admin-dashboard/{section}/')
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f'/admin-dashboard/{section}/')

    def test_admin_logout_redirects_to_login(self):
        User.objects.create_user(
            username='staff_logout',
            password='securepass123',
            is_staff=True,
        )
        self.client.login(username='staff_logout', password='securepass123')
        response = self.client.get('/admin-dashboard/logout/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/admin-dashboard/login/')
        # After logout, accessing dashboard redirects to login
        dash_response = self.client.get('/admin-dashboard/')
        self.assertEqual(dash_response.status_code, 302)
        self.assertIn('/admin-dashboard/login/', dash_response.url)

    def test_super_admin_role_can_access_dashboard(self):
        user = User.objects.create_user(
            username='super_admin_user',
            password='securepass123',
            role=User.ROLE_SUPER_ADMIN,
        )
        self.assertTrue(user.is_staff)
        self.client.login(username='super_admin_user', password='securepass123')
        response = self.client.get('/admin-dashboard/')
        self.assertEqual(response.status_code, 200)

    def test_admin_role_can_access_dashboard(self):
        user = User.objects.create_user(
            username='admin_role_user',
            password='securepass123',
            role=User.ROLE_ADMIN,
        )
        self.assertTrue(user.is_staff)
        self.client.login(username='admin_role_user', password='securepass123')
        response = self.client.get('/admin-dashboard/')
        self.assertEqual(response.status_code, 200)

    def test_customer_role_cannot_access_dashboard(self):
        customer = User.objects.create_user(
            username='regular_customer',
            password='securepass123',
            role=User.ROLE_CUSTOMER,
        )
        # Attempt to access dashboard directly while logged in as customer
        self.client.login(username='regular_customer', password='securepass123')
        response = self.client.get('/admin-dashboard/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin-dashboard/login/', response.url)

        # Attempt to log in to the admin dashboard login page with customer credentials
        self.client.logout()
        login_resp = self.client.post('/admin-dashboard/login/', {
            'username': 'regular_customer',
            'password': 'securepass123',
        })
        self.assertEqual(login_resp.status_code, 200)
        self.assertContains(login_resp, 'Access denied')


    def test_admin_dashboard_post_actions(self):
        User.objects.create_user(
            username='admin_worker',
            password='securepass123',
            is_staff=True,
        )
        self.client.login(username='admin_worker', password='securepass123')

        # 1. Add Customer action
        cust_resp = self.client.post('/admin-dashboard/customers/', {
            'action': 'add_customer',
            'username': 'new_customer_1',
            'password': 'Password123!',
            'first_name': 'New',
            'last_name': 'Subscriber',
            'phone_number': '0722000000',
            'email': 'sub@example.com',
        }, follow=True)
        self.assertEqual(cust_resp.status_code, 200)
        self.assertTrue(User.objects.filter(username='new_customer_1').exists())

        # 2. Create Package action
        pkg_resp = self.client.post('/admin-dashboard/packages/', {
            'action': 'create_package',
            'name': 'Monthly Pro',
            'price': '1500.00',
            'duration_hours': '720',
            'speed_limit_mbps': '20',
            'data_allowance_gb': '50',
            'upload_speed_mbps': '10',
            'download_speed_mbps': '20',
            'devices_allowed': '4',
            'description': 'High speed monthly internet',
        }, follow=True)
        self.assertEqual(pkg_resp.status_code, 200)
        created_pkg = Package.objects.filter(name='Monthly Pro').first()
        self.assertIsNotNone(created_pkg)

        # 3. Toggle Package action
        toggle_resp = self.client.post('/admin-dashboard/packages/', {
            'action': 'toggle_package',
            'package_id': created_pkg.id,
        }, follow=True)
        self.assertEqual(toggle_resp.status_code, 200)
        created_pkg.refresh_from_db()
        self.assertEqual(created_pkg.status, Package.STATUS_INACTIVE)

        # 4. Generate Vouchers action
        vouch_resp = self.client.post('/admin-dashboard/vouchers/', {
            'action': 'generate_vouchers',
            'package_id': self.package.id,
            'count': '5',
        }, follow=True)
        self.assertEqual(vouch_resp.status_code, 200)
        from .models import Voucher
        self.assertEqual(Voucher.objects.filter(package=self.package).count(), 5)

        # 5. Add Router action
        router_resp = self.client.post('/admin-dashboard/routers/', {
            'action': 'add_router',
            'name': 'Test Gateway',
            'ip_address': '192.168.10.1',
            'api_port': '8728',
            'username': 'admin',
            'password': 'password',
        }, follow=True)
        self.assertEqual(router_resp.status_code, 200)
        from .models import Router
        router = Router.objects.filter(name='Test Gateway').first()
        self.assertIsNotNone(router)

        # 6. Test Router action
        test_r_resp = self.client.post('/admin-dashboard/routers/', {
            'action': 'test_router',
            'router_id': router.id,
        }, follow=True)
        self.assertEqual(test_r_resp.status_code, 200)
        router.refresh_from_db()
        self.assertEqual(router.connection_status, 'connected')
