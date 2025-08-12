# MCP Multi-Property Upgrade Specification

## Executive Summary

This document outlines a comprehensive upgrade to the Google Analytics 4 (GA4) and Google Search Console (GSC) Model Context Protocol (MCP) server to support multiple property IDs and domain names as input parameters. The upgrade will enable users to query specific subsets of their properties/domains in a single call, improving efficiency and reducing the need for multiple API calls.

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Business Rationale](#business-rationale)
3. [Current Architecture Analysis](#current-architecture-analysis)
4. [Requirements](#requirements)
5. [Design Approaches](#design-approaches)
6. [Recommended Implementation](#recommended-implementation)
7. [API Design Specification](#api-design-specification)
8. [Data Format Enhancements](#data-format-enhancements)
9. [Backward Compatibility Strategy](#backward-compatibility-strategy)
10. [Performance Considerations](#performance-considerations)
11. [Error Handling Strategy](#error-handling-strategy)
12. [Testing Strategy](#testing-strategy)
13. [Implementation Phases](#implementation-phases)
14. [Risk Assessment](#risk-assessment)
15. [Success Metrics](#success-metrics)

## Problem Statement

### Current Limitations

The existing MCP server tools have the following limitations:

1. **Binary Property Selection**: Tools accept either a single property ID/domain or query ALL properties
2. **Inefficient Workflows**: Users must make multiple API calls to query specific subsets of properties
3. **Limited Source Attribution**: Results lack clear identification of which property/domain generated each data point
4. **Poor Resource Utilization**: Cannot optimize queries for specific property groups

### Pain Points

- **Enterprise Users**: Managing 10+ properties requires inefficient "query all + filter" approach
- **Multi-Brand Organizations**: Cannot easily compare data across specific brand properties
- **Regional Analysis**: Difficult to aggregate data from properties in specific geographic regions
- **Development Workflows**: Cannot test against specific development/staging properties efficiently

## Business Rationale

### Target Use Cases

1. **Multi-Brand Portfolio Analysis**
   - Compare performance across specific brand properties
   - Generate cross-brand reports with source attribution
   - Analyze cannibalization between competing brands

2. **Regional Market Intelligence**
   - Aggregate data from properties in specific markets
   - Compare regional performance metrics
   - Optimize regional SEO and marketing strategies

3. **Development Lifecycle Management**
   - Query staging/development properties for testing
   - Validate changes across specific property sets
   - Isolate production from non-production data

4. **Client Reporting Automation**
   - Agencies managing client properties
   - Automated report generation for specific client portfolios
   - Cost center attribution and billing

### Value Proposition

- **Efficiency**: Reduce API calls by 70-90% for subset queries
- **Clarity**: Improved data attribution and source identification
- **Flexibility**: Enable complex multi-property analysis workflows
- **Performance**: Optimize resource usage for large property portfolios

## Current Architecture Analysis

### Existing Implementation

```python
# Current GA4 tool signature
async def query_ga4_data(
    start_date: str, 
    end_date: str, 
    property_id: str = "",  # Single property or empty for all
    domain_filter: str = "",
    # ... other params
) -> dict:
```

### Current Behavior Analysis

1. **When property_id is empty**: Queries ALL accessible properties
2. **When property_id is specified**: Queries only that single property
3. **Data Aggregation**: Results combined into single DataFrame
4. **Source Attribution**: Limited property identification in results

### Current Data Flow

```
User Request → MCP Tool → Property Discovery → Individual API Calls → Aggregation → Response
```

**Example Current Response Structure:**
```json
{
  "status": "success",
  "data": [
    {"pagePath": "/home", "screenPageViews": 1000, "property_name": "Main Site"},
    {"pagePath": "/about", "screenPageViews": 500, "property_name": "Main Site"}
  ],
  "row_count": 2,
  "source": "ga4"
}
```

## Requirements

### Functional Requirements

1. **Multi-Property Input Support**
   - Accept list of property IDs as string or array
   - Accept list of domain names as string or array
   - Support comma-separated string format for backward compatibility

2. **Enhanced Source Attribution**
   - Include property ID/domain in each result row
   - Provide property metadata (name, type, URL)
   - Enable filtering and grouping by source property

3. **Flexible Query Modes**
   - All properties (current behavior)
   - Specific property list
   - Single property (current behavior)
   - Mixed property and domain filtering

4. **Result Organization**
   - Maintain aggregated format option
   - Add grouped-by-property format option
   - Include per-property summary statistics

### Non-Functional Requirements

1. **Performance**
   - Maximum 20% overhead compared to current all-properties query
   - Concurrent property queries where possible
   - Efficient property validation and filtering

2. **Usability**
   - Intuitive parameter format
   - Clear error messages for invalid properties
   - Helpful suggestions for property discovery

3. **Reliability**
   - Graceful handling of inaccessible properties
   - Partial success responses for mixed results
   - Timeout handling for slow properties

4. **Maintainability**
   - Minimal changes to existing code structure
   - Clear separation of concerns
   - Comprehensive test coverage

## Design Approaches

### Approach 1: String-Based List Format

**Implementation**: Extend existing string parameters to accept comma-separated lists

```python
# Example usage
property_id = "123456,789012,345678"
domain = "site1.com,site2.com,blog.company.com"
```

**Pros:**
- Minimal API changes
- Backward compatible
- Simple implementation

**Cons:**
- Limited validation capabilities
- Parsing complexity
- Type safety concerns

### Approach 2: New Array Parameters

**Implementation**: Add new list-based parameters alongside existing ones

```python
# New parameters
property_ids: List[str] = []
domains: List[str] = []

# Maintain existing for backward compatibility
property_id: str = ""
domain: str = ""
```

**Pros:**
- Type safety
- Better validation
- Clear semantics

**Cons:**
- Parameter proliferation
- Complex precedence rules
- Migration complexity

### Approach 3: Unified Object Parameter

**Implementation**: Replace individual parameters with structured input

```python
# New structured parameter
targets: Dict = {
    "property_ids": [],
    "domains": [],
    "include_all": False
}
```

**Pros:**
- Clean interface
- Extensible design
- Clear semantics

**Cons:**
- Breaking change
- Migration required
- Increased complexity

### Approach 4: Hybrid String/Array Support (RECOMMENDED)

**Implementation**: Intelligent parameter parsing supporting both formats

```python
# Support both formats
property_id: Union[str, List[str]] = ""
domain: Union[str, List[str]] = ""

# Internal parsing logic handles:
# - Single string: "123456"
# - Comma-separated: "123456,789012"
# - Array: ["123456", "789012"]
```

**Pros:**
- Backward compatible
- Flexible input formats
- Gradual migration path

**Cons:**
- Complex parsing logic
- Type ambiguity
- Validation complexity

## Recommended Implementation

### Chosen Approach: Hybrid String/Array Support (Approach 4)

This approach provides the best balance of backward compatibility, usability, and functionality.

#### Implementation Strategy

1. **Parameter Enhancement**: Extend existing parameters to accept multiple formats
2. **Intelligent Parsing**: Detect and parse different input formats
3. **Validation Layer**: Comprehensive property/domain validation
4. **Response Enhancement**: Improved source attribution and organization

#### Key Design Decisions

1. **Parameter Names**: Keep existing `property_id` and `domain` parameter names
2. **Input Formats**: Support string, comma-separated string, and array formats
3. **Validation**: Pre-validate all properties/domains before querying
4. **Error Handling**: Return partial results with detailed error information
5. **Response Format**: Maintain existing structure with enhanced attribution

## API Design Specification

### Enhanced Tool Signatures

```python
@mcp.tool()
async def query_ga4_data(
    start_date: str,
    end_date: str,
    auth_identifier: str = "",
    property_id: Union[str, List[str]] = "",  # ENHANCED: Multi-format support
    domain_filter: Union[str, List[str]] = "",  # ENHANCED: Multi-format support
    metrics: str = "screenPageViews,totalAdRevenue,sessions",
    dimensions: str = "pagePath",
    response_format: str = "aggregated",  # NEW: "aggregated" | "grouped"
    include_property_metadata: bool = True,  # NEW: Include property details
    debug: bool = False
) -> dict:
```

```python
@mcp.tool()
async def query_gsc_data(
    start_date: str,
    end_date: str,
    auth_identifier: str = "",
    domain: Union[str, List[str]] = "",  # ENHANCED: Multi-format support
    dimensions: str = "page,query,country,device",
    search_type: str = "web",
    response_format: str = "aggregated",  # NEW: "aggregated" | "grouped"
    include_domain_metadata: bool = True,  # NEW: Include domain details
    debug: bool = False
) -> dict:
```

### Input Format Examples

```python
# Single property (existing behavior)
property_id = "123456789"

# Multiple properties - comma-separated string
property_id = "123456789,987654321,456789123"

# Multiple properties - array format
property_id = ["123456789", "987654321", "456789123"]

# Mixed domain filtering
domain_filter = ["mainsite.com", "blog.mainsite.com"]
```

### Parameter Processing Logic

```python
def parse_multi_input(value: Union[str, List[str]]) -> List[str]:
    """Parse property_id or domain parameter into list of values."""
    if not value:
        return []
    
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    
    if isinstance(value, str):
        if ',' in value:
            return [v.strip() for v in value.split(',') if v.strip()]
        else:
            return [value.strip()] if value.strip() else []
    
    return []
```

## Data Format Enhancements

### Enhanced Response Structure

```json
{
  "status": "success",
  "message": "Retrieved data from 3 properties",
  "request_metadata": {
    "requested_properties": ["123456", "789012", "345678"],
    "successful_properties": ["123456", "789012"],
    "failed_properties": [{
      "property_id": "345678",
      "error": "Access denied",
      "suggestion": "Check property permissions"
    }],
    "response_format": "aggregated"
  },
  "date_range": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  },
  "data": [
    {
      "pagePath": "/home",
      "screenPageViews": 1000,
      "totalAdRevenue": 25.50,
      "property_id": "123456",
      "property_name": "Main Website",
      "property_url": "https://example.com",
      "_source_attribution": {
        "property_id": "123456",
        "property_name": "Main Website",
        "data_freshness": "2024-01-31T10:00:00Z"
      }
    },
    {
      "pagePath": "/about",
      "screenPageViews": 500,
      "totalAdRevenue": 12.75,
      "property_id": "789012",
      "property_name": "Blog Site",
      "property_url": "https://blog.example.com",
      "_source_attribution": {
        "property_id": "789012",
        "property_name": "Blog Site",
        "data_freshness": "2024-01-31T09:45:00Z"
      }
    }
  ],
  "summary": {
    "total_rows": 2,
    "properties_queried": 2,
    "properties_successful": 2,
    "properties_failed": 1,
    "aggregated_metrics": {
      "total_screenPageViews": 1500,
      "total_totalAdRevenue": 38.25
    }
  },
  "property_metadata": [
    {
      "property_id": "123456",
      "property_name": "Main Website",
      "property_url": "https://example.com",
      "account_name": "Example Company",
      "rows_contributed": 1,
      "data_range_coverage": "complete"
    },
    {
      "property_id": "789012",
      "property_name": "Blog Site", 
      "property_url": "https://blog.example.com",
      "account_name": "Example Company",
      "rows_contributed": 1,
      "data_range_coverage": "complete"
    }
  ],
  "row_count": 2,
  "source": "ga4",
  "request_id": "abc12345",
  "duration_seconds": 2.34,
  "todays_date": "2024-02-01"
}
```

### Grouped Response Format

When `response_format = "grouped"`:

```json
{
  "status": "success",
  "response_format": "grouped",
  "properties": {
    "123456": {
      "property_metadata": {
        "property_id": "123456",
        "property_name": "Main Website",
        "property_url": "https://example.com"
      },
      "data": [
        {
          "pagePath": "/home",
          "screenPageViews": 1000,
          "totalAdRevenue": 25.50
        }
      ],
      "row_count": 1,
      "summary": {
        "total_screenPageViews": 1000,
        "total_totalAdRevenue": 25.50
      }
    },
    "789012": {
      "property_metadata": {
        "property_id": "789012",
        "property_name": "Blog Site",
        "property_url": "https://blog.example.com"
      },
      "data": [
        {
          "pagePath": "/about",
          "screenPageViews": 500,
          "totalAdRevenue": 12.75
        }
      ],
      "row_count": 1,
      "summary": {
        "total_screenPageViews": 500,
        "total_totalAdRevenue": 12.75
      }
    }
  },
  "overall_summary": {
    "total_properties": 2,
    "total_rows": 2,
    "aggregated_metrics": {
      "total_screenPageViews": 1500,
      "total_totalAdRevenue": 38.25
    }
  }
}
```

## Backward Compatibility Strategy

### Compatibility Matrix

| Parameter Usage | Before | After | Compatibility |
|----------------|--------|-------|---------------|
| `property_id=""` | Query all properties | Query all properties | ✅ Full |
| `property_id="123456"` | Query single property | Query single property | ✅ Full |
| `property_id="123,456"` | ❌ Invalid | Query multiple properties | ✅ New feature |
| `property_id=["123","456"]` | ❌ Type error | Query multiple properties | ✅ New feature |

### Migration Path

1. **Phase 1**: Deploy with backward compatibility
2. **Phase 2**: Add deprecation warnings for old usage patterns (if any)
3. **Phase 3**: Remove deprecated features (future release)

### Compatibility Testing

```python
# Test cases for backward compatibility
test_cases = [
    # Existing behavior preservation
    {"property_id": "", "expected": "query_all_properties"},
    {"property_id": "123456", "expected": "query_single_property"},
    
    # New functionality
    {"property_id": "123,456", "expected": "query_multiple_properties"},
    {"property_id": ["123", "456"], "expected": "query_multiple_properties"},
]
```

## Performance Considerations

### Performance Optimization Strategies

1. **Concurrent Querying**
   ```python
   # Parallel property queries
   async def query_multiple_properties_concurrent(property_ids: List[str]):
       tasks = [query_single_property(pid) for pid in property_ids]
       results = await asyncio.gather(*tasks, return_exceptions=True)
       return results
   ```

2. **Property Validation Caching**
   ```python
   # Cache property access validation
   @lru_cache(maxsize=1000, ttl=3600)  # 1 hour cache
   def validate_property_access(auth_id: str, property_id: str) -> bool:
       # Expensive validation logic
       pass
   ```

3. **Batch Size Limits**
   ```python
   MAX_PROPERTIES_PER_REQUEST = 20  # Prevent resource exhaustion
   MAX_DOMAINS_PER_REQUEST = 15     # Prevent timeout issues
   ```

4. **Smart Aggregation**
   ```python
   # Memory-efficient data combination
   def stream_aggregate_results(property_results: Iterator[DataFrame]) -> DataFrame:
       # Process results in chunks to manage memory
       pass
   ```

### Performance Benchmarks

| Scenario | Current Time | Target Time | Max Properties |
|----------|--------------|-------------|----------------|
| Single property | 1.2s | 1.2s | 1 |
| All properties (10) | 8.5s | 8.5s | 10 |
| Specific 3 properties | N/A | 3.5s | 3 |
| Specific 5 properties | N/A | 5.8s | 5 |
| Max batch (20 properties) | N/A | 15.0s | 20 |

### Resource Management

```python
# Resource limits and monitoring
class ResourceLimits:
    MAX_CONCURRENT_PROPERTIES = 10
    MAX_MEMORY_PER_REQUEST = "500MB"
    REQUEST_TIMEOUT = 30  # seconds
    PROPERTY_TIMEOUT = 10  # seconds per property
```

## Error Handling Strategy

### Error Categories

1. **Input Validation Errors**
   - Invalid property ID format
   - Inaccessible properties
   - Exceeded batch limits

2. **Runtime Errors**
   - Property query failures
   - Network timeouts
   - Rate limiting

3. **Partial Failure Scenarios**
   - Some properties succeed, others fail
   - Mixed access permissions
   - Inconsistent data availability

### Error Response Format

```json
{
  "status": "partial_success",
  "message": "Retrieved data from 2 of 3 requested properties",
  "successful_properties": ["123456", "789012"],
  "failed_properties": [
    {
      "property_id": "345678",
      "error_type": "access_denied",
      "error_message": "Insufficient permissions for property 345678",
      "suggestion": "Check property permissions in Google Analytics",
      "retry_recommended": false
    }
  ],
  "data": [...],  // Data from successful properties
  "warnings": [
    "Property 345678 was skipped due to access issues"
  ]
}
```

### Error Handling Decision Tree

```
Input Validation
├── Valid property IDs?
│   ├── No → Return validation error
│   └── Yes → Continue
├── Within batch limits?
│   ├── No → Return batch limit error
│   └── Yes → Continue
└── Properties accessible?
    ├── None → Return access error
    ├── Some → Continue with partial
    └── All → Continue with full

Query Execution
├── All properties succeed?
│   └── Yes → Return success
├── Some properties succeed?
│   └── Yes → Return partial_success
└── No properties succeed?
    └── Return error
```

## Testing Strategy

### Test Categories

1. **Unit Tests**
   - Parameter parsing logic
   - Data aggregation functions
   - Error handling routines

2. **Integration Tests**
   - End-to-end multi-property queries
   - Authentication with multiple properties
   - Error scenario testing

3. **Performance Tests**
   - Concurrent query performance
   - Memory usage under load
   - Timeout handling

4. **Compatibility Tests**
   - Backward compatibility validation
   - API contract preservation
   - Response format consistency

### Test Data Setup

```python
# Test property configuration
TEST_PROPERTIES = {
    "valid_accessible": ["123456", "789012"],
    "valid_inaccessible": ["345678"],
    "invalid_format": ["invalid-id", ""],
    "non_existent": ["999999"]
}

# Test scenarios
test_scenarios = [
    {
        "name": "single_property_backward_compat",
        "property_id": "123456",
        "expected_status": "success"
    },
    {
        "name": "multiple_properties_success",
        "property_id": ["123456", "789012"],
        "expected_status": "success"
    },
    {
        "name": "partial_success_scenario",
        "property_id": ["123456", "345678"],  # One accessible, one not
        "expected_status": "partial_success"
    },
    {
        "name": "all_properties_inaccessible",
        "property_id": ["345678", "999999"],
        "expected_status": "error"
    }
]
```

### Automated Testing Pipeline

```yaml
# CI/CD Test Pipeline
testing_stages:
  - unit_tests:
      - parameter_parsing
      - data_aggregation
      - error_handling
  
  - integration_tests:
      - multi_property_queries
      - authentication_flows
      - error_scenarios
  
  - performance_tests:
      - concurrent_query_performance
      - memory_usage_validation
      - timeout_handling
  
  - compatibility_tests:
      - backward_compatibility
      - api_contract_validation
      - response_format_consistency
```

## Implementation Phases

### Phase 1: Core Infrastructure (4 weeks)

**Deliverables:**
- Enhanced parameter parsing logic
- Multi-property query orchestration
- Basic error handling framework
- Unit test coverage (>90%)

**Key Components:**
- `parse_multi_input()` function
- `validate_properties()` function
- `query_multiple_properties_async()` function
- Enhanced response formatting

### Phase 2: Advanced Features (3 weeks)

**Deliverables:**
- Grouped response format
- Property metadata enhancement
- Performance optimizations
- Integration test suite

**Key Components:**
- Response format selection
- Concurrent querying implementation
- Memory optimization
- Comprehensive error scenarios

### Phase 3: Production Readiness (2 weeks)

**Deliverables:**
- Performance testing and optimization
- Documentation updates
- Monitoring and observability
- Deployment preparation

**Key Components:**
- Load testing results
- Performance benchmarks
- Monitoring dashboards
- Deployment scripts

### Phase 4: Rollout and Monitoring (1 week)

**Deliverables:**
- Gradual deployment
- Real-world validation
- User feedback collection
- Bug fixes and optimizations

**Key Components:**
- Phased rollout plan
- Monitoring alerts
- User feedback channels
- Performance metrics

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Performance degradation** | Medium | High | Concurrent querying, batch limits, performance testing |
| **Memory exhaustion** | Low | High | Memory limits, streaming aggregation, monitoring |
| **Backward compatibility breaks** | Low | High | Comprehensive compatibility testing, gradual rollout |
| **API rate limiting** | Medium | Medium | Request throttling, retry logic, batch optimization |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **User workflow disruption** | Low | Medium | Backward compatibility, gradual migration |
| **Increased support burden** | Medium | Low | Comprehensive documentation, clear error messages |
| **Development timeline overrun** | Medium | Medium | Phased approach, regular checkpoints, scope flexibility |

### Mitigation Strategies

1. **Performance Risks**
   - Implement comprehensive performance testing
   - Set conservative batch limits initially
   - Monitor resource usage in production

2. **Compatibility Risks**
   - Maintain existing API contracts
   - Extensive automated testing
   - Feature flags for gradual rollout

3. **Operational Risks**
   - Enhanced error messages and debugging
   - Comprehensive monitoring and alerting
   - Rollback procedures for quick recovery

## Success Metrics

### Technical Metrics

1. **Performance Metrics**
   - Response time for multi-property queries < 10s for 5 properties
   - Memory usage increase < 20% compared to current implementation
   - Success rate > 99% for valid property queries

2. **Quality Metrics**
   - Test coverage > 95%
   - Zero backward compatibility breaks
   - Error rate < 1% for valid inputs

3. **Usability Metrics**
   - Clear error messages for invalid inputs
   - Comprehensive source attribution in results
   - Intuitive parameter formats

### Business Metrics

1. **Efficiency Gains**
   - Reduce API calls by 70% for multi-property use cases
   - Improve query flexibility for enterprise users
   - Enable new analytical workflows

2. **User Adoption**
   - Track usage of multi-property features
   - Monitor user feedback and satisfaction
   - Measure reduction in support requests

3. **System Health**
   - Maintain current system reliability
   - No increase in error rates
   - Stable memory and CPU usage

### Measurement Plan

```python
# Metrics collection framework
metrics_to_track = {
    "performance": {
        "multi_property_response_time": "histogram",
        "memory_usage_per_request": "gauge", 
        "concurrent_query_success_rate": "counter"
    },
    "usage": {
        "multi_property_requests": "counter",
        "properties_per_request": "histogram",
        "response_format_usage": "counter"
    },
    "quality": {
        "error_rate_by_type": "counter",
        "partial_success_rate": "counter",
        "user_satisfaction_score": "gauge"
    }
}
```

## Conclusion

The proposed multi-property upgrade will significantly enhance the capabilities of the MCP server, enabling more efficient and flexible analytics workflows. The hybrid string/array approach provides an optimal balance of backward compatibility, usability, and functionality.

Key benefits include:
- **70-90% reduction** in API calls for subset queries
- **Enhanced data attribution** for multi-property analysis
- **Backward compatibility** preservation
- **Scalable architecture** supporting future enhancements

The phased implementation approach ensures minimal risk while delivering maximum value to users managing multiple GA4 properties and GSC domains.

---

**Document Version**: 1.0  
**Last Updated**: 2024-01-31  
**Review Date**: 2024-02-28  
**Status**: Draft for Review