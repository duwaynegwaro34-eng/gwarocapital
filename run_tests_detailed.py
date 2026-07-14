#!/usr/bin/env python3
"""Comprehensive test runner with detailed output logging"""

import sys
import os
import unittest
import logging

# Configure logging
logging.basicConfig(
    filename='test_execution.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def run_tests():
    """Run all tests and log results"""
    
    try:
        logging.info("Starting test discovery...")
        
        # Discover tests
        loader = unittest.TestLoader()
        suite = loader.discover('tests', pattern='test_*.py')
        
        # Run tests with detailed reporting
        logging.info(f"Running {suite.countTestCases()} tests...")
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Log results
        logging.info(f"Tests completed: {result.testsRun} run")
        logging.info(f"Failures: {len(result.failures)}")
        logging.info(f"Errors: {len(result.errors)}")
        logging.info(f"Skipped: {len(result.skipped)}")
        
        # Log individual failures
        if result.failures:
            logging.info("\n=== FAILURES ===")
            for test, trace in result.failures:
                logging.error(f"\nFAILED: {test}")
                logging.error(trace)
        
        # Log individual errors
        if result.errors:
            logging.info("\n=== ERRORS ===")
            for test, trace in result.errors:
                logging.error(f"\nERROR: {test}")
                logging.error(trace)
        
        return 0 if result.wasSuccessful() else 1
        
    except Exception as e:
        logging.exception(f"Test execution failed: {e}")
        return 1

if __name__ == '__main__':
    exit_code = run_tests()
    logging.info(f"Exiting with code {exit_code}")
    
    # Also print summary to console
    print(f"Tests completed. Check test_execution.log for details.")
    sys.exit(exit_code)
