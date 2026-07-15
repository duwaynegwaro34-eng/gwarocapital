# MT5 Bridge Deployment Script
# Run from gwaro-capital directory

$ErrorActionPreference = "Stop"

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "MT5 Bridge Production Deployment" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

# Check git availability
try {
    $gitVersion = git --version
    Write-Host "[✓] Git available: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "[✗] Git not found" -ForegroundColor Red
    exit 1
}

# Stage changes
Write-Host "`n[1/4] Staging all changes..." -ForegroundColor Yellow
git add -A
Write-Host "[✓] Staged" -ForegroundColor Green

# Show status
Write-Host "`n[2/4] Current status:" -ForegroundColor Yellow
git status --short

# Commit
Write-Host "`n[3/4] Creating commit..." -ForegroundColor Yellow
try {
    $output = git commit -m "Implement production MT5 Bridge service with API key auth, retries, and multi-session support" 2>&1
    Write-Host $output -ForegroundColor Green
} catch {
    Write-Host "[!] Note: May have no new changes to commit" -ForegroundColor Yellow
}

# Push
Write-Host "`n[4/4] Pushing to GitHub..." -ForegroundColor Yellow
git push origin main

# Verify
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Latest Commit:" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green
git log --oneline -1

Write-Host "`nDeployment Instructions:" -ForegroundColor Cyan
Write-Host "1. Configure Render environment variables:"
Write-Host "   - MT5_BRIDGE_URL=http://<windows-host-ip>:5001"
Write-Host "   - MT5_BRIDGE_API_KEY=<secure-key>"
Write-Host "`n2. Trigger Render redeploy from dashboard"
Write-Host "`n3. Start Windows bridge service:"
Write-Host "   - python services/standalone_mt5_bridge.py"
Write-Host "`n4. Test connectivity:"
Write-Host "   - curl https://gwaro-capital.com/api/mt5/status`n"

Read-Host "Press Enter to exit"
