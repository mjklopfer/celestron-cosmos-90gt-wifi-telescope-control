"""Verify diagnostic classification and read-only query coverage without hardware."""
from pathlib import Path
import unittest
import threading
from unittest.mock import MagicMock, patch
import diagnostics


class Recorder:
    directory = Path('/tmp/simulated-diagnostics')
    def __init__(self, callback, secrets):
        self.callback = callback
    def record(self, event, **fields):
        self.callback({'event': event, **fields})
    def finish(self, report):
        self.report = report


class Session:
    commands = []
    def __init__(self, *args):
        self.entered = False
    def enter(self):
        self.entered = True
    def command(self, command):
        self.commands.append(command)
        if command == 'ver':
            return 'WiFly Ver 2.40-CEL on RN-171'
        return 'SSID=Example\nPassphrase=test-secret\n<2.40-CEL>'
    def exit(self):
        return True


class Probe:
    missing_axis = None
    calls = []
    def __init__(self, *args):
        pass
    def receive(self, seconds):
        pass
    def query(self, axis, command, attempts=2):
        self.calls.append((axis, command))
        if axis == self.missing_axis or axis in (0xb0, 0xb2, 0xb5):
            return None
        return b'\x05\x18' if command == 0xfe else b'\x00\x00\x00'
    def close(self):
        pass


