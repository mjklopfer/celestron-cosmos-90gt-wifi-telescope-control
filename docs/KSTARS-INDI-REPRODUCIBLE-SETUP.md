# Reproduce the Raspberry Pi KStars / INDI / Control Bridge installation

This is the detailed build, installation and operating recipe for the inspected
Pi deployment. See also the [daily guide](TELESCOPE-CONTROL-START-HERE.md) and
[alignment/application note](KSTARS-BRIDGE-NOTE.md). KStars and INDI are optional
companions, not prerequisites for the telescope application.

## Scope and evidence

Inspected November 18, 2026. Application commit `7ae366e` ran on the Pi with 39
passing offline deployment checks. KStars/INDI then exchanged 256 client packets
and 918 forwarded return packets over 131 seconds, with fresh readings from both
motors and no bridge errors. Tracking was off; no movement was commanded in this
check. Earlier bounded two-axis motion and Stop tests are recorded in the
[validation history](engineering/2026-11-16-pi-kstars-validation.md).

This recipe reconstructs the working installation from installed files, source
commits, the local CMake diff, build caches and live checks. **A complete rebuild
from a fresh OS image using this assembled guide has not been repeated.** Package
availability can differ. Real-star alignment, GoTo accuracy and sustained tracking
remain unverified. Do not downgrade a newer OS just to reproduce legacy versions.

## 1. Connection architecture

```text
KStars / Ekos
  -> INDI server: 127.0.0.1:7624 on the Pi
     -> real Celestron AUX driver
        -> this app's Control Bridge: BRIDGE_IP:2000
           -> SkyQLink telescope: TELESCOPE_IP:2000
     -> CCD Simulator: placeholder camera for legacy Ekos only
```

`BRIDGE_IP` is the computer running the bridge, not the telescope. Enter
`TELESCOPE_IP` in the telescope application's upstream connection field. The
tested installation used the Pi's LAN address for INDI-to-bridge traffic. A bridge
bound only to that LAN address does not listen on localhost. To use loopback,
explicitly bind the bridge to `127.0.0.1` and use that address in INDI too.
Loopback binding prevents remote phones/computers from reaching the bridge.

If the bridge runs on another computer, use that computer's reachable LAN address
in the AUX driver. The INDI server can remain local on port 7624. Allow required
local-network traffic through firewalls; do not expose these services to the
Internet. The inspected INDI server listens on all interfaces; setting localhost
in KStars is not a firewall rule.

This recipe uses the **SkyQLink** profile and its legacy bridge. Modern Celestron
modules use their supported direct AUX connection instead. Only one owner should
connect directly to the SkyQLink telescope at a time.

## 2. Recorded versions and source revisions

| Component | Inspected/tested value |
| --- | --- |
| Hardware | Raspberry Pi 3 B+, 1 GB, armv7l / armhf |
| OS / kernel | Raspbian 10 Buster; 5.10.103-v7+ |
| Application Python | 3.12.16, separate environment; system Python remains 3.7.3 |
| Tcl/Tk / psutil | 8.6.9 / 7.2.2 |
| KStars | 3.0.0, Debian package `5:3.0.0-1` |
| Custom INDI core | v1.9.4 plus supplied minimal-build patch |
| Custom indi-3rdparty | v1.9.4, Celestron AUX subtree, no local modifications |
| Celestron AUX DRIVER_VERSION | 1.0; this is not the INDI library version |
| System INDI / CCD Simulator | `1.7.5+dfsg-1`; simulator DRIVER_VERSION 1.0 |
| CMake | `3.16.3-3~bpo10+1` |
| Compiler | GCC 8.3.0 |
| Desktop | PCManFM 1.3.1; LXSession 0.5.4 |

Pinned source revisions:

- INDI core: `84d43ad6f90571fe25e147b30594d2c622e44a40`
- indi-3rdparty: `b1406fc8503b5b482ae06e9a79bf7e46471aa26d`

