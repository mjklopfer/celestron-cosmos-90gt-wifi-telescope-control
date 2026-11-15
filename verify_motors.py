#!/usr/bin/env python3
"""Verify the production motor service, with optional bounded, measured jogs."""
import argparse
import queue
import time
from motor_control import MotorController, AXES


def verify(host, port=2000, move=False):
    events = queue.Queue()
    controller = MotorController(host, port, events.put)
    results = []

    def wait(kind, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                event = events.get(timeout=.1)
            except queue.Empty:
                continue
            if event['event'] in ('motor_error', 'motor_disconnected'):
                raise ConnectionError(event.get('message', 'Motor service disconnected'))
            if event['event'] == kind:
                return event
        raise TimeoutError('Timed out waiting for ' + kind)

    try:
        controller.start()
        wait('motor_connected')
        # Both current values must be visible through the same production events
        # consumed by the Tk application before issuing any test movement.
        initial = {}
        while len(initial) < len(AXES):
            event = wait('motor_values')
            initial[event['axis']] = event['encoder']
        print('VERIFIED initial encoder counts:', initial, flush=True)
        if move:
            for axis in AXES:
                for direction in (1, -1):
                    print(f'Test {AXES[axis]} {direction:+d}: rate 6, 0.5 seconds', flush=True)
                    controller.jog(axis, direction, 6, .5)
                    result = wait('motor_motion_result')
                    results.append(result)
                    print(result, flush=True)
                    if result['measured_counts'] is None or direction * result['measured_counts'] <= 0:
                        raise RuntimeError('Expected encoder movement was not measured')
                    if result['stationary_verified'] is not True:
                        raise RuntimeError('Stationary encoder samples were not verified after Stop')
        return results
    finally:
        controller.disconnect()
        if controller.thread:
            controller.thread.join(10)
        if controller.thread and controller.thread.is_alive():
            raise RuntimeError('Motor worker did not close; Stop delivery is unconfirmed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='1.2.3.4')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--move', action='store_true', help='Half-second forward and reverse test per axis')
    args = parser.parse_args()
    verify(args.host, args.port, args.move)


if __name__ == '__main__':
    main()
