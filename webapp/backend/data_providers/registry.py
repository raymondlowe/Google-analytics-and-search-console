"""
Data provider registry and unified interface
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import logging
from .ga4_provider import GA4Provider
from .gsc_provider import GSCProvider

logger = logging.getLogger(__name__)


class DataProviderRegistry:
    """Registry for managing different data providers"""
    
    def __init__(self):
        self.providers = {
            "ga4": GA4Provider(),
            "gsc": GSCProvider()
        }
    
    def get_provider(self, source: str):
        """Get data provider by source name"""
        return self.providers.get(source)
    
    def list_sources(self) -> List[str]:
        """Get list of available data sources"""
        return list(self.providers.keys())
    
    async def get_all_metadata(self) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
        """Get metadata from all providers"""
        metadata = {}
        for source, provider in self.providers.items():
            try:
                metadata[source] = await provider.get_metadata()
            except Exception as e:
                logger.error(f"Error getting metadata for {source}: {e}")
                metadata[source] = {"dimensions": [], "metrics": []}
        
        return metadata
    
    async def execute_unified_query(self, start_date: str, end_date: str,
                                  sources: List[str], dimensions: List[str],
                                  metrics: List[str], properties: Optional[List[str]] = None,
                                  auth_identifier: str = "", debug: bool = False,
                                  filters: Optional[Dict[str, Any]] = None,
                                  progress_callback=None) -> List[Dict[str, Any]]:
        """Execute query across multiple data sources and return unified results"""
        
        all_results = []
        gsc_results = []
        total_sources = len(sources)
        current_source = 0

        for source in sources:
            provider = self.get_provider(source)
            if not provider:
                logger.warning(f"Unknown data source: {source}")
                continue

            # Report progress for starting this source
            if progress_callback:
                await progress_callback({
                    "current": 2,
                    "total": 3,
                    "message": f"Querying {source.upper()} data... ({current_source + 1}/{total_sources})"
                })

            try:
                if source == "ga4":
                    # GA4 specific handling
                    property_ids = properties if properties else None
                    df = await provider.execute_query(
                        start_date=start_date,
                        end_date=end_date,
                        dimensions=dimensions,
                        metrics=metrics,
                        property_ids=property_ids,
                        auth_identifier=auth_identifier,
                        filters=filters,
                        debug=debug
                    )
                    normalized_data = provider.normalize_data(df)
                    all_results.extend(normalized_data)
                    logger.info(f"GA4 query completed: {len(normalized_data)} rows retrieved")
                    
                elif source == "gsc":
                    # GSC specific handling - filter dimensions to only valid GSC ones
                    gsc_metadata = await provider.get_metadata()
                    valid_gsc_dims = [dim["id"] for dim in gsc_metadata["dimensions"]]
                    gsc_dimensions = [dim for dim in dimensions if dim in valid_gsc_dims]

                    if not gsc_dimensions:
                        gsc_dimensions = ["page"]  # Default to page if no valid dimensions

                    df = await provider.execute_query(
                        start_date=start_date,
                        end_date=end_date,
                        dimensions=gsc_dimensions,
                        domain_filter=properties,
                        auth_identifier=auth_identifier,
                        debug=debug
                    )
                    normalized_data = provider.normalize_data(df)
                    gsc_results.extend(normalized_data)
                    logger.info(f"GSC query completed: {len(normalized_data)} rows retrieved")
                else:
                    continue

                # Report progress after completing this source
                current_source += 1
                if progress_callback and current_source < total_sources:
                    await progress_callback({
                        "current": 2,
                        "total": 3,
                        "message": f"Completed {source.upper()}, processing next source... ({current_source}/{total_sources})"
                    })

            except Exception as e:
                logger.error(f"Error executing query for {source}: {e}")
                current_source += 1
                continue

        # Aggregate GSC domain variants if any GSC results
        if gsc_results:
            if progress_callback:
                await progress_callback({
                    "current": 2,
                    "total": 3,
                    "message": "Aggregating GSC domain variants..."
                })
            from .aggregate_domains import aggregate_gsc_domain_variants
            gsc_results = aggregate_gsc_domain_variants(gsc_results)
            all_results.extend(gsc_results)

        return all_results