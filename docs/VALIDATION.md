# Validation and remaining checks

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
- Real hardware showed occasional idle encoder delays. The new three-miss policy
  is covered by loopback integration tests; live endurance validation remains due.
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
