#!/usr/bin/env python3
"""
Test script to verify the authorization fallback mechanism works correctly.
This tests both header-based authentication and URL parameter fallback.
"""
import asyncio
import subprocess
import time
import json
import httpx
import secrets

async def test_auth_fallback():
    """Test both header-based and URL parameter authentication"""
    
    # Generate test API key
    test_key = secrets.token_urlsafe(16)
    
    print("🧪 Testing Authorization Fallback Mechanism")
    print(f"Using test API key: {test_key}")
    
    # Start the MCP server in HTTP mode
    print("\n📡 Starting MCP HTTP server...")
    server_process = subprocess.Popen([
        "/home/runner/.local/bin/uv", "run", "python", "mcp_server.py", 
        "--http", "--host", "127.0.0.1", "--port", "8001", 
        "--key", test_key
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    await asyncio.sleep(3)
    
    base_url = "http://127.0.0.1:8001/mcp"
    
    try:
        async with httpx.AsyncClient() as client:
            print("\n🔑 Test 1: Header-based authentication (RECOMMENDED)")
            
            # Test with Authorization header (should work)
            headers = {"Authorization": f"Bearer {test_key}"}
            try:
                response = await client.get(f"{base_url}/health", headers=headers, timeout=10)
                if response.status_code == 200:
                    print("✅ Header-based auth: SUCCESS")
                else:
                    print(f"❌ Header-based auth failed: {response.status_code}")
            except Exception as e:
                print(f"❌ Header-based auth error: {e}")
            
            print("\n🔄 Test 2: URL parameter fallback authentication")
            
            # Test with URL parameter (should work as fallback)
            try:
                response = await client.get(f"{base_url}/health?key={test_key}", timeout=10)
                if response.status_code == 200:
                    print("✅ URL parameter fallback auth: SUCCESS")
                else:
                    print(f"❌ URL parameter fallback failed: {response.status_code}")
            except Exception as e:
                print(f"❌ URL parameter fallback error: {e}")
            
            print("\n🚫 Test 3: No authentication (should fail)")
            
            # Test without any authentication (should fail)
            try:
                response = await client.get(f"{base_url}/health", timeout=10)
                if response.status_code == 401:
                    print("✅ No auth rejection: SUCCESS (correctly rejected)")
                else:
                    print(f"❌ No auth should have been rejected but got: {response.status_code}")
            except Exception as e:
                print(f"❌ No auth test error: {e}")
            
            print("\n🔍 Test 4: Invalid key (should fail)")
            
            # Test with wrong key (should fail)
            try:
                response = await client.get(f"{base_url}/health?key=wrong_key", timeout=10)
                if response.status_code == 401:
                    print("✅ Invalid key rejection: SUCCESS (correctly rejected)")
                else:
                    print(f"❌ Invalid key should have been rejected but got: {response.status_code}")
            except Exception as e:
                print(f"❌ Invalid key test error: {e}")
            
            print("\n🎯 Test 5: Header takes precedence over URL param")
            
            # Test header precedence (valid header, invalid URL param)
            headers = {"Authorization": f"Bearer {test_key}"}
            try:
                response = await client.get(f"{base_url}/health?key=wrong_key", headers=headers, timeout=10)
                if response.status_code == 200:
                    print("✅ Header precedence: SUCCESS (header used over URL param)")
                else:
                    print(f"❌ Header precedence failed: {response.status_code}")
            except Exception as e:
                print(f"❌ Header precedence test error: {e}")
    
    finally:
        # Clean up
        print("\n🧹 Cleaning up...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
        print("✅ Server stopped")
    
    print("\n🎉 Auth fallback testing completed!")

if __name__ == "__main__":
    print("🚀 Starting Authorization Fallback Tests")
    asyncio.run(test_auth_fallback())