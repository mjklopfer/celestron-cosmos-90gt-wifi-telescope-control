"""Read-only inventory of supported WiFly queries and AUX motor endpoints."""
import socket
import time
from celestron_probe import AuxProbe
from motor_control import AXES, angle, version
from setup_backend import LiveRecorder, validate_endpoint, check_direct_route
from wifly_configure import Session, sanitize
from endpoint_lock import exclusive_endpoint

WIFI_QUERIES = ('ver', 'get mac', 'get wlan', 'get ip', 'get uart', 'get com',
                'get sys', 'get option', 'show net', 'show rssi', 'show stats', 'show time')


@exclusive_endpoint
def diagnose(host, port, callback=lambda event: None):
    host, port = validate_endpoint(host, port)
    recorder = LiveRecorder(callback, ())
    report = {'host': host, 'port': port, 'settings_changed': False,
              'movement_sent': False, 'rows': [], 'wifi_verified': False,
              'motor_positions_verified': False}

    def row(device, endpoint, status, reply):
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
                    for command in WIFI_QUERIES:
                        try:
                            reply = session.command(command)
                            row('Wi-Fi adapter', command, 'REPLY', reply)
                            if command == 'ver':
                                report['wifi_verified'] = 'WiFly' in reply and 'RN-171' in reply
                        except Exception as error:
                            row('Wi-Fi adapter', command, 'ERROR',
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
            for axis, name in (*AXES.items(), (0xb5, 'Wi-Fi AUX node (optional)')):
                reply = probe.query(axis, 0xfe)
                endpoint = f'AUX 0x{axis:02X} / GET_VER 0xFE'
                if reply is not None and len(reply) in (2, 4):
                    row(name, endpoint, 'REPLY', f'Firmware {version(reply)}; raw {reply.hex()}')
                    motor_versions[axis] = version(reply)
                else:
                    row(name, endpoint, 'NO VALID REPLY', 'Timed out' if reply is None else reply.hex())
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
                        row(name, endpoint, 'NO VALID REPLY', 'Timed out' if reply is None else reply.hex())
            report['motor_positions_verified'] = len(positions) == len(AXES)
            report['motor_firmware_verified'] = all(a in motor_versions for a in AXES)
        finally:
            probe.close()
    except Exception as error:
        report['error'] = sanitize(str(error))
        row('Connection', f'{host}:{port}', 'ERROR', report['error'])
    finally:
        report['log_directory'] = str(recorder.directory)
        recorder.finish(report)
    return report
