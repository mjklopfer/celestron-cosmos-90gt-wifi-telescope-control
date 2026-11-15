"""Regression checks for recover link. No real telescope is connected."""
import unittest
from unittest.mock import MagicMock, patch
import recover_link
from test_diagnostics import Recorder


class RecoveryTests(unittest.TestCase):
    def perform(self, identity='WiFly Ver 2.40-CEL on RN-171', uart_error=False):
        sessions = []
        class Session:
            def __init__(self, sock, recorder):
                self.entered = False
                self.exits = 0
                sessions.append(self)
            def enter(self):
                self.entered = True
            def command(self, command):
                if command == 'ver':
                    return identity
                if uart_error:
                    raise RuntimeError('UART query failed')
                return 'Baudrate=19200'
            def receive(self, timeout):
                raise ConnectionError('Restart closed connection')
            def exit(self):
                self.entered = False
                self.exits += 1
                return True
        sock = MagicMock()
        context = MagicMock()
        context.__enter__.return_value = sock
        probe = MagicMock()
        probe.query.return_value = b'\x00\x7c\x73'
        with patch.object(recover_link.socket, 'create_connection', return_value=context), \
             patch.object(recover_link, 'Session', Session), \
             patch.object(recover_link, 'LiveRecorder', Recorder), \
             patch.object(recover_link, 'AuxProbe', return_value=probe), \
             patch.object(recover_link.time, 'sleep'):
            report = recover_link.recover('192.0.2.150')
        return report, sock, sessions[0]

    def test_identified_restart_sends_no_configuration_or_motion_writes(self):
        report, sock, session = self.perform()
        self.assertTrue(report['restart_sent'])
        self.assertTrue(report['motor_positions_verified'])
        self.assertFalse(report['configuration_writes_sent'])
        self.assertFalse(report['movement_sent'])
        sock.sendall.assert_called_once_with(b'reboot\r')

    def test_unrecognized_module_exits_command_mode_without_restart(self):
        report, sock, session = self.perform('WiFly Ver 4.0 on RN-131')
        self.assertFalse(report['restart_sent'])
        self.assertEqual(session.exits, 1)
        sock.sendall.assert_not_called()

    def test_failed_pre_restart_query_still_exits_command_mode(self):
        report, sock, session = self.perform(uart_error=True)
        self.assertEqual(report['error'], 'UART query failed')
        self.assertFalse(report['restart_sent'])
        self.assertEqual(session.exits, 1)
        sock.sendall.assert_not_called()
