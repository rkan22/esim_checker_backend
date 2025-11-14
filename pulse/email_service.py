"""
Email Service
Handles sending eSIM details and renewal confirmations via email
"""

import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailError(Exception):
    """Custom exception for email errors"""
    pass


class ESIMEmailService:
    """Service for sending eSIM-related emails"""
    
    @staticmethod
    def send_esim_details_email(
        recipient_email: str,
        esim_details: Dict[str, Any],
        subject: str = None
    ) -> bool:
        """
        Send eSIM details to a customer via email
        
        Args:
            recipient_email: Customer's email address
            esim_details: Dict containing eSIM information
            subject: Email subject (optional)
            
        Returns:
            bool: True if email sent successfully
            
        Raises:
            EmailError: If email sending fails
        """
        if not recipient_email:
            raise EmailError("Recipient email is required")
        
        if subject is None:
            subject = f"{settings.EMAIL_SUBJECT_PREFIX} Your eSIM Details"
        
        try:
            logger.info(f"Preparing eSIM details email for {recipient_email}")
            
            # Create HTML content
            html_content = ESIMEmailService._create_esim_details_html(esim_details)
            
            # Create plain text content
            text_content = ESIMEmailService._create_esim_details_text(esim_details)
            
            # Create email
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],
            )
            
            # Attach HTML alternative
            email.attach_alternative(html_content, "text/html")
            
            # Send email
            email.send(fail_silently=False)
            
            logger.info(f"eSIM details email sent successfully to {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send eSIM details email: {e}")
            raise EmailError(f"Failed to send email: {str(e)}")
    
    @staticmethod
    def send_renewal_confirmation_email(
        recipient_email: str,
        renewal_details: Dict[str, Any],
        esim_details: Dict[str, Any],
        subject: str = None
    ) -> bool:
        """
        Send renewal confirmation email to a customer
        
        Args:
            recipient_email: Customer's email address
            renewal_details: Dict containing renewal/order information
            esim_details: Dict containing eSIM information
            subject: Email subject (optional)
            
        Returns:
            bool: True if email sent successfully
            
        Raises:
            EmailError: If email sending fails
        """
        if not recipient_email:
            raise EmailError("Recipient email is required")
        
        if subject is None:
            subject = f"{settings.EMAIL_SUBJECT_PREFIX} eSIM Renewal Confirmation"
        
        try:
            logger.info(f"Preparing renewal confirmation email for {recipient_email}")
            
            # Create HTML content
            html_content = ESIMEmailService._create_renewal_confirmation_html(
                renewal_details, esim_details
            )
            
            # Create plain text content
            text_content = ESIMEmailService._create_renewal_confirmation_text(
                renewal_details, esim_details
            )
            
            # Create email
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],
            )
            
            # Attach HTML alternative
            email.attach_alternative(html_content, "text/html")
            
            # Send email
            email.send(fail_silently=False)
            
            logger.info(f"Renewal confirmation email sent successfully to {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send renewal confirmation email: {e}")
            raise EmailError(f"Failed to send email: {str(e)}")
    
    @staticmethod
    def _create_esim_details_html(details: Dict[str, Any]) -> str:
        """Create HTML content for eSIM details email"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(45deg, #1e3a8a 30%, #0891b2 90%);
                    color: white;
                    padding: 20px;
                    border-radius: 8px 8px 0 0;
                    text-align: center;
                }}
                .content {{
                    background: #f9fafb;
                    padding: 20px;
                    border: 1px solid #e5e7eb;
                    border-top: none;
                    border-radius: 0 0 8px 8px;
                }}
                .detail-row {{
                    margin: 12px 0;
                    padding: 10px;
                    background: white;
                    border-radius: 4px;
                }}
                .detail-label {{
                    font-weight: bold;
                    color: #1e3a8a;
                }}
                .detail-value {{
                    margin-top: 4px;
                    color: #4b5563;
                }}
                .activation-code {{
                    background: #fff7ed;
                    border: 2px solid #f97316;
                    padding: 15px;
                    border-radius: 4px;
                    margin: 20px 0;
                    word-break: break-all;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #e5e7eb;
                    text-align: center;
                    color: #6b7280;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📱 Your eSIM Details</h1>
            </div>
            <div class="content">
                <p>Here are the details for your eSIM:</p>
                
                <div class="detail-row">
                    <div class="detail-label">ICCID</div>
                    <div class="detail-value">{details.get('iccid', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Order/SIM ID</div>
                    <div class="detail-value">{details.get('order_sim_id', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Plan Name</div>
                    <div class="detail-value">{details.get('plan_name', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Status</div>
                    <div class="detail-value">{details.get('status', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Purchase Date</div>
                    <div class="detail-value">{details.get('purchase_date', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Validity</div>
                    <div class="detail-value">{details.get('validity', 'N/A')} days</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Data Capacity</div>
                    <div class="detail-value">{details.get('data_capacity', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Data Consumed</div>
                    <div class="detail-value">{details.get('data_consumed', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Data Remaining</div>
                    <div class="detail-value">{details.get('data_remaining', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">APN</div>
                    <div class="detail-value">{details.get('apn', 'N/A')}</div>
                </div>
                
                <div class="activation-code">
                    <div class="detail-label">⚡ Activation Code</div>
                    <div class="detail-value" style="margin-top: 10px; font-family: monospace; font-size: 12px;">
                        {details.get('activation_code', 'N/A')}
                    </div>
                </div>
                
                <p style="margin-top: 20px; color: #6b7280; font-size: 14px;">
                    <strong>Note:</strong> Keep this activation code secure. You'll need it to install your eSIM.
                </p>
            </div>
            <div class="footer">
                <p>This email was sent from eSIM Status Checker</p>
                <p>© {datetime.now().year} eSIM Support. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        return html
    
    @staticmethod
    def _create_esim_details_text(details: Dict[str, Any]) -> str:
        """Create plain text content for eSIM details email"""
        text = f"""