The custom prefix `/opt/indi-cosmos-1.9.4` keeps the newer server/driver separate
from system packages used by the old camera simulator. It is an installation
choice, not a personal path. If changing it, adjust all build and service paths.

## 3. Prepare prerequisites and preserve an existing setup

First follow the [Pi desktop guide](RASPBERRY-PI-DESKTOP.md) for the telescope app,
Python SSL/Tk requirements, venv and desktop launch actions. Do not replace system
Python. Newer supported operating systems can use the ordinary application setup.

Before rebuilding an existing system: stop motion, disconnect KStars devices,
switch Bridge OFF, close KStars, and stop the user service:

```sh
systemctl --user stop cosmos-indi.service
```

Back up `~/.indi`, `~/.local/share/kstars/userdb.sqlite`, launchers and the service.
Copy the SQLite database only with KStars closed, or use SQLite's backup API.
The commands below assume fresh source/build directories; preserve existing work
before reusing those names. Existing application checkout folders can keep their
old name; use the actual path rather than renaming solely to match this guide.

On Buster, follow the Pi guide's archive-repository repair if the original Raspbian
URL is unavailable. Keep package signature and TLS verification enabled. Do not
mix release repositories or install binaries for the wrong CPU architecture.

```sh
sudo apt update
sudo apt install git build-essential cmake pkg-config python3 \
  kstars indi-bin libindi-data \
  libnova-dev libcfitsio-dev libusb-1.0-0-dev libgsl-dev libjpeg-dev \
  libcurl4-gnutls-dev libfftw3-dev zlib1g-dev libev-dev
cmake --version
command -v indi_simulator_ccd indi_getprop indi_setprop
```

The `-S` / `-B` syntax below needs CMake 3.13 or newer. The inspected Pi had 3.16.3
from backports; verify available candidates rather than assuming old repositories
remain available. Installation below uses the build's `install` target, also
usable with 3.13. Recorded dependencies included libnova 0.16-4, CFITSIO 3.450-3,
GSL 2.5, FFTW3 3.3.8, libusb 1.0.22, libev 4.25, zlib 1.2.11 and curl 7.64.0.
These describe the environment, not instructions to downgrade a current system.

## 4. Fetch pinned sources and apply the actual Pi patch

Set `PROJECT_DIR` to the application checkout containing this guide. Keep these
variables in the same terminal for the subsequent build/install commands.

```sh
PROJECT_DIR="$HOME/celestron-telescope-network-control"
INDI_WORK="$HOME/src/indi-cosmos"
INDI_PREFIX=/opt/indi-cosmos-1.9.4
mkdir -p "$INDI_WORK"
cd "$INDI_WORK"
git clone --depth 1 --branch v1.9.4 https://github.com/indilib/indi.git
git clone --depth 1 --branch v1.9.4 https://github.com/indilib/indi-3rdparty.git
test "$(git -C indi rev-parse HEAD)" = 84d43ad6f90571fe25e147b30594d2c622e44a40
test "$(git -C indi-3rdparty rev-parse HEAD)" = b1406fc8503b5b482ae06e9a79bf7e46471aa26d
git -C indi apply --check "$PROJECT_DIR/examples/indi/indi-core-v1.9.4-minimal.patch"
git -C indi apply "$PROJECT_DIR/examples/indi/indi-core-v1.9.4-minimal.patch"
git -C indi diff --stat
```

Stop if either revision test or patch check fails. Execute commands in order,
checking errors rather than continuing past them. Do not apply the patch to an
arbitrary newer source tree. On an already patched tree, reverse-apply **checking**
can confirm its presence; do not actually reverse it.

The [patch](../examples/indi/indi-core-v1.9.4-minimal.patch) is the exact seven-line
addition to the working Pi's CMakeLists.txt. It disables the duplicate static
driver library and the large unrelated built-in driver target group. Shared core
libraries, alignment support and the INDI server remain. Celestron AUX is built
separately; the system CCD Simulator remains necessary for the legacy workaround.

## 5. Build and install

The following flags match the working build caches. Use `-j1` instead of `-j2`
if the 1 GB Pi runs out of memory. A failed build is not a successful install.

```sh
cd "$INDI_WORK"
cmake -S indi -B build-core \
  -DCMAKE_INSTALL_PREFIX="$INDI_PREFIX" \
  -DINDI_BUILD_QT5_CLIENT=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build-core -j2
sudo cmake --build build-core --target install
cmake -S indi-3rdparty/indi-celestronaux -B build-aux \
  -DCMAKE_INSTALL_PREFIX="$INDI_PREFIX" \
  -DCMAKE_PREFIX_PATH="$INDI_PREFIX" \
  -DCMAKE_INSTALL_RPATH="$INDI_PREFIX/lib" -DCMAKE_BUILD_TYPE=Release
cmake --build build-aux -j2
sudo cmake --build build-aux --target install
env LD_LIBRARY_PATH="$INDI_PREFIX/lib" ldd "$INDI_PREFIX/bin/indi_celestron_aux"
```

The AUX build cache must select the custom `include/libindi`, `libindidriver`
and `libindiAlignmentDriver`, not the system 1.7.5 libraries. In `ldd`, both INDI
libraries should resolve under the custom prefix and nothing should be `not found`.
Do not globally export this LD_LIBRARY_PATH in a login profile: the older system
camera simulator needs its own matching system libraries.

## 6. Install the wrapper, user service and launcher

The [adjunct files](../examples/indi/README.md) reproduce the installed arrangement
without a hardcoded username. `%h` in the service resolves the current home.

```sh
mkdir -p "$HOME/.local/bin" "$HOME/.config/systemd/user"
install -m 755 "$PROJECT_DIR/examples/indi/cosmos-ccd-simulator" "$HOME/.local/bin/cosmos-ccd-simulator"
install -m 755 "$PROJECT_DIR/examples/indi/launch-cosmos-kstars" "$HOME/.local/bin/launch-cosmos-kstars"
install -m 644 "$PROJECT_DIR/examples/indi/cosmos-indi.service" "$HOME/.config/systemd/user/cosmos-indi.service"
sh -n "$HOME/.local/bin/cosmos-ccd-simulator"
sh -n "$HOME/.local/bin/launch-cosmos-kstars"
systemctl --user daemon-reload
systemctl --user start cosmos-indi.service
systemctl --user status cosmos-indi.service --no-pager
```

Use the logged-in graphical user, not `sudo systemctl --user`. The service is
manual/static with no Install target; `systemctl --user enable` is not needed.
The launcher starts the service, then KStars. Restart-on-failure does not restore
a telescope alignment model or request movement.

For SSH commands targeting that user's existing desktop D-Bus session:

```sh
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
```

Remote graphical launch also needs the correct X session/authorization. The
inspected Pi uses DISPLAY=:0 and XAUTHORITY="$HOME/.Xauthority"; verify these on
your system. Normally launch from the desktop. A new X server or user lingering
is not required by this recipe.

Create the KStars desktop entry with the current home expanded during installation:

```sh
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || printf '%s/Desktop' "$HOME")"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/KStars-COSMOS.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=KStars - Celestron Control Bridge
Comment=Start INDI and KStars; select COSMOS 90GT - Local Control Bridge in Ekos
Exec="$HOME/.local/bin/launch-cosmos-kstars"
Icon=kstars
Terminal=false
Categories=Education;Astronomy;
EOF
chmod +x "$DESKTOP_DIR/KStars-COSMOS.desktop"
```

The desktop may require marking the shortcut trusted. This is separate from the
telescope application's shortcut and its 80%/100%/standard-view actions installed
by `tools/install_linux_shortcut.py`. The KStars shortcut does not start Bridge:
switch Bridge ON in the telescope application before connecting the mount.

