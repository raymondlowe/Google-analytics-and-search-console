import requests
import time
import sys

API_URL = "http://127.0.0.1:8000/api/query"
STATUS_URL = "http://127.0.0.1:8000/api/query_status/{}"

# Example query payload (adjust as needed for your backend)
payload = {
    "start_date": "2025-08-01",
    "end_date": "2025-08-03",
    "sources": ["gsc"],
    "dimensions": ["page"],
    "metrics": ["clicks"],
    "properties": [],
    "auth_identifier": "",
    "debug": False,
    "filters": {},
}

def main():
    print(f"POSTing to {API_URL} ...")
    resp = requests.post(API_URL, json=payload)
    if resp.status_code != 200:
        print(f"Failed to start query: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    query_id = data.get("query_id")
    if not query_id:
        print(f"No query_id returned: {data}")
        sys.exit(1)
    print(f"Started query: {query_id}")
    print(f"Polling {STATUS_URL.format(query_id)} ...")
    while True:
        r = requests.get(STATUS_URL.format(query_id))
        if r.status_code == 404:
            print("Query not found (yet?)")
            time.sleep(1)
            continue
        status = r.json()
        progress = status.get("progress")
        print(f"Progress: {progress}")
        if progress and (progress.get("message", "").lower().startswith("finished") or progress.get("current") == progress.get("total")):
            print("Query complete.")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()