YOUR eSIM DETAILS
=====================================

ICCID: {details.get('iccid', 'N/A')}
Order/SIM ID: {details.get('order_sim_id', 'N/A')}
Plan Name: {details.get('plan_name', 'N/A')}
Status: {details.get('status', 'N/A')}
Purchase Date: {details.get('purchase_date', 'N/A')}
Validity: {details.get('validity', 'N/A')} days
Data Capacity: {details.get('data_capacity', 'N/A')}
Data Consumed: {details.get('data_consumed', 'N/A')}
Data Remaining: {details.get('data_remaining', 'N/A')}
APN: {details.get('apn', 'N/A')}

ACTIVATION CODE:
{details.get('activation_code', 'N/A')}

Note: Keep this activation code secure. You'll need it to install your eSIM.

This email was sent from eSIM Status Checker
© {datetime.now().year} eSIM Support. All rights reserved.
        """
        return text.strip()
    
    @staticmethod
    def _create_renewal_confirmation_html(
        renewal_details: Dict[str, Any],
        esim_details: Dict[str, Any]
    ) -> str:
        """Create HTML content for renewal confirmation email"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(45deg, #059669 30%, #10b981 90%);
                    color: white;
                    padding: 20px;
                    border-radius: 8px 8px 0 0;
                    text-align: center;
                }}
                .content {{
                    background: #f9fafb;
                    padding: 20px;
                    border: 1px solid #e5e7eb;
                    border-top: none;
                    border-radius: 0 0 8px 8px;
                }}
                .success-box {{
                    background: #d1fae5;
                    border: 2px solid #059669;
                    padding: 15px;
                    border-radius: 4px;
                    margin: 20px 0;
                    text-align: center;
                }}
                .detail-row {{
                    margin: 12px 0;
                    padding: 10px;
                    background: white;
                    border-radius: 4px;
                }}
                .detail-label {{
                    font-weight: bold;
                    color: #1e3a8a;
                }}
                .detail-value {{
                    margin-top: 4px;
                    color: #4b5563;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #e5e7eb;
                    text-align: center;
                    color: #6b7280;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>✅ eSIM Renewal Confirmed!</h1>
            </div>
            <div class="content">
                <div class="success-box">
                    <h2 style="color: #059669; margin: 0;">Payment Successful!</h2>
                    <p style="margin: 10px 0 0 0;">Your eSIM has been successfully renewed.</p>
                </div>
                
                <h3>Order Details</h3>
                <div class="detail-row">
                    <div class="detail-label">Order ID</div>
                    <div class="detail-value">{renewal_details.get('order_id', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Package</div>
                    <div class="detail-value">{renewal_details.get('package_name', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Amount Paid</div>
                    <div class="detail-value">${renewal_details.get('amount', '0.00')} {renewal_details.get('currency', 'USD')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Date</div>
                    <div class="detail-value">{datetime.now().strftime('%B %d, %Y %I:%M %p')}</div>
                </div>
                
                <h3 style="margin-top: 30px;">eSIM Details</h3>
                <div class="detail-row">
                    <div class="detail-label">ICCID</div>
                    <div class="detail-value">{esim_details.get('iccid', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Plan Name</div>
                    <div class="detail-value">{esim_details.get('plan_name', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Status</div>
                    <div class="detail-value">{esim_details.get('status', 'N/A')}</div>
                </div>
                
                <div class="detail-row">
                    <div class="detail-label">Data Capacity</div>
                    <div class="detail-value">{esim_details.get('data_capacity', 'N/A')}</div>
                </div>
                
                <p style="margin-top: 20px; color: #6b7280; font-size: 14px;">
                    <strong>Note:</strong> Your eSIM renewal will be active shortly. Please allow up to 10 minutes for the changes to take effect.
                </p>
            </div>
            <div class="footer">
                <p>Thank you for using eSIM Status Checker!</p>
                <p>© {datetime.now().year} eSIM Support. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        return html
    
    @staticmethod
    def _create_renewal_confirmation_text(
        renewal_details: Dict[str, Any],
        esim_details: Dict[str, Any]
    ) -> str:
        """Create plain text content for renewal confirmation email"""
        text = f"""
eSIM RENEWAL CONFIRMED!
=====================================

✅ Payment Successful!
Your eSIM has been successfully renewed.

ORDER DETAILS
-----------
Order ID: {renewal_details.get('order_id', 'N/A')}
Package: {renewal_details.get('package_name', 'N/A')}
Amount Paid: ${renewal_details.get('amount', '0.00')} {renewal_details.get('currency', 'USD')}
Date: {datetime.now().strftime('%B %d, %Y %I:%M %p')}

eSIM DETAILS
-----------
ICCID: {esim_details.get('iccid', 'N/A')}
Plan Name: {esim_details.get('plan_name', 'N/A')}
Status: {esim_details.get('status', 'N/A')}
Data Capacity: {esim_details.get('data_capacity', 'N/A')}

Note: Your eSIM renewal will be active shortly. Please allow up to 10 minutes for the changes to take effect.

Thank you for using eSIM Status Checker!
© {datetime.now().year} eSIM Support. All rights reserved.
        """
        return text.strip()

