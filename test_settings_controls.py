"""No-hardware validation of explicit setting writes and reply checks."""
import unittest
from unittest.mock import MagicMock, patch
import motor_settings as ms
import time_settings as ts
from test_diagnostics import Recorder


class SettingTests(unittest.TestCase):
    def test_modern_missing_backlash_preserves_position(self):
        probe = MagicMock()
        probe.query.side_effect = [bytes.fromhex('400000'), b'\x00', None]
        with patch.object(ms, 'LiveRecorder', Recorder), patch.object(ms, 'check_direct_route'), patch.object(ms, 'AuxProbe', return_value=probe):
            result = ms.motor_settings('192.0.2.1', 2000, 0x10, interface_mode='modern')
        self.assertNotIn('error', result)
        self.assertEqual(result['values']['degrees'], 90)
        self.assertIsNone(result['values']['negative_backlash'])
        probe.sock.sendall.assert_not_called()

    def test_modern_missing_backlash_blocks_write(self):
        probe = MagicMock()
        probe.query.side_effect = [b'\x00', None]
        with patch.object(ms, 'LiveRecorder', Recorder), patch.object(ms, 'check_direct_route'), patch.object(ms, 'AuxProbe', return_value=probe):
            result = ms.motor_settings('192.0.2.1', 2000, 0x10, interface_mode='modern', changes={0x10: 5})
        self.assertIn('error', result)
        probe.sock.sendall.assert_not_called()

    def test_proxy_mode_rejected_before_socket(self):
        with patch.object(ms, 'AuxProbe') as probe, self.assertRaises(ValueError):
            ms.motor_settings('192.0.2.1', 2000, 0x10, interface_mode='proxy')
        probe.assert_not_called()

    def test_extended_packets_reject_wrong_axes_and_values(self):
        self.assertEqual(ms.setting_packet(0x10, 0x38, None)[5:-1], b'')
        self.assertEqual(ms.setting_packet(0x11, 0xFD, 1)[5:-1], b'\x01')
        for axis, command, value in ((0x11, 0x38, None), (0x11, 0x3A, 90), (0x10, 0xFD, 2), (0x10, 0x38, 1)):
            with self.assertRaises(ValueError):
                ms.setting_packet(axis, command, value)

    def test_unsupported_approach_does_not_write(self):
        probe = MagicMock()
        probe.query.return_value = None
        with patch.object(ms, 'LiveRecorder', Recorder), patch.object(ms, 'check_direct_route'), patch.object(ms, 'AuxProbe', return_value=probe):
            result = ms.motor_settings('192.0.2.1', 2000, 0x11, changes={0xFD: 1})
        self.assertIn('error', result)
        probe.sock.sendall.assert_not_called()

    def test_cordwrap_and_approach_write_readback_for_both_profiles(self):
        for profile in ('legacy', 'modern'):
            for command, value in ((0x38, None), (0x39, None), (0x3A, 90), (0xFD, 1)):
                with self.subTest(profile=profile, command=command):
                    state = {1: bytes(3), 0x40: b'\x00', 0x41: b'\x00', 0xFC: b'\x00', 0x3B: b'\x00', 0x3C: bytes(3)}
                    probe = MagicMock()
                    probe.query.side_effect = lambda axis, cmd, state=state, **kw: state[cmd]
                    probe.receive.return_value = b''
                    def write(packet, state=state):
                        cmd = packet[4]
                        key = {0x38: 0x3B, 0x39: 0x3B, 0x3A: 0x3C, 0xFD: 0xFC}[cmd]
                        state[key] = b'\xff' if cmd == 0x38 else b'\x00' if cmd == 0x39 else packet[5:-1]
                    probe.sock.sendall.side_effect = write
                    with patch.object(ms, 'LiveRecorder', Recorder), patch.object(ms, 'check_direct_route'), patch.object(ms, 'AuxProbe', return_value=probe), patch.object(ms.time, 'sleep'):
                        result = ms.motor_settings('192.0.2.1', 2000, 0x10, changes={command: value}, interface_mode=profile, include_extended=True)
                    self.assertNotIn('error', result)
                    self.assertTrue(result['writes'][0]['verified'])

    def test_backlash_normalization_rejects_fraction_and_wrong_sign(self):
        for text, expected in [(' 002.0 ', 2), ('+99', 99), ('0', 0)]:
            self.assertEqual(ms.parse_backlash(text), expected)
        self.assertEqual(ms.parse_backlash('-2.0', delta=True), -2)
        for text in ('-2', '-0.2', '2.3', '1e1', '100', '-0', ''):
            with self.assertRaises(ValueError):
                ms.parse_backlash(text)

    def test_changed_backlash_blocks_delta_write(self):
        probe = MagicMock()
        probe.query.side_effect = [bytes(3)] * 4 + [bytes([11]), bytes([10])]
        with patch.object(ms, 'LiveRecorder', Recorder), patch.object(ms, 'check_direct_route'), patch.object(ms, 'AuxProbe', return_value=probe):
            result = ms.motor_settings('192.0.2.1', 2000, 0x10, changes={0x10: 12}, expected_backlash=(10, 10))
        self.assertIn('changed since', result['error'])
        self.assertEqual(result['writes'], [])
        probe.sock.sendall.assert_not_called()

    def test_degree_input_format_and_axis_ranges(self):
        for text, expected in [('060.84', 60.84), (' +100.52 ', 100.52), ('360', 360), ('.5', .5)]:
            self.assertEqual(ms.parse_degrees(text, 0, 360), expected)
        self.assertEqual(ms.parse_degrees('-60.31', -90, 90), -60.31)
        for text in ('', '-', 'NaN', 'inf', '1e2', '1,2', '30 deg', '1.123456', '-0.01', '360.01'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                ms.parse_degrees(text, 0, 360)
        for axis, value in ((0x10, -.01), (0x11, 90.01), (0x11, -90.01)):
            with self.subTest(axis=axis, value=value), self.assertRaises(ValueError):
                ms.setting_packet(axis, 4, value)
        for value in (-90, 0, 90):
            ms.setting_packet(0x11, 4, value)

    def test_motor_packet_bounds_and_axis(self):
        self.assertEqual(ms.setting_packet(0x10, 4, 90)[5:-1], bytes.fromhex('400000'))
        self.assertEqual(ms.setting_packet(0x11, 4, -90)[5:-1], bytes.fromhex('c00000'))
        for command, value in ((4, float('nan')), (4, 361), (0x10, 100), (0x11, -1), (0x24, 1)):
            with self.assertRaises(ValueError):
                ms.setting_packet(0x10, command, value)
        with self.assertRaises(ValueError):
            ms.setting_packet(0x12, 4, 0)

    def test_moving_motor_blocks_write(self):
        probe = MagicMock()
        probe.query.side_effect = [bytes(3), bytes(3), bytes.fromhex('000100'), bytes(3)]
        with patch.object(ms, 'LiveRecorder', Recorder), patch.object(ms, 'check_direct_route'), patch.object(ms, 'AuxProbe', return_value=probe):
            report = ms.motor_settings('192.0.2.234', 2000, 0x10, changes={4: 90})
        self.assertIn('movement detected', report['error'])
        probe.sock.sendall.assert_not_called()

    def test_write_needs_ack_and_matching_readback(self):
        probe = MagicMock()
        probe.query.side_effect = [bytes(3)] * 4 + [b'\x04']
        probe.receive.return_value = b''
        with patch.object(ms, 'LiveRecorder', Recorder), patch.object(ms, 'check_direct_route'), patch.object(ms, 'AuxProbe', return_value=probe):
            report = ms.motor_settings('192.0.2.234', 2000, 0x10, changes={0x10: 5})
        self.assertIn('readback mismatch', report['error'])
        self.assertFalse(report['writes'][0]['verified'])

    def time_report(self, *, mismatch=False, **kwargs):
        session = MagicMock()
        calls = []
        def command(q, **options):
            calls.append(q)
            if q == 'ver':
                return 'RN-171 WiFly 2.40-CEL'
            if q == 'get time':
                return 'TimeEna=' + ('0' if mismatch else '1') + '\nTIMEADR=192.0.2.1:123\nZone=7'
            if q == 'save':
                return 'Storing in config\n<2.40-CEL>'
            return 'Time NOT SET\nRTC=123'
        session.command.side_effect = command
        with patch.object(ts, 'LiveRecorder', Recorder), patch.object(ts, 'check_direct_route'), patch.object(ts.socket, 'create_connection', return_value=MagicMock()), patch.object(ts, 'Session', return_value=session):
            report = ts.configure_time('192.0.2.235', enable=1, **kwargs)
        return report, calls

    def test_time_readback_mismatch_prevents_save(self):
        report, calls = self.time_report(mismatch=True, persist=True)
        self.assertIn('mismatch', report['error'])
        self.assertNotIn('save', calls)

    def test_time_server_verified_before_optional_save(self):
        report, calls = self.time_report(server_ip='192.0.2.1', persist=True)
        self.assertTrue(report['applied'])
        self.assertTrue(report['saved'])
        self.assertFalse(report['clock_text_available'])
        self.assertLess(calls.index('set time address 192.0.2.1'), calls.index('save'))
        self.assertNotIn('time', calls)

    def test_invalid_ntp_reply_rejected(self):
        sock = MagicMock()
        sock.__enter__.return_value = sock
        sock.recv.return_value = bytes(48)
        with patch.object(ts.socket, 'getaddrinfo', return_value=[(2, 2, 17, '', ('192.0.2.1', 123))]), patch.object(ts.socket, 'socket', return_value=sock):
            with self.assertRaises(ValueError):
                ts.test_time_server('time.example.org')
