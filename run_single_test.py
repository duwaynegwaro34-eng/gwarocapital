#!/usr/bin/env python3
import sys
import unittest

if len(sys.argv) != 2:
    print('Usage: python run_single_test.py <test_identifier>')
    sys.exit(1)

test_id = sys.argv[1]
loader = unittest.TestLoader()
suite = loader.loadTestsFromName(test_id)
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)
print('\nRESULT:', 'OK' if result.wasSuccessful() else 'FAIL')
print('testsRun=', result.testsRun)
print('failures=', len(result.failures))
print('errors=', len(result.errors))
print('skipped=', len(result.skipped))
sys.exit(0 if result.wasSuccessful() else 1)
