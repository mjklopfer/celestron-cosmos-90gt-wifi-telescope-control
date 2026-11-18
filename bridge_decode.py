"""Conservative AUX trace descriptions, scoped by device and payload shape.

Primary command definitions: INDI indi-celestronaux/auxproto.h and Andre
Paquette NexStar AUX Command Set 1.0 (0xFC/0xFD approach). Additional
backlash/approach reads and writes match this project's motor_settings and
diagnostics modules. A description identifies protocol intent, never successful
execution or persisted settings. Echoes retain the original source/destination.
Unknown commands remain unknown; never apply a motor meaning to a GPS command.
"""
from diagnostics import decode_time_site, decode_motor_setting
from motor_control import angle, version

NODES = {0x01: 'Main board', 0x04: 'Hand controller', 0x0d: 'Hand controller+',
         0x10: 'Azimuth motor', 0x11: 'Elevation motor', 0x12: 'Focuser',
         0x20: 'Control app', 0xb0: 'GPS', 0xb2: 'RTC', 0xb5: 'Wi-Fi adapter'}
MOTOR = {1: 'Read position', 2: 'GoTo fast', 4: 'Set encoder reference (not sky alignment)',
         5: 'Read model', 6: 'Set positive guide/tracking rate', 7: 'Set negative guide/tracking rate',
         0x10: 'Set positive backlash', 0x11: 'Set negative backlash', 0x13: 'Read slew-complete status',
         0x17: 'GoTo slow', 0x24: 'Move positive', 0x25: 'Move negative',
         0x26: 'AUX guide pulse', 0x27: 'Read AUX guide active',
         0x38: 'Enable cord-wrap protection', 0x39: 'Disable cord-wrap protection',
         0x3a: 'Set cord-wrap position', 0x3b: 'Read cord-wrap enabled', 0x3c: 'Read cord-wrap position',
         0x40: 'Read positive backlash', 0x41: 'Read negative backlash',
         0x46: 'Set autoguide rate', 0x47: 'Read autoguide rate',
         0xfc: 'Read GoTo approach', 0xfd: 'Set GoTo approach'}
TIME = {1: 'Read latitude', 2: 'Read longitude', 3: 'Read month/day', 4: 'Read year',
        0x33: 'Read UTC time', 0x36: 'Read time-valid status', 0x37: 'Read GPS-linked status',
        0x83: 'Set RTC month/day', 0x84: 'Set RTC year', 0xb3: 'Set RTC time'}


def describe_aux(frame):
    """Return best-effort text without hiding the raw packet or raising on data."""
    if len(frame) < 6:
        return 'Incomplete AUX frame'
    src, dst, cmd = frame[2:5]
    data = frame[5:-1]
    reply = src not in (0x20, 0x04, 0x0d) and dst in (0x20, 0x04, 0x0d)
    device = src if reply else dst
    label = f'{NODES.get(src, f"Device 0x{src:02X}")} → {NODES.get(dst, f"Device 0x{dst:02X}")}: '
    name = 'Read firmware version' if cmd == 0xfe else (
        MOTOR.get(cmd, f'Unknown command 0x{cmd:02X}') if device in (16, 17) else
        TIME.get(cmd, f'Unknown command 0x{cmd:02X}') if (device == 0xb0 and cmd in (1, 2, 3, 4, 0x33, 0x36, 0x37)) or (device == 0xb2 and cmd in (3, 4, 0x33, 0x83, 0x84, 0xb3)) else
        f'Unknown command 0x{cmd:02X}')
    detail = ''
    try:
        if cmd == 0xfe and reply and data:
            detail = version(data)
        elif device in (16, 17):
            if cmd in (1, 2, 4, 0x17, 0x3a, 0x3c) and len(data) == 3:
                count = int.from_bytes(data, 'big')
                detail = f'{count} counts = {angle(count):.6f}° raw motor angle'
            elif cmd in (0x24, 0x25) and not reply and len(data) == 1:
                detail = 'STOP' if data[0] == 0 else f'speed level {data[0]}'
            elif cmd in (6, 7) and not reply and data:
                detail = f'raw rate {int.from_bytes(data, "big")} (conversion not asserted)'
            elif reply and cmd in (0x13, 0x3b, 0x40, 0x41, 0x47, 0xfc):
                detail = decode_motor_setting(cmd, data)
            elif not reply and cmd in (0x10, 0x11) and len(data) == 1:
                detail = f'{data[0]} compensation units (not degrees)'
            elif not reply and cmd == 0xfd and data in (b'\x00', b'\x01'):
                detail = 'positive approach' if data == b'\x00' else 'negative approach'
        elif device in (0xb0, 0xb2) and reply and cmd in (1, 2, 3, 4, 0x33, 0x36, 0x37):
            detail = str(decode_time_site(cmd, data)[1])
    except (ValueError, IndexError, TypeError, KeyError):
        detail = 'Unexpected payload; interpretation unavailable'
    if data and not detail:
        detail = f'payload {data.hex(" ").upper()} (meaning unverified)'
    return label + name + (' reply' if reply else ' request/echo') + (': ' + detail if detail else '')
