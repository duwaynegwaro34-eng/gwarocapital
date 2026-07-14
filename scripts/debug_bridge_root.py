import os, sys
from pathlib import Path
sys.path.insert(0, os.getcwd())
from config import settings as app_settings
from services.mt5_bridge import MT5Bridge

print('cwd:', os.getcwd())
print('sys.path[0]:', sys.path[0])
print('MT5_BRIDGE_DIR env:', os.getenv('MT5_BRIDGE_DIR'))
print('config.mt5_bridge_dir:', app_settings.mt5_bridge_dir)

bridge = MT5Bridge(base_dir=app_settings.mt5_bridge_dir, mt5_manager=None)
print('bridge.base_dir:', bridge.base_dir)
print('bridge.base_dir exists:', bridge.base_dir.exists())
print('bridge._command_file:', bridge._command_file)
print('bridge._command_file exists:', bridge._command_file.exists())
print('bridge._status_file:', bridge._status_file)
print('bridge._status_file exists:', bridge._status_file.exists())
print('root contents:')
for item in sorted(bridge.base_dir.iterdir()):
    print('  ', item.name)

print('--- writing test command ---')
ok, msg = bridge.send_command('START', 'debugbot', bot_path='C:\\test\\path.ex5')
print('send_command result:', ok, msg)
print('root contents after send_command:')
for item in sorted(bridge.base_dir.iterdir()):
    print('  ', item.name)
print('latest_command exists:', bridge._command_file.exists())
if bridge._command_file.exists():
    print('latest_command contents:')
    print(bridge._command_file.read_text(encoding='utf-8'))
