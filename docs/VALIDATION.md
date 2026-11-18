# Validation and remaining checks

## 2026-11-16 UI clarity and profile release

- Windows full regression: **142 tests passed**. The first run found an obsolete label assertion; the assertion was corrected to check explicit address/blank-field guidance and the full suite passed.
- Subsequent bridge wording/layout changes were checked with the focused bridge/release-guidance tests. Ruff, whitespace checks, GUI smoke tests and wheel/source builds passed.
- Reviewed Windows tabs, status readouts, profile filename and connection options. GUI starts disconnected and does not issue hardware commands during smoke tests.
- README/user guide now distinguish current Windows checks from earlier macOS/Pi validation. This batch does not claim a new live telescope, Excel-paste, macOS or Pi hardware test.
- Future ESP32 transport, PC-to-WiFly clock writes, general HTTP companion API and full-pass native tracking remain deferred/experimental as recorded in the roadmap.
- Pi deployment and KStars/INDI manual movement checks are complete; see the Pi/KStars closeout record below for scope and remaining limits.


## 2026-11-16 GUI, calibration and optional MCP audit

- Windows local suite: **129 tests passed**, including separate axis readouts,
  retained local-reference history, numeric input validation, stale-backlash
  rejection, adapter-MAC matching, keyboard/Num Lock and zoom behavior.
- Ruff and whitespace checks passed. Wheel/source package and Windows PyInstaller
  build completed; the packaged GUI smoke test exited successfully.
- MCP stdio initialization, listing **31 tools**, and structured status read
  passed without connecting to the telescope. Backlash-delta control is exposed.
- Operator confirmed the keyboard shortcuts work after the Windows modifier fix.
  The checkbox was subsequently replaced by an OFF/ON rocker using the same handler.
- Earlier live evidence: 36 supervised timed calibration pulses completed with
  encoder/Stop checks; a 180-second stationary feedback run tolerated delayed
  replies. This does not establish the underlying WiFly delay root cause.
- Native target commissioning could not obtain initial fresh feedback: no target
  motion was sent, and the proposed 5-degree tracking sweep was not performed.
- Controller encoder/backlash writes, WiFly time synchronization, full-pass tracking,
  new GUI behavior on Pi/macOS and long-duration reliability remain unverified.
  General companion HTTP API, confirmed rounding, reset-state restore and new
  modern/ESP AUX backends are deferred in the development roadmap.

The notes below describe earlier baselines, not the scope of this latest audit.

Release preparation: 2026-11-15.

## Desktop application

- Clean curated export: 84 tests passed, including mocked motor operations,
  provisioning redaction, protocol parsing, bridge sessions and delayed/missing replies.
- Three focused GUI checks passed after the final guidance adjustment: required
  shared-network IP, infrastructure/direct-address warning and discovery preserving
  direct mode. The complete suite now contains 85 tests.
- Ruff checks, Tk window smoke test, source distribution and portable Python wheel
  build passed locally. Current GitHub workflow runs the complete checkout tests
  and package build on Windows/Linux with Python 3.10 and 3.14.
- Real COSMOS 90GT / RN-171 operations and SkySafari bridge sessions were observed
  on macOS. Both a shared infrastructure LAN and Wi-Fi-to-telescope plus Ethernet-
  to-phone-LAN topology were verified. Exact phone app editions/versions were not
  recorded. An additional SkySafari application was reported working.
- Real hardware showed occasional idle encoder delays. The then-current three-miss
  policy was covered by loopback tests; it was subsequently removed by the unified
  scheduler on November 18. See the latest validation section below.
- Windows/Linux CI validates software without a real telescope. Hardware tests
  and a native Windows application build remain separate follow-up work.

## Embedded simulator

ESP32 simulator firmware 0.2.2 was flashed and tested separately. It successfully
connected to SkySafari and displayed virtual telescope movement. Site scanning,
network mode persistence, infrastructure joining, reply checksums, count changes,
Stop and deliberate failed-configuration recovery were checked. It has no physical
AUX transport. The published tree contains source, not private flash/NVS backups.

## Publication audit

The release excludes device-profile snapshots, local SSIDs/passwords, user account
paths, raw hardware logs, neighbor lists, flash/NVS dumps, toolchain binaries,
virtual environments, legacy experiment scripts and private handoff archives.
Runtime addresses/interfaces are discovered or entered. Tests use synthetic device
identities and network fixtures. Fixed 1.2.3.4 is the adapter protocol's normal direct
address; cosmossetup is an explicitly documented simulator-only setup password.


