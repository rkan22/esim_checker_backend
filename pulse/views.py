from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
import logging

from .serializers import (
    ESIMDetailsSerializer,
    ESIMQueryRequestSerializer,
    ErrorResponseSerializer,
    RenewalPackageSerializer,
    CreateRenewalOrderSerializer,
    RenewalOrderSerializer,
    PaymentIntentResponseSerializer,
    ConfirmPaymentSerializer,
    SendEmailSerializer
)
from .esim_service import ESIMService
from .models import ESIMQuery, RenewalOrder
from .renewal_service import RenewalService, RenewalError
from .currency_service import currency_service, CurrencyConversionError
from script_enhanced import OrderNotFoundError, APIError, AuthenticationError

logger = logging.getLogger(__name__)


@api_view(['POST'])
@csrf_exempt
def check_esim_status(request):
    """
    API endpoint to check eSIM status by ICCID
    
    POST /api/esim/check/
    Body: {"iccid": "89001012345678901234"}
    
    Returns:
        200: eSIM details found
        400: Invalid ICCID format
        404: eSIM not found
        500: Server error
    """
    # Validate request
    serializer = ESIMQueryRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid ICCID', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    iccid = serializer.validated_data['iccid']
    
    try:
        # Fetch eSIM details
        esim_data = ESIMService.get_esim_details(iccid)
        
        # Log the query
        ESIMQuery.objects.create(
            iccid=iccid,
            api_provider=esim_data.get('api_provider', 'UNKNOWN'),
            response_time_ms=esim_data.get('response_time_ms'),
            was_successful=True,
            cached_response=esim_data
        )
        
        # Serialize and return response
        response_serializer = ESIMDetailsSerializer(data=esim_data)
        if response_serializer.is_valid():
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(esim_data, status=status.HTTP_200_OK)
        
    except OrderNotFoundError as e:
        logger.warning(f"eSIM not found: {iccid}")
        
        # Log failed query
        ESIMQuery.objects.create(
            iccid=iccid,
            api_provider='NONE',
            was_successful=False,
            error_message=str(e)
        )
        
        return Response(
            {'error': 'eSIM not found', 'details': str(e), 'iccid': iccid},
            status=status.HTTP_404_NOT_FOUND
        )
    
    except (APIError, AuthenticationError) as e:
        logger.error(f"API error for ICCID {iccid}: {e}")
        
        # Log failed query
        ESIMQuery.objects.create(
            iccid=iccid,
            api_provider='ERROR',
            was_successful=False,
            error_message=str(e)
        )
        
        return Response(
            {'error': 'API Error', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    except Exception as e:
        logger.exception(f"Unexpected error for ICCID {iccid}: {e}")
        
        # Log failed query
        ESIMQuery.objects.create(
            iccid=iccid,
            api_provider='ERROR',
            was_successful=False,
            error_message=str(e)
        )
        
        return Response(
            {'error': 'Server Error', 'details': 'An unexpected error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint
    
    GET /api/health/
    """
    return Response({
        'status': 'healthy',
        'service': 'eSIM Status Checker API',
        'version': '1.0.0'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_query_stats(request):
    """
    Get query statistics
    
    GET /api/stats/
    """
    total_queries = ESIMQuery.objects.count()
    successful_queries = ESIMQuery.objects.filter(was_successful=True).count()
    
    # Provider breakdown
    provider_stats = {}
    for provider in ['AIRHUB', 'ESIMCARD', 'TRAVELROAM']:
        count = ESIMQuery.objects.filter(
            api_provider=provider,
            was_successful=True
        ).count()
        provider_stats[provider] = count
    
    return Response({
        'total_queries': total_queries,
        'successful_queries': successful_queries,
        'failed_queries': total_queries - successful_queries,
        'provider_stats': provider_stats,
    }, status=status.HTTP_200_OK)


# ==========================================
# RENEWAL API ENDPOINTS
# ==========================================

@api_view(['GET'])
def get_renewal_packages(request):
    """
    Get available renewal packages
    
    GET /api/esim/renewal/packages/?provider=TRAVELROAM
    """
    provider = request.query_params.get('provider', None)
    
    try:
        packages = RenewalService.get_available_packages(provider)
        serializer = RenewalPackageSerializer(packages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except RenewalError as e:
        logger.error(f"Error fetching packages: {e}")
        return Response(
            {'error': 'Failed to fetch packages', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@csrf_exempt
def create_renewal_order(request):
    """
    Create a new renewal order with currency conversion
    
    POST /api/esim/renewal/create/
    Body: {
        "iccid": "89001012345678901234",
        "package_id": "esim_1GB_7D_IN_U",
        "provider": "TRAVELROAM",
        "amount": 9.99,
        "currency": "EUR",
        "package_name": "1GB Turkey 7 Days"
    }
    """
    from decimal import Decimal
    
    serializer = CreateRenewalOrderSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid request data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        data = serializer.validated_data
        
        # Get currency and amount
        original_currency = data.get('currency', 'USD')
        original_amount = Decimal(str(data['amount']))
        
        # If currency is not USD, convert it
        if original_currency != 'USD':
            try:
                conversion_result = currency_service.convert_amount(
                    original_amount,
                    'USD',
                    original_currency
                )
                final_amount = Decimal(str(conversion_result['converted_amount']))
                logger.info(f"Converted ${original_amount} USD to {conversion_result['formatted_converted']}")
            except CurrencyConversionError as e:
                logger.warning(f"Currency conversion failed: {e}. Using original amount.")
                final_amount = original_amount
        else:
            final_amount = original_amount
        
        order = RenewalService.create_renewal_order(
            iccid=data['iccid'],
            provider=data['provider'],
            amount=final_amount,
            currency=original_currency,
            order_sim_id=data.get('order_sim_id'),
            plan_name=data.get('plan_name'),
            package_id=data.get('package_id'),
            renewal_days=data.get('renewal_days', 7),
            country_code=data.get('country_code')
        )
        
        # Create Stripe Checkout Session
        payment_data = RenewalService.process_payment(
            order,
            package_name=data.get('package_name', 'eSIM Bundle Renewal')
        )
        
        # Return order and payment details
        order_serializer = RenewalOrderSerializer(order)
        return Response({
            'order': order_serializer.data,
            'payment': payment_data
        }, status=status.HTTP_201_CREATED)
        
    except RenewalError as e:
        logger.error(f"Error creating renewal order: {e}")
        return Response(
            {'error': 'Failed to create order', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@csrf_exempt
def confirm_payment(request):
    """
    Confirm Stripe Checkout payment and complete renewal order
    
    POST /api/esim/renewal/confirm-payment/
    Body: {
        "session_id": "cs_test_xxxxxxxxxxxxx"
    }
    """
    session_id = request.data.get('session_id') or request.data.get('payment_intent_id')
    
    if not session_id:
        return Response(
            {'error': 'session_id or payment_intent_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        order = RenewalService.verify_checkout_and_complete_order(
            session_id=session_id
        )
        
        order_serializer = RenewalOrderSerializer(order)
        return Response({
            'success': True,
            'order': order_serializer.data,
            'message': 'Payment confirmed and order completed successfully'
        }, status=status.HTTP_200_OK)
        
    except RenewalError as e:
        logger.error(f"Error confirming payment: {e}")
        return Response(
            {'error': 'Failed to confirm payment', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@csrf_exempt
def send_esim_email(request):
    """
    Send eSIM details via email
    
    POST /api/esim/email/send/
    Body: {
        "order_id": "REN-XXXXXXXXXXXX",
        "recipient_email": "customer@example.com",
        "email_type": "details"  // or "confirmation"
    }
    """
    serializer = SendEmailSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid request data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        order_id = serializer.validated_data['order_id']
        recipient_email = serializer.validated_data['recipient_email']
        email_type = serializer.validated_data.get('email_type', 'details')
        
        if email_type == 'confirmation':
            RenewalService.send_renewal_confirmation_email(order_id, recipient_email)
        else:
            RenewalService.send_esim_details_email(order_id, recipient_email)
        
        return Response({
            'success': True,
            'message': 'Email sent successfully'
        }, status=status.HTTP_200_OK)
        
    except RenewalError as e:
        logger.error(f"Error sending email: {e}")
        return Response(
            {'error': 'Failed to send email', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_renewal_order(request, order_id):
    """
    Get renewal order details
    
    GET /api/esim/renewal/order/{order_id}/
    """
    try:
        order = RenewalOrder.objects.get(order_id=order_id)
        serializer = RenewalOrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except RenewalOrder.DoesNotExist:
        return Response(
            {'error': 'Order not found'},
            status=status.HTTP_404_NOT_FOUND
        )


# ==========================================
# CURRENCY API ENDPOINTS
# ==========================================

@api_view(['GET'])
def get_supported_currencies(request):
    """
    Get list of supported currencies
    
    GET /api/esim/currency/supported/
    """
    try:
        currencies = currency_service.get_supported_currencies()
        return Response({
            'success': True,
            'data': currencies
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error fetching supported currencies: {e}")
        return Response(
            {'error': 'Failed to fetch currencies', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_exchange_rate(request):
    """
    Get exchange rate between two currencies
    
    GET /api/esim/currency/exchange-rate/?from=USD&to=EUR
    """
    from_currency = request.query_params.get('from', 'USD')
    to_currency = request.query_params.get('to', 'EUR')
    
    try:
        rate = currency_service.get_exchange_rate(from_currency, to_currency)
        return Response({
            'success': True,
            'data': {
                'from': from_currency,
                'to': to_currency,
                'rate': float(rate),
                'formatted': f"1 {from_currency} = {rate} {to_currency}"
            }
        }, status=status.HTTP_200_OK)
    except CurrencyConversionError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error fetching exchange rate: {e}")
        return Response(
            {'error': 'Failed to fetch exchange rate', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@csrf_exempt
def convert_currency(request):
    """
    Convert amount between currencies
    
    POST /api/esim/currency/convert/
    Body: {
        "amount": 100,
        "from_currency": "USD",
        "to_currency": "EUR"
    }
    """
    from decimal import Decimal
    
    amount = request.data.get('amount')
    from_currency = request.data.get('from_currency', 'USD')
    to_currency = request.data.get('to_currency', 'EUR')
    
    if not amount:
        return Response(
            {'error': 'Amount is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        result = currency_service.convert_amount(
            Decimal(str(amount)),
            from_currency,
            to_currency
        )
        return Response({
            'success': True,
            'data': result
        }, status=status.HTTP_200_OK)
    except CurrencyConversionError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error converting currency: {e}")
        return Response(
            {'error': 'Failed to convert currency', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
