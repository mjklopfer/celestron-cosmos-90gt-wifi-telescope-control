"""Regression checks for discover modules. No real telescope is connected."""
from pathlib import Path
import ipaddress
import unittest
from unittest.mock import patch
from discover_modules import identify, scan_modules
from network_info import parse_neighbors
from test_motor_control import Adapter


class Recorder:
    directory = Path('/tmp/simulated-protocol-discovery')
    def __init__(self, kind):
        pass
    def record(self, *args, **kwargs):
        pass
    def finish(self, report):
        pass


class ModuleDiscoveryTests(unittest.TestCase):
    def test_identifies_aux_by_valid_replies_without_mac_or_ssid(self):
        adapter = Adapter()
        result = identify('192.168.1.99', socket_factory=lambda address, timeout: adapter)
        self.assertTrue(result['verified'])
        self.assertEqual(result['motor_versions'], {'azimuth': '5.24', 'altitude': '5.24'})
        self.assertEqual(result['port'], 2000)
        self.assertTrue(adapter.closed)
        self.assertFalse(any(frame[4] in (0x24, 0x25) for _, frame in adapter.sent))

    def test_closed_port_is_not_a_module(self):
        def closed(address, timeout):
            raise ConnectionRefusedError()
        self.assertIsNone(identify('192.168.1.99', socket_factory=closed))

    def test_identifies_legacy_adapter_when_both_motors_are_silent(self):
        class SilentMotors(Adapter):
            def sendall(self, frame):
                self.incoming.put(b'*HELLO*')
        class WiFlySession:
            entered = False
            def __init__(self, *args):
                pass
            def enter(self):
                self.entered = True
            def command(self, command):
                return 'WiFly Ver 2.40-CEL, 03-05-2012 on RN-171\r\n<2.40-CEL>'
            def exit(self):
                return True
        adapter = SilentMotors()
        with patch('discover_modules.Session', WiFlySession):
            result = identify('192.168.1.99', socket_factory=lambda *args: adapter)
        self.assertTrue(result['verified'])
        self.assertTrue(result['adapter_verified'])
        self.assertFalse(result['motors_verified'])
        self.assertEqual(result['motor_versions']['azimuth'], 'No reply')
        self.assertIn('motors not responding', result['verification_note'])

    def test_invalid_motor_replies_not_accepted(self):
        class BadAdapter(Adapter):
            def sendall(self, frame):
                self.incoming.put(b'*HELLO*\r\nHTTP unrelated\r\n')
        adapter = BadAdapter()
        self.assertIsNone(identify('192.168.1.99', socket_factory=lambda address, timeout: adapter))
        self.assertTrue(adapter.closed)

    def test_cached_neighbor_mac_is_not_a_filter(self):
        lans = [('en0', '192.168.1.20', ipaddress.ip_network('192.168.1.0/24'))]
        arp = '? (192.168.1.99) at de:ad:be:ef:11:22 on en0 ifscope [ethernet]'
        found = {'ip': '192.168.1.99', 'port': 2000, 'verified': True, 'module_type': 'Celestron AUX Wi-Fi bridge'}
        with patch('discover_modules.connected_lans', return_value=lans), \
             patch('discover_modules.neighbor_entries', return_value=parse_neighbors(arp)), \
             patch('discover_modules.Recorder', Recorder), \
             patch('discover_modules.identify', return_value=found) as probe:
            result = scan_modules()
        self.assertEqual(result['matches'][0]['ip'], '192.168.1.99')
        self.assertEqual(probe.call_args.args[:2], ('192.168.1.99', 2000))

    def test_rn171_vendor_prefix_is_tried_before_other_neighbors(self):
        lans = [('en0', '192.168.1.20', ipaddress.ip_network('192.168.1.0/24'))]
        arp = ('? (192.168.1.88) at de:ad:be:ef:11:22 on en0\n'
               '? (192.168.1.42) at 0:6:66:11:22:33 on en0')
        found = {'ip': '192.168.1.42', 'port': 2000, 'verified': True}
        with patch('discover_modules.connected_lans', return_value=lans), \
             patch('discover_modules.neighbor_entries', return_value=parse_neighbors(arp)), \
             patch('discover_modules.Recorder', Recorder), \
             patch('discover_modules.identify', return_value=found) as probe:
            result = scan_modules()
        self.assertEqual(result['vendor_hint_candidates'], ['192.168.1.42'])
        probe.assert_called_once()
        self.assertEqual(probe.call_args.args[:2], ('192.168.1.42', 2000))
        self.assertTrue(probe.call_args.kwargs['rn171_hint'])

    def test_direct_network_only_probes_known_endpoint_not_public_subnet(self):
        lans = [('en1', '1.2.3.10', ipaddress.ip_network('1.2.3.0/24'))]
        with patch('discover_modules.connected_lans', return_value=lans), \
             patch('discover_modules.neighbor_entries', return_value=[]), \
             patch('discover_modules.Recorder', Recorder), \
             patch('discover_modules.identify', return_value=None) as probe:
            scan_modules()
        self.assertEqual(probe.call_count, 2)
        self.assertEqual(probe.call_args.args[:2], ('1.2.3.4', 2000))
        self.assertTrue(probe.call_args.kwargs['rn171_hint'])
        self.assertGreater(probe.call_args.kwargs['connect_timeout'], 2.5)

    def test_transient_rn171_failure_is_retried(self):
        lans = [('en0', '192.168.1.20', ipaddress.ip_network('192.168.1.0/24'))]
        arp = '? (192.168.1.42) at 0:6:66:11:22:33 on en0'
        found = {'ip': '192.168.1.42', 'verified': True}
        with patch('discover_modules.connected_lans', return_value=lans), \
             patch('discover_modules.neighbor_entries', return_value=parse_neighbors(arp)), \
             patch('discover_modules.Recorder', Recorder), \
             patch('discover_modules.identify', side_effect=[None, found]) as probe:
            report = scan_modules()
        self.assertEqual(probe.call_count, 2)
        self.assertEqual(report['matches'], [found])

    def test_direct_mode_ignores_house_lan_and_retries_known_adapter(self):
        lans = [('house', '192.168.1.20', ipaddress.ip_network('192.168.1.0/24')),
                ('scope', '1.2.3.10', ipaddress.ip_network('1.2.3.0/24'))]
        found = {'ip': '1.2.3.4', 'verified': True, 'adapter_verified': True}
        with patch('discover_modules.connected_lans', return_value=lans), \
             patch('discover_modules.neighbor_entries', return_value=[]), \
             patch('discover_modules.Recorder', Recorder), \
             patch('discover_modules.identify', side_effect=[None, found]) as probe:
            report = scan_modules(mode='direct')
        self.assertEqual(report['matches'], [found])
        self.assertEqual(report['networks_checked'], ['1.2.3.0/24'])
        self.assertTrue(all(call.args[0] == '1.2.3.4' for call in probe.call_args_list))

    def test_direct_mode_reports_missing_telescope_interface(self):
        lans = [('house', '192.168.1.20', ipaddress.ip_network('192.168.1.0/24'))]
        with patch('discover_modules.connected_lans', return_value=lans), \
             patch('discover_modules.Recorder', Recorder), \
             patch('discover_modules.identify') as probe:
            report = scan_modules(mode='direct')
        probe.assert_not_called()
        self.assertIn('no usable direct-network address', report['error'])

    def test_expired_scan_budget_skips_network_probes(self):
        lans = [('en1', '1.2.3.10', ipaddress.ip_network('1.2.3.0/24'))]
        with patch('discover_modules.connected_lans', return_value=lans), \
             patch('discover_modules.neighbor_entries', return_value=[]), \
             patch('discover_modules.Recorder', Recorder), \
             patch('discover_modules.identify') as probe:
            report = scan_modules(timeout=0)
        probe.assert_not_called()
        self.assertTrue(report['timed_out'])


if __name__ == '__main__':
    unittest.main()