## 7. Create the Ekos profile

Use KStars' graphical profile editor; do not distribute a personal KStars database.

| Field | Setting |
| --- | --- |
| Profile name | COSMOS 90GT - Local Control Bridge |
| Mode | Remote INDI, even on the same Pi |
| Server host / port | 127.0.0.1 / 7624 |
| Auto-connect devices | Disabled |
| Mount | Celestron AUX |
| CCD | CCD Simulator |
| Guider | Internal/default; no physical guider required here |

Open KStars, open Ekos, add a profile, enter these settings and save. Start that
profile. If remote drivers are not listed, verify the service is running and
select the exposed devices. Do not start another local INDI server on port 7624.
The AUX XML settings and the Ekos profile are separate: one does not create the other.

KStars 3.0.0 rejected a mount-only profile. CCD Simulator satisfies that legacy
requirement. The wrapper removes LD_LIBRARY_PATH before starting the system
`indi_simulator_ccd`, avoiding custom 1.9.4 libraries in the system 1.7.5 simulator.
Only the camera is simulated. This is not physical image alignment and does not
verify a real camera. Newer Ekos versions may not require this workaround.

## 8. Configure the real mount and save settings

In the telescope application, select Infrastructure where appropriate, discover
or enter the telescope address, and apply the SkyQLink profile. Turn Bridge ON;
verify motor replies and note its listening address. Direct/ad hoc networking
requires the application's Two Interface Mode arrangement instead; the inspected
installation used shared infrastructure LAN.

In Ekos, open **INDI Control Panel → Celestron AUX**. This is a device tab, not a
separate application. Configure while the device is disconnected:

| Property | Value |
| --- | --- |
| Connection mode / protocol | Network TCP, not serial or UDP |
| Address / port | Bridge listening IP / 2000 |
| Automatic LAN search | Disabled for an explicit endpoint |
| Mount type | Alt-Az |
| Port type | AUX/PC, not hand-controller USB |

Use **Options → Save configuration**. After a later server start, use **Options →
Load configuration** and check the address before connecting. The inspected driver
could revert to 1.2.3.4 until saved settings were loaded. Connect the Celestron AUX
device: starting Ekos only connects KStars to INDI when auto-connect is disabled.

The [example XML](../examples/indi-celestron-bridge.xml) supplies the core settings
with a placeholder address. To install it, stop the INDI service, back up
`~/.indi/Celestron AUX_config.xml`, replace the placeholder address in the example,
and copy it to that filename. Restart the service and explicitly load it in Options.
Prefer UI edits to preserve existing extra settings. Do not share personal site,
alignment or account configuration as a public example.

## 9. Read-only verification

These system indi-bin utilities inspect the same driver KStars uses, not a second
direct telescope connection:

```sh
indi_getprop -h localhost -p 7624 -t 3 'Celestron AUX.CONNECTION.*'
indi_getprop -h localhost -p 7624 -t 3 'Celestron AUX.DEVICE_ADDRESS.*'
indi_getprop -h localhost -p 7624 -t 3 'Celestron AUX.HORIZONTAL_COORD.*'
indi_getprop -h localhost -p 7624 -t 3 'Celestron AUX.TELESCOPE_TRACK_STATE.*'
ss -tnp
journalctl --user -u cosmos-indi.service -n 60 --no-pager
```

Expect CONNECT=On **and fresh actual replies**. In the bridge Communications Log,
check external-client requests and return routes to that client. Verify both axis
sample ages stay current over repeated observations. Zero counts after reset can
be legitimate; an unchanged display is not proof of fresh data. The driver may
not update displayed horizontal angles for changes smaller than about 0.1°.

Before KStars connects, bridge polling replies may say **not forwarded**: this
app requested and received them locally, without an external recipient. This is
not itself an error. Conversely, KStars can say Online while upstream replies
have stopped; use timestamps and the bridge readouts.

