"""Standalone COSMOS calibration/baseline utility, deliberately outside the GUI.

Install this project's normal dependencies and run with its Python environment.
No arguments cause motion. Examples (replace the address/config path as needed):

  python calibrate_telescope.py --host 192.168.1.231 --snapshot
  python calibrate_telescope.py --host 192.168.1.231 --snapshot --deep
  python calibrate_telescope.py --host 192.168.1.231 --snapshot --device-reset-confirmed
  python calibrate_telescope.py --host 192.168.1.231 --move --clearance-deg 5
  python calibrate_telescope.py --host 192.168.1.231 --import-report prior-run.json

--snapshot reads available WiFly/AUX settings, raw replies and interpretations,
including motor positions/backlash and optional GPS/RTC endpoints. --deep adds
the application's allowlisted intrusive reads. Unsupported/missing data remains
explicitly unknown. No reset, provisioning, clock or encoder setting is written.
--device-reset-confirmed labels a snapshot USER-DECLARED reset/default state;
it does not verify factory defaults or reset anything. Use it only after manually
resetting the intended device. Without it, snapshots are current configured state.
Previous snapshots are retained in baseline_history and never become normative
defaults automatically. Do not reset a working Wi-Fi setup merely to collect one.

--move explicitly authorizes physical movement. Disconnect all controllers,
supervise the telescope, and confirm unobstructed travel/cable clearance of at
least --clearance-deg in BOTH directions on BOTH axes. This runs positive then
negative pulses at rates 1..9, one axis at a time, at most one second each.
It uses the production motor watchdog/Stop/encoder checks and aborts on any
uncertain result. No automated return-to-origin is attempted after failure.
Ctrl+C enters cleanup and sends Stop. Loss of transport may prevent delivery;
the operator must remain able to cut power. Counts alone cannot prove clearance.

Effective rates are encoder displacement divided by host command duration.
Ramps, backlash, deceleration, load and transport jitter affect them; a single
one-second sample is NOT a general linear model or steady-state speed. Rates
are stored separately per axis, speed and direction with all sample evidence.
The 24-bit encoder-to-degree scale comes from AUX documentation, NOT an external
angular measurement. Relative targets can be computed, but this utility does
not send MC_GOTO_FAST/SLOW or establish celestial alignment.

Config defaults to ~/.cosmos90gt/telescope-calibration.json (or the data directory
selected by COSMOS90GT_DATA_DIR). --config overrides it. Existing rate samples
are replaced only by --move or --import-report; snapshots preserve them. Writes
are atomic and retain the previous config as .previous. After an IP change, --snapshot verifies the same adapter MAC before updating
the saved address. A different adapter MAC is rejected; use a separate profile. Credentials are redacted
by the shared diagnostic recorder. Review snapshots before publishing them.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import queue
import time
from diagnostics import diagnose
from motor_control import AXES, MotorController, relative_angle
from telescope_calibration import DEFAULT_CONFIG, from_report, load_config, save_config, identify_profile


def measure(host, port, clearance, seconds=1.0):
    if clearance < 5 or not .1 <= seconds <= 1:
        raise ValueError('Require at least 5 degrees clear travel and 0.1–1 second pulses')
    events = queue.Queue()
    controller = MotorController(host, port, events.put)
    results = []
    error = None

    def wait(kind, timeout=18):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                event = events.get(timeout=.1)
            except queue.Empty:
                continue
            if event['event'] in ('motor_error', 'motor_disconnected'):
                raise RuntimeError(event.get('message', 'Controller disconnected'))
            if event['event'] == kind:
                return event
        raise TimeoutError(kind)

    try:
        controller.start()
        wait('motor_connected')
        origin = dict(controller.positions)
        for rate in range(1, 10):
            for axis in AXES:
                for direction in (1, -1):
                    deadline = time.monotonic() + 10
                    while not (controller.connected.is_set() and all(
                            time.monotonic() - controller.position_times.get(a, 0) < 2 for a in AXES)):
                        if time.monotonic() > deadline:
                            raise RuntimeError('Fresh positions unavailable')
                        wait('motor_values', 4)
                    drift = abs(relative_angle(controller.positions[axis], origin[axis]))
                    # Conservative allowance above the published ~3 deg/s maximum;
                    # not a guarantee of physical travel or a substitute for supervision.
                    if drift + 4 * seconds > clearance:
                        raise RuntimeError('Remaining confirmed travel envelope is insufficient')
                    print(f'{AXES[axis]} rate {rate}, direction {direction:+d}, {seconds}s', flush=True)
                    controller.jog(axis, direction, rate, seconds)
                    result = wait('motor_motion_result')
                    result.update(rate=rate, direction=direction,
                                  elapsed_seconds=controller.report['jogs'][-1]['elapsed_seconds'])
                    results.append(result)
                    if (result['stationary_verified'] is not True
                            or result['measured_degrees'] is None
                            or direction * result['measured_degrees'] <= 0
                            or abs(relative_angle(result['end_encoder'], origin[axis])) > clearance):
                        raise RuntimeError('Movement/Stop verification failed; no further jogs')
                    time.sleep(.2)
    except (Exception, KeyboardInterrupt) as failure:
        error = str(failure) or 'Interrupted by operator'
    finally:
        controller.disconnect()
        if controller.thread:
            controller.thread.join(12)
        if controller.thread and controller.thread.is_alive():
            error = 'Worker still running; Stop delivery unconfirmed'
    return {'results': results, 'error': error,
            'session_log': str(controller.recorder.directory) if controller.recorder else None,
            'firmware': controller.firmware}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--move', action='store_true')
    parser.add_argument('--clearance-deg', type=float, default=0)
    parser.add_argument('--seconds', type=float, default=1)
    parser.add_argument('--snapshot', action='store_true')
    parser.add_argument('--deep', action='store_true')
    parser.add_argument('--device-reset-confirmed', action='store_true')
    parser.add_argument('--import-report', type=Path)
    args = parser.parse_args()
    if not (args.snapshot or args.move or args.import_report):
        parser.error('Select --snapshot, --move, or --import-report; no operation performed')
    if args.move and args.import_report:
        parser.error('Use --move or --import-report, not both')
    if args.device_reset_confirmed and not args.snapshot:
        parser.error('--device-reset-confirmed requires --snapshot')
    config = load_config(args.config) if args.config.exists() else from_report({}, args.host, args.port)
    if (config['telescope']['host'], config['telescope']['port']) != (args.host, args.port) and not args.snapshot:
        parser.error('Address changed: use --snapshot to verify the same adapter MAC first')
    if args.snapshot:
        snapshot = {'captured_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                    'classification': 'user_declared_reset_state' if args.device_reset_confirmed else 'current_observed_state',
                    'factory_defaults_independently_verified': False,
                    'report': diagnose(args.host, args.port, deep=args.deep)}
        identify_profile(config, snapshot['report'])
        config.setdefault('baseline_history', []).append(snapshot)
        config['latest_baseline'] = snapshot
        save_config(config, args.config)
    if args.move or args.import_report:
        report = (measure(args.host, args.port, args.clearance_deg, args.seconds) if args.move
                  else json.loads(args.import_report.read_text(encoding='utf-8')))
        updated = from_report(report, args.host, args.port)
        updated['telescope'] = dict(config['telescope'])
        updated['baseline_history'] = config.get('baseline_history', [])
        if 'latest_baseline' in config:
            updated['latest_baseline'] = config['latest_baseline']
        if config.get('samples'):
            updated['previous_calibration'] = {k: config[k] for k in ('observed_at_utc', 'samples')}
        save_config(updated, args.config)
        if report.get('error'):
            print('Incomplete calibration:', report['error'])
            return 1
    print('Saved config:', args.config)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
