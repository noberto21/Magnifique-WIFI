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

    def test_django_admin_remains_available(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)
