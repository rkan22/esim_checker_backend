from rest_framework import serializers
from .models import ESIMQuery, ESIMDetails, RenewalPackage, RenewalOrder, PaymentTransaction


class ESIMDetailsSerializer(serializers.Serializer):
    """Serializer for eSIM details response"""
    
    order_sim_id = serializers.CharField()
    iccid = serializers.CharField()
    plan_name = serializers.CharField()
    status = serializers.CharField()
    purchase_date = serializers.CharField()
    validity = serializers.CharField()
    data_capacity = serializers.CharField()
    data_consumed = serializers.CharField()
    data_remaining = serializers.CharField()
    activation_code = serializers.CharField()
    apn = serializers.CharField()
    api_provider = serializers.CharField()
    last_updated = serializers.DateTimeField(required=False)


class ESIMQueryRequestSerializer(serializers.Serializer):
    """Serializer for ICCID query request"""
    
    iccid = serializers.CharField(
        max_length=50,
        min_length=10,
        required=True,
        help_text="The ICCID of the eSIM to query"
    )
    
    def validate_iccid(self, value):
        """Validate ICCID format"""
        # Remove spaces and dashes
        cleaned = value.replace(' ', '').replace('-', '')
        
        # Check if alphanumeric
        if not cleaned.isalnum():
            raise serializers.ValidationError("ICCID must contain only letters and numbers")
        
        # Check minimum length
        if len(cleaned) < 10:
            raise serializers.ValidationError("ICCID seems too short (minimum 10 characters)")
        
        return value


class ErrorResponseSerializer(serializers.Serializer):
    """Serializer for error responses"""
    
    error = serializers.CharField()
    details = serializers.CharField(required=False)
    iccid = serializers.CharField(required=False)


# Renewal Serializers

class RenewalPackageSerializer(serializers.ModelSerializer):
    """Serializer for renewal packages"""
    
    class Meta:
        model = RenewalPackage
        fields = [
            'id', 'provider', 'package_id', 'package_name', 'description',
            'data_quantity', 'data_unit', 'validity_days', 'price', 'currency'
        ]


class CreateRenewalOrderSerializer(serializers.Serializer):
    """Serializer for creating a renewal order"""
    
    iccid = serializers.CharField(max_length=50, required=True)
    provider = serializers.ChoiceField(
        choices=['AIRHUB', 'ESIMCARD', 'TRAVELROAM'],
        required=True
    )
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    currency = serializers.CharField(max_length=3, default='USD')
    
    # eSIM details from status check
    order_sim_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    plan_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    package_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    package_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    renewal_days = serializers.IntegerField(required=False, default=7)
    country_code = serializers.CharField(max_length=2, required=False, allow_blank=True, allow_null=True)


class RenewalOrderSerializer(serializers.ModelSerializer):
    """Serializer for renewal orders"""
    
    package_details = RenewalPackageSerializer(source='package', read_only=True)
    payment_status = serializers.SerializerMethodField()
    
    class Meta:
        model = RenewalOrder
        fields = [
            'order_id', 'iccid', 'provider', 'package_details', 'amount', 'currency',
            'status', 'payment_status', 'customer_email', 'email_sent',
            'created_at', 'updated_at', 'completed_at'
        ]
    
    def get_payment_status(self, obj):
        """Get payment status if exists"""
        try:
            return obj.payment.status
        except PaymentTransaction.DoesNotExist:
            return None


class PaymentIntentResponseSerializer(serializers.Serializer):
    """Serializer for payment intent response"""
    
    payment_intent_id = serializers.CharField()
    client_secret = serializers.CharField()
    amount = serializers.FloatField()
    currency = serializers.CharField()


class ConfirmPaymentSerializer(serializers.Serializer):
    """Serializer for confirming payment"""
    
    payment_intent_id = serializers.CharField(required=True)


class SendEmailSerializer(serializers.Serializer):
    """Serializer for sending email request"""
    
    order_id = serializers.CharField(max_length=100, required=True)
    recipient_email = serializers.EmailField(required=True)
    email_type = serializers.ChoiceField(
        choices=['details', 'confirmation'],
        default='details'
    )

