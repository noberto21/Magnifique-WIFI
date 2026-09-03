# Berto_satelite

A Django-based Wi‑Fi billing and hotspot management backend aligned with the provided business requirements.

## Included modules

- Customer registration and login using the Django auth system
- Wi‑Fi package catalog management
- Customer, payment, subscription, router, voucher, and session models
- M-Pesa payment abstraction and callback handling logic
- MikroTik RouterOS integration wrapper service
- Notification abstraction layer
- Admin dashboard API endpoints and captive portal endpoint
- Seed command for demo data

## Run locally

```bash
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

## API examples

- `POST /api/register/`
- `POST /api/login/`
- `GET /api/packages/`
- `GET /api/dashboard/`
- `POST /api/payment/initiate/`
- `POST /api/payment/callback/`
- `GET /api/portal/`

## Notes

This is a backend foundation designed to match the prompt. It intentionally keeps the business logic in Django services and exposes JSON APIs for the frontend to consume.
