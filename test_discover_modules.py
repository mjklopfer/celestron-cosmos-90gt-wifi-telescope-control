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
    def setUp(self):
        patcher = patch('discover_modules.identify_proxy', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

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




class ProxyDiscoveryTests(unittest.TestCase):
    def socket(self, version='COSMOSBridge-AMW007-0.1.0.0, Python proxy', identity=None):
        import json
        from unittest.mock import Mock
        sock = Mock()
        identity = identity if identity is not None else {
            'schema': 1, 'product': 'cosmos90gt-control', 'role': 'software_proxy',
            'physical_module': False, 'data_port': 2000, 'management_port': 3000}
        sock.recv.side_effect = [(version + '\r\n> ').encode(), (json.dumps(identity) + '\r\n> ').encode()]
        return sock

    def test_proxy_does_not_open_motor_port(self):
        from unittest.mock import Mock
        sock = self.socket()
        factory = Mock(return_value=sock)
        result = identify('192.0.2.22', socket_factory=factory)
        factory.assert_called_once_with(('192.0.2.22', 3000), .35)
        self.assertEqual(result['endpoint_kind'], 'software_proxy')
        self.assertFalse(result['motors_verified'])
        self.assertFalse(result['adapter_verified'])
        self.assertEqual([c.args[0] for c in sock.sendall.call_args_list],
                         [b'version\n', b'get cosmos.proxy\n'])
        sock.close.assert_called_once()

    def test_nonproxy_never_receives_private_query(self):
        from discover_modules import identify_proxy
        sock = self.socket(version='AMW007 hardware')
        self.assertIsNone(identify_proxy('192.0.2.22', socket_factory=lambda *args: sock))
        sock.sendall.assert_called_once_with(b'version\n')

    def test_legacy_proxy_remains_proxy_without_structured_reply(self):
        from discover_modules import identify_proxy
        sock = self.socket()
        sock.recv.side_effect = [b'COSMOSBridge-AMW007-old\r\n> ', b'ERR Unsupported\r\n> ']
        result = identify_proxy('192.0.2.22', socket_factory=lambda *args: sock)
        self.assertEqual(result['endpoint_kind'], 'software_proxy')
        self.assertNotIn('proxy_identity', result)

    def test_physical_match_does_not_hide_software_proxy(self):
        lans = [('eth', '192.168.1.1', ipaddress.ip_network('192.168.1.0/29'))]
        physical = {'ip': '192.168.1.2', 'verified': True}
        proxy = {'ip': '192.168.1.3', 'endpoint_kind': 'software_proxy', 'verified': True}
        with patch('discover_modules.connected_lans', return_value=lans), \
             patch('discover_modules.neighbor_entries', return_value=[{'ip':'192.168.1.2','mac':'00:06:66:01:02:03'}]), \
             patch('discover_modules.Recorder', Recorder), \
             patch('discover_modules.identify', return_value=physical), \
             patch('discover_modules.identify_proxy', side_effect=lambda host, port: proxy if host == '192.168.1.3' else None):
            result = scan_modules(mode='infrastructure')
        self.assertEqual({m['ip'] for m in result['matches']}, {'192.168.1.2', '192.168.1.3'})


if __name__ == '__main__':
    unittest.main()
