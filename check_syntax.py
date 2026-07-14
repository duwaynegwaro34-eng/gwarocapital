#!/usr/bin/env python3
"""Check syntax of main application files"""
import py_compile
import sys

files_to_check = [
    'app.py',
    'config.py',
    'bot.py',
    'mt5_manager.py',
    'verify_auth.py',
    'services/bot_manager.py',
    'services/trading_engine.py',
    'services/payment_service.py',
    'services/backup_service.py',
]

errors = []
for filepath in files_to_check:
    try:
        py_compile.compile(filepath, doraise=True)
        print(f"✓ {filepath}")
    except py_compile.PyCompileError as e:
        print(f"✗ {filepath}")
        errors.append(f"{filepath}: {e}")

if errors:
    print("\n=== ERRORS ===")
    for error in errors:
        print(error)
    sys.exit(1)
else:
    print("\n✓ All files have correct syntax")
    sys.exit(0)
