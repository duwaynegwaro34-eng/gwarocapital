#!/usr/bin/env python3
"""
Generate a detailed list of all changes for the MT5 Bridge production deployment.
This helps verify that all necessary files are staged before commit.
"""
import os
from pathlib import Path

def check_file_exists(path):
    """Check if a file exists and return a status indicator."""
    full_path = Path(path)
    exists = full_path.exists()
    size = full_path.stat().st_size if exists else 0
    return "✓" if exists else "✗", size

files_to_commit = {
    "Core Bridge Implementation": [
        "services/mt5_bridge_client.py",
        "services/standalone_mt5_bridge.py",
    ],
    "Integration Updates": [
        "app.py",
        "mt5_manager.py",
        "config.py",
    ],
    "Testing & Verification": [
        "tests/test_mt5_bridge_client.py",
        "tests/test_mt5_connect_api.py",
        "tests/test_mt5.py",
        "tests/test_bot_manager_api.py",
        "tests/test_dynamic_bot_discovery.py",
        "verify_mt5_tests.py",
        "run_mt5_tests.py",
    ],
    "Deployment Scripts": [
        "start_mt5_bridge.bat",
        "deploy_mt5_bridge.ps1",
    ],
    "Documentation": [
        "DEPLOYMENT_SUMMARY.md",
        "README_DEPLOY.md",
        "docs/mt5_bridge_production.md",
        "docs/mt5_bridge_service.md",
    ],
}

print("=" * 70)
print("MT5 BRIDGE PRODUCTION DEPLOYMENT - FILE CHECKLIST")
print("=" * 70)

total_size = 0
total_files = 0

for category, files in files_to_commit.items():
    print(f"\n{category}:")
    print("-" * 70)
    
    for filepath in files:
        status, size = check_file_exists(filepath)
        total_files += 1
        total_size += size
        size_kb = size / 1024 if size > 0 else 0
        print(f"  {status} {filepath:<45} ({size_kb:>7.1f} KB)")

print("\n" + "=" * 70)
print(f"Total Files: {total_files} | Total Size: {total_size / 1024:.1f} KB")
print("=" * 70)

print("\nGit Commit Instructions:")
print("-" * 70)
print("""
1. Stage all changes:
   git add -A

2. Review staged changes:
   git status

3. Commit with descriptive message:
   git commit -m "Implement production MT5 Bridge service with API key auth, retries, and multi-session support"

4. Verify commit:
   git log --oneline -1

5. Push to GitHub:
   git push origin main

6. Monitor Render deployment:
   - Check Render dashboard for redeploy trigger
   - Verify deployment logs
   - Test /api/mt5/status endpoint on deployed site
""")
