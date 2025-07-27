
# Automated MCP server test script with verbose output
# Tests multiple tools and prints results for each

import requests
import time
import json

BASE_URL = "http://127.0.0.1:8000/mcp"
API_KEY = "testkey123"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}

def mcp_request(method, params=None, session=None):
    """
    Send a JSON-RPC request to the MCP server.
    method: The tool or method name (e.g., 'get_server_stats')
    params: Dictionary of parameters for the tool
    session: Session ID if required
    Returns: Parsed JSON response or raw text
    """
    payload = {
        "jsonrpc": "2.0",
        "id": str(time.time()),
        "method": method,
        "params": params or {}
    }
    if session:
        payload["session"] = session
    resp = requests.post(BASE_URL, headers=HEADERS, data=json.dumps(payload))
    try:
        return resp.json()
    except Exception:
        return resp.text

def print_section(title):
    print("\n" + "="*60)
    print(f"{title}")
    print("="*60)

def main():
    # Step 1: Initialize session
    print_section("Initializing MCP session")
    init_resp = mcp_request("session.initialize")
    print(json.dumps(init_resp, indent=2))
    session_id = None
    if "result" in init_resp and "session" in init_resp["result"]:
        session_id = init_resp["result"]["session"]
    else:
        print("Failed to initialize session, aborting.")
        return

    # Step 2: Test get_server_stats
    print_section("Testing get_server_stats tool")
    stats_resp = mcp_request("get_server_stats", session=session_id)
    print(json.dumps(stats_resp, indent=2))

    # Step 3: Test list_ga4_properties
    print_section("Testing list_ga4_properties tool")
    ga4_resp = mcp_request("list_ga4_properties", session=session_id)
    print(json.dumps(ga4_resp, indent=2))

    # Step 4: Test list_gsc_domains
    print_section("Testing list_gsc_domains tool")
    gsc_resp = mcp_request("list_gsc_domains", session=session_id)
    print(json.dumps(gsc_resp, indent=2))

    # Step 5: Test validate_ga4_parameters with sample input
    print_section("Testing validate_ga4_parameters tool")
    validate_resp = mcp_request(
        "validate_ga4_parameters",
        params={"dimensions": "pagePath", "metrics": "screenPageViews"},
        session=session_id
    )
    print(json.dumps(validate_resp, indent=2))

    # Step 6: Test a tool with required arguments (query_ga4_data)
    print_section("Testing query_ga4_data tool (with minimal required args)")
    today = time.strftime("%Y-%m-%d")
    query_resp = mcp_request(
        "query_ga4_data",
        params={
            "start_date": today,
            "end_date": today
        },
        session=session_id
    )
    print(json.dumps(query_resp, indent=2))

    print("\nAll tests completed.")

if __name__ == "__main__":
    main()
