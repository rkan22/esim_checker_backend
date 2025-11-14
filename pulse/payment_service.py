"""
Stripe Payment Service
Handles payment processing for eSIM renewals
"""

import stripe
import logging
from django.conf import settings
from typing import Dict, Any
from decimal import Decimal

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentError(Exception):
    """Custom exception for payment errors"""
    pass


class StripePaymentService:
    """Service for handling Stripe payments"""
    
    @staticmethod
    def create_checkout_session(
        amount: Decimal,
        currency: str = None,
        metadata: Dict[str, Any] = None,
        success_url: str = None,
        cancel_url: str = None,
        customer_email: str = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout Session
        
        Args:
            amount: Amount to charge (in base currency units, e.g., dollars)
            currency: Currency code (default: USD)
            metadata: Additional metadata for the payment
            success_url: URL to redirect to after successful payment
            cancel_url: URL to redirect to if payment is cancelled
            customer_email: Pre-fill customer email
            
        Returns:
            Dict containing checkout session details including url
            
        Raises:
            PaymentError: If checkout session creation fails
        """
        if currency is None:
            currency = settings.STRIPE_CURRENCY.lower()
        
        if success_url is None:
            success_url = 'http://localhost:3000/renewal/success?session_id={CHECKOUT_SESSION_ID}'
        
        if cancel_url is None:
            cancel_url = 'http://localhost:3000/renewal/cancelled'
        
        # Convert amount to cents (Stripe requires smallest currency unit)
        amount_cents = int(amount * 100)
        
        try:
            logger.info(f"Creating Stripe checkout session for ${amount} {currency}")
            
            session_params = {
                'payment_method_types': ['card'],
                'line_items': [{
                    'price_data': {
                        'currency': currency,
                        'product_data': {
                            'name': 'eSIM Bundle Renewal',
                            'description': metadata.get('package_name', 'eSIM Data Package') if metadata else 'eSIM Data Package',
                        },
                        'unit_amount': amount_cents,
                    },
                    'quantity': 1,
                }],
                'mode': 'payment',
                'success_url': success_url,
                'cancel_url': cancel_url,
                'metadata': metadata or {},
            }
            
            if customer_email:
                session_params['customer_email'] = customer_email
            
            checkout_session = stripe.checkout.Session.create(**session_params)
            
            logger.info(f"Checkout session created: {checkout_session.id}")
            
            return {
                'id': checkout_session.id,
                'url': checkout_session.url,
                'status': checkout_session.status,
                'amount': float(amount),
                'currency': str(currency),
                'payment_status': checkout_session.payment_status,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise PaymentError(f"Failed to create checkout session: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating checkout session: {e}")
            raise PaymentError(f"Unexpected error: {str(e)}")
    
    @staticmethod
    def retrieve_checkout_session(session_id: str) -> Dict[str, Any]:
        """
        Retrieve a Stripe Checkout Session
        
        Args:
            session_id: Stripe Checkout Session ID
            
        Returns:
            Dict containing checkout session details
            
        Raises:
            PaymentError: If retrieval fails
        """
        try:
            logger.info(f"Retrieving checkout session: {session_id}")
            
            session = stripe.checkout.Session.retrieve(session_id)
            
            return {
                'id': session.id,
                'status': session.status,
                'payment_status': session.payment_status,
                'amount_total': session.amount_total / 100 if session.amount_total else 0,
                'currency': session.currency,
                'payment_intent': session.payment_intent,
                'metadata': session.metadata,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving checkout session: {e}")
            raise PaymentError(f"Failed to retrieve checkout session: {str(e)}")
    
    @staticmethod
    def create_payment_intent(
        amount: Decimal,
        currency: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe Payment Intent (kept for backward compatibility)
        
        Args:
            amount: Amount to charge (in base currency units, e.g., dollars)
            currency: Currency code (default: USD)
            metadata: Additional metadata for the payment
            
        Returns:
            Dict containing payment intent details including client_secret
            
        Raises:
            PaymentError: If payment intent creation fails
        """
        if currency is None:
            currency = settings.STRIPE_CURRENCY.lower()
        
        # Convert amount to cents (Stripe requires smallest currency unit)
        amount_cents = int(amount * 100)
        
        try:
            logger.info(f"Creating Stripe payment intent for ${amount} {currency}")
            
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={'enabled': True},
            )
            
            logger.info(f"Payment intent created: {payment_intent.id}")
            
            return {
                'id': payment_intent.id,
                'client_secret': payment_intent.client_secret,
                'status': payment_intent.status,
                'amount': amount,
                'currency': currency,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {e}")
            raise PaymentError(f"Failed to create payment intent: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating payment intent: {e}")
            raise PaymentError(f"Unexpected error: {str(e)}")
    
    @staticmethod
    def retrieve_payment_intent(payment_intent_id: str) -> Dict[str, Any]:
        """
        Retrieve a Stripe Payment Intent
        
        Args:
            payment_intent_id: Stripe Payment Intent ID
            
        Returns:
            Dict containing payment intent details
            
        Raises:
            PaymentError: If retrieval fails
        """
        try:
            logger.info(f"Retrieving payment intent: {payment_intent_id}")
            
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            return {
                'id': payment_intent.id,
                'status': payment_intent.status,
                'amount': payment_intent.amount / 100,  # Convert cents to dollars
                'currency': payment_intent.currency,
                'charge_id': payment_intent.latest_charge if payment_intent.latest_charge else None,
                'metadata': payment_intent.metadata,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving payment intent: {e}")
            raise PaymentError(f"Failed to retrieve payment intent: {str(e)}")
    
    @staticmethod
    def confirm_payment_intent(payment_intent_id: str) -> Dict[str, Any]:
        """
        Confirm a Stripe Payment Intent
        
        Args:
            payment_intent_id: Stripe Payment Intent ID
            
        Returns:
            Dict containing confirmed payment details
            
        Raises:
            PaymentError: If confirmation fails
        """
        try:
            logger.info(f"Confirming payment intent: {payment_intent_id}")
            
            payment_intent = stripe.PaymentIntent.confirm(payment_intent_id)
            
            return {
                'id': payment_intent.id,
                'status': payment_intent.status,
                'amount': payment_intent.amount / 100,
                'currency': payment_intent.currency,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error confirming payment intent: {e}")
            raise PaymentError(f"Failed to confirm payment intent: {str(e)}")
    
    @staticmethod
    def cancel_payment_intent(payment_intent_id: str) -> Dict[str, Any]:
        """
        Cancel a Stripe Payment Intent
        
        Args:
            payment_intent_id: Stripe Payment Intent ID
            
        Returns:
            Dict containing cancellation details
            
        Raises:
            PaymentError: If cancellation fails
        """
        try:
            logger.info(f"Cancelling payment intent: {payment_intent_id}")
            
            payment_intent = stripe.PaymentIntent.cancel(payment_intent_id)
            
            return {
                'id': payment_intent.id,
                'status': payment_intent.status,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error cancelling payment intent: {e}")
            raise PaymentError(f"Failed to cancel payment intent: {str(e)}")
    
    @staticmethod
    def create_refund(charge_id: str, amount: Decimal = None) -> Dict[str, Any]:
        """
        Create a refund for a charge
        
        Args:
            charge_id: Stripe Charge ID
            amount: Amount to refund (optional, full refund if not provided)
            
        Returns:
            Dict containing refund details
            
        Raises:
            PaymentError: If refund creation fails
        """
        try:
            refund_data = {'charge': charge_id}
            
            if amount is not None:
                refund_data['amount'] = int(amount * 100)
            
            logger.info(f"Creating refund for charge: {charge_id}")
            
            refund = stripe.Refund.create(**refund_data)
            
            return {
                'id': refund.id,
                'status': refund.status,
                'amount': refund.amount / 100,
                'currency': refund.currency,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating refund: {e}")
            raise PaymentError(f"Failed to create refund: {str(e)}")
    
    @staticmethod
    def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """
        Handle Stripe webhook events
        
        Args:
            payload: Raw request body
            sig_header: Stripe signature header
            
        Returns:
            Dict containing event data
            
        Raises:
            PaymentError: If webhook verification fails
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            
            logger.info(f"Received Stripe webhook event: {event['type']}")
            
            return {
                'type': event['type'],
                'data': event['data']['object'],
            }
            
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise PaymentError("Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise PaymentError("Invalid signature")

