"""
Optimized multi-API eSIM fetching with parallel execution
"""
import requests
import logging
from typing import Optional, Dict, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from script_enhanced import (
    airhub_login, airhub_get_orders, find_order_by_iccid, airhub_get_activation_details,
    esimcard_login, esimcard_get_esim_by_iccid,
    travelroam_get_esim_details, travelroam_get_applied_bundles, travelroam_get_location,
    APIProvider, OrderNotFoundError, APIError, AuthenticationError
)

logger = logging.getLogger(__name__)


def check_airhub_provider(iccid: str) -> Tuple[Optional[APIProvider], Optional[Dict], Optional[Dict]]:
    """Check AirHub provider"""
    try:
        logger.info("🔍 Checking AirHub...")
        access_token, partner_code = airhub_login()
        orders = airhub_get_orders(access_token, partner_code, flag=1)
        order = find_order_by_iccid(orders.get('data', []), iccid)
        
        activation = None
        if order:
            order_id = order.get('orderId')
            activation_details = airhub_get_activation_details(access_token, partner_code, [order_id])
            activation = activation_details.get(order_id)
            logger.info("✅ Found in AirHub")
            return (APIProvider.AIRHUB, order, activation)
        
        logger.info("❌ Not found in AirHub")
        return (None, None, None)
    except Exception as e:
        logger.warning(f"AirHub check failed: {e}")
        return (None, None, None)


def check_esimcard_provider(iccid: str) -> Tuple[Optional[APIProvider], Optional[Dict], Optional[Dict], Optional[Dict]]:
    """Check eSIMCard provider with OPTIMIZED DIRECT ICCID LOOKUP (no pagination!)"""
    try:
        logger.info("🔍 Checking eSIMCard...")
        token = esimcard_login()
        
        # 🚀 NEW: Direct ICCID lookup - no pagination needed!
        data = esimcard_get_esim_by_iccid(token, iccid)
        
        if data:
            logger.info("✅ Found in eSIMCard")
            # Extract the different data sections from the response
            esim_info = data.get('sim', {})
            in_use_packages = data.get('in_use_packages', [])
            coverage = data.get('coverage', [])
            overall_usage = data.get('overall_usage', {})
            
            # Structure similar to old format for compatibility
            result = {
                'esim': esim_info,
                'packages': in_use_packages,
                'coverage': coverage,
                'usage': overall_usage
            }
            
            return (APIProvider.ESIMCARD, result, data, overall_usage)
        
        logger.info("❌ Not found in eSIMCard")
        return (None, None, None, None)
    except Exception as e:
        logger.warning(f"eSIMCard check failed: {e}")
        return (None, None, None, None)


def check_travelroam_provider(iccid: str) -> Tuple[Optional[APIProvider], Optional[Dict], Optional[Dict], Optional[Dict]]:
    """Check TravelRoam provider"""
    try:
        logger.info("🔍 Checking TravelRoam...")
        details = travelroam_get_esim_details(iccid)
        bundles = travelroam_get_applied_bundles(iccid)
        location = travelroam_get_location(iccid)
        
        if details:
            logger.info("✅ Found in TravelRoam")
            return (APIProvider.TRAVELROAM, details, bundles, location)
        logger.info("❌ Not found in TravelRoam")
        return (None, None, None, None)
    except Exception as e:
        logger.warning(f"TravelRoam check failed: {e}")
        return (None, None, None, None)


def try_fetch_from_all_apis_parallel(iccid: str) -> Tuple:
    """
    Check all providers in parallel and return as soon as one finds the ICCID
    Returns tuple compatible with original function
    """
    logger.info(f"🚀 Starting parallel search for ICCID: {iccid}")
    
    results = {
        'airhub': {'found': False, 'order': None, 'activation': None},
        'esimcard': {'found': False, 'esim': None, 'details': None, 'usage': None},
        'travelroam': {'found': False, 'data': None, 'bundles': None, 'location': None}
    }
    
    # Use ThreadPoolExecutor for I/O-bound parallel operations
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all provider checks
        future_airhub = executor.submit(check_airhub_provider, iccid)
        future_esimcard = executor.submit(check_esimcard_provider, iccid)
        future_travelroam = executor.submit(check_travelroam_provider, iccid)
        
        futures = {
            'airhub': future_airhub,
            'esimcard': future_esimcard,
            'travelroam': future_travelroam
        }
        
        # Process results as they complete
        found_provider = None
        for provider_name, future in futures.items():
            try:
                result = future.result(timeout=90)  # 90 second timeout per provider
                
                if provider_name == 'airhub':
                    provider, order, activation = result
                    if provider:
                        results['airhub'] = {'found': True, 'order': order, 'activation': activation}
                        found_provider = provider
                        
                elif provider_name == 'esimcard':
                    provider, esim, details, usage = result
                    if provider:
                        results['esimcard'] = {'found': True, 'esim': esim, 'details': details, 'usage': usage}
                        found_provider = provider
                        
                elif provider_name == 'travelroam':
                    provider, details, bundles, location = result
                    if provider:
                        results['travelroam'] = {'found': True, 'data': details, 'bundles': bundles, 'location': location}
                        found_provider = provider
                
            except Exception as e:
                logger.error(f"Error checking {provider_name}: {e}")
    
    # Return in format compatible with original function
    provider = found_provider
    airhub_order = results['airhub']['order']
    airhub_activation = results['airhub']['activation']
    esimcard_esim = results['esimcard']['esim']
    esimcard_details = results['esimcard']['details']
    esimcard_usage = results['esimcard']['usage']
    travelroam_data = results['travelroam']['data']
    travelroam_bundles = results['travelroam']['bundles']
    travelroam_location = results['travelroam']['location']
    
    if not provider:
        logger.warning(f"❌ ICCID {iccid} not found in any provider")
        raise OrderNotFoundError(f"eSIM with ICCID {iccid} not found in any API provider")
    
    logger.info(f"✅ Found in {provider.value.upper()}")
    
    return (
        provider,
        airhub_order,
        airhub_activation,
        esimcard_esim,
        esimcard_usage,
        travelroam_data,
        travelroam_bundles,
        travelroam_location
    )

