# ESP32 direct AUX adapter: resume here

Decision record: 2026-11-16. This is a distinct hardware/firmware subproject within
the COSMOS control project. Preserve the working legacy SkyQLink path while it is
developed. No real AUX adapter has been built or verified in this work session.

## Read these first

- [Architecture and capability plan](ARCHITECTURE-PLAN.md)
- [Breakout-board wiring diagram and electrical limits](ESP32-ACCESSORY-WIRING.md)
- [Development roadmap](DEVELOPMENT-ROADMAP.md)
- [Existing ESP32 simulator](../hardware/esp32-simulator/README.md)
- [Tracking producer/controller plan](TRACKING-DESIGN.md)

The simulator explicitly has no physical AUX UART/GPIO interface. Its documented
Wi-Fi/SkySafari success must not be reported as physical-bus compatibility. Review
its README for the historical flashed board/core versions and pending portal tests.
Do not flash over an existing board without identifying its current firmware and
preserving a backup; hardware identity and current state must be rechecked at resume.

## Agreed scope and decisions

- Assemble using development/breakout boards and wired interconnections; no custom
  PCB is required for the prototype. A small socketed-buffer/perfboard section is
  acceptable. Exact purchases, pin assignments and the final netlist are undecided.
- An ESP32 provides Wi-Fi plus direct Celestron AUX communication. Add optional
  GNSS/compass and battery-backed RTC capabilities independently.
- Two separate interface groups: telescope AUX UART plus bus arbitration on one
  side; a separate GPS UART plus sensor I2C on the other. These are logical groups,
  not a requirement to use opposite physical sides of a development board.
- Power concept: nominal telescope 12 V through a suitable 12-to-5 V converter;
  feed a development board that explicitly accepts 5 V at VIN/5V. ESP32 GPIO stays
  at 3.3 V. Verify port power capacity, converter margin and USB backfeed behavior.
  All modules share ground. Check actual connector orientation and cable continuity.
- Candidate GNSS board: SEQURE M10-25Q, with UART NMEA/UBX GPS and QMC5883L compass
  over I2C. Manufacturer specifies 5 V supply; signal voltages/pull-ups still need
  verification on the purchased revision. A compass alone is not a complete IMU;
  add tilt sensing if needed. Keep magnetic sensors away from steel/motor fields.
- Candidate RTC: DS3231, preferably a 3.3 V-compatible breakout. Store UTC, discipline
  from valid GPS time, retain time with a backup battery and report holdover age.
  Check oscillator-stop/validity status and battery charging circuitry. Do not
  present an old fix or invalid RTC as fresh GPS data.
- User's generic transistor "logic level converter" boards are candidates for
  open-drain I2C ONLY where voltage domains differ. Do not automatically place
  every sensor on a 5 V side because its board's power input is 5 V.
- AUX transmit: 74HCT125 or SN74AHCT125N at 5 V combines TTL-compatible 3.3 V input
  recognition, 5 V output and tri-state enable. No additional upstream level
  converter is needed for that direction. Prefer a proven AUX topology; the faster
  AHCT part is not a guarantee of compatibility with arbitrary wiring.
- AUX receive: separately provide 5 V-tolerant input and 3.3 V output, for example
  an appropriately wired SN74LVC125A powered at 3.3 V. A 5 V-powered HCT/AHCT output
  cannot connect directly to an ESP32 GPIO. HCT/AHCT and LVC parts are not identical.
- BUSY assertion/release and sensing are distinct from voltage translation. Ensure
  no contention, safe disabled outputs at boot/reset and no 5 V GPIO pull-up through
  output-enable wiring. Firmware must honor bus ownership and timing. A generic
  I2C translator does not replace the AUX interface.

## Accessory emulation decisions

AUX GPS/compass address 0xB0 is the initial candidate. Documented reads include
latitude, longitude, UTC date/year/time, validity, satellite/receiver status and
compass. The legacy 0xA0 compass reply is one of eight direction codes, not degrees
and not a writable compass setting. More precise heading/tilt belongs in our own
capability API unless a verified standard endpoint exists.

Optional RTC address 0xB2 is model-dependent and must be researched separately.
A physical DS3231 can supply GPS-style time responses without necessarily exposing
0xB2. Detect address conflicts and do not impersonate an existing accessory.

GPS, compass and time do not by themselves establish shared celestial alignment
or autonomous tracking. Observe what COSMOS/control software actually queries and
whether it caches values. No verified universal site-location write endpoint in
COSMOS motor controllers has been found. Missing replies do not prove absence of
undocumented commands; never brute-force opcodes on motor destinations.

