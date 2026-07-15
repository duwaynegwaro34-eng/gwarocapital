@echo off
REM MT5 Bridge Production Deployment Script
REM This script stages, commits, and pushes all MT5 Bridge changes to GitHub

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ========================================
echo MT5 Bridge Production Deployment
echo ========================================
echo.

REM Check if git is available
where git >nul 2>nul
if errorlevel 1 (
    echo ERROR: git is not installed or not in PATH
    exit /b 1
)

REM Stage all changes
echo [1/4] Staging all changes...
git add -A
if errorlevel 1 (
    echo ERROR: Failed to stage changes
    exit /b 1
)
echo       ✓ All changes staged

REM Show status
echo.
echo [2/4] Checking git status...
git status --short
echo.

REM Commit changes
echo [3/4] Committing changes...
git commit -m "Implement production MT5 Bridge service with API key auth, retries, and multi-session support"
if errorlevel 1 (
    echo ERROR: Failed to commit changes (no changes to commit or other error)
    REM Don't fail - this might be expected if nothing changed
)
echo       ✓ Changes committed

REM Push to GitHub
echo.
echo [4/4] Pushing to GitHub...
git push origin main
if errorlevel 1 (
    echo WARNING: Failed to push to GitHub
    echo Please check your network connection and git credentials
    exit /b 1
)
echo       ✓ Pushed to GitHub

REM Show latest commit
echo.
echo ========================================
echo Deployment Complete!
echo ========================================
echo.
git log --oneline -1
echo.
echo Next Steps:
echo 1. Monitor Render deployment dashboard
echo 2. Verify website reaches MT5 Bridge
echo 3. Test /api/mt5/status endpoint
echo.
echo Configure Render environment variables:
echo   MT5_BRIDGE_URL=http://^<windows-host-ip^>:5001
echo   MT5_BRIDGE_API_KEY=^<secure-key^>
echo.

pause
