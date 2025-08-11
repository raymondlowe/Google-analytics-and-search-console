#!/usr/bin/env python3
"""
Test authentication fallback functionality for mcp_server.py.

This test verifies that the server allows EITHER Bearer header OR URL parameter authentication,
and importantly, falls back from invalid header auth to valid URL parameter auth.
"""
import subprocess
import sys
import time
import requests
import json
import threading
from threading import Thread


class MCPServerTest:
    def __init__(self, api_key="testkey123", port=8004):
        self.api_key = api_key
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self.server_proc = None
        
    def start_server(self):
        """Start the MCP server in a subprocess"""
        cmd = [sys.executable, "mcp_server.py", "--http", "--port", str(self.port), "--key", self.api_key]
        self.server_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(3)  # Give server time to start
        
    def stop_server(self):
        """Stop the MCP server"""
        if self.server_proc:
            self.server_proc.terminate()
            self.server_proc.wait()
            
    def make_request(self, headers=None, url_params=None):
        """Make a request to the MCP server with given headers and URL parameters"""
        url = f"{self.base_url}/mcp"
        if url_params:
            url += "?" + "&".join([f"{k}={v}" for k, v in url_params.items()])
        
        default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if headers:
            default_headers.update(headers)
            
        payload = {"jsonrpc": "2.0", "id": "test", "method": "initialize", "params": {}}
        
        try:
            response = requests.post(url, headers=default_headers, json=payload, timeout=5)
            return response.status_code, response.text
        except Exception as e:
            return None, str(e)
    
    def test_valid_bearer_only(self):
        """Test: Valid Bearer header only"""
        print("Test 1: Valid Bearer header only")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        status, text = self.make_request(headers=headers)
        success = status == 200
        print(f"  Status: {status}, Success: {success}")
        return success
    
    def test_valid_url_only(self):
        """Test: Valid URL parameter only"""
        print("Test 2: Valid URL parameter only")
        url_params = {"key": self.api_key}
        status, text = self.make_request(url_params=url_params)
        success = status == 200
        print(f"  Status: {status}, Success: {success}")
        return success
    
    def test_invalid_bearer_valid_url(self):
        """Test: Invalid Bearer header with valid URL parameter (this is the key test)"""
        print("Test 3: Invalid Bearer header + valid URL parameter (FALLBACK TEST)")
        headers = {"Authorization": "Bearer wrongkey"}
        url_params = {"key": self.api_key}
        status, text = self.make_request(headers=headers, url_params=url_params)
        success = status == 200
        print(f"  Status: {status}, Success: {success}")
        if not success:
            print(f"  Response: {text[:200]}")
        return success
    
    def test_valid_bearer_invalid_url(self):
        """Test: Valid Bearer header with invalid URL parameter (should use header)"""
        print("Test 4: Valid Bearer header + invalid URL parameter")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url_params = {"key": "wrongkey"}
        status, text = self.make_request(headers=headers, url_params=url_params)
        success = status == 200
        print(f"  Status: {status}, Success: {success}")
        return success
    
    def test_both_invalid(self):
        """Test: Both authentication methods invalid"""
        print("Test 5: Both Bearer header and URL parameter invalid")
        headers = {"Authorization": "Bearer wrongkey"}
        url_params = {"key": "wrongkey2"}
        status, text = self.make_request(headers=headers, url_params=url_params)
        success = status == 401  # Should fail
        print(f"  Status: {status}, Success: {success}")
        return success
    
    def test_no_auth(self):
        """Test: No authentication provided"""
        print("Test 6: No authentication")
        status, text = self.make_request()
        success = status == 401  # Should fail
        print(f"  Status: {status}, Success: {success}")
        return success
    
    def run_all_tests(self):
        """Run all authentication tests"""
        print("Starting authentication fallback tests...\n")
        
        self.start_server()
        
        try:
            tests = [
                ("valid_bearer_only", self.test_valid_bearer_only),
                ("valid_url_only", self.test_valid_url_only),
                ("invalid_bearer_valid_url", self.test_invalid_bearer_valid_url),  # KEY TEST
                ("valid_bearer_invalid_url", self.test_valid_bearer_invalid_url),
                ("both_invalid", self.test_both_invalid),
                ("no_auth", self.test_no_auth)
            ]
            
            results = {}
            for test_name, test_func in tests:
                results[test_name] = test_func()
                print()
            
            # Print summary
            print("=" * 60)
            print("TEST RESULTS SUMMARY")
            print("=" * 60)
            
            all_passed = True
            for test_name, passed in results.items():
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"{test_name:25} {status}")
                if not passed:
                    all_passed = False
            
            # Check the key test specifically
            key_test_passed = results.get("invalid_bearer_valid_url", False)
            if key_test_passed:
                print(f"\n🎉 SUCCESS: Authentication fallback is working!")
                print(f"   Invalid Bearer header + valid URL parameter = SUCCESS")
            else:
                print(f"\n❌ FAILURE: Authentication fallback is NOT working!")
                print(f"   Invalid Bearer header + valid URL parameter = FAILED")
            
            print(f"\nOverall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
            return all_passed
            
        finally:
            self.stop_server()


def main():
    """Main test function"""
    tester = MCPServerTest()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()