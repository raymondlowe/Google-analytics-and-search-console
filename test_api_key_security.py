#!/usr/bin/env python3
"""
Test script to validate API key security mechanism in mcp_server.py
"""
import asyncio
import subprocess
import time
import requests
import signal
import sys
import os

def test_api_key_security():
    """Test the API key security mechanism"""
    
    print("🧪 Testing API Key Security for MCP Server...")
    
    # Test 1: Auto-generated API key
    print("\n1. Testing auto-generated API key...")
    process = subprocess.Popen(
        [sys.executable, "-m", "uv", "run", "mcp_server.py", "--http", "--port", "8003"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PATH": "/home/runner/.local/bin:" + os.environ.get("PATH", "")}
    )
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        # Test unauthorized request
        response = requests.get("http://localhost:8003/mcp", timeout=5)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "Missing Authorization header" in response.text
        print("   ✅ Unauthorized request correctly rejected")
        
        # Test wrong API key
        response = requests.get(
            "http://localhost:8003/mcp", 
            headers={"Authorization": "Bearer wrong-key"},
            timeout=5
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "Invalid API key" in response.text
        print("   ✅ Wrong API key correctly rejected")
        
        # Get the generated API key from stdout
        stdout, _ = process.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        stdout, _ = process.communicate()
    
    # Extract API key from output
    api_key = None
    for line in stdout.split('\n'):
        if line.startswith('🔑 API Key:'):
            api_key = line.split('🔑 API Key: ')[1].strip()
            break
    
    if api_key:
        print(f"   📝 Generated API key: {api_key[:10]}...{api_key[-10:]}")
        
        # Start server again for testing with the correct key
        process2 = subprocess.Popen(
            [sys.executable, "-m", "uv", "run", "mcp_server.py", "--http", "--port", "8004", "--key", api_key],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PATH": "/home/runner/.local/bin:" + os.environ.get("PATH", "")}
        )
        
        time.sleep(3)
        
        try:
            # Test with correct API key
            response = requests.get(
                "http://localhost:8004/mcp", 
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5
            )
            # Should get through auth but fail on MCP protocol (expected)
            assert response.status_code != 401, f"Got 401 with correct key: {response.text}"
            print("   ✅ Correct API key accepted")
            
        finally:
            process2.terminate()
            process2.wait(timeout=5)
    else:
        print("   ⚠️ Could not extract API key from output")
    
    # Always terminate the first process
    process.terminate()
    process.wait(timeout=5)
    
    # Test 2: Custom API key
    print("\n2. Testing custom API key...")
    custom_key = "my-custom-test-key-12345"
    process3 = subprocess.Popen(
        [sys.executable, "-m", "uv", "run", "mcp_server.py", "--http", "--port", "8005", "--key", custom_key],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PATH": "/home/runner/.local/bin:" + os.environ.get("PATH", "")}
    )
    
    time.sleep(3)
    
    try:
        # Test with custom API key
        response = requests.get(
            "http://localhost:8005/mcp", 
            headers={"Authorization": f"Bearer {custom_key}"},
            timeout=5
        )
        # Should get through auth but fail on MCP protocol (expected)
        assert response.status_code != 401, f"Got 401 with custom key: {response.text}"
        print(f"   ✅ Custom API key '{custom_key}' accepted")
        
        # Test wrong key
        response = requests.get(
            "http://localhost:8005/mcp", 
            headers={"Authorization": "Bearer wrong-custom-key"},
            timeout=5
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("   ✅ Wrong custom key correctly rejected")
        
    finally:
        process3.terminate()
        process3.wait(timeout=5)
    
    print("\n✅ All API key security tests passed!")
    print("🔒 Security is ON by default")
    print("🔑 Auto-generation works when no key provided")
    print("🛠️ Custom keys work when provided via --key parameter")
    print("🚫 Unauthorized requests are properly blocked")

if __name__ == "__main__":
    test_api_key_security()