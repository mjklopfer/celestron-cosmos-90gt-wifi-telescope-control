"""Explicit, stationary motor coordinate/backlash edits under exclusive ownership."""
import math
import re
import time
from celestron_probe import AuxProbe
from endpoint_lock import exclusive_endpoint
from motor_control import AXES, angle, relative_counts
from setup_backend import LiveRecorder, check_direct_route, validate_endpoint


def parse_degrees(text, low, high):
    """Validate completed decimal-degree input without fighting intermediate typing.

    Accept a sign, leading zeros and up to five decimal places. Reject exponent
    notation, units, commas, nonfinite values and excess precision explicitly;
    do not silently clamp or round user input. Encoder writes separately round
    to the nearest 24-bit count (360 / 2**24 ~= 0.00002146 degrees).
    """
    text = text.strip()
    if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]{0,5})?|\.[0-9]{1,5})', text):
        raise ValueError('Use decimal degrees with up to 5 decimal places, e.g. 060.84; no units or commas.')
    value = float(text)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Enter degrees from {low} to {high}.')
    return 0.0 if value == 0 else value


def parse_backlash(text, delta=False):
    """Normalize integral decimals/zeros; never change a sign or round a fraction."""
    text = text.strip()
    if not re.fullmatch(r'[+-]?[0-9]+(?:\.0+)?', text):
        raise ValueError('Backlash uses whole-number units, not degrees. Examples: 2 or 02.0; fractions are not allowed.')
    value = int(text.split('.')[0])
    if not (-99 if delta else 0) <= value <= 99:
        raise ValueError('Backlash delta must be -99 to +99.' if delta else 'Backlash must be 0–99; negative absolute values are not allowed.')
    if not delta and text.startswith('-'):
        raise ValueError('Do not use a minus sign for an absolute backlash value.')
    return value


def setting_packet(axis, command, value):
    if axis not in AXES:
        raise ValueError('Select a motor axis')
    if command in (4, 0x3A):
        if command == 0x3A and axis != 0x10:
            raise ValueError("Cord wrap applies only to azimuth")
        low, high = (0, 360) if axis == 0x10 else (-90, 90)
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{AXES[axis]} angle must be between {low} and {high} degrees')
        data = (round((value % 360) * (1 << 24) / 360) % (1 << 24)).to_bytes(3, 'big')
    elif command == 0xFD:
        if type(value) is not int or value not in (0, 1):
            raise ValueError('GoTo approach must be 0 (positive) or 1 (negative)')
        data = bytes((value,))
    elif command in (0x38, 0x39):
        if axis != 0x10 or value is not None:
            raise ValueError('Cord-wrap enable/disable takes no data and applies only to azimuth')
        data = b''
    elif command in (0x10, 0x11):
        if type(value) is not int or not 0 <= value <= 99:
            raise ValueError('Backlash must be an integer from 0 to 99')
        data = bytes((value,))
    else:
        raise ValueError('Unsupported motor setting write')
    body = bytes((len(data) + 3, 0x20, axis, command)) + data
    return b'\x3b' + body + bytes((-sum(body) & 255,))


