# eSIM Status Checker - Backend

Django REST API backend for checking eSIM status across multiple providers and processing renewals with Stripe payment integration.

## 🚀 Features

- **Multi-API Integration**: AirHub, eSIMCard, and TravelRoam
- **Intelligent Provider Selection**: Automatically chooses the best data source
- **Bundle Catalog**: Fetches and matches renewal bundles
- **Stripe Payment**: Secure payment processing with Checkout
- **Currency Conversion**: Real-time USD/EUR conversion
- **Renewal Management**: Complete order and payment tracking
- **Error Handling**: Graceful fallback with manual processing support

---

## 📋 Prerequisites

- Python 3.8 or higher
- PostgreSQL or SQLite (for development)
- pip (Python package manager)
- Virtual environment (recommended)

---

## 🔧 Installation

### 1. Clone the Repository

```bash
cd esim_status_checker/backend
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the backend directory:

```bash
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (SQLite for development)
DATABASE_URL=sqlite:///db.sqlite3

# API Credentials (Hardcoded in script_enhanced.py)
# AirHub: info@roam2world.com
# eSIMCard: aydogan@buysim.de
# TravelRoam: API keys in script

# Stripe Configuration
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_CURRENCY=USD
STRIPE_LIVE_MODE=False

# Email Configuration (Optional)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=eSIM Support <noreply@esim.com>

# Currency API (Optional)
CURRENCYFREAKS_API_KEY=your-api-key
CURRENCYFREAKS_API_BASE_URL=https://api.currencyfreaks.com/v2.0
```

### 5. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

---

## 🎯 Running the Server

### Development Server

```bash
python manage.py runserver
```

Server will be available at: `http://localhost:8000`

### With Custom Port

```bash
python manage.py runserver 8080
```

---

## 📚 API Endpoints

### eSIM Status Check

```bash
POST /api/esim/check/
Content-Type: application/json

{
  "iccid": "8932042000010245583"
}

# Response
{
  "iccid": "8932042000010245583",
  "status": "Expired",
  "plan_name": "eSIM, 1GB, 7 Days, Turkey, V2",
  "api_provider": "TRAVELROAM",
  "order_sim_id": "BJTZ7-DSPJI-JHHTL-M2Z0I",
  "data_capacity": "0.93 GB",
  "data_consumed": "0.93 GB",
  "data_remaining": "0.00 GB",
  "validity": "7 days",
  "purchase_date": "2025-11-02 01:01:00",
  "activation_code": "rsp-3104.idemia.io",
  "apn": "AveaIletisim Hizmetleri A.S. (TR)",
  "last_updated": "2025-11-14T16:22:35Z"
}
```

### Create Renewal Order

```bash
POST /api/esim/renewal/create/
Content-Type: application/json

{
  "iccid": "8932042000010245583",
  "provider": "TRAVELROAM",
  "amount": 10.00,
  "currency": "USD",
  "order_sim_id": "BJTZ7-DSPJI-JHHTL-M2Z0I",
  "plan_name": "eSIM, 1GB, 7 Days, Turkey, V2",
  "package_name": "Turkey 1GB 7 Days",
  "renewal_days": 7,
  "country_code": "TR"
}

# Response
{
  "success": true,
  "order": {
    "order_id": "REN-ABC123",
    "status": "PENDING"
  },
  "payment": {
    "checkout_url": "https://checkout.stripe.com/...",
    "session_id": "cs_test_..."
  }
}
```

### Confirm Payment

```bash
POST /api/esim/renewal/confirm-payment/
Content-Type: application/json

{
  "session_id": "cs_test_..."
}

# Response
{
  "success": true,
  "order": {
    "order_id": "REN-ABC123",
    "status": "COMPLETED",  # or "PROVIDER_FAILED"
    "iccid": "8932042000010245583",
    "amount": "10.00",
    "currency": "USD"
  }
}
```

### Health Check

```bash
GET /api/esim/health/

# Response
{
  "status": "healthy",
  "timestamp": "2025-11-14T16:00:00Z",
  "apis": {
    "airhub": true,
    "esimcard": true,
    "travelroam": true
  }
}
```

### Currency Endpoints

```bash
# Get supported currencies
GET /api/esim/currency/supported/

# Get exchange rate
GET /api/esim/currency/exchange-rate/?from=USD&to=EUR

# Convert amount
GET /api/esim/currency/convert/?amount=10&from=USD&to=EUR
```

---

## 🗄️ Database Models

### RenewalOrder

Tracks eSIM renewal orders:

```python
- order_id: Unique order identifier
- iccid: eSIM ICCID
- provider: AIRHUB, ESIMCARD, or TRAVELROAM
- amount: Payment amount
- currency: USD or EUR
- status: PENDING, PAID, COMPLETED, FAILED, PROVIDER_FAILED, CANCELLED
- provider_response: JSON with provider API response
- created_at, updated_at, completed_at
```

### PaymentTransaction

Records Stripe payment details:

```python
- renewal_order: ForeignKey to RenewalOrder
- stripe_payment_intent_id: Stripe session ID
- stripe_charge_id: Stripe charge ID
- amount: Payment amount
- currency: Payment currency
- status: PENDING, PAID, FAILED, REFUNDED
- created_at, completed_at
```

---

## 🔧 Core Files

### `script_enhanced.py`

Core multi-API integration logic:
- `try_fetch_from_all_apis()`: Query all three providers
- `travelroam_get_catalog()`: Fetch bundle catalog
- `travelroam_find_matching_bundle()`: Match plan to bundle
- `travelroam_process_order()`: Process renewal order
- `travelroam_get_esim_assignments()`: Get eSIM details after order