Optional D-Bus inspection, verified with KStars 3.0.0:

```sh
qdbus org.kde.kstars /KStars/Ekos org.kde.kstars.Ekos.getProfiles
qdbus org.kde.kstars /KStars/Ekos org.kde.kstars.Ekos.logText
```

Do not interpret a status number alone as motor health. Ekos also exposes
connectDevices/disconnectDevices; these affect all devices in the profile.
Use the UI for routine operation. No unattended movement test is provided here.

## 10. Motion, alignment and shutdown

Test movement only after checking clearance, cables and mechanical travel. Use a
small manual jog followed by Stop/Abort and verify fresh positions stop changing.
Raw encoder references and this application's local offsets do not align KStars.
For manual eyepiece alignment, set the observing site/time, center a known star,
then Sync that object in KStars. Rebuild the model after power cycling or changing
encoder origins. See the separate alignment note; accuracy is not established by
installation or readback tests.

Shutdown:

1. Stop/Abort in KStars and confirm physical rest.
2. Disconnect devices and stop the Ekos profile.
3. Switch Bridge OFF; inspect Stop results instead of assuming delivery.
4. Close KStars; stop `cosmos-indi.service` if no longer needed.
5. Close the telescope app, then remove telescope power or shut down the Pi normally.

## 11. Troubleshooting

| Symptom | Action |
| --- | --- |
| Ekos demands a CCD/guider | Add CCD Simulator with the library-isolating wrapper |
| Port already in use | Inspect `ss -ltnp`; do not start a second INDI server |
| Undefined symbols / simulator exits | Check matching libraries and wrapper; remove global custom LD_LIBRARY_PATH |
| Driver tries 1.2.3.4 | Load saved AUX configuration; check bridge address |
| localhost:2000 refused | Match the bridge's actual bind address in INDI |
| Online without fresh positions | Inspect return packets; disconnect stale sessions before recovery |
| ARP FAILED / telescope unreachable | Check power, Wi-Fi mode, current router address and network |
| Reset by peer / connection refused | Disconnect other clients; verify adapter state; power-cycle and rediscover if necessary |
| Aged values with polling OFF | No request means no guaranteed fresh sample; configure polling deliberately |
| Suspected SSID loss | Preserve readback evidence after releasing control; cause is unverified |
| Compiler killed | Try -j1 and inspect memory/error output |
| User service cannot reach bus | Use the logged-in desktop user's session, not root |

Bridge polling/heartbeat and direct Motor control idle release are separate.
An idle release does not start Bridge. Current SkyQLink code can perform a guarded
handoff when Bridge ON is selected during a direct motor session: it requires
both Stop acknowledgments and socket release before bridge startup. Do not bypass
a failed handoff to create competing owners.

## 12. Updates, rollback and remaining verification

App updates do not require rebuilding INDI. Stop sessions before replacing app
code, pull with `--ff-only`, reinstall using the existing venv, smoke-test and
refresh desktop actions. Documentation-only pulls need no driver restart.
Preserve existing checkout directory names where convenient.

Before changing INDI, back up the custom prefix, service, wrappers and saved
configuration. A new upstream version needs patch/dependency/behavior review.
For rollback, stop the service and restore a matching set of binaries/libraries
and service settings. Do not mix versions or overwrite the system KStars/simulator
with custom files. The source patch is specific to the pinned revision.

Adjunct files: [patch, wrappers and user service](../examples/indi/README.md).
Runtime evidence: [validation](VALIDATION.md). Python/app prerequisites:
[Pi desktop guide](RASPBERRY-PI-DESKTOP.md).

A fresh-image reconstruction remains to be repeated independently. Long-duration
reliability, real-star alignment, accurate GoTo and tracking are separate tests.
The operator's report of lost saved SSID settings is not a proven firmware defect
or a proven consequence of removing power before disconnecting.
