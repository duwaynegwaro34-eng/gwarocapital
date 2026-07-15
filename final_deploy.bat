@echo off
REM Simplified MT5 Bridge Git Deployment
REM Run this from the gwaro-capital directory

echo Checking git repository status...
git status

echo.
echo Staging all changes...
git add .

echo.
echo Creating commit...
git commit -m "Implement production MT5 Bridge service with API key auth, retries, and multi-session support"

echo.
echo Pushing to GitHub...
git push origin main

echo.
echo Done! Check Render dashboard for deployment trigger.
pause
