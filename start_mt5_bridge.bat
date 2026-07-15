@echo off
setlocal
cd /d "%~dp0"
set "MT5_BRIDGE_HOST=0.0.0.0"
set "MT5_BRIDGE_PORT=5001"
if not defined MT5_LOGIN set "MT5_LOGIN="
if not defined MT5_PASSWORD set "MT5_PASSWORD="
if not defined MT5_SERVER set "MT5_SERVER="
python services\standalone_mt5_bridge.py
