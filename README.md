# Celestron Cosmos 90GT Telescope WiFi Control

**Legacy Celestron SkyQLink Wi-Fi setup, telescope control, and a SkySafari / SkyPortal bridge.**

[![Python checks](https://github.com/mjklopfer/celestron-cosmos-90gt-wifi-telescope-control/actions/workflows/checks.yml/badge.svg)](https://github.com/mjklopfer/celestron-cosmos-90gt-wifi-telescope-control/actions/workflows/checks.yml)

Have a **Celestron Cosmos 90GT WiFi telescope** with the original **SkyQLink /
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
[Bridge setup](#bridge-two-addresses-with-different-purposes) ·
[Phone hotspot limitations](#phone-hotspot-compatibility--unverified)

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

This project targets the **Celestron COSMOS 90GT WiFi telescope (model 22094)**
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

## Phone hotspot compatibility — unverified

Operation through a phone hotspot **may or may not work and has not yet been
verified**. In testing with an iPhone Personal Hotspot, the original RN-171
accepted, read back and saved the requested Wi-Fi settings, but a successful
hotspot association and a reachable telescope connection were not established.
Repeated telescope restarts did not establish connectivity, and no telescope
response was found on TCP port 2000 from a laptop connected to that hotspot.

This does not establish whether the cause was Wi-Fi association/authentication,
DHCP, or hotspot restrictions on local device communication. Communication
between hotspot clients, automatic discovery, and SkySafari running on the
hotspot-hosting iPhone remain unverified. Successful provisioning alone does
not prove the telescope joined the hotspot. The verified house-router and
computer-bridge arrangements should not be taken as verification of a phone
hotspot arrangement.

## Requirements

- Python **3.10 or newer**, with **Tkinter/Tcl-Tk** and a graphical desktop.
- `psutil` (installed automatically by pip). No manufacturer driver is required
  for ordinary TCP/IP telescope communication.
- A powered compatible mount and an IPv4 connection to its adapter, normally
  TCP **2000**. The application does not configure the computer's network joins.
- For infrastructure mode, computer, telescope and phone must have mutual local
  network access. Guest/client isolation can block discovery and connections.
- For a two-interface bridge, one interface reaches SkyQLink directly and another
  reaches the phone's LAN. Ethernet plus Wi-Fi has been verified on hardware.
- Only one application/session should own the original adapter connection.

Windows, Linux and macOS are intended hosts. Hardware operation was tested with
**macOS and Python 3.14**. Windows/Linux hardware operation has not yet been
verified. Automated tests use mock devices; they do not establish hardware
compatibility on another OS. CI checks are defined for Windows and Linux.

On some Linux installations, install the distribution's Tk package first
(for example `python3-tk` on Debian/Ubuntu). Linux GUI tests need an X display
or Xvfb. On Windows, use a Python distribution installed with Tcl/Tk support.
Check availability with `python -m tkinter`.

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
  provisioned. Enter its router-assigned IP or use **Discover modules on LAN**.
  `1.2.3.4` is not its house-network address. DHCP addresses can change.

Selecting a software mode changes guidance and connection settings. It does not
move the telescope slider or connect the computer to a different Wi-Fi network.

## Application tabs

1. **Motor control:** connect, verify both motor position replies, choose rate
   1–9, and use hold arrows or bounded timed jogs. Stop ends commanded movement.
   Displays include firmware, raw encoder counts, angles and relative changes.
   Encoder angles are mechanical positions, not an independently aligned celestial
   solution. Use the scope/app's alignment procedure for sky pointing.
2. **Diagnostics:** displays actual adapter query data, replies, timeouts and
   controller details. A responding RN-171 can be listed even when motors do not
   answer; adapter detection alone does not prove motor connectivity.
3. **Bridge:** relays native AUX traffic to a compatible phone/desktop control app.
   Defaults OFF. While ON, the other control tabs are disabled and readbacks/logs
   remain visible. The controlling application can command real telescope motion.
4. **Wi-Fi provisioning:** Connect & Read Settings displays replies in the
   **Transfer log below the tabs**, not a popup, and saves a report. Read settings or replace the router SSID, password and
   supported security settings. Supports an already provisioned adapter through
   its reachable infrastructure address as well as direct mode. Saving replaces
   network configuration; power OFF, set the physical slider RIGHT, and power ON
   to join the saved router. Discover the newly assigned IP afterward.

The selected connection mode controls discovery: **Direct / ad hoc** checks only
`1.2.3.4:2000` on the telescope Wi-Fi; **Infrastructure / house Wi-Fi** scans
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

**Telescope IP** is the upstream destination. **Computer LAN IP** is the local
listening address the phone/control app connects to. Selecting a computer-interface
row chooses that listening IP; it does not choose or join a Wi-Fi network.

For one shared infrastructure LAN, use the computer's IP reachable from the phone.
A blank Computer LAN IP lets the OS-selected route to the telescope supply a source
address; select an explicit IP on multi-interface systems when that is ambiguous.

For **Two interfaces**, an explicit shared-network computer IP is required:

1. Connect computer Wi-Fi to the telescope's direct SkyQLink network, with the
   mount's physical switch LEFT. Keep Ethernet (or another interface) on the router.
2. Keep the phone on router Wi-Fi. Enter telescope destination **1.2.3.4:2000**.
3. Check **Two interfaces**. Select the computer's **router/Ethernet IP** in the
   interface table, or type it into Computer LAN IP. Do not choose its SkyQLink IP.
4. Switch Bridge ON. In the control application choose Celestron Wi-Fi / Access
   Point mode, using the displayed **computer** IP and TCP 2000 if fields exist.

Example topology using illustrative addresses:

```text
phone (router Wi-Fi) -> computer Ethernet 192.168.50.20:2000
                    -> computer SkyQLink Wi-Fi 1.2.3.10 -> telescope 1.2.3.4:2000
```

This is an application proxy; OS Internet Sharing, NAT and router port forwarding
are unnecessary. One hardware test verified Ethernet plus direct telescope Wi-Fi
and a SkySafari phone session. Two separate Wi-Fi radios have not been tested.

Allow this Python application incoming **TCP 2000 and 3000** from the phone's local
network and outgoing broadcast **UDP 55555**. Give the phone app Local Network
permission where required. A listening socket does not prove firewall access.
Do not expose these listeners through Internet port forwarding.

## Errors and recovery

If a connection fails, disconnect any other controlling applications, such as
SkySafari, SkyPortal or CPWI. Check the telescope destination, computer listening
IP and physical network joins. A telescope power-cycle may be needed after a lost
connection; it is not a guaranteed cure.

Idle encoder polling tolerates isolated missing replies. Three consecutive missed
polls for either axis close the bridge; TCP failure still fails immediately.
This change is mock-tested and awaits further hardware endurance testing. Earlier
hardware sessions showed intermittent idle reply delays; connection reliability
must not be inferred from one successful session. The bridge does not inject
position polls while a control client owns the connection. Client loss or 15
seconds without incoming client traffic triggers Stop attempts. Stop delivery
cannot be guaranteed after transport/power loss; inspect the readback and mount.

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
