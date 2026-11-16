"""Read-only native WiFly settings and AUX controller diagnostics.

Leave command mode before opening a fresh transparent AUX connection. Preserve
actual replies and timeouts rather than treating TCP connection as motor proof."""
import re
import socket
import time
import datetime as dt
from celestron_probe import AuxProbe, NODES
from motor_control import AXES, angle, version
from setup_backend import LiveRecorder, validate_endpoint, check_direct_route
from wifly_configure import Session, sanitize
from endpoint_lock import exclusive_endpoint

WIFI_QUERIES = ('ver', 'get mac', 'get wlan', 'get ip', 'get uart', 'get com',
                'get sys', 'get option', 'show net', 'show rssi', 'show stats',
                'get time', 'show time', 'show t t', 'get apmode', 'get broadcast',
                'get dns', 'get ftp', 'get everything', 'get ip a',
                'show connection', 'show io', 'show net n', 'ls')
BASE_WIFI_QUERIES = WIFI_QUERIES[:14]

TIME_SITE_QUERIES = (
    (0xb0, 'GPS (optional)', ((0x36, 'TIME_VALID'), (0x37, 'GPS_LINKED'),
                            (0x01, 'LATITUDE'), (0x02, 'LONGITUDE'),
                            (0x03, 'DATE'), (0x04, 'YEAR'), (0x33, 'UTC_TIME'),
                            (0x07, 'SATELLITES'), (0xA0, 'COMPASS'),
                            (0x08, 'RECEIVER_STATUS'), (0x55, 'HARDWARE_ID'))),
    (0xb2, 'RTC (optional; model-dependent)', ((0x03, 'DATE'), (0x04, 'YEAR'),
                                            (0x33, 'UTC_TIME'))),
)
MOTOR_SETTING_QUERIES = ((0x40, 'GET_POS_BACKLASH'), (0x41, 'GET_NEG_BACKLASH'),
                         (0x47, 'GET_AUTOGUIDE_RATE'), (0x13, 'SLEW_DONE'),
                         (0xFC, 'GET_APPROACH'))


def clock_summary(replies):
    text = '\n'.join(replies.values())
    fields = {'Status': 'Unset' if 'Time NOT SET' in text else 'Not reported'}
    clock_lines = [line.strip() for line in text.splitlines()
                   if re.match(r'^Time[ =:]', line) and 'NOT SET' not in line]
    fields['Reported clock text'] = '; '.join(clock_lines) or 'Not reported'
    if clock_lines:
        fields['Status'] = 'Clock text reported; validity unverified'
    for label, key in (('Uptime', 'UpTime'), ('RTC counter', 'RTC'), ('RAW counter (hex)', 'RAW'),
                       ('Restarts', 'Restarts'), ('Wake count', 'Wake'), ('Time sync enable', 'TimeEna'),
                       ('Time server', 'TIMEADR'), ('Zone setting (raw)', 'Zone')):
        found = re.findall(r'^' + key + r'=(.*)$', text, re.M)
        fields[label] = found[-1].strip() if found else 'Not reported'
    fields['Zone interpretation'] = ('UTC-07:00 per WiFly manual; not a geographic site or verified DST rule'
                                     if fields['Zone setting (raw)'] == '7' else 'Not reported')
    fields['Calendar UTC'] = 'Not reported'
    if fields['Status'] != 'Unset' and fields['RTC counter'].isdigit() and clock_lines:
        try:
            fields['Calendar UTC'] = dt.datetime.fromtimestamp(int(fields['RTC counter']), dt.timezone.utc).isoformat() + ' (derived from reported RTC Unix seconds; device validity unverified)'
        except (ValueError, OverflowError, OSError):
            fields['Calendar UTC'] = 'RTC outside supported calendar range'
    return fields


def motor_queries(address, deep=True):
    if not deep:
        return MOTOR_SETTING_QUERIES
    extra = ((0x18, 'AT_INDEX'), (0x3B, 'POLL_CORDWRAP'), (0x3C, 'GET_CORDWRAP_POS')) if address == 0x10 else ((0x12, 'LEVEL_DONE'),)
    return MOTOR_SETTING_QUERIES + ((0x15, 'PEC_RECORD_DONE'),) + extra


