//+------------------------------------------------------------------+
//| GWARO DOLLAR PRINTER.mq5                                       |
//| Single-bot Gwaro Dollar Printer EA with bridge control support    |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

input string BridgeDir = "gwaro_mt5_bridge";
input string CommandFile = "latest_command.json";
input string AckFile = "latest_ack.json";
input string StatusFile = "latest_status.json";
input string ForwardFile = "attached_ea_command.json";
input bool VerboseLogging = true;
input int MagicNumber = 714001;
input double LotSize = 0.01;
input int SessionStartHour = 2;
input int SessionEndHour = 3;
input int SignalLookback = 5;

CTrade g_trade;

string g_current_state = "STOPPED";
string g_last_command = "";
string g_last_error = "";
bool g_running = false;
int g_current_day = -1;
bool g_trade_taken = false;
bool g_session_captured = false;
double g_session_high = 0.0;
double g_session_low = 999999.0;
bool g_bullish_sweep = false;
bool g_bearish_sweep = false;
bool g_bullish_bos = false;
bool g_bearish_bos = false;
double g_buy_order_block = 0.0;
double g_sell_order_block = 0.0;
double g_buy_fvg = 0.0;
double g_sell_fvg = 0.0;

int OnInit()
{
   EventSetTimer(1);
   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints(20);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trade.SetTypeTime(ORDER_TIME_GTC);
   ResetTradingDay();
   g_current_state = "STOPPED";
   g_last_command = "";
   g_last_error = "";
   g_running = false;
   WriteStatus(g_current_state, g_last_command, "gwarodollarprinter", g_last_error);
   Print("Gwaro Dollar Printer EA initialized");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTick()
{
   PollBridge();
   if(g_running)
      RunStrategy();
   WriteStatus(g_current_state, g_last_command, "gwarodollarprinter", g_last_error);
}

void OnTimer()
{
   PollBridge();
   if(g_running)
      RunStrategy();
   WriteStatus(g_current_state, g_last_command, "gwarodollarprinter", g_last_error);
}

void RunStrategy()
{
   ResetTradingDay();
   CaptureSession();
   if(!g_session_captured)
      return;

   DetectLiquiditySweep();
   DetectMSS();
   DetectOrderBlock();
   DetectFVG();
   WaitForRetest();
   ManageTrade();
   TrailingStop();
}

void ResetTradingDay()
{
   int today = TimeDay(TimeCurrent());
   if(today != g_current_day)
   {
      g_current_day = today;
      g_trade_taken = false;
      g_session_captured = false;
      g_session_high = 0.0;
      g_session_low = 999999.0;
      g_bullish_sweep = false;
      g_bearish_sweep = false;
      g_bullish_bos = false;
      g_bearish_bos = false;
      g_buy_order_block = 0.0;
      g_sell_order_block = 0.0;
      g_buy_fvg = 0.0;
      g_sell_fvg = 0.0;
      Print("New Trading Day");
   }
}

void CaptureSession()
{
   datetime now = TimeCurrent();
   if(TimeHour(now) == SessionStartHour && !g_session_captured)
   {
      MqlRates rates[];
      ArraySetAsSeries(rates, true);
      int copied = CopyRates(_Symbol, PERIOD_M5, 0, 12, rates);
      if(copied > 0)
      {
         double high = rates[0].high;
         double low = rates[0].low;
         for(int i = 1; i < copied; i++)
         {
            if(rates[i].high > high) high = rates[i].high;
            if(rates[i].low < low) low = rates[i].low;
         }
         g_session_high = high;
         g_session_low = low;
         g_session_captured = true;
         Print("Session High: ", g_session_high, " Session Low: ", g_session_low);
      }
   }

   if(TimeHour(now) >= SessionEndHour && !g_session_captured)
   {
      g_session_captured = true;
      Print("Session captured successfully!");
   }
}

void DetectLiquiditySweep()
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M5, 0, 3, rates);
   if(copied <= 0)
      return;

   g_bullish_sweep = false;
   g_bearish_sweep = false;

   if(rates[1].low < g_session_low && rates[1].close > g_session_low)
   {
      g_bullish_sweep = true;
      Print("Bullish liquidity sweep detected!");
   }

   if(rates[1].high > g_session_high && rates[1].close < g_session_high)
   {
      g_bearish_sweep = true;
      Print("Bearish liquidity sweep detected!");
   }
}

