"""
Currency Conversion Service
Uses CurrencyFreaks API for real-time exchange rates
"""

import requests
import logging
from decimal import Decimal
from typing import Dict, Optional
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# CurrencyFreaks API Configuration
CURRENCYFREAKS_API_KEY = "c0c09a9d787e4b38b93aec15e8bd5e8f"  # Free tier API key
CURRENCYFREAKS_API_BASE_URL = "https://api.currencyfreaks.com/v2.0"

# Supported currencies for conversion
SUPPORTED_CURRENCIES = {
    'USD': {'symbol': '$', 'name': 'US Dollar', 'locale': 'en-US'},
    'EUR': {'symbol': '€', 'name': 'Euro', 'locale': 'en-EU'},
}

# Fallback rates (used when API is unavailable)
FALLBACK_RATES = {
    'EUR': Decimal('0.85'),
}

# Cache timeout: 1 hour for exchange rates
CACHE_TIMEOUT = 3600


class CurrencyConversionError(Exception):
    """Custom exception for currency conversion errors"""
    pass


class CurrencyService:
    """Service for handling currency conversions"""
    
    @staticmethod
    def get_exchange_rate(from_currency: str, to_currency: str = 'USD') -> Decimal:
        """
        Get exchange rate from one currency to another
        
        Args:
            from_currency: Source currency code (e.g., 'USD')
            to_currency: Target currency code (e.g., 'EUR')
            
        Returns:
            Decimal: Exchange rate
            
        Raises:
            CurrencyConversionError: If conversion fails
        """
        # If same currency, return 1
        if from_currency == to_currency:
            return Decimal('1.0')
        
        # Check cache first
        cache_key = f'exchange_rate_{from_currency}_{to_currency}'
        cached_rate = cache.get(cache_key)
        if cached_rate:
            logger.info(f"Using cached exchange rate: {from_currency} to {to_currency} = {cached_rate}")
            return Decimal(str(cached_rate))
        
        try:
            # Fetch from CurrencyFreaks API
            url = f"{CURRENCYFREAKS_API_BASE_URL}/rates/latest"
            params = {
                'apikey': CURRENCYFREAKS_API_KEY,
                'base': from_currency
            }
            
            logger.info(f"Fetching exchange rate from API: {from_currency} to {to_currency}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                rates = data.get('rates', {})
                
                if to_currency in rates:
                    rate = Decimal(str(rates[to_currency]))
                    # Cache the rate for 1 hour
                    cache.set(cache_key, float(rate), CACHE_TIMEOUT)
                    logger.info(f"Fetched exchange rate: {from_currency} to {to_currency} = {rate}")
                    return rate
                else:
                    raise CurrencyConversionError(f"Currency {to_currency} not found in API response")
            
            elif response.status_code == 402:
                # API quota exceeded, use fallback rates
                logger.warning("CurrencyFreaks API quota exceeded, using fallback rates")
                return CurrencyService._get_fallback_rate(from_currency, to_currency)
            
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return CurrencyService._get_fallback_rate(from_currency, to_currency)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching exchange rate: {e}")
            return CurrencyService._get_fallback_rate(from_currency, to_currency)
        except Exception as e:
            logger.error(f"Unexpected error fetching exchange rate: {e}")
            return CurrencyService._get_fallback_rate(from_currency, to_currency)
    
    @staticmethod
    def _get_fallback_rate(from_currency: str, to_currency: str) -> Decimal:
        """
        Get fallback exchange rate when API is unavailable
        
        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            
        Returns:
            Decimal: Fallback exchange rate
        """
        # Convert everything through USD as base
        if from_currency == 'USD':
            return FALLBACK_RATES.get(to_currency, Decimal('1.0'))
        elif to_currency == 'USD':
            from_rate = FALLBACK_RATES.get(from_currency, Decimal('1.0'))
            return Decimal('1.0') / from_rate
        else:
            # Convert from_currency to USD, then USD to to_currency
            from_to_usd = Decimal('1.0') / FALLBACK_RATES.get(from_currency, Decimal('1.0'))
            usd_to_target = FALLBACK_RATES.get(to_currency, Decimal('1.0'))
            return from_to_usd * usd_to_target
    
    @staticmethod
    def convert_amount(
        amount: Decimal,
        from_currency: str,
        to_currency: str = 'USD'
    ) -> Dict:
        """
        Convert an amount from one currency to another
        
        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code
            
        Returns:
            Dict containing conversion details
            
        Raises:
            CurrencyConversionError: If conversion fails
        """
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        # Validate currencies
        if from_currency not in SUPPORTED_CURRENCIES:
            raise CurrencyConversionError(f"Currency {from_currency} not supported")
        if to_currency not in SUPPORTED_CURRENCIES:
            raise CurrencyConversionError(f"Currency {to_currency} not supported")
        
        # Get exchange rate
        rate = CurrencyService.get_exchange_rate(from_currency, to_currency)
        
        # Convert amount
        converted_amount = amount * rate
        
        # Format amounts
        formatted_original = CurrencyService.format_amount(amount, from_currency)
        formatted_converted = CurrencyService.format_amount(converted_amount, to_currency)
        
        return {
            'original_amount': float(amount),
            'converted_amount': float(converted_amount),
            'from_currency': from_currency,
            'to_currency': to_currency,
            'exchange_rate': float(rate),
            'formatted_original': formatted_original,
            'formatted_converted': formatted_converted,
            'cached_rate_used': cache.get(f'exchange_rate_{from_currency}_{to_currency}') is not None
        }
    
    @staticmethod
    def format_amount(amount: Decimal, currency_code: str) -> str:
        """
        Format amount with currency symbol
        
        Args:
            amount: Amount to format
            currency_code: Currency code
            
        Returns:
            str: Formatted amount with symbol
        """
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        currency_info = SUPPORTED_CURRENCIES.get(currency_code, {'symbol': '$'})
        symbol = currency_info['symbol']
        
        # Format with 2 decimal places
        formatted_amount = f"{amount:.2f}"
        
        # Add thousands separator
        parts = formatted_amount.split('.')
        parts[0] = '{:,}'.format(int(parts[0]))
        formatted_amount = '.'.join(parts)
        
        return f"{symbol}{formatted_amount}"
    
    @staticmethod
    def get_supported_currencies() -> list:
        """
        Get list of supported currencies
        
        Returns:
            list: List of currency dictionaries
        """
        return [
            {
                'code': code,
                'name': info['name'],
                'symbol': info['symbol'],
                'locale': info['locale']
            }
            for code, info in SUPPORTED_CURRENCIES.items()
        ]
    
    @staticmethod
    def validate_currency_code(currency_code: str) -> bool:
        """
        Validate if a currency code is supported
        
        Args:
            currency_code: Currency code to validate
            
        Returns:
            bool: True if supported
        """
        return currency_code in SUPPORTED_CURRENCIES


# Create a singleton instance
currency_service = CurrencyService()

