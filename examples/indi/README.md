# Legacy Raspberry Pi INDI adjunct files

Follow [the complete reproduction guide](../../docs/KSTARS-INDI-REPRODUCIBLE-SETUP.md).
These files reproduce the inspected Buster/INDI 1.9.4 arrangement; they are not
required for every newer Raspberry Pi OS installation.

- `indi-core-v1.9.4-minimal.patch`: exact seven-line CMake customization from the
  tested Pi. Applies to INDI core commit `84d43ad6f90571fe25e147b30594d2c622e44a40`.
  Omits duplicate static indidriver and unrelated built-in driver targets;
  preserves shared libraries/server and separately built Celestron AUX.
- `cosmos-ccd-simulator`: isolates the system camera simulator from custom INDI
  libraries. Only the camera is simulated.
- `cosmos-indi.service`: manual user service; `%h` resolves the current home.
  `/opt/indi-cosmos-1.9.4` is the chosen install prefix, not a user-specific path.
- `launch-cosmos-kstars`: starts that service before KStars in the graphical user
  session. No automatic telescope connection or movement is requested here.

The companion [INDI configuration example](../indi-celestron-bridge.xml) has a
placeholder bridge IP; replace it before use. Do not publish your live KStars
SQLite database or observing-site/account settings as an example.

The patch was exported from the live source diff and checked with reverse-apply
validation. Wrappers were generalized from the installed files; shell syntax is
checked. A clean OS/source rebuild using this assembled guide remains untested.
