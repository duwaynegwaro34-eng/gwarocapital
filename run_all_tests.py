#!/usr/bin/env python3
import sys
import unittest
import io
from contextlib import redirect_stdout, redirect_stderr

# Discover and run all tests
loader = unittest.TestLoader()
suite = loader.discover('tests', pattern='test_*.py')

# Capture output
output = io.StringIO()
errors_output = io.StringIO()

with redirect_stdout(output), redirect_stderr(errors_output):
    runner = unittest.TextTestRunner(stream=output, verbosity=2)
    result = runner.run(suite)

# Write results to file
with open('test_results_detailed.txt', 'w', encoding='utf-8') as f:
    f.write("=== TEST OUTPUT ===\n")
    f.write(output.getvalue())
    f.write("\n\n=== STDERR ===\n")
    f.write(errors_output.getvalue())
    f.write("\n\n=== SUMMARY ===\n")
    f.write(f"Tests run: {result.testsRun}\n")
    f.write(f"Failures: {len(result.failures)}\n")
    f.write(f"Errors: {len(result.errors)}\n")
    f.write(f"Skipped: {len(result.skipped)}\n")
    
    if result.failures:
        f.write("\n=== FAILURES ===\n")
        for test, traceback in result.failures:
            f.write(f"\n{test}:\n{traceback}\n")
    
    if result.errors:
        f.write("\n=== ERRORS ===\n")
        for test, traceback in result.errors:
            f.write(f"\n{test}:\n{traceback}\n")

# Also print summary to console
print(f"Tests run: {result.testsRun}")
print(f"Failures: {len(result.failures)}")
print(f"Errors: {len(result.errors)}")
print(f"Results saved to test_results_detailed.txt")
sys.exit(0 if result.wasSuccessful() else 1)
