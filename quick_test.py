#!/usr/bin/env python3
"""Quick test to verify basic functionality"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Test imports
try:
    import app as app_module
    print("✓ app.py imports successfully")
except Exception as e:
    print(f"✗ app.py import failed: {e}")
    sys.exit(1)

# Test config
try:
    from config import settings
    print(f"✓ config loads: debug={settings.debug}")
except Exception as e:
    print(f"✗ config failed: {e}")
    sys.exit(1)

# Test database creation
try:
    with app_module.app.app_context():
        app_module.db.create_all()
        print("✓ Database created")
except Exception as e:
    print(f"✗ Database creation failed: {e}")
    sys.exit(1)

# Test basic app creation
try:
    client = app_module.app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    print(f"✓ Home page loads (status {response.status_code})")
except Exception as e:
    print(f"✗ Home page failed: {e}")
    sys.exit(1)

# Test login page
try:
    response = client.get("/login")
    assert response.status_code == 200 or response.status_code == 302
    print(f"✓ Login page accessible (status {response.status_code})")
except Exception as e:
    print(f"✗ Login page failed: {e}")
    sys.exit(1)

print("\n✓ All quick tests passed!")
