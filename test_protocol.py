"""Regression checks for protocol. No real telescope is connected."""
import unittest

from celestron_probe import FrameParser, packet


def response(source, command, data=b''):
    body = bytes((len(data) + 3, source, 0x20, command)) + data
    return b'\x3b' + body + bytes((-sum(body) & 255,))


class ProtocolTests(unittest.TestCase):
    def test_split_frame_with_adapter_text_and_echo(self):
        parser = FrameParser()
        reply = response(0x10, 1, b'\x00\x00\x01')
        self.assertEqual(parser.feed(b'*HELLO*' + reply[:4]), [])
        self.assertEqual(parser.feed(reply[4:] + b'*CLOS*'), [reply])

    def test_checksum_failure_resynchronizes(self):
        parser = FrameParser()
        good = response(0x11, 0xfe, b'\x01\x02')
        bad = good[:-1] + bytes((good[-1] ^ 1,))
        self.assertEqual(parser.feed(b'\x3b\xff' + bad + good), [good])

    def test_multiple_frames_in_one_tcp_read(self):
        first, second = response(0x10, 1, bytes(3)), response(0x11, 1, bytes(3))
        self.assertEqual(FrameParser().feed(first + second), [first, second])

    def test_read_packet_and_motion_rejection(self):
        self.assertEqual(packet(0x10, 1).hex(), '3b03201001cc')
        for command in (0x02, 0x04, 0x17, 0x24, 0x25):
            with self.assertRaises(ValueError):
                packet(0x10, command)

    def test_time_reads_are_destination_scoped_and_writes_blocked(self):
        for device in (0xb0, 0xb2):
            for command in (3, 4, 0x33):
                wire = packet(device, command)
                self.assertEqual(wire[2:5], bytes((0x20, device, command)))
                self.assertEqual(sum(wire[1:]) & 255, 0)
            for command in (0x83, 0x84, 0xb3, 0x24, 0x25):
                with self.assertRaises(ValueError):
                    packet(device, command)
        for device in (0x10, 0x11):
            with self.assertRaises(ValueError):
                packet(device, 4)


if __name__ == '__main__':
    unittest.main()
