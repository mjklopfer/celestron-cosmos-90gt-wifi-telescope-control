#!/usr/bin/env python3
"""Opt-in live validation of Tk arrow events, encoder fields, and link recovery."""
import argparse
import time
import tkinter as tk
from celestron_probe import Recorder
from skyqlink_setup import SetupApp


def main():
    """Parse command-line options and run this module’s entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--move', action='store_true', help='Test 0.7-second holds in all four directions')
    parser.add_argument('--soak-seconds', type=float, default=0, help='Continue reading both axes after the checks')
    args = parser.parse_args()
    root = tk.Tk()
    app = SetupApp(root)
    app.host.set(args.host)
    app.port.set(str(args.port))
    app.connection_mode.set('infrastructure' if args.host != '1.2.3.4' else 'direct')
    app.update_mode_help()
    recorder = Recorder('gui-hardware-validation')
    report = {'host': args.host, 'port': args.port, 'movement_requested': args.move, 'results': []}
    deadline = time.monotonic() + 100 + args.soak_seconds
    phase = 'connecting'
    controller = None
    sequence = [(2, 0x10, 1), (1, 0x10, -1), (0, 0x11, 1), (3, 0x11, -1)]
    step = 0
    soak_until = next_progress = 0

    def finish(error=None):
        """Save the opt-in hardware-check result and close the GUI services."""
        nonlocal phase
        if phase == 'closing':
            return
        phase = 'closing'
        if error:
            report['error'] = str(error)
        report['motor_log_directory'] = str(controller.recorder.directory) if controller and controller.recorder else None
        report['recovery_attempted'] = app.connect_recovery_attempted
        recorder.finish(report)
        app.close()

    def press(index):
        """Generate a bounded GUI arrow hold for the explicitly requested hardware check."""
        button = app.jog_buttons[index]
        root.focus_force()
        button.focus_set()
        button.event_generate('<ButtonPress-1>', x=10, y=10)
        root.after(700, lambda: button.event_generate('<ButtonRelease-1>', x=10, y=10))

    def watch():
        """Advance the opt-in hardware-check state machine from current GUI telemetry."""
        nonlocal phase, controller, step, soak_until, next_progress
        if phase == 'closing':
            return
        try:
            if time.monotonic() > deadline:
                raise TimeoutError('GUI hardware check timed out: ' + app.motion_status.get())
            if phase == 'connecting' and app.motor_ready and len(app.last_positions) == 2:
                controller = app.motor
                report['initial_fields'] = {str(axis): app.values[axis]['encoder'].get() for axis in app.values}
                if not args.move:
                    phase = 'soak'
                    soak_until = time.monotonic() + args.soak_seconds
                else:
                    phase = 'moving'
                    press(sequence[step][0])
            elif phase == 'moving' and controller and controller.report['jogs']:
                entries = controller.report['jogs']
                expected = step + 1
                if len(entries) >= expected and 'measured_counts' in entries[expected - 1] and not app.jogging:
                    entry = dict(entries[expected - 1])
                    values = app.values[sequence[step][1]]
                    result = {**entry, 'displayed_delta_counts': values['delta_counts'].get(),
                              'displayed_delta_angle': values['delta_degrees'].get(),
                              'displayed_stop_check': values['stationary'].get()}
                    report['results'].append(result)
                    if entry['measured_counts'] is None or entry['direction'] * entry['measured_counts'] <= 0:
                        raise RuntimeError('No encoder motion in the commanded direction')
                    if entry['stationary_verified'] is not True or result['displayed_stop_check'] != 'Verified':
                        raise RuntimeError('GUI stop verification did not pass')
                    if result['displayed_delta_counts'] != f'{entry["measured_counts"]:+d}':
                        raise RuntimeError('Displayed encoder delta differs from the measured value')
                    step += 1
                    if step < len(sequence):
                        press(sequence[step][0])
                    else:
                        phase = 'soak'
                        soak_until = time.monotonic() + args.soak_seconds
            elif phase == 'soak':
                if not app.motor_ready or any(time.monotonic() - t > 3 for t in app.last_positions.values()):
                    raise RuntimeError('Live feedback stopped during the continuous-read check')
                if time.monotonic() >= next_progress:
                    print('Continuous feedback:', controller.positions, flush=True)
                    next_progress = time.monotonic() + 30
                if time.monotonic() >= soak_until:
                    report['continuous_read_seconds'] = args.soak_seconds
                    report['final_counts'] = dict(controller.positions)
                    finish()
                    return
        except Exception as error:
            finish(error)
            return
        root.after(50, watch)

    root.after(300, app.connect_motors)
    root.after(400, watch)
    root.mainloop()
    if report.get('error'):
        raise SystemExit(report['error'])


if __name__ == '__main__':
    main()