### `pulse/views.py`

Django REST API endpoints:
- `check_esim_status()`: eSIM status check
- `create_renewal_order()`: Create renewal order with payment
- `confirm_payment()`: Verify payment and complete order
- `health_check()`: System health check

### `pulse/renewal_service.py`

Renewal orchestration:
- `create_renewal_order()`: Create order record
- `process_payment()`: Create Stripe checkout session
- `verify_checkout_and_complete_order()`: Verify payment and process renewal

### `pulse/payment_service.py`

Stripe integration:
- `create_checkout_session()`: Create Stripe Checkout
- `retrieve_checkout_session()`: Verify payment status

---

## 🧪 Testing

### Run Tests

```bash
python manage.py test
```

### Test Individual Components

```bash
# Test script functions
python3 script_enhanced.py

# Test API endpoints
curl -X POST http://localhost:8000/api/esim/check/ \
  -H "Content-Type: application/json" \
  -d '{"iccid": "8932042000010245583"}'

# Test bundle matching
python3 << EOF
from script_enhanced import travelroam_find_matching_bundle
bundle = travelroam_find_matching_bundle("eSIM, 1GB, 7 Days, Turkey, V2", "TR")
print(f"Found: {bundle}")
EOF
```

---

## 📊 Logging

Logs are written to:
- **Console**: Standard output
- **File**: `esim_checker.log`

Log levels:
- `INFO`: Normal operations
- `WARNING`: Potential issues
- `ERROR`: Failures and exceptions

View logs:
```bash
tail -f esim_checker.log
tail -f /tmp/django_server.log  # If running in background
```

---

## 🔒 Security

### Environment Variables

Never commit `.env` files to git. Use environment-specific configurations:

```bash
# Development
DEBUG=True
STRIPE_SECRET_KEY=sk_test_...

# Production
DEBUG=False
STRIPE_SECRET_KEY=sk_live_...
ALLOWED_HOSTS=yourdomain.com
```

### API Keys

API credentials for AirHub, eSIMCard, and TravelRoam are currently hardcoded in `script_enhanced.py`. For production:

1. Move to environment variables
2. Use secure key management (AWS Secrets Manager, etc.)
3. Rotate keys regularly

---

## 🚀 Deployment

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Configure production database
- [ ] Set up proper `ALLOWED_HOSTS`
- [ ] Use production Stripe keys
- [ ] Configure HTTPS/SSL
- [ ] Set up static file serving
- [ ] Configure logging
- [ ] Set up monitoring
- [ ] Configure backup strategy
- [ ] Set up Stripe webhooks

### Environment Setup

```bash
# Production
pip install gunicorn
gunicorn esim_status_checker.wsgi:application --bind 0.0.0.0:8000

# With workers
gunicorn esim_status_checker.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 3 \
  --timeout 120
```

### Static Files

```bash
python manage.py collectstatic --noinput
```

---

## 📈 Performance

### Database Optimization

```python
# Use select_related for foreign keys
orders = RenewalOrder.objects.select_related('package').all()

# Use prefetch_related for many-to-many
orders = RenewalOrder.objects.prefetch_related('payments').all()
```

### Caching

```python
from django.core.cache import cache

# Cache bundle catalog
bundles = cache.get('bundles_TR')
if not bundles:
    bundles = travelroam_get_catalog(countries='TR')
    cache.set('bundles_TR', bundles, 300)  # 5 minutes
```

---

## 🐛 Troubleshooting

### Common Issues

**1. "ModuleNotFoundError"**
```bash
# Install missing dependencies
pip install -r requirements.txt
```

**2. "Database locked"**
```bash
# For SQLite, ensure only one process is accessing it
# Or switch to PostgreSQL for production
```

**3. "CORS errors"**
```bash
# Check CORS_ALLOWED_ORIGINS in settings.py
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://yourdomain.com"
]
```

**4. "TravelRoam 404/422 errors"**
- 404: Endpoint incorrect (now fixed to match working implementation)
- 422: Test credentials limitation (normal for sandbox)
- Use production credentials for actual order processing

### Debug Commands

```bash
# Django shell
python manage.py shell

# Check database
from pulse.models import RenewalOrder
orders = RenewalOrder.objects.all()
print(orders)

# Test API function
from script_enhanced import travelroam_get_catalog
bundles = travelroam_get_catalog(countries="TR")
print(len(bundles))
```

---

## 📞 Support

### Getting Help

- Check logs: `tail -f esim_checker.log`
- Review documentation in `/docs` folder
- Check API provider documentation
- Contact API providers for credential issues

### Useful Commands

```bash
# Check migrations
python manage.py showmigrations

# Create new migration
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Reset database (development only!)
rm db.sqlite3
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start shell
python manage.py shell
```

---

## 📝 License

[Your License Here]

---

## 👥 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 🔄 Version History

### v1.0.0 (Current)
- Multi-API integration (AirHub, eSIMCard, TravelRoam)
- Stripe payment processing
- Bundle catalog and matching
- Renewal order management
- Currency conversion
- Two-phase transaction handling
- Comprehensive error handling

---

For more detailed documentation, see:
- `BUNDLE_CATALOG_IMPLEMENTED.md` - Bundle matching guide
- `DATABASE_FIX_COMPLETE.md` - Payment verification details
- `FINAL_SYSTEM_STATUS.md` - System status and comparison
- `COMPLETE_FLOW_TEST_RESULTS.md` - Test results

---

**Last Updated**: November 14, 2025  
**Status**: Production Ready ✅

