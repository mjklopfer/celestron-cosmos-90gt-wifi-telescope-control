"""Network smoke test. Refuses motor simulation unless identity says COSMOS-SIM."""
import argparse
import json
import socket
import time
from urllib.request import urlopen


def packet(axis, command, data=b""):
    body = bytes((len(data) + 3, 0x20, axis, command)) + data
    return b"\x3b" + body + bytes((-sum(body) & 255,))


def reply(connection, axis, command, data=b""):
    connection.sendall(packet(axis, command, data))
    buffer = bytearray()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        chunk = connection.recv(128)
        if not chunk:
            raise ConnectionError("Simulator disconnected")
        buffer.extend(chunk)
        while buffer:
            if buffer[0] != 0x3B:
                del buffer[0]
                continue
            if len(buffer) < 2:
                break
            size = buffer[1] + 3
            if size < 6 or size > 35:
                del buffer[0]
                continue
            if len(buffer) < size:
                break
            frame = bytes(buffer[:size])
            del buffer[:size]
            if sum(frame[1:]) & 255:
                raise ValueError("Bad AUX checksum")
            if frame[2:5] == bytes((axis, 0x20, command)):
                return frame[5:-1]
    raise TimeoutError("No matching simulated AUX reply")


def verify(host):
    with socket.create_connection((host, 3000), timeout=3) as manager:
        manager.sendall(b"version\n")
        identity = manager.recv(512).decode("ascii", "replace")
    if not identity.startswith("COSMOS-SIM-AMW007-"):
        raise RuntimeError("Refusing test: endpoint is not our isolated COSMOS-SIM firmware")
    with urlopen(f"http://{host}/", timeout=3) as response:
        assert "No physical motors" in response.read().decode()
    result = {"identity": identity.strip(), "host": host, "axes": {}}
    with socket.create_connection((host, 2000), timeout=3) as connection:
        try:
            for axis, name in ((0x10, "azimuth"), (0x11, "altitude")):
                version = reply(connection, axis, 0xFE)
                before = int.from_bytes(reply(connection, axis, 1), "big")
                assert reply(connection, axis, 0x24, b"\x09") == b"\x01"
                time.sleep(0.25)
                reply(connection, axis, 0x24, b"\x00")
                after = int.from_bytes(reply(connection, axis, 1), "big")
                delta = ((after - before + 8388608) % 16777216) - 8388608
                assert delta > 0, "Simulated position did not advance"
                time.sleep(0.1)
                stopped = int.from_bytes(reply(connection, axis, 1), "big")
                assert stopped == after, "Simulated Stop did not hold position"
                result["axes"][name] = {
                    "version": list(version), "before": before, "after": after,
                    "delta_counts": delta, "delta_degrees": delta * 360 / 16777216,
                    "stop_verified": True,
                }
        finally:
            for axis in (0x10, 0x11):
                connection.sendall(packet(axis, 0x24, b"\x00"))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    args = parser.parse_args()
    print(json.dumps(verify(args.host), indent=2))
