# Raspberry Pi / KStars session closeout — 2026-11-16

## Verified hardware path

KStars D-Bus INDI controls → local INDI server → this application's GUI Control Bridge → SkyQLink RN-171 → real COSMOS 90GT motor controllers.

After rebooting the Pi, KStars and the INDI server started. Loading the saved Celestron AUX configuration restored the bridge computer's address. The bridge initially refused to start because motor encoder replies were missing, despite a reachable Wi-Fi adapter. Recovery could not confirm WiFly command mode and therefore sent no restart. After the user power-cycled the telescope, discovery identified it, the bridge started, and KStars connected. Four successive fresh samples confirmed stationary readback from both axes. Telescope power cycling reset the raw encoder counts to zero; these are not aligned sky coordinates.

With explicit user authorization and clearance, two bounded 0.7-second directional requests were sent through KStars, using driver rate label 5x (not a calibrated degrees/second value). An independent local watchdog requested Stop/Abort after 1.2 seconds, and normal/finally cleanup also requested Stop. Fresh raw bridge samples verified:

| Axis | Measured change | Subsequent change after Stop |
| --- | ---: | ---: |
| Azimuth | -0.049073696° | 0° |
| Elevation | +0.062935352° | 0° |

KStars remained connected. The v1.9.4 AUX driver updates its horizontal-coordinate display only after approximately 0.1° of change, so these small movements did not immediately change that display. Validation used fresh timestamped encoder replies, not cached display values. Earlier manual movement/Stop checks also succeeded on both axes. No celestial GoTo, real-star alignment, or sustained tracking accuracy was tested.

## Environment and workarounds

| Component | Version / arrangement |
| --- | --- |
| Computer | Raspberry Pi 3 B+, armv7l, 32-bit, 1 GB RAM |
| OS / kernel | Raspbian GNU/Linux 10 Buster; 5.10.103-v7+ |
| Python / Tk | 3.12.16; Tcl/Tk 8.6.9 |
| TLS / process library | OpenSSL 1.1.1n; psutil 7.2.2 |
| KStars | 3.0.0; Debian package 5:3.0.0-1 |
| Custom INDI core / AUX source | v1.9.4 / indi-3rdparty v1.9.4; AUX DRIVER_VERSION reports 1.0 |
| System INDI / CCD Simulator | 1.7.5+dfsg-1; simulator DRIVER_VERSION reports 1.0 |
| Desktop | PCManFM 1.3.1-1+rpt27; libfm 1.3.1-1+rpt18; lxsession 0.5.4-1+rpt1 |

Legacy Ekos rejected a mount-only profile: CCD Simulator is required as a placeholder. It does not simulate the telescope and must not be used to claim physical alignment. The custom AUX server uses its own library directory; the system simulator wrapper removes LD_LIBRARY_PATH before starting the simulator to avoid mixing library versions. The KStars shortcut starts the user INDI service. The saved profile uses remote INDI at loopback port 7624, automatic device connection disabled, Celestron AUX mount, and CCD Simulator. Load saved settings in the Celestron AUX device tab before connecting; server startup alone may leave the default telescope address active.

The tested motion application baseline was fc65ac7. Windows recorded 142 passing tests, and Pi recorded 142 tests with 3 optional-MCP skips. The later upstream macOS fix was independently user-confirmed; this work does not repeat or reopen it. Final documentation/assets deployment is separate from that motion baseline.

## Alignment and reset boundaries

Use manual eyepiece centering and KStars Sync, as described in the application note. No camera alignment workflow is part of this deployment. Controller position writes and application-local offsets do not populate INDI's alignment model. After a power cycle or changed raw reference, rebuild the INDI model; do not assume another app's offsets are shared.

Active local offsets clear on disconnect/lost motor feedback. Same-session, same-adapter uptime/restart observations from diagnostics or the time dialog can also clear offsets and warn. This is sampled evidence of a possible adapter restart, not continuous motor-reset detection. Rollover cannot reliably be distinguished. The application does not clear or rebuild KStars' separate alignment model.

## Remaining work

- Observe real stars, build a manual multi-star Sync model, and assess GoTo accuracy and tracking.
- Investigate the intermittent reachable-adapter/no-motor-replies condition; a Pi reboot does not reset SkyQLink.
- Improve coordinated session/reset handling across bridge clients without interrupting motor traffic for WiFly polling.
- CPWI and other clients need separate end-to-end verification. No universal compatibility claim is made.
- Native Windows/macOS appearance of the new icon containers remains unverified; macOS GUI rendering was already fixed separately.

Detailed installation-specific logs and network identifiers remain on the deployment machine, outside the public repository. See the portable desktop guide and application note for reproducible operating steps.

## Durable development rules from this session

- Preserve the independently completed macOS appearance fix; do not reopen it without new evidence.
- Keep application examples illustrative, not implied compatibility guarantees. Keep KStars guidance in an application note.
- Distinguish fresh raw encoder feedback, displayed INDI coordinates, controller references, application-local offsets and celestial alignment.
- Never call a network connection or simulated camera proof of real telescope alignment. Manual eyepiece centering and Sync are the requested workflow.
- After power cycling or changing raw references, invalidate assumptions about the external client's alignment. Current local offset clearing does not reset INDI's model.
- Record firmware/driver/library versions and actual test scope. Keep machine-specific logs, keys and paths outside public examples.
- Close an existing GUI before testing a desktop launch action. Do not run GUI tests on an actively operated telescope display.
- Future live motion tests require current clearance and other controllers disconnected; use bounded motion, independent Stop and fresh feedback checks.

Release verification: the portable desktop installer was run successfully on the Pi, preserving the venv interpreter, installing the requested shortcut name/icon and all three zoom actions. Generated shell syntax passed. The updated guide was installed on the desktop. Nine targeted time/position tests and lint passed on Windows. Earlier PCManFM right-click action visibility was visually verified; the installer recreates those action definitions.
