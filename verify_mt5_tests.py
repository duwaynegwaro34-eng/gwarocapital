#!/usr/bin/env python3
"""
Minimal MT5 test verification - checks if tests can import and run without errors.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("Step 1: Testing bridge client imports...")
try:
    from services.mt5_bridge_client import MT5BridgeClient
    print("  ✓ MT5BridgeClient imported successfully")
except Exception as e:
    print(f"  ✗ Failed to import MT5BridgeClient: {e}")
    sys.exit(1)

print("\nStep 2: Testing MT5Manager imports...")
try:
    from mt5_manager import MT5Manager
    print("  ✓ MT5Manager imported successfully")
except Exception as e:
    print(f"  ✗ Failed to import MT5Manager: {e}")
    sys.exit(1)

print("\nStep 3: Testing Flask app imports...")
try:
    import app as app_module
    print("  ✓ Flask app imported successfully")
except Exception as e:
    print(f"  ✗ Failed to import Flask app: {e}")
    sys.exit(1)

print("\nStep 4: Testing Flask test client creation...")
try:
    app_module.app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SECRET_KEY="test-secret",
    )
    client = app_module.app.test_client()
    print("  ✓ Flask test client created successfully")
except Exception as e:
    print(f"  ✗ Failed to create Flask test client: {e}")
    sys.exit(1)

print("\nStep 5: Testing /api/mt5/status endpoint...")
try:
    response = client.get("/api/mt5/status")
    payload = response.get_json()
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "connected" in payload, "Missing 'connected' field"
    assert "status" in payload, "Missing 'status' field"
    print(f"  ✓ /api/mt5/status endpoint works: {payload}")
except Exception as e:
    print(f"  ✗ /api/mt5/status endpoint failed: {e}")
    sys.exit(1)

print("\nStep 6: Testing /api/mt5/account endpoint...")
try:
    response = client.get("/api/mt5/account")
    payload = response.get_json()
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "connected" in payload, "Missing 'connected' field"
    assert "status" in payload, "Missing 'status' field"
    print(f"  ✓ /api/mt5/account endpoint works: connected={payload.get('connected')}")
except Exception as e:
    print(f"  ✗ /api/mt5/account endpoint failed: {e}")
    sys.exit(1)

print("\nStep 7: Testing /api/mt5/connect POST endpoint...")
try:
    response = client.post("/api/mt5/connect", json={"login": "", "password": "", "server": ""})
    payload = response.get_json()
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "ok" in payload, "Missing 'ok' field"
    print(f"  ✓ /api/mt5/connect endpoint works: ok={payload.get('ok')}")
except Exception as e:
    print(f"  ✗ /api/mt5/connect endpoint failed: {e}")
    sys.exit(1)

print("\n" + "="*70)
print("ALL VERIFICATION CHECKS PASSED!")
print("="*70)