def decode_motor_setting(command, reply):
    if command == 0x3C:
        if len(reply) != 3:
            raise ValueError('Expected three position bytes')
        counts = int.from_bytes(reply, 'big')
        return f'{counts} counts; {angle(counts):.5f}° motor cordwrap position'
    if len(reply) != 1:
        raise ValueError('Expected one setting byte')
    value = reply[0]
    if command in (0x12, 0x13, 0x15, 0x18, 0x3B):
        if value not in (0, 255):
            raise ValueError('Unknown status encoding (expected 00 or ff)')
        label = {0x12: 'Level complete', 0x13: 'Slew complete', 0x15: 'PEC recording complete',
                 0x18: 'At index', 0x3B: 'Cordwrap enabled'}[command]
        return label + (': Yes' if value else ': No')
    if command == 0xFC:
        if value not in (0, 1):
            raise ValueError('Unknown approach encoding')
        return 'Negative GOTO approach' if value else 'Positive GOTO approach'
    if command == 0x47:
        return f'{value * 100 / 256:.4f}% of sidereal (autoguide setting, not tracking state)'
    if value > 99:
        raise ValueError('Backlash outside 0–99')
    return f'{value} (backlash compensation, 0–99)'


def endpoint_catalog(deep=False):
    """Enumerate documented reads, not every possible or vendor-private command."""
    items = [('Wi-Fi adapter', command) for command in (WIFI_QUERIES if deep else BASE_WIFI_QUERIES)]
    for address, name in NODES.items():
        items.append((name, f'AUX 0x{address:02X} / GET_VER 0xFE'))
        if address in AXES:
            items.extend((name, f'AUX 0x{address:02X} / GET_POSITION 0x01 / sample {sample}')
                         for sample in (1, 2))
            items.extend((name, f'AUX 0x{address:02X} / {label} 0x{command:02X}')
                         for command, label in motor_queries(address, deep))
    for address, name, queries in TIME_SITE_QUERIES:
        items.extend((name, f'AUX 0x{address:02X} / {label} 0x{command:02X}')
                     for command, label in queries if deep or command not in (0x08, 0x55))
    return items


def decode_time_site(command, data):
    """Decode a GPS/RTC field without substituting computer time or a location."""
    size = {0x01: 3, 0x02: 3, 0x03: 2, 0x04: 2, 0x33: 3, 0x36: 1, 0x37: 1, 0x07: 2, 0xA0: 1, 0x08: 2, 0x55: 1}[command]
    if len(data) != size:
        raise ValueError(f'Expected {size} bytes, received {len(data)}')
    if command == 0x55:
        return data[0], f'Hardware identification byte {data[0]} (model meaning unverified)'
    if command == 0x08:
        value = int.from_bytes(data, 'big')
        modes = ('Reserved', 'Reserved', 'Bad geometry', 'Acquiring satellites',
                 'Position hold', 'Propagate mode', '2D fix', '3D fix')
        return value, f'{modes[value >> 13]}; receiver status bits 0x{value:04X} (remaining bits retained raw)'
    if command == 0x07:
        return list(data), f'{data[0]} satellites visible; {data[1]} tracked'
    if command == 0xA0:
        heading = {0x0b: 'N', 0x09: 'NE', 0x0d: 'E', 0x0c: 'SE',
                   0x0e: 'S', 0x06: 'SW', 0x07: 'W', 0x03: 'NW'}.get(data[0])
        return data[0], heading or f'Unknown compass code {data[0]}'
    if command in (0x36, 0x37):
        if data[0] not in (0, 1):
            raise ValueError('Validity flag must be 0 or 1')
        return bool(data[0]), 'Yes' if data[0] else 'No'
    if command in (0x01, 0x02):
        degrees = int.from_bytes(data, 'big', signed=True) * 360 / (1 << 24)
        if command == 0x01 and not -90 <= degrees <= 90:
            raise ValueError('Latitude outside -90 to +90 degrees')
        hemisphere = ('N' if degrees >= 0 else 'S') if command == 1 else ('E' if degrees >= 0 else 'W')
        return degrees, f'{abs(degrees):.7f}° {hemisphere} (reported; GPS validity shown separately)'
    if command == 0x03:
        dt.date(2000, data[0], data[1])  # Leap-year template; year is a separate query.
        return list(data), f'{data[0]:02d}-{data[1]:02d} (month-day; year queried separately)'
    if command == 0x04:
        year = int.from_bytes(data, 'big')
        if not 1 <= year <= 9999:
            raise ValueError('Year outside supported calendar range')
        return year, str(year)
    dt.time(*data)
    return list(data), ':'.join(f'{v:02d}' for v in data) + ' UTC (reported; not independently verified)'


