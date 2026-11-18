# Version 1.1 — network control profile refresh

Release date: 2026-11-18. Application: **Celestron Telescope Network Control**.
Repository: **mjklopfer/celestron-telescope-network-control**. Existing checkout
folders, Python package name and `cosmos90gt` command names remain compatible.

## Changes

- Three communications profiles: legacy SkyQLink, modern Celestron module, and
  read-only controller proxy. Discovery recommends a profile; Apply commits the
  selected target. Pending selection disables operational tabs. Green indicates
  applied configuration, not verified connectivity.
- Bridge is available only for legacy SkyQLink. Modern-profile polling and logs
  are under Diagnostics; direct motor control uses AUX without WiFly startup or
  recovery commands. Identified controller proxies cannot issue motor writes.
- View Local Network Interfaces is available above the tabs in every profile.
  Adapter addresses, subnets and status are distinct from the telescope address.
- Two-axis controller readouts retain alignment and history. Read one axis at a
  time. Supported cord-wrap and GoTo-approach controls use read-before-write and
  readback; unavailable settings remain disabled. Default/Reversed mapping is
  provisional, and raw encoder changes do not establish celestial alignment.
- Restart Bridge Connection attempts Stop and requires successful Stop replies
  before reopening the same target. It does not restart the Wi-Fi module or
  replay motion. Log rendering is bounded and follows the bottom only when the
  user has not scrolled upward.
- Logs identify local/external origins and routing, distinguish raw AUX hex from
  interpretation, and label inferred reply purpose. Save All Logs creates a ZIP;
  offline import/export supports multiple sessions with bounded archive sizes.
- Experimental modern Wi-Fi setup provides SSID/password and automatic Personal
  security negotiation. Commercial configuration requires explicit opt-in. ESP32
  source 0.2.3 adds capability advertisement and staged configuration; old 0.2.2
  firmware still needs its portal. Saving is not proof of successful network join.
- HomeBrew interface research and the guarded standalone fakegps prototype are
  documented separately. No new generic time/location write endpoint is claimed.
- README, user guide, deployment recipe, roadmap and interface documentation
  explain the profile boundaries. The Pi launcher retains display-size actions.

## Verification boundaries

See [validation results](VALIDATION.md) for the completed software checks and Pi
installation evidence. Existing COSMOS 90GT live-motion tests are historical
baseline evidence, not new tests of this release. Commercial module provisioning,
ESP32 0.2.3 firmware compilation/flash, physical ESP32 AUX wiring, new macOS visual
review, celestial alignment and sustained high-speed tracking remain unverified.
No physical movement or credential writes were performed for this release check.

The GUI test harness now waits for its queued events to drain instead of assuming
all rendering finishes in 150 ms; the production GUI retains its bounded batches.

Local reference works in both physical-module profiles over a direct motor connection. Connect Motors and Disconnect buttons are available inside that section, alongside connection status, current raw encoder angles, sample ages and operation status. Read buttons request a fresh axis sample even with periodic polling off; reads do not renew the user-idle release timer or issue movement. Wait for one axis read to finish before requesting another. Set local reference changes only this app’s coordinate display, not telescope or other-app alignment. Controller-proxy and active-bridge sessions do not support these direct local-reference operations.

## Final review refinements

- The top connection control is now an indicator only, aligned beside the profile
  dropdown. Connect through Motor control or the legacy Control Bridge. Motor
  release retains orange/unconfirmed without holding a connection; terminal
  failures show red. Fresh bridge feedback shows green.
- SkyQLink can hand off a direct motor session to the bridge after Stop replies
  from both axes and socket release. Failure prevents bridge startup.
- Modern Celestron Diagnostics includes the latest motor-position table and
  shared polling/keep-alive controls. This display adds no polling traffic.
- README uses the current bridge screenshot and current repository clone path;
  the obsolete legacy screenshot section and switch instructions are removed.
