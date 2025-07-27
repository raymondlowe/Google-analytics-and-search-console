import subprocess
import sys
import json
import time

# Test script for MCP server in stdio mode

def start_server():
    # Start the server in stdio mode
    return subprocess.Popen(
        [sys.executable, "mcp_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

def send_request(proc, method, params=None):
    req = {
        "jsonrpc": "2.0",
        "id": str(time.time()),
        "method": method,
        "params": params or {}
    }
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    # Read response
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        try:
            resp = json.loads(line)
            if resp.get("id") == req["id"]:
                return resp
        except Exception:
            continue

def main():
    proc = start_server()
    time.sleep(2)  # Give server time to start

    # Test get_server_stats
    print("Testing get_server_stats...")
    resp = send_request(proc, "get_server_stats")
    print(json.dumps(resp, indent=2))

    # Test list_ga4_properties
    print("Testing list_ga4_properties...")
    resp = send_request(proc, "list_ga4_properties")
    print(json.dumps(resp, indent=2))

    # Test list_gsc_domains
    print("Testing list_gsc_domains...")
    resp = send_request(proc, "list_gsc_domains")
    print(json.dumps(resp, indent=2))

    proc.terminate()

if __name__ == "__main__":
    main()
