# Future connection backends

Recorded 2026-11-16 from the operator's development direction. This is planned
work, not a claim of current ESP32/ESP8266 or modern-module support.

Today the application's provisioning and control path targets the legacy
SkyQLink RN-171 / 2.40-CEL. Its Control Bridge presents selected modern
Celestron Wi-Fi discovery/management behavior to clients while forwarding AUX
to that legacy adapter.

Future ESP32/ESP8266-to-AUX work may provide another transport and additional
features. The application should eventually support both direct motor control
and bridge roles with legacy SkyQLink and a modern Celestron Wi-Fi-compatible
interface. The name is **Celestron**, not Skytron. Compatibility must be verified
for each actual implementation, rather than inferred from an advertised identity.

## Proposed separation

- Connection backend: connect/disconnect, identity, transport, packet exchange,
  telemetry freshness, recovery and capability reporting.
- Motion service: stop, position, bounded jog/target, limits, calibration and
  reference handling, independent of WiFly provisioning commands.
- Adapter settings: legacy WiFly commands only for positively identified legacy
  hardware; future firmware configuration uses a separate adapter implementation.
- Bridge role: client-facing discovery/relay configured separately from the
  telescope-facing connection backend.
- GUI and MCP: share service contracts and capabilities. A future **Connection
  type** selector chooses the backend; unsupported controls are disabled with
  a clear explanation, not silently routed through legacy commands.

Profiles should identify hardware/firmware/backend and protocol capabilities,
not only an IP address. Maintain migration/versioning for calibration and site
settings. Do not mix pulse calibration, encoder reference or device defaults
between backends without verification. Endpoint ownership remains exclusive.

## Implementation gates

1. Bring up ESP-to-AUX transport and establish voltage/electrical behavior,
   framing, command/response integrity, latency and disconnect/Stop behavior.
2. Define a capability/version handshake and test a backend service contract.
3. Verify motion and limits with supervised bounded tests; calibrate per device.
4. Add GUI connection selection and capability-dependent controls, then MCP
   reporting and bridge integration; retain legacy regression tests.
5. Publish a tested hardware/firmware/client matrix. Shared celestial alignment,
   autonomous tracking, time/site persistence and higher-rate motion remain
   separate capabilities to establish, not assumptions of the new transport.

## Deferred: ESP32 Wi-Fi, GPS, compass and RTC accessory

Requested 2026-11-16; viable as a research prototype, not implemented or verified
on COSMOS. Combine an AUX/Wi-Fi bridge with a GNSS receiver, magnetometer/IMU
and optional battery-backed RTC. Keep transport and emulated accessories separate
capabilities that can be enabled independently.

- Emulate documented GPS/compass replies at AUX address `0xB0`: location, UTC
  date/time, validity, satellite status and compass response. The documented
  `0xA0` compass read returns only eight direction codes, not a degree heading or
  a writable setting. Offer precise heading/tilt through a separate API rather
  than inventing a new payload for the legacy command.
- Validate magnetometer calibration, tilt compensation, mounting orientation,
  magnetic interference from motors/steel, and magnetic versus true north.
  Compass plus GPS supplies initial reference information, not proven celestial
  alignment or autonomous tracking.
- Use GPS UTC to discipline the RTC; report holdover age and validity honestly
  when GPS is unavailable. Never report a retained location as a fresh fix.
- Investigate optional `0xB2` RTC emulation separately: the known interface is
  model dependent. A physical RTC does not require presenting this AUX address
  if clients only consume GPS time replies.
- Verify AUX electrical levels, bus arbitration, timing and address conflicts
  before attachment. Do not impersonate an accessory already on the bus.
- Capture actual client requests to establish whether COSMOS, a hand controller,
  or control software requests and caches this information. Supplying replies
  does not establish a writable site endpoint in the motor controllers.
- Validate separately: packet fixtures, bench electrical tests, read-only client
  compatibility, restart/no-fix behavior, then supervised alignment tests.

Protocol basis: [NexStar AUX observations, GPS/compass chapter](https://paquettefamily.ca/nexstar/NexStar_AUX_Commands_10.pdf).
This is a reverse-engineered research document, not an official Celestron
compatibility guarantee.
