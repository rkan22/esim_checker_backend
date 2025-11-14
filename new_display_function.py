def display_esim_summary(order: Dict, activation: Dict, provider: APIProvider, 
                        esimcard_data: Optional[Dict] = None, 
                        usage_data: Optional[Dict] = None,
                        travelroam_data: Optional[Dict] = None,
                        travelroam_bundles: Optional[Dict] = None,
                        travelroam_location: Optional[Dict] = None) -> None:
    """
    Display eSIM information - INTELLIGENTLY MERGES data from all available APIs
    Priority: Use best data from each API for each field
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
                            
                            # Calculate validity
                            start_time = assignment.get('startTime', '')
                            end_time = assignment.get('endTime', '')
                            if start_time and end_time and merged['validity'] == 'N/A':
                                try:
                                    from datetime import datetime
                                    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                                    merged['validity'] = str((end - start).days)
                                except:
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

