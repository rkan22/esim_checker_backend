"""
eSIM Status Checker
A professional tool for checking eSIM order status using Order ID or ICCID
"""

import requests
import sys
import logging
from typing import Optional, Dict, List, Any, Tuple

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
BASE_URL = "https://api.airhubapp.com"
USERNAME = "info@roam2world.com"
PASSWORD = "airhubworld@25"
REQUEST_TIMEOUT = 30  # seconds


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
# API FUNCTIONS
# ========================
def login() -> Tuple[str, str]:
    """
    Authenticate with the eSIM API and return access token and partner code
    
    Returns:
        tuple: (access_token, partner_code)
        
    Raises:
        AuthenticationError: If login fails
        APIError: If network or API error occurs
    """
    url = f"{BASE_URL}/api/Authentication/UserLogin"
    payload = {"userName": USERNAME, "password": PASSWORD}
    
    try:
        logger.info("Attempting to login...")
        response = requests.post(
            url, 
            json=payload, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("isSuccess"):
            error_msg = data.get("message", "Unknown authentication error")
            logger.error(f"Authentication failed: {error_msg}")
            raise AuthenticationError(f"Login failed: {error_msg}")
        
        token = data.get("token")
        if not token:
            raise AuthenticationError("No token received from API")
        
        # Extract partner code from login response
        partner_code = data.get("data", {}).get("partnerCode", "")
        if not partner_code:
            raise AuthenticationError("No partner code received from API")
        
        logger.info(f"Authentication successful. Partner Code: {partner_code}")
        return token, str(partner_code)
        
    except requests.exceptions.Timeout:
        logger.error("Login request timed out")
        raise APIError("Login request timed out. Please check your internet connection.")
    except requests.exceptions.ConnectionError:
        logger.error("Connection error during login")
        raise APIError("Cannot connect to API server. Please check your internet connection.")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error during login: {e}")
        raise APIError(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error during login: {e}")
        raise APIError(f"Request failed: {e}")
    except KeyError as e:
        logger.error(f"Unexpected response format: {e}")
        raise APIError("Unexpected response format from API")


def get_orders(token: str, partner_code: str, flag: int = 1) -> Dict[str, Any]:
    """
    Fetch orders from the API
    
    Args:
        token: Authentication token
        partner_code: Partner code from login
        flag: Search flag (1 = last 300 records, 2 = date range)
        
    Returns:
        Dict containing order details
        
    Raises:
        APIError: If API request fails
    """
    url = f"{BASE_URL}/api/ESIM/GetOrderDetail"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "partnerCode": partner_code,
        "flag": str(flag),
        "fromDate": "",
        "toDate": ""
    }
    
    try:
        logger.info(f"Fetching orders with flag={flag}")
        response = requests.post(
            url, 
            json=payload, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Retrieved {len(data.get('getOrderdetails', []))} orders")
        return data
        
    except requests.exceptions.Timeout:
        logger.error("Order fetch request timed out")
        raise APIError("Request timed out while fetching orders")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error while fetching orders: {e}")
        if e.response.status_code == 401:
            raise AuthenticationError("Authentication token expired or invalid")
        raise APIError(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching orders: {e}")
        raise APIError(f"Failed to fetch orders: {e}")


def get_activation_details(token: str, partner_code: str, order_ids: List[str]) -> Dict[str, Any]:
    """
    Fetch activation details for specific order IDs
    
    Args:
        token: Authentication token
        partner_code: Partner code from login
        order_ids: List of order IDs to fetch
        
    Returns:
        Dict containing activation details
        
    Raises:
        APIError: If API request fails
    """
    url = f"{BASE_URL}/api/ESIM/GetActivationCode"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "partnerCode": partner_code,
        "orderid": order_ids
    }
    
    try:
        logger.info(f"Fetching activation details for orders: {order_ids}")
        response = requests.post(
            url, 
            json=payload, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info("Activation details retrieved successfully")
        return data
        
    except requests.exceptions.Timeout:
        logger.error("Activation details request timed out")
        raise APIError("Request timed out while fetching activation details")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error while fetching activation: {e}")
        if e.response.status_code == 401:
            raise AuthenticationError("Authentication token expired or invalid")
        raise APIError(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching activation details: {e}")
        raise APIError(f"Failed to fetch activation details: {e}")


# ========================
# SEARCH FUNCTIONS
# ========================
def find_order_by_id(orders: List[Dict], order_id: str) -> Optional[Dict]:
    """
    Find an order by Order ID
    
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
    Find an order by ICCID
    
    Args:
        orders: List of order dictionaries
        iccid: ICCID to search for
        
    Returns:
        Order dict if found, None otherwise
    """
    try:
        # Clean up the search ICCID
        search_iccid = iccid.strip().replace(' ', '').replace('-', '').lower()
        
        if not search_iccid:
            logger.warning("Empty ICCID provided for search")
            return None
        
        for order in orders:
            # Get ICCID from various possible fields
            order_iccid = (
                order.get('simID', '') or 
                order.get('iccid', '') or 
                order.get('ICCID', '')
            )
            
            # Clean up the order ICCID
            clean_order_iccid = order_iccid.strip().replace(' ', '').replace('-', '').lower()
            
            # Match exact ICCID or if search string is contained
            if search_iccid == clean_order_iccid or search_iccid in clean_order_iccid:
                logger.info(f"Found order with ICCID: {order_iccid}")
                print(f"   ✓ Matched ICCID: {order_iccid}")
                return order
        
        logger.warning(f"ICCID {iccid} not found")
        return None
        
    except Exception as e:
        logger.error(f"Error searching for order by ICCID: {e}")
        return None


# ========================
# DISPLAY FUNCTIONS
# ========================
def display_esim_summary(order: Dict, activation: Dict) -> None:
    """
    Display eSIM information in a formatted summary
    
    Args:
        order: Order information dictionary
        activation: Activation details dictionary
    """
    try:
        print("\n" + "=" * 50)
        print("📱 eSIM SUMMARY")
        print("=" * 50)
        
        # Extract and display order information
        order_id = order.get('orderId', 'N/A')
        iccid = (
            order.get('simID') or 
            order.get('iccid') or 
            order.get('ICCID') or 
            activation.get('iccid') or 
            'N/A'
        )
        plan_name = order.get('planName', 'N/A')
        status = 'Active' if order.get('isActive') else 'Inactive'
        purchase_date = order.get('purchaseDate', 'N/A')
        validity = order.get('vaildity', 'N/A')
        capacity = order.get('capacity', 'N/A')
        capacity_unit = order.get('capacityUnit', '')
        data_consumed = order.get('dataConsumed', 'N/A')
        data_remaining = order.get('dataRemaining', 'N/A')
        
        # Extract activation details
        activation_code = activation.get('activationCode', 'N/A') if activation else 'N/A'
        apn = activation.get('apn', 'N/A') if activation else 'N/A'
        
        # Display formatted information
        print(f"Order ID:        {order_id}")
        print(f"ICCID:           {iccid}")
        print(f"Plan:            {plan_name}")
        print(f"Status:          {status}")
        print(f"Purchase Date:   {purchase_date}")
        print(f"Validity:        {validity} days")
        print(f"Data:            {capacity} {capacity_unit}")
        print(f"Data Consumed:   {data_consumed}")
        print(f"Data Remaining:  {data_remaining}")
        
        # Add note if data usage is not available
        if data_consumed == 'N/A' and data_remaining == 'N/A':
            if status == 'Inactive':
                print(f"                 (Usage data unavailable for inactive eSIMs)")
        
        print(f"Activation Code: {activation_code if activation_code else 'N/A'}")
        print(f"APN:             {apn if apn else 'N/A'}")
        print("=" * 50)
        
        logger.info(f"Displayed summary for order {order_id}")
        
    except Exception as e:
        logger.error(f"Error displaying summary: {e}")
        print(f"\n⚠️ Error formatting display: {e}")


# ========================
# MAIN PROCESS FUNCTIONS
# ========================
def process_search(search_value: str, search_type: str) -> None:
    """
    Main process to search and display eSIM information
    
    Args:
        search_value: Order ID or ICCID to search
        search_type: Type of search ('order_id' or 'iccid')
        
    Raises:
        Various custom exceptions for different error conditions
    """
    token = None
    partner_code = None
    
    try:
        # Step 1: Authentication
        print("🔐 Logging in...")
        token, partner_code = login()
        print("✅ Logged in\n")
        
        # Step 2: Fetch orders
        search_label = "Order ID" if search_type == 'order_id' else "ICCID"
        print(f"📊 Searching for order by {search_label}...")
        
        orders_response = get_orders(token, partner_code)
        orders = orders_response.get("getOrderdetails", [])
        
        if not orders:
            raise OrderNotFoundError("No orders found in your account")
        
        # Step 3: Find specific order
        order = None
        if search_type == 'order_id':
            order = find_order_by_id(orders, search_value)
        else:
            order = find_order_by_iccid(orders, search_value)
        
        if not order:
            raise OrderNotFoundError(
                f"No order found for {search_label}: '{search_value}'\n"
                f"Note: Search is limited to last 300 orders."
            )
        
        print("✅ Order found\n")
        
        # Step 4: Get order ID
        order_id = order.get('orderId')
        if not order_id:
            raise APIError("Order ID is missing from order data")
        
        print(f"🔍 Using Order ID: {order_id}")
        
        # Step 5: Fetch activation details
        print("📡 Fetching activation details...")
        activation = {}
        try:
            activation_response = get_activation_details(token, partner_code, [str(order_id)])
            activation_list = activation_response.get("getOrderdetails", [])
            activation = activation_list[0] if activation_list else {}
            print("✅ Activation details retrieved\n")
        except APIError as e:
            logger.warning(f"Could not fetch activation details: {e}")
            print(f"⚠️ Could not fetch activation details")
            print("Continuing with order information only...\n")
        
        # Step 6: Display summary
        display_esim_summary(order, activation)
        
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
        # Order ID should be numeric
        if not cleaned_value.isdigit():
            raise InvalidInputError("Order ID must contain only numbers")
    
    elif input_type == 'iccid':
        # ICCID should be alphanumeric (allowing spaces and dashes)
        cleaned_for_check = cleaned_value.replace(' ', '').replace('-', '')
        if not cleaned_for_check.isalnum():
            raise InvalidInputError("ICCID must contain only letters and numbers")
        
        # ICCID should have reasonable length (typically 19-20 digits)
        if len(cleaned_for_check) < 10:
            raise InvalidInputError("ICCID seems too short (minimum 10 characters)")
    
    return cleaned_value


# ========================
# MAIN ENTRY POINT
# ========================
def list_all_orders() -> None:
    """List all available orders with their ICCIDs and Order IDs"""
    try:
        print("🔐 Logging in...")
        token, partner_code = login()
        print("✅ Logged in\n")
        
        print("📊 Fetching all orders...")
        orders_response = get_orders(token, partner_code)
        orders = orders_response.get("getOrderdetails", [])
        
        if not orders:
            print("❌ No orders found in your account")
            return
        
        print(f"\n✅ Found {len(orders)} order(s)\n")
        print("=" * 100)
        print(f"{'#':<4} {'Order ID':<12} {'ICCID':<30} {'Plan':<30} {'Status':<10}")
        print("=" * 100)
        
        for idx, order in enumerate(orders, 1):
            order_id = order.get('orderId', 'N/A')
            
            # Get ICCID and clean up the "SIM ID: " prefix if present
            iccid_raw = order.get('simID', '') or order.get('iccid', '') or order.get('ICCID', '') or 'N/A'
            iccid = iccid_raw.replace('SIM ID: ', '').strip() if iccid_raw != 'N/A' else 'N/A'
            
            plan_name = order.get('planName', 'N/A')
            status = 'Active' if order.get('isActive') else 'Inactive'
            
            # Truncate fields if too long
            if len(iccid) > 30:
                iccid = iccid[:27] + "..."
            if len(plan_name) > 30:
                plan_name = plan_name[:27] + "..."
            
            print(f"{idx:<4} {order_id:<12} {iccid:<30} {plan_name:<30} {status:<10}")
        
        print("=" * 100)
        print(f"\nTotal orders: {len(orders)}")
        print("\nNote: This shows the last 300 orders. Use search options to find specific orders.\n")
        
    except Exception as e:
        logger.error(f"Error listing orders: {e}")
        print(f"\n❌ Error listing orders: {e}")


def main():
    """Main entry point for the eSIM Status Checker"""
    try:
        print("=" * 50)
        print("🌐 eSIM Status Checker")
        print("=" * 50)
        
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
