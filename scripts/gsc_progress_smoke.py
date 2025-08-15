import asyncio
from pathlib import Path
import sys

# Ensure repo root on path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from webapp.backend.data_providers.gsc_provider import GSCProvider


async def main():
    prov = GSCProvider()

    # Collect progress
    events = []
    async def progress_cb(payload):
        events.append(payload)
        msg = payload.get('message') or payload.get('event')
        if msg:
            print(f"[progress] {msg}")

    # Try to limit scope to a single domain to keep runtime fast
    domains = await prov.list_domains(auth_identifier="")
    domain_filter = None
    if domains:
        domain_filter = [domains[0]['id']]
        print(f"Using domain_filter: {domain_filter[0]}")
    else:
        print("No domains discovered; proceeding without filter.")

    df = await prov.execute_query(
        start_date="2025-08-01",
        end_date="2025-08-03",
        dimensions=["page"],
        domain_filter=domain_filter,
        auth_identifier="",
        debug=False,
        progress_callback=progress_cb,
    )

    print(f"Result rows: {0 if df is None else len(df)}")
    print(f"Progress events: {len(events)}")


if __name__ == "__main__":
    asyncio.run(main())
