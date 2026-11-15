"""Read simulator USB diagnostics without toggling reset or logging credentials."""
import argparse
from pathlib import Path
import time

import serial


def main():
    """Parse command-line options and run this module’s entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--seconds", type=float, default=600)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    device = serial.Serial(port=None, baudrate=115200, timeout=0.3)
    device.dtr = False
    device.rts = False
    device.port = args.port
    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
    log = args.log.open("a", encoding="utf-8") if args.log else None
    try:
        device.open()
        end = time.monotonic() + args.seconds
        next_status = 0
        while time.monotonic() < end:
            if time.monotonic() >= next_status:
                device.write(b"STATUS\n")
                next_status = time.monotonic() + 10
            line = device.readline().decode("utf-8", "replace").strip()
            if line:
                print(line, flush=True)
                if log:
                    log.write(line + "\n")
                    log.flush()
    finally:
        device.close()
        if log:
            log.close()


if __name__ == "__main__":
    main()