def read_time_site(probe, row, deep=False):
    """Bounded optional-node reads; missing devices do not invalidate motor results."""
    results = {}
    for address, name, queries in TIME_SITE_QUERIES:
        fields = results[f'0x{address:02X}'] = {}
        for command, label in queries:
            if not deep and command in (0x08, 0x55):
                continue
            endpoint = f'AUX 0x{address:02X} / {label} 0x{command:02X}'
            try:
                reply = probe.query(address, command, attempts=1)
            except (OSError, ConnectionError) as error:
                fields[label] = {'status': 'ERROR', 'error': str(error)}
                row(name, endpoint, 'ERROR', str(error))
                continue
            if reply is None:
                fields[label] = {'status': 'NO REPLY'}
                row(name, endpoint, 'NO REPLY', 'Timed out; device may be absent or command unsupported')
                continue
            try:
                value, display = decode_time_site(command, reply)
            except ValueError as error:
                fields[label] = {'status': 'INVALID REPLY', 'raw_hex': reply.hex()}
                row(name, endpoint, 'INVALID REPLY', f'{error}; raw {reply.hex()}')
            else:
                fields[label] = {'status': 'REPLY', 'value': value, 'raw_hex': reply.hex()}
                row(name, endpoint, 'REPLY', f'{display}; raw {reply.hex()}')
    return results


