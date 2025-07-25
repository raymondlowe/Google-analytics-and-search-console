#!/usr/bin/env python3
"""
Simple test to verify authentication fallback mechanism works.
"""
import subprocess
import time
import requests
import secrets

def test_auth_simple():
    """Test both header-based and URL parameter authentication"""
    
    # Generate test API key
    test_key = "testkey123"
    
    print("🧪 Testing Authorization Fallback Mechanism")
    print(f"Using test API key: {test_key}")
    
    # Start the MCP server in HTTP mode
    print("\n📡 Starting MCP HTTP server...")
    server_process = subprocess.Popen([
        "/home/runner/.local/bin/uv", "run", "python", "mcp_server.py", 
        "--http", "--host", "127.0.0.1", "--port", "8002", 
        "--key", test_key
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    time.sleep(4)
    
    base_url = "http://127.0.0.1:8002/mcp"
    
    try:
        print("\n🔑 Test 1: No authentication (should fail with 401)")
        response = requests.get(base_url, timeout=10)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ No auth correctly rejected with 401")
        
        print("\n🔑 Test 2: Wrong key via URL parameter (should fail with 401)")
        response = requests.get(f"{base_url}?key=wrongkey", timeout=10)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Wrong key correctly rejected with 401")
        
        print("\n🔑 Test 3: Correct key via Authorization header (should pass auth)")
        headers = {"Authorization": f"Bearer {test_key}"}
        response = requests.get(base_url, headers=headers, timeout=10)
        assert response.status_code != 401, f"Auth should have passed but got {response.status_code}"
        print(f"✅ Header auth passed (got {response.status_code}, not 401)")
        
        print("\n🔑 Test 4: Correct key via URL parameter (should pass auth)")
        response = requests.get(f"{base_url}?key={test_key}", timeout=10)
        assert response.status_code != 401, f"Auth should have passed but got {response.status_code}"
        print(f"✅ URL parameter auth passed (got {response.status_code}, not 401)")
        
        print("\n🔑 Test 5: Header takes precedence (valid header + invalid URL)")
        headers = {"Authorization": f"Bearer {test_key}"}
        response = requests.get(f"{base_url}?key=wrongkey", headers=headers, timeout=10)
        assert response.status_code != 401, f"Header should take precedence but got {response.status_code}"
        print(f"✅ Header precedence works (got {response.status_code}, not 401)")
        
        print("\n🎉 All authentication tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        # Clean up
        print("\n🧹 Cleaning up...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
        print("✅ Server stopped")
    
    return True

if __name__ == "__main__":
    print("🚀 Starting Simple Authentication Fallback Tests")
    success = test_auth_simple()
    if success:
        print("\n✅ SUCCESS: Authorization fallback mechanism is working correctly!")
    else:
        print("\n❌ FAILURE: Something went wrong with the tests.")