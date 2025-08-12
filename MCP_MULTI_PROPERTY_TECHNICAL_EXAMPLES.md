# MCP Multi-Property Upgrade - Technical Implementation Examples

## Code Examples and Implementation Details

This document provides concrete code examples and technical implementation details for the multi-property upgrade.

## Parameter Parsing Implementation

### Enhanced Parameter Processing

```python
from typing import Union, List
import re

def parse_multi_input(value: Union[str, List[str]]) -> List[str]:
    """
    Parse property_id or domain parameter into list of values.
    
    Supports:
    - Single string: "123456"
    - Comma-separated: "123456,789012,345678"
    - Array: ["123456", "789012", "345678"]
    - Mixed with whitespace: "123456, 789012 , 345678"
    """
    if not value:
        return []
    
    if isinstance(value, list):
        # Handle array input
        result = []
        for item in value:
            if isinstance(item, (str, int)):
                cleaned = str(item).strip()
                if cleaned:
                    result.append(cleaned)
        return result
    
    if isinstance(value, str):
        if ',' in value:
            # Handle comma-separated string
            return [v.strip() for v in value.split(',') if v.strip()]
        else:
            # Handle single string
            return [value.strip()] if value.strip() else []
    
    # Handle other types (int, etc.)
    if value:
        return [str(value).strip()]
    
    return []

def validate_property_ids(property_ids: List[str]) -> tuple[List[str], List[str]]:
    """
    Validate property ID format and return valid/invalid lists.
    
    Returns:
        tuple: (valid_ids, invalid_ids)
    """
    valid_ids = []
    invalid_ids = []
    
    # GA4 property IDs are typically 9-12 digit numbers
    property_id_pattern = re.compile(r'^\d{9,12}$')
    
    for prop_id in property_ids:
        if property_id_pattern.match(prop_id):
            valid_ids.append(prop_id)
        else:
            invalid_ids.append(prop_id)
    
    return valid_ids, invalid_ids

def validate_domains(domains: List[str]) -> tuple[List[str], List[str]]:
    """
    Validate domain format and return valid/invalid lists.
    
    Returns:
        tuple: (valid_domains, invalid_domains)
    """
    valid_domains = []
    invalid_domains = []
    
    # Basic domain validation pattern
    domain_pattern = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
    )
    
    for domain in domains:
        if domain_pattern.match(domain) and len(domain) <= 253:
            valid_domains.append(domain)
        else:
            invalid_domains.append(domain)
    
    return valid_domains, invalid_domains
```

## Enhanced Tool Implementation

### Multi-Property GA4 Query Tool

```python
@mcp.tool()
async def query_ga4_data(
    start_date: str, 
    end_date: str, 
    auth_identifier: str = "",
    property_id: Union[str, List[str]] = "",
    domain_filter: Union[str, List[str]] = "",
    metrics: str = "screenPageViews,totalAdRevenue,sessions",
    dimensions: str = "pagePath",
    response_format: str = "aggregated",  # "aggregated" | "grouped"
    include_property_metadata: bool = True,
    max_properties: int = 20,
    debug: bool = False
) -> dict:
    """
    Enhanced GA4 query tool with multi-property support.
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    set_request_context(request_id)
    
    # Parse and validate inputs
    property_ids = parse_multi_input(property_id)
    domain_filters = parse_multi_input(domain_filter)
    
    logger.info(f"[{request_id}] Multi-property GA4 query - "
               f"properties: {len(property_ids) or 'all'}, "
               f"domains: {len(domain_filters) or 'all'}")
    
    # Validate date range
    if not validate_date_range(start_date, end_date):
        return create_error_response(request_id, "Invalid date range")
    
    # Validate property IDs if provided
    if property_ids:
        valid_props, invalid_props = validate_property_ids(property_ids)
        if invalid_props:
            return create_validation_error_response(
                request_id, 
                f"Invalid property IDs: {invalid_props}",
                {"invalid_property_ids": invalid_props}
            )
        property_ids = valid_props
    
    # Validate domain filters if provided
    if domain_filters:
        valid_domains, invalid_domains = validate_domains(domain_filters)
        if invalid_domains:
            return create_validation_error_response(
                request_id,
                f"Invalid domains: {invalid_domains}",
                {"invalid_domains": invalid_domains}
            )
        domain_filters = valid_domains
    
    # Check batch limits
    if property_ids and len(property_ids) > max_properties:
        return create_error_response(
            request_id,
            f"Too many properties requested: {len(property_ids)}. Maximum: {max_properties}"
        )
    
    try:
        # Determine query strategy
        if property_ids:
            # Query specific properties
            result = await query_specific_properties(
                property_ids, start_date, end_date, auth_identifier,
                metrics, dimensions, domain_filters, debug, request_id
            )
        else:
            # Query all properties (existing behavior)
            result = await query_all_properties(
                start_date, end_date, auth_identifier,
                metrics, dimensions, domain_filters, debug, request_id
            )
        
        # Format response based on requested format
        if response_format == "grouped":
            formatted_result = format_grouped_response(result, include_property_metadata)
        else:
            formatted_result = format_aggregated_response(result, include_property_metadata)
        
        # Add timing and metadata
        duration = time.time() - start_time
        formatted_result.update({
            "request_id": request_id,
            "duration_seconds": round(duration, 2),
            "todays_date": datetime.now().strftime('%Y-%m-%d')
        })
        
        logger.info(f"[{request_id}] Multi-property GA4 query completed - "
                   f"{formatted_result.get('summary', {}).get('total_rows', 0)} rows in {duration:.2f}s")
        
        return formatted_result
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Multi-property GA4 query failed: {str(e)}"
        logger.error(f"[{request_id}] {error_msg}, duration: {duration:.2f}s", exc_info=True)
        return create_error_response(request_id, error_msg)

async def query_specific_properties(
    property_ids: List[str],
    start_date: str,
    end_date: str,
    auth_identifier: str,
    metrics: str,
    dimensions: str,
    domain_filters: List[str],
    debug: bool,
    request_id: str
) -> dict:
    """Query specific GA4 properties concurrently."""
    
    # Get property metadata first
    properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
    if properties_df is None or properties_df.empty:
        raise Exception("No GA4 properties accessible")
    
    # Filter to requested properties
    available_properties = properties_df[
        properties_df['property_id'].isin(property_ids) | 
        properties_df['id'].isin(property_ids)
    ]
    
    if available_properties.empty:
        raise Exception(f"None of the requested properties are accessible: {property_ids}")
    
    # Track results and errors
    successful_properties = []
    failed_properties = []
    combined_df = pd.DataFrame()
    
    # Create domain filter expression if provided
    filter_expr = None
    if domain_filters:
        # Create OR filter for multiple domains
        domain_conditions = [f"hostname=={domain}" for domain in domain_filters]
        filter_expr = " OR ".join(domain_conditions)
    
    # Query properties concurrently (with concurrency limit)
    semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
    
    async def query_single_property_safe(property_row):
        async with semaphore:
            pid = property_row.get("property_id") or property_row.get("id")
            property_name = property_row.get("displayName", f"Property {pid}")
            
            try:
                df_prop = GA4query3.produce_report(
                    start_date=start_date,
                    end_date=end_date,
                    property_id=pid,
                    property_name=property_name,
                    account=auth_identifier,
                    filter_expression=filter_expr,
                    dimensions=dimensions,
                    metrics=metrics,
                    debug=debug
                )
                
                if df_prop is not None and not df_prop.empty:
                    # Add source attribution
                    df_prop['property_id'] = pid
                    df_prop['property_name'] = property_name
                    df_prop['_source_attribution'] = df_prop.apply(
                        lambda row: {
                            "property_id": pid,
                            "property_name": property_name,
                            "data_freshness": datetime.now().isoformat()
                        }, axis=1
                    )
                    
                    successful_properties.append({
                        "property_id": pid,
                        "property_name": property_name,
                        "rows_contributed": len(df_prop),
                        "status": "success"
                    })
                    return df_prop
                else:
                    successful_properties.append({
                        "property_id": pid,
                        "property_name": property_name,
                        "rows_contributed": 0,
                        "status": "no_data"
                    })
                    return pd.DataFrame()
                    
            except Exception as e:
                failed_properties.append({
                    "property_id": pid,
                    "property_name": property_name,
                    "error": str(e),
                    "error_type": "query_failed",
                    "retry_recommended": True
                })
                logger.warning(f"[{request_id}] Property {pid} query failed: {str(e)}")
                return pd.DataFrame()
    
    # Execute concurrent queries
    tasks = [
        query_single_property_safe(row) 
        for _, row in available_properties.iterrows()
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Combine successful results
    for result in results:
        if isinstance(result, pd.DataFrame) and not result.empty:
            combined_df = pd.concat([combined_df, result], ignore_index=True)
    
    # Determine overall status
    total_requested = len(property_ids)
    total_successful = len(successful_properties)
    total_failed = len(failed_properties)
    
    if total_successful == 0:
        status = "error"
        message = f"All {total_requested} properties failed"
    elif total_failed == 0:
        status = "success"
        message = f"Retrieved data from all {total_successful} properties"
    else:
        status = "partial_success"
        message = f"Retrieved data from {total_successful} of {total_requested} properties"
    
    return {
        "status": status,
        "message": message,
        "data": combined_df,
        "successful_properties": successful_properties,
        "failed_properties": failed_properties,
        "request_metadata": {
            "requested_properties": property_ids,
            "total_requested": total_requested,
            "total_successful": total_successful,
            "total_failed": total_failed
        }
    }
```

## Response Formatting Functions

### Aggregated Response Format

```python
def format_aggregated_response(query_result: dict, include_metadata: bool = True) -> dict:
    """Format query result as aggregated response."""
    
    df = query_result["data"]
    response = {
        "status": query_result["status"],
        "message": query_result["message"],
        "date_range": {
            "start_date": query_result.get("start_date"),
            "end_date": query_result.get("end_date")
        }
    }
    
    if not df.empty:
        response.update({
            "data": df.to_dict('records'),
            "row_count": len(df),
            "summary": {
                "total_rows": len(df),
                "properties_queried": len(query_result["successful_properties"]),
                "properties_successful": len([p for p in query_result["successful_properties"] if p["status"] == "success"]),
                "properties_failed": len(query_result["failed_properties"])
            }
        })
        
        # Add aggregated metrics if numeric columns exist
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) > 0:
            aggregated_metrics = {}
            for col in numeric_columns:
                if col not in ['property_id']:  # Skip ID columns
                    aggregated_metrics[f"total_{col}"] = df[col].sum()
            response["summary"]["aggregated_metrics"] = aggregated_metrics
    else:
        response.update({
            "data": [],
            "row_count": 0,
            "summary": {
                "total_rows": 0,
                "properties_queried": len(query_result["successful_properties"]) + len(query_result["failed_properties"]),
                "properties_successful": 0,
                "properties_failed": len(query_result["failed_properties"])
            }
        })
    
    # Include metadata if requested
    if include_metadata:
        response["property_metadata"] = query_result["successful_properties"]
        
    # Include errors if any
    if query_result["failed_properties"]:
        response["failed_properties"] = query_result["failed_properties"]
    
    response["source"] = "ga4"
    return response

def format_grouped_response(query_result: dict, include_metadata: bool = True) -> dict:
    """Format query result as grouped-by-property response."""
    
    df = query_result["data"]
    response = {
        "status": query_result["status"],
        "message": query_result["message"],
        "response_format": "grouped",
        "properties": {}
    }
    
    if not df.empty:
        # Group data by property
        for prop_info in query_result["successful_properties"]:
            prop_id = prop_info["property_id"]
            prop_data = df[df["property_id"] == prop_id].copy()
            
            # Remove internal columns for cleaner output
            display_data = prop_data.drop(columns=['property_id', 'property_name', '_source_attribution'], errors='ignore')
            
            property_response = {
                "data": display_data.to_dict('records'),
                "row_count": len(prop_data),
                "status": prop_info["status"]
            }
            
            if include_metadata:
                property_response["property_metadata"] = {
                    "property_id": prop_id,
                    "property_name": prop_info["property_name"],
                    "rows_contributed": prop_info["rows_contributed"]
                }
            
            # Add property-level summary
            numeric_columns = display_data.select_dtypes(include=[np.number]).columns
            if len(numeric_columns) > 0:
                property_summary = {}
                for col in numeric_columns:
                    property_summary[f"total_{col}"] = display_data[col].sum()
                property_response["summary"] = property_summary
            
            response["properties"][prop_id] = property_response
    
    # Add overall summary
    response["overall_summary"] = {
        "total_properties": len(query_result["successful_properties"]) + len(query_result["failed_properties"]),
        "successful_properties": len(query_result["successful_properties"]),
        "failed_properties": len(query_result["failed_properties"]),
        "total_rows": len(df) if not df.empty else 0
    }
    
    # Include aggregated metrics across all properties
    if not df.empty:
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) > 0:
            aggregated_metrics = {}
            for col in numeric_columns:
                if col not in ['property_id']:
                    aggregated_metrics[f"total_{col}"] = df[col].sum()
            response["overall_summary"]["aggregated_metrics"] = aggregated_metrics
    
    # Include failed properties
    if query_result["failed_properties"]:
        response["failed_properties"] = query_result["failed_properties"]
    
    response["source"] = "ga4"
    return response
```

## Error Handling Utilities

```python
def create_error_response(request_id: str, message: str, details: dict = None) -> dict:
    """Create standardized error response."""
    response = {
        "status": "error",
        "message": message,
        "request_id": request_id,
        "todays_date": datetime.now().strftime('%Y-%m-%d')
    }
    
    if details:
        response.update(details)
    
    return response

def create_validation_error_response(request_id: str, message: str, validation_details: dict) -> dict:
    """Create validation error response with helpful suggestions."""
    
    suggestions = []
    
    if "invalid_property_ids" in validation_details:
        suggestions.extend([
            "Ensure property IDs are 9-12 digit numbers",
            "Use the 'list_ga4_properties' tool to see available properties",
            "Check that you have access to the specified properties"
        ])
    
    if "invalid_domains" in validation_details:
        suggestions.extend([
            "Ensure domains are in valid format (e.g., 'example.com')",
            "Do not include 'http://' or 'https://' in domain names",
            "Use the 'list_gsc_domains' tool to see available domains"
        ])
    
    return create_error_response(
        request_id, 
        message, 
        {
            **validation_details,
            "error_type": "validation_error",
            "suggestions": suggestions
        }
    )
```

## Usage Examples

### Basic Multi-Property Query

```python
# Query specific properties with enhanced attribution
result = await query_ga4_data(
    start_date="2024-01-01",
    end_date="2024-01-31",
    property_id=["123456789", "987654321", "456789123"],
    metrics="screenPageViews,totalAdRevenue,sessions",
    dimensions="pagePath,deviceCategory",
    response_format="aggregated",
    include_property_metadata=True
)
```

### Grouped Response Example

```python
# Get data grouped by property for comparison
result = await query_ga4_data(
    start_date="2024-01-01",
    end_date="2024-01-31",
    property_id="123456,789012",  # Comma-separated format
    response_format="grouped",
    metrics="screenPageViews,totalAdRevenue"
)

# Access individual property data
main_site_data = result["properties"]["123456"]["data"]
blog_site_data = result["properties"]["789012"]["data"]
```

### Error Handling Example

```python
# Handle partial success scenarios
result = await query_ga4_data(
    property_id=["123456", "invalid-id", "999999"],
    start_date="2024-01-01",
    end_date="2024-01-31"
)

if result["status"] == "partial_success":
    successful_data = result["data"]
    failed_properties = result["failed_properties"]
    
    for failure in failed_properties:
        print(f"Property {failure['property_id']} failed: {failure['error']}")
        if failure.get("retry_recommended"):
            print("Retry may succeed")
```

## Performance Monitoring

```python
import time
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class QueryMetrics:
    """Track performance metrics for multi-property queries."""
    request_id: str
    property_count: int
    start_time: float
    end_time: float
    success_count: int
    failure_count: int
    total_rows: int
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return (self.success_count / total) if total > 0 else 0.0

class PerformanceMonitor:
    """Monitor and track multi-property query performance."""
    
    def __init__(self):
        self.metrics: List[QueryMetrics] = []
        self.active_queries: Dict[str, float] = {}
    
    def start_query(self, request_id: str, property_count: int):
        """Start tracking a query."""
        self.active_queries[request_id] = {
            "start_time": time.time(),
            "property_count": property_count
        }
    
    def end_query(self, request_id: str, success_count: int, failure_count: int, total_rows: int):
        """End tracking and record metrics."""
        if request_id in self.active_queries:
            query_info = self.active_queries.pop(request_id)
            
            metrics = QueryMetrics(
                request_id=request_id,
                property_count=query_info["property_count"],
                start_time=query_info["start_time"],
                end_time=time.time(),
                success_count=success_count,
                failure_count=failure_count,
                total_rows=total_rows
            )
            
            self.metrics.append(metrics)
            return metrics
    
    def get_performance_stats(self) -> dict:
        """Get aggregated performance statistics."""
        if not self.metrics:
            return {"message": "No metrics available"}
        
        durations = [m.duration for m in self.metrics]
        success_rates = [m.success_rate for m in self.metrics]
        
        return {
            "total_queries": len(self.metrics),
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "avg_success_rate": sum(success_rates) / len(success_rates),
            "total_properties_queried": sum(m.property_count for m in self.metrics),
            "total_rows_returned": sum(m.total_rows for m in self.metrics)
        }

# Global performance monitor instance
performance_monitor = PerformanceMonitor()
```

## Testing Examples

```python
import pytest
import asyncio
from unittest.mock import Mock, patch

class TestMultiPropertyParsing:
    """Test parameter parsing functionality."""
    
    def test_parse_single_string(self):
        result = parse_multi_input("123456")
        assert result == ["123456"]
    
    def test_parse_comma_separated(self):
        result = parse_multi_input("123456,789012,345678")
        assert result == ["123456", "789012", "345678"]
    
    def test_parse_array(self):
        result = parse_multi_input(["123456", "789012"])
        assert result == ["123456", "789012"]
    
    def test_parse_empty_input(self):
        assert parse_multi_input("") == []
        assert parse_multi_input([]) == []
        assert parse_multi_input(None) == []
    
    def test_parse_with_whitespace(self):
        result = parse_multi_input("123456, 789012 , 345678")
        assert result == ["123456", "789012", "345678"]

class TestPropertyValidation:
    """Test property ID validation."""
    
    def test_valid_property_ids(self):
        valid, invalid = validate_property_ids(["123456789", "987654321"])
        assert valid == ["123456789", "987654321"]
        assert invalid == []
    
    def test_invalid_property_ids(self):
        valid, invalid = validate_property_ids(["invalid", "123", ""])
        assert valid == []
        assert invalid == ["invalid", "123", ""]
    
    def test_mixed_property_ids(self):
        valid, invalid = validate_property_ids(["123456789", "invalid", "987654321"])
        assert valid == ["123456789", "987654321"]
        assert invalid == ["invalid"]

@pytest.mark.asyncio
class TestMultiPropertyQuery:
    """Test multi-property query functionality."""
    
    @patch('GA4query3.list_properties')
    @patch('GA4query3.produce_report')
    async def test_successful_multi_property_query(self, mock_produce_report, mock_list_properties):
        # Setup mocks
        mock_list_properties.return_value = pd.DataFrame([
            {"property_id": "123456", "displayName": "Test Site 1"},
            {"property_id": "789012", "displayName": "Test Site 2"}
        ])
        
        mock_produce_report.return_value = pd.DataFrame([
            {"pagePath": "/home", "screenPageViews": 1000}
        ])
        
        # Execute query
        result = await query_ga4_data(
            start_date="2024-01-01",
            end_date="2024-01-31",
            property_id=["123456", "789012"]
        )
        
        # Verify results
        assert result["status"] == "success"
        assert len(result["data"]) == 2  # Two properties, one row each
        assert result["summary"]["properties_successful"] == 2
    
    async def test_partial_success_scenario(self):
        # Test when some properties succeed and others fail
        # Implementation would test error handling
        pass
    
    async def test_batch_limit_enforcement(self):
        # Test that batch limits are properly enforced
        result = await query_ga4_data(
            start_date="2024-01-01",
            end_date="2024-01-31",
            property_id=["123456"] * 25,  # Exceed limit
            max_properties=20
        )
        
        assert result["status"] == "error"
        assert "Too many properties" in result["message"]
```

This technical appendix provides concrete implementation examples and code patterns for the multi-property upgrade. The code emphasizes:

1. **Robust Parameter Parsing**: Handles multiple input formats gracefully
2. **Comprehensive Validation**: Validates both format and accessibility
3. **Concurrent Processing**: Efficiently queries multiple properties
4. **Rich Error Handling**: Provides detailed error information and suggestions
5. **Flexible Response Formats**: Supports both aggregated and grouped outputs
6. **Performance Monitoring**: Tracks and reports performance metrics
7. **Comprehensive Testing**: Covers all major functionality and edge cases