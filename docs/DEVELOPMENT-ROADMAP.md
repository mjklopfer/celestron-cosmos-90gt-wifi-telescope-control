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
5. Consider uptime-based reboot evidence as an additional warning. Do not rely on
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
