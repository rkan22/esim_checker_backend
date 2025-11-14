"""
Renewal Service
Orchestrates eSIM renewal process including payment, provider API calls, and email notifications
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from .models import RenewalPackage, RenewalOrder, PaymentTransaction
from .payment_service import StripePaymentService, PaymentError
from .email_service import ESIMEmailService, EmailError
from .esim_service import try_fetch_from_all_apis

logger = logging.getLogger(__name__)

# Import renewal functions from script_enhanced.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from script_enhanced import (
    travelroam_get_catalog,
    travelroam_process_order,
    airhub_renew_plan,
    esimcard_check_topup_availability,
    esimcard_purchase_package,
    APIProvider
)


class RenewalError(Exception):
    """Custom exception for renewal errors"""
    pass


class RenewalService:
    """Service for managing eSIM renewals"""
    
    @staticmethod
    def get_available_packages(provider: str = None) -> List[Dict[str, Any]]:
        """
        Get available renewal packages from provider(s)
        
        Args:
            provider: Specific provider to fetch from (optional, fetches all if None)
            
        Returns:
            List of available packages with pricing
        """
        packages = []
        
        try:
            if provider is None or provider.upper() == 'TRAVELROAM':
                # Fetch TravelRoam packages
                try:
                    catalog = travelroam_get_catalog()
                    if catalog and 'bundles' in catalog:
                        for bundle in catalog['bundles']:
                            packages.append({
                                'provider': 'TRAVELROAM',
                                'package_id': bundle.get('name', ''),
                                'package_name': bundle.get('description', bundle.get('name', '')),
                                'data_quantity': bundle.get('data', 0),
                                'data_unit': 'GB',
                                'validity_days': bundle.get('validity', 0),
                                'price': bundle.get('price', 0),
                                'currency': 'USD',
                            })
                except Exception as e:
                    logger.error(f"Error fetching TravelRoam packages: {e}")
            
            # Add more providers as needed
            # For now, we'll return TravelRoam packages
            # AirHub and eSIMCard package listing would be added here
            
            logger.info(f"Retrieved {len(packages)} packages")
            return packages
            
        except Exception as e:
            logger.error(f"Error getting available packages: {e}")
            raise RenewalError(f"Failed to get available packages: {str(e)}")
    
    @staticmethod
    @transaction.atomic
    def create_renewal_order(
        iccid: str,
        provider: str,
        amount: Decimal,
        currency: str = 'USD',
        order_sim_id: str = None,
        plan_name: str = None,
        package_id: str = None,
        renewal_days: int = 7,
        country_code: str = None
    ) -> RenewalOrder:
        """
        Create a new renewal order
        
        Args:
            iccid: ICCID of the eSIM to renew
            provider: Provider name (AIRHUB, ESIMCARD, TRAVELROAM)
            amount: Amount to charge
            currency: Currency code
            order_sim_id: Provider's order/SIM ID
            plan_name: Current plan name
            package_id: Package ID (for catalog-based providers)
            renewal_days: Number of days to renew (for AirHub)
            
        Returns:
            Created RenewalOrder instance
        """
        try:
            # Generate unique order ID
            order_id = f"REN-{uuid.uuid4().hex[:12].upper()}"
            
            # Try to get the package from database
            package = None
            if package_id:
                try:
                    package = RenewalPackage.objects.get(
                        provider=provider.upper(),
                        package_id=package_id
                    )
                except RenewalPackage.DoesNotExist:
                    logger.warning(f"Package not found in DB: {provider} - {package_id}")
            
            # Create renewal order with provider details
            order = RenewalOrder.objects.create(
                order_id=order_id,
                iccid=iccid,
                provider=provider.upper(),
                package=package,
                amount=amount,
                currency=currency,
                status='PENDING',
                provider_order_id=order_sim_id or '',
                provider_response={
                    'plan_name': plan_name or '',
                    'package_id': package_id or '',
                    'renewal_days': int(renewal_days) if renewal_days else 7,
                    'country_code': country_code or ''
                }
            )
            
            logger.info(f"Created renewal order: {order_id} for {provider} - {iccid}")
            return order
            
        except Exception as e:
            logger.error(f"Error creating renewal order: {e}")
            raise RenewalError(f"Failed to create renewal order: {str(e)}")
    
    @staticmethod
    def process_payment(order: RenewalOrder, package_name: str = None) -> Dict[str, Any]:
        """
        Process payment for a renewal order using Stripe Checkout
        
        Args:
            order: RenewalOrder instance
            package_name: Package name for display in Stripe
            
        Returns:
            Dict containing checkout session details including URL
        """
        try:
            logger.info(f"Processing payment for order: {order.order_id}")
            
            # Create Stripe Checkout Session
            checkout_session = StripePaymentService.create_checkout_session(
                amount=order.amount,
                currency=order.currency,
                metadata={
                    'order_id': order.order_id,
                    'iccid': order.iccid,
                    'provider': order.provider,
                    'package_name': package_name or 'eSIM Bundle Renewal',
                },
                success_url=f'http://localhost:3000/renewal/success?session_id={{CHECKOUT_SESSION_ID}}',
                cancel_url='http://localhost:3000/renewal/cancelled'
            )
            
            # Create payment transaction record
            payment = PaymentTransaction.objects.create(
                renewal_order=order,
                stripe_payment_intent_id=checkout_session['id'],  # Store session ID
                amount=order.amount,
                currency=order.currency,
                status='PENDING',
                raw_response=checkout_session
            )
            
            logger.info(f"Checkout session created: {checkout_session['id']}")
            
            return {
                'session_id': checkout_session['id'],
                'checkout_url': checkout_session['url'],
                'amount': float(order.amount),
                'currency': str(order.currency),
            }
            
        except PaymentError as e:
            logger.error(f"Payment error for order {order.order_id}: {e}")
            order.status = 'FAILED'
            order.save()
            raise RenewalError(f"Payment failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error processing payment: {e}")
            order.status = 'FAILED'
            order.save()
            raise RenewalError(f"Failed to process payment: {str(e)}")
    
    @staticmethod
    def verify_checkout_and_complete_order(session_id: str) -> RenewalOrder:
        """
        Verify Stripe Checkout Session and complete the renewal order with provider
        
        This method performs two separate transactions:
        1. Verify payment with Stripe and update order to PAID (atomic)
        2. Process renewal with provider (can fail without rolling back payment)
        
        Args:
            session_id: Stripe Checkout Session ID
            
        Returns:
            Updated RenewalOrder instance
        """
        try:
            # Get payment transaction
            payment = PaymentTransaction.objects.get(
                stripe_payment_intent_id=session_id  # We store session ID here
            )
            order = payment.renewal_order
            
            logger.info(f"Verifying checkout and completing order: {order.order_id}")
            
            # Step 1: Verify payment with Stripe (in separate transaction)
            with transaction.atomic():
                # Retrieve checkout session from Stripe
                checkout_session = StripePaymentService.retrieve_checkout_session(session_id)
                
                # Update payment status
                payment.status = checkout_session['payment_status'].upper()
                if checkout_session.get('payment_intent'):
                    payment.stripe_charge_id = checkout_session['payment_intent']
                payment.save()
                
                if checkout_session['payment_status'] == 'paid':
                    # Payment successful, update order
                    order.status = 'PAID'
                    order.save()
                    logger.info(f"Order {order.order_id} marked as PAID")
                else:
                    order.status = 'FAILED'
                    order.save()
                    raise RenewalError(f"Payment not successful: {checkout_session['payment_status']}")
            
            # Step 2: Process renewal with provider (separate transaction, can fail independently)
            if order.status == 'PAID':
                try:
                    with transaction.atomic():
                        provider_response = RenewalService._process_with_provider(order)
                        
                        order.status = 'COMPLETED'
                        order.provider_response = provider_response
                        order.completed_at = timezone.now()
                        order.save()
                        
                        payment.status = 'SUCCEEDED'
                        payment.completed_at = timezone.now()
                        payment.save()
                        
                        logger.info(f"Order {order.order_id} completed successfully with provider")
                        
                except Exception as e:
                    logger.error(f"Provider API error for order {order.order_id}: {e}")
                    # Update order status to show provider API failed
                    # But payment was successful, so don't roll it back
                    with transaction.atomic():
                        order.refresh_from_db()  # Get latest state
                        order.status = 'PROVIDER_FAILED'
                        order.provider_response = {'error': str(e), 'payment_successful': True}
                        order.save()
                    
                    # Note: We don't raise the error here because payment was successful
                    # The order can be manually processed later
                    logger.warning(f"Order {order.order_id} payment succeeded but provider API failed. Manual processing may be required.")
            
            # Refresh order to get latest state
            order.refresh_from_db()
            return order
            
        except PaymentTransaction.DoesNotExist:
            logger.error(f"Payment transaction not found for session: {session_id}")
            raise RenewalError("Payment transaction not found")
        except RenewalError:
            # Re-raise RenewalErrors as-is
            raise
        except Exception as e:
            logger.error(f"Error confirming order: {e}")
            raise RenewalError(f"Failed to confirm order: {str(e)}")
    
    @staticmethod
    def _process_with_provider(order: RenewalOrder) -> Dict[str, Any]:
        """
        Process renewal with the appropriate provider API
        
        Args:
            order: RenewalOrder instance
            
        Returns:
            Provider API response
        """
        provider = order.provider
        provider_data = order.provider_response or {}
        
        try:
            if provider == 'TRAVELROAM':
                # Use TravelRoam API - top up existing eSIM
                from script_enhanced import travelroam_find_matching_bundle, travelroam_process_order
                
                plan_name = provider_data.get('plan_name', '')
                country_code = provider_data.get('country_code', None)
                
                # Try to get package_id from provider_response first
                bundle_name = provider_data.get('package_id', '')
                
                # If no package_id, find matching bundle from catalog
                if not bundle_name:
                    logger.info(f"No package_id found, searching catalog for: {plan_name}")
                    bundle_name = travelroam_find_matching_bundle(plan_name, country_code)
                
                if not bundle_name:
                    raise RenewalError(f"Could not find matching bundle for plan: {plan_name}")
                
                logger.info(f"TravelRoam renewal: bundle={bundle_name}, iccid={order.iccid}")
                response = travelroam_process_order(
                    bundle_name=bundle_name,
                    iccid=order.iccid
                )
                return response
                
            elif provider == 'AIRHUB':
                # Use AirHub API - renew with order ID
                airhub_order_id = order.provider_order_id
                renewal_days = provider_data.get('renewal_days', 7)
                
                logger.info(f"AirHub renewal: order_id={airhub_order_id}, days={renewal_days}")
                response = airhub_renew_plan(
                    order_id=airhub_order_id,
                    renewal_days=renewal_days,
                    user_amount=str(order.amount)
                )
                return response
                
            elif provider == 'ESIMCARD':
                # Use eSIMCard API - top up with package ID
                package_id = provider_data.get('package_id', '')
                
                logger.info(f"eSIMCard renewal: imei={order.iccid}, package={package_id}")
                response = esimcard_purchase_package(
                    imei=order.iccid,
                    package_type_id=package_id
                )
                return response
                
            else:
                raise RenewalError(f"Unknown provider: {provider}")
                
        except Exception as e:
            logger.error(f"Error processing with provider {provider}: {e}")
            raise
    
    @staticmethod
    def send_esim_details_email(
        order_id: str,
        recipient_email: str
    ) -> bool:
        """
        Send eSIM details to customer via email
        
        Args:
            order_id: Renewal order ID
            recipient_email: Customer's email address
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            # Get order
            order = RenewalOrder.objects.get(order_id=order_id)
            
            # Fetch latest eSIM details
            provider, airhub_order, airhub_activation, esimcard_data, usage_data, \
                travelroam_data, travelroam_bundles, travelroam_location = \
                try_fetch_from_all_apis(order.iccid)
            
            if not provider:
                raise RenewalError("Could not fetch eSIM details")
            
            # Prepare eSIM details for email
            esim_details = {
                'iccid': order.iccid,
                'order_sim_id': airhub_order.get('orderId', 'N/A') if airhub_order else 'N/A',
                'plan_name': airhub_order.get('planName', 'N/A') if airhub_order else 'N/A',
                'status': 'Active' if airhub_order and airhub_order.get('isActive') else 'Inactive',
                'purchase_date': airhub_order.get('purchaseDate', 'N/A') if airhub_order else 'N/A',
                'validity': airhub_order.get('vaildity', 'N/A') if airhub_order else 'N/A',
                'data_capacity': f"{airhub_order.get('capacity', 'N/A')} {airhub_order.get('capacityUnit', 'GB')}" if airhub_order else 'N/A',
                'data_consumed': airhub_order.get('dataConsumed', 'N/A') if airhub_order else 'N/A',
                'data_remaining': airhub_order.get('dataRemaining', 'N/A') if airhub_order else 'N/A',
                'activation_code': airhub_activation.get('activationCode', 'N/A') if airhub_activation else 'N/A',
                'apn': airhub_activation.get('apn', 'N/A') if airhub_activation else 'N/A',
            }
            
            # Send email
            ESIMEmailService.send_esim_details_email(
                recipient_email=recipient_email,
                esim_details=esim_details
            )
            
            # Update order
            order.customer_email = recipient_email
            order.email_sent = True
            order.email_sent_at = timezone.now()
            order.save()
            
            logger.info(f"eSIM details email sent for order: {order_id}")
            return True
            
        except RenewalOrder.DoesNotExist:
            logger.error(f"Order not found: {order_id}")
            raise RenewalError("Order not found")
        except EmailError as e:
            logger.error(f"Email error: {e}")
            raise RenewalError(f"Failed to send email: {str(e)}")
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise RenewalError(f"Failed to send email: {str(e)}")
    
    @staticmethod
    def send_renewal_confirmation_email(
        order_id: str,
        recipient_email: str
    ) -> bool:
        """
        Send renewal confirmation email to customer
        
        Args:
            order_id: Renewal order ID
            recipient_email: Customer's email address
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            # Get order
            order = RenewalOrder.objects.get(order_id=order_id)
            
            # Fetch latest eSIM details
            provider, airhub_order, airhub_activation, esimcard_data, usage_data, \
                travelroam_data, travelroam_bundles, travelroam_location = \
                try_fetch_from_all_apis(order.iccid)
            
            # Prepare renewal details
            renewal_details = {
                'order_id': order.order_id,
                'package_name': order.package.package_name if order.package else 'N/A',
                'amount': float(order.amount),
                'currency': order.currency,
            }
            
            # Prepare eSIM details
            esim_details = {
                'iccid': order.iccid,
                'plan_name': airhub_order.get('planName', 'N/A') if airhub_order else 'N/A',
                'status': 'Active' if airhub_order and airhub_order.get('isActive') else 'Inactive',
                'data_capacity': f"{airhub_order.get('capacity', 'N/A')} {airhub_order.get('capacityUnit', 'GB')}" if airhub_order else 'N/A',
            }
            
            # Send email
            ESIMEmailService.send_renewal_confirmation_email(
                recipient_email=recipient_email,
                renewal_details=renewal_details,
                esim_details=esim_details
            )
            
            # Update order
            order.customer_email = recipient_email
            order.email_sent = True
            order.email_sent_at = timezone.now()
            order.save()
            
            logger.info(f"Renewal confirmation email sent for order: {order_id}")
            return True
            
        except RenewalOrder.DoesNotExist:
            logger.error(f"Order not found: {order_id}")
            raise RenewalError("Order not found")
        except EmailError as e:
            logger.error(f"Email error: {e}")
            raise RenewalError(f"Failed to send email: {str(e)}")
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise RenewalError(f"Failed to send email: {str(e)}")

