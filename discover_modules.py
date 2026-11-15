"""Bounded identification of Celestron AUX and original RN-171 Wi-Fi endpoints.

Scans attached supported networks; vendor prefixes are hints, not identity checks.
Discovery sends no motor movement or configuration-write commands."""
import concurrent.futures
import ipaddress
import re
import socket
import threading
import time
from celestron_probe import FrameParser, Recorder
from network_info import connected_lans, neighbor_entries
from motor_control import motor_packet, version
from wifly_configure import Session
from endpoint_lock import EndpointLease, EndpointBusy

RN171_VENDOR_PREFIXES = {'00:06:66'}  # Candidate hint from the observed RN-171, never proof of identity.


def vendor_prefix(mac):
    """Normalize the MAC vendor prefix used only to prioritize discovery."""
    parts = mac.lower().split(':')
    return ':'.join(part.zfill(2) for part in parts[:3]) if len(parts) == 6 else ''


class SafeRecorder:
    def __init__(self, recorder):
        """Initialize SafeRecorder state; external work starts only in the corresponding operation."""
        self.recorder = recorder
        self.lock = threading.Lock()
    def record(self, kind, **fields):
        """Append a timestamped event to the operation log."""
        with self.lock:
            self.recorder.record(kind, **fields)


def identify(host, port=2000, recorder=None, socket_factory=socket.create_connection, rn171_hint=False):
    """Read both motor versions, optionally the Wi-Fi node and WiFly firmware. No settings/motion."""
    class NullRecorder:
        def record(self, *args, **kwargs):
            pass
    recorder = recorder or NullRecorder()
    lease = EndpointLease(host, port)
    try:
        lease.acquire()
        sock = socket_factory((host, port), .35)
    except (OSError, EndpointBusy) as error:
        recorder.record('candidate_unavailable', host=host, port=port, error=str(error))
        lease.release()
        return None
    parser = FrameParser()
    hello = False
    def query(axis, timeout=.6):
        """Send a read-only AUX query and await the matching controller reply."""
        nonlocal hello
        sock.sendall(motor_packet(axis, 0xfe) if axis in (0x10, 0x11) else bytes.fromhex('3b0320b5fe2a'))
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                raw = sock.recv(4096)
            except socket.timeout:
                continue
            if not raw:
                raise ConnectionError('Peer closed connection')
            hello = hello or b'*HELLO*' in raw
            for frame in parser.feed(raw):
                if frame[2] == axis and frame[3] == 0x20 and frame[4] == 0xfe and len(frame[5:-1]) in (2, 4):
                    return frame[5:-1]
        return None
    try:
        sock.settimeout(.05)
        # The legacy module announces itself before any AUX traffic. Identify it
        # first rather than requiring downstream motor replies for discovery.
        greeting = bytearray()
        end = time.monotonic() + .25
        while time.monotonic() < end:
            try:
                raw = sock.recv(4096)
            except socket.timeout:
                continue
            if not raw:
                raise ConnectionError('Peer closed connection')
            greeting.extend(raw)
            if b'*HELLO*' in greeting:
                hello = True
                break
        result = {'ip': host, 'port': port, 'verified': False,
                  'motors_verified': False, 'adapter_verified': False,
                  'module_type': 'Celestron AUX Wi-Fi bridge', 'motor_versions': {}}
        identity_attempted = False

        def identify_wifly():
            nonlocal identity_attempted
            identity_attempted = True
            session = Session(sock, recorder)
            try:
                session.enter()
                text = session.command('ver')
                match = re.search(r'WiFly Ver ([^,\r\n]+),\s*([^\r\n]+) on (RN-\d+)', text)
                if match:
                    result.update(module_type=('Celestron SkyQLink / ' if 'CEL' in match.group(1) else '') +
                                  'WiFly ' + match.group(3), module_version=match.group(1),
                                  module_build_date=match.group(2), identity_reply=text)
                    if match.group(3) == 'RN-171':
                        result.update(adapter_verified=True, verified=True)
            except Exception as error:
                result['module_version_note'] = str(error)
            finally:
                if session.entered:
                    try:
                        result['command_mode_exit_confirmed'] = session.exit()
                    except Exception as error:
                        result['exit_error'] = str(error)
        if hello or rn171_hint:
            identify_wifly()
        if result.get('exit_error') or result.get('command_mode_exit_confirmed') is False:
            motors = {axis: None for axis in (0x10, 0x11)}
        else:
            motors = {axis: query(axis) for axis in (0x10, 0x11)}
        motors_verified = all(data is not None for data in motors.values())
        result.update(verified=result['verified'] or motors_verified, motors_verified=motors_verified,
                      motor_versions={name: version(motors[axis]) if motors[axis] is not None else 'No reply'
                                      for axis, name in ((0x10, 'azimuth'), (0x11, 'altitude'))})
        wifi = query(0xb5, .3) if motors_verified else None
        if wifi is not None:
            result['wifi_aux_version'] = version(wifi)
        if hello and not identity_attempted:
            identify_wifly()
        if not result['verified']:
            recorder.record('unverified_open_port', host=host, port=port)
            return None
        result['verification_note'] = ('Both motor firmware replies verified' if motors_verified else
                                       'SkyQLink adapter identified; motors not responding')
        recorder.record('verified_module', **result)
        return result
    except (OSError, ConnectionError) as e:
        recorder.record('probe_failed', host=host, port=port, error=str(e))
        return None
    finally:
        sock.close()
        lease.release()


