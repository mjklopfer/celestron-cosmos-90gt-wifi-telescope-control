# Validation and remaining checks

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