@exclusive_endpoint
def motor_settings(host, port, axis, *, changes=None, expected_backlash=None, interface_mode="legacy", include_extended=False, callback=lambda e: None):
    if interface_mode not in ("legacy", "modern"):
        raise ValueError("Motor settings require a physical-module mode; proxies are read-only")
    host, port = validate_endpoint(host, port)
    if axis not in AXES:
        raise ValueError('Select a motor axis')
    changes = changes or {}
    packets = [(command, setting_packet(axis, command, value)) for command, value in changes.items()]
    recorder = LiveRecorder(callback, ())
    report = {'host': host, 'port': port, 'axis': axis, 'writes': [], 'movement_sent': False}
    probe = None
    def read(axis, command, size):
        result = probe.query(axis, command, attempts=2)
        if result is None or len(result) != size:
            raise ConnectionError(f'No valid readback: AUX {axis:02X}/{command:02X}')
        return result
    try:
        check_direct_route(host)
        probe = AuxProbe(host, port, recorder)
        if interface_mode == "legacy":
            probe.receive(.6)
        if interface_mode == "modern" and any(c in (0x10, 0x11) for c in changes):
            # Require readable compensation values before attempting an optional write.
            read(axis, 0x40, 1)
            read(axis, 0x41, 1)
        # Optional writes require a valid capability read even if a GUI cache says
        # supported. The same motor AUX endpoints apply through both Wi-Fi families.
        for command in changes:
            if command == 0xFD and read(axis, 0xFC, 1)[0] not in (0, 1):
                raise ValueError('Unrecognized GoTo approach encoding; no write sent')
            if command in (0x38, 0x39, 0x3A):
                if read(axis, 0x3B, 1)[0] not in (0, 255):
                    raise ValueError('Unrecognized cord-wrap encoding; no write sent')
                read(axis, 0x3C, 3)
        if packets:
            first = {a: int.from_bytes(read(a, 1, 3), 'big') for a in AXES}
            time.sleep(.3)
            second = {a: int.from_bytes(read(a, 1, 3), 'big') for a in AXES}
            if any(abs(relative_counts(second[a], first[a])) > 1 for a in AXES):
                raise RuntimeError('Encoder movement detected; settings not written')
        if expected_backlash is not None:
            actual = (read(axis, 0x40, 1)[0], read(axis, 0x41, 1)[0])
            if tuple(expected_backlash) != actual:
                raise RuntimeError('Backlash changed since your read. No delta written; read current values again.')
        for command, packet in packets:
            probe.receive(.25)
            probe.sock.sendall(packet)
            entry = {'command': command, 'sent': True, 'verified': False}
            report['writes'].append(entry)
            recorder.record('motor_setting_write', axis=axis, command=command, hex=packet.hex())
            # Wait for a matching acknowledgement before verifying the value.
            ack = probe.receive(1.2, axis, command)
            if ack is None:
                raise RuntimeError('Write acknowledgement missing; setting may have changed. Read before retrying.')
            query = {4: 1, 0x10: 0x40, 0x11: 0x41, 0xFD: 0xFC, 0x38: 0x3B, 0x39: 0x3B, 0x3A: 0x3C}[command]
            raw = read(axis, query, 3 if command in (4, 0x3A) else 1)
            wanted = b'\xff' if command == 0x38 else b'\x00' if command == 0x39 else packet[5:-1]
            if raw != wanted:
                raise RuntimeError('Setting readback mismatch; partial changes may remain')
            entry['verified'] = True
        raw_position = read(axis, 1, 3)
        def optional_backlash(command):
            try:
                return read(axis, command, 1)[0]
            except ConnectionError:
                if interface_mode == 'legacy':
                    raise
                return None
        pos = optional_backlash(0x40)
        neg = optional_backlash(0x41)
        if any(v is not None and v > 99 for v in (pos, neg)):
            raise ValueError('Unrecognized backlash encoding')
        report['values'] = {'encoder': int.from_bytes(raw_position, 'big'),
                            'degrees': angle(int.from_bytes(raw_position, 'big')),
                            'positive_backlash': pos, 'negative_backlash': neg}
        if include_extended:
            values = report['values']
            for key, command, size, allowed in (
                    ('approach', 0xFC, 1, (0, 1)),
                    ('cordwrap_enabled', 0x3B, 1, (0, 255)),
                    ('cordwrap_position', 0x3C, 3, None)):
                values[key] = None
                if key.startswith('cordwrap') and axis != 0x10:
                    continue
                try:
                    raw = read(axis, command, size)
                    value = int.from_bytes(raw, 'big')
                    if allowed is not None and value not in allowed:
                        raise ValueError('Unrecognized encoding')
                    values[key] = value
                except (ConnectionError, ValueError) as error:
                    report.setdefault('unavailable', {})[key] = str(error)

    except Exception as error:
        report['error'] = str(error)
    finally:
        if probe:
            probe.close()
        report['log_directory'] = str(recorder.directory)
        recorder.finish(report)
    return report