class DiagnosticTests(unittest.TestCase):
    def test_abort_after_first_wifi_reply_exits_and_preserves_results(self):
        cancel = threading.Event()
        session = MagicMock()
        session.command.return_value = 'WiFly RN-171 2.40-CEL'
        session.exit.return_value = True
        def callback(event):
            if event['event'] == 'diagnostic_row' and event['device'] == 'Wi-Fi adapter':
                cancel.set()
        with patch.object(diagnostics, 'LiveRecorder', Recorder), \
             patch.object(diagnostics, 'check_direct_route'), \
             patch.object(diagnostics.socket, 'create_connection', return_value=MagicMock()), \
             patch.object(diagnostics, 'Session', return_value=session), \
             patch.object(diagnostics, 'AuxProbe') as probe:
            report = diagnostics.diagnose('192.0.2.231', 2000, callback, cancel=cancel)
        self.assertTrue(report['aborted'])
        self.assertNotIn('error', report)
        self.assertEqual(session.command.call_count, 1)
        session.exit.assert_called_once()
        probe.assert_not_called()
        self.assertTrue(any(row['status'] == 'NOT QUERIED' for row in report['rows']))

    def test_time_site_decode_boundaries(self):
        self.assertEqual(diagnostics.decode_time_site(1, bytes(3))[0], 0)
        self.assertEqual(diagnostics.decode_time_site(2, bytes.fromhex('c00000'))[0], -90)
        self.assertEqual(diagnostics.decode_time_site(4, bytes.fromhex('07ea'))[0], 2026)
        self.assertEqual(diagnostics.decode_time_site(0x33, bytes((23, 59, 59)))[0], [23, 59, 59])
        self.assertFalse(diagnostics.decode_time_site(0x36, b'\x00')[0])
        for command, data in ((1, bytes.fromhex('600000')), (4, bytes(2)),
                              (3, bytes((2, 30))), (0x33, bytes((24, 0, 0))),
                              (0x37, b'\x02'), (0x33, b'')):
            with self.subTest(command=command, data=data), self.assertRaises(ValueError):
                diagnostics.decode_time_site(command, data)

    def test_hemispheres_satellites_and_unknown_compass(self):
        self.assertIn('W', diagnostics.decode_time_site(2, bytes.fromhex('c00000'))[1])
        self.assertIn('N', diagnostics.decode_time_site(1, bytes(3))[1])
        self.assertEqual(diagnostics.decode_time_site(7, bytes((8, 5)))[0], [8, 5])
        self.assertEqual(diagnostics.decode_time_site(0xa0, b'\x0b')[1], 'N')
        self.assertIn('Unknown', diagnostics.decode_time_site(0xa0, b'\xff')[1])

    def test_catalog_queries_are_allowed_but_writes_are_blocked(self):
        from celestron_probe import packet
        for address, _, queries in diagnostics.TIME_SITE_QUERIES:
            for command, _ in queries:
                packet(address, command)
        for address in (0x10, 0x11):
            for command, _ in diagnostics.motor_queries(address):
                packet(address, command)
            for command in (2, 4, 6, 7, 0x24, 0x25, 0x38, 0x39, 0x46, 0x81, 0xfd):
                with self.assertRaises(ValueError):
                    packet(address, command)

    def test_clock_sources_and_deep_default(self):
        result = diagnostics.clock_summary({'show t t': 'Time NOT SET\nUpTime=919 s\nRTC=919\nRAW=1cbd7da',
                                            'get time': 'TimeEna=0\nZone=7'})
        self.assertEqual(result['Status'], 'Unset')
        self.assertEqual(result['RTC counter'], '919')
        self.assertEqual(result['Calendar UTC'], 'Not reported')
        self.assertIn('UTC-07:00', result['Zone interpretation'])
        dated = diagnostics.clock_summary({'show t t': 'Time=00:00:00\nRTC=1704067200'})
        self.assertIn('2024-01-01T00:00:00', dated['Calendar UTC'])
        self.assertEqual(result['Zone setting (raw)'], '7')
        self.assertEqual(result['Time server'], 'Not reported')
        self.assertLess(len(diagnostics.endpoint_catalog()), len(diagnostics.endpoint_catalog(True)))
        self.assertNotIn('get everything', [q for _, q in diagnostics.endpoint_catalog()])

    def test_extended_decoders_and_axis_scope(self):
        from celestron_probe import packet
        from wifly_configure import sanitize
        self.assertIn('90.00000', diagnostics.decode_motor_setting(0x3c, bytes.fromhex('400000')))
        self.assertIn('Yes', diagnostics.decode_motor_setting(0x3b, b'\xff'))
        self.assertIn('3D fix', diagnostics.decode_time_site(8, bytes.fromhex('e000'))[1])
        self.assertIn('unverified', diagnostics.decode_time_site(0x55, b'\xab')[1])
        self.assertNotIn('secret123', sanitize('FTP Pass=secret123'))
        for device, command in ((0x11, 0x3b), (0x11, 0x3c), (0x10, 0x12), (0x11, 0x18)):
            with self.assertRaises(ValueError):
                packet(device, command)
        for command, raw in ((0x3c, b'\x00'), (0x3b, b'\x01'), (0xfc, b'\xff')):
            with self.assertRaises(ValueError):
                diagnostics.decode_motor_setting(command, raw)

    def test_invalid_reply_does_not_hide_other_optional_fields(self):
        probe = MagicMock()
        probe.query.side_effect = [b'\x00', b'\x01', bytes(3), bytes.fromhex('c00000'),
                                   b'\x02\x1e', b'\x07\xea', b'\x0c\x22\x38',
                                   b'\x08\x05', b'\x0b', b'\xe0\x00', b'\xab', None, b'\x07\xea', b'\x0c\x22\x38']
        rows = []
        result = diagnostics.read_time_site(probe, lambda *args: rows.append(args), deep=True)
        self.assertEqual(result['0xB0']['DATE']['status'], 'INVALID REPLY')
        self.assertFalse(result['0xB0']['TIME_VALID']['value'])
        self.assertEqual(result['0xB0']['LONGITUDE']['value'], -90)
        self.assertEqual(result['0xB2']['UTC_TIME']['value'], [12, 34, 56])
        self.assertEqual(len(rows), 14)

    def run_diagnostic(self, missing=None):
        Probe.missing_axis = missing
        Probe.calls = []
        Session.commands = []
        events = []
        with patch.object(diagnostics, 'LiveRecorder', Recorder), \
             patch.object(diagnostics, 'check_direct_route'), \
             patch.object(diagnostics.socket, 'create_connection', return_value=MagicMock()), \
             patch.object(diagnostics, 'Session', Session), \
             patch.object(diagnostics, 'AuxProbe', Probe):
            report = diagnostics.diagnose('192.0.2.231', 2000, events.append, deep=True)
        return report, events

    def test_valid_zero_positions_and_optional_node_timeout(self):
        report, events = self.run_diagnostic()
        self.assertTrue(report['wifi_verified'])
        self.assertTrue(report['motor_positions_verified'])
        self.assertTrue(report['motor_firmware_verified'])
        self.assertFalse(report['settings_changed'])
        self.assertFalse(report['movement_sent'])
        self.assertEqual(Session.commands, list(diagnostics.WIFI_QUERIES))
        self.assertTrue(all(command in (1, 0x12, 0x13, 0x15, 0x18, 0x3b, 0x3c, 0x40, 0x41, 0x47, 0xfc, 0xfe)
                            for axis, command in Probe.calls if axis in (0x10, 0x11)))
        self.assertEqual(len(report['time_site']['0xB0']), 11)
        self.assertTrue(all(v['status'] == 'NO REPLY' for v in report['time_site']['0xB0'].values()))
        self.assertEqual(len([e for e in events if e['event'] == 'diagnostic_position']), 4)
        self.assertNotIn('test-secret', str(report) + str(events))

    def test_unreachable_session_lists_unqueried_catalog(self):
        with patch.object(diagnostics, 'LiveRecorder', Recorder), \
             patch.object(diagnostics, 'check_direct_route', side_effect=OSError('offline')):
            report = diagnostics.diagnose('192.0.2.232', 2000)
        self.assertEqual(sum(r['status'] == 'NOT QUERIED' for r in report['rows']),
                         len(diagnostics.endpoint_catalog()))
        self.assertFalse(report['motor_positions_verified'])

    def test_missing_motor_never_reports_positions_verified(self):
        report, events = self.run_diagnostic(0x11)
        self.assertTrue(report['wifi_verified'])
        self.assertFalse(report['motor_positions_verified'])
        self.assertFalse(report['motor_firmware_verified'])
        self.assertTrue(any(r['device'] == 'Elevation motor' and r['status'] == 'NO VALID REPLY'
                            for r in report['rows']))
