#!/usr/bin/env python3
"""
QuickBooks Online Items Extractor
Simple script to get all items from QBO for AvSight mapping
"""

import requests
import json
import base64
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
import csv
from datetime import datetime

def get_qbo_items():
    print("=" * 60)
    print("    QUICKBOOKS ONLINE ITEMS EXTRACTOR")
    print("=" * 60)
    print()
    
    # Get credentials from user
    print("Enter the credentials your boss provided:")
    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()
    
    if not client_id or not client_secret:
        print("❌ Error: Both Client ID and Client Secret are required")
        return
    
    print(f"\n✅ Using PRODUCTION QuickBooks Online")
    print("⚠️  Make sure your app is published or approved for production!")
    
    # Step 1: Get Authorization
    print(f"\n" + "="*50)
    print("STEP 1: GETTING AUTHORIZATION")
    print("="*50)
    
    auth_url = f"https://appcenter.intuit.com/connect/oauth2?" + urllib.parse.urlencode({
        'client_id': client_id,
        'scope': 'com.intuit.quickbooks.accounting',
        'redirect_uri': 'https://b8dfe4fc8f10.ngrok-free.app/callback',
        'response_type': 'code',
        'access_type': 'offline',
        'state': 'qbo_items_' + str(int(time.time()))
    })
    
    # Variables to capture the callback
    callback_data = {'code': None, 'company_id': None, 'error': None}
    
    class CallbackHandler(BaseHTTPRequestHandler):
        def _write_html(self, status_code: int, html: str):
            self.send_response(status_code)
            # Explicitly tell the browser we’re sending UTF-8
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            # Encode to UTF-8 so non-ASCII (emoji) is safe
            self.wfile.write(html.encode('utf-8'))

        def do_GET(self):
            parsed_url = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed_url.query)
            
            if 'code' in params and 'realmId' in params:
                callback_data['code'] = params['code'][0]
                callback_data['company_id'] = params['realmId'][0]

                self._write_html(200, """
                <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: green;">✅ SUCCESS!</h1>
                <p>Authorization completed successfully.</p>
                <p>You can close this window and return to your terminal.</p>
                <script>setTimeout(() => window.close(), 3000);</script>
                </body></html>
                """)
                
            elif 'error' in params:
                callback_data['error'] = params.get('error', ['Unknown'])[0]
                self._write_html(400, f"""
                <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: red;">❌ ERROR</h1>
                <p>Authorization failed: {callback_data['error']}</p>
                </body></html>
                """)
            
            # Shutdown server after handling request
            threading.Thread(target=lambda: (time.sleep(1), self.server.shutdown())).start()
        
        def log_message(self, format, *args):
            pass  # Suppress server logs
    
    # Start callback server
    server = HTTPServer(('localhost', 8080), CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.start()
    
    print(f"🌐 Opening QuickBooks Online authorization page...")
    print(f"📋 If browser doesn't open, copy this URL:")
    print(f"   {auth_url}")
    print(f"\n⏳ Waiting for authorization...")
    
    webbrowser.open(auth_url)
    
    # Wait for callback (max 5 minutes)
    start_time = time.time()
    while time.time() - start_time < 300:  # 5 minutes timeout
        if callback_data['code'] or callback_data['error']:
            break
        time.sleep(0.5)
    
    server_thread.join(timeout=1)
    
    if callback_data['error']:
        print(f"❌ Authorization failed: {callback_data['error']}")
        return
    
    if not callback_data['code']:
        print(f"❌ Timeout: No authorization received after 5 minutes")
        return
    
    print(f"✅ Authorization successful!")
    print(f"📊 Company ID: {callback_data['company_id']}")
    
    # Step 2: Get Access Token
    print(f"\n" + "="*50)
    print("STEP 2: GETTING ACCESS TOKEN")
    print("="*50)
    
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    
    token_response = requests.post(
        'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer',
        headers={
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        data={
            'grant_type': 'authorization_code',
            'code': callback_data['code'],
            'redirect_uri': 'https://b8dfe4fc8f10.ngrok-free.app/callback'
        }
    )
    
    if token_response.status_code != 200:
        print(f"❌ Failed to get access token: {token_response.text}")
        return
    
    token_data = token_response.json()
    access_token = token_data['access_token']
    
    print(f"✅ Access token obtained!")
    
    # Step 3: Get All Items
    print(f"\n" + "="*50)
    print("STEP 3: DOWNLOADING ALL ITEMS")
    print("="*50)
    
    all_items = []
    start_position = 1
    max_results = 200
    
    while True:
        print(f"📥 Fetching items starting from position {start_position}...")
        
        query = f"SELECT * FROM Item STARTPOSITION {start_position} MAXRESULTS {max_results}"
        
        response = requests.get(
            f"https://prod-quickbooks.api.intuit.com/v3/company/{callback_data['company_id']}/query",
            headers={'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'},
            params={'query': query}
        )
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        
        if 'QueryResponse' not in data or 'Item' not in data['QueryResponse']:
            break
        
        items_batch = data['QueryResponse']['Item']
        all_items.extend(items_batch)
        
        print(f"   Found {len(items_batch)} items in this batch")
        
        if len(items_batch) < max_results:
            break  # Got all items
        
        start_position += max_results
    
    print(f"✅ Downloaded {len(all_items)} total items")
    
    # Step 4: Process and Save Items
    print(f"\n" + "="*50)
    print("STEP 4: PROCESSING AND SAVING DATA")
    print("="*50)
    
    processed_items = []
    
    for item in all_items:
        processed_item = {
            'QBO_ID': item.get('Id'),
            'Name': item.get('Name', ''),
            'Type': item.get('Type', ''),
            'Active': item.get('Active', True),
            'Description': item.get('Description', ''),
            'Unit_Price': item.get('UnitPrice', ''),
            'SKU': item.get('Sku', ''),
            'Qty_On_Hand': item.get('QtyOnHand', '') if item.get('Type') == 'Inventory' else 'N/A',
            'Full_Name': item.get('FullyQualifiedName', item.get('Name', '')),
            'Last_Modified': item.get('MetaData', {}).get('LastUpdatedTime', '')
        }
        processed_items.append(processed_item)
    
    # Generate timestamp for filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save as CSV
    csv_filename = f"qbo_items_{timestamp}.csv"
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['QBO_ID', 'Name', 'Type', 'Active', 'Description', 'Unit_Price', 'SKU', 'Qty_On_Hand', 'Full_Name', 'Last_Modified']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(processed_items)
    
    # Save as JSON
    json_filename = f"qbo_items_{timestamp}.json"
    with open(json_filename, 'w', encoding='utf-8') as jsonfile:
        json.dump(processed_items, jsonfile, indent=2, ensure_ascii=False)
    
    print(f"💾 Files saved:")
    print(f"   📊 CSV: {csv_filename}")
    print(f"   📋 JSON: {json_filename}")
    
    # Summary
    print(f"\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    
    active_items = sum(1 for item in processed_items if item['Active'])
    inactive_items = len(processed_items) - active_items
    
    item_types = {}
    for item in processed_items:
        item_type = item['Type']
        item_types[item_type] = item_types.get(item_type, 0) + 1
    
    print(f"📊 Total Items: {len(processed_items)}")
    print(f"✅ Active Items: {active_items}")
    print(f"❌ Inactive Items: {inactive_items}")
    print(f"\n📋 Items by Type:")
    for item_type, count in sorted(item_types.items()):
        print(f"   {item_type}: {count}")
    
    print(f"\n🎯 NEXT STEPS:")
    print(f"1. Open {csv_filename} in Excel or Numbers")
    print(f"2. Use the 'QBO_ID' column for mapping in AvSight")
    print(f"3. Match item names between AvSight and QuickBooks")
    
    print(f"\n✅ COMPLETE! Your QuickBooks items are ready for AvSight mapping.")

if __name__ == "__main__":
    try:
        get_qbo_items()
    except KeyboardInterrupt:
        print(f"\n❌ Process cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"Please check your credentials and try again.")
