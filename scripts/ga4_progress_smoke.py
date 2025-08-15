import asyncio
from pathlib import Path
import sys

# Ensure repo root on path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from webapp.backend.data_providers.ga4_provider import GA4Provider


async def main():
    prov = GA4Provider()

    # Collect progress
    events = []
    async def progress_cb(payload):
        events.append(payload)
        msg = payload.get('message') or payload.get('event')
        if msg:
            print(f"[progress] {msg}")

    # Use up to 4 properties for a more robust smoke test
    props = await prov.list_properties(auth_identifier="")
    property_ids = None
    if props:
        property_ids = [p['id'] for p in props[:4]]
        print(f"Using property_ids: {property_ids}")
    else:
        print("No properties discovered; proceeding to list and query none.")

    df = await prov.execute_query(
        start_date="2025-08-01",
        end_date="2025-08-03",
        dimensions=["pagePath"],
        metrics=["screenPageViews"],
        property_ids=property_ids,
        auth_identifier="",
        debug=False,
        progress_callback=progress_cb,
    )

    print(f"Result rows: {0 if df is None else len(df)}")
    print(f"Progress events: {len(events)}")


if __name__ == "__main__":
    asyncio.run(main())