@exclusive_endpoint
def diagnose(host, port, callback=lambda event: None, deep=False):
    """Read WiFly settings and both motor controllers, reporting replies and failures separately."""
    host, port = validate_endpoint(host, port)
    recorder = LiveRecorder(callback, ())
    report = {'host': host, 'port': port, 'settings_changed': False,
              'movement_sent': False, 'deep_diagnostics': deep, 'rows': [], 'wifi_verified': False,
              'motor_positions_verified': False,
              'observed_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'host_clock': {'local_iso': dt.datetime.now().astimezone().isoformat(),
                             'timezone_name': dt.datetime.now().astimezone().tzname(),
                             'source': 'This computer; not telescope time or location'},
              'location_status': 'No documented WiFly geographic-site read. AUX GPS values, if any, are listed separately; host location is not inferred.',
              'time_site_note': 'Reported device data only; not computer time. '
                                'Optional GPS/RTC presence and data accuracy are not assumed.'}
    report['endpoint_catalog'] = [dict(device=device, endpoint=endpoint)
                                  for device, endpoint in endpoint_catalog(deep)]

    def row(device, endpoint, status, reply):
        """Append and publish one diagnostic result with its actual response data."""
        item = dict(device=device, endpoint=endpoint, status=status, reply=sanitize(reply))
        report['rows'].append(item)
        recorder.record('diagnostic_row', **item)

    try:
        check_direct_route(host)
        session = None
        try:
            with socket.create_connection((host, port), 3) as sock:
                sock.settimeout(.2)
                session = Session(sock, recorder)
                try:
                    session.enter()
                    for command in (WIFI_QUERIES if deep else BASE_WIFI_QUERIES):
                        try:
                            reply = session.command(command)
                            row('Wi-Fi adapter', command, 'REPLY', reply)
                            if command in ('get time', 'show time', 'show t t'):
                                report.setdefault('wifly_clock_replies', {})[command] = sanitize(reply)
                            if command == 'ver':
                                report['wifi_verified'] = 'WiFly' in reply and 'RN-171' in reply
                        except Exception as error:
                            row('Wi-Fi adapter', command, 'REJECTED' if 'Adapter rejected' in str(error) else 'ERROR',
                                str(error) + '\n' + getattr(session, 'last_reply', ''))
                finally:
                    report['command_mode_exit_confirmed'] = session.exit()
        except Exception as error:
            row('Wi-Fi adapter', f'{host}:{port} / command mode', 'ERROR', str(error))
        if session and session.entered and not report.get('command_mode_exit_confirmed'):
            raise RuntimeError('Command-mode exit unconfirmed; AUX queries skipped')

        # A new connection restores the transparent AUX stream after command mode.
        probe = AuxProbe(host, port, recorder)
        positions = {}
        motor_versions = {}
        try:
            probe.receive(.6)
            for axis, name in NODES.items():
                reply = probe.query(axis, 0xfe, attempts=2 if axis in AXES else 1)
                endpoint = f'AUX 0x{axis:02X} / GET_VER 0xFE'
                if reply is not None and len(reply) in (2, 4):
                    row(name, endpoint, 'REPLY', f'Firmware {version(reply)}; raw {reply.hex()}')
                    motor_versions[axis] = version(reply)
                else:
                    row(name, endpoint, 'NO VALID REPLY', 'Timed out' if reply is None else 'Unknown interpretation; raw ' + reply.hex())
                if axis not in AXES:
                    continue
                # Two samples distinguish a valid stationary position from silence.
                for sample in range(2):
                    reply = probe.query(axis, 0x01)
                    endpoint = f'AUX 0x{axis:02X} / GET_POSITION 0x01 / sample {sample + 1}'
                    if reply is not None and len(reply) == 3:
                        encoder = int.from_bytes(reply, 'big')
                        positions[axis] = encoder
                        row(name, endpoint, 'REPLY', f'{encoder} counts; {angle(encoder):.5f}°; raw {reply.hex()}')
                        recorder.record('diagnostic_position', axis=axis, encoder=encoder,
                                        angle=angle(encoder), firmware=motor_versions.get(axis, 'No reply'),
                                        monotonic=time.monotonic())
                    else:
                        positions.pop(axis, None)
                        row(name, endpoint, 'NO VALID REPLY', 'Timed out' if reply is None else 'Unknown interpretation; raw ' + reply.hex())
                for command, label in motor_queries(axis, deep):
                    endpoint = f'AUX 0x{axis:02X} / {label} 0x{command:02X}'
                    reply = probe.query(axis, command, attempts=1)
                    if reply is None:
                        row(name, endpoint, 'NO REPLY', 'Timed out; command may be unsupported')
                    else:
                        try:
                            value = decode_motor_setting(command, reply)
                        except ValueError as error:
                            row(name, endpoint, 'INVALID REPLY', f'{error}; raw {reply.hex()}')
                        else:
                            row(name, endpoint, 'REPLY', f'{value}; raw {reply.hex()}')
            report['motor_positions_verified'] = len(positions) == len(AXES)
            report['motor_firmware_verified'] = all(a in motor_versions for a in AXES)
            report['time_site'] = read_time_site(probe, row, deep)
        finally:
            probe.close()
    except Exception as error:
        report['error'] = sanitize(str(error))
        row('Connection', f'{host}:{port}', 'ERROR', report['error'])
    finally:
        queried = {item['endpoint'] for item in report['rows']}
        for device, endpoint in endpoint_catalog(deep):
            if endpoint not in queried:
                row(device, endpoint, 'NOT QUERIED',
                    'Session unavailable or interrupted; no conclusion about endpoint support')
        report['wifly_clock'] = clock_summary(report.get('wifly_clock_replies', {}))
        for field, value in report['wifly_clock'].items():
            row('WiFly clock', field, 'REPORTED' if value != 'Not reported' else 'NOT REPORTED', str(value))
        report['log_directory'] = str(recorder.directory)
        recorder.finish(report)
    return report
