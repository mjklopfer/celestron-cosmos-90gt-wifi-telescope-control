"""Verify diagnostic classification and read-only query coverage without hardware."""
from pathlib import Path
import unittest
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
    def query(self, axis, command):
        self.calls.append((axis, command))
        if axis == self.missing_axis or axis == 0xb5:
            return None
        return b'\x05\x18' if command == 0xfe else b'\x00\x00\x00'
    def close(self):
        pass


class DiagnosticTests(unittest.TestCase):
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
            report = diagnostics.diagnose('192.0.2.231', 2000, events.append)
        return report, events

    def test_valid_zero_positions_and_optional_node_timeout(self):
        report, events = self.run_diagnostic()
        self.assertTrue(report['wifi_verified'])
        self.assertTrue(report['motor_positions_verified'])
        self.assertTrue(report['motor_firmware_verified'])
        self.assertFalse(report['settings_changed'])
        self.assertFalse(report['movement_sent'])
        self.assertEqual(Session.commands, list(diagnostics.WIFI_QUERIES))
        self.assertTrue(all(command in (1, 0xfe) for axis, command in Probe.calls))
        self.assertEqual(len([e for e in events if e['event'] == 'diagnostic_position']), 4)
        self.assertNotIn('test-secret', str(report) + str(events))

    def test_missing_motor_never_reports_positions_verified(self):
        report, events = self.run_diagnostic(0x11)
        self.assertTrue(report['wifi_verified'])
        self.assertFalse(report['motor_positions_verified'])
        self.assertFalse(report['motor_firmware_verified'])
        self.assertTrue(any(r['device'] == 'Altitude' and r['status'] == 'NO VALID REPLY'
                            for r in report['rows']))
