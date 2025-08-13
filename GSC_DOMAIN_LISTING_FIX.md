# GSC Domain Listing Fix - Issue #48

## Problem Summary
The webapp was unable to list GSC (Google Search Console) domains when users selected "Google Search Console" from the interface. The error shown was:

```
Error processing account : Could not find Google client secrets file 'client_secrets.json'. This may be due to an invalid or missing 'auth_identifier' or secrets file. Checked: 'client_secrets.json' and 'client_secrets.json'
```

However, the CLI command `uv run .\NewDownloads.py --list-domains` worked perfectly, demonstrating that the authentication and API access were configured correctly.

## Root Cause Analysis
The issue was caused by incorrect path resolution in the webapp environment:

1. **Working Directory Change**: `webfrontend.py` changes the working directory to `webapp/backend` (line 104)
2. **Hardcoded Paths**: The GSC provider was using hardcoded `'client_secrets.json'` paths
3. **Path Resolution Failure**: When running from `webapp/backend`, the relative path `client_secrets.json` looked for the file in the wrong location

## Solution Implemented

### 1. GSC Provider Fix (`webapp/backend/data_providers/gsc_provider.py`)
- **Environment Variable Support**: Now reads `CLIENT_SECRETS_PATH` environment variable set by `webfrontend.py`
- **Intelligent Path Resolution**: Converts relative paths to absolute paths relative to repository root
- **Enhanced Logging**: Added detailed logging to track path resolution and authentication steps

### 2. NewDownloads.py Improvements
- **Helper Function**: Added `get_client_secrets_path()` function for consistent path resolution
- **Environment Variable Integration**: Supports both CLI usage (default path) and webapp usage (environment variable)
- **Updated References**: All hardcoded `'client_secrets.json'` references now use the helper function

### 3. Enhanced Logging Throughout
- Detailed logging shows exactly which client secrets file is being used
- Better error reporting with stack traces for troubleshooting
- Clear indication of path resolution process

## Code Changes Made

### GSC Provider Changes
```python
# Before (hardcoded path)
service = get_service('webmasters', 'v3', scope, 'client_secrets.json', auth_identifier)

# After (environment-aware path resolution)
client_secrets_path = os.environ.get('CLIENT_SECRETS_PATH', 'client_secrets.json')
if not os.path.isabs(client_secrets_path):
    repo_root = Path(__file__).parent.parent.parent.parent
    client_secrets_path = str(repo_root / client_secrets_path)
logger.info(f"GSC Provider: Using resolved client secrets path: {client_secrets_path}")
service = get_service('webmasters', 'v3', scope, client_secrets_path, auth_identifier)
```

### NewDownloads.py Helper Function
```python
def get_client_secrets_path(default_path='client_secrets.json'):
    """
    Get the resolved path to client_secrets.json, checking environment variables and making paths absolute.
    This ensures consistent path resolution between CLI and webapp usage.
    """
    client_secrets_path = os.environ.get('CLIENT_SECRETS_PATH', default_path)
    
    if not os.path.isabs(client_secrets_path):
        script_dir = Path(__file__).parent
        client_secrets_path = str(script_dir / client_secrets_path)
    
    return client_secrets_path
```

## Testing and Verification

The fix has been tested to ensure:

1. ✅ **CLI Functionality Preserved**: `NewDownloads.py --list-domains` continues to work as before
2. ✅ **Webapp Path Resolution**: Webapp now correctly finds `client_secrets.json` regardless of working directory
3. ✅ **Environment Variable Support**: `CLIENT_SECRETS_PATH` is properly read and used
4. ✅ **Enhanced Logging**: Better troubleshooting information is now available

## Impact

### Before the Fix
- ❌ Webapp: "Could not find Google client secrets file"
- ✅ CLI: Worked correctly

### After the Fix
- ✅ Webapp: Correctly finds and uses client secrets file
- ✅ CLI: Continues to work as before
- ✅ Better logging and error messages for troubleshooting

## How to Test the Fix

1. **Start the webapp**: `uv run webfrontend.py`
2. **Access the web interface**: Navigate to `http://127.0.0.1:8000`
3. **Select Google Search Console**: The domain list should now populate correctly
4. **Check logs**: Enhanced logging will show the path resolution process

## Additional Benefits

1. **Consistent Path Handling**: Both CLI and webapp now use the same path resolution logic
2. **Environment Variable Support**: Makes deployment and configuration more flexible
3. **Better Debugging**: Enhanced logging helps troubleshoot authentication issues
4. **Future-Proof**: The solution works regardless of working directory changes

This fix resolves the core issue while maintaining backward compatibility and improving the overall robustness of the authentication system.