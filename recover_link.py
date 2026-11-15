#!/usr/bin/env python3
"""Explicit RN-171 restart, preserving stored settings, then read-only AUX check."""
import argparse
import socket
import time
from celestron_probe import AuxProbe
from setup_backend import check_direct_route, validate_endpoint, LiveRecorder
from wifly_configure import Session, sanitize
from endpoint_lock import exclusive_endpoint


@exclusive_endpoint
def recover(host, port=2000, callback=lambda event: None):
    host, port = validate_endpoint(host, port)
    check_direct_route(host)
    recorder = LiveRecorder(callback, ())
    report = {'host': host, 'port': port, 'movement_sent': False,
              'configuration_writes_sent': False, 'restart_sent': False}
    probe = None
    try:
        recorder.record('stage', message=f'Restarting the verified RN-171 at {host}:{port}; saved Wi-Fi settings retained')
        with socket.create_connection((host, port), 3) as sock:
            sock.settimeout(.2)
            session = Session(sock, recorder)
            session.enter()
            try:
                identity = session.command('ver')
                report['identity'] = sanitize(identity)
                if '2.40-CEL' not in identity or 'RN-171' not in identity:
                    raise RuntimeError('Restart restricted to the identified legacy adapter')
                report['uart_before'] = sanitize(session.command('get uart'))
                # No set, save, factory reset, boot-image, or firmware command.
                recorder.record('restart_tx', command='reboot')
                sock.sendall(b'reboot\r')
                report['restart_sent'] = True
                try:
                    report['restart_reply'] = sanitize(session.receive(2))
                except ConnectionError:
                    report['restart_connection_closed'] = True
            finally:
                if session.entered and not report['restart_sent']:
                    report['exit_confirmed'] = session.exit()
        deadline = time.monotonic() + 40
        # Allow the radio to restart before opening its shared control socket.
        time.sleep(3)
        while time.monotonic() < deadline:
            try:
                probe = AuxProbe(host, port, recorder)
                break
            except OSError:
                time.sleep(1)
        if probe is None:
            raise ConnectionError('Adapter has not returned at the previous IP; discover its DHCP address')
        probe.receive(.6)
        report['positions'] = {}
        for axis in (0x10, 0x11):
            reply = probe.query(axis, 1)
            report['positions'][hex(axis)] = int.from_bytes(reply, 'big') if reply is not None and len(reply) == 3 else None
        report['motor_positions_verified'] = all(p is not None for p in report['positions'].values())
    except Exception as error:
        report['error'] = sanitize(str(error))
    finally:
        if probe:
            probe.close()
        report['log_directory'] = str(recorder.directory)
        recorder.finish(report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    recover(args.host, args.port)