## 2026-11-16 clock readback and uptime-warning update

- 136 unit/GUI tests passed, including clock UTC comparison, missing/unset date,
  day-scale differences, counter discontinuities, identity separation, and a
  read-only GUI request that bypasses write confirmation and editable settings.
- Ruff and diff whitespace checks passed; Tk smoke test passed; wheel and sdist
  built with `python -m build --no-isolation`.
- Live read-only time operation completed with command-mode exit confirmed,
  `applied=False`, `sync_requested=False`, `movement_sent=False`. At the sample,
  reported RTC was approximately 1.6 seconds ahead of the local PC clock in UTC.
- Uptime warning logic is automated-test verified; no physical reset or long-term
  counter rollover was performed. PC-to-WiFly clock copying remains disabled.
- ESP32 accessory wiring is a design concept, not an electrically tested build.

## Historical macOS layout report after UI refresh (resolved below)

The user reports that the program runs on macOS but formatting differs. The latest visual layout has not been verified on macOS. Custom tab styling copies a clam tab element into the native theme; larger fonts/padding and selected-page height are additional possible contributors. The cause is unconfirmed pending a screenshot and macOS/Tk version. Track this as an open visual-compatibility issue, not a confirmed functional failure or a verified fix.

## macOS conditional appearance update — November 16, 2026

Application change: `775308e`. Native Aqua tab styling/centering, compact Mac
connection and Diagnostics toolbars, theme-aware explanatory text, readable
bridge-status text and font-based zoomed diagnostic row height. Windows/Linux
retain their existing layout and tab color choices. See
[Mac appearance notes](MACOS-APPEARANCE.md) for implementation scope.

On local macOS / Python 3.14, GUI startup and lint passed. The full offline
suite ran 147 tests successfully (144 passed, 3 skipped); the new Aqua layout
regression also passed separately. After integrating the concurrent upstream
test fixes, seven focused zoom/layout/export tests passed. Automated screenshot
access timed out, but the user visually reviewed the relaunched app and confirmed
that it looked much better. Windows/Linux were not visually retested in this
session, and no new telescope hardware/endurance validation is claimed.

## Pi/KStars closeout — 2026-11-16

The earlier pending Pi integration status is superseded by the [versioned hardware validation record](engineering/2026-11-16-pi-kstars-validation.md): both-axis manual motion, Stop, fresh encoder feedback and fresh-session reconnection verified. Real-star alignment, GoTo accuracy and sustained tracking remain unverified.


## Bridge mediation and trace decoder — 2026-11-17

Windows / Python 3.14: broader offline suite ran 112 tests (111 passed, one skipped).
Focused bridge/decoder/withdrawn-GUI suite subsequently passed 25 tests, including
external-command priority, fragmented frames across a toggle, bounded jogging,
stale-feedback lockout, GUI feedback gates and raw-hex/decoded logging. Initial
parallel targeted tests collided on the simulated endpoint lease; rerun serially
passed. Ruff and diff whitespace checks passed. Wheel and source archive built
successfully with the decoder included. The full focus-taking GUI suite was not
rerun during the user's ongoing capture.

Live evidence covers external SkySafari traffic on the previously running build,
not the new local-jog mediation. Live joint jogging, new Pi/macOS UI review and
alignment preservation remain unverified. See the
[observation record](engineering/2026-11-17-skysafari-aux-observations.md).


## Bridge inactivity removal — 2026-11-18

All 18 loopback bridge tests passed, including a 16-second quiet interval for
both control and management sockets, subsequent successful requests, and no
inactivity-triggered Stop. Ruff and whitespace checks passed. Direct Motor control
idle release was not modified. Live app restart remains pending; the existing
process retains its old timeout behavior until restarted.


## Queued bridge telemetry and restart — 2026-11-18

Bridge/decoder suite passed 22 tests; six additional targeted tests passed (the
blocked-writer relay regression plus five withdrawn-GUI tests). Ruff passed. The
blocked writer test held packet logging while two motor position requests and
replies completed through loopback, proving disk work no longer gates forwarding.
TCP_NODELAY was checked on upstream and accepted control sockets. No numerical
hardware-latency improvement or high-speed tracking accuracy is claimed.

Windows GUI was closed normally and relaunched. Updated bridge started at
08:20:41 UTC; both axes answered startup queries. Old raw logs/report were preserved
locally with hashes. New SkySafari endurance and joint local-jog tests remain
pending; no agent-commanded jog was used for this restart.


## Independent position recording and heartbeat — 2026-11-18

28 bridge/GUI tests passed before subsecond range expansion. Nine focused tests
then passed covering background-read scheduling, interval validation, pending-query
limits, fresh-sample reuse, GUI regressions and externally changed encoder positions
without issuing jog commands. Ruff and whitespace checks passed. Subsecond physical
load/endurance and simultaneous third-party AUX control remain unverified.


Recording export: ten focused exporter/background-read/GUI tests passed. Tests cover
selection separation, timestamps, raw data, CSV quoting, source preservation,
partial active-file tails and rejected corrupt complete records. The preserved live
capture exported to CSV positions and combined JSON without warnings. These are
raw-motion/command records, not verified sky tracks or replayable trajectories.


## Unified bridge polling and time-range export — 2026-11-18

Full Windows offline suite: 173 tests run, 172 passed, one Aqua-specific macOS
layout test skipped; no failures/errors (165.609 seconds). Focused bridge,
export and GUI regression suite also passed. Ruff and git whitespace checks pass.
Wheel and source distribution build successfully using Python 3.14. No new
third-party runtime dependency is required for recording/export.

Coverage includes one scheduler with/without a control client; optional reads OFF
by default; reuse of incoming samples and pending external requests; no injected
reads during partial client frames; missing-sample reporting without idle shutdown;
local-jog feedback loss Stop; normal command arbitration; interval validation and
Control Bridge GUI placement. Export tests cover session/range selection, explicit
Unix/local timestamp fields, source hashes, raw data, quoting and active-file tails.

The running older GUI was deliberately left untouched during the user's SkySafari
test. That capture recorded client TCP EOF after about 122 seconds and 40 seconds,
with the bridge staying alive. The user reported disconnecting when switching away
from the phone app. This is observational evidence, not a proven iOS/SkySafari root
cause or proof that the new scheduler fixes disconnects or lag. Local-jog feedback
was enabled in that capture and added queries at 0.4 seconds. The new scheduler
reduces duplicate reads but its live timing/stability remains to be verified.

Pending: restart for visual user review, live foreground/background comparisons,
measured end-to-end latency, sustained subsecond sampling, and simultaneous external
AUX-controller tests. No physical motion was commanded by the agent in this change.


## Restart, documentation audit and live read-only check — 2026-11-18

The previous GUI closed normally and the committed unified-scheduler version
reopened successfully on Windows. Control Bridge started at 08:56:09 UTC; both
motor controllers returned position and firmware 5.24. With both optional controls
OFF and local jogging OFF, no recurring queries were logged for approximately
38 seconds after readiness. Enabling five-second keep-alive produced three query
pairs with measured spacings approximately 5.07 seconds. Both axes replied.

Enabling one-second recording while keeping heartbeat ON produced 82 readings per
axis over a 91.2-second observation. No extra keep-alive query pairs were injected
during recording, and no bridge errors or missing-sample messages occurred. Actual
sample intervals exceeded one second slightly, as documented for best-effort timing.
This was a stationary, no-control-client test, not a SkySafari endurance benchmark.
Local jogging stayed OFF; no movement commands were used for the check.

The actual GUI showed the controls and instructions on Control Bridge. Its export
dialog populated the available date/time bounds with UTC offsets. GUI CSV export
saved 133 records plus a metadata row; independent parsing verified packet,
position and status records and the timestamp_local_iso8601 header/offset values.
Private captures and the exported CSV remain local, outside the repository.

Corrected stale current-behavior text in README, USER-GUIDE, BRIDGE-MODE and the
engineering history: removed claims of a 15-second bridge idle cutoff, automatic
three-missed-polls shutdown, blanket Motor control lockout and no injected reads
with a connected client. Historical observations remain explicitly dated; the
separate ESP32 simulator's documented timeout remains its own behavior.

The same application code passed the full 173-test suite (172 pass, one macOS-only
skip) immediately before this documentation audit. Lint and whitespace checks
passed again. Package builds include the updated documentation. Left the GUI and
bridge running with one-second recording ON, heartbeat OFF and local jogging OFF.
Still pending: SkySafari foreground/background comparison, measured relay latency,
long-duration stability, subsecond hardware load and independent external AUX
motion capture. These checks do not establish all-platform hardware compatibility.


## Direct keep-alive, automatic connection release and bridge instructions — November 18

Direct Motor control now exposes existing idle encoder polling as Keep connection
alive (default ON, one second; 1–300 seconds). Idle release defaults to 30 seconds
and additionally offers 1/2/5 minutes and Never. Keep-alive never renews the idle
release timer. Controls are disabled during direct sessions and all bridge
operation, including bridge jogging; selections are preserved. The warning
explains adapter ownership without asserting a fixed 30-second firmware lockup.

Turning idle reads OFF or making them slow exposed a cached-position prerequisite
that would reject otherwise valid jogs. The final worker now obtains both encoders
before issuing movement and refuses motion if either reply is absent. Movement
feedback-loss and Stop safeguards remain. No physical movement was performed for
this change; motion tests use the in-memory adapter.

Full regression before this final pre-movement refinement: 177 tests, 176 passed,
one macOS-only skip, no failures/errors. After refinement: all 23 motor tests
passed, including stale-read refresh of both axes before motion and missing-other-
axis rejection with no movement command. Seven bridge GUI tests also passed,
including disabled controls for both bridge jogging states and retained selections.
Ruff/whitespace checks passed and wheel/source distributions rebuilt successfully.

The updated Windows GUI was relaunched and visually reviewed. It is left open,
direct motors disconnected and bridge OFF, for user review. The local bridge
jogging experimental label was removed; specific subsecond/tracking limitations
remain documented. Instructions now cover control software on this computer or
another device on the shared LAN, with correct local-only localhost semantics.
Long-session direct keep-alive and on-hardware pre-movement behavior remain to be
verified. Automated passes do not establish transport reliability or fix the
previously recorded overnight missing replies/remote reset.


## Direct connection section wording and disabled appearance — November 18

Renamed the section Direct motor connection settings, with Applied on next
connection as a separate subtitle and explicit Connect Motors instructions.
The frame, heading, labels, explanation and inputs now disable/dim together during
bridge operation or an active direct connection. When editable, the interval stays
editable even if keep-alive is unchecked, allowing presetting; it is only used when
keep-alive is enabled. Seven bridge GUI regression tests passed, including full
section disable/restore and selection preservation. Lint and whitespace pass.
The already-running app is not interrupted; this UI adjustment requires a restart.


## Direct Never / two-second keep-alive observation — November 18

Reviewed the direct session from 07:53:50 to 10:17:08 PST (about 2h23m). Policy was
Never idle release with keep-alive ON at two seconds. It logged 8,085 position
readings, 85 per-request timeouts and 57 feedback-retry episodes; all 57 had a
feedback-restored event. The report contained no fatal errors, and both motor Stop
replies were received during cleanup. These counts distinguish individual query
timeouts from recovery episodes. No jog events were recorded in this session.

This supports recovery tolerance during stationary direct polling, not uninterrupted
feedback or reliable tracking during motion. Keep the current movement lockout,
Stop and bounded-recovery logic. Never disables intentional idle release only;
transport and feedback faults can still close the connection. Do not infer that
keep-alive prevents failures or change timeout defaults from this single run.
A controlled 2-second versus 5/10-second interval comparison is a follow-up, not a
completed result. Another direct session began around 10:17 with the same policy.

Persistent Control Bridge tab markers added: red when not ready, green after
bridge_ready; cleared on shutdown request, error and bridge_off. Existing yellow
Motor control marker retained. Focused GUI regression covers initial red, ready
green, simultaneous yellow motor indicator and red after shutdown.

Seven focused bridge GUI tests passed after adding the persistent initial red
marker. Ruff, whitespace checks and wheel/source distribution build passed.
The updated Windows GUI was relaunched and its red Control Bridge marker visually
confirmed from Motor control, together with the renamed settings title/subtitle.
Left disconnected, bridge OFF, for user testing; no physical motion commanded.


## Software proxy identity and discovery — November 18

Added a read-only management identity and UDP discovery metadata that distinguish
this computer's software proxy from a physical WiFly adapter or an unclassified
AUX endpoint. Discovery verifies the version family before sending the private
identity query and does not open the motor port for recognized proxies. Selecting
a proxy does not replace the GUI hardware/provisioning target.

All 60 tests passed across test_bridge_mode, test_discover_modules,
test_setup_gui.BridgeGuiTests and test_setup_gui.ReleaseGuidanceTests. The loopback
test keeps a simulated control client connected while discovering the proxy,
verifies no upstream commands or Stop are injected, then verifies the client's
next motor-position query still receives its reply. This is automated fake-mount
validation, not a live telescope or SkySafari compatibility test.

Ruff, whitespace checks, and the wheel/source distribution build passed. The
existing running GUI was not interrupted; restart it to expose the new identity.
Custom management-port auto-discovery, authenticated identity, and the future
physical ESP32 control mode remain outside this change. See PROXY-DISCOVERY.md.
