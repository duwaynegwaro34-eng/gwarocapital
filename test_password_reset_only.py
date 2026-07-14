#!/usr/bin/env python3
"""Run forgot password tests with detailed output"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the test class
from tests.test_forgot_password import ForgotPasswordTests

if __name__ == '__main__':
    # Create a test suite with just these tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add specific tests
    suite.addTest(ForgotPasswordTests('test_forgot_password_request_creates_token_and_sends_email'))
    suite.addTest(ForgotPasswordTests('test_verify_code_rejects_expired_code'))
    
    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    # Print details of any failures
    if result.failures:
        print("\n" + "="*70)
        print("FAILURES:")
        for test, trace in result.failures:
            print(f"\n{test}:")
            print(trace)
    
    # Print details of any errors
    if result.errors:
        print("\n" + "="*70)
        print("ERRORS:")
        for test, trace in result.errors:
            print(f"\n{test}:")
            print(trace)
    
    sys.exit(0 if result.wasSuccessful() else 1)
