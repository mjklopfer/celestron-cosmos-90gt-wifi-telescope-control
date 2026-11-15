"""Check the physical ESP32 portal/scan; optionally save local-hotspot mode."""
import argparse
import json
from pathlib import Path
import re
import socket
import time
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener


def verify(host, save_hotspot=False):
    with socket.create_connection((host, 3000), timeout=3) as manager:
        manager.sendall(b"version\n")
        identity = manager.recv(512).decode("ascii", "replace")
    if not identity.startswith("COSMOS-SIM-AMW007-"):
        raise RuntimeError("Endpoint is not our isolated simulator")
    opener = build_opener(ProxyHandler({}))
    base = f"http://{host}"
    with opener.open(base + "/", timeout=5) as response:
        page = response.read().decode("utf-8")
        assert response.headers.get_content_charset() == "utf-8"
    assert "Scan nearby Wi-Fi networks" in page
    assert "Keep a local hotspot" in page
    assert "Join another Wi-Fi network" in page
    token = re.search(r'name="token" value="([a-f0-9]+)"', page)
    assert token, "Expected setup form"
    with opener.open(base + "/scan?start=1", timeout=6) as response:
        status, body = response.status, response.read()
    deadline = time.monotonic() + 30
    while status == 202 and time.monotonic() < deadline:
        time.sleep(0.7)
        with opener.open(base + "/scan", timeout=6) as response:
            status, body = response.status, response.read()
    assert status == 200, "Scan did not finish"
    networks = json.loads(body)["networks"]
    for network in networks:
        assert all(key in network for key in ("ssid", "rssi", "security", "supported", "open"))
    result = {"identity": identity.strip(), "portal": "passed", "network_count": len(networks),
              "network_metadata": "passed", "saved_hotspot": False}
    if save_hotspot:
        data = urlencode({"mode": "hotspot", "token": token.group(1)}).encode()
        with opener.open(Request(base + "/configure", data=data), timeout=5) as response:
            saved = response.read().decode("utf-8")
        assert "Saved. Rebooting." in saved
        assert "http://1.2.3.4/" in saved
        result["saved_hotspot"] = True
        result["reboot_verification"] = "Reconnect to hotspot and verify 1.2.3.4 separately"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("--save-hotspot", action="store_true",
                        help="Save local hotspot mode and reboot this disposable simulator")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.host, args.save_hotspot)
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")
