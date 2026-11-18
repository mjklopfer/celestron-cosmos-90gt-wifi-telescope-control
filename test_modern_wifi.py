import unittest
from unittest.mock import MagicMock, patch
import modern_wifi as m

class ModernWifiTests(unittest.TestCase):
    def test_invalid_input_never_connects(self):
        for ssid, password, security in [('x\nsave','abcdefgh','Personal (automatic)'), ('x','abc','Personal (automatic)'), ('x','abcdefgh','Open (no password)'), ('x','abcdefgh','WEP'), ('x"','abcdefgh','Personal (automatic)')]:
            with self.subTest(ssid=ssid,password=password), patch.object(m.socket,'create_connection') as connect, self.assertRaises(ValueError):
                m.configure('192.0.2.1',ssid=ssid,password=password,security=security)
            connect.assert_not_called()

    def run_reply(self, replies, **kwargs):
        with patch.object(m,'EndpointLease'), patch.object(m.socket,'create_connection') as connect, patch.object(m.Management,'command',side_effect=replies) as command:
            connect.return_value.__enter__.return_value = MagicMock()
            result = m.configure('192.0.2.1',**kwargs)
        return result, [c.args[0] for c in command.call_args_list]

    def test_success_checks_ssid_and_saves_last(self):
        result, commands = self.run_reply(['COSMOS-SIM-AMW007-0.2.3.0','1','Old','Set OK','Set OK','Set OK','Set OK','New','Success'],ssid='New',password='abcdefgh')
        self.assertEqual(commands[-2:], ['get wlan.ssid','save'])
        self.assertNotIn('abcdefgh',str(result))
        self.assertTrue(result['saved'])
        self.assertFalse(result['network_join_verified'])

    def test_old_firmware_no_write(self):
        with self.assertRaises(ValueError):
            self.run_reply(['COSMOS-SIM-AMW007-0.2.2.0','ERR unsupported'],ssid='New',password='abcdefgh')

    def test_proxy_rejected(self):
        with self.assertRaises(ValueError):
            self.run_reply(['COSMOSBridge-AMW007-1'],ssid='New',password='abcdefgh')

    def test_failed_ack_does_not_save_or_expose_reply(self):
        with patch.object(m,'EndpointLease'), patch.object(m.socket,'create_connection'), patch.object(m.Management,'command',side_effect=['COSMOS-SIM-AMW007-0.2.3.0','1','Old','Set OK','ERR abcdefgh']) as command:
            with self.assertRaises(ValueError) as error:
                m.configure('192.0.2.1',ssid='New',password='abcdefgh')
            self.assertNotIn('abcdefgh',str(error.exception))
            self.assertNotIn('save',[c.args[0] for c in command.call_args_list])

    def test_read_does_not_fetch_password(self):
        result, commands = self.run_reply(['COSMOS-SIM-AMW007-0.2.3.0','1','Network'])
        self.assertEqual(result['ssid'],'Network')
        self.assertFalse(any('passkey' in c for c in commands))

    def test_open_network(self):
        m.validate_settings('Network','','Open (no password)')

    def test_commercial_requires_opt_in(self):
        with self.assertRaises(ValueError):
            self.run_reply(['AMW007 version'])
        result, commands = self.run_reply(['AMW007 version','Network'],allow_commercial=True)
        self.assertEqual(result['ssid'],'Network')
        self.assertNotIn('get cosmos.wifi.config',commands)
