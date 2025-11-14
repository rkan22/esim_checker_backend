from django.urls import path
from . import views

urlpatterns = [
    # eSIM Status Check
    path('check/', views.check_esim_status, name='check_esim_status'),
    path('health/', views.health_check, name='health_check'),
    path('stats/', views.get_query_stats, name='query_stats'),
    
    # Renewal Endpoints
    path('renewal/packages/', views.get_renewal_packages, name='get_renewal_packages'),
    path('renewal/create/', views.create_renewal_order, name='create_renewal_order'),
    path('renewal/confirm-payment/', views.confirm_payment, name='confirm_payment'),
    path('renewal/order/<str:order_id>/', views.get_renewal_order, name='get_renewal_order'),
    
    # Email Endpoint
    path('email/send/', views.send_esim_email, name='send_esim_email'),
    
    # Currency Endpoints
    path('currency/supported/', views.get_supported_currencies, name='get_supported_currencies'),
    path('currency/exchange-rate/', views.get_exchange_rate, name='get_exchange_rate'),
    path('currency/convert/', views.convert_currency, name='convert_currency'),
]

