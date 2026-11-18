# COSMOS ESP32 sham telescope bench firmware

This firmware runs entirely on the ESP32. It does not connect to the original
telescope, drive GPIO motor outputs, or implement a physical AUX interface.
The virtual AZ/ALT motor controllers maintain in-memory encoder positions.

The first build was flashed on 2026-11-15 to an ESP32D0WDQ6 revision 1 with 4 MB
flash. Its prior flash image was backed up locally under
`backups/esp32-before-connectivity-test/`; that backup is private and unrelated
to the telescope module's firmware.

## Configure Wi-Fi

1. On first boot, join `Celestron-XXXXXX` (this board's name), password
   `cosmossetup`. Other boards use their own MAC suffix.
2. Open `http://192.168.4.1/` if the setup page does not appear automatically.
3. Choose **Join another Wi-Fi network**, then **Scan nearby Wi-Fi networks**.
   The scan lists SSIDs, signal levels and detected security. Select a supported
   network and enter its password; security is negotiated automatically. A hidden
   SSID can be entered manually. Save. The firmware writes a
   versioned configuration blob into ESP32 Preferences/NVS and reboots.
   This is flash-backed nonvolatile storage, not a physical EEPROM chip.
4. Rejoin the router network on the phone. The board automatically reconnects
   using saved settings. Its new address appears on USB serial and in the router
   client list under hostname `Celestron-XXXXXX`.
5. Open the new address in a browser to see simulated positions and status.

Alternatively, select **Keep a local hotspot for the phone**, then save. On
restart, join `Celestron-XXXXXX` with the same hotspot password and open
`http://1.2.3.4/`. The simulated telescope listens at `1.2.3.4:2000`; choose
Celestron Wi-Fi / Direct Connect in the app. This is a SoftAP hotspot, rather
than legacy IBSS ad hoc. Local hotspot mode does not require a router.

The mode is saved with the credentials. Initial setup and failed-router fallback
use `192.168.4.1`; explicitly saved local-hotspot mode uses `1.2.3.4`. The hotspot
sets its own IP, gateway and /24 subnet explicitly and starts its web server
after the AP interface is active. The original v0.1 build intermittently failed
to lease an address to the phone; its page later became reachable. These startup
changes in v0.2.2 require phone retesting before claiming that symptom resolved.

The original bench build used ESP32 Arduino core 1.0.1 and showed intermittent
network errors. Version 0.2.2 builds against core 2.0.17; the local validation
record identifies the flashed source and binary hashes. The portal negotiates supported
open/WPA/WPA2 Personal security automatically. Enterprise authentication is not
implemented.

If association fails for 30 seconds, the board stores a failure reason and
reboots once into the setup hotspot at 192.168.4.1. The portal explicitly shows
that the previous configuration could not connect and asks the user to try again.
It retains the SSID, stays in recovery across further resets, and does not retry
and reboot forever. Saving corrected settings clears recovery and tries again.
If the failure marker cannot be saved, the portal opens without another reboot.
Stored credentials remain intact until replaced by a new saved configuration. To reopen setup while running, hold BOOT for four
seconds and release (do not hold BOOT while powering up). USB commands at 115200:
`STATUS`, `SETUP`, `REBOOT`, `RESET_WIFI`. Reset clears only this application's
saved Wi-Fi configuration. Router passwords are not printed or placed in source.
The setup hotspot password is intentionally a documented bench credential.

## SkySafari / SkyPortal test

Turn OFF the computer's existing Bridge mode before the app test so its discovery
advertisements do not compete with this simulator. Keep the real telescope
disconnected from the app. The ESP32 itself has no upstream telescope connection.

For infrastructure mode, use Celestron Wi-Fi / Access Point mode while the phone is on the same router
network. Where the app exposes an address, enter the ESP32's infrastructure IP,
port 2000. UDP discovery is also advertised on port 55555; limited read-only
management runs on TCP 3000. DHCP supplies the infrastructure IP; the advertised
host name and hotspot SSID share the Celestron MAC-suffix naming. Discovery
packets advertise the module's MAC and AMW007-style simulator identity.
Router client isolation or separate guest networks
can prevent discovery/connection. A SkySafari phone session was verified; exact edition/version was not recorded.
Compatibility with every app/version is not established.

Virtual controllers answer the motor startup commands observed in our working
Python bridge capture: firmware/model, position, status, movement, Stop and GoTo.
They return synthetic version 5.24 and model bytes for compatibility with the
COSMOS startup sequence. This is not a genuine motor controller or an exact
timing/kinematics model. Unsupported accessory queries receive no invented reply.
GPS, StarSense, firmware updating, real sky alignment, and real motor operation
are not implemented. App alignment behavior has not yet been validated.

Manual rate commands advance simulated encoder values; Stop holds them. GoTo
targets advance at a simulated maximum of 3 degrees per second. Loss of the
client or 15 seconds without client data stops virtual motion. Encoder values
reset when the ESP32 restarts; Wi-Fi settings persist.

## Source and verification

- `simulator/main.cpp`: network provisioning, persistence, discovery, TCP and HTTP.
- `simulator/aux_simulator.h`: portable C++ virtual motor protocol and positions.
- `test_aux_simulator.cpp`: desktop checks for rates, GoTo, Stop and reply checksums.
- `monitor.py`: USB status monitor without deliberate reset-line toggles.
- `verify_portal.py`: live portal/scan checks and optional hotspot save/reboot.
- `verify_simulator.py`: HTTP/TCP smoke test with a strict simulator
  identity check before sending any virtual motion commands.

Run from the repository root:

```sh
c++ -std=c++11 -Wall -Wextra -Werror hardware/esp32-simulator/test_aux_simulator.cpp -o /tmp/test-aux-simulator
/tmp/test-aux-simulator
python hardware/esp32-simulator/verify_simulator.py ESP32_IP
python hardware/esp32-simulator/monitor.py --port YOUR_SERIAL_PORT
```

The monitor requires pyserial. Serial ports are platform-specific; on this bench
`/dev/cu.SLAB_USBtoUART` worked, while the alternate USB serial driver name reported
busy. Close the monitor before flashing. Build tools and binary evidence are local
and excluded from Git. The initial build used Arduino CLI 1.6.0 and 64-bit Arduino
ctags 5.8-arduino12; the older bundled tools could not run on the current host.

For another system, install Arduino CLI and the chosen ESP32 core and build:

```sh
arduino-cli core update-index --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core install esp32:esp32@2.0.17 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli compile --fqbn esp32:esp32:esp32 hardware/esp32-simulator/simulator
arduino-cli upload --fqbn esp32:esp32:esp32 --port YOUR_SERIAL_PORT hardware/esp32-simulator/simulator
```

Later core versions may require API adjustments and revalidation. The simulator
logic is separate so an ESP8266 port can replace networking/storage drivers and
use bounded buffers with its smaller RAM. ESP32 Preferences is not an ESP8266 API.

## Next hardware direction

A single ESP32 (or a suitably engineered ESP8266 port) connected to the mount's
AUX bus can replace the two-radio Wi-Fi proxy arrangement. That requires an AUX
transport with proper electrical levels, shared-bus arbitration/BUSY handling,
boot-safe pins, and controlled transmit enables. It is not an RS-232 connection
and a generic voltage shifter alone is not a complete design. The current board
is USB-connected only; no AUX wiring has been selected or tested.

The two-ESP arrangement remains an alternative when retaining the original
telescope Wi-Fi as the transport: unit A always faces the telescope, unit B either
hosts the phone hotspot or joins the router network, with a proposed wired link.

References:
- https://github.com/CalPlug/ESP8266_Load_Controller
- https://github.com/CalPlug/ESP32WiFiSetup
- https://arduino-esp8266.readthedocs.io/en/latest/reference.html#serial
- https://docs.espressif.com/projects/arduino-esp32/en/latest/api/preferences.html
- https://www.rtr.ca/hbg3/parts.html

No third-party HomeBrew firmware source was copied into this simulator.

## Observed SkySafari success — 2026-11-15

The user confirmed that firmware 0.2.2 connected to SkySafari and displayed
simulated telescope movement successfully over infrastructure Wi-Fi. USB logs
showed a connected client, 356 AUX packets, changing virtual AZ/ALT values, and
simulation stopping on disconnect. Exact app edition/version was not recorded.
This validates the tested simulator session, not physical AUX operation.


## Modern-module Wi-Fi configuration (experimental, 2026-11-18)

The Celestron module profile now has SSID, masked password, network security,
Read module Wi-Fi settings, and Apply & Save Router Wi-Fi Settings controls.
Disconnect Motor control/Control Bridge and finish other operations first.
Read obtains the SSID, not the password. Enter a password before Apply; an
explicit Open selection requires an empty password. Personal encryption is
negotiated automatically using a method supported by both device and router.
This is not a claim of WPA3-only, WEP or Enterprise support. Quotes, backslashes
and control characters are currently rejected rather than guessing escaping rules.

Our ESP32 source v0.2.3 implements the management configuration capability and
uses the same saved record as the captive portal. Some emulated modules offer
captive Wi-Fi setup pages as an alternative; the project includes our ESP32
portal code. Existing v0.2.2 firmware does not support desktop provisioning:
use its portal until the new firmware has been compiled, tested and uploaded.

Desktop writes stage SSID/passkey and enable DHCP, check staged SSID readback,
then save. On our ESP32, station mode is selected in software and saving schedules
a restart. Commercial AMW007/ZentriOS writes require the experimental opt-in;
module identity and expected acknowledgments must match. Its physical switch
may still need to be set to WLAN. A save acknowledgment does not verify a network
join. Reconnect the computer to the router network and rediscover the module.
Do not automatically retry after a timeout; saved state may be uncertain.

The official commercial procedure starts in Direct Connect, joins Celestron-###,
uses SkyPortal > Connect > Settings > Communication > Configure Access Point,
enters SSID/password, sends configuration and selects Use Access Point. Set the
module switch to WLAN, then join that router network on the controlling device.
The switch chooses network mode, not encryption.
Reference: https://celestron-site-support-files.s3.amazonaws.com/support_files/93973_Celestron%20SkyPortal%20WiFi%20Accessory_Manual_5LANG_Web.pdf

Validation: eight mocked backend tests and two focused GUI tests pass; lint passes.
ESP32 compilation, upload, actual configuration/network recovery and commercial
module interoperability remain unverified. No credentials or live configuration
were sent during implementation. The running desktop app must be relaunched to
show these additions. This section supersedes earlier portal-only statements.