void DetectMSS()
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M5, 0, 5, rates);
   if(copied <= 0)
      return;

   g_bullish_bos = false;
   g_bearish_bos = false;

   if(g_bullish_sweep && rates[0].close > rates[1].high)
   {
      g_bullish_bos = true;
      Print("Bullish MSS");
   }

   if(g_bearish_sweep && rates[0].close < rates[1].low)
   {
      g_bearish_bos = true;
      Print("Bearish MSS");
   }
}

void DetectOrderBlock()
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M5, 0, 20, rates);
   if(copied <= 0)
      return;

   g_buy_order_block = 0.0;
   g_sell_order_block = 0.0;

   if(g_bullish_bos)
   {
      for(int i = copied - 1; i >= 0; i--)
      {
         if(rates[i].close < rates[i].open)
         {
            g_buy_order_block = rates[i].low;
            Print("BUY OB: ", g_buy_order_block);
            break;
         }
      }
   }

   if(g_bearish_bos)
   {
      for(int i = copied - 1; i >= 0; i--)
      {
         if(rates[i].close > rates[i].open)
         {
            g_sell_order_block = rates[i].high;
            Print("SELL OB: ", g_sell_order_block);
            break;
         }
      }
   }
}

void DetectFVG()
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M5, 0, 5, rates);
   if(copied <= 0)
      return;

   g_buy_fvg = 0.0;
   g_sell_fvg = 0.0;

   if(g_bullish_bos && rates[2].high < rates[0].low)
   {
      g_buy_fvg = rates[0].low;
      Print("BUY FVG: ", g_buy_fvg);
   }

   if(g_bearish_bos && rates[2].low > rates[0].high)
   {
      g_sell_fvg = rates[0].high;
      Print("SELL FVG: ", g_sell_fvg);
   }
}

void WaitForRetest()
{
   if(g_trade_taken)
      return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;

   if(g_bullish_bos)
   {
      double entry = (g_buy_order_block > 0.0 ? g_buy_order_block : g_buy_fvg);
      if(entry > 0.0 && tick.ask <= entry)
      {
         Print("BUY ENTRY");
         ExecuteTrade("BUY");
      }
   }

   if(g_bearish_bos)
   {
      double entry = (g_sell_order_block > 0.0 ? g_sell_order_block : g_sell_fvg);
      if(entry > 0.0 && tick.bid >= entry)
      {
         Print("SELL ENTRY");
         ExecuteTrade("SELL");
      }
   }
}

void ExecuteTrade(string direction)
{
   if(g_trade_taken)
      return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;

   double price = 0.0;
   double sl = 0.0;
   double tp = 0.0;
   int order_type = ORDER_TYPE_BUY;

   if(direction == "BUY")
   {
      price = tick.ask;
      sl = g_session_low;
      double risk = price - sl;
      tp = price + (risk * 3);
      order_type = ORDER_TYPE_BUY;
   }
   else
   {
      price = tick.bid;
      sl = g_session_high;
      double risk = sl - price;
      tp = price - (risk * 3);
      order_type = ORDER_TYPE_SELL;
   }

   bool ok = false;
   if(order_type == ORDER_TYPE_BUY)
      ok = g_trade.Buy(LotSize, _Symbol, price, sl, tp, "Gwaro Capital");
   else
      ok = g_trade.Sell(LotSize, _Symbol, price, sl, tp, "Gwaro Capital");

   if(ok)
   {
      g_trade_taken = true;
      Print("Trade Opened Successfully");
      g_last_error = "";
   }
   else
   {
      g_last_error = "Trade order failed";
      Print("Trade order failed");
   }
}

