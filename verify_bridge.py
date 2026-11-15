#!/usr/bin/env python3
"""Read-only relay/reconnect verification; listeners stay on loopback, no advertisements."""
import argparse
import queue
import socket
import time
from bridge_mode import Bridge
from celestron_probe import FrameParser
from motor_control import motor_packet


def verify(host, port=2000):
    events = queue.Queue()
    bridge = Bridge(host, port, events.put, bind_host='127.0.0.1', listen_port=0,
                    management_port=0, advertise=False)
    results = []
    bridge.start()
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            event = events.get(timeout=3)
            if event['event'] == 'bridge_error':
                raise ConnectionError(event['message'])
            if event['event'] == 'bridge_ready':
                break
        else:
            raise TimeoutError('Bridge did not become ready')
        for cycle in range(3):
            with socket.create_connection(('127.0.0.1', bridge.listen_port), 2) as client:
                client.settimeout(3)
                parser = FrameParser()
                counts = {}
                for axis in (16, 17):
                    client.sendall(motor_packet(axis, 1))
                    deadline = time.monotonic() + 4
                    while time.monotonic() < deadline:
                        for frame in parser.feed(client.recv(4096)):
                            if frame[2:5] == bytes((axis, 32, 1)) and len(frame[5:-1]) == 3:
                                counts[str(axis)] = int.from_bytes(frame[5:-1], 'big')
                        if str(axis) in counts:
                            break
                    if str(axis) not in counts:
                        raise TimeoutError('Missing relayed encoder reply')
                results.append(counts)
                print('Read-only relay cycle', cycle + 1, counts, flush=True)
            # Wait for the bridge to detect EOF and send Stops before reconnecting.
            deadline = time.monotonic() + 3
            while bridge.client is not None and time.monotonic() < deadline:
                time.sleep(.02)
            if bridge.client is not None:
                raise TimeoutError('Bridge did not release disconnected client')
            time.sleep(.2)
        bridge.report['relay_read_results'] = results
        bridge.report['verification_motion_requested'] = False
    finally:
        bridge.stop()
        bridge.thread.join(10)
        if bridge.thread.is_alive():
            raise RuntimeError('Bridge failed to stop')
    if bridge.report['errors'] or len(results) != 3:
        raise RuntimeError('Bridge relay verification failed: ' + str(bridge.report['errors']))
    if not all(bridge.report.get('cleanup_stop_replies', {}).get(str(a)) for a in (16, 17)):
        raise RuntimeError('Final Stop acknowledgements incomplete; see saved report')
    return bridge.report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    verify(args.host, args.port)
