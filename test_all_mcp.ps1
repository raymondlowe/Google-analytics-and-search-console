# PowerShell script to install Node.js/npm, run Python tests and remote MCP client tests

# 1. Install Node.js LTS (includes npm and npx)
Write-Host "Installing Node.js LTS via winget..."
winget install --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements --silent

# 2. Refresh environment variables (requires PackageManagement/Developer PowerShell tools)
Write-Host "Refreshing environment variables..."
if (Get-Command RefreshEnv -ErrorAction SilentlyContinue) {
    RefreshEnv
} else {
    Write-Host "RefreshEnv not available; please open a new shell to pick up Node.js path."
}

# Ensure Node.js installation directory is in PATH (for this session)
$nodeDefaultPath = 'C:\Program Files\nodejs'
if (Test-Path $nodeDefaultPath) {
    Write-Host "Adding Node.js to PATH: $nodeDefaultPath"
    $env:Path = "$nodeDefaultPath;$env:Path"
}

# 3. Verify Node, npm and npx versions
Write-Host "Node.js version:"; node --version
Write-Host "npm version:"; npm --version
Write-Host "npx version:"; npx --version

# 4. Activate Python virtual environment
Write-Host "Activating Python venv..."
. .\.venv\Scripts\Activate

# 5. Run basic STDIO Python test
Write-Host "\n=== RUNNING BASIC MCP CLIENT TEST (STDIO MODE) ==="
uv run test_mcp_client.py

# 6. Start HTTP MCP server in background
Write-Host "`n=== STARTING HTTP MCP SERVER ON PORT 8000 ==="
# Capture logs to extract API key
$outLog = Join-Path $PSScriptRoot 'mcp_server.out.log'
$errLog = Join-Path $PSScriptRoot 'mcp_server.err.log'
foreach ($f in @($outLog, $errLog)) {
    if (Test-Path $f) { Remove-Item $f }
}
# Start HTTP MCP server in background and redirect logs
$serverProc = Start-Process uv -ArgumentList 'run mcp_server.py --http --host 127.0.0.1 --port 8000' -RedirectStandardOutput $outLog -RedirectStandardError $errLog -WorkingDirectory $PSScriptRoot -NoNewWindow -PassThru
# Wait for server startup
Start-Sleep -Seconds 5

# Extract Bearer token from logs
Write-Host "Extracting bearer token from server logs..."
$logContent = ""
if (Test-Path $outLog) { $logContent += Get-Content $outLog -Raw }
if (Test-Path $errLog) { $logContent += "`n" + (Get-Content $errLog -Raw) }
$tokenMatch = [Regex]::Match($logContent, 'Authorization":\s*"Bearer\s*(?<token>[^\"]+)"')
if ($tokenMatch.Success) {
    $token = $tokenMatch.Groups['token'].Value
    Write-Host "Found Bearer token: $token"
} else {
    Write-Error "Bearer token not found in server log. Exiting."
    $serverProc | Stop-Process -Force
    exit 1
}

# 7. Test remote MCP client inspect
Write-Host "\n=== RUNNING REMOTE MCP CLIENT INSPECT ==="
npx @raymondlowe/mcp-client inspect --type http --url http://127.0.0.1:8000/mcp --bearer $token

# 8. Test remote MCP client simple tool call
Write-Host "\n=== RUNNING REMOTE TOOL CALL: list_gsc_domains ==="
npx @raymondlowe/mcp-client --type http --url http://127.0.0.1:8000/mcp --bearer $token --tool list_gsc_domains --fields "debug=true"

# 9. Stop HTTP server
Write-Host "\n=== STOPPING HTTP MCP SERVER ==="
$serverProc | Stop-Process -Force

Write-Host "All tests complete."
