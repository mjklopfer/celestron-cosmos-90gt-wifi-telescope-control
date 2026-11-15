"""Bridge integration tests use loopback and a simulated telescope only."""
import json
import queue
import socket
import threading
import time
import unittest
from unittest.mock import patch
from bridge_mode import Bridge
from celestron_probe import FrameParser
from endpoint_lock import EndpointLease, EndpointBusy
from motor_control import motor_packet
from test_motor_control import FakeRecorder


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen()
        self.listener.settimeout(.1)
        self.halt = threading.Event()
        self.frames = []
        self.drop_positions = 0
        self.positions = {16: 12345, 17: 67890}
        self.events = queue.Queue()
        self.patch = patch('bridge_mode.Recorder', FakeRecorder)
        self.patch.start()
        self.server = threading.Thread(target=self.serve, daemon=True)
        self.server.start()
        self.bridge = Bridge('192.0.2.231', 2000, self.events.put, bind_host='127.0.0.1',
                             listen_port=0, management_port=0, advertise=False,
                             socket_factory=lambda address, timeout: socket.create_connection(self.listener.getsockname(), timeout))
        self.bridge.start()
        self.wait('bridge_ready')

    def serve(self):
        connection = None
        try:
            while not self.halt.is_set():
                try:
                    connection, _ = self.listener.accept()
                    break
                except socket.timeout:
                    continue
            if connection is None:
                return
            connection.settimeout(.1)
            parser = FrameParser()
            while not self.halt.is_set():
                try:
                    raw = connection.recv(4096)
                except socket.timeout:
                    continue
                if not raw:
                    break
                for frame in parser.feed(raw):
                    self.frames.append(frame)
                    axis, command = frame[3:5]
                    if command == 1 and self.drop_positions:
                        self.drop_positions -= 1
                        continue
                    data = (b'\x05\x18' if command == 0xfe else self.positions[axis].to_bytes(3, 'big')
                            if command == 1 else b'')
                    body = bytes((3 + len(data), axis, frame[2], command)) + data
                    reply = b'\x3b' + body + bytes((-sum(body) & 255,))
                    connection.sendall(reply[:2])
                    connection.sendall(reply[2:])
        except OSError:
            pass
        finally:
            if connection:
                connection.close()

    def wait(self, kind, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                event = self.events.get(timeout=.05)
            except queue.Empty:
                continue
            if event['event'] == 'bridge_error':
                self.fail(event['message'])
            if event['event'] == kind:
                return event
        self.fail('Missing event: ' + kind)

    def tearDown(self):
        self.bridge.stop()
        self.bridge.thread.join(5)
        self.assertFalse(self.bridge.thread.is_alive())
        self.halt.set()
        self.listener.close()
        self.server.join(2)
        self.patch.stop()

    def connect(self, port):
        return socket.create_connection(('127.0.0.1', port), 2)

    def test_forwarding_split_packets_encoder_readback_and_no_competing_poll(self):
        with self.connect(self.bridge.listen_port) as client:
            client.settimeout(2)
            self.wait('bridge_client')
            # Let an idle poll already in flight finish before checking ownership.
            time.sleep(.2)
            before = len(self.frames)
            time.sleep(1.2)
            self.assertEqual(len(self.frames), before)
            packet = motor_packet(16, 1)
            client.sendall(packet[:3])
            client.sendall(packet[3:])
            parser = FrameParser()
            deadline = time.monotonic() + 2
            reply = None
            while time.monotonic() < deadline and reply is None:
                for frame in parser.feed(client.recv(4096)):
                    if frame[2:5] == b'\x10\x20\x01':
                        reply = frame
            self.assertIsNotNone(reply)
            self.assertEqual(int.from_bytes(reply[5:-1], 'big'), 12345)
            self.assertIn(packet, self.frames)
        self.wait('bridge_client')
        deadline = time.monotonic() + 1
        while not self.bridge.report['stop_attempts'] and time.monotonic() < deadline:
            time.sleep(.01)
        while not any(f[4:6] == b'\x24\x00' for f in self.frames) and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(any(f[4:6] == b'\x24\x00' for f in self.frames))

    def test_single_idle_timeout_keeps_bridge_alive_and_recovers(self):
        self.drop_positions = 1
        event = self.wait('bridge_status', timeout=5)
        self.assertIn('reply delayed', event['message'])
        self.wait('bridge_values', timeout=5)
        self.assertTrue(self.bridge.thread.is_alive())

    def test_repeated_idle_timeouts_still_fail_closed(self):
        self.drop_positions = 100
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            event = self.events.get(timeout=4)
            if event['event'] == 'bridge_error':
                self.assertIn('three consecutive polls', event['message'])
                break
        else:
            self.fail('Repeated missing replies did not stop bridge')

    def test_endpoint_exclusion_off_stops_and_releases(self):
        other = EndpointLease('192.0.2.231', 2000)
        with self.assertRaises(EndpointBusy):
            other.acquire()
        self.bridge.stop()
        self.wait('bridge_off')
        self.bridge.thread.join(2)
        self.assertEqual(self.bridge.report['cleanup_stop_replies'], {'16': True, '17': True})
        with other:
            pass
        self.assertTrue(all(any(f[3] == axis and f[4:6] == b'\x24\x00' for f in self.frames) for axis in (16, 17)))

    def test_management_read_only_and_credentials_not_logged(self):
        with self.connect(self.bridge.management_port) as client:
            client.settimeout(2)
            client.sendall(b'get all\n')
            raw = client.recv(4096)
            self.assertIn(b'wlan.dhcp.enabled: 1', raw)
            client.sendall(b'set wlan.passkey secret-to-never-log\n')
            self.assertIn(b'ERR Unsupported', client.recv(4096))
        self.assertNotIn('secret-to-never-log', repr(self.bridge.recorder.events))
        self.assertFalse(any(f[4] in (0x24, 0x25) and f[5] > 0 for f in self.frames))

    def test_second_client_is_rejected(self):
        with self.connect(self.bridge.listen_port):
            self.wait('bridge_client')
            with self.connect(self.bridge.listen_port) as second:
                second.settimeout(2)
                self.assertEqual(second.recv(1), b'')

    def test_discovery_packet_has_proxy_identity_and_expected_udp_destination(self):
        sent = queue.Queue()
        class UDP:
            def sendto(self, payload, destination):
                sent.put((payload, destination))
            def close(self):
                pass
        self.bridge.udp = UDP()
        payload, destination = sent.get(timeout=3)
        data = json.loads(payload)
        self.assertEqual(destination, ('255.255.255.255', 55555))
        self.assertEqual(data['mac'], self.bridge.mac)
        self.assertIn('AMW007', data['version'])


class BridgeConfigurationTests(unittest.TestCase):
    def test_direct_requires_explicit_dual_interface_opt_in_and_other_lan(self):
        for options in ({}, {'allow_direct_upstream': True},
                        {'allow_direct_upstream': True, 'bind_host': '1.2.3.10'}):
            with self.assertRaises(ValueError):
                Bridge('1.2.3.4', **options)
        bridge = Bridge('1.2.3.4', allow_direct_upstream=True, bind_host='192.168.1.30')
        self.assertEqual(bridge.bind_host, '192.168.1.30')

    def test_advertisement_identity_and_management_are_distinct_from_real_firmware(self):
        from bridge_mode import IDENTITY
        bridge = Bridge('192.0.2.231', bind_host='127.0.0.1')
        self.assertIn('AMW007', IDENTITY)
        self.assertTrue(bridge.mac.startswith('02:'))
        self.assertIn('ERR', bridge.management_reply('save'))
        self.assertIn('ERR', bridge.management_reply('reset'))
