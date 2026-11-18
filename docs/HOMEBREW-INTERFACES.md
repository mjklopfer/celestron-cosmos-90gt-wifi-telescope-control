# Alternative interfaces and ESP32 compatibility plan

Research checkpoint: 2026-11-18. These are implementations and conventions,
not formal certification standards. No physical AUX compliance or HomeBrew
interoperability has been verified by this project.

## Objective

Build our ESP32 as a Celestron-compatible Wi-Fi/AUX module, optionally extended.
HomeBrew is a reference and an optional interoperable family, not a dependency.
The captive portal and desktop tool must share one validated configuration model.
A browser portal must not replace compatible app-driven configuration endpoints.
Keep simulated motor replies explicitly identified until real AUX transport exists.

## References and findings

- [Wixely](https://github.com/Wixely/CelestronESPWifi): ESP8266 TCP 2000 to AUX
  transport; compiled-in Wi-Fi credentials; HTTP firmware updater. Minimal diode
  interface is a reference, not our validated ESP32 electrical design.
- [alex-vg](https://github.com/alex-vg/esp-skyportal-module): ESP32 AUX adapter;
  captured original-module TCP 3000 exchange uses get/set wlan.ssid,
  wlan.passkey, wlan.dhcp.enabled, wlan.static.ip/netmask/gateway and save.
  Its own client-mode configuration implementation is incomplete. Direct 5 V
  connections described there are not approved for our 3.3 V ESP32 design.
- [sophoclis-sw](https://github.com/sophoclis-sw/ESP32_Telescope_WiFi_Controller):
  TCP 4030 to 9600-baud RS-232 through a hand controller, not direct AUX.
  Set Time & Location in this architecture targets the hand controller.
- [HBG3](https://rtr.ca/hbg3/) and [history](https://rtr.ca/hbg3/history.html):
  GPS emulation, fakegps location, NTP and newer setGPS time/location operation.
  Exact setGPS argument order, epoch, reply and validity lifetime remain unverified.
  These extensions must not be assumed on stock Celestron adapters.
- [Author discussion](https://www.cloudynights.com/forums/topic/854327-homebrew-gen3-pcb-wifibtgpsmusbrelay/page/16/#comment-12773742):
  page includes historical GPS date/time validity improvements. Exact anchored
  comment was not independently resolved; do not infer current firmware behavior.
- [Flashing guide](https://rtr.ca/hbg3/flashing/): deployment reference only.
  Direct fetch timed out. No firmware downloaded or flashed during this work.

No HomeBrew firmware source was copied. Review licensing before incorporating
third-party code; documenting commands does not grant firmware redistribution rights.

## Experimental desktop implementation

`homebrew_settings.py` independently builds a validated fakegps command using
signed decimal latitude [-90,90] and longitude [-180,180], rounded to six decimals.
Precision formatting is not an accuracy claim. Preview does not access the network:

```sh
python -m homebrew_settings --latitude 33.0 --longitude -117.0
```

For a supervised HomeBrew bench test only, add `--host DEVICE_IP --apply-unverified`.
This locks both local endpoint ports, checks live version for HomeBrew identity
and help for fakegps support before writing. The assumed port-3000 prompt protocol
NEEDS HARDWARE TESTING. The tool prints the raw reply; it does not claim verified
acceptance or persistence. It does not send save, a time command or motor motion.
Do not run alongside another controlling application. This prototype is not yet
wired into the GUI/MCP. No live write was tested. A failed reply after a write
means outcome unknown; inspect the device before retrying.

## Firmware and desktop implementation path (pending)

1. Add standard-compatible management reads and staged writes to our firmware;
   validate SSID/password lengths and quoting, DHCP/static addresses and mode.
   Use the same backing configuration as the portal. Save atomically; respond
   before restart/reconnection. Never log passwords or return them in get all.
2. Advertise a versioned capability response under our own namespace. A simulator
   remains identified as such. Stock AUX traffic remains compatible; extensions
   are enabled only after identification and capability checks.
3. Add an explicitly namespaced time/location setter using UTC Unix seconds,
   signed latitude/longitude and separately reported validity/source/age. This
   is our proposed extension, NOT a verified Celestron or HomeBrew wire format.
   Obtain time from the PC; obtain location from user input or an explicit source,
   never infer geographic coordinates from timezone or IP address.
4. Optionally accept the documented fakegps syntax for compatibility. Do not
   guess setGPS time argument order on third-party devices. Prefer our documented
   extension on our firmware and add HomeBrew time support after capture/testing.
5. Expose supplied values through a GPS AUX emulator when enabled, avoiding a
   duplicate real GPS address. Supply valid date/time independently of position
   validity. Neither GPS emulation nor encoder reference writes establish sky
   alignment or autonomous tracking.
6. Desktop Diagnostics gets a capability-specific menu with Read, Preview, Apply,
   UTC/local display and readback comparison. Disable unsupported operations;
   retain a single connection owner. GUI integration remains pending.
7. Test portal/tool consistency, malformed inputs, credential redaction, failed
   save/reboot recovery, cold boot/stale time, GPS AUX replies and client behavior.
   Validate real electrical levels, BUSY arbitration and boot states separately.

## Release boundary

The desktop profile refresh can ship independently of these experimental firmware
extensions. Do not describe time/location or modern provisioning as hardware-tested.
