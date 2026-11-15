"""Regression checks for wifly configure. No real telescope is connected."""
import unittest
from wifly_configure import configure, make_plan, sanitize


class FakeSession:
    def __init__(self, reject=None, ssid='Test network', dhcp='ON', auth='WPA2'):
        self.commands = []
        self.reject, self.ssid, self.dhcp = reject, ssid, dhcp
        self.auth = auth
        self.secrets = ('example password',)

    def command(self, command, **kwargs):
        self.commands.append(command)
        if command == self.reject:
            raise RuntimeError('Adapter rejected command')
        if command == 'get wlan':
            return f'SSID={self.ssid}\r\nJoin=1\r\nChan=0\r\nAuth={self.auth}\r\n<2.40-CEL> '
        if command == 'get ip':
            return f'DHCP={self.dhcp}\r\n<2.40-CEL> '
        if command == 'save':
            return 'Storing in config\r\n<2.40-CEL> '
        return 'AOK\r\n<2.40-CEL> '


class ConfigTests(unittest.TestCase):
    def report(self):
        return {'before': {'get option': 'Replace=0x24\r\n'}, 'saved': False}

    def test_space_encoding_avoids_literal_collision(self):
        plan = make_plan('Test % network', 'Example pass!')
        self.assertEqual(plan[0][0], 'set opt replace 0x7e')
        self.assertIn(('set wlan ssid Test~%~network', False), plan)

    def test_injection_and_bad_lengths_are_rejected(self):
        for ssid, password in [('test\rreboot', 'example pass'), ('net', 'bad\npass'), ('x'*33, 'example pass'), ('net', 'short')]:
            with self.assertRaises(ValueError):
                make_plan(ssid, password)

    def test_credentials_and_echo_redacted(self):
        raw = 'set wlan phrase example%password\r\nAOK\r\nPassphrase=other\r\nSSID=Test\r\n'
        result = sanitize(raw, ('example password', 'example%password'))
        self.assertNotIn('example', result)
        self.assertNotIn('other', result)
        self.assertIn('SSID=Test', result)

    def test_success_verifies_before_save_and_restores_encoding(self):
        session, report = FakeSession(), self.report()
        configure(session, 'Test network', 'example password', report)
        self.assertTrue(report['saved'])
        self.assertLess(session.commands.index('get ip'), session.commands.index('save'))
        self.assertIn('set opt replace 0x24', session.commands)
        self.assertNotIn('example password', str(report))
        self.assertNotIn('example%password', str(report))

    def test_rejected_write_never_saves(self):
        session, report = FakeSession(reject='set wlan auth 4'), self.report()
        with self.assertRaises(RuntimeError):
            configure(session, 'Test network', 'example password', report)
        self.assertNotIn('save', session.commands)
        self.assertFalse(report['saved'])

    def test_failed_readback_never_saves(self):
        for session in (FakeSession(ssid='Wrong'), FakeSession(dhcp='SERVER'), FakeSession(auth='OPEN')):
            report = self.report()
            with self.assertRaises(RuntimeError):
                configure(session, 'Test network', 'example password', report)
            self.assertNotIn('save', session.commands)

    def test_open_mode_does_not_send_a_password(self):
        plan = make_plan('Open network', '', 'Open (no password)')
        self.assertIn(('set wlan auth 0', False), plan)
        self.assertFalse(any(secret for _, secret in plan))
        session, report = FakeSession(ssid='Open network', auth='OPEN'), self.report()
        configure(session, 'Open network', '', report, 'Open (no password)')
        self.assertTrue(report['saved'])

    def test_wpa_mode(self):
        plan = make_plan('Test network', 'example password', 'WPA-Personal (TKIP)')
        self.assertIn(('set wlan auth 2', False), plan)
        session, report = FakeSession(auth='WPA1'), self.report()
        configure(session, 'Test network', 'example password', report, 'WPA-Personal (TKIP)')
        self.assertTrue(report['saved'])


if __name__ == '__main__':
    unittest.main()
