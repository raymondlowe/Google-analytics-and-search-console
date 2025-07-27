# MCP Server Authentication Guide

This document explains the authentication methods available for the MCP server and their security implications.

## Authentication Methods

The MCP server supports two authentication methods for API key verification:

### 1. Authorization Header (Recommended) 🔒

**Method**: HTTP Authorization header with Bearer token
**Format**: `Authorization: Bearer <your-api-key>`
**Security**: ✅ High - Keys are not logged in standard access logs

```json
{
  "mcpServers": {
    "ga4-gsc-mcp": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer your-api-key-here"
      },
      "tools": ["query_ga4_data", "query_gsc_data", ...]
    }
  }
}
```

### 2. URL Parameter (Fallback) ⚠️

**Method**: URL query parameter
**Format**: `?key=<your-api-key>`
**Security**: ⚠️ Lower - Keys may be exposed in logs and browser history

```json
{
  "mcpServers": {
    "ga4-gsc-mcp": {
      "type": "http",
      "url": "http://localhost:8000/mcp?key=your-api-key-here",
      "tools": ["query_ga4_data", "query_gsc_data", ...]
    }
  }
}
```

## Security Considerations

### Why Header Authentication is Preferred

1. **Not logged**: Authorization headers are typically not included in standard access logs
2. **Not cached**: Headers are not cached by browsers or proxies
3. **Not in history**: Headers don't appear in browser history
4. **Not in referrers**: Headers are not sent in referrer headers to external sites

### Risks of URL Parameter Authentication

URL parameters containing API keys may be exposed in:

- ✗ **Server access logs** - Standard web server logs include full URLs
- ✗ **Browser history** - Users can see the key in their browser history
- ✗ **Proxy logs** - Corporate proxies and CDNs may log full URLs  
- ✗ **Referrer headers** - Keys may leak to external sites via referrer headers
- ✗ **Browser dev tools** - Keys are visible in network tabs
- ✗ **Shared URLs** - Users may accidentally share URLs containing keys

### When to Use URL Parameter Authentication

URL parameter authentication should only be used when:

1. Your MCP client cannot send custom headers
2. You understand and accept the security risks
3. You implement additional security measures:
   - Regularly rotate API keys
   - Monitor access logs for key exposure
   - Use HTTPS only
   - Limit key permissions/scopes

## Authentication Precedence

If both authentication methods are provided, the server uses this precedence:

1. **Authorization header** (if present and valid)
2. **URL parameter** (if header missing and parameter present)

This ensures backwards compatibility while allowing graceful fallback.

## Implementation Details

The server middleware:

1. Checks for `Authorization: Bearer <token>` header first
2. Falls back to `?key=<token>` URL parameter if header is missing
3. Uses constant-time comparison to prevent timing attacks
4. Logs authentication method and security warnings
5. Returns detailed error messages for troubleshooting

## Best Practices

1. **Always use HTTPS** in production to encrypt all communications
2. **Prefer header authentication** whenever possible
3. **Rotate API keys regularly** especially if using URL parameters
4. **Monitor logs** for any unintended key exposure
5. **Use environment variables** to store keys, never hardcode them
6. **Implement key scoping** to limit permissions

## Example Usage

### Starting the Server

```bash
# With a specific key

uv run mcp_server.py --http --key your-secure-api-key

# Example: Using the official MCP client

To test your MCP server with the official client, use:

```
npx -y @raymondlowe/mcp-client --url http://127.0.0.1:8000/mcp --bearer your-secure-api-key --verbose
```

Replace `your-secure-api-key` with your actual API key. The correct flag is `--bearer` (not `--key`).

# With auto-generated key
uv run mcp_server.py --http
```

### Testing Authentication

```bash
# Test header auth (recommended)
curl -H "Authorization: Bearer your-key" http://localhost:8000/mcp

# Test URL parameter auth (fallback)
curl "http://localhost:8000/mcp?key=your-key"

# Both should return the same response (406 for GET requests is expected)
```

## Migration Guide

If you're currently using a client that only supports URL parameter authentication:

1. **Check if your client supports custom headers** - Many clients have been updated
2. **Update client configuration** to use Authorization headers if possible
3. **Keep URL parameter as backup** during transition period
4. **Monitor logs** to ensure header authentication is working
5. **Remove URL parameter** once header authentication is confirmed working