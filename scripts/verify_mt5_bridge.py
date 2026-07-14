import os
import json
from services.mt5_bridge import MT5Bridge
from config import settings as app_settings


def print_info(bridge):
    print("bridge.base_dir:", bridge.base_dir)
    print("config.mt5_bridge_dir:", app_settings.mt5_bridge_dir)
    cmd = getattr(bridge, '_command_file', None)
    status = getattr(bridge, '_status_file', None)
    print('command_file:', cmd)
    print('status_file :', status)
    print('command exists:', cmd.exists() if cmd else False)
    print('status exists :', status.exists() if status else False)
    if cmd and cmd.exists():
        print('command contents:\n', cmd.read_text(encoding='utf-8'))
    if status and status.exists():
        print('status contents:\n', status.read_text(encoding='utf-8'))
    try:
        expected = os.path.abspath(app_settings.mt5_bridge_dir)
        actual = os.path.abspath(str(bridge.base_dir))
        print('expected == actual ?', expected == actual)
        print('expected:', expected)
        print('actual  :', actual)
    except Exception as e:
        print('Error comparing paths:', e)


if __name__ == '__main__':
    b = MT5Bridge(base_dir=app_settings.mt5_bridge_dir, mt5_manager=None)
    print('--- Before send_command ---')
    print_info(b)
    ok, msg = b.send_command('START', 'test_ea', bot_path=r"C:\Experts\TestEA.ex5")
    print('\nsend_command returned:', ok, msg)
    print('\n--- After send_command ---')
    print_info(b)
    ok2, msg2 = b.send_command('STOP', 'test_ea')
    print('\nsend_command STOP returned:', ok2, msg2)
    print('\n--- After send_command STOP ---')
    print_info(b)
