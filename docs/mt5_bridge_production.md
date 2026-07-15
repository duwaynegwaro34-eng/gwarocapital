# Production MT5 Bridge deployment

## Windows service host

1. Install Python and the bridge dependencies on the Windows machine running MetaTrader 5.
2. Set environment variables:
   - MT5_BRIDGE_HOST=0.0.0.0
   - MT5_BRIDGE_PORT=5001
   - MT5_BRIDGE_API_KEY=<strong-random-key>
   - MT5_LOGIN=<login>
   - MT5_PASSWORD=<password>
   - MT5_SERVER=<broker-server>
3. Start the bridge with:
   ```powershell
   python services/standalone_mt5_bridge.py
   ```
4. Verify the health endpoint:
   ```powershell
   curl http://127.0.0.1:5001/health
   ```

## Render-hosted website

Set these environment variables in Render:
- MT5_BRIDGE_URL=http://<windows-host-ip>:5001
- MT5_BRIDGE_API_KEY=<same-key-as-above>

The website will now use the bridge for connect, disconnect, account info, positions, orders, and bot commands.
