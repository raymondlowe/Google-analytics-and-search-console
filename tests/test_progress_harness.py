import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys

import pandas as pd

# Ensure repo root is on sys.path so `webapp` package is importable when running from tests/
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Import provider from webapp backend
from webapp.backend.data_providers.gsc_provider import GSCProvider

logging.basicConfig(level=logging.INFO)

async def main():
    provider = GSCProvider()

    # Collect progress messages here
    events = []

    async def progress_cb(payload):
        # Simple console print and store
        msg = payload.get("message")
        cur = payload.get("current")
        tot = payload.get("total")
        print(f"[CB] {msg} ({cur}/{tot})")
        events.append(payload)

    # Quick auth check: list domains
    domains = await provider.list_domains("")
    print(f"Domains available: {len(domains)}")
    if not domains:
        print("No domains accessible; progress demo may exit early.")

    # Use a tiny recent window; adjust if needed
    end_date = datetime.utcnow().date()
    start_date = (end_date - timedelta(days=1))

    # Try a domain-less run to exercise listing and multiple sites; keep dimensions simple
    df = await provider.execute_query(
        start_date=str(start_date),
        end_date=str(end_date),
        dimensions=["page"],
        domain_filter=None,
        auth_identifier="",  # default token
        search_type="web",
        debug=True,
        progress_callback=progress_cb,
    )

    print(f"Result rows: {0 if df is None else len(df)}")

    # Basic assertions for manual run
    # Expect at least start and finish events
    start_seen = any(e.get("message", "").lower().startswith("gsc: starting") or e.get("event") == "start" for e in events)
    finish_seen = any("finished" in (e.get("message", "").lower()) or e.get("event") == "finish" for e in events)
    print(f"Start seen: {start_seen}, Finish seen: {finish_seen}, Progress events: {len(events)}")

if __name__ == "__main__":
    asyncio.run(main())
