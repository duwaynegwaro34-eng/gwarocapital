import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mt5_manager import MT5Manager
from services.mt5_bridge_client import MT5BridgeClient


class MT5BridgeClientTests(unittest.TestCase):
    def test_builds_base_url_from_host_and_port(self):
        with patch.dict(os.environ, {"MT5_BRIDGE_HOST": "bridge.internal", "MT5_BRIDGE_PORT": "5001"}, clear=False):
            client = MT5BridgeClient(base_url=None)

        self.assertEqual(client.base_url, "http://bridge.internal:5001")

    def test_health_reports_misconfigured_when_not_configured(self):
        client = MT5BridgeClient(base_url="")

        payload = client.health()

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "misconfigured")

    def test_manager_uses_bridge_health_before_connect(self):
        manager = MT5Manager(bridge_url="http://bridge.internal:5001")
        manager._bridge = Mock()
        manager._bridge.health.return_value = {"ok": True, "status": "ok"}

        self.assertTrue(manager.initialize_client())
        manager._bridge.health.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
