"""
Service layer for eSIM status checking using the enhanced script logic
"""
import logging
import time
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

# Import the enhanced script functions
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to use optimized version, fall back to original
try:
    from script_optimized import try_fetch_from_all_apis_parallel as try_fetch_from_all_apis
    logger.info("Using optimized parallel API fetching")
except ImportError:
    from script_enhanced import try_fetch_from_all_apis
    logger.info("Using standard API fetching")

from script_enhanced import (
    APIProvider,
    OrderNotFoundError,
    APIError,
    AuthenticationError
)


class ESIMService:
    """Service for fetching eSIM details from multiple providers"""
    
    @staticmethod
    def get_esim_details(iccid: str) -> Dict:
        """
        Fetch eSIM details for given ICCID
        
        Args:
            iccid: The ICCID to search for
            
        Returns:
            Dict containing all eSIM details
            
        Raises:
            OrderNotFoundError: If eSIM not found in any API
            APIError: If API request fails
        """
        start_time = time.time()
        
        try:
            logger.info(f"Fetching eSIM details for ICCID: {iccid}")
            
            # Use the enhanced script's parallel API checking
            result = try_fetch_from_all_apis(iccid)
            
            (provider, order, activation, esimcard_data, usage_data, 
             travelroam_data, travelroam_bundles, travelroam_location) = result
            
            if not provider:
                raise OrderNotFoundError(f"eSIM with ICCID {iccid} not found in any API provider")
            
            # Extract and format data based on provider
            esim_data = ESIMService._extract_esim_data(
                provider, order, activation, esimcard_data, usage_data,
                travelroam_data, travelroam_bundles, travelroam_location
            )
            
            # Add metadata
            esim_data['api_provider'] = provider.value.upper()
            esim_data['response_time_ms'] = int((time.time() - start_time) * 1000)
            esim_data['last_updated'] = timezone.now().isoformat()
            
            logger.info(f"Successfully fetched eSIM details from {provider.value} in {esim_data['response_time_ms']}ms")
            
            return esim_data
            
        except OrderNotFoundError as e:
            logger.warning(f"eSIM not found: {e}")
            raise
        except (APIError, AuthenticationError) as e:
            logger.error(f"API error: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            raise APIError(f"Unexpected error occurred: {str(e)}")
    
    @staticmethod
    def _extract_esim_data(provider, order, activation, esimcard_data, usage_data,
                          travelroam_data, travelroam_bundles, travelroam_location) -> Dict:
        """
        Extract and MERGE eSIM data from ALL available APIs
        This mirrors the logic in script_enhanced.py's display_esim_summary()
        """
        import re
        from datetime import datetime
        
        # Initialize merged data structure
        merged = {
            'order_sim_id': 'N/A',
            'iccid': 'N/A',
            'plan_name': 'N/A',
            'status': 'N/A',
            'purchase_date': 'N/A',
            'validity': 'N/A',
            'data_capacity': 'N/A',
            'data_consumed': 'N/A',
            'data_remaining': 'N/A',
            'activation_code': 'N/A',
            'apn': 'N/A',
        }
        
        # ==== PHASE 1: Extract from AirHub if available ====
        if order:
            merged['order_sim_id'] = order.get('orderId', merged['order_sim_id'])
            merged['iccid'] = order.get('simID') or order.get('iccid') or order.get('ICCID') or merged['iccid']
            merged['plan_name'] = order.get('planName', merged['plan_name'])
            merged['status'] = 'Active' if order.get('isActive') else 'Inactive'
            merged['purchase_date'] = order.get('purchaseDate', merged['purchase_date'])
            merged['validity'] = f"{order.get('vaildity', 'N/A')}" if order.get('vaildity') else merged['validity']
            
            capacity = order.get('capacity')
            if capacity and capacity != 'N/A':
                capacity_unit = order.get('capacityUnit', 'GB')
                merged['data_capacity'] = f"{capacity} {capacity_unit}"
            
            if order.get('dataConsumed'):
                merged['data_consumed'] = order.get('dataConsumed')
            if order.get('dataRemaining'):
                merged['data_remaining'] = order.get('dataRemaining')
        
        if activation:
            if activation.get('activationCode') and merged['activation_code'] == 'N/A':
                merged['activation_code'] = activation.get('activationCode')
            if activation.get('apn') and merged['apn'] == 'N/A':
                merged['apn'] = activation.get('apn')
        
        # ==== PHASE 2: Merge eSIMCard data (can override) ====
        if esimcard_data:
            # NEW OPTIMIZED FORMAT: Direct ICCID lookup returns complete data
            sim_data = esimcard_data.get('esim', {})  # Changed from 'sim' to 'esim'
            in_use_packages = esimcard_data.get('packages', [])  # Changed from 'assigned_packages' to 'packages'
            overall_usage = esimcard_data.get('usage', {})
            
            if merged['order_sim_id'] == 'N/A':
                merged['order_sim_id'] = str(sim_data.get('id', merged['order_sim_id']))
            
            if merged['iccid'] == 'N/A':
                merged['iccid'] = sim_data.get('iccid', merged['iccid'])
            
            if sim_data.get('last_bundle'):
                merged['plan_name'] = sim_data.get('last_bundle')
            
            if sim_data.get('status'):
                esim_status = sim_data.get('status')
                if merged['status'] == 'N/A' or merged['status'] != esim_status:
                    merged['status'] = esim_status
            
            if sim_data.get('created_at'):
                merged['purchase_date'] = sim_data.get('created_at')
            
            activation_code_esim = (
                sim_data.get('qr_code_text') or
                sim_data.get('qr_code') or
                sim_data.get('activation_code') or
                sim_data.get('lpa')
            )
            if activation_code_esim and merged['activation_code'] == 'N/A':
                merged['activation_code'] = activation_code_esim
            
            if sim_data.get('apn') and merged['apn'] == 'N/A':
                merged['apn'] = sim_data.get('apn')
            
            # Use in_use_packages (active packages) instead of assigned_packages
            if in_use_packages:
                package = in_use_packages[0]
                
                if package.get('initial_data_quantity'):
                    capacity = package.get('initial_data_quantity')
                    capacity_unit = package.get('initial_data_unit', 'GB')
                    merged['data_capacity'] = f"{capacity} {capacity_unit}"
                
                if merged['plan_name'] and 'Days' in merged['plan_name']:
                    match = re.search(r'(\d+)\s*Days?', merged['plan_name'], re.IGNORECASE)
                    if match:
                        merged['validity'] = f"{match.group(1)} days"
                
                initial_data = package.get('initial_data_quantity', 0)
                remaining_data = package.get('rem_data_quantity', 0)
                data_unit = package.get('rem_data_unit', 'GB')
                
                if initial_data and remaining_data is not None:
                    try:
                        consumed = float(initial_data) - float(remaining_data)
                        merged['data_consumed'] = f"{consumed:.2f} {data_unit}"
                        merged['data_remaining'] = f"{remaining_data} {data_unit}"
                    except (ValueError, TypeError):
                        pass
            
            # Also use overall_usage if available
            elif overall_usage:
                initial_data = overall_usage.get('initial_data_quantity', 0)
                remaining_data = overall_usage.get('rem_data_quantity', 0)
                data_unit = overall_usage.get('rem_data_unit', 'GB')
                
                if initial_data:
                    merged['data_capacity'] = f"{initial_data} {data_unit}"
                if remaining_data is not None:
                    merged['data_remaining'] = f"{remaining_data} {data_unit}"
                if initial_data and remaining_data is not None:
                    try:
                        consumed = float(initial_data) - float(remaining_data)
                        merged['data_consumed'] = f"{consumed:.2f} {data_unit}"
                    except (ValueError, TypeError):
                        pass
        
        # ==== PHASE 3: Merge TravelRoam data (can override) ====
        if travelroam_data:
            if merged['order_sim_id'] == 'N/A':
                merged['order_sim_id'] = str(travelroam_data.get('matchingId', merged['order_sim_id']))
            
            if merged['iccid'] == 'N/A':
                merged['iccid'] = travelroam_data.get('iccid', merged['iccid'])
            
            if travelroam_data.get('profileStatus'):
                tr_status = travelroam_data.get('profileStatus')
                if merged['status'] == 'N/A':
                    merged['status'] = tr_status
            
            if travelroam_data.get('smdpAddress') and merged['activation_code'] == 'N/A':
                merged['activation_code'] = travelroam_data.get('smdpAddress')
            
            purchase_date_timestamp = travelroam_data.get('firstInstalledDateTime')
            if purchase_date_timestamp and merged['purchase_date'] == 'N/A':
                try:
                    dt = datetime.fromtimestamp(purchase_date_timestamp / 1000)
                    merged['purchase_date'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
        
        if travelroam_bundles and travelroam_bundles.get('bundles'):
            bundles = travelroam_bundles['bundles']
            if bundles:
                first_bundle = bundles[0]
                
                plan_name_tr = first_bundle.get('description') or first_bundle.get('name')
                if plan_name_tr and merged['plan_name'] == 'N/A':
                    merged['plan_name'] = plan_name_tr
                
                assignments = first_bundle.get('assignments', [])
                for assignment in assignments:
                    if assignment.get('callTypeGroup', '').lower() == 'data':
                        initial_bytes = assignment.get('initialQuantity', 0)
                        remaining_bytes = assignment.get('remainingQuantity', 0)
                        
                        if initial_bytes > 0:
                            initial_gb = initial_bytes / (1024 ** 3)
                            remaining_gb = remaining_bytes / (1024 ** 3)
                            consumed_gb = initial_gb - remaining_gb
                            
                            # OVERRIDE if current data is N/A
                            if merged['data_consumed'] == 'N/A' or merged['data_remaining'] == 'N/A':
                                merged['data_capacity'] = f"{initial_gb:.2f} GB"
                                merged['data_consumed'] = f"{consumed_gb:.2f} GB"
                                merged['data_remaining'] = f"{remaining_gb:.2f} GB"
                            
                            start_time = assignment.get('startTime', '')
                            end_time = assignment.get('endTime', '')
                            if start_time and end_time:
                                try:
                                    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                                    
                                    # Calculate validity
                                    if merged['validity'] == 'N/A':
                                        merged['validity'] = f"{(end - start).days} days"
                                    
                                    # Check if bundle has expired
                                    now = datetime.now(end.tzinfo)
                                    if now > end:
                                        merged['status'] = 'Expired'
                                        logger.info(f"Bundle expired on {end_time}, setting status to Expired")
                                except Exception as e:
                                    logger.warning(f"Error parsing bundle dates: {e}")
                                    pass
                        break
        
        if travelroam_location and travelroam_location.get('networkName'):
            network_name = travelroam_location.get('networkName', '')
            network_brand = travelroam_location.get('networkBrandName', '')
            country = travelroam_location.get('country', '')
            
            if network_name or network_brand:
                apn_from_location = f"{network_name or network_brand} ({country})" if country else (network_name or network_brand)
                if merged['apn'] in ['N/A', 'internet', 'wholesale']:
                    merged['apn'] = apn_from_location
        
        return merged
    
    @staticmethod
    def _extract_airhub_data(order: Dict, activation: Dict) -> Dict:
        """Extract data from AirHub API response"""
        iccid = (
            order.get('simID') or 
            order.get('iccid') or 
            order.get('ICCID') or 
            activation.get('iccid') or 
            'N/A'
        )
        
        return {
            'order_sim_id': str(order.get('orderId', 'N/A')),
            'iccid': iccid,
            'plan_name': order.get('planName', 'N/A'),
            'status': 'Active' if order.get('isActive') else 'Inactive',
            'purchase_date': order.get('purchaseDate', 'N/A'),
            'validity': f"{order.get('vaildity', 'N/A')} days",
            'data_capacity': f"{order.get('capacity', 'N/A')} {order.get('capacityUnit', '')}".strip(),
            'data_consumed': order.get('dataConsumed', 'N/A'),
            'data_remaining': order.get('dataRemaining', 'N/A'),
            'activation_code': activation.get('activationCode', 'N/A') if activation else 'N/A',
            'apn': activation.get('apn', 'N/A') if activation else 'N/A',
        }
    
    @staticmethod
    def _extract_esimcard_data(order: Dict, esimcard_data: Dict, usage_data: Dict) -> Dict:
        """Extract data from eSIMCard API response"""
        sim_data = esimcard_data.get('sim', {}) if esimcard_data else {}
        assigned_packages = esimcard_data.get('assigned_packages', []) if esimcard_data else []
        
        plan_name = sim_data.get('last_bundle', 'N/A')
        
        # Get package data
        package = assigned_packages[0] if assigned_packages else None
        
        if package:
            capacity = f"{package.get('initial_data_quantity', 'N/A')} {package.get('initial_data_unit', 'GB')}"
            
            # Extract validity from plan name
            import re
            validity = 'N/A days'
            if plan_name and 'Days' in plan_name:
                match = re.search(r'(\d+)\s*Days?', plan_name, re.IGNORECASE)
                if match:
                    validity = f"{match.group(1)} days"
            
            # Calculate data consumed/remaining
            initial_data = package.get('initial_data_quantity', 0)
            remaining_data = package.get('rem_data_quantity', 0)
            data_unit = package.get('rem_data_unit', 'GB')
            
            if initial_data and remaining_data is not None:
                consumed = float(initial_data) - float(remaining_data)
                data_consumed = f"{consumed:.2f} {data_unit}"
                data_remaining = f"{remaining_data} {data_unit}"
            else:
                data_consumed = 'N/A'
                data_remaining = 'N/A'
        else:
            capacity = 'N/A'
            validity = 'N/A days'
            data_consumed = 'N/A'
            data_remaining = 'N/A'
        
        return {
            'order_sim_id': sim_data.get('id', 'N/A'),
            'iccid': sim_data.get('iccid', 'N/A'),
            'plan_name': plan_name,
            'status': sim_data.get('status', 'Unknown'),
            'purchase_date': sim_data.get('created_at', 'N/A'),
            'validity': validity,
            'data_capacity': capacity,
            'data_consumed': data_consumed,
            'data_remaining': data_remaining,
            'activation_code': (
                sim_data.get('qr_code_text') or
                sim_data.get('qr_code') or
                'N/A'
            ),
            'apn': sim_data.get('apn', 'N/A'),
        }
    
    @staticmethod
    def _extract_travelroam_data(travelroam_data: Dict, travelroam_bundles: Dict, 
                                 travelroam_location: Dict) -> Dict:
        """Extract data from TravelRoam API response"""
        
        order_id = travelroam_data.get('matchingId', 'N/A') if travelroam_data else 'N/A'
        iccid = travelroam_data.get('iccid', 'N/A') if travelroam_data else 'N/A'
        status = travelroam_data.get('profileStatus', 'Unknown') if travelroam_data else 'Unknown'
        
        # Get plan name and data from bundles
        plan_name = 'N/A'
        capacity = 'N/A'
        validity = 'N/A days'
        data_consumed = 'N/A'
        data_remaining = 'N/A'
        
        if travelroam_bundles and travelroam_bundles.get('bundles'):
            bundles = travelroam_bundles['bundles']
            if bundles:
                first_bundle = bundles[0]
                plan_name = first_bundle.get('description') or first_bundle.get('name', 'N/A')
                
                assignments = first_bundle.get('assignments', [])
                if assignments:
                    for assignment in assignments:
                        if assignment.get('callTypeGroup', '').lower() == 'data':
                            initial_bytes = assignment.get('initialQuantity', 0)
                            remaining_bytes = assignment.get('remainingQuantity', 0)
                            
                            if initial_bytes > 0:
                                initial_gb = initial_bytes / (1024 ** 3)
                                remaining_gb = remaining_bytes / (1024 ** 3)
                                consumed_gb = initial_gb - remaining_gb
                                
                                capacity = f"{initial_gb:.2f} GB"
                                data_consumed = f"{consumed_gb:.2f} GB"
                                data_remaining = f"{remaining_gb:.2f} GB"
                            
                            # Calculate validity
                            start_time = assignment.get('startTime', '')
                            end_time = assignment.get('endTime', '')
                            if start_time and end_time:
                                try:
                                    from datetime import datetime
                                    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                                    days = (end - start).days
                                    validity = f"{days} days"
                                except:
                                    pass
                            break
        
        # Format purchase date
        purchase_date = 'N/A'
        purchase_date_timestamp = travelroam_data.get('firstInstalledDateTime') if travelroam_data else None
        if purchase_date_timestamp:
            try:
                dt = datetime.fromtimestamp(purchase_date_timestamp / 1000)
                purchase_date = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                purchase_date = str(purchase_date_timestamp)
        
        # Get APN from location
        apn = 'internet'
        if travelroam_location and travelroam_location.get('networkName'):
            network_name = travelroam_location.get('networkName', '')
            country = travelroam_location.get('country', '')
            if network_name:
                apn = f"{network_name} ({country})" if country else network_name
        
        return {
            'order_sim_id': order_id,
            'iccid': iccid,
            'plan_name': plan_name,
            'status': status,
            'purchase_date': purchase_date,
            'validity': validity,
            'data_capacity': capacity,
            'data_consumed': data_consumed,
            'data_remaining': data_remaining,
            'activation_code': travelroam_data.get('smdpAddress', 'N/A') if travelroam_data else 'N/A',
            'apn': apn,
        }

