# macOS appearance adjustments — November 16, 2026

The application remains a portable Python/Tk program. Tk's `aqua` window-system
identifier enables the following appearance adjustments only on macOS:

- Keep native Aqua notebook tabs, centered within the form; do not import the
  clam tab element or custom light-blue/gray selection map into the Mac theme.
- Place discovery below the network-mode choices and shorten the infrastructure
  label. Lay out the five Diagnostics toolbar controls in two rows. Previously
  the hidden Diagnostics page forced the whole form wider than the window,
  shifting the tab bar and hiding the port and provisioning controls.
- Use the native label foreground for explanatory text, avoiding hard-coded
  black/dark-gray text in macOS dark appearance. Keep explicit dark foreground
  on the bridge's light status panel so labels remain readable.
- Derive diagnostic tree row height from the text metrics when zoom is enabled.

Other window systems retain their existing toolbar layout, labels and tab color
map. This change does not require an OS-specific Python dependency and does not
change networking, motor commands, provisioning or bridge behavior.

Validation uses local Python 3.14 / Tk on macOS, GUI startup, offline GUI and
regression tests. Windows and Raspbian 10 appearance was reported working before
these changes; it has not been visually rechecked in this Mac session. Earlier
hardware validation remains separate from this formatting work. A missing
`telescope` section in a local calibration profile also exposed an export crash;
the profile label now falls back to unidentified rather than raising KeyError.

Completed checks: 147 offline tests ran successfully (144 passed, 3 skipped), plus the new Aqua layout
regression passed separately. Lint and zoom-enabled GUI startup passed. The
layout regression checks the form fits a 980-pixel window and verifies that the
custom tab background map is absent. The original rendering was inspected in a
screenshot. Post-change automated screenshot review was blocked by native UI
access timeouts; the subsequent user review of the relaunched app is recorded below.

User visual review after relaunch: confirmed the updated Mac rendering looks
much better. This confirms appearance on the tested Mac, not new hardware
behavior or a fresh Windows/Linux visual validation.
