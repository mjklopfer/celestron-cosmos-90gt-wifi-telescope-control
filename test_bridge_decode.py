"""Decode only known device-scoped AUX meanings; no telescope IO."""
import unittest
from bridge_decode import describe_aux


def frame(src, dst, command, data=b''):
    body = bytes((len(data) + 3, src, dst, command)) + data
    return b'\x3b' + body + bytes((-sum(body) & 255,))


class DecodeTests(unittest.TestCase):
    def test_targets_are_not_tracking_rates_or_encoder_resets(self):
        self.assertIn('GoTo fast', describe_aux(frame(32, 16, 2, b'\x40\x00\x00')))
        self.assertIn('90.000000° raw motor angle', describe_aux(frame(32, 16, 2, b'\x40\x00\x00')))
        self.assertIn('guide/tracking rate', describe_aux(frame(32, 17, 6, b'\x00\x05\x23')))
        self.assertNotIn('GoTo', describe_aux(frame(32, 17, 6, b'\x00\x05\x23')))
        self.assertIn('encoder reference', describe_aux(frame(32, 16, 4, b'\x00\x00\x00')))

    def test_device_scoping_and_unknowns(self):
        self.assertIn('Read year', describe_aux(frame(32, 0xb0, 4)))
        self.assertNotIn('encoder', describe_aux(frame(32, 0xb0, 4)))
        self.assertIn('Unknown', describe_aux(frame(32, 16, 0x83, b'\x01\x01')))
        self.assertIn('Unknown', describe_aux(frame(32, 0xb0, 0x83, b'\x01\x01')))
        self.assertIn('Set RTC month/day', describe_aux(frame(32, 0xb2, 0x83, b'\x01\x01')))
        self.assertIn('Set GoTo approach request/echo: negative approach', describe_aux(frame(32, 17, 0xfd, b'\x01')))
        self.assertIn('Unknown command 0x21', describe_aux(frame(16, 32, 0x21, b'\x0c\xb2')))

    def test_reply_echo_and_invalid_data(self):
        self.assertIn('5.24', describe_aux(frame(16, 32, 0xfe, b'\x05\x18')))
        self.assertIn('request/echo', describe_aux(frame(32, 16, 0x24, b'\x00')))
        self.assertIn('STOP', describe_aux(frame(32, 16, 0x24, b'\x00')))
        self.assertIn('reply', describe_aux(frame(16, 32, 0x24, b'\x01')))
        self.assertIn('Unexpected payload', describe_aux(frame(16, 32, 0xfc, b'\xff')))
        self.assertIn('UTC time reply: 12:30:45', describe_aux(frame(0xb0, 32, 0x33, bytes((12, 30, 45)))))
