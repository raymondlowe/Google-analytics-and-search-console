#!/usr/bin/env python3
"""
Test script to debug authentication issues with MCP server.
This helps identify if headers are being stripped by proxies/tunnels.
"""

import requests
import json
import sys

def test_mcp_server(base_url, api_key, use_header_auth=True):
    """Test MCP server authentication"""
    
    print(f"\n🔍 Testing MCP server at: {base_url}")
    print(f"📋 Using {'header' if use_header_auth else 'URL parameter'} authentication")
    
    # Prepare the request
    if use_header_auth:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        url = f"{base_url}/mcp"
        auth_method = "Authorization header"
    else:
        headers = {
            "Content-Type": "application/json"
        }
        url = f"{base_url}/mcp?key={api_key}"
        auth_method = "URL parameter"
    
    # Simple HTTP test - just check if authentication works
    print(f"🚀 Sending test request using {auth_method}...")
    print(f"📤 Headers: {headers}")
    print(f"🔗 URL: {url}")
    
    try:
        # First, try a simple GET request to check authentication
        get_response = requests.get(
            url,
            headers=headers if use_header_auth else {},
            params={} if use_header_auth else {"key": api_key},
            timeout=30
        )
        
        print(f"\n📋 GET Response Status: {get_response.status_code}")
        print(f"📋 GET Response Headers: {dict(get_response.headers)}")
        
        if get_response.status_code == 200:
            print("✅ Authentication successful!")
            print(f"📄 GET Response: Connection established and authenticated")
            return True
        elif get_response.status_code == 401:
            print(f"❌ Authentication failed!")
            try:
                error_details = get_response.json()
                print(f"🔴 Error details: {json.dumps(error_details, indent=2)}")
            except json.JSONDecodeError:
                print(f"🔴 Error response (raw): {get_response.text}")
            return False
        else:
            print(f"⚠️ Unexpected response code: {get_response.status_code}")
            print(f"📄 Response: {get_response.text}")
            
        # If GET worked, try a POST with MCP message format
        if get_response.status_code == 200:
            print("\n🔄 Testing MCP protocol message...")
            
            # MCP protocol message to test
            test_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "debug_request_headers",
                    "arguments": {}
                }
            }
            
            post_headers = headers.copy()
            post_headers["Content-Type"] = "application/vnd.openai.mcp+json"  # MCP content type
            
            response = requests.post(
                url,
                headers=post_headers,
                json=test_message,
                timeout=30
            )
            
            print(f"\n📋 POST Response Status: {response.status_code}")
            print(f"📋 POST Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                print("✅ MCP protocol communication successful!")
                try:
                    result = response.json()
                    print(f"📄 MCP Response: {json.dumps(result, indent=2)}")
                except json.JSONDecodeError:
                    print(f"📄 MCP Response (raw): {response.text}")
                return True
            else:
                print(f"⚠️ MCP protocol failed with status: {response.status_code}")
                print(f"� MCP Error: {response.text}")
                return get_response.status_code == 200  # Auth worked even if MCP didn't
        
        return False
                
    except requests.exceptions.RequestException as e:
        print(f"🔴 Request failed: {e}")
        return False

def main():
    if len(sys.argv) < 3:
        print("Usage: python test_auth_debug.py <base_url> <api_key> [test_both]")
        print("Examples:")
        print("  python test_auth_debug.py http://localhost:8080 mypassword")
        print("  python test_auth_debug.py https://your-tunnel.trycloudflare.com mypassword test_both")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    api_key = sys.argv[2]
    test_both = len(sys.argv) > 3 and sys.argv[3] == "test_both"
    
    print("🧪 MCP Server Authentication Debug Tool")
    print("=" * 50)
    
    # Test header authentication
    header_success = test_mcp_server(base_url, api_key, use_header_auth=True)
    
    if test_both or not header_success:
        # Test URL parameter authentication
        print("\n" + "=" * 50)
        url_success = test_mcp_server(base_url, api_key, use_header_auth=False)
        
        print("\n🏁 Summary:")
        print(f"📋 Header auth: {'✅ Working' if header_success else '❌ Failed'}")
        print(f"📋 URL param auth: {'✅ Working' if url_success else '❌ Failed'}")
        
        if not header_success and url_success:
            print("\n💡 Diagnosis: Authorization headers are being stripped!")
            print("   This commonly happens with:")
            print("   - Cloudflare tunnels without proper configuration")
            print("   - Reverse proxies that filter Authorization headers")
            print("   - Load balancers with security policies")
            print("   - Network security appliances")
    else:
        print("\n🏁 Header authentication working correctly!")

if __name__ == "__main__":
    main()
