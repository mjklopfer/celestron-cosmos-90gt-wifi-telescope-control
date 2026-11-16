"""Explicit WiFly time-setting operation, separate from read-only diagnostics."""
import datetime as dt
import secrets
import struct
import time
import ipaddress
import re
import socket
from diagnostics import clock_summary
from endpoint_lock import exclusive_endpoint
from setup_backend import LiveRecorder, check_direct_route, validate_endpoint
from wifly_configure import Session, sanitize


def compare_clock(replies, sampled_at):
    """Compare reported Unix RTC seconds with host UTC, never wall-clock text.

    UTC comparison needs no WiFly zone correction. Convert the same instant to
    the PC local zone for display only. Missing date is not guessed from today.
    """
    text = replies.get('show t t', '')
    host = dt.datetime.fromtimestamp(sampled_at, dt.timezone.utc)
    result = {'Computer local time': host.astimezone().isoformat(timespec='seconds'),
              'Computer UTC': host.isoformat(timespec='seconds')}
    if re.search(r'Time\s+NOT SET', text, re.I):
        result['Comparison'] = 'Time not set on WiFly; no valid date/time comparison.'
        return result
    match = re.search(r'^\s*RTC=(\d+)\s*$', text, re.M)
    clock = re.search(r'^\s*Time[=:]\s*\d{1,2}:\d{2}:\d{2}', text, re.M)
    if not match or not clock:
        result['Comparison'] = 'Date not available or clock validity unknown; cannot calculate a full date/time difference.'
        return result
    try:
        stamp = int(match[1])
        if stamp == 0:
            raise ValueError('unset')
        board = dt.datetime.fromtimestamp(stamp, dt.timezone.utc)
    except (ValueError, OverflowError, OSError):
        result['Comparison'] = 'Date not set or RTC outside supported calendar range.'
        return result
    delta = stamp - sampled_at
    result['WiFly UTC (from RTC)'] = board.isoformat(timespec='seconds')
    result['WiFly in computer local timezone'] = board.astimezone().isoformat(timespec='seconds')
    result['Difference seconds (WiFly minus computer)'] = round(delta, 1)
    result['Comparison'] = (
        ('Difference is greater than 1 day. ' if abs(delta) > 86400 else '')
        + f'WiFly is {abs(delta):.1f} seconds {"ahead of" if delta >= 0 else "behind"} the computer. '
        + 'Approximate sampled difference; includes network delay and one-second device resolution. '
        + 'RTC interpreted as UTC Unix seconds; no timezone offset is added.'
    )
    return result


@exclusive_endpoint
def configure_time(host, port=2000, *, enable=None, sync_now=False, persist=False, server_ip=None, callback=lambda e: None):
    host, port = validate_endpoint(host, port)
    if enable is not None and (type(enable) is not int or not 0 <= enable <= 65535):
        raise ValueError('Time enable must be 0 (off), 1 (startup), or 2–65535 minutes')
    if persist and enable is None:
        raise ValueError('Select a setting before saving')
    if server_ip is not None:
        address = ipaddress.IPv4Address(server_ip)
        if address.is_multicast or address.is_unspecified or address.is_loopback:
            raise ValueError('Use a unicast time-server IPv4 address')
    recorder = LiveRecorder(callback, ())
    report = {'host': host, 'port': port, 'operation': 'WiFly time settings', 'applied': False,
              'saved': False, 'sync_requested': False, 'movement_sent': False}
    try:
        check_direct_route(host)
        with socket.create_connection((host, port), 3) as sock:
            sock.settimeout(.2)
            session = Session(sock, recorder)
            try:
                session.enter()
                identity = session.command('ver')
                if 'RN-171' not in identity or '2.40-CEL' not in identity:
                    raise RuntimeError('Time writes restricted to identified RN-171 2.40-CEL')
                report['adapter_identity'] = sanitize(session.command('get mac'))
                report['before'] = sanitize(session.command('get time'))
                if server_ip is not None:
                    session.command(f'set time address {server_ip}', write=True)
                    session.command('set time port 123', write=True)
                    report['server_readback'] = sanitize(session.command('get time'))
                    if not re.search(r'(?im)^\s*(?:TIMEADR|ADDR)=' + re.escape(server_ip) + r':123\s*$', report['server_readback']):
                        raise RuntimeError('Time-server readback mismatch; not saved')
                if enable is not None:
                    session.command(f'set time enable {enable}', write=True)
                    report['write_acknowledged'] = True
                    readback = session.command('get time')
                    report['readback'] = sanitize(readback)
                    if not re.search(r'(?im)^\s*(?:TimeEna|ENA)=' + str(enable) + r'\s*$', readback):
                        raise RuntimeError('Time-enable readback mismatch; not saved')
                    report['applied'] = True
                    if persist:
                        reply = session.command('save')
                        report['save_reply'] = sanitize(reply)
                        if not re.search(r'Stor(?:ing|ed)', reply, re.I):
                            raise RuntimeError('Save not confirmed')
                        report['saved'] = True
                if sync_now:
                    report['sync_requested'] = True
                    report['sync_reply'] = sanitize(session.command('time'))
                replies = {q: sanitize(session.command(q)) for q in ('get time', 'show time', 'show t t')}
                report['clock_sampled_at'] = time.time()
                report['clock_comparison'] = compare_clock(replies, report['clock_sampled_at'])
                report['clock'] = clock_summary(replies)
                report['clock_replies'] = replies
                report['clock_text_available'] = report['clock']['Reported clock text'] != 'Not reported' and report['clock']['Status'] != 'Unset'
            finally:
                report['exit_confirmed'] = session.exit()
    except Exception as error:
        report['error'] = sanitize(str(error))
    finally:
        report['log_directory'] = str(recorder.directory)
        recorder.finish(report)
    return report

