from django.core.management.base import BaseCommand

from wifi_billing.models import Package, Router, User


class Command(BaseCommand):
    help = 'Seed the Wi-Fi billing database with default packages and a demo router.'

    def handle(self, *args, **options):
        if not Package.objects.exists():
            Package.objects.create(
                name='Daily',
                description='24-hour internet access',
                price=50,
                duration_hours=24,
                speed_limit_mbps=5,
                data_allowance_gb=1,
                upload_speed_mbps=2,
                download_speed_mbps=5,
                devices_allowed=2,
            )
            Package.objects.create(
                name='Weekly',
                description='7-day internet access',
                price=250,
                duration_hours=168,
                speed_limit_mbps=10,
                data_allowance_gb=5,
                upload_speed_mbps=5,
                download_speed_mbps=10,
                devices_allowed=3,
            )
            Package.objects.create(
                name='Monthly',
                description='30-day internet access',
                price=1000,
                duration_hours=720,
                speed_limit_mbps=15,
                data_allowance_gb=20,
                upload_speed_mbps=8,
                download_speed_mbps=15,
                devices_allowed=4,
            )

        if not Router.objects.exists():
            Router.objects.create(
                name='Main Router',
                ip_address='192.168.88.1',
                api_port=8728,
                username='admin',
                password='secret-password',
                connection_status='disconnected',
            )

        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin123')

        self.stdout.write(self.style.SUCCESS('Database seeded successfully'))
