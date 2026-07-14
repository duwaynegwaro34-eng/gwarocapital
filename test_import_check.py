#!/usr/bin/env python3
"""Test that app.py can be imported without MetaTrader5"""
import sys

try:
    import app as app_module
    print("✓ SUCCESS: app.py imported successfully")
    print(f"✓ Has mt5_manager: {hasattr(app_module, 'mt5_manager')}")
    print(f"✓ mt5_manager is configured: {app_module.mt5_manager is not None}")
    
    # Test the endpoints exist
    print(f"✓ Has test_mt5 route: {hasattr(app_module, 'test_mt5')}")
    print(f"✓ Has get_market_data function: {hasattr(app_module, 'get_market_data')}")
    print(f"✓ Has generate_signals function: {hasattr(app_module, 'generate_signals')}")
    
    sys.exit(0)
except Exception as e:
    print(f"✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
