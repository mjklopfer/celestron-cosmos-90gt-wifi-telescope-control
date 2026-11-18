import unittest
from unittest.mock import MagicMock, patch
import homebrew_settings as h

class HomeBrewTests(unittest.TestCase):
    def test_bounds_and_injection(self):
        for lat, lon in [(91, 0), (0, -181), (float('nan'), 0), (0, float('inf')), ('1\r\nsave', 0)]:
            with self.subTest(lat=lat, lon=lon), self.assertRaises(ValueError):
                h.location_plan(lat, lon)
        self.assertEqual(h.location_plan(-90, 180)['command'], 'fakegps -90.000000 180.000000')

    def test_default_cannot_write(self):
        with patch.object(h.socket, 'create_connection') as connect, self.assertRaises(ValueError):
            h.apply_location('192.0.2.1', 33, -117)
        connect.assert_not_called()

    def exercise(self, replies):
        sock = MagicMock()
        sock.__enter__.return_value = sock
        with patch.object(h, 'EndpointLease'), patch.object(h.socket, 'create_connection', return_value=sock), patch.object(h, 'read_prompt', side_effect=replies):
            try:
                result = h.apply_location('192.0.2.1', 33, -117, allow_unverified=True)
            except ValueError:
                result = None
        return sock, result

    def test_stock_adapter_receives_no_write(self):
        sock, result = self.exercise(['> ', 'AMW007 > '])
        self.assertIsNone(result)
        self.assertEqual([c.args[0] for c in sock.sendall.call_args_list], [b'version\r\n'])

    def test_missing_capability_receives_no_write(self):
        sock, result = self.exercise(['> ', 'HBG3 v9', 'help version exit'])
        self.assertIsNone(result)
        self.assertEqual(sock.sendall.call_count, 2)

    def test_reply_is_not_claimed_as_verified(self):
        sock, result = self.exercise(['> ', 'HBG3 v9', 'fakegps latitude longitude', 'OK\r\n> '])
        self.assertFalse(result['readback_verified'])
        self.assertFalse(result['time_sent'])
        self.assertEqual(sock.sendall.call_args.args[0], b'fakegps 33.000000 -117.000000\r\n')

    def test_truncated_prompt_rejected(self):
        sock = MagicMock()
        sock.recv.side_effect = [b'incomplete', b'']
        with self.assertRaises(ConnectionError):
            h.read_prompt(sock)
