"""Experimental single-client Celestron AUX LAN bridge. Explicit start/stop only."""
import argparse
import ipaddress
import json
import select
import socket
import threading
import time
import uuid
from celestron_probe import Recorder, FrameParser
from endpoint_lock import EndpointLease
from motor_control import AXES, angle, relative_angle, motor_packet, version
from setup_backend import validate_endpoint, check_direct_route
from network_info import route_source_address

IDENTITY = 'COSMOSBridge-AMW007-0.1.0.0, Python proxy'



class Bridge:
    def __init__(self, host, port=2000, callback=lambda event: None, bind_host='',
                 listen_port=2000, management_port=3000, advertise=True, allow_direct_upstream=False,
                 socket_factory=socket.create_connection):
        self.host, self.port = validate_endpoint(host, port)
        address = ipaddress.ip_address(self.host)
        direct = address in ipaddress.ip_network('1.2.3.0/24')
        if direct and (not allow_direct_upstream or not bind_host):
            raise ValueError('Direct telescope link requires two-interface mode and an explicit computer router-LAN IP')
        if address.version != 4 or (not address.is_private and not direct):
            raise ValueError('Bridge requires an infrastructure/private IPv4 telescope address')
        self.bind_host = bind_host or route_source_address(self.host, self.port)
        if direct and ipaddress.ip_address(self.bind_host) in ipaddress.ip_network('1.2.3.0/24'):
            raise ValueError('Phone-facing bridge address must be on a separate router LAN, not SkyQLink')
        bind_address = ipaddress.ip_address(self.bind_host)
        if bind_address.version != 4 or not bind_address.is_private or bind_address.is_unspecified or bind_address.is_multicast:
            raise ValueError('Select a specific local IPv4 address for the bridge')
        if (self.bind_host, listen_port) == (self.host, self.port):
            raise ValueError('Bridge listener and telescope endpoint must differ')
        self.listen_port, self.management_port = listen_port, management_port
        self.advertise = advertise
        self.callback = callback
        self.socket_factory = socket_factory
        self.stopping = threading.Event()
        self.ready = threading.Event()
        self.thread = None
        self.recorder = None
        self.upstream = self.client = self.manager = None
        self.listeners = []
        self.udp = None
        self.parser = FrameParser()
        self.client_parser = FrameParser()
        self.origins, self.firmware = {}, {}
        # A locally administered identity identifies this proxy, not the RN-171.
        self.mac = ':'.join(f'{b:02X}' for b in b'\x02' + uuid.uuid4().bytes[:5])
        self.report = {'host': self.host, 'port': self.port, 'experimental': True,
                       'ios_compatibility_verified': False, 'clients': [], 'errors': [],
                       'bytes_to_mount': 0, 'bytes_to_client': 0, 'stop_attempts': []}
        self.lease = EndpointLease(self.host, self.port)

    def emit(self, kind, **fields):
        if self.recorder:
            self.recorder.record(kind, **fields)
        self.callback({'event': kind, **fields})

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Bridge has already been started')
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()

    def observe(self, raw, direction):
        parser = self.parser if direction == 'mount' else self.client_parser
        frames = parser.feed(raw)
        for frame in frames:
            # Log checksummed AUX frames, not arbitrary ASCII/configuration data.
            self.emit('bridge_packet', direction=direction, hex=frame.hex())
            axis = frame[2]
            if direction != 'mount' or axis not in AXES or frame[3] != 0x20:
                continue
            data = frame[5:-1]
            if frame[4] == 0xfe:
                self.firmware[axis] = version(data)
            if frame[4] == 1 and len(data) == 3:
                count = int.from_bytes(data, 'big')
                self.origins.setdefault(axis, count)
                self.emit('bridge_values', axis=axis, encoder=count, angle=angle(count),
                          relative=relative_angle(count, self.origins[axis]),
                          firmware=self.firmware.get(axis, 'Unknown'), monotonic=time.monotonic())
        return frames

    def request(self, axis, command, timeout=1.2):
        self.upstream.sendall(motor_packet(axis, command))
        deadline = time.monotonic() + timeout
        while not self.stopping.is_set() and time.monotonic() < deadline:
            try:
                raw = self.upstream.recv(4096)
            except socket.timeout:
                continue
            if not raw:
                raise ConnectionError('Telescope closed the bridge connection')
            for frame in self.observe(raw, 'mount'):
                if frame[2:5] == bytes((axis, 0x20, command)):
                    return frame[5:-1]
        return None

    def send_stops(self, axes=AXES):
        for axis in axes:
            try:
                self.upstream.sendall(motor_packet(axis, 0x24, b'\x00'))
                self.report['stop_attempts'].append({'axis': axis, 'sent': True})
            except Exception as error:
                self.report['stop_attempts'].append({'axis': axis, 'sent': False, 'error': str(error)})
                message = f'{AXES[axis]} Stop delivery unconfirmed: {error}'
                self.report['errors'].append(message)
                self.callback({'event': 'bridge_error', 'message': message})
        self.emit('bridge_status', message='Stop attempted on both axes; encoder verification is separate.')

    def close_client(self):
        if self.client:
            self.client.close()
            self.client = None
            self.client_parser = FrameParser()
            self.send_stops()
            self.emit('bridge_client', message='App client disconnected; Stop attempted. Waiting for a new client.')

    def management_reply(self, command):
        # This is a proxy, never a WiFly provisioning or firmware-update gateway.
        values = {'wifi.mode': '1', 'wlan.dhcp.enabled': '1',
                  'wlan.static.ip': self.bind_host, 'softap.ssid': 'COSMOS-Bridge'}
        if command == 'version':
            return IDENTITY
        if command == 'get all':
            return '\r\n'.join(f'{key}: {value}' for key, value in values.items())
        if command.startswith('get ') and command[4:] in values:
            return values[command[4:]]
        return 'ERR Unsupported proxy command; configure the telescope outside Bridge mode'

    def listen(self, port):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listeners.append(server)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE if hasattr(socket, 'SO_EXCLUSIVEADDRUSE') else socket.SO_REUSEADDR, 1)
        server.bind((self.bind_host, port))
        server.listen(2)
        return server

    def run(self):
        try:
            self.recorder = Recorder('bridge')
            self.emit('bridge_starting', message='Opening infrastructure bridge and verifying motor replies…',
                      log_directory=str(self.recorder.directory))
            self.lease.acquire()
            check_direct_route(self.host)
            data_server = self.listen(self.listen_port)
            management_server = self.listen(self.management_port)
            self.listen_port = data_server.getsockname()[1]
            self.management_port = management_server.getsockname()[1]
            self.upstream = self.socket_factory((self.host, self.port), 3)
            self.upstream.settimeout(.1)
            end = time.monotonic() + .6
            while not self.stopping.is_set() and time.monotonic() < end:
                try:
                    if not self.upstream.recv(4096):
                        raise ConnectionError('Telescope closed during startup')
                except socket.timeout:
                    pass
            for axis in AXES:
                self.request(axis, 0xfe)
                count = self.request(axis, 1)
                if self.stopping.is_set():
                    return
                if count is None or len(count) != 3:
                    raise ConnectionError('Bridge not ready: encoder replies missing; disconnect other telescope clients')
            if self.stopping.is_set():
                return
            if self.advertise:
                self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                self.udp.bind((self.bind_host, 0))
            self.ready.set()
            self.report.update(bind_host=self.bind_host, listen_port=self.listen_port,
                               management_port=self.management_port, proxy_mac=self.mac,
                               upstream_local=self.upstream.getsockname())
            self.emit('bridge_ready', message=f'Bridge ON — Control app connects to {self.bind_host}:{self.listen_port}',
                      **{k: self.report[k] for k in ('bind_host', 'listen_port', 'management_port', 'upstream_local')})
            missed_polls = {axis: 0 for axis in AXES}
            next_poll = next_advert = 0
            last_client = last_manager = time.monotonic()
            manager_buffer = bytearray()
            while not self.stopping.is_set():
                now = time.monotonic()
                if self.udp and self.client is None and now >= next_advert:
                    packet = json.dumps({'mac': self.mac, 'version': IDENTITY}).encode()
                    try:
                        self.udp.sendto(packet, ('255.255.255.255', 55555))
                    except OSError as error:
                        self.emit('bridge_status', message=f'Discovery broadcast failed: {error}')
                    next_advert = now + 1
                if self.client is None and now >= next_poll:
                    for axis in AXES:
                        count = self.request(axis, 1)
                        if self.stopping.is_set():
                            return
                        if count is None or len(count) != 3:
                            missed_polls[axis] += 1
                            if missed_polls[axis] >= 3:
                                raise ConnectionError('Bridge lost encoder feedback after three consecutive polls. Disconnect connected control apps; restarting the telescope may be necessary before reconnecting.')
                            self.emit('bridge_status', message=f'{AXES[axis]} encoder reply delayed; retrying ({missed_polls[axis]}/3).')
                        else:
                            missed_polls[axis] = 0
                    next_poll = now + 1
                sockets = self.listeners + [self.upstream]
                sockets += [s for s in (self.client, self.manager) if s]
                readable, _, _ = select.select(sockets, [], [], .05)
                for source in readable:
                    if source in self.listeners:
                        connection, peer = source.accept()
                        connection.settimeout(.2)
                        if source is data_server:
                            if self.client is not None:
                                connection.close()
                                self.emit('bridge_status', message='Rejected a second motor-control client')
                            else:
                                self.client = connection
                                last_client = time.monotonic()
                                self.report['clients'].append(peer[0])
                                self.emit('bridge_client', message=f'Client {peer[0]} connected; AUX traffic forwarding')
                        elif self.manager is not None:
                            connection.close()
                        else:
                            self.manager = connection
                            last_manager = time.monotonic()
                            manager_buffer.clear()
                    elif source is self.upstream:
                        raw = source.recv(4096)
                        if not raw:
                            raise ConnectionError('Telescope disconnected')
                        self.observe(raw, 'mount')
                        if self.client:
                            try:
                                self.client.sendall(raw)
                                self.report['bytes_to_client'] += len(raw)
                            except OSError:
                                self.close_client()
                    elif source is self.client:
                        try:
                            raw = source.recv(4096)
                        except OSError:
                            raw = b''
                        if not raw:
                            self.close_client()
                        else:
                            self.observe(raw, 'client')
                            self.upstream.sendall(raw)
                            self.report['bytes_to_mount'] += len(raw)
                            last_client = time.monotonic()
                    elif source is self.manager:
                        try:
                            raw = source.recv(4096)
                            if not raw:
                                raise ConnectionError('Management client disconnected')
                            manager_buffer.extend(raw)
                            if len(manager_buffer) > 4096:
                                raise ConnectionError('Management command too long')
                            last_manager = time.monotonic()
                            while b'\n' in manager_buffer:
                                line, _, manager_buffer = manager_buffer.partition(b'\n')
                                command = line.decode('ascii', 'replace').strip()
                                # Log operation name only, never potential password arguments.
                                operation = command.split(' ', 1)[0]
                                self.emit('bridge_management', operation=operation if operation in
                                          ('get', 'set', 'version', 'save', 'reset', 'exit') else 'unsupported')
                                if command == 'exit':
                                    raise ConnectionError('Management exit')
                                source.sendall((self.management_reply(command) + '\r\n> ').encode())
                        except OSError:
                            source.close()
                            self.manager = None
                if self.client and time.monotonic() - last_client > 15:
                    self.close_client()
                if self.manager and time.monotonic() - last_manager > 10:
                    self.manager.close()
                    self.manager = None
        except Exception as error:
            message = str(error)
            if isinstance(error, (BrokenPipeError, ConnectionResetError, ConnectionRefusedError)):
                message = (f'Telescope {self.host}:{self.port} closed or refused the connection ({error}). '
                           'Disconnect any control apps from the original adapter (for example SkySafari, SkyPortal or CPWI). '
                           'Start Bridge first, then connect the control app to this computer in Access Point mode. '
                           'If it still fails with other clients disconnected, the adapter may need a power-cycle.')
            self.report['errors'].append(message)
            self.callback({'event': 'bridge_error', 'message': message})
        finally:
            self.ready.clear()
            if self.upstream:
                try:
                    self.send_stops()
                    # Drain final replies before closing the legacy RN-171 stream.
                    deadline = time.monotonic() + .8
                    replies = set()
                    last_rx = time.monotonic()
                    retried = False
                    while time.monotonic() < deadline:
                        if not retried and deadline - time.monotonic() < .5:
                            missing = [axis for axis in AXES if axis not in replies]
                            if missing:
                                self.send_stops(missing)
                                self.report['cleanup_retry_axes'] = missing
                            retried = True
                        try:
                            raw = self.upstream.recv(4096)
                        except socket.timeout:
                            if len(replies) == 2 and time.monotonic() - last_rx >= .1:
                                break
                            continue
                        if not raw:
                            break
                        last_rx = time.monotonic()
                        for frame in self.observe(raw, 'mount'):
                            if frame[2] in AXES and frame[3:5] == b'\x20\x24':
                                replies.add(frame[2])
                    self.report['cleanup_stop_replies'] = {str(a): a in replies for a in AXES}
                    self.upstream.shutdown(socket.SHUT_WR)
                except Exception as error:
                    self.report['errors'].append('Cleanup: ' + str(error))
            for connection in [self.client, self.manager, self.upstream, self.udp] + self.listeners:
                if connection:
                    try:
                        connection.close()
                    except OSError:
                        pass
            self.lease.release()
            directory = str(self.recorder.directory) if self.recorder else ''
            if self.recorder:
                try:
                    self.recorder.finish(self.report)
                except Exception as error:
                    self.callback({'event': 'bridge_error', 'message': f'Cannot save bridge report: {error}'})
            self.callback({'event': 'bridge_off', 'log_directory': directory,
                           'stop_replies': self.report.get('cleanup_stop_replies', {})})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='Telescope infrastructure IP')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--bind', default='', help='Computer LAN IP (default: route to telescope)')
    parser.add_argument('--two-interfaces', action='store_true', help='Allow a directly attached SkyQLink upstream; requires --bind router-LAN IP')
    args = parser.parse_args()
    bridge = Bridge(args.host, args.port, bind_host=args.bind, allow_direct_upstream=args.two_interfaces,
                    callback=lambda e: print(e, flush=True))
    bridge.start()
    try:
        while bridge.thread.is_alive():
            bridge.thread.join(.2)
    except KeyboardInterrupt:
        bridge.stop()
        bridge.thread.join(10)


if __name__ == '__main__':
    main()
