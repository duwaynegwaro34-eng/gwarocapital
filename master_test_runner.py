#!/usr/bin/env python3
"""Master test runner - execute all tests with comprehensive reporting"""

import os
import sys
import unittest
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def run_all_tests():
    """Run all tests and generate comprehensive report"""
    
    print("=" * 80)
    print("GWARO CAPITAL - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print(f"Start time: {datetime.now().isoformat()}\n")
    
    # Discover and run all tests
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Generate summary report
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests run: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    # Detailed failure information
    if result.failures:
        print("\n" + "-" * 80)
        print("FAILURES:")
        print("-" * 80)
        for i, (test, trace) in enumerate(result.failures, 1):
            print(f"\n{i}. {test}:")
            print(trace)
    
    if result.errors:
        print("\n" + "-" * 80)
        print("ERRORS:")
        print("-" * 80)
        for i, (test, trace) in enumerate(result.errors, 1):
            print(f"\n{i}. {test}:")
            print(trace)
    
    # Success indicator
    print("\n" + "=" * 80)
    if result.wasSuccessful():
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED - See details above")
    print("=" * 80)
    print(f"End time: {datetime.now().isoformat()}\n")
    
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)
