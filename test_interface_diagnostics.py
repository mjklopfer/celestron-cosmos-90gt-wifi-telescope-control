"""Proxy diagnostics must never connect to the motor data socket."""
import unittest
from unittest.mock import MagicMock, patch
import interface_diagnostics as module
from test_diagnostics import Recorder

class ProxyDiagnosticsTests(unittest.TestCase):
    def test_unverified_proxy_never_opens_socket(self):
        with patch.object(module, 'LiveRecorder', Recorder), patch.object(module, 'identify_proxy', return_value=None), patch.object(module.socket, 'create_connection') as connect:
            result = module.diagnose_proxy('192.0.2.1')
        connect.assert_not_called()
        self.assertIn('signature not verified', result['error'])

    def test_verified_proxy_only_requests_cached_management_telemetry(self):
        sock = MagicMock()
        sock.__enter__.return_value = sock
        sock.recv.return_value = b'{"read_only":true,"positions":{}}\n> '
        with patch.object(module, 'LiveRecorder', Recorder), patch.object(module, 'identify_proxy', return_value={'endpoint_kind': 'software_proxy'}), patch.object(module.socket, 'create_connection', return_value=sock) as connect:
            result = module.diagnose_proxy('192.0.2.1', 2000)
        connect.assert_called_once_with(('192.0.2.1', 3000), 2)
        sock.sendall.assert_called_once_with(b'get cosmos.telemetry\n')
        self.assertFalse(result['movement_sent'])
        self.assertNotIn('error', result)
