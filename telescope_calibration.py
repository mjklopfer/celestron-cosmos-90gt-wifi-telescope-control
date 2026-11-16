"""Telescope-specific pulse measurements; encoder scale is protocol-derived."""
import datetime as dt
import json
import math
import re
from pathlib import Path
from celestron_probe import ROOT

DEFAULT_CONFIG = ROOT / 'telescope-calibration.json'
COUNTS_PER_TURN = 1 << 24


def from_report(report, host, port=2000):
    """Keep raw evidence and direction-specific effective pulse rates."""
    samples = []
    for item in report.get('results', []):
        seconds = item.get('elapsed_seconds', 0)
        degrees = item.get('measured_degrees')
        if (item.get('stationary_verified') is not True or degrees is None
                or not math.isfinite(seconds) or seconds <= 0
                or not math.isfinite(degrees) or degrees * item['direction'] <= 0):
            continue
        samples.append(dict(item, effective_deg_per_second=abs(degrees) / seconds))
    return {
        'schema_version': 1,
        'observed_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'telescope': {'model': 'COSMOS 90GT', 'host': host, 'port': port,
                      'identity_note': 'Endpoint is not a unique hardware serial number.'},
        'encoder': {'counts_per_turn': COUNTS_PER_TURN,
                    'degrees_per_count': 360 / COUNTS_PER_TURN,
                    'source': 'Documented 24-bit AUX full-turn representation',
                    'independently_measured_physical_scale': False},
        'rate_method': 'Encoder displacement / host measured command interval, including ramps, backlash and transport effects; not steady-state speed.',
        'estimated_duration_bounds_seconds': [0.1, 2.0],
        'source_log': report.get('session_log'),
        'calibration_error': report.get('error'),
        'samples': samples,
    }


def save_config(config, path=DEFAULT_CONFIG):
    """Atomically replace the profile; preserve an existing profile as .previous."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config, indent=2, allow_nan=False) + '\n'
    if path.exists():
        path.with_suffix(path.suffix + '.previous').write_bytes(path.read_bytes())
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(path)


def load_config(path=DEFAULT_CONFIG):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    if config.get('schema_version') != 1:
        raise ValueError('Unsupported calibration schema')
    baseline = config.get('latest_baseline', {}).get('report', {})
    mac = report_mac(baseline)
    if mac and not config['telescope'].get('adapter_mac'):
        config['telescope']['adapter_mac'] = mac
        config['telescope']['identity_note'] = 'WiFly adapter MAC identifies the profile; IP is its last verified network address. Recalibrate if the adapter moves to another mount.'
    return config


def report_mac(report):
    """Read only an actual successful get mac reply, never an SSID suffix."""
    for row in report.get('rows', []):
        if row.get('endpoint') == 'get mac' and row.get('status') == 'REPLY':
            match = re.search(r'Mac Addr\s*=\s*((?:[0-9a-f]{2}:){5}[0-9a-f]{2})', row.get('reply', ''), re.I)
            if match:
                return match[1].upper()
    return None


def identify_profile(config, report):
    """Update the network address only after the same adapter answers at it."""
    if report.get('saved_report'):
        raise ValueError('Saved diagnostics cannot verify the current telescope address')
    mac = report_mac(report)
    if not mac:
        raise ValueError('No adapter MAC reply; profile identity is unverified')
    device = config['telescope']
    expected = device.get('adapter_mac')
    if expected and expected != mac:
        raise ValueError('Different adapter MAC; calibration was not reassigned')
    if not expected and config.get('samples') and report.get('host') != device['host']:
        raise ValueError('Old calibration has no stable identity; verify its original telescope first')
    device.update(adapter_mac=mac, host=report['host'], port=report.get('port', 2000),
                  identity_note='WiFly adapter MAC identifies the profile; IP is its last verified network address. Recalibrate if the adapter moves to another mount.')


def profile_label(config):
    device = config['telescope']
    mac = device.get('adapter_mac')
    return f'SkyQLink RN-171 · MAC {mac}' if mac else 'Unidentified telescope — run diagnostics to read adapter MAC'


def measured_rate(config, axis, rate, direction):
    values = [s['effective_deg_per_second'] for s in config.get('samples', [])
              if s['axis'] == axis and s['rate'] == rate and s['direction'] == direction]
    if not values or any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('No valid measurement for this axis, speed and direction')
    return sum(values) / len(values)


def estimate_seconds(config, axis, rate, degrees, host, port=2000):
    if config['telescope']['host'] != host or config['telescope']['port'] != port:
        raise ValueError('Address has changed: run diagnostics or a calibration --snapshot to verify the same adapter MAC before using this profile')
    if not math.isfinite(degrees) or degrees == 0:
        raise ValueError('Enter a finite, nonzero relative angle')
    seconds = abs(degrees) / measured_rate(config, axis, rate, 1 if degrees > 0 else -1)
    if not .1 <= seconds <= 2:
        raise ValueError(f'Estimated duration {seconds:.3f}s is outside the supported 0.1–2s jog range')
    return seconds


def relative_target(current_encoder, degrees):
    """Compute a target only; this never sends an unverified GOTO command."""
    if not isinstance(current_encoder, int) or not 0 <= current_encoder < COUNTS_PER_TURN:
        raise ValueError('Invalid encoder count')
    if not math.isfinite(degrees) or not -180 < degrees < 180:
        raise ValueError('Relative target must be less than half a turn')
    return (current_encoder + round(degrees * COUNTS_PER_TURN / 360)) % COUNTS_PER_TURN