## Desktop program changes: future TODO

- [ ] Implement a separate direct-adapter backend after physical AUX validation.
- [ ] Add Motor control connection selection. User suggested a checkbox; the
  proposed clearer UI is Auto-detect / Legacy SkyQLink / Direct Celestron Wi-Fi.
  Final presentation remains subject to review.
- [ ] Discover either adapter type, positively identify it and negotiate capabilities.
  The current discovery button's planned label is Discover SkyQLink / Celestron
  Modules; a label change is not implementation of the complete direct backend.
- [ ] Share supported motor operations and AUX diagnostics across backends. Expose
  ESP32 identity, firmware, uptime/reset reason, bus health, GPS validity and RTC
  source/age only after these endpoints exist and are verified.
- [ ] Keep WiFly command-mode provisioning, RN-171 recovery and WiFly clock/server
  controls exclusive to legacy SkyQLink. Give unavailable controls an explanation.
- [ ] Disable desktop Control Bridge in direct-adapter mode. It has NO role when
  the ESP32 already exposes the direct modern-compatible interface. Do not run its
  listeners or advertisements automatically. A mode change requires disconnecting
  and clearing active local references; do not auto-switch a live motor session.
- [ ] Share GUI/MCP service contracts without duplicate polling or control loops.
  Keep lightweight operation on Raspberry Pi. Associate calibration, defaults and
  session evidence with verified device/backend identity, not only an IP address.
- [ ] Preserve the legacy regression suite and document a tested mount/client matrix.

## Hardware/firmware TODO in order

1. Identify exact ESP32, GPS, RTC, converter and translator boards; obtain their
   schematics and confirm voltage levels, pull-ups, current budget and pin choices.
2. Finish a reviewed netlist and AUX connector drawing. Resolve 19200-baud framing:
   older research notes say 8N1 while newer HomeBrew notes report 8N2. Capture real
   COSMOS traffic and match the chosen circuit/firmware; do not guess RTS/CTS behavior.
3. Bench-test supply rails, startup/reset output states, receive levels, BUSY
   assertion/release and TX timing with no telescope attached. Use a scope/logic
   analyzer; record traces and component revisions.
4. Implement bounded framing, checksum validation, queues, deadlines, contention
   handling and echo handling. Release TX only after its last stop bit. Establish
   guard times and failure behavior from evidence, not network-loop timing.
5. Test read-only AUX on the real mount before any supervised movement. Then test
   Stop, disconnect/reconnect, partial frames, stalled clients and power loss.
6. Add GPS/compass/RTC emulation with independent enable controls and honest
   validity/source/age reporting; test consumers and persistence separately.
7. Enable desktop direct mode only after the above gates; repeat on Windows,
   macOS and Raspberry Pi, and record app/firmware/core/library versions.

## Reference findings and limits

The architecture/wiring documents link TI, Analog Devices and SEQURE datasheets,
Andre Paquette's reverse-engineered AUX observations, and HomeBrew author material.
An archived HomeBrew v3.8 source was reviewed for interface concepts, not imported.
The HBG3 mirror reports restrictions on redistribution of newer code: verify
permissions before reuse. Current HBG3 website/schematic fetches timed out during
this session, so a complete current-circuit review remains pending. Do not label
our proposal certified or universally compliant; establish interoperability with
specific tested hardware and clients.

## Related current application work (separate from ESP32)

The legacy app now has clock readback/UTC comparison and session-scoped uptime
warnings. A live read-only comparison showed about +1.6 seconds versus the PC at
one sample; no clock write was sent. PC-to-WiFly copying remains disabled pending
verification of the customized 2.40-CEL command. SkySafari documents time/location
transfer, but its destination and actual commands remain unknown here. A future
controlled capture should compare before/after reads. Existing bridge logs capture
valid AUX frames in both directions, not arbitrary non-AUX bytes. This experiment
must not be mistaken for implementation of the direct ESP32 adapter.

## Resume checklist

Read this file and its linked design documents; inspect git status and the current
hardware state. Confirm which boards were actually acquired. Complete electrical
review and bench tests before telescope attachment. Preserve legacy behavior, keep
new features visibly experimental until tested, and update this record with exact
results rather than treating planned items as completed.


### HomeBrew and alternative interfaces — research checkpoint

See [alternative interface findings and ESP32 implementation plan](HOMEBREW-INTERFACES.md).
Our ESP32 remains a Celestron-compatible module project with optional extensions.
HomeBrew location support is an unverified, opt-in developer prototype; GUI/MCP
integration and physical device validation remain pending.
