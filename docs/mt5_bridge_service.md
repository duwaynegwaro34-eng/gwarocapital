# Standalone MT5 Bridge service for Gwaro Capital

This service runs on a Windows machine that also hosts MetaTrader 5. It exposes a small REST API that the Render-hosted website can call for MT5 connectivity.

## Requirements

- Windows machine with MetaTrader 5 installed
- Python 3.10+
- MetaTrader5 Python package
- Flask
- requests

## Installation

1. Create a virtual environment:
   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install Flask requests MetaTrader5
   ```
3. Set these environment variables before starting the bridge:
   ```powershell
   $env:MT5_BRIDGE_HOST="0.0.0.0"
   $env:MT5_BRIDGE_PORT="5001"
   $env:MT5_LOGIN="123456"
   $env:MT5_PASSWORD="your-password"
   $env:MT5_SERVER="Broker-Server"
   ```

## Start the bridge

```powershell
python services/standalone_mt5_bridge.py
```

## Endpoints

- GET /health
- POST /connect
- GET /account
- GET /positions
- GET /orders
- POST /disconnect

## Health checks

Use:

```powershell
curl http://127.0.0.1:5001/health
```

The website should call the bridge health endpoint first and only attempt a connection if the bridge reports `ok: true`.

## Render configuration

Set the website environment variable:

```text
MT5_BRIDGE_URL=http://<windows-host>:5001
```
