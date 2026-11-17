# Development roadmap

Updated 2026-11-16. Priority: stable cross-platform control, including modest
Raspberry Pi systems, before additional interfaces or unattended tracking.

## Current release scope

Two-axis controller settings with independent timestamped readouts, angle and
backlash inputs, signed backlash deltas with source-value recheck, and retained
applied-change history. Local references are connection-session values: clear on
disconnect or lost feedback, keep inactive history, reapply only explicitly.
Keyboard control has an OFF/ON switch and Windows Num Lock handling. Profiles
identify the adapter by its full MAC; network address changes need identity
verification. Diagnostics can abort while preserving results. User and MCP guides
document behavior and limits.

Automated tests exercise fake hardware; live readback and timed calibration jogs
have separate evidence. Native target streaming, actual controller setting writes,
and WiFly clock synchronization are not hardware-verified. These limits remain
visible in the documentation; successful UI tests must not erase them.

## Next: validation and usability

1. Review the updated GUI on Windows and repeat on the actual Raspberry Pi and
   macOS. Measure CPU use, memory, UI responsiveness and polling latency on the Pi.
2. Verify each setting write with recorded before/after values and explicit
   operator authorization. Verify persistence separately across a power cycle.
3. Provide user-confirmed rounding for angle inputs beyond five decimals;
   currently they reject, rather than silently changing a requested coordinate.
4. Add hardware-baseline restore only after a verified reset-state snapshot and
   device identity match. Never assume zero is a factory default.
5. Validate the session-scoped uptime discontinuity warning on hardware. Do not rely on
   it to keep old alignment valid; reconnect/feedback loss already clears local
   offsets. A dropped connection does not prove the mount rebooted.
6. Review small-screen settings-dialog scrolling and accessibility with real Pi
   desktop scaling. Keep per-axis operations visible and clearly separated.

## Deferred: optional companion HTTP API

The general application API is **not implemented**. The existing HTTP endpoint
accepts tracking targets only; MCP exposes backend operations through stdio.
The future companion API should reuse the same tested operation contracts and
structured outputs, not implement a second motor-control engine.

- Disabled by default; an explicit GUI enable/disable control, with `--noapi`
  overriding startup activation. No HTTP server or MCP dependency load in normal
  GUI operation unless explicitly requested.
- Bind to localhost and require per-session authentication. Document endpoints,
  errors, capability discovery, job status, cancellation and shutdown semantics.
- Preserve exclusive telescope ownership and explicit write/movement flags.
  Do not run duplicate polling loops for GUI, MCP and HTTP clients.
- Keep all network I/O off the GUI thread. Bound request bodies, worker counts,
  queued work, retained telemetry and logs. Give Stop priority.
- Distinguish accepted requests from verified outcomes; include connection state,
  telemetry age, device identity and experimental capability flags.
- Review deployment/authentication separately before supporting remote clients.

## Deferred: tracking and new transport backends

Follow the [tracking plan](TRACKING-DESIGN.md) and its
[engineering constraints log](engineering/2026-11-16-tracking-constraints.md).
MCP supervises; a deterministic local producer handles frequent targets.
Keep the latest target, reject stale input, cap telemetry refresh, and measure
real hardware rates/latency before increasing update rates. Predictive velocity,
arrival deadlines, Orbitron/WispDDE, TLE and launch CSV producers remain planned.

Follow the [backend architecture plan](ARCHITECTURE-PLAN.md) for future ESP32/
ESP8266 AUX and modern Celestron Wi-Fi support. Keep transport, motion service,
adapter settings and bridge roles separate. Expose only capabilities verified on
the selected backend. New transport support must not destabilize legacy control.

The architecture plan also records a deferred ESP32 GPS/compass/RTC accessory
emulator alongside the Wi-Fi bridge. Client consumption of these replies and
COSMOS compatibility require verification; no shared alignment is promised.

## Implemented baseline: uptime evidence for potentially stale references

Implemented 2026-11-16: the GUI retains session-scoped samples by adapter MAC from
diagnostics and time-menu reads. Falling uptime or a changed restart count warns
and clears active local offsets. Real restart/rollover validation remains pending.
Disconnect/lost-feedback handling also clears active local offsets.

- Compare samples for the same verified adapter identity, recording host monotonic
  elapsed time and sample freshness. Collect at safe diagnostic/connect boundaries;
  do not interrupt motor traffic to enter WiFly command mode for periodic polling.
- A decrease in uptime is evidence of a possible adapter restart or counter
  discontinuity, not proof that the motor controllers lost power. Correlate restart
  counters and fresh encoder readings; do not infer a reset from connection loss.
- The Microchip manual documents seconds for UpTime but does not establish its
  counter width or rollover behavior for customized firmware `2.40-CEL`. Do not
  assume a 32-bit millisecond counter or a 49.7-day wrap. Only classify rollover
  when a verified modulus and elapsed-time-consistent transition support it;
  otherwise report uncertainty. Long sampling gaps also limit classification.
- Calendar RTC time may change during synchronization. It is not the reset detector.
  The manual describes RAW as a 64-bit counter at 32,768 Hz; its full-width wrap
  is approximately 17.8 million years, but that does not establish UpTime's width
  or this customized firmware's behavior.
- Warn: "Adapter uptime restarted or changed unexpectedly. Previous local
  references may be stale; establish a new reference before reapplying offsets."
  Clear active local references conservatively on detected discontinuity; retain
  history as inactive and never automatically restore it or write motor settings.
- Test normal progression, restart, verified rollover, missing samples, clock
  sync, host restart and changed device identity before enabling this feature.

Reference: [Microchip WiFly manual, section 3.11](https://ww1.microchip.com/downloads/en/DeviceDoc/50002230B.pdf).
This manual is newer than the installed customized firmware; verify behavior
on hardware before claiming reliable reboot detection.

PC-to-WiFly clock copying remains unimplemented until the 2.40-CEL write command
is verified. Investigate SkySafari traffic; its documented time/site transfer
does not identify which device stores those values.

The future direct ESP32/Celestron Wi-Fi mode is separate from legacy SkyQLink.
Control Bridge is disabled in that mode; add the selector only after physical
AUX validation, not merely simulator success. See the architecture acceptance gates.

ESP32 work resume point: [decisions, wiring references and ordered TODO checklist](ESP32-RESUME.md).


## 2026-11-16 GUI release

Implemented for review: explicit action-oriented instructions and named copy
sources; larger tabs/section headings; selected-page height; shaded motor connection
status; direct/ad hoc bridge requirements and topology guidance; profile filename
and details dialog; JSON-defined optional keymap with disable-on-missing behavior;
rate table moved to a conditional dialog with CSV and Excel clipboard formats.
The current user's existing profile received its previous letter mapping explicitly;
other profiles receive no automatic fallback. Windows automated and GUI review
results are recorded in VALIDATION.md. Hardware ESP32, direct mode, PC-clock writing
and complete SkySafari transport capture remain deferred as documented above.

Adapter-generation terminology: **Celestron Version 1 Wi-Fi — SkyQLink RN-171** uses `SkyQLink-xx`; **Version 2 and later Celestron Wi-Fi** use `Celestron-xxxx`. The current provisioning workflow and LEFT/RIGHT switch instructions apply only to the Version 1 RN-171 / 2.40-CEL. Future adapter support must provide model-specific connection and provisioning instructions; a network name alone does not verify device capabilities. Newer-adapter provisioning is not implemented by this wording change.
