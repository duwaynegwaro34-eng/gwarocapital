from datetime import datetime, timezone
import threading

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


class MT5Manager:
    def __init__(self):
        self._lock = threading.RLock()
        self._login = None
        self._password = None
        self._server = None
        self._connected = False
        self._connection_time = None
        self._last_error = ""
        self._initialized = False

    def _initialize_mt5(self):
        if mt5 is None:
            return False

        if self._initialized:
            return True

        if self._login is not None and self._password and self._server:
            initialized = mt5.initialize(login=self._login, password=self._password, server=self._server)
        else:
            initialized = mt5.initialize()

        if not initialized:
            return False

        self._initialized = True
        return True

    def connect(self, login, password, server):
        if mt5 is None:
            return {
                "ok": False,
                "message": "MetaTrader5 package is not installed.",
            }

        login_str = str(login).strip()
        password_str = str(password).strip()
        server_str = str(server).strip()

        if not login_str or not password_str or not server_str:
            return {
                "ok": False,
                "message": "Login, password, and server are required.",
            }

        try:
            login_int = int(login_str)
        except ValueError:
            return {
                "ok": False,
                "message": "MT5 login must be numeric.",
            }

        with self._lock:
            self._login = login_int
            self._password = password_str
            self._server = server_str

            if self._initialized:
                self.shutdown_client()

            initialized = mt5.initialize(login=login_int, password=password_str, server=server_str)
            if not initialized:
                error = mt5.last_error()
                self._last_error = f"{error[0]}: {error[1]}" if error else "Unknown MT5 error"
                self._connected = False
                self._connection_time = None
                return {
                    "ok": False,
                    "message": f"Failed to connect to MT5: {self._last_error}",
                }

            account = mt5.account_info()
            if account is None:
                self._connected = False
                self._connection_time = None
                self._last_error = "Connected terminal has no logged-in account."
                self.shutdown_client()
                return {
                    "ok": False,
                    "message": self._last_error,
                }

            self._initialized = True
            self._login = int(getattr(account, "login", login_int))
            self._server = getattr(account, "server", server_str) or server_str
            self._connected = True
            self._connection_time = datetime.now(timezone.utc)
            self._last_error = ""

            return {
                "ok": True,
                "message": "MT5 connected successfully.",
            }

    def disconnect(self):
        with self._lock:
            self.shutdown_client()
            self._connected = False
            self._connection_time = None

        return {
            "ok": True,
            "message": "MT5 disconnected.",
        }

    def connection_status(self):
        if mt5 is None:
            return {
                "installed": False,
                "running": False,
                "connected": False,
                "status": "Disconnected",
                "account_login": None,
                "server": "",
                "connection_time": "--",
                "last_error": "MetaTrader5 package is not installed.",
            }

        with self._lock:
            running = False
            account_login = None
            server = self._server or ""

            if not self._initialize_mt5():
                self._connected = False
                error = mt5.last_error() if mt5 is not None else None
                self._last_error = f"{error[0]}: {error[1]}" if error else "Unknown MT5 error"
            else:
                running = True
                account = mt5.account_info()
                if account is not None:
                    account_login = int(getattr(account, "login", 0) or 0)
                    server = getattr(account, "server", server) or server
                    self._connected = True
                    self._last_error = ""
                else:
                    self._connected = False
                    self._last_error = "Connected terminal has no logged-in account."
                    self.shutdown_client()
                    running = False

            return {
                "installed": True,
                "running": running,
                "connected": self._connected,
                "status": "Connected" if self._connected else "Disconnected",
                "account_login": account_login if self._connected else None,
                "server": server if self._connected else "",
                "connection_time": self._connection_time.isoformat() if self._connection_time else "--",
                "last_error": self._last_error if not self._connected else "",
            }

    def initialize_client(self):
        if mt5 is None:
            return False

        with self._lock:
            return self._initialize_mt5()

    def shutdown_client(self):
        if mt5 is None:
            return

        with self._lock:
            if not self._initialized:
                return
            try:
                mt5.shutdown()
            except Exception:
                pass
            finally:
                self._initialized = False
                self._connected = False


mt5_manager = MT5Manager()