COMMON_TIME_SERVERS = ('time.cloudflare.com', 'time.google.com', '129.6.15.28')


def test_time_server(host):
    """One bounded SNTP query from this computer; never changes either clock."""
    host = host.strip()
    if not host or len(host) > 253 or not re.fullmatch(r'[A-Za-z0-9.:-]+', host):
        raise ValueError('Enter a time-server hostname or IPv4 address')
    addresses = socket.getaddrinfo(host, 123, socket.AF_INET, socket.SOCK_DGRAM)
    ip = addresses[0][4][0]
    address = ipaddress.IPv4Address(ip)
    if address.is_multicast or address.is_unspecified or address.is_loopback:
        raise ValueError('Select a reachable unicast time server')
    nonce = secrets.token_bytes(8)
    request = bytearray(48)
    request[0] = 0x23
    request[40:48] = nonce
    started = time.monotonic()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(3)
        sock.connect((ip, 123))
        sock.send(request)
        reply = sock.recv(512)
    if (len(reply) < 48 or reply[0] & 7 != 4 or reply[0] >> 6 == 3
            or not 1 <= reply[1] <= 15 or reply[24:32] != nonce):
        raise ValueError('Invalid, unsynchronized, or refused SNTP response')
    seconds, fraction = struct.unpack('!II', reply[40:48])
    if seconds == 0:
        raise ValueError('Missing server transmit timestamp')
    unix = seconds - 2208988800 + fraction / (1 << 32)
    # Select the NTP era closest to the local clock (rollover in 2036).
    unix += round((time.time() - unix) / (1 << 32)) * (1 << 32)
    return {'host': host, 'ip': ip, 'utc': dt.datetime.fromtimestamp(unix, dt.timezone.utc).isoformat(),
            'round_trip_ms': round((time.monotonic() - started) * 1000, 1), 'tested_at': time.monotonic(),
            'source': 'This computer; telescope connectivity not established'}


class UptimeEvidence:
    """Session-only adapter evidence. Unknown counter width means no wrap guess."""
    def __init__(self):
        self.samples = {}

    def observe(self, identity, clock, sampled_at=None):
        mac = re.search(r'(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', identity)
        uptime = re.fullmatch(r'(\d+)\s*(?:s)?', str(clock.get('Uptime', '')))
        if not mac or not uptime:
            return {'warning': False, 'message': 'Reset check unavailable: missing adapter identity or uptime.'}
        now = time.monotonic() if sampled_at is None else sampled_at
        key = mac[0].lower()
        current = (int(uptime[1]), now, clock.get('Restarts'))
        previous = self.samples.get(key)
        self.samples[key] = current
        if previous is None:
            return {'warning': False, 'message': 'Uptime baseline recorded for this adapter; no earlier session sample.'}
        decreased = current[0] < previous[0]
        restart_changed = (current[2] not in (None, 'Not reported')
                           and previous[2] not in (None, 'Not reported')
                           and current[2] != previous[2])
        if decreased or restart_changed:
            return {'warning': True, 'message': 'Adapter uptime or restart count changed unexpectedly. Possible adapter restart or counter discontinuity; rollover is not distinguishable on this firmware. This does not prove a motor-controller reset. Active local offsets cleared; establish a new reference before reapplying history.'}
        return {'warning': False, 'message': 'No adapter restart evidence in these samples; motor power continuity is not established.'}
