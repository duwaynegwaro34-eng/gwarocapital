#!/usr/bin/env python3
"""
Run MT5 Bridge integration tests and report results.
"""
import sys
import unittest
import os

# Ensure the project is in the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Load MT5-specific tests
    test_modules = [
        "tests.test_mt5_bridge_client",
        "tests.test_mt5_connect_api",
        "tests.test_mt5",
        "tests.test_bot_manager_api",
        "tests.test_dynamic_bot_discovery",
    ]
    
    for module in test_modules:
        try:
            suite.addTests(loader.loadTestsFromName(module))
        except Exception as e:
            print(f"Warning: Could not load {module}: {e}")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"\n{test}:")
            print(traceback)
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"\n{test}:")
            print(traceback)
    
    sys.exit(0 if result.wasSuccessful() else 1)
