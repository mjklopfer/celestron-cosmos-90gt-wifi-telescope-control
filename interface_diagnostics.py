"""Read-only proxy management diagnostics; never opens the motor port."""
import json
import socket
import time
from diagnostics import LiveRecorder
from discover_modules import identify_proxy

def diagnose_proxy(host, port=2000, callback=lambda event: None, cancel=None):
    recorder = LiveRecorder(callback, ())
    report = {'host': host, 'port': port, 'rows': [], 'settings_changed': False, 'movement_sent': False,
              'interface_mode': 'proxy', 'motor_positions_verified': False, 'wifi_verified': False}
    def row(endpoint, status, reply):
        item = dict(device='Controller proxy (read-only)', endpoint=endpoint, status=status, reply=reply)
        report['rows'].append(item)
        recorder.record('diagnostic_row', **item)
    try:
        identity = identify_proxy(host, port)
        if not identity or identity.get('endpoint_kind') != 'software_proxy':
            raise ValueError('Controller proxy signature not verified. No motor socket opened.')
        row('TCP 3000 / version and get cosmos.proxy', 'REPLY', json.dumps(identity, indent=2))
        if cancel is not None and cancel.is_set():
            report['aborted'] = True
        else:
            with socket.create_connection((host, 3000), 2) as sock:
                sock.settimeout(.3)
                sock.sendall(b'get cosmos.telemetry\n')
                data = bytearray()
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and len(data) < 65536:
                    if cancel is not None and cancel.is_set():
                        report['aborted'] = True
                        break
                    try:
                        chunk = sock.recv(4096)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    data.extend(chunk)
                    if b'\n> ' in data:
                        break
                row('get cosmos.telemetry (cached positions)', 'REPLY' if data else 'NO REPLY', data.decode('utf-8', 'replace'))
    except Exception as error:
        report['error'] = str(error)
        row('Management identity', 'ERROR', str(error))
    finally:
        report['log_directory'] = str(recorder.directory)
        recorder.finish(report)
    return report
