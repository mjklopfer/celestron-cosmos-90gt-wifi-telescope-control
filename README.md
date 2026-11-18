# Celestron Cosmos 90GT Telescope Wi-Fi Control

**Legacy Celestron SkyQLink Wi-Fi setup, telescope control, and a SkySafari / SkyPortal bridge.**

**Tested platforms: Windows 11, macOS, and Raspberry Pi OS (Raspbian)** —
see [testing scope](#platform-testing-status) for the checks completed on each.
An optional **View menu** provides zoom in/out, reset to 100%, and Fit width
for different screen sizes. Enable it with `cosmos90gt --zoom-controls`;
see [display sizing](#smaller-screens-and-optional-zoom-including-raspberry-pi).

**Raspberry Pi desktop setup:** [Raspbian build, Buster fixes, versions and desktop launcher](docs/RASPBERRY-PI-DESKTOP.md).

**User guide:** [Setup, controls, keyboard shortcuts, diagnostics, bridge, logs and configuration](docs/USER-GUIDE.md).
Motor control now includes an explicit **Keyboard control** OFF/ON switch,
consolidated **Controller Angle / Backlash Settings**, measured speed readouts,
and intentional idle release. Diagnostics can be aborted while retaining results.
The standalone `calibrate_telescope.py` records current settings and, with explicit
motion options, measures timed jogs into a telescope configuration; see the
[configuration instructions](docs/USER-GUIDE.md#generate-the-telescope-configuration).
Optional [MCP automation](docs/MCP-CONTROL.md) and an experimental
[tracking design](docs/TRACKING-DESIGN.md) are documented separately; native
streaming is not yet hardware-verified. [Future backend architecture](docs/ARCHITECTURE-PLAN.md)
records planned legacy/modern Celestron Wi-Fi support.

[![Python checks](https://github.com/mjklopfer/celestron-cosmos-90gt-wifi-telescope-control/actions/workflows/checks.yml/badge.svg)](https://github.com/mjklopfer/celestron-cosmos-90gt-wifi-telescope-control/actions/workflows/checks.yml)

Have a **Celestron Cosmos 90GT Wi-Fi telescope** with the original **SkyQLink /
WiFly RN-171** module? This Python desktop application lets you configure its
router Wi-Fi, drive the motors, inspect encoder positions, and bridge compatible
astronomy apps to the original adapter. SkySafari is a tested example client.

| What you need | What this application provides |
| --- | --- |
| Put an old SkyQLink telescope on home Wi-Fi | Read, upload and save infrastructure Wi-Fi credentials |
| Connect a compatible app to a legacy Celestron Wi-Fi module | Optional later-module-style discovery and TCP bridge |
| Move the telescope and check whether it moved | Manual Alt-Az motor controls with encoder position and motion delta readback |
| Diagnose a connection problem | Module identification, native WiFly replies and motor-controller diagnostics |
| Reach telescope Wi-Fi and home Wi-Fi at the same time | Verified computer Ethernet + telescope Wi-Fi bridge arrangement |

**Start here:** [Install and run](#install-and-run) ·
[Supported hardware](#supported-telescope-and-wi-fi-hardware) ·
[Wi-Fi modes and physical switch](#telescope-wi-fi-modes-and-physical-switch) ·
[Bridge setup](#bridge-two-addresses-with-different-purposes)

The original radio module is the **Roving Networks WiFly RN-171** (also
written RN171), rather than an ESP32 or ESP8266. The inspected telescope reports
**WiFly firmware `2.40-CEL`**, build date **03-05-2012**; native provisioning
currently checks for that RN-171 / `2.40-CEL` combination before writing settings.
The ESP32 simulator included in this repository is a separate hardware project.

The target hardware is the original WiFly **Wi-Fi** interface, not a Bluetooth
(BT) adapter. Direct hardware support for later-generation Celestron modules is
not established. Bridge mode instead presents selected later-generation-style
behavior to control applications while communicating with the original module.

## Supported telescope and Wi-Fi hardware

This project targets the **Celestron COSMOS 90GT Wi-Fi telescope (model 22094)**
and its **first-generation / Gen 1 / Version 1 Celestron SkyQLink Wi-Fi module**.
The original radio is the **Roving Networks WiFly RN-171 (RN171)**, with
Celestron-specific **2.40-CEL** firmware. Related names and functions used in
this project include:

- **Celestron WiFi / Celestron Wi-Fi**, legacy SkyQLink adapter and telescope control.
- **SkySafari, SkyPortal and CPWI** compatibility, with an optional TCP bridge.
- **Celestron AUX protocol**, altitude/azimuth (Alt-Az) motor control and encoder
  position readback over TCP port **2000**.
- **WiFly configuration**, Wi-Fi provisioning, infrastructure / station mode,
  direct / ad hoc mode and WPA2-Personal network setup.
- **Python / Tkinter** desktop control, network discovery and read-only diagnostics.

These terms identify the hardware and functionality discussed here; they do not
extend the compatibility claims to every Celestron telescope or Wi-Fi generation.

## Bridge emulation and provisioning-only use

Bridge mode presents **later-generation Celestron Wi-Fi module-style discovery
and connection behavior** to the control application, while relaying native AUX
commands to the original Version 1 adapter. It uses an AMW007-style discovery
identity and limited read-only management replies. This is a compatibility bridge,
not a complete emulation of every newer module feature, and it does not replace
or upgrade the original adapter's firmware.

**The full bridge is optional.** After the Version 1 adapter has been provisioned
onto the router's infrastructure Wi-Fi, compatible control applications can
connect directly to the telescope's assigned IP. This includes supported
SkySafari configurations and compatible PC-based Celestron applications, such as
CPWI. App version, telescope profile and original-module compatibility still
matter; this is not a guarantee that every Celestron-labelled profile works.
The computer does not need to relay that connection.

**Direct/ad hoc operation is a separate case.** The original SkyQLink network can
have connectivity or compatibility problems with newer control applications.
That is where the bridge can help: it connects upstream to the old adapter while
presenting later-generation-style discovery and connection behavior to the app.
In the verified two-interface arrangement, computer Wi-Fi joins SkyQLink and
computer Ethernet reaches the house network, while the phone remains on house
Wi-Fi. The bridge does not modify or repair the adapter's radio, and the computer
must still be able to join and communicate over the telescope-facing network.

If your control app already works directly over infrastructure Wi-Fi, use this
software only for provisioning:

1. Connect to the original adapter using its reachable direct or infrastructure IP.
2. In **Wi-Fi provisioning**, enter the router SSID, password and supported security,
   then upload and save the settings.
3. Power the telescope OFF, set its physical Wi-Fi switch RIGHT for infrastructure
   mode, and power it ON. Find its router-assigned IP.
4. Disconnect this software from the adapter, then connect the control application
   directly to that telescope IP using its infrastructure/Access Point settings.

In that arrangement, **leave Bridge OFF**. The computer and this software do not
need to remain running after provisioning. Here, “directly” means control app to
adapter through the router network; it does not mean the app's Direct Connect
hotspot mode. App/version compatibility varies, so a successful direct connection
should be verified rather than assumed. Use the bridge when the control app
cannot communicate reliably with the original module on its own.

## Celestron SkyQLink connection questions

### SkySafari or SkyPortal cannot connect to an old Celestron Wi-Fi module

This project provides an optional **SkySafari / SkyPortal Wi-Fi bridge** for the
original Version 1 SkyQLink adapter. It presents selected newer-module discovery
and management behavior while relaying commands to the original telescope.
It addresses a tested legacy-adapter compatibility case, rather than promising
a fix for every “Connection Failure” or “Automatic Telescope Wi-Fi Detection
Failed” message. Start by verifying the adapter and motors in Diagnostics.

### How do I configure SkyQLink infrastructure mode without the phone app?

Use **Wi-Fi provisioning** to read the RN-171 settings and save a supported
router SSID and password. Follow the physical-switch and restart instructions.
A compatible control application can then connect to the assigned IP directly;
leave Bridge OFF when that connection works. See [provisioning-only use](#bridge-emulation-and-provisioning-only-use).

### Is this a Celestron firmware update or a replacement Wi-Fi adapter?

It is desktop software for communicating with the existing **WiFly RN-171**
adapter. The bridge does not flash the telescope or turn its radio into newer
hardware. The included ESP32 telescope simulator is a separate development tool.
Phone-hotspot operation remains unverified.[^phone-hotspot]

## Requirements

- Python **3.10 or newer**, with **Tkinter/Tcl-Tk** and a graphical desktop.
- `psutil>=5.9,<8` (installed automatically by pip). No manufacturer driver is required
  for ordinary TCP/IP telescope communication.
- A powered compatible mount and an IPv4 connection to its adapter, normally
  TCP **2000**. The application does not configure the computer's network joins.
- For infrastructure mode, computer, telescope and phone must have mutual local
  network access. Guest/client isolation can block discovery and connections.
- For a two-interface bridge, one interface reaches SkyQLink directly and another
  reaches the phone's LAN. Ethernet plus Wi-Fi has been verified on hardware.
- Only one application/session should own the original adapter connection.

Windows, Linux and macOS are intended hosts. See the platform testing status
below for verified and reported results. Automated tests use mock devices;
they do not establish hardware compatibility. CI checks are defined for
Windows and Linux.

On some Linux installations, install the distribution's Tk package first
(for example `python3-tk` on Debian/Ubuntu). Linux GUI tests need an X display
or Xvfb. On Windows, use a Python distribution installed with Tcl/Tk support.
Check availability with `python -m tkinter`.

### Platform testing status

**macOS appearance:** native Aqua tabs, theme-aware text and compact connection/diagnostic
toolbars improve layout on Mac laptop screens. These adjustments are conditional;
Windows and Linux retain their existing layout and theme choices. See
[macOS appearance notes](docs/MACOS-APPEARANCE.md) for scope and validation.

| Platform | Completed testing | Remaining checks |
| --- | --- | --- |
| Windows 11 Pro, build 26100, Python 3.14 | Current GUI release: 142 automated tests passed; lint, package build and GUI startup passed. Tabs, status readouts and bridge guidance reviewed locally. Earlier View menu/80% checks also passed. | New UI changes do not revalidate every hardware feature; see the detailed validation record for earlier hardware checks and remaining limits. |
| macOS, Python 3.14 | Telescope operation and Ethernet + telescope Wi-Fi bridging were previously tested. November 16 appearance update: GUI startup, zoom/layout tests and lint passed; the user confirmed improved rendering after relaunch. | This appearance update does not repeat hardware or endurance testing; automated post-change screenshot capture was unavailable. |
| Raspbian 10 Buster, 32-bit, Raspberry Pi 3 B+, Python 3.12.16 | SSL/Tk-enabled Python build, editable install, default and 80% zoom smoke tests, all four zoom tests, and desktop-entry launch verified. View menu and running X window visually checked. [Environment and setup details](docs/RASPBERRY-PI-DESKTOP.md). Both-axis manual movement, Stop and fresh feedback through KStars/INDI/Control Bridge verified, including fresh-session reconnection. Earlier Pi regression: 142 tests with 3 optional-MCP skips. | Real-star alignment, GoTo accuracy, sustained tracking and endurance remain unverified. |

The current Windows and earlier zoom-update checks were performed on November 16, 2026. Platform testing
does not imply every feature or hardware configuration has been validated.

Optional development tools are installed with `pip install -e ".[dev]"`; MCP uses
`pip install -e ".[mcp]"`. Neither extra is required for the ordinary GUI.
Python must include SSL for secure package downloads and Tk for the window;
a Linux SSH session also needs access to an existing graphical display.

The [complete runtime-option reference](docs/RUNTIME-OPTIONS.md) lists every GUI launch switch and the separate bridge/calibration tools, with defaults, examples, when to use each and when not to use it.

## Install and run

Download this repository using Git (or use GitHub's **Code → Download ZIP**):

```sh
git clone https://github.com/mjklopfer/celestron-cosmos-90gt-wifi-telescope-control.git
cd celestron-cosmos-90gt-wifi-telescope-control
```

Create a virtual environment from the repository folder:

```sh
python -m venv .venv
```

Activate it using your shell:

```sh
# POSIX shells
. .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Windows Command Prompt
.venv\Scripts\activate.bat
```

Install and launch:

```sh
python -m pip install -e .
cosmos90gt
# Or:
python -m skyqlink_setup --host 1.2.3.4 --port 2000
```

Use `python3` or the Windows `py` launcher if that is how your installation names
Python. No local developer account, fixed MAC address, home SSID or saved router
password is required. Infrastructure addresses are entered or discovered at run time.
The interface inventory uses native names supplied by the host OS.

### macOS layout and appearance

Mac formatting is selected automatically when Tk reports the **Aqua** window
system. No special install, command-line flag or extra dependency is required.
The application uses native, centered Mac tabs instead of mixing custom tab
colors with Aqua. Discovery sits below the network-mode choices, and the
Diagnostics toolbar uses two rows so a hidden tab cannot force the whole form
past the right edge of a laptop window. Explanatory text follows the native
foreground; the light bridge-status panel has explicit dark text for contrast.
With zoom enabled, diagnostic row height accommodates the font's line height.

Windows and Linux retain their existing tab styling, connection labels and
single-row toolbars. The changes improve display formatting; they do not alter
Wi-Fi settings, telescope protocols or motor movement. A separate compatibility
fix lets spreadsheet export label an older calibration profile without crashing
when its optional telescope metadata is absent.

The updated Mac appearance was reviewed and confirmed by the user on November
16, 2026. See [the detailed change and validation notes](docs/MACOS-APPEARANCE.md).

### Smaller screens and optional zoom (including Raspberry Pi)

The default text and control sizes remain at 100%. The window can be resized,
with horizontal and vertical scrollbars keeping oversized content reachable.
To enable a **View** menu with **Zoom in**, **Zoom out**, **Actual size (100%)**,
and **Fit width**, launch from your activated virtual environment:

```sh
python -m skyqlink_setup --zoom-controls
# Start at 80% on a smaller display:
python -m skyqlink_setup --zoom-controls --ui-scale 0.8
# Fixed startup size without a zoom menu:
python -m skyqlink_setup --ui-scale 1.25
```

`--ui-scale` accepts 0.5 through 2.0. Zoom changes fonts, text-based control
sizes, spacing, table rows/columns and the bridge switch. Fit width is a manual
action after resizing the window; it does not continuously shrink text as you
resize. Content taller than the window remains vertically scrollable. At the
minimum zoom, especially narrow windows may still need horizontal scrolling.
Zoom does not reconnect the telescope or change entered settings. Sizes are
not saved between launches. Omit both options for the default size and no menu.

### Verified Windows 11 setup

On **November 15, 2026**, a fresh clone of commit `7e7f543` was installed and
launched on **Windows 11 Pro (build 26100), using Python 3.14 with Tcl/Tk**.
No Windows-specific source changes or additional runtime requirements beyond
the instructions above were needed. The desktop window was visually checked
and remained responsive while disconnected from the telescope.

Validation used `python -m pip install -e '.[dev]'` to include the documented
developer tools; ordinary use only needs `python -m pip install -e .`.
Results on that PC:

- All **88 automated tests passed** using mock devices and loopback sockets.
- `ruff check .` passed.
- `python -m build` produced a source distribution and Python wheel.
- `python -m skyqlink_setup --smoke-test` passed, and the normal GUI launched.

The passing test suite emitted a Tcl progress-bar callback warning during GUI
cleanup (`can't invoke "winfo" command: application has been destroyed`). This
remains an issue to investigate; no corresponding error was observed in the
normal application launch.

The documented `COSMOS90GT_DATA_DIR` override was used to keep runtime data in
the checkout; it is optional. A standalone Windows executable was not built.
**Real telescope connectivity, motor control, Wi-Fi provisioning, bridge access
through Windows Firewall, and endurance operation remain unverified on Windows.**
These results establish software installation and startup on the tested PC,
not hardware compatibility or operation on every Windows 11 configuration.

## Telescope Wi-Fi modes and physical switch

The physical Wi-Fi slider is on the telescope mount beside its power connection.
For the tested original COSMOS unit, **LEFT** selects the direct SkyQLink network;
**RIGHT** selects the saved infrastructure/router configuration. Switch positions
refer to hardware, not the application's radio buttons. Power the mount OFF before
changing that switch, then power it ON.

- **Direct / ad hoc:** join the telescope's SkyQLink Wi-Fi on the computer. Its
  normal address is **1.2.3.4:2000**. This original module can use legacy networking
  that some current Wi-Fi hardware/drivers do not support.
- **Infrastructure / house Wi-Fi:** join the network where the telescope has been
  provisioned. Enter its router-assigned IP or use **Discover SkyQLink / Celestron Modules**.
  `1.2.3.4` is not its house-network address. DHCP addresses can change.

Selecting a software mode changes guidance and connection settings. It does not
move the telescope slider or connect the computer to a different Wi-Fi network.

## Application tabs

1. **Motor control:** connect, verify both motor position replies, choose rate
   1–9, and use hold arrows or bounded timed jogs. Stop ends commanded movement.
   Displays include firmware, raw encoder counts, angles and relative changes.
   Encoder angles are raw motor positions converted to degrees. They do not show
   the telescope’s aligned sky-pointing azimuth/elevation or an object’s coordinates. Use the scope/app's alignment procedure for sky pointing.
2. **Control Bridge:** relays native AUX traffic to a compatible phone/desktop control app.
   Defaults OFF. While ON, Diagnostics and Wi-Fi provisioning are disabled.
   Motor control offers optional local jogging through the bridge,
   with external-command priority; readbacks/logs remain visible. The controlling application can command real telescope motion.
3. **Diagnostics:** displays actual adapter query data, replies, timeouts and
   controller details. A responding RN-171 can be listed even when motors do not
   answer; adapter detection alone does not prove motor connectivity.
4. **Wi-Fi provisioning:** Connect & Read Settings displays replies in the
   **Transfer log below the tabs**, not a popup, and saves a report. Read settings or replace the router SSID, password and
   supported security settings. Supports an already provisioned adapter through
   its reachable infrastructure address as well as direct mode. Saving replaces
   network configuration; power OFF, set the physical slider RIGHT, and power ON
   to join the saved router. Discover the newly assigned IP afterward.

The selected connection mode controls discovery: **Direct / ad hoc** checks only
`1.2.3.4:2000` on the telescope Wi-Fi; **Infrastructure** scans
attached supported router networks. Direct discovery waits up to three seconds
for each connection attempt and retries once. If the telescope-facing Wi-Fi has
no usable address yet, the app explains that instead of searching Ethernet and
reporting an unidentified module. A successful settings read and a failed scan
can otherwise reflect different connection timing on this single-client adapter.

Discovery shows an animated state and a 60-second **search period**. The deadline
prevents new probes; already active probes may finish afterward. Neighbor/MAC
vendor hints prioritize candidates but do not replace protocol identification.
Scanning is limited to attached IPv4 private networks of /24 or smaller and the
known direct endpoint. It is not a general network inventory tool.

## Bridge: two addresses with different purposes

**Telescope Wi-Fi interface IP address** identifies SkyQLink. **This computer’s IP on the shared infrastructure network** identifies the local adapter on the control device's network,
not a MAC address. Select that adapter in **Local System Network Interfaces** to
fill the field; selecting it does not join a Wi-Fi network.

In **Infrastructure** mode, the telescope, this computer and the control device
use a common access-point network. An empty local IPv4 field uses the adapter
chosen by the operating system's route to the telescope.

In **Direct / ad hoc** mode, the Control Bridge switch is disabled until you check
**Two Interface Mode**. The notice beside the switch explains the requirement.
Connect one compatible Wi-Fi adapter to SkyQLink and a second adapter to the
control-app network. Select that second adapter's local IPv4 address (required),
then switch Control Bridge ON. Enter the displayed computer address and TCP port
in the astronomy app, using Celestron WiFi / Access Point mode.

The second adapter can be Ethernet to the router used by a phone/tablet over
Wi-Fi, Ethernet to a configured wired control device, or a second Wi-Fi adapter
joining the control device's router/hotspot. A supported second Wi-Fi adapter can
instead host a hotspot configured in the operating system. Phones/tablets do not
require two computer Wi-Fi adapters when the Ethernet-to-router path is available.
The control network must permit communication between devices; guest/client
isolation can block it.

```text
Phone/tablet -- router Wi-Fi -- router -- computer Ethernet
                                           |
                                      Control Bridge
                                           |
                                computer SkyQLink Wi-Fi -- telescope
```

Internet access, OS network bridging and NAT are not required for this command
proxy. Optional Internet sharing from a third interface, hotspot configuration,
DHCP and routing are outside the program; it does not merge network segments.
See the [user guide](docs/USER-GUIDE.md#directad-hoc-why-control-bridge-is-disabled)
for steps and topology choices. Earlier hardware testing covered Ethernet plus
SkyQLink Wi-Fi; two-Wi-Fi and hosted-hotspot setups remain unverified.

Allow this Python application incoming **TCP 2000 and 3000** from the phone's local
network and outgoing broadcast **UDP 55555**. Give the phone app Local Network
permission where required. A listening socket does not prove firewall access.
Do not expose these listeners through Internet port forwarding.

## Errors and recovery

If a connection fails, disconnect any other controlling applications, such as
SkySafari, SkyPortal or CPWI. Check the telescope destination, computer listening
IP and physical network joins. A telescope power-cycle may be needed after a lost
connection; it is not a guaranteed cure.

Control Bridge has no control-client or management-client inactivity cutoff.
Optional keep-alive and motor-position polling share one scheduler; both default
OFF and can be configured under Control Bridge. Local jogging uses the same
scheduler for required safety feedback. Incoming replies and pending external
queries are reused to avoid duplicate bridge-generated reads.

Missing optional replies are logged as gaps rather than closing the bridge after
three misses. A transport failure can still end the connection. Client disconnect
attempts Stop and leaves the bridge waiting for reconnection. Active local jogging
also attempts Stop if feedback is stale. Stop delivery cannot be guaranteed after
transport/power loss; inspect the readback and mount. Switching away from SkySafari
was observed to close its socket; a bridge heartbeat cannot prevent that. Reliability
and uninterrupted tracking must not be inferred from one successful session.

## Logs and private configuration

Runtime logs default to `~/.cosmos90gt/logs`. Set **COSMOS90GT_DATA_DIR** to change
the data root. This is a writable user data directory, not a source/install path.
Passwords are redacted from provisioning logs and not stored in source. Logs can
contain local IPs, device identifiers and movement data: review before sharing.
The original adapter retains the uploaded credentials itself.

Private development evidence, device profiles, flash/NVS backups, toolchains,
virtual environments and source snapshots are excluded from version control.
No credentials or raw user-specific hardware logs are required to run the app.

## Development and validation

```sh
python -m pip install -e '.[dev]'
python -m unittest discover -v
ruff check .
python -m build
# Linux without a desktop display:
xvfb-run -a python -m unittest discover -v
```

The tests use local fake adapters/loopback sockets and do not move the telescope.
`python -m skyqlink_setup --smoke-test` checks window construction without hardware.
Live scripts such as `verify_motors.py` and `gui_hardware_check.py` are separate,
explicitly invoked checks. Movement requires `--move`; do not run them while a
phone app or bridge is controlling the mount.

Create a standalone desktop build on the target OS:

```sh
python -m pip install -e '.[bundle]'
pyinstaller --noconfirm --clean --onedir --windowed --name COSMOS90GT skyqlink_setup.py
```

Build Windows executables on Windows; a build made on another OS is not a Windows
cross-build. Test the resulting program on the target computer with its network
interfaces, firewall and Tcl/Tk installation. Python source is the primary entry point.

## ESP32 simulator and future hardware

`hardware/esp32-simulator/` is an independent embedded prototype with a captive
Wi-Fi setup portal, saved network modes and a virtual telescope. A real SkySafari
session successfully displayed its simulated motion. It never connects to the
real telescope and is not the Python bridge. Its README covers separate Arduino
requirements and recovery behavior.

A physical ESP-to-AUX implementation is future work. AUX is a shared TTL bus,
not RS-232; voltage conversion alone does not implement bus arbitration. No AUX
wiring or ESP8266 port is claimed complete by this release.

## Source map

- `skyqlink_setup.py`: Tk interface and background operation/event coordination.
- `motor_control.py`: motor protocol, polling, movement and stop handling.
- `bridge_mode.py`: exclusive upstream ownership, TCP relay and discovery.
- `discover_modules.py`, `diagnostics.py`: module identification and native replies.
- `network_info.py`: portable interfaces, routing and optional neighbor hints.
- `endpoint_lock.py`: process-level endpoint exclusion on supported host platforms.
- `wifly_configure.py`, `setup_backend.py`: provisioning, validation and redaction.

Research references: [COSMOS 90GT](https://www.celestron.com/products/cosmos-90gt-wifi-telescope),
[WiFly command reference](https://ww1.microchip.com/downloads/en/DeviceDoc/50002230B.pdf),
[AUX protocol investigation](https://paquettefamily.ca/nexstar/NexStar_AUX_Commands_10.pdf).
The project is independent of Celestron and the control-app vendors.

## Maintainer notes

Each source module describes its role at the top of the file. Function docstrings
cover input validation, endpoint ownership, protocol framing, UI events, network
operations and shutdown responsibilities. Firmware comments distinguish virtual
motor behavior from future physical AUX transport. Tests explain their fixtures;
ordinary test commands do not connect to a real telescope.

Keep network I/O in its owning worker, send UI changes through the event queue,
and preserve command-mode exit and stop/drain cleanup when extending the code.
Do not log router secrets or treat an open TCP connection as proof of motor motion.

### AUX register diagnostics

The Diagnostics tab reports a bounded catalog of documented, read-only AUX
queries as well as native WiFly queries. Each AUX row identifies the destination
address and command ID, and retains the raw reply hex beside its interpretation.
Select a row to read the full response.

- Known node addresses: firmware identification (GET_VER 0xFE).
- Motor nodes 0x10/0x11: encoder counts and degrees, positive/negative backlash,
  autoguide percentage, slew-complete status, and GOTO approach direction.
- Optional GPS 0xB0: latitude/longitude with N/S/E/W, month/day, year, UTC time,
  time-valid and GPS-linked flags, satellite counts, and compass direction.
- Optional RTC 0xB2: month/day, year, and UTC time. This interface is documented
  for other Celestron models; its presence on COSMOS is unverified.
- WiFly clock configuration/status: `get time`, `show time`, and `show t t`.
  Older customized firmware may reject these commands.

A timeout does not prove a device is absent or a command unsupported. Unrecognized
or invalid replies retain raw hex without a guessed physical meaning. If the
connection fails, catalog entries show **NOT QUERIED**. Host observation time is
separate from device time. Encoder degrees are motor coordinates, not an aligned
celestial position; autoguide rate is not a tracking-enabled indicator. GPS values
must be considered alongside the reported validity flags.

This is a documented query catalog, not an exhaustive command/address scan.
Command IDs are destination-specific: GPS 0x04 reads the year, while motor 0x04
writes position. Diagnostic whitelists block motion, position, RTC, and firmware
writes. Diagnostic scans do not set time, synchronize SNTP, or change observing location. The separate explicit settings dialogs are described below.

Protocol reference: [NexStar AUX command observations](https://paquettefamily.ca/nexstar/NexStar_AUX_Commands_10.pdf).
Software decoding and read-only guards are tested; live COSMOS GPS/RTC support
remains unverified. No optional hardware capability is inferred from a catalog row.

See [diagnostic coverage and live results](docs/DIAGNOSTIC-COVERAGE.md) for the
unchecked, confirmation-guarded **Deep diagnostics** mode, supported readouts,
clock/site provenance, unknown response encodings, and explicit exclusions.


## Motor controls and settings update (2026-11-16)

Tabs are Motor control, Bridge, Diagnostics, then Wi-Fi provisioning.
Motor control releases its connection after **30 seconds without movement commands
by default**. Select 10, 20, 30 seconds or Off for the next connection. Telemetry
polling does not renew this idle period. Reconnect explicitly to continue. An
in-flight read and Stop cleanup can extend actual closure beyond the nominal
idle deadline. This is application sharing policy, not a verified WiFly lease.

With a valid `keymap` in the JSON profile, set **Keyboard control** to ON
(OFF at startup), then use the displayed keys while
the Motor tab is selected and focus is outside an input. Ctrl/Alt are not required:
Letters are displayed in uppercase to match keyboard labels. You do not need to hold Shift or turn on Caps Lock.

The example mapping uses **I** up, **J** left, **K** stop, **L** right, **M** down; **O** connect,
**P** disconnect. Release a held direction key to stop that movement. With the main program
window active, press the **Esc key** to stop both motors.

Both local references and explicit controller angle writes validate decimal degrees
when Set is pressed. **Azimuth: 0 to 360, no negative values** (100.52 or 060.84).
**Elevation: -90 to +90** (-60.31 or 060.84). Leading zeros and surrounding spaces
are accepted; valid entries normalize. Up to five decimal places are accepted.
Commas, units, scientific notation, nonfinite values, excess precision and
out-of-range values produce an error and send no setting. These are coordinate
input ranges, not verified mechanical travel limits. Azimuth 360 is equivalent
to 0. Encoder writes round to the nearest 24-bit count (~0.00002146 degrees).
Negative elevation uses the motor's circular encoder representation; the settings
editor converts readback above 180 degrees to a signed value for display.

Local references change only this application's display and clear on disconnect;
they do not align the telescope or write its encoder. The consolidated **Controller
Angle / Backlash Settings** dialog contains local reference and hardware modes,
reads current values, and offers deliberate
encoder-reference and positive/negative backlash (integer 0-99) writes. Disconnect
manual control and the bridge first. Writes require stationary encoder checks,
confirmation, acknowledgement and matching readback. A failed readback can mean a
setting changed without verification; read again before retrying. Encoder changes
invalidate previous alignment assumptions. Live reads of both motors succeeded;
**actual encoder and backlash writes have not been tested on the telescope**.

Diagnostics offers a time-server dialog with Cloudflare, Google and a numeric
server address, plus custom input. Test performs an SNTP query from this computer;
it does not prove the WiFly module can reach that server. Push requires a recent
successful test, resolves an IPv4 address, and selects disabled, once at startup,
or every 2-1440 minutes. Sync WiFly from time server now requests the configured server. Saving to flash
is optional and saves ALL current WiFly RAM settings. The telescope needs network
access to UDP 123. Timezone is displayed read-only: a supported setter for this
custom firmware has not been established. These controls affect the WiFly clock,
not telescope sky alignment. Server queries from Windows succeeded; **WiFly clock
writes and synchronization have not been live-tested**.

### Feedback-delay investigation and controlled failure

WiFly RN-171 2.40-CEL / motors 5.24 sometimes returned delayed or batched encoder
replies. Earlier code disconnected after one missed 1.2-second idle reply. Recorded
failures occurred at different elapsed times; `IdleTimer=0` was reported, so there
is no evidence of a built-in 30-second lease. Retrying individual axes still failed
when both replies arrived in a burst after an approximately five-second gap.

Idle recovery now disables movement, sends zero-rate Stops and retries complete
encoder pairs for a bounded recovery window. Persistent loss closes the connection
and reports a feedback timeout; idle expiration reports intentional release.
Neither path resumes motion automatically. Active-motion feedback loss retains
its separate stop path. A stationary 180-second live run recovered 20 delayed
feedback episodes with no disconnect errors, without requesting motion. This
establishes improved tolerance, **not the underlying transport root cause**.

Detailed evidence, timing limitations, stale-reply caveats and remaining work are
commented beside the recovery loop in `motor_control.py`. Remaining investigation:
correlate TCP and AUX serial captures with WiFly counters; compare direct and
infrastructure Wi-Fi and another host; distinguish RF loss, buffering, firmware
scheduling and client receive behavior. No undocumented adapter tuning was applied.

Diagnostics includes **Abort diagnostics**: stop new queries, exit WiFly command mode and close the connection, preserving completed results and marking unqueried endpoints. The current bounded query and cleanup may finish before cancellation completes.

Session events are automatically saved to disk, with a summary when the operation finishes. **Clear displayed log…** asks for confirmation and clears only the on-screen text; it does not delete saved session files. Open Logs opens the recorded session directory.

Known Position Reference displays polled encoder angles, proposed known coordinates, and their wrapped angular difference before setting a local reference. This is not a shared celestial alignment. No verified COSMOS endpoint for a universal sky-alignment model has been established; encoder writes must not be mistaken for one. The suspected lower mechanical elevation limit has not been verified.

## Development status and next steps

The [user guide](docs/USER-GUIDE.md) describes both-axis controller settings,
timestamped readouts, backlash deltas, local reference sessions and keyboard control.
Calibration profiles use the adapter MAC; an IP change requires a matching diagnostic
read before updating the saved address. See the [development roadmap](docs/DEVELOPMENT-ROADMAP.md)
for Raspberry Pi validation, the deferred companion API and experimental tracking.
Current automated checks do not establish untested hardware-write behavior.


Recent clock diagnostics: **Time / Time Server Settings…** now offers read-only
board settings/clock refresh and a UTC-based comparison with the computer clock,
including unset/missing-date and greater-than-one-day messages. PC-to-WiFly clock
copying remains disabled pending protocol verification. Session-scoped uptime
checks warn on possible adapter resets and clear active local references; they
cannot prove motor resets or distinguish undocumented uptime rollover. See the
[user guide](docs/USER-GUIDE.md) for limits and the
[future architecture plan](docs/ARCHITECTURE-PLAN.md) for ESP32 GPS/compass/RTC work.


Motor control shows the loaded profile name and its configuration filename,
`telescope-calibration.json`. **Profile file details…** shows the full
resolved path, format and schema version, with **Copy profile file details**. The Motor
control table copy also includes the profile and configuration path. The file
contains structured JSON, not a proprietary format; it holds device identity and
calibration evidence. Loading it does not push settings to the telescope. After
updating the file, click **Reload calibration**. If no usable profile is loaded,
the GUI identifies the expected filename rather than claiming calibration is active.


The JSON profile also supplies the optional keyboard `keymap`. If it is missing
or invalid, the shortcut list is blank and the Keyboard control rocker is disabled;
Esc remains the fixed stop key in the active main window. No default letter mapping
is silently installed. See the [user guide](docs/USER-GUIDE.md#editing-the-json-keyboard-map)
and [example JSON fragment](examples/keymap.example.json). The calibration script
preserves an existing keymap when replacing measurement data.

**Measured slew rates…** opens the rate table instead of displaying it permanently
on Motor control. It is disabled without usable measurements. The dialog provides
comma-separated CSV copying and tab-separated copying for direct Excel paste.
Connection feedback appears in a shaded **Connection status:** box. Copy buttons
identify their source, and the tab container fits the selected page. See the
[ESP32 resume document](docs/ESP32-RESUME.md) for the separate hardware plan and TODOs.

Wi-Fi provisioning uses **Infrastructure / Router Wi-Fi Settings** for new values.
**Connect & Read Settings** reads the stored SSID and network configuration without changing them; the **Settings read from telescope** panel shows the SSID in bold, separately from instructions and editable fields. Full replies appear in the Transfer log. Password fields are redacted before display and saving; provisioning logs do not provide password recovery. **Show password** reveals only entered text. Password recovery through other tools is unverified for RN-171 / 2.40-CEL.

For the original SkyQLink RN-171, use the physical slider **LEFT** for Direct/ad hoc: connect this computer to SkyQLink-xx and read at `1.2.3.4:2000`. Use **RIGHT** for Infrastructure: connect this computer to the telescope’s current network and discover its assigned IP. Power OFF before moving the slider, then power ON. The app’s mode selector does not move the switch or join Wi-Fi. Readback describes stored settings, not a sensed physical switch position.

Adapter-generation terminology: **Celestron Version 1 Wi-Fi — SkyQLink RN-171** uses `SkyQLink-xx`; **Version 2 and later Celestron Wi-Fi** use `Celestron-xxxx`. The current provisioning workflow and LEFT/RIGHT switch instructions apply only to the Version 1 RN-171 / 2.40-CEL. Future adapter support must provide model-specific connection and provisioning instructions; a network name alone does not verify device capabilities. Newer-adapter provisioning is not implemented by this wording change.

For direct/infrastructure addresses and the roles of TCP 2000, TCP 3000, UDP 55555 discovery and UDP 123 time synchronization, see the **Note — Wi-Fi addresses and ports** on Wi-Fi provisioning and the [user guide port reference](docs/USER-GUIDE.md#wi-fi-address-and-port-reference).

[^phone-hotspot]: Phone hotspot compatibility is unverified. The RN-171 accepted and saved iPhone Personal Hotspot settings, but association and reachable telescope control were not established, including after restarts. The cause (association/authentication, DHCP, or client isolation) is unresolved. Communication between hotspot clients, discovery, and control from the hotspot-hosting phone remain unverified; successful provisioning does not establish connectivity.

Application note: [KStars/INDI connection and manual eyepiece alignment](docs/KSTARS-BRIDGE-NOTE.md), with [measured results and versions](docs/engineering/2026-11-16-pi-kstars-validation.md). [Portable desktop start/stop guide](docs/TELESCOPE-CONTROL-START-HERE.md).


Bridge logs now show known AUX interpretations beside raw hex; unknowns remain
unknown. See the [user-guide appendix](docs/USER-GUIDE.md#technical-appendix-interpreting-external-application-traffic)
for captured SkySafari command findings, including commands without GUI controls.
[Local jogging through the bridge](docs/USER-GUIDE.md#local-jogging-while-control-bridge-is-on)
is OFF by default; supervised live coexistence testing remains pending.


Control Bridge does not disconnect control or management clients because they are
idle. Idle release applies only to the direct Motor control connection; local-jog
duration and feedback safeguards remain separate.


The **Control Bridge** tab offers **Poll and record motor positions**
(0.2–300 seconds; default 1, subsecond experimental) and optional **Keep connection alive (heartbeat)** (1–300 seconds; default 5). Both start OFF and are configured on Control Bridge. One scheduler reuses incoming replies and handles both options, including when no control app is connected. Local jogging shares it for required safety feedback; turn local jogging OFF when using only your external app.
See the [user guide](docs/USER-GUIDE.md#record-motor-positions-and-optional-idle-heartbeat)
and [CLI reference](docs/RUNTIME-OPTIONS.md#optional-bridge-background-reads-cli-and-gui).

**Export bridge recording…** saves Wi-Fi packets, measured encoder positions, or
both as CSV/JSON for offline analysis. See the [export instructions](docs/USER-GUIDE.md#export-packets-measured-positions-or-both).


Direct Motor control now exposes its existing idle position reads as **Keep
connection alive** (ON at 1 second by default; adjustable 1–300 seconds). **Idle
release** remains 30 seconds by default, with longer options and Never. Keep-alive
does not reset idle release. Both settings are disabled while connected or during
any bridge operation; see the [direct connection guide](docs/USER-GUIDE.md#direct-motor-connection-keep-alive-and-idle-release)
for ownership warnings and movement-safety behavior.


Control Bridge supports a control application on **this same computer** or on
**another device on the shared LAN segment**. Switch the bridge ON in this program;
configure the control application with the bridge's displayed address and port,
not the telescope's address. For another device, select this computer's adapter
on that shared LAN. For local-only use, explicitly bind the bridge to `127.0.0.1`
and use that address in the local control application. Localhost on another device
cannot reach this computer. See [connection instructions](docs/USER-GUIDE.md#control-bridge).


The Control Bridge tab always carries a status marker: **green** after startup
checks succeed, **red** when OFF, starting, stopping or faulted. It remains visible
while another tab is selected. The Motor control tab retains its **yellow** marker
while operating through the bridge. Green indicates bridge readiness, not proof
of alignment, tracking accuracy or uninterrupted motor feedback.


Discovery distinguishes this program's **software proxy** from physical WiFly
hardware. A recognized proxy is labeled **COSMOS software proxy — not a physical
module** and identified on its management port without opening its motor-control
connection. Selecting it leaves the hardware target unchanged; use the proxy
address in your control application. Unidentified AUX endpoints remain labeled
hardware-or-proxy unknown. See the [proxy identity protocol](docs/PROXY-DISCOVERY.md)
for fields, compatibility limits and future ESP32 integration considerations.


### Bridge-local jog feedback recovery

The Motor control tab's yellow bridge-jog panel has a **Local jog feedback timeout**
(default 2 seconds, range 1–10; click **Apply timeout**) and a red **Restart local
jogging** button while jogging is enabled. Missing feedback stops the local jog;
fresh readings from both axes sustained across a recovery window (at least one second) automatically unlock the
buttons without resuming movement. Restart switches local jogging OFF for one
second, then ON and waits for fresh feedback. It does not restart Control Bridge.
These settings do not affect direct Motor control or bridge polling intervals.
See [local bridge jogging](docs/USER-GUIDE.md#local-jogging-while-control-bridge-is-on).


Control Bridge's **Current polling source** readout explains which requests are
active without changing the selected settings. Motor control repeats the applied
heartbeat/polling values beside its direct-connection settings while bridge jogging
is ON. Encoder display freshness uses `max(10 seconds, active polling interval +
3 seconds)`; this does not relax the separate local-jog safety timeout. See the
[user guide](docs/USER-GUIDE.md#seeing-which-bridge-polling-settings-are-active).


The bridge's **Local-jog feedback polling interval** is adjustable from 0.2–5s
(default **0.4s**) with **Apply local-jog interval**. Keep it shorter than the
local-jog feedback timeout. Longer intervals reduce this source of query traffic;
external apps and other enabled polling can still request readings faster.
See [polling guidance](docs/USER-GUIDE.md#adjusting-local-jog-feedback-traffic).

Timed-jog choices now extend to **5 seconds** in direct and bridge-local control.
Bridge hold-to-move remains capped at 2 seconds per press; Stop and missing-feedback
safeguards remain active. The calibration-based degree estimator keeps its existing
0.1–2 second limit.


With Control Bridge OFF, direct Motor control uses **Poll motor positions (keep
connection alive)** to read encoders at the selected interval. Its status distinguishes
saved settings from an active session. Idle release still closes the connection;
retained values then show **NOT LIVE — disconnected**. Choose Never before connecting
only when persistent direct ownership is desired.
