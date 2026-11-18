"""Experimental, independently written HomeBrew management adapter.

NEEDS HARDWARE TESTING: fakegps latitude longitude is documented by HomeBrew;
TCP 3000 prompt framing, help/version response formats, persistence and readback
are provisional. This is NOT a stock Celestron or WiFly command. No third-party
firmware is included. See docs/HOMEBREW-INTERFACES.md for evidence and test gates.

Preview (no network): python -m homebrew_settings --latitude 33 --longitude -117
Explicit lab write: add --host ADDRESS --apply-unverified. Disconnect other
controllers first. This sets location only, not time, alignment or tracking.
"""
import argparse
import json
import math
import re
import socket
import time

from endpoint_lock import EndpointLease
from setup_backend import validate_endpoint


def location_plan(latitude, longitude):
    lat, lon = float(latitude), float(longitude)
    if not math.isfinite(lat) or not -90 <= lat <= 90:
        raise ValueError('Latitude must be finite and between -90 and 90 degrees.')
    if not math.isfinite(lon) or not -180 <= lon <= 180:
        raise ValueError('Longitude must be finite and between -180 and 180 degrees.')
    return {'status': 'UNVERIFIED — hardware test required', 'family': 'HomeBrew',
            'command': f'fakegps {lat:.6f} {lon:.6f}', 'management_port': 3000,
            'latitude_deg': lat, 'longitude_deg': lon, 'time_sent': False,
            'alignment_established': False, 'persistence': 'unverified'}


def read_prompt(sock):
    """Bounded prompt reader; fail closed on truncation, timeout or disconnect."""
    data = bytearray()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and len(data) < 32768:
        try:
            chunk = sock.recv(min(4096, 32768 - len(data)))
        except socket.timeout:
            continue
        if not chunk:
            break
        data.extend(chunk)
        if re.search(rb'(?:^|[\r\n])>\s*$', data):
            return data.decode('utf-8', 'replace')
    raise ConnectionError('HomeBrew command prompt not received; operation stopped.')


def apply_location(host, latitude, longitude, *, allow_unverified=False):
    plan = location_plan(latitude, longitude)
    if not allow_unverified:
        raise ValueError('Experimental HomeBrew writes require explicit opt-in.')
    host, _ = validate_endpoint(host, 2000)
    # Lock both the motor endpoint and management endpoint. Identification is
    # repeated on this socket; a discovery label or SSID is not sufficient.
    with EndpointLease(host, 2000), EndpointLease(host, 3000):
        with socket.create_connection((host, 3000), 3) as sock:
            sock.settimeout(.25)
            read_prompt(sock)

            def command(text):
                sock.sendall((text + '\r\n').encode('ascii'))
                return read_prompt(sock)

            identity = command('version')
            if not re.search(r'\b(?:HBG[34]|HomeBrew)\b', identity, re.I):
                raise ValueError('HomeBrew identity not confirmed; no location write sent.')
            help_text = command('help')
            if not re.search(r'\bfakegps\b', help_text, re.I):
                raise ValueError('Device does not advertise fakegps; no location write sent.')
            reply = command(plan['command'])
            # A prompt/ACK is NOT proof of stored coordinates or GPS validity.
            # Do not silently issue save or retry a write after connection loss.
            return dict(plan, write_sent=True, readback_verified=False,
                        identity=identity, reply=reply,
                        status='Write sent; acceptance and GPS readback remain unverified')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--latitude', required=True, type=float)
    parser.add_argument('--longitude', required=True, type=float)
    parser.add_argument('--host')
    parser.add_argument('--apply-unverified', action='store_true',
                        help='Send experimental location write after live identity/capability checks.')
    args = parser.parse_args()
    try:
        if args.apply_unverified and not args.host:
            parser.error('--host is required with --apply-unverified')
        result = (apply_location(args.host, args.latitude, args.longitude, allow_unverified=True)
                  if args.apply_unverified else location_plan(args.latitude, args.longitude))
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, OSError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
