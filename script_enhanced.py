"""
Enhanced eSIM Status Checker
A professional tool for checking eSIM order status using Order ID or ICCID
Supports multiple API providers based on APN/Network provider
"""

import requests
import sys
import logging
import re
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('esim_checker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========================
# CONFIGURATION
# ========================

# AirHub API Configuration
AIRHUB_BASE_URL = "https://api.airhubapp.com"
AIRHUB_USERNAME = "info@roam2world.com"
AIRHUB_PASSWORD = "airhubworld@25"

# eSIMCard API Configuration
ESIMCARD_BASE_URL = "https://portal.esimcard.com/api/developer/reseller"
ESIMCARD_EMAIL = "aydogan@buysim.de"
ESIMCARD_PASSWORD = "aE190500"

# TravelRoam API Configuration
TRAVELROAM_BASE_URL = "https://travelroam.com/api/whitelabel"
TRAVELROAM_API_KEY = "cm6BdGIXp8josCzANeADbwajrH96leGHCwhq2SY7cx6o8yqKSfzMxombvi4x"
TRAVELROAM_CLIENT_SECRET = "6LDCnfC5wGKxcrT6S6iFbKNpBSRPijrZRDxFObXrqJ1vX9gfIsKHUK9Tvmlx"

REQUEST_TIMEOUT = 30  # seconds


class APIProvider(Enum):
    """Enum for API providers"""
    AIRHUB = "airhub"
    ESIMCARD = "esimcard"
    TRAVELROAM = "travelroam"


# ========================
# CUSTOM EXCEPTIONS
# ========================
class ESIMCheckerError(Exception):
    """Base exception for eSIM Checker"""
    pass


class AuthenticationError(ESIMCheckerError):
    """Raised when authentication fails"""
    pass


class APIError(ESIMCheckerError):
    """Raised when API request fails"""
    pass


class OrderNotFoundError(ESIMCheckerError):
    """Raised when order is not found"""
    pass


class InvalidInputError(ESIMCheckerError):
    """Raised when input validation fails"""
    pass


# ========================
# AIRHUB API FUNCTIONS
# ========================
def airhub_login() -> Tuple[str, str]:
    """
    Authenticate with the AirHub API and return access token and partner code
    
    Returns:
        tuple: (access_token, partner_code)
        
    Raises:
        AuthenticationError: If login fails
        APIError: If network or API error occurs
    """
    url = f"{AIRHUB_BASE_URL}/api/Authentication/UserLogin"
    payload = {"userName": AIRHUB_USERNAME, "password": AIRHUB_PASSWORD}
    
    try:
        logger.info("Attempting to login to AirHub API...")
        response = requests.post(
            url, 
            json=payload, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("isSuccess"):
            error_msg = data.get("message", "Unknown authentication error")
            logger.error(f"AirHub authentication failed: {error_msg}")
            raise AuthenticationError(f"AirHub login failed: {error_msg}")
        
        token = data.get("token")
        if not token:
            raise AuthenticationError("No token received from AirHub API")
        
        partner_code = data.get("data", {}).get("partnerCode", "")
        if not partner_code:
            raise AuthenticationError("No partner code received from AirHub API")
        
        logger.info(f"AirHub authentication successful. Partner Code: {partner_code}")
        return token, str(partner_code)
        
    except requests.exceptions.Timeout:
        logger.error("AirHub login request timed out")
        raise APIError("AirHub login request timed out. Please check your internet connection.")
    except requests.exceptions.ConnectionError:
        logger.error("Connection error during AirHub login")
        raise APIError("Cannot connect to AirHub API server.")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error during AirHub login: {e}")
        raise APIError(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error during AirHub login: {e}")
        raise APIError(f"Request failed: {e}")


def airhub_get_orders(token: str, partner_code: str, flag: int = 1) -> Dict[str, Any]:
    """
    Fetch orders from the AirHub API
    
    Args:
        token: Authentication token
        partner_code: Partner code from login
        flag: Search flag (1 = last 300 records, 2 = date range)
        
    Returns:
        Dict containing order details
        
    Raises:
        APIError: If API request fails
    """
    url = f"{AIRHUB_BASE_URL}/api/ESIM/GetOrderDetail"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "partnerCode": partner_code,
        "flag": str(flag),
        "fromDate": "",
        "toDate": ""
    }
    
    try:
        logger.info(f"Fetching orders from AirHub with flag={flag}")
        response = requests.post(
            url, 
            json=payload, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Retrieved {len(data.get('getOrderdetails', []))} orders from AirHub")
        return data
        
    except requests.exceptions.Timeout:
        logger.error("AirHub order fetch request timed out")
        raise APIError("Request timed out while fetching orders from AirHub")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error while fetching AirHub orders: {e}")
        if e.response.status_code == 401:
            raise AuthenticationError("AirHub authentication token expired or invalid")
        raise APIError(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching AirHub orders: {e}")
        raise APIError(f"Failed to fetch orders: {e}")


def airhub_get_activation_details(token: str, partner_code: str, order_ids: List[str]) -> Dict[str, Any]:
    """
    Fetch activation details for specific order IDs from AirHub
    
    Args:
        token: Authentication token
        partner_code: Partner code from login
        order_ids: List of order IDs to fetch
        
    Returns:
        Dict containing activation details
        
    Raises:
        APIError: If API request fails
    """
    url = f"{AIRHUB_BASE_URL}/api/ESIM/GetActivationCode"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "partnerCode": partner_code,
        "orderid": order_ids
    }
    
    try:
        logger.info(f"Fetching activation details from AirHub for orders: {order_ids}")
        response = requests.post(
            url, 
            json=payload, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info("AirHub activation details retrieved successfully")
        return data
        
    except requests.exceptions.Timeout:
        logger.error("AirHub activation details request timed out")
        raise APIError("Request timed out while fetching activation details")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error while fetching AirHub activation: {e}")
        if e.response.status_code == 401:
            raise AuthenticationError("AirHub authentication token expired or invalid")
        raise APIError(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching AirHub activation details: {e}")
        raise APIError(f"Failed to fetch activation details: {e}")


# ========================
# ESIMCARD API FUNCTIONS
# ========================
def esimcard_login() -> str:
    """
    Authenticate with the eSIMCard API and return access token
    
    Returns:
        str: access_token
        
    Raises:
        AuthenticationError: If login fails
        APIError: If network or API error occurs
    """
    url = f"{ESIMCARD_BASE_URL}/login"
    payload = {"email": ESIMCARD_EMAIL, "password": ESIMCARD_PASSWORD}
    
    try:
        logger.info("Attempting to login to eSIMCard API...")
        response = requests.post(
            url, 
            json=payload, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("status"):
            error_msg = data.get("message", "Unknown authentication error")
            logger.error(f"eSIMCard authentication failed: {error_msg}")
            raise AuthenticationError(f"eSIMCard login failed: {error_msg}")
        
        token = data.get("access_token")
        if not token:
            raise AuthenticationError("No token received from eSIMCard API")
        
        user_info = data.get("user", {})
        logger.info(f"eSIMCard authentication successful. User: {user_info.get('name', 'N/A')}, Balance: ${user_info.get('balance', 0)}")
        return token
        
    except requests.exceptions.Timeout:
        logger.error("eSIMCard login request timed out")
        raise APIError("eSIMCard login request timed out.")
    except requests.exceptions.ConnectionError:
        logger.error("Connection error during eSIMCard login")
        raise APIError("Cannot connect to eSIMCard API server.")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error during eSIMCard login: {e}")
        raise APIError(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error during eSIMCard login: {e}")
        raise APIError(f"Request failed: {e}")


def esimcard_get_my_esims(token: str) -> List[Dict[str, Any]]:
    """
    Fetch all purchased eSIMs from eSIMCard API
    
    Args:
        token: Authentication token
        
    Returns:
        List of eSIM dictionaries
        
    Raises:
        APIError: If API request fails
    """
    url = f"{ESIMCARD_BASE_URL}/my-esims"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        logger.info("Fetching eSIMs from eSIMCard API...")
        response = requests.get(
            url, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("status"):
            raise APIError("Failed to fetch eSIMs from eSIMCard API")
        
        esims = data.get("data", [])
        logger.info(f"Retrieved {len(esims)} eSIMs from eSIMCard")
        return esims
        
    except requests.exceptions.Timeout:
        logger.error("eSIMCard fetch request timed out")
        raise APIError("Request timed out while fetching eSIMs")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error while fetching eSIMCard eSIMs: {e}")
        if e.response.status_code == 401:
            raise AuthenticationError("eSIMCard authentication token expired or invalid")
        raise APIError(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching eSIMCard eSIMs: {e}")
        raise APIError(f"Failed to fetch eSIMs: {e}")


def esimcard_get_esim_details(token: str, esim_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific eSIM from eSIMCard API
    
    Args:
        token: Authentication token
        esim_id: eSIM ID (UUID)
        
    Returns:
        Dict containing eSIM details
        
    Raises:
        APIError: If API request fails
    """
    url = f"{ESIMCARD_BASE_URL}/my-esims/{esim_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        logger.info(f"Fetching details for eSIM {esim_id} from eSIMCard API...")
        response = requests.get(
            url, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("status"):
            raise APIError(f"Failed to fetch eSIM details for {esim_id}")
        
        logger.info(f"Retrieved details for eSIM {esim_id}")
        return data.get("data", {})
        
    except requests.exceptions.Timeout:
        logger.error("eSIMCard details fetch timed out")
        raise APIError("Request timed out while fetching eSIM details")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error while fetching eSIMCard details: {e}")
        if e.response.status_code == 401:
            raise AuthenticationError("eSIMCard authentication token expired or invalid")
        raise APIError(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching eSIMCard details: {e}")
        raise APIError(f"Failed to fetch eSIM details: {e}")


def esimcard_get_usage(token: str, esim_id: str) -> Dict[str, Any]:
    """
    Retrieve usage details of a specific eSIM from eSIMCard API
    
    Args:
        token: Authentication token
        esim_id: eSIM ID (UUID)
        
    Returns:
        Dict containing usage information
        
    Raises:
        APIError: If API request fails
    """
    url = f"{ESIMCARD_BASE_URL}/my-sim/{esim_id}/usage"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        logger.info(f"Fetching usage for eSIM {esim_id} from eSIMCard API...")
        response = requests.get(
            url, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("status"):
            logger.warning(f"Usage data not available for eSIM {esim_id}")
            return {}
        
        logger.info(f"Retrieved usage for eSIM {esim_id}")
        return data.get("data", {})
        
    except requests.exceptions.Timeout:
        logger.error("eSIMCard usage fetch timed out")
        raise APIError("Request timed out while fetching usage")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Could not fetch usage from eSIMCard: {e}")
        return {}
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error fetching usage: {e}")
        return {}


def esimcard_get_my_bundles(token: str) -> List[Dict[str, Any]]:
    """
    Get list of purchased bundles from eSIMCard API
    
    Args:
        token: Authentication token
        
    Returns:
        List of bundle dictionaries
        
    Raises:
        APIError: If API request fails
    """
    url = f"{ESIMCARD_BASE_URL}/my-bundles"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        logger.info("Fetching bundles from eSIMCard API...")
        response = requests.get(
            url, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("status"):
            raise APIError("Failed to fetch bundles from eSIMCard API")
        
        bundles = data.get("data", [])
        logger.info(f"Retrieved {len(bundles)} bundles from eSIMCard")
        return bundles
        
    except requests.exceptions.Timeout:
        logger.error("eSIMCard bundles fetch timed out")
        return []
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Could not fetch bundles from eSIMCard: {e}")
        return []
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error fetching bundles: {e}")
        return []


# ========================
# TRAVELROAM API FUNCTIONS
# ========================
def travelroam_get_esim_details(iccid: str) -> Dict[str, Any]:
    """
    Receive eSIM details for an ICCID from TravelRoam API
    
    Args:
        iccid: ICCID to fetch details for
        
    Returns:
        Dict containing eSIM details
        
    Raises:
        APIError: If API request fails
    """
    url = f"{TRAVELROAM_BASE_URL}/esims/details"
    headers = {
        "Accept": "application/json",
        "x-api-key": TRAVELROAM_API_KEY,
        "clientSecret": TRAVELROAM_CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    payload = {"iccid": iccid}
    
    try:
        logger.info(f"Fetching eSIM details from TravelRoam for ICCID: {iccid}")
        response = requests.post(
            url, 
            json=payload, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"TravelRoam eSIM details retrieved for {iccid}")
        return data
        
    except requests.exceptions.Timeout:
        logger.error("TravelRoam details fetch timed out")
        raise APIError("Request timed out while fetching eSIM details from TravelRoam")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error while fetching TravelRoam details: {e}")
        if e.response.status_code == 403:
            raise AuthenticationError("TravelRoam authentication failed")
        raise APIError(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching TravelRoam details: {e}")
        raise APIError(f"Failed to fetch eSIM details: {e}")


def travelroam_get_applied_bundles(iccid: str) -> Dict[str, Any]:
    """
    Provides details about the current Bundles applied to an eSIM from TravelRoam
    
    Args:
        iccid: ICCID to fetch bundles for
        
    Returns:
        Dict containing bundle details with remaining data
        
    Raises:
        APIError: If API request fails
    """
    url = f"{TRAVELROAM_BASE_URL}/esims/applied/bundles"
    headers = {
        "Accept": "application/json",
        "x-api-key": TRAVELROAM_API_KEY,
        "clientSecret": TRAVELROAM_CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    payload = {"iccid": iccid}
    
    try:
        logger.info(f"Fetching applied bundles from TravelRoam for ICCID: {iccid}")
        response = requests.post(
            url, 
            json=payload, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"TravelRoam bundles retrieved for {iccid}")
        return data
        
    except requests.exceptions.Timeout:
        logger.error("TravelRoam bundles fetch timed out")
        raise APIError("Request timed out while fetching bundles from TravelRoam")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error while fetching TravelRoam bundles: {e}")
        if e.response.status_code == 403:
            raise AuthenticationError("TravelRoam authentication failed")
        raise APIError(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching TravelRoam bundles: {e}")
        raise APIError(f"Failed to fetch bundles: {e}")


def travelroam_get_location(iccid: str) -> Dict[str, Any]:
    """
    Returns the last known location and operator for a given eSIM from TravelRoam
    
    Args:
        iccid: ICCID to fetch location for
        
    Returns:
        Dict containing location and network information including APN
        
    Raises:
        APIError: If API request fails
    """
    url = f"{TRAVELROAM_BASE_URL}/esims/location"
    headers = {
        "Accept": "application/json",
        "x-api-key": TRAVELROAM_API_KEY,
        "clientSecret": TRAVELROAM_CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    payload = {"iccid": iccid}
    
    try:
        logger.info(f"Fetching location from TravelRoam for ICCID: {iccid}")
        response = requests.post(
            url, 
            json=payload, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"TravelRoam location retrieved for {iccid}")
        return data
        
    except requests.exceptions.Timeout:
        logger.error("TravelRoam location fetch timed out")
        return {}
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Could not fetch location from TravelRoam: {e}")
        return {}
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error fetching TravelRoam location: {e}")
        return {}


# ========================
# RENEWAL / TOP-UP FUNCTIONS
# ========================

def travelroam_get_catalog(countries: str = None, region: str = None, description: str = None) -> Dict[str, Any]:
    """
    Get list of available bundles from TravelRoam
    
    Args:
        countries: Comma-separated list of country ISO codes (e.g., "TR, US, GB")
        region: Region name (e.g., "Europe", "Asia", "Global")
        description: Wildcard search for description
    
    Returns:
        List of available bundles
        
    Raises:
        APIError: If API request fails
    """
    url = f"{TRAVELROAM_BASE_URL}/catalogue"
    headers = {
        "Accept": "application/json",
        "x-api-key": TRAVELROAM_API_KEY,
        "clientSecret": TRAVELROAM_CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    
    payload = {}
    if countries:
        payload["countries"] = countries
    if region:
        payload["region"] = region
    if description:
        payload["description"] = description
    
    try:
        logger.info(f"Fetching TravelRoam bundle catalog for {countries or region or 'all'}...")
        response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        bundles = data.get('bundles', [])
        logger.info(f"TravelRoam catalog retrieved: {len(bundles)} bundles")
        return bundles
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching TravelRoam catalog: {e}")
        raise APIError(f"Failed to fetch TravelRoam catalog: {e}")


def travelroam_get_bundle_details(bundle_name: str) -> Dict[str, Any]:
    """
    Get details of a specific bundle from TravelRoam
    
    Args:
        bundle_name: Name of the bundle (e.g., "esim_1GB_7D_TR_U")
        
    Returns:
        Dict containing bundle details
        
    Raises:
        APIError: If API request fails
    """
    url = f"{TRAVELROAM_BASE_URL}/bundle"
    headers = {
        "Accept": "application/json",
        "x-api-key": TRAVELROAM_API_KEY,
        "clientSecret": TRAVELROAM_CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    
    payload = {"bundlename": bundle_name}
    
    try:
        logger.info(f"Fetching TravelRoam bundle details for: {bundle_name}")
        response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Bundle details retrieved: {data.get('name', bundle_name)}")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching TravelRoam bundle details: {e}")
        raise APIError(f"Failed to fetch TravelRoam bundle details: {e}")


def travelroam_find_matching_bundle(current_plan: str, country_code: str = None) -> str:
    """
    Find a matching bundle for renewal based on current plan details
    
    Args:
        current_plan: Current plan name (e.g., "eSIM, 1GB, 7 Days, Turkey, V2")
        country_code: Country ISO code (e.g., "TR" for Turkey)
        
    Returns:
        Bundle name (e.g., "esim_1GB_7D_TR_U") or empty string if not found
    """
    try:
        # Extract details from plan name
        import re
        
        # Try to extract data amount (1GB, 2GB, etc.)
        data_match = re.search(r'(\d+)\s*GB', current_plan, re.IGNORECASE)
        data_amount = data_match.group(1) if data_match else None
        
        # Try to extract duration (7 Days, 15 Days, etc.)
        days_match = re.search(r'(\d+)\s*Day', current_plan, re.IGNORECASE)
        days = days_match.group(1) if days_match else None
        
        # Try to extract country
        if not country_code:
            country_match = re.search(r',\s*([A-Za-z\s]+),', current_plan)
            country_name = country_match.group(1).strip() if country_match else None
        else:
            country_name = None
        
        logger.info(f"Searching for bundle: {data_amount}GB, {days}D, Country: {country_code or country_name}")
        
        # Fetch bundles for the country or region
        if country_code:
            bundles = travelroam_get_catalog(countries=country_code)
        else:
            # Try to search by description
            search_term = f"{data_amount}GB" if data_amount else ""
            bundles = travelroam_get_catalog(description=search_term)
        
        # Find matching bundle
        for bundle in bundles:
            bundle_name = bundle.get('name', '')  # This is the bundle code like "esimp_1GB_7D_TR_V2"
            bundle_desc = bundle.get('description', '').lower()  # This is the display name
            
            # Try exact match on description first
            if current_plan.lower() in bundle_desc or bundle_desc in current_plan.lower():
                logger.info(f"Found exact match: {bundle_name} ({bundle_desc})")
                return bundle_name
            
            # Otherwise, try to match data amount and duration
            match_data = data_amount and f"{data_amount}gb" in bundle_name.lower()
            match_days = days and f"{days}d" in bundle_name.lower()
            match_country = country_code and country_code.lower() in bundle_name.lower()
            
            if match_data and match_days and (match_country or not country_code):
                logger.info(f"Found matching bundle: {bundle_name}")
                return bundle_name
        
        logger.warning(f"No matching bundle found for: {current_plan}")
        return ""
        
    except Exception as e:
        logger.error(f"Error finding matching bundle: {e}")
        return ""


def travelroam_get_esim_assignments(order_reference: str) -> Dict[str, Any]:
    """
    Get eSIM assignments for a specific order reference from TravelRoam
    
    Args:
        order_reference: Order reference ID from processorders response
        
    Returns:
        Dict containing eSIM assignment details
        
    Raises:
        APIError: If API request fails
    """
    url = f"{TRAVELROAM_BASE_URL}/getesimassignments"
    headers = {
        "Accept": "application/json",
        "x-api-key": TRAVELROAM_API_KEY,
        "clientSecret": TRAVELROAM_CLIENT_SECRET
    }
    
    params = {
        "orderReference": order_reference
    }
    
    try:
        logger.info(f"Fetching eSIM assignments for order: {order_reference}")
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"eSIM assignments retrieved for order: {order_reference}")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching eSIM assignments: {e}")
        raise APIError(f"Failed to fetch eSIM assignments: {e}")


def travelroam_process_order(bundle_name: str, iccid: str = None) -> Dict[str, Any]:
    """
    Purchase/Top-up a bundle for an eSIM from TravelRoam
    
    Args:
        bundle_name: Name of the bundle to purchase (e.g., 'esim_1GB_7D_IN_U')
        iccid: ICCID of the eSIM to top-up (optional, creates new eSIM if not provided)
        
    Returns:
        Dict containing order details and status
        
    Raises:
        APIError: If API request fails
    """
    url = f"{TRAVELROAM_BASE_URL}/processorders"
    headers = {
        "Accept": "application/json",
        "x-api-key": TRAVELROAM_API_KEY,
        "clientSecret": TRAVELROAM_CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    
    payload = {
        "bundleName": bundle_name,  # Match your working implementation
        "orderType": "COUNTRY"      # Match your working implementation
    }
    
    if iccid:
        payload["iccid"] = iccid
        logger.info(f"Processing TravelRoam top-up order for ICCID: {iccid}, Bundle: {bundle_name}")
    else:
        logger.info(f"Processing TravelRoam new order for Bundle: {bundle_name}")
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"TravelRoam order processed successfully: {data}")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error processing TravelRoam order: {e}")
        raise APIError(f"Failed to process TravelRoam order: {e}")


def airhub_renew_plan(order_id: str, renewal_days: int, user_amount: str) -> Dict[str, Any]:
    """
    Renew an eSIM plan via AirHub API
    
    Args:
        order_id: Order ID to renew
        renewal_days: Number of days to renew for
        user_amount: Amount charged to user
        
    Returns:
        Dict containing renewal result
        
    Raises:
        APIError: If API request fails
    """
    access_token, partner_code = airhub_login()
    
    url = f"{AIRHUB_BASE_URL}/api/Renew/InsertRenew"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "userAmount": user_amount,
        "orderID": order_id,
        "renewalDays": renewal_days
    }
    
    try:
        logger.info(f"Renewing AirHub plan for Order ID: {order_id}, Days: {renewal_days}")
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"AirHub renewal processed successfully: {data}")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error renewing AirHub plan: {e}")
        raise APIError(f"Failed to renew AirHub plan: {e}")


def esimcard_check_topup_availability(imei: str) -> Dict[str, Any]:
    """
    Check if an eSIM can be topped up via eSIMCard API
    
    Args:
        imei: IMEI of the eSIM to check
        
    Returns:
        Dict containing topup availability status
        
    Raises:
        APIError: If API request fails
    """
    token = esimcard_login()
    
    url = f"{ESIMCARD_BASE_URL}/check-topup"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {"imei": imei}
    
    try:
        logger.info(f"Checking eSIMCard topup availability for IMEI: {imei}")
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"eSIMCard topup availability: {data}")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking eSIMCard topup availability: {e}")
        raise APIError(f"Failed to check eSIMCard topup availability: {e}")


def esimcard_purchase_package(imei: str, package_type_id: str) -> Dict[str, Any]:
    """
    Purchase/Top-up a package for an eSIM via eSIMCard API
    
    Args:
        imei: IMEI of the eSIM to top-up
        package_type_id: UUID of the package to purchase
        
    Returns:
        Dict containing purchase details and status
        
    Raises:
        APIError: If API request fails
    """
    token = esimcard_login()
    
    url = f"{ESIMCARD_BASE_URL}/purchase-package"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "imei": imei,
        "package_type_id": package_type_id
    }
    
    try:
        logger.info(f"Purchasing eSIMCard package for IMEI: {imei}, Package: {package_type_id}")
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"eSIMCard package purchased successfully: {data}")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error purchasing eSIMCard package: {e}")
        raise APIError(f"Failed to purchase eSIMCard package: {e}")


# ========================
# HELPER FUNCTIONS
# ========================
def determine_api_provider(apn: str) -> APIProvider:
    """
    Determine which API provider to use based on APN
    
    Args:
        apn: Access Point Name from the eSIM
        
    Returns:
        APIProvider enum value
    """
    if not apn:
        logger.info("No APN provided, defaulting to AirHub")
        return APIProvider.AIRHUB
    
    apn_lower = apn.lower()
    
    # Orange packages use eSIMCard API for better data tracking
    if "orange" in apn_lower:
        logger.info(f"Detected Orange APN: {apn}, using eSIMCard API")
        return APIProvider.ESIMCARD
    
    # You can add more APN-to-provider mappings here
    # elif "vodafone" in apn_lower:
    #     return APIProvider.ESIMCARD
    
    logger.info(f"APN {apn} not matched to specific provider, using AirHub")
    return APIProvider.AIRHUB


def find_order_by_id(orders: List[Dict], order_id: str) -> Optional[Dict]:
    """
    Find an order by Order ID in AirHub orders
    
    Args:
        orders: List of order dictionaries
        order_id: Order ID to search for
        
    Returns:
        Order dict if found, None otherwise
    """
    try:
        for order in orders:
            if str(order.get("orderId", "")) == str(order_id):
                logger.info(f"Found order with ID: {order_id}")
                return order
        
        logger.warning(f"Order ID {order_id} not found")
        return None
        
    except Exception as e:
        logger.error(f"Error searching for order by ID: {e}")
        return None


def find_order_by_iccid(orders: List[Dict], iccid: str) -> Optional[Dict]:
    """
    Find an order by ICCID in AirHub orders
    
    Args:
        orders: List of order dictionaries
        iccid: ICCID to search for
        
    Returns:
        Order dict if found, None otherwise
    """
    try:
        search_iccid = iccid.strip().replace(' ', '').replace('-', '').lower()
        
        if not search_iccid:
            logger.warning("Empty ICCID provided for search")
            return None
        
        for order in orders:
            order_iccid = (
                order.get('simID', '') or 
                order.get('iccid', '') or 
                order.get('ICCID', '')
            )
            
            clean_order_iccid = order_iccid.strip().replace(' ', '').replace('-', '').lower()
            
            if search_iccid == clean_order_iccid or search_iccid in clean_order_iccid:
                logger.info(f"Found order with ICCID: {order_iccid}")
                print(f"   ✓ Matched ICCID: {order_iccid}")
                return order
        
        logger.warning(f"ICCID {iccid} not found")
        return None
        
    except Exception as e:
        logger.error(f"Error searching for order by ICCID: {e}")
        return None


def find_esimcard_by_iccid(esims: List[Dict], iccid: str) -> Optional[Dict]:
    """
    Find an eSIM by ICCID in eSIMCard API results
    
    Args:
        esims: List of eSIM dictionaries from eSIMCard
        iccid: ICCID to search for
        
    Returns:
        eSIM dict if found, None otherwise
    """
    try:
        search_iccid = iccid.strip().replace(' ', '').replace('-', '').lower()
        
        if not search_iccid:
            logger.warning("Empty ICCID provided for search")
            return None
        
        for esim in esims:
            esim_iccid = esim.get('iccid', '') or esim.get('ICCID', '')
            
            clean_esim_iccid = esim_iccid.strip().replace(' ', '').replace('-', '').lower()
            
            if search_iccid == clean_esim_iccid or search_iccid in clean_esim_iccid:
                logger.info(f"Found eSIM with ICCID: {esim_iccid}")
                print(f"   ✓ Matched ICCID: {esim_iccid}")
                return esim
        
        logger.warning(f"ICCID {iccid} not found in eSIMCard")
        return None
        
    except Exception as e:
        logger.error(f"Error searching for eSIM by ICCID: {e}")
        return None


def calculate_data_completeness(data_consumed: str, data_remaining: str, status: str) -> int:
    """
    Calculate a completeness score for the data based on available fields
    
    Args:
        data_consumed: Data consumed value
        data_remaining: Data remaining value
        status: Status of the eSIM
        
    Returns:
        int: Completeness score (higher is better)
    """
    score = 0
    
    # Check if we have actual data consumption info
    # Must not be N/A, empty string, None, or '0'
    if data_consumed and data_consumed != 'N/A' and data_consumed.strip() not in ['', '0', '0.0', '0 GB', '0 MB']:
        score += 50
    
    if data_remaining and data_remaining != 'N/A' and data_remaining.strip() not in ['', '0', '0.0', '0 GB', '0 MB']:
        score += 50
    
    # If we found SOME data (even if empty), give base points for having the record
    if data_consumed is not None or data_remaining is not None:
        score += 30
    
    # Bonus for active status
    if status and status.lower() in ['active', 'enabled', 'installed']:
        score += 20
    
    return score


def try_fetch_from_all_apis(iccid: str) -> Tuple[Optional[APIProvider], Optional[Dict], Optional[Dict], Optional[Dict], Optional[Dict], Optional[Dict], Optional[Dict], Optional[Dict]]:
    """
    Try to fetch eSIM information from all three APIs in parallel
    Returns the API with the most complete data
    
    Args:
        iccid: ICCID to search for
        
    Returns:
        Tuple: (best_provider, order_data, activation_data, esimcard_data, usage_data, travelroam_data, travelroam_bundles, travelroam_location)
    """
    results = {
        'airhub': {'found': False, 'order': None, 'activation': None, 'score': 0},
        'esimcard': {'found': False, 'esim': None, 'details': None, 'usage': None, 'score': 0},
        'travelroam': {'found': False, 'details': None, 'bundles': None, 'location': None, 'score': 0}
    }
    
    # Try AirHub
    print("🔍 Checking AirHub API...")
    try:
        token, partner_code = airhub_login()
        orders_response = airhub_get_orders(token, partner_code)
        orders = orders_response.get("getOrderdetails", [])
        order = find_order_by_iccid(orders, iccid)
        
        if order:
            results['airhub']['found'] = True
            results['airhub']['order'] = order
            print("   ✅ Found in AirHub")
            
            # Try to get activation details
            try:
                order_id = order.get('orderId')
                if order_id:
                    activation_response = airhub_get_activation_details(token, partner_code, [str(order_id)])
                    activation_list = activation_response.get("getOrderdetails", [])
                    results['airhub']['activation'] = activation_list[0] if activation_list else {}
            except:
                pass
            
            # Calculate score
            data_consumed = order.get('dataConsumed', 'N/A')
            data_remaining = order.get('dataRemaining', 'N/A')
            status = 'Active' if order.get('isActive') else 'Inactive'
            results['airhub']['score'] = calculate_data_completeness(data_consumed, data_remaining, status)
        else:
            print("   ❌ Not found in AirHub")
    except Exception as e:
        logger.warning(f"AirHub API failed: {e}")
        print(f"   ⚠️ AirHub API error")
    
    # Try eSIMCard
    print("🔍 Checking eSIMCard API...")
    try:
        token = esimcard_login()
        esims = esimcard_get_my_esims(token)
        esim = find_esimcard_by_iccid(esims, iccid)
        
        if esim:
            results['esimcard']['found'] = True
            results['esimcard']['esim'] = esim
            print("   ✅ Found in eSIMCard")
            
            # Get details, usage, and bundles
            try:
                esim_id = esim.get('id')
                if esim_id:
                    results['esimcard']['details'] = esimcard_get_esim_details(token, esim_id)
                    results['esimcard']['usage'] = esimcard_get_usage(token, esim_id)
                    
                    # Also try to get bundles to find package info
                    bundles = esimcard_get_my_bundles(token)
                    # Match bundle to this ICCID
                    for bundle in bundles:
                        bundle_iccid = bundle.get('iccid', '')
                        if bundle_iccid and iccid.replace(' ', '').replace('-', '').lower() in bundle_iccid.replace(' ', '').replace('-', '').lower():
                            # Found matching bundle, add to details
                            if results['esimcard']['details']:
                                if 'in_use_packages' not in results['esimcard']['details'] or not results['esimcard']['details']['in_use_packages']:
                                    results['esimcard']['details']['in_use_packages'] = [bundle]
                            logger.info(f"Found matching bundle: {bundle.get('package_name', 'Unknown')}")
                            break
            except Exception as e:
                logger.warning(f"Error fetching eSIMCard additional data: {e}")
            
            # Calculate score
            usage = results['esimcard']['usage'] or {}
            initial_data = usage.get('initial_data_quantity', 'N/A')
            remaining_data = usage.get('rem_data_quantity', 'N/A')
            status = esim.get('status', 'Unknown')
            
            data_consumed = 'N/A'
            data_remaining = 'N/A'
            if initial_data != 'N/A' and remaining_data != 'N/A':
                try:
                    consumed = float(initial_data) - float(remaining_data)
                    data_consumed = str(consumed)
                    data_remaining = str(remaining_data)
                except:
                    pass
            
            results['esimcard']['score'] = calculate_data_completeness(data_consumed, data_remaining, status)
        else:
            print("   ❌ Not found in eSIMCard")
    except Exception as e:
        logger.warning(f"eSIMCard API failed: {e}")
        print(f"   ⚠️ eSIMCard API error")
    
    # Try TravelRoam
    print("🔍 Checking TravelRoam API...")
    try:
        details = travelroam_get_esim_details(iccid)
        
        if details and details.get('iccid'):
            results['travelroam']['found'] = True
            results['travelroam']['details'] = details
            print("   ✅ Found in TravelRoam")
            
            # Try to get bundles and location
            try:
                bundles = travelroam_get_applied_bundles(iccid)
                results['travelroam']['bundles'] = bundles
            except:
                pass
            
            try:
                location = travelroam_get_location(iccid)
                results['travelroam']['location'] = location
            except:
                pass
            
            # Calculate score from bundles
            data_consumed = 'N/A'
            data_remaining = 'N/A'
            bundles = results['travelroam']['bundles']
            if bundles and bundles.get('bundles'):
                bundle_list = bundles['bundles']
                if bundle_list and bundle_list[0].get('assignments'):
                    for assignment in bundle_list[0]['assignments']:
                        # Case-insensitive check
                        if assignment.get('callTypeGroup', '').lower() == 'data':
                            initial = assignment.get('initialQuantity', 0)
                            remaining = assignment.get('remainingQuantity', 0)
                            if initial > 0:
                                # Convert bytes to GB for scoring
                                consumed_gb = (initial - remaining) / (1024 ** 3)
                                remaining_gb = remaining / (1024 ** 3)
                                data_consumed = f"{consumed_gb:.2f}"
                                data_remaining = f"{remaining_gb:.2f}"
                            break
            
            status = details.get('profileStatus', 'Unknown')
            results['travelroam']['score'] = calculate_data_completeness(data_consumed, data_remaining, status)
        else:
            print("   ❌ Not found in TravelRoam")
    except Exception as e:
        logger.warning(f"TravelRoam API failed: {e}")
        print(f"   ⚠️ TravelRoam API error")
    
    # Determine which API has the best data
    print("\n📊 Comparing results...")
    best_provider = None
    best_score = 0
    found_any = False
    
    for provider, data in results.items():
        if data['found']:
            found_any = True
            logger.info(f"{provider.upper()}: Found={data['found']}, Score={data['score']}")
            print(f"   {provider.upper()}: Score = {data['score']}")
            if data['score'] > best_score:
                best_score = data['score']
                best_provider = provider
    
    if not found_any:
        logger.warning("eSIM not found in any API")
        return None, None, None, None, None, None, None, None
    
    print(f"\n✨ Using {best_provider.upper()} as primary (score: {best_score})")
    print(f"🔄 Merging data from all available APIs for complete information...\n")
    logger.info(f"Selected {best_provider} as primary provider with score {best_score}")
    
    # Return ALL data from all providers - let display function merge them
    return (
        APIProvider[best_provider.upper()],
        results['airhub']['order'] if results['airhub']['found'] else None,
        results['airhub']['activation'] if results['airhub']['found'] else None,
        results['esimcard']['details'] if results['esimcard']['found'] else None,
        results['esimcard']['usage'] if results['esimcard']['found'] else None,
        results['travelroam']['details'] if results['travelroam']['found'] else None,
        results['travelroam']['bundles'] if results['travelroam']['found'] else None,
        results['travelroam']['location'] if results['travelroam']['found'] else None
    )


# ========================
# DISPLAY FUNCTIONS
# ========================
def display_esim_summary(order: Dict, activation: Dict, provider: APIProvider, 
                        esimcard_data: Optional[Dict] = None, 
                        usage_data: Optional[Dict] = None,
                        travelroam_data: Optional[Dict] = None,
                        travelroam_bundles: Optional[Dict] = None,
                        travelroam_location: Optional[Dict] = None) -> None:
    """
    Display eSIM information in a formatted summary - MERGES data from all available APIs
    
    Args:
        order: Order information dictionary (from AirHub or transformed)
        activation: Activation details dictionary
        provider: Which API provider was used as primary
        esimcard_data: Optional eSIMCard detailed data
        usage_data: Optional usage data from eSIMCard
        travelroam_data: Optional TravelRoam eSIM details
        travelroam_bundles: Optional TravelRoam bundle information
        travelroam_location: Optional TravelRoam location data
    """
    try:
        print("\n" + "=" * 70)
        print("📱 eSIM SUMMARY (Multi-API Merged Data)")
        print("=" * 70)
        
        # Initialize merged data
        merged = {
            'order_id': 'N/A',
            'iccid': 'N/A',
            'plan_name': 'N/A',
            'status': 'N/A',
            'purchase_date': 'N/A',
            'validity': 'N/A',
            'capacity': 'N/A',
            'capacity_unit': '',
            'data_consumed': 'N/A',
            'data_remaining': 'N/A',
            'activation_code': 'N/A',
            'apn': 'N/A',
            'data_sources': []
        }
        
        # ==== PHASE 1: Extract from AirHub ====
        if order:
            merged['data_sources'].append('AirHub')
            merged['order_id'] = order.get('orderId', merged['order_id'])
            merged['iccid'] = order.get('simID') or order.get('iccid') or order.get('ICCID') or merged['iccid']
            merged['plan_name'] = order.get('planName', merged['plan_name'])
            merged['status'] = 'Active' if order.get('isActive') else 'Inactive'
            merged['purchase_date'] = order.get('purchaseDate', merged['purchase_date'])
            merged['validity'] = order.get('vaildity', merged['validity'])
            
            capacity = order.get('capacity')
            if capacity and capacity != 'N/A':
                merged['capacity'] = capacity
                merged['capacity_unit'] = order.get('capacityUnit', 'GB')
            
            # AirHub data consumption (often empty for inactive)
            if order.get('dataConsumed'):
                merged['data_consumed'] = order.get('dataConsumed')
            if order.get('dataRemaining'):
                merged['data_remaining'] = order.get('dataRemaining')
        
        if activation:
            merged['activation_code'] = activation.get('activationCode', merged['activation_code'])
            merged['apn'] = activation.get('apn', merged['apn'])
        
        # ==== PHASE 2: Extract from eSIMCard (can override if better) ====
        if esimcard_data:
            merged['data_sources'].append('eSIMCard')
            sim_data = esimcard_data.get('sim', {})
            assigned_packages = esimcard_data.get('assigned_packages', [])
            
            # Override order_id if not set
            if merged['order_id'] == 'N/A':
                merged['order_id'] = sim_data.get('id', merged['order_id'])
            
            # Override ICCID if not set
            if merged['iccid'] == 'N/A':
                merged['iccid'] = sim_data.get('iccid', merged['iccid'])
            
            # Use eSIMCard plan name if available
            if sim_data.get('last_bundle'):
                merged['plan_name'] = sim_data.get('last_bundle')
            
            # eSIMCard status
            if sim_data.get('status'):
                # Keep eSIMCard status if different
                esim_status = sim_data.get('status')
                if merged['status'] == 'N/A' or merged['status'] != esim_status:
                    merged['status'] = esim_status
            
            # eSIMCard purchase date
            if sim_data.get('created_at'):
                merged['purchase_date'] = sim_data.get('created_at')
            
            # eSIMCard activation code (might be better than AirHub)
            activation_code_esim = (
                sim_data.get('qr_code_text') or
                sim_data.get('qr_code') or
                sim_data.get('activation_code') or
                sim_data.get('lpa')
            )
            if activation_code_esim and merged['activation_code'] == 'N/A':
                merged['activation_code'] = activation_code_esim
            
            # eSIMCard APN
            if sim_data.get('apn') and merged['apn'] == 'N/A':
                merged['apn'] = sim_data.get('apn')
            
            # eSIMCard package data (PRIORITY - often has usage data)
            if assigned_packages:
                package = assigned_packages[0]
                
                # Data capacity from eSIMCard
                if package.get('initial_data_quantity'):
                    merged['capacity'] = package.get('initial_data_quantity')
                    merged['capacity_unit'] = package.get('initial_data_unit', 'GB')
                
                # Extract validity from plan name
                if merged['plan_name'] and 'Days' in merged['plan_name']:
                    match = re.search(r'(\d+)\s*Days?', merged['plan_name'], re.IGNORECASE)
                    if match:
                        merged['validity'] = match.group(1)
                
                # Data consumption from eSIMCard (OVERRIDE if available!)
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
        
        # ==== PHASE 3: Extract from TravelRoam (can override if better) ====
        if travelroam_data:
            merged['data_sources'].append('TravelRoam')
            
            # Override order_id if not set
            if merged['order_id'] == 'N/A':
                merged['order_id'] = travelroam_data.get('matchingId', merged['order_id'])
            
            # Override ICCID if not set
            if merged['iccid'] == 'N/A':
                merged['iccid'] = travelroam_data.get('iccid', merged['iccid'])
            
            # TravelRoam status
            if travelroam_data.get('profileStatus'):
                tr_status = travelroam_data.get('profileStatus')
                if merged['status'] == 'N/A':
                    merged['status'] = tr_status
            
            # TravelRoam activation code
            if travelroam_data.get('smdpAddress') and merged['activation_code'] == 'N/A':
                merged['activation_code'] = travelroam_data.get('smdpAddress')
            
            # TravelRoam purchase date
            purchase_date_timestamp = travelroam_data.get('firstInstalledDateTime')
            if purchase_date_timestamp and merged['purchase_date'] == 'N/A':
                try:
                    from datetime import datetime
                    dt = datetime.fromtimestamp(purchase_date_timestamp / 1000)
                    merged['purchase_date'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
        
        # TravelRoam bundles (PRIORITY - often has complete usage data!)
        if travelroam_bundles and travelroam_bundles.get('bundles'):
            bundles = travelroam_bundles['bundles']
            if bundles:
                first_bundle = bundles[0]
                
                # Use TravelRoam plan name if available
                plan_name_tr = first_bundle.get('description') or first_bundle.get('name')
                if plan_name_tr and merged['plan_name'] == 'N/A':
                    merged['plan_name'] = plan_name_tr
                
                # Get data assignments
                assignments = first_bundle.get('assignments', [])
                for assignment in assignments:
                    if assignment.get('callTypeGroup', '').lower() == 'data':
                        initial_bytes = assignment.get('initialQuantity', 0)
                        remaining_bytes = assignment.get('remainingQuantity', 0)
                        
                        if initial_bytes > 0:
                            # Convert bytes to GB
                            initial_gb = initial_bytes / (1024 ** 3)
                            remaining_gb = remaining_bytes / (1024 ** 3)
                            consumed_gb = initial_gb - remaining_gb
                            
                            # OVERRIDE if current data is N/A (TravelRoam has better data!)
                            if merged['data_consumed'] == 'N/A' or merged['data_remaining'] == 'N/A':
                                merged['capacity'] = f"{initial_gb:.2f}"
                                merged['capacity_unit'] = 'GB'
                                merged['data_consumed'] = f"{consumed_gb:.2f} GB"
                                merged['data_remaining'] = f"{remaining_gb:.2f} GB"
                            
                            # Calculate validity and check if bundle is expired
                            start_time = assignment.get('startTime', '')
                            end_time = assignment.get('endTime', '')
                            if start_time and end_time:
                                try:
                                    from datetime import datetime
                                    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                                    
                                    # Calculate validity days
                                    if merged['validity'] == 'N/A':
                                        merged['validity'] = str((end - start).days)
                                    
                                    # Check if bundle has expired
                                    now = datetime.now(end.tzinfo)
                                    if now > end:
                                        merged['status'] = 'Expired'
                                        logger.info(f"Bundle expired on {end_time}, setting status to Expired")
                                except Exception as e:
                                    logger.warning(f"Error parsing bundle dates: {e}")
                                    pass
                        break
        
        # TravelRoam location (for accurate APN)
        if travelroam_location and travelroam_location.get('networkName'):
            network_name = travelroam_location.get('networkName', '')
            network_brand = travelroam_location.get('networkBrandName', '')
            country = travelroam_location.get('country', '')
            
            if network_name or network_brand:
                apn_from_location = f"{network_name or network_brand} ({country})" if country else (network_name or network_brand)
                # Override APN with location data if current APN is generic
                if merged['apn'] in ['N/A', 'internet', 'wholesale']:
                    merged['apn'] = apn_from_location
        
        # ==== DISPLAY MERGED DATA ====
        data_sources_str = " + ".join(merged['data_sources'])
        print(f"Data Sources:    {data_sources_str}")
        print(f"Primary API:     {provider.value.upper()}")
        print(f"Order/SIM ID:    {merged['order_id']}")
        print(f"ICCID:           {merged['iccid']}")
        print(f"Plan:            {merged['plan_name']}")
        print(f"Status:          {merged['status']}")
        print(f"Purchase Date:   {merged['purchase_date']}")
        print(f"Validity:        {merged['validity']} days" if merged['validity'] != 'N/A' else f"Validity:        {merged['validity']}")
        print(f"Data Capacity:   {merged['capacity']} {merged['capacity_unit']}")
        print(f"Data Consumed:   {merged['data_consumed']}")
        print(f"Data Remaining:  {merged['data_remaining']}")
        
        # Add note if data is complete or incomplete
        if merged['data_consumed'] != 'N/A' and merged['data_remaining'] != 'N/A':
            print(f"                 ✅ Complete usage data available!")
        else:
            print(f"                 ⚠️ Usage data unavailable or incomplete")
        
        print(f"Activation Code: {merged['activation_code']}")
        print(f"APN:             {merged['apn']}")
        print("=" * 70)
        
        logger.info(f"Displayed merged summary from {data_sources_str}")
        
    except Exception as e:
        logger.error(f"Error displaying summary: {e}")
        print(f"\n⚠️ Error formatting display: {e}")



# ========================
# MAIN PROCESS FUNCTIONS
# ========================
def process_search_airhub(search_value: str, search_type: str) -> None:
    """
    Process search using AirHub API
    
    Args:
        search_value: Order ID or ICCID to search
        search_type: Type of search ('order_id' or 'iccid')
    """
    token = None
    partner_code = None
    
    try:
        # Step 1: Authentication
        print("🔐 Logging in to AirHub API...")
        token, partner_code = airhub_login()
        print("✅ Logged in to AirHub\n")
        
        # Step 2: Fetch orders
        search_label = "Order ID" if search_type == 'order_id' else "ICCID"
        print(f"📊 Searching for order by {search_label}...")
        
        orders_response = airhub_get_orders(token, partner_code)
        orders = orders_response.get("getOrderdetails", [])
        
        if not orders:
            raise OrderNotFoundError("No orders found in your AirHub account")
        
        # Step 3: Find specific order
        order = None
        if search_type == 'order_id':
            order = find_order_by_id(orders, search_value)
        else:
            order = find_order_by_iccid(orders, search_value)
        
        if not order:
            raise OrderNotFoundError(
                f"No order found for {search_label}: '{search_value}'\n"
                f"Note: Search is limited to last 300 orders in AirHub."
            )
        
        print("✅ Order found in AirHub\n")
        
        # Step 4: Get activation details
        order_id = order.get('orderId')
        if not order_id:
            raise APIError("Order ID is missing from order data")
        
        print(f"🔍 Using Order ID: {order_id}")
        
        print("📡 Fetching activation details...")
        activation = {}
        try:
            activation_response = airhub_get_activation_details(token, partner_code, [str(order_id)])
            activation_list = activation_response.get("getOrderdetails", [])
            activation = activation_list[0] if activation_list else {}
            print("✅ Activation details retrieved\n")
        except APIError as e:
            logger.warning(f"Could not fetch activation details: {e}")
            print(f"⚠️ Could not fetch activation details\n")
        
        # Step 5: Check APN and determine if we need eSIMCard API
        apn = activation.get('apn', '')
        api_provider = determine_api_provider(apn)
        
        if api_provider == APIProvider.ESIMCARD:
            print(f"🔄 Detected {apn} - switching to eSIMCard API for better data tracking...")
            try:
                process_search_esimcard_by_iccid(order.get('simID', ''), order, activation)
                return
            except Exception as e:
                logger.warning(f"Failed to get data from eSIMCard API: {e}")
                print(f"⚠️ Could not fetch from eSIMCard API, showing AirHub data\n")
        
        # Step 6: Display summary with AirHub data
        display_esim_summary(order, activation, APIProvider.AIRHUB)
        
    except AuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        print(f"\n❌ Authentication Error: {e}")
        print("Please check your credentials and try again.")
        sys.exit(1)
        
    except OrderNotFoundError as e:
        logger.warning(f"Order not found: {e}")
        print(f"\n❌ {e}")
        sys.exit(1)
        
    except APIError as e:
        logger.error(f"API error: {e}")
        print(f"\n❌ API Error: {e}")
        print("Please try again later or contact support.")
        sys.exit(1)
        
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"\n❌ Unexpected Error: {e}")
        print("Please contact support if the problem persists.")
        sys.exit(1)


def process_search_esimcard_by_iccid(iccid: str, airhub_order: Optional[Dict] = None, 
                                     airhub_activation: Optional[Dict] = None) -> None:
    """
    Process search using eSIMCard API by ICCID
    
    Args:
        iccid: ICCID to search for
        airhub_order: Optional order data from AirHub
        airhub_activation: Optional activation data from AirHub
    """
    try:
        # Step 1: Authentication
        if not airhub_order:
            print("🔐 Logging in to eSIMCard API...")
        token = esimcard_login()
        if not airhub_order:
            print("✅ Logged in to eSIMCard\n")
        
        # Step 2: Fetch eSIMs
        print("📊 Searching for eSIM in eSIMCard database...")
        esims = esimcard_get_my_esims(token)
        
        if not esims:
            raise OrderNotFoundError("No eSIMs found in your eSIMCard account")
        
        # Step 3: Find specific eSIM by ICCID
        esim = find_esimcard_by_iccid(esims, iccid)
        
        if not esim:
            raise OrderNotFoundError(
                f"No eSIM found for ICCID: '{iccid}' in eSIMCard"
            )
        
        print("✅ eSIM found in eSIMCard\n")
        
        # Step 4: Get detailed eSIM information
        esim_id = esim.get('id')
        if not esim_id:
            raise APIError("eSIM ID is missing from eSIM data")
        
        print(f"🔍 Fetching detailed information...")
        esim_details = esimcard_get_esim_details(token, esim_id)
        
        # Step 5: Get usage data
        print(f"📊 Fetching usage data...")
        usage_data = esimcard_get_usage(token, esim_id)
        print("✅ Data retrieved\n")
        
        # Step 6: Display summary
        display_esim_summary(
            esim, 
            airhub_activation or {}, 
            APIProvider.ESIMCARD,
            esimcard_data=esim_details,
            usage_data=usage_data
        )
        
    except AuthenticationError as e:
        logger.error(f"eSIMCard authentication error: {e}")
        print(f"\n❌ eSIMCard Authentication Error: {e}")
        sys.exit(1)
        
    except OrderNotFoundError as e:
        logger.warning(f"eSIM not found: {e}")
        print(f"\n❌ {e}")
        sys.exit(1)
        
    except APIError as e:
        logger.error(f"eSIMCard API error: {e}")
        print(f"\n❌ API Error: {e}")
        sys.exit(1)


def process_search(search_value: str, search_type: str) -> None:
    """
    Main process to search and display eSIM information
    Routes to appropriate API based on findings
    
    Args:
        search_value: Order ID or ICCID to search
        search_type: Type of search ('order_id' or 'iccid')
    """
    # For ICCID searches, check all APIs and use the one with best data
    if search_type == 'iccid':
        try:
            print("🌐 Checking all API providers for complete data...\n")
            provider, order, activation, esimcard_data, usage_data, travelroam_data, travelroam_bundles, travelroam_location = try_fetch_from_all_apis(search_value)
            
            if not provider:
                print("\n❌ eSIM not found in any API provider")
                logger.error(f"ICCID {search_value} not found in any API")
                sys.exit(1)
            
            # Display summary with data from best provider
            display_esim_summary(
                order,
                activation or {},
                provider,
                esimcard_data=esimcard_data,
                usage_data=usage_data,
                travelroam_data=travelroam_data,
                travelroam_bundles=travelroam_bundles,
                travelroam_location=travelroam_location
            )
            
        except Exception as e:
            logger.exception(f"Error during multi-API search: {e}")
            print(f"\n❌ Error during search: {e}")
            sys.exit(1)
    else:
        # For Order ID searches, use AirHub only
        process_search_airhub(search_value, search_type)


def validate_input(value: str, input_type: str) -> str:
    """
    Validate user input
    
    Args:
        value: Input value to validate
        input_type: Type of input ('order_id' or 'iccid')
        
    Returns:
        Cleaned and validated input value
        
    Raises:
        InvalidInputError: If input is invalid
    """
    cleaned_value = value.strip()
    
    if not cleaned_value:
        raise InvalidInputError(f"{input_type.upper()} cannot be empty")
    
    if input_type == 'order_id':
        if not cleaned_value.isdigit():
            raise InvalidInputError("Order ID must contain only numbers")
    
    elif input_type == 'iccid':
        cleaned_for_check = cleaned_value.replace(' ', '').replace('-', '')
        if not cleaned_for_check.isalnum():
            raise InvalidInputError("ICCID must contain only letters and numbers")
        
        if len(cleaned_for_check) < 10:
            raise InvalidInputError("ICCID seems too short (minimum 10 characters)")
    
    return cleaned_value


# ========================
# MAIN ENTRY POINT
# ========================
def list_all_orders() -> None:
    """List all available orders from both APIs"""
    print("\n" + "=" * 70)
    print("Choose API to list orders from:")
    print("1. AirHub (last 300 orders)")
    print("2. eSIMCard (all purchased eSIMs)")
    print("3. Both APIs")
    
    choice = input("\nEnter your choice (1, 2, or 3): ").strip()
    
    if choice in ["1", "3"]:
        try:
            print("\n" + "=" * 70)
            print("📊 AIRHUB ORDERS")
            print("=" * 70)
            print("🔐 Logging in to AirHub...")
            token, partner_code = airhub_login()
            print("✅ Logged in\n")
            
            print("📊 Fetching orders from AirHub...")
            orders_response = airhub_get_orders(token, partner_code)
            orders = orders_response.get("getOrderdetails", [])
            
            if not orders:
                print("❌ No orders found in AirHub account")
            else:
                print(f"\n✅ Found {len(orders)} order(s)\n")
                print("=" * 100)
                print(f"{'#':<4} {'Order ID':<12} {'ICCID':<30} {'Plan':<30} {'Status':<10}")
                print("=" * 100)
                
                for idx, order in enumerate(orders, 1):
                    order_id = order.get('orderId', 'N/A')
                    iccid_raw = order.get('simID', '') or order.get('iccid', '') or 'N/A'
                    iccid = iccid_raw.replace('SIM ID: ', '').strip() if iccid_raw != 'N/A' else 'N/A'
                    plan_name = order.get('planName', 'N/A')
                    status = 'Active' if order.get('isActive') else 'Inactive'
                    
                    if len(iccid) > 30:
                        iccid = iccid[:27] + "..."
                    if len(plan_name) > 30:
                        plan_name = plan_name[:27] + "..."
                    
                    print(f"{idx:<4} {order_id:<12} {iccid:<30} {plan_name:<30} {status:<10}")
                
                print("=" * 100)
                print(f"\nTotal AirHub orders: {len(orders)}\n")
                
        except Exception as e:
            logger.error(f"Error listing AirHub orders: {e}")
            print(f"\n❌ Error listing AirHub orders: {e}")
    
    if choice in ["2", "3"]:
        try:
            print("\n" + "=" * 70)
            print("📊 ESIMCARD eSIMs")
            print("=" * 70)
            print("🔐 Logging in to eSIMCard...")
            token = esimcard_login()
            print("✅ Logged in\n")
            
            print("📊 Fetching eSIMs from eSIMCard...")
            esims = esimcard_get_my_esims(token)
            
            if not esims:
                print("❌ No eSIMs found in eSIMCard account")
            else:
                print(f"\n✅ Found {len(esims)} eSIM(s)\n")
                print("=" * 100)
                print(f"{'#':<4} {'eSIM ID':<38} {'ICCID':<30} {'Status':<15}")
                print("=" * 100)
                
                for idx, esim in enumerate(esims, 1):
                    esim_id = esim.get('id', 'N/A')
                    iccid = esim.get('iccid', 'N/A')
                    status = esim.get('status', 'Unknown')
                    
                    if len(iccid) > 30:
                        iccid = iccid[:27] + "..."
                    if len(esim_id) > 38:
                        esim_id = esim_id[:35] + "..."
                    
                    print(f"{idx:<4} {esim_id:<38} {iccid:<30} {status:<15}")
                
                print("=" * 100)
                print(f"\nTotal eSIMCard eSIMs: {len(esims)}\n")
                
        except Exception as e:
            logger.error(f"Error listing eSIMCard eSIMs: {e}")
            print(f"\n❌ Error listing eSIMCard eSIMs: {e}")


def main():
    """Main entry point for the Enhanced eSIM Status Checker"""
    try:
        print("=" * 70)
        print("🌐 Enhanced eSIM Status Checker")
        print("   Multi-API Support (AirHub + eSIMCard)")
        print("=" * 70)
        
        print("\nOptions:")
        print("1. Search by Order ID")
        print("2. Search by ICCID")
        print("3. List all orders")
        
        choice = input("\nEnter your choice (1, 2, or 3): ").strip()
        
        if choice == "1":
            search_value = input("📝 Enter Order ID: ").strip()
            search_value = validate_input(search_value, 'order_id')
            search_type = 'order_id'
            print()
            logger.info(f"Starting search for {search_type}: {search_value}")
            process_search(search_value, search_type)
            
        elif choice == "2":
            search_value = input("📝 Enter ICCID: ").strip()
            search_value = validate_input(search_value, 'iccid')
            search_type = 'iccid'
            print()
            logger.info(f"Starting search for {search_type}: {search_value}")
            process_search(search_value, search_type)
            
        elif choice == "3":
            print()
            logger.info("Listing all orders")
            list_all_orders()
            
        else:
            raise InvalidInputError("Invalid choice. Please enter 1, 2, or 3.")
        
    except InvalidInputError as e:
        logger.warning(f"Invalid input: {e}")
        print(f"\n❌ {e}")
        sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        print("\n\n⚠️ Process interrupted by user")
        sys.exit(0)
        
    except Exception as e:
        logger.exception(f"Unexpected error in main: {e}")
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

