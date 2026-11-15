import unittest
from setup_backend import clean, validate_endpoint
from wifly_configure import Session


class BackendTests(unittest.TestCase):
    def test_editable_ip_and_port_validation(self):
        self.assertEqual(validate_endpoint('192.168.1.150', '2222'), ('192.168.1.150', 2222))
        for host, port in [('127.0.0.1', 2000), ('1.2.3.4', 0), ('1.2.3.4', 65536),
                           ('1.2.3.4', 'abc'), ('invalid', 2000)]:
            with self.assertRaises(ValueError):
                validate_endpoint(host, port)

    def test_nested_report_scrubbing(self):
        result = clean({'events': [{'text': 'a demo-secret value'}]}, ['demo-secret'])
        self.assertNotIn('demo-secret', str(result))

    def test_fragmented_password_echo_never_logged(self):
        class Socket:
            parts = iter((b'set wlan phrase test', b'Secret42\r\nAOK\r\n', b'<2.40-CEL> '))
            def recv(self, size):
                return next(self.parts)
        class Recorder:
            events = []
            def record(self, kind, **fields):
                self.events.append(fields)
        recorder = Recorder()
        reply = Session(Socket(), recorder, ['testSecret42']).receive()
        self.assertIn('AOK', reply)
        self.assertNotIn('testSecret42', str(recorder.events))
        self.assertNotIn('test', str(recorder.events))

    def test_status_value_fail_is_displayed_as_data_not_command_rejection(self):
        class Socket:
            def sendall(self, data):
                pass
            def recv(self, size):
                return b'show net\r\nAssoc=OK\r\nTime=FAIL\r\n<2.40-CEL> '
        class Recorder:
            def record(self, *args, **kwargs):
                pass
        reply = Session(Socket(), Recorder()).command('show net')
        self.assertIn('Time=FAIL', reply)


if __name__ == '__main__':
    unittest.main()
