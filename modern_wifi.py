"""Experimental AMW007-style provisioning, independently implemented.

NEEDS COMMERCIAL HARDWARE TESTING. Based on alex-vg/esp-skyportal-module
captured TCP 3000 commands. Our ESP32 explicitly advertises write capability.
No generic numeric encryption command is guessed. Protected Personal networks
negotiate encryption automatically; open networks have an empty passkey.
"""
import re
import socket
import time
from endpoint_lock import EndpointLease
from setup_backend import validate_endpoint


def validate_settings(ssid, password, security):
    if not 1 <= len(ssid.encode('utf-8')) <= 32:
        raise ValueError('SSID must contain 1-32 UTF-8 bytes.')
    if any(ord(c) < 32 or c in '\\"' for c in ssid + password):
        raise ValueError('Quotes, backslashes and control characters are not supported by this experimental command format.')
    if security not in ('Personal (automatic)', 'Open (no password)'):
        raise ValueError('Only automatic Personal security or an open network is supported.')
    if security == 'Open (no password)':
        if password:
            raise ValueError('Clear the password when selecting an open network.')
    elif not (8 <= len(password) <= 63 and password.isascii() or re.fullmatch(r'[0-9a-fA-F]{64}', password)):
        raise ValueError('Personal password must be 8-63 ASCII characters or 64 hexadecimal digits.')


class Management:
    def __init__(self, sock):
        self.sock = sock

    def command(self, command):
        self.sock.sendall((command + '\r\n').encode('utf-8'))
        data = bytearray()
        deadline = time.monotonic() + 3
        while len(data) < 16384 and time.monotonic() < deadline:
            try:
                chunk = self.sock.recv(min(4096, 16384-len(data)))
            except socket.timeout:
                continue
            if not chunk:
                break
            data.extend(chunk)
            # Our firmware does not send an unsolicited initial prompt. Commercial
            # devices may: an empty prompt is ignored until a response is received.
            text = data.decode('utf-8', 'replace').strip()
            if re.search(r'(?:^|[\r\n])>\s*$', text):
                return text.rstrip('> \r\n')
        raise ConnectionError('Management response timed out; settings may be partially staged or saved. Read before retrying.')


def configure(host, port=2000, *, ssid=None, password='', security='Personal (automatic)', allow_commercial=False):
    host, port = validate_endpoint(host, port)
    if port == 3000:
        raise ValueError('Use the telescope data port (normally 2000), not management port 3000.')
    if ssid is not None:
        validate_settings(ssid, password, security)
    with EndpointLease(host, port), EndpointLease(host, 3000):
        with socket.create_connection((host, 3000), 3) as sock:
            # Consume an optional welcome prompt before the first command. An
            # empty SSID response later is valid for a factory-default module.
            sock.settimeout(.15)
            try:
                sock.recv(4096)
            except socket.timeout:
                pass
            sock.settimeout(.25)
            manager = Management(sock)
            identity = manager.command('version')
            ours = identity.startswith('COSMOS-SIM-AMW007-')
            commercial = identity.startswith(('AMW007', 'ZentriOS'))
            if not ours and not (commercial and allow_commercial):
                raise ValueError('Supported module identity not confirmed. No Wi-Fi settings written.')
            if ours and manager.command('get cosmos.wifi.config') != '1':
                raise ValueError('ESP32 firmware lacks desktop provisioning support. Use its setup page or update firmware.')
            current = manager.command('get wlan.ssid')
            if current.startswith(('ERR', 'Unknown')):
                raise ValueError('SSID read not supported; no settings written.')
            if ssid is None:
                return {'ssid': current, 'identity': identity, 'saved': False,
                        'message': 'SSID read. Password is not retrieved; enter it before applying.'}
            # Never expose a response to a secret-bearing command: some firmwares echo it.
            commands = [f'set wlan.ssid "{ssid}"', f'set wlan.passkey "{password}"',
                        'set wlan.dhcp.enabled 1']
            for command in commands:
                reply = manager.command(command)
                if reply.strip() != 'Set OK':
                    raise ValueError('A setting was not acknowledged; save was not sent. Re-read before retrying.')
            if ours and manager.command('set wifi.mode 1').strip() != 'Set OK':
                raise ValueError('Station mode was not acknowledged; save was not sent.')
            if manager.command('get wlan.ssid') != ssid:
                raise ValueError('Staged SSID readback did not match; save was not sent.')
            if manager.command('save').strip() != 'Success':
                raise ValueError('Save was not acknowledged. Saved state is unknown; re-read before retrying.')
            return {'ssid': ssid, 'saved': True, 'identity': identity,
                    'message': ('Saved. ESP32 is restarting to join the router; rediscover its address.' if ours else
                                'Save acknowledged. Select WLAN/access-point mode using the module switch, then reconnect and rediscover. Commercial behavior needs hardware testing.'),
                    'network_join_verified': False}
