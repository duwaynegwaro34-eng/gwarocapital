# Gwaro MT5 EA Installation

## 1. Place the EA
Copy the file `GWARO DOLLAR PRINTER.mq5` into your MetaTrader 5 Experts folder:

- Windows: `%AppData%\MetaQuotes\Terminal\<Your_Terminal_ID>\MQL5\Experts`

If you want it in the Advisors folder instead, place it in:

- `%AppData%\MetaQuotes\Terminal\<Your_Terminal_ID>\MQL5\Experts\Advisors`

## 2. Compile the EA
1. Open MetaTrader 5.
2. Open the MetaEditor.
3. Open `GWARO DOLLAR PRINTER.mq5`.
4. Press F7 or choose Compile.
5. If compilation succeeds, the compiled `.ex5` file appears next to the `.mq5` source.

## 3. Attach it to a chart
1. Open any chart (for example XAUUSD M5).
2. Drag the compiled `GWARO DOLLAR PRINTER` from the Navigator to the chart.
3. Keep it running continuously.

## 4. MT5 settings
Enable:
- AutoTrading / Algo Trading
- Allow web requests if you later use WebRequest-based bridge transport
- Any required file access permissions for the bridge folder

## 5. Bridge folder
The EA reads/writes files in:

- `%AppData%\MetaQuotes\Terminal\<Your_Terminal_ID>\MQL5\Files\gwaro_mt5_bridge`

The Flask app writes commands into this directory and reads acknowledgements from it.

## 6. Test from the website
1. Start the Flask app.
2. Open the Bot Control page.
3. Select an EA and press Start.
4. The `GWARO DOLLAR PRINTER` EA should acknowledge the command by writing to the bridge status files.

> Note: Do not use the legacy `GwaroControllerEA.mq5` controller placeholder. The website is designed to work with `GWARO DOLLAR PRINTER.mq5` directly.
5. Press Stop and verify the status changes back to Stopped.