def scan_modules(port=2000, callback=lambda event: None, timeout=60):
    """Search supported attached LANs within a period and identify replies without changing settings."""
    started = time.monotonic()
    deadline = started + timeout
    recorder = Recorder('discover-modules')
    safe = SafeRecorder(recorder)
    report = {'port': port, 'matches': [], 'networks_checked': [],
              'method': 'RN-171 vendor-prefix hints first, then TCP firmware identification; no exact MAC or SSID requirement',
              'settings_changed': False, 'motor_commands_sent': False}
    try:
        lans = connected_lans()
        if not lans:
            raise ValueError('Connect to the telescope router LAN. Automatic scan supports attached private IPv4 /24 or smaller networks; otherwise enter its IP manually.')
        neighbors = neighbor_entries()
        hosts = {}
        for interface, local, network in lans:
            report['networks_checked'].append(str(network))
            if network == ipaddress.ip_network('1.2.3.0/24'):
                hosts['1.2.3.4'] = interface  # Only the directly attached known endpoint, never this public subnet.
                continue
            for address in network.hosts():
                if str(address) != local:
                    hosts[str(address)] = interface
        # Try all known neighbors first, regardless of their manufacturer/MAC.
        cached = list(dict.fromkeys(n['ip'] for n in neighbors if n['ip'] in hosts))
        preferred = list(dict.fromkeys(n['ip'] for n in neighbors if n['ip'] in hosts
                                      and vendor_prefix(n['mac']) in RN171_VENDOR_PREFIXES))
        report['vendor_hint_candidates'] = preferred
        def probe(address):
            if time.monotonic() >= deadline:
                report['timed_out'] = True
                return None
            result = identify(address, port, safe, rn171_hint=address in preferred)
            if result:
                result['interface'] = hosts[address]
                result['observed_mac'] = next((n['mac'] for n in neighbors if n['ip'] == address), None)
            return result
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            callback({'event': 'scan_progress', 'message': f'Checking {len(preferred)} RN-171 vendor-prefix candidate(s) on TCP {port}…'})
            found = [item for item in executor.map(probe, preferred) if item]
            if preferred and not found and time.monotonic() < deadline:
                callback({'event': 'scan_progress', 'message': 'Retrying RN-171 candidates after a short connection pause…'})
                time.sleep(.5)
                found = [item for item in executor.map(probe, preferred) if item]
            if not found:
                callback({'event': 'scan_progress', 'message': f'Checking other cached LAN neighbors on TCP {port}…'})
                found = [item for item in executor.map(probe, [h for h in cached if h not in preferred]) if item]
            if not found:
                callback({'event': 'scan_progress', 'message': f'Checking the remaining LAN addresses on TCP {port}…'})
                found = [item for item in executor.map(probe, [h for h in hosts if h not in cached]) if item]
        report['matches'] = found
        report['scan_scope'] = 'Cached LAN neighbors first; full attached subnet scan if none verify.'
        report['limitations'] = 'Busy single-client modules, client isolation, and blocked ports may prevent identification. Close other telescope apps before a protocol scan.'
    except Exception as e:
        report['error'] = str(e)
    report['elapsed_seconds'] = round(time.monotonic() - started, 2)
    report['timeout_seconds'] = timeout
    safe.record('discovery_result', **report)
    report['log_directory'] = str(recorder.directory)
    recorder.finish(report)
    return report


if __name__ == '__main__':
    scan_modules()
