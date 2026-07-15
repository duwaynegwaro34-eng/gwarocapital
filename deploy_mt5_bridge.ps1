$ErrorActionPreference = 'Stop'
$bridgeHost = if ($env:MT5_BRIDGE_HOST) { $env:MT5_BRIDGE_HOST } else { '0.0.0.0' }
$bridgePort = if ($env:MT5_BRIDGE_PORT) { $env:MT5_BRIDGE_PORT } else { '5001' }
$bridgeApiKey = if ($env:MT5_BRIDGE_API_KEY) { $env:MT5_BRIDGE_API_KEY } else { 'change-me' }
$mt5Login = if ($env:MT5_LOGIN) { $env:MT5_LOGIN } else { '' }
$mt5Password = if ($env:MT5_PASSWORD) { $env:MT5_PASSWORD } else { '' }
$mt5Server = if ($env:MT5_SERVER) { $env:MT5_SERVER } else { '' }
$env:MT5_BRIDGE_HOST = $bridgeHost
$env:MT5_BRIDGE_PORT = $bridgePort
$env:MT5_BRIDGE_API_KEY = $bridgeApiKey
$env:MT5_LOGIN = $mt5Login
$env:MT5_PASSWORD = $mt5Password
$env:MT5_SERVER = $mt5Server
python .\services\standalone_mt5_bridge.py