void ManageTrade()
{
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(!PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      double price_open = PositionGetDouble(POSITION_PRICE_OPEN);
      double tp = PositionGetDouble(POSITION_TP);
      double sl = PositionGetDouble(POSITION_SL);
      MqlTick tick;
      if(!SymbolInfoTick(_Symbol, tick))
         continue;

      if(type == POSITION_TYPE_BUY)
      {
         double profit = tick.bid - price_open;
         if(profit > 2.0)
         {
            g_trade.PositionModify(ticket, price_open, tp);
         }
      }
      else if(type == POSITION_TYPE_SELL)
      {
         double profit = price_open - tick.ask;
         if(profit > 2.0)
         {
            g_trade.PositionModify(ticket, price_open, tp);
         }
      }
   }
}

void TrailingStop()
{
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(!PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      MqlTick tick;
      if(!SymbolInfoTick(_Symbol, tick))
         continue;

      if(type == POSITION_TYPE_BUY)
      {
         double new_sl = tick.bid - 1.0;
         if(new_sl > sl)
            g_trade.PositionModify(ticket, new_sl, tp);
      }
      else if(type == POSITION_TYPE_SELL)
      {
         double new_sl = tick.ask + 1.0;
         if(sl == 0.0 || new_sl < sl)
            g_trade.PositionModify(ticket, new_sl, tp);
      }
   }
}

void PollBridge()
{
   string rel_command = BridgePath(CommandFile);
   string rel_ack = BridgePath(AckFile);
   string rel_forward = BridgePath(ForwardFile);
   string payload = ReadTextFile(rel_command);
   if(StringLen(payload) == 0)
   {
      WriteStatus(g_current_state, g_last_command, "gwarodollarprinter", g_last_error);
      return;
   }

   string command = ExtractJsonString(payload, "command");
   string bot_id = ExtractJsonString(payload, "bot_id");
   string symbol = ExtractJsonString(payload, "symbol");
   if(StringLen(symbol) == 0)
      symbol = _Symbol;

   string normalized = StringUpper(command);
   string reply = "";
   string state = g_current_state;
   string error = "";

   if(normalized == "START")
   {
      g_running = true;
      state = "RUNNING";
      reply = "ACK_START:" + bot_id + ":" + symbol;
      SendToAttachedEA(normalized, bot_id, symbol, rel_forward);
   }
   else if(normalized == "STOP")
   {
      g_running = false;
      state = "STOPPED";
      reply = "ACK_STOP:" + bot_id;
      SendToAttachedEA(normalized, bot_id, symbol, rel_forward);
   }
   else if(normalized == "RESTART")
   {
      g_running = true;
      state = "RUNNING";
      reply = "ACK_RESTART:" + bot_id + ":" + symbol;
      SendToAttachedEA(normalized, bot_id, symbol, rel_forward);
   }
   else if(normalized == "CLOSE_ALL" || normalized == "CLOSE_ALL_TRADES" || normalized == "CLOSEALL")
   {
      CloseAllPositions();
      g_running = false;
      state = "STOPPED";
      reply = "ACK_CLOSE_ALL:" + bot_id;
      SendToAttachedEA(normalized, bot_id, symbol, rel_forward);
   }
   else if(normalized == "BREAK_EVEN")
   {
      BreakEvenPositions();
      g_running = true;
      state = "RUNNING";
      reply = "ACK_BREAK_EVEN:" + bot_id;
      SendToAttachedEA(normalized, bot_id, symbol, rel_forward);
   }
   else if(normalized == "REFRESH")
   {
      state = g_current_state;
      reply = "ACK_REFRESH:" + bot_id;
   }
   else
   {
      state = "ERROR";
      error = "Unsupported command: " + normalized;
      reply = "ERR:" + error;
   }

   g_current_state = state;
   g_last_command = normalized;
   g_last_error = error;
   WriteStatus(g_current_state, g_last_command, bot_id, g_last_error);
   WriteTextFile(rel_ack, reply);

   if(FileDelete(rel_command))
   {
      if(VerboseLogging)
         Print("Processed command file");
   }
}

