# Celestron Cosmos 90GT Telescope WiFi Control

A portable Python/Tk application for the **Celestron Cosmos 90GT telescope with
a Version 1 Celestron WiFi module** (the original SkyQLink RN-171 / WiFly adapter).
This project targets **Version 1 Celestron WiFi modules**; support for later
module generations is not established.

**Hardware scope:** the original Version 1 **WiFly RN-171 Wi-Fi modules**,
including the SkyQLink interface in the Cosmos 90GT. RN-171 is a Wi-Fi module,
not a Bluetooth (BT) adapter; Bluetooth telescope interfaces are not supported. It provides manual motor control,
encoder readback, module discovery, diagnostics, Wi-Fi provisioning and a LAN
bridge for compatible telescope applications. SkySafari is a tested example.

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
