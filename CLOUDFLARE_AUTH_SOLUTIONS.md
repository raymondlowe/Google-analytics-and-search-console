# MCP Server Authentication Solutions for Cloudflare Tunnel

## Problem
Cloudflare tunnels can strip `Authorization` headers due to CORS preflight requests, causing authentication failures when connecting remotely.

## Solutions

### 1. Standard Configuration (works locally)
```json
{
  "mcpServers": {
    "ga4-gsc-mcp": {
      "type": "http",
      "url": "https://mcp2.wlmedia.com/mcp",
      "headers": {
        "Authorization": "Bearer mypassword"
      },
      "tools": ["..."]
    }
  }
}
```

### 2. Custom Header Workaround (for Cloudflare tunnel)
If Authorization headers are being stripped, try using custom headers:

```json
{
  "mcpServers": {
    "ga4-gsc-mcp": {
      "type": "http", 
      "url": "https://mcp2.wlmedia.com/mcp",
      "headers": {
        "X-API-Key": "mypassword"
      },
      "tools": ["..."]
    }
  }
}
```

Or:

```json
{
  "mcpServers": {
    "ga4-gsc-mcp": {
      "type": "http",
      "url": "https://mcp2.wlmedia.com/mcp", 
      "headers": {
        "X-Auth-Token": "mypassword"
      },
      "tools": ["..."]
    }
  }
}
```

### 3. URL Parameter Fallback (always works)
```json
{
  "mcpServers": {
    "ga4-gsc-mcp": {
      "type": "http",
      "url": "https://mcp2.wlmedia.com/mcp?key=mypassword",
      "tools": ["..."]
    }
  }
}
```

## Cloudflare Tunnel Configuration

To preserve Authorization headers, update your `cloudflared.yml`:

```yaml
tunnel: your-tunnel-id
credentials-file: /path/to/credentials.json

ingress:
  - hostname: mcp2.wlmedia.com
    service: http://localhost:8080
    originRequest:
      httpHostHeader: "localhost:8080"
      connectTimeout: 30s
      tlsTimeout: 10s
      tcpKeepAlive: 30s
      keepAliveConnections: 100
      keepAliveTimeout: 90s
  - service: http_status:404
```

## Testing

1. **Test locally first** - ensure header auth works with `http://localhost:8080`
2. **Test remote with custom headers** - try `X-API-Key` or `X-Auth-Token`
3. **Fallback to URL parameters** - guaranteed to work but less secure

## Debug Commands

```bash
# Test local server
uv run test_auth_debug.py http://localhost:8080 mypassword

# Test remote tunnel
uv run test_auth_debug.py https://mcp2.wlmedia.com mypassword test_both
```

The enhanced server now:
- ✅ Handles CORS preflight requests
- ✅ Supports custom header authentication  
- ✅ Preserves URL parameter fallback
- ✅ Provides detailed logging for debugging
