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

Resolved by the macOS appearance update (`775308e`, documented in `8262108`): reported formatting changes after the UI refresh. Check Aqua/custom-tab mixing, font metrics, page height and zoom with the user’s macOS/Tk version; preserve native rendering where needed. The user confirmed the corrected Mac appearance; see MACOS-APPEARANCE.md.

## Pi/KStars closeout — 2026-11-16

Completed: both-axis manual movement, Stop, fresh encoder readback, and fresh Pi-session connection after telescope power cycling. See the [versioned validation record](engineering/2026-11-16-pi-kstars-validation.md) and [manual operating note](KSTARS-BRIDGE-NOTE.md). Remaining: real-star manual alignment/GoTo accuracy, sustained tracking, intermittent adapter reply loss, coordinated external-client reset handling, and separate CPWI verification. No camera-based alignment work is planned for this deployment.


## Bridge mediation and AUX observations — 2026-11-17

Implemented: optional bounded local jogging using the bridge worker, external-command
priority, and raw-hex plus conservative command interpretation. Captured findings,
unknown commands, and remaining live-validation tasks are recorded in the
[engineering note](engineering/2026-11-17-skysafari-aux-observations.md).
No new controls for unknown commands, no claim of shared alignment, and no new
verified time/location-write endpoint. Live SkySafari coexistence and new UI
validation on Pi/macOS remain pending.


## Low-latency relay and future motion reconstruction — 2026-11-18

Implemented: TCP_NODELAY, forwarding before packet observation, and a separate
queued event writer/decoder/UI publisher. Tested with a deliberately stalled log
writer while commands and replies continue on loopback. No bridge inactivity
expiry; direct motor idle release and local-jog safety limits remain.

Remaining: measure receive-to-send latency and end-to-end motor response latency
under load; consider explicit high-resolution receive/send stamps plus per-session
sequence IDs. Existing UTC/monotonic stamps denote queued observations, not hardware
execution. Preserve sample timing rather than using disk-write time.

Plan an offline JSONL-to-CSV motion-track exporter with separate commanded and
measured encoder tracks, 24-bit wrap handling, reconnect/reset segmentation, gap
and dropped-event warnings, and optional plots. Require alignment/site/time metadata
before converting raw encoder angles to sky coordinates. Captured manual rocket
tracking could become an edited reference trajectory, but a different launch needs
its own trajectory and time origin; do not blindly replay packets or assume it
follows the same path. Validate rates, acceleration, clearance and stale samples.

Optional read-only heartbeat is implemented, OFF by default, with GUI/CLI switches
and configurable intervals. It shares the position-read scheduler, suspends when
normal traffic resumes, and avoids injecting duplicate outstanding queries. The
former fixed no-client polling and three-miss shutdown are removed. A heartbeat is
not a substitute for diagnosing missing replies or app-initiated disconnects.

Position recording is implemented independently of local jogging (0.2–300s,
default 1s, OFF initially). Keep-alive is separately selectable but shares the scheduler (1–300s, default 5s,
OFF initially). Live extra-query compatibility and subsecond load validation remain
pending; trajectory plotting/replay and high-resolution timing instrumentation
remain future work.


Implemented subsequently: independent CSV/JSON export of packets, measured positions
or a combined timeline, via GUI and `python -m export_recording`. Original timestamps,
raw data and gap/status notices are retained; active-file snapshots are supported.
Remaining analysis work: plotting, angle unwrap/reset segmentation, aligned sky
coordinate transformation and validated trajectory playback. None is implied by
exporting the recorded data.

### Unified bridge reads (2026-11-18)

Implemented one nonblocking scheduler for optional keep-alive, configurable motor
position sampling, and required local-jog feedback. Removed fixed no-client 1 Hz
polling and its three-miss shutdown. Moved settings to Control Bridge with explicit
seconds-per-sample examples and the local-jog safety override. Pending external
position requests suppress injected duplicates; normal external traffic is never
rate-limited. Live SkySafari stability/lag comparison remains pending. AUX has no
transaction IDs: identical replies cannot prove which overlapping request caused
them. Do not present observed command/reply timings as isolated bridge latency.


### Direct-session ownership and local/remote bridge guidance (2026-11-18)

Expose the existing direct motor idle encoder polling as optional keep-alive,
default ON at one second, configurable 1–300 seconds. It is not a second polling
loop and never renews the movement-idle timer. Default idle release remains 30
seconds; longer options and Never are available with an adapter-ownership warning.
Disable these settings during active direct sessions and all bridge operation,
including local bridge jogging; preserve selections for the next direct session.
Required movement feedback and Stop paths remain independent.

Bridge setup now distinguishes a control application on the same computer from
another device on the shared LAN. Point both to this computer's displayed bridge
address, not the telescope; localhost is local-only and requires an explicit
loopback bind. The bridge relays telescope traffic, not general LAN routing.

Overnight capture review: the stationary recording ran approximately 4h25m with
27,475 encoder samples but 602 missing-reply warnings, then a remote TCP reset.
There was no SkySafari client during that capture. The longest inter-reading gap
was about 60 seconds; some gaps also affected all emitted events. Investigate
host scheduling/blocking alongside Wi-Fi/adapter behavior. This is not a clean
endurance pass or evidence that keep-alive fixes the underlying cause.
