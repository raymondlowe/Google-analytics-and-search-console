# High-level aggregation for GSC domain variants
# This function should be called after all_results are collected in execute_unified_query
from collections import defaultdict
from typing import List, Dict, Any
import re

def aggregate_gsc_domain_variants(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Aggregate GSC results by base domain, summing numeric fields for all variants (e.g., www, http, https).
    Returns a new list with one entry per base domain.
    """
    domain_groups = defaultdict(list)
    domain_pattern = re.compile(r"^(https?://)?(www\.)?([^/]+)")

    for row in results:
        domain = None
        # Try to find a domain field (commonly 'site', 'property', or 'domain')
        for key in ['site', 'property', 'domain', 'siteUrl', 'propertyUrl', 'page', 'url']:
            if key in row:
                match = domain_pattern.match(str(row[key]))
                if match:
                    domain = match.group(3)
                    break
        if not domain:
            continue  # skip if no domain found
        domain_groups[domain].append(row)

    aggregated = []
    for domain, rows in domain_groups.items():
        agg_row = dict(rows[0])
        # Overwrite the domain field to just the base domain
        for key in ['site', 'property', 'domain', 'siteUrl', 'propertyUrl', 'page', 'url']:
            if key in agg_row:
                agg_row[key] = domain
        # Sum or average numeric fields as appropriate
        for k in agg_row:
            if isinstance(agg_row[k], (int, float)):
                if k in ("position", "ctr"):
                    # Average, ignoring missing/nulls
                    values = [float(r.get(k, 0)) for r in rows if r.get(k) is not None]
                    agg_row[k] = sum(values) / len(values) if values else 0
                else:
                    agg_row[k] = sum(float(r.get(k, 0) or 0) for r in rows)
        aggregated.append(agg_row)
    return aggregated