void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(!PositionSelectByTicket(ticket))
         continue;
      g_trade.PositionClose(ticket);
   }
}

void BreakEvenPositions()
{
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(!PositionSelectByTicket(ticket))
         continue;
      double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
      g_trade.PositionModify(ticket, open_price, PositionGetDouble(POSITION_TP));
   }
}

void SendToAttachedEA(string command, string bot_id, string symbol, string rel_forward)
{
   string payload = "{\"command\":\"" + EscapeJsonString(command) + "\",\"bot_id\":\"" + EscapeJsonString(bot_id) + "\",\"symbol\":\"" + EscapeJsonString(symbol) + "\",\"timestamp\":\"" + TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS) + "\"}";
   WriteTextFile(rel_forward, payload);
   if(VerboseLogging)
      Print("Forwarded command to attached EA: ", command);
}

void WriteStatus(string state, string last_command, string bot_id, string error)
{
   string payload = "{\"state\":\"" + EscapeJsonString(state) + "\",\"bot_id\":\"" + EscapeJsonString(bot_id) + "\",\"symbol\":\"" + EscapeJsonString(_Symbol) + "\",\"running\":" + (state == "RUNNING" ? "true" : "false") + ",\"last_command\":\"" + EscapeJsonString(last_command) + "\",\"last_error\":\"" + EscapeJsonString(error) + "\",\"updated_at\":\"" + TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS) + "\",\"session_captured\":" + (g_session_captured ? "true" : "false") + ",\"trade_taken\":" + (g_trade_taken ? "true" : "false") + ",\"positions\":" + IntegerToString(PositionsTotal()) + ",\"session_high\":" + DoubleToString(g_session_high, 5) + ",\"session_low\":" + DoubleToString(g_session_low, 5) + "}";
   WriteTextFile(BridgePath(StatusFile), payload);
}

bool WriteTextFile(string path, string text)
{
   int handle = FileOpen(path, FILE_WRITE | FILE_TXT);
   if(handle == INVALID_HANDLE)
      return false;
   FileWriteString(handle, text);
   FileClose(handle);
   return true;
}

string ReadTextFile(string path)
{
   int handle = FileOpen(path, FILE_READ | FILE_TXT);
   if(handle == INVALID_HANDLE)
      return "";
   string text = FileReadString(handle);
   FileClose(handle);
   return text;
}

string BridgePath(string file_name)
{
   string folder = BridgeDir;
   while(StringLen(folder) > 0 && (StringSubstr(folder, 0, 1) == "\\" || StringSubstr(folder, 0, 1) == "/"))
      folder = StringSubstr(folder, 1);

   string data_path = TerminalInfoString(TERMINAL_DATA_PATH);
   if(StringLen(data_path) > 0)
      return data_path + "\\MQL5\\Files\\" + folder + "\\" + file_name;

   return folder + "\\" + file_name;
}

string EscapeJsonString(string value)
{
   string escaped = value;
   StringReplace(escaped, "\\", "\\\\");
   StringReplace(escaped, "\"", "\\\"");
   StringReplace(escaped, "\n", "\\n");
   StringReplace(escaped, "\r", "\\r");
   return escaped;
}

string ExtractJsonString(string payload, string key)
{
   string pattern = "\"" + key + "\":\"";
   int pos = StringFind(payload, pattern);
   if(pos < 0)
      return "";
   int start = pos + StringLen(pattern);
   int end = StringFind(payload, "\"", start);
   if(end < 0)
      return "";
   return StringSubstr(payload, start, end - start);
}

string StringUpper(string str)
{
   string result = str;
   int len = StringLen(result);
   for(int i = 0; i < len; i++)
   {
      ushort ch = StringGetCharacter(result, i);
      if(ch >= 97 && ch <= 122)
         ch = (ushort)(ch - 32);
      StringSetCharacter(result, i, ch);
   }
   return result;
}
