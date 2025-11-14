from django.db import models
from django.utils import timezone


class ESIMQuery(models.Model):
    """Model to track eSIM queries for analytics"""
    
    API_PROVIDER_CHOICES = [
        ('AIRHUB', 'AirHub'),
        ('ESIMCARD', 'eSIMCard'),
        ('TRAVELROAM', 'TravelRoam'),
    ]
    
    iccid = models.CharField(max_length=50, db_index=True)
    api_provider = models.CharField(max_length=20, choices=API_PROVIDER_CHOICES)
    query_timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    was_successful = models.BooleanField(default=True)
    error_message = models.TextField(null=True, blank=True)
    
    # Cache the response for quick retrieval
    cached_response = models.JSONField(null=True, blank=True)
    cache_expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-query_timestamp']
        indexes = [
            models.Index(fields=['iccid', '-query_timestamp']),
        ]
    
    def __str__(self):
        return f"{self.iccid} - {self.api_provider} - {self.query_timestamp}"
    
    def is_cache_valid(self):
        """Check if cached response is still valid"""
        if not self.cache_expires_at or not self.cached_response:
            return False
        return timezone.now() < self.cache_expires_at


class ESIMDetails(models.Model):
    """Model to store eSIM details"""
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('INSTALLED', 'Installed'),
        ('RELEASED', 'Released'),
        ('ENABLED', 'Enabled'),
        ('DISABLED', 'Disabled'),
    ]
    
    iccid = models.CharField(max_length=50, unique=True, db_index=True)
    order_sim_id = models.CharField(max_length=100, blank=True)
    plan_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True)
    purchase_date = models.CharField(max_length=50, blank=True)
    validity_days = models.IntegerField(null=True, blank=True)
    data_capacity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    data_capacity_unit = models.CharField(max_length=10, default='GB')
    data_consumed = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    data_consumed_unit = models.CharField(max_length=10, default='GB')
    data_remaining = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    data_remaining_unit = models.CharField(max_length=10, default='GB')
    activation_code = models.TextField(blank=True)
    apn = models.CharField(max_length=255, blank=True)
    
    # Metadata
    api_provider = models.CharField(max_length=20)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "eSIM Details"
        ordering = ['-last_updated']
    
    def __str__(self):
        return f"{self.iccid} - {self.plan_name}"


class RenewalPackage(models.Model):
    """Model to store available renewal packages from different providers"""
    
    PROVIDER_CHOICES = [
        ('AIRHUB', 'AirHub'),
        ('ESIMCARD', 'eSIMCard'),
        ('TRAVELROAM', 'TravelRoam'),
    ]
    
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    package_id = models.CharField(max_length=255)  # Provider's package ID
    package_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    data_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    data_unit = models.CharField(max_length=10, default='GB')
    validity_days = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['provider', 'price']
        unique_together = ['provider', 'package_id']
    
    def __str__(self):
        return f"{self.provider} - {self.package_name} - ${self.price}"


class RenewalOrder(models.Model):
    """Model to track renewal/top-up orders"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Payment'),
        ('PAID', 'Payment Confirmed'),
        ('PROCESSING', 'Processing with Provider'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('PROVIDER_FAILED', 'Payment Successful - Provider Processing Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PROVIDER_CHOICES = [
        ('AIRHUB', 'AirHub'),
        ('ESIMCARD', 'eSIMCard'),
        ('TRAVELROAM', 'TravelRoam'),
    ]
    
    order_id = models.CharField(max_length=100, unique=True, db_index=True)
    iccid = models.CharField(max_length=50, db_index=True)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    package = models.ForeignKey(RenewalPackage, on_delete=models.SET_NULL, null=True)
    
    # Order details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Provider response
    provider_order_id = models.CharField(max_length=255, blank=True)
    provider_response = models.JSONField(null=True, blank=True)
    
    # Email details
    customer_email = models.EmailField(blank=True)
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order {self.order_id} - {self.iccid} - {self.status}"


class PaymentTransaction(models.Model):
    """Model to track Stripe payment transactions"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SUCCEEDED', 'Succeeded'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    ]
    
    renewal_order = models.OneToOneField(RenewalOrder, on_delete=models.CASCADE, related_name='payment')
    
    # Stripe details
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True)
    stripe_charge_id = models.CharField(max_length=255, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Metadata
    payment_method = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    raw_response = models.JSONField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payment {self.stripe_payment_intent_id} - {self.status}"
