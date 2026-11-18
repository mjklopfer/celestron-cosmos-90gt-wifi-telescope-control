# User guide: Celestron Cosmos 90GT Telescope Wi-Fi Control

This application configures and controls the original **Celestron Wi-Fi Control
Version 1 - SkyQLink RN-171** adapter. It also provides a bridge for compatible
astronomy software. It is not a planetarium or a complete celestial alignment
system. The four tabs are **Motor control**, **Control Bridge**, **Diagnostics**,
and **Wi-Fi provisioning**.

## Install, start and resize

Follow [README installation](../README.md#install-and-run). Source installations
require Python 3.10 or newer, Tkinter and the project dependencies. In your active
virtual environment, run:

```console
python -m pip install -e .
python -m skyqlink_setup --zoom-controls
```

The optional View menu provides zoom, reset to 100%, and Fit width. Scrollbars
allow access to controls on small displays. The default size remains available
without the switch. Raspberry Pi installation, Python/SSL problems on Buster,
and a desktop shortcut are covered in the [Pi desktop guide](RASPBERRY-PI-DESKTOP.md).
Earlier platform checks covered Windows 11, macOS and Raspberry Pi OS; the latest
GUI changes have not been rechecked on every platform. See [validation](VALIDATION.md).

## macOS display and resizing

The Mac layout activates automatically through Tk's Aqua window system. Use
the same installation and launch commands as on Windows or Linux. On macOS:

- The tab bar uses native system styling and is centered within the form.
- **Discover SkyQLink / Celestron Modules** appears on a separate row below the
  direct/infrastructure choices. The shorter **Infrastructure / shared router
  Wi-Fi** label still means the telescope and computer share a router network.
- The Diagnostics toolbar spans two rows. This keeps the form within a normal
  laptop window and prevents the port, password controls and tab bar from being
  displaced off the visible right edge by the hidden Diagnostics page.
- Explanatory labels use the native text color for readability in the tested
  dark appearance. The bridge's light status panel uses dark text explicitly.
- When zoom controls are enabled, diagnostic table rows reserve enough height
  for their text. Use **View → Fit width** if your window is narrower; scrollbars
  remain available at large zoom or small window sizes.

No OS-specific setup is needed, and these display changes do not change the
connection, physical-switch instructions, motor commands or provisioning steps.
Windows and Linux keep their existing tab colors and toolbar arrangement.
Restart an already-open application after updating its source to load the new
layout. The user confirmed improved Mac rendering after the November 16, 2026
relaunch; this appearance review does not repeat telescope hardware tests.
See [Mac appearance notes](MACOS-APPEARANCE.md) and [validation](VALIDATION.md).

## Complete runtime-switch reference

See [every launch option, default, usage case and limitation](RUNTIME-OPTIONS.md) for the GUI, bridge, calibration, MCP environment and shipped diagnostic/verification commands. It also distinguishes on-screen switches from command-line flags and lists the Pi desktop launch actions.

## Connect to the telescope

Only one connection may own the telescope interface at a time. Control Bridge can mediate local jogging with one external control application, as described below. **Disconnect** means clicking the Disconnect button on the Motor control tab to release this application’s connection; it does not mean unplugging motor cables or turning off telescope power. For the bridge, switch Control Bridge OFF. Wait for an active operation to finish before starting another. Disconnect phone
apps, other desktop controllers and this application's bridge before manual
motor control, diagnostics or settings work.

**Telescope Wi-Fi interface IP address** identifies the telescope, not this computer. The normal
port is 2000. Choose the connection mode matching the telescope and computer:

| Mode | Telescope switch / computer connection | Telescope address |
| --- | --- | --- |
| Direct / ad hoc | Switch LEFT; computer joins SkyQLink-xx | Normally 1.2.3.4 |
| Infrastructure | Switch RIGHT; telescope and computer reach a common access point/network | Address assigned by that network |

The mode selector changes application settings. It does not move the physical
switch or connect the computer to a Wi-Fi network. Power off before changing the
telescope switch. Use **Discover SkyQLink / Celestron Modules** to find responding modules on
the selected connection, then select a result. An infrastructure address may
change after a restart. Discovery checks protocol replies; it does not move the
telescope or change its settings.

## Motor control

1. Check that the telescope and cables have clearance. Click **Connect Motors**.
2. Wait for verified position replies from both motors. A network connection
   alone does not enable movement.
3. Select a speed (1–9). Use **Hold to move** or **Timed jog**. In hold mode,
   release the arrow to stop. A timed jog runs for its selected duration.
4. Click **STOP**, or press the **Esc key** while the main program window is active, to stop both motors. **Disconnect** stops and releases the connection.

Azimuth means horizontal rotation; elevation means up/down. Encoder counts are
the motor's raw position counter. Encoder angles convert that counter to degrees;
they do not show the telescope's aligned sky-pointing azimuth/elevation or the
coordinates of a celestial object. Position age indicates how recently feedback arrived. Jog readouts
show before/after counts, measured angular change and the stop check.

**Idle release**, under **Direct motor connection settings**, offers Never,
10/20/30 seconds or 1/2/5 minutes. The default
is 30 seconds without movement activity. This automatic connection release
prevents an unused direct session from occupying the adapter indefinitely so another
application can connect. Keep-alive traffic does not reset it. Reconnect to move again. This is application policy,
not a proven timer inside the telescope. Missing feedback is a different fault:
movement is disabled during recovery, Stop is attempted, and persistent failure
closes the connection. Do not treat delayed position data as current.

### Keyboard control

Keyboard shortcuts are loaded from the `keymap` object in the active JSON profile.
With a valid keymap loaded, set **Keyboard control** to ON beneath Idle release.
It starts OFF on launch. A missing, empty or invalid keymap clears the shortcut
list and disables the switch; the nearby status message explains why.
Enabling it places keyboard focus in the motor panel. The application must be
the active window with the Motor control tab selected.

Letters are displayed in uppercase to match keyboard labels. You do not need to hold Shift or turn on Caps Lock.

The example keymap uses the following letters; the on-screen list reflects your
actual profile rather than fixed program shortcuts.

| Key | Action |
| --- | --- |
| I / M | Elevation up / down |
| J / L | Azimuth left / right |
| K | Stop |
| O | Connect to the motors |
| P | Stop and disconnect from the motors |
| Esc key | Stop both motors while the main program window is active, even when Keyboard control is OFF |

Letters typed into an entry field, dropdown or log do not operate the motors.
After editing, click the motor panel to restore focus. Release a held direction
key to stop; switching keyboard control OFF stops held motion. Changing tabs or
leaving the application also stops held keyboard movement. Direction keys cannot
move anything until valid motor feedback enables the controls. The selected
Hold/Timed jog mode applies to keyboard directions as well.

### Position reference and controller settings

Open **Controller Angle / Backlash Settings…**. This contains both former
reference controls and the hardware settings; choose the intended mode:

- **Local reference (this app only):** connect motors, point at a known object,
  and enter that object's current azimuth/elevation. Current readings and the
  proposed coordinate offset are displayed before setting the reference. This
  changes this application's displayed coordinates only; it clears on disconnect.
- **Telescope controller:** disconnect manual motor control and the bridge,
  both Azimuth and Elevation are visible together. Each axis has its own **Current values from telescope** panel and **Read current values** button. The timestamp identifies the completed read; editable fields below are the proposed new settings, not live telemetry. An encoder-angle write changes that
  motor's coordinate origin, not its physical direction. Backlash entries are
  positive/negative compensation values, integers 0–99. Writes require stationary
  checks, explicit confirmation, acknowledgement and matching readback.

Other applications can observe hardware encoder/backlash changes, but those
changes do not create shared celestial alignment. They can invalidate existing
alignment assumptions. Local reference is also not a full multi-star sky model. Local offsets clear on disconnect or lost feedback; inactive applied-offset history is retained until the app closes. **Poll Azimuth/Elevation now** waits for the next sample from the existing motor polling loop. **Clear local references** resets only local offsets. Explicit reapply requires fresh feedback and confirmation that the telescope has not been power-cycled, moved manually or realigned. A connection loss cannot reliably identify a power cycle.
Actual encoder/backlash writes remain unverified on this telescope; readback has
been exercised. If a write reports uncertain verification, read again before
retrying—it may already have changed the setting.

Angle entries accept azimuth **0–360 degrees** (360 equals 0), and elevation
**-90 to +90 degrees**. Examples: `100.52`, `060.84`, `-60.31` (elevation only).
Leading zeros and surrounding spaces normalize. Up to five decimal places are
accepted. Units, commas, scientific notation, excessive precision, nonfinite or
out-of-range values produce an error before sending a setting. Writes round to
the nearest encoder count. These are coordinate ranges, not mechanical limits;
the suspected approximately -10-degree lower stop is not verified.

### Backlash editing and retained changes

Each controller axis has absolute positive-direction and negative-direction
backlash fields. Both accept **0–99 whole-number controller units, not degrees**.
The direction labels do not permit negative absolute values. Spaces, leading
zeros and integral decimals normalize (`002.0` becomes `2`); fractions such as
`0.2`, negative absolute values, and out-of-range entries are rejected.

To adjust by a delta, read that axis within 60 seconds, enter signed whole-number
deltas, and select **Preview / apply backlash delta…**. The confirmation shows
current + delta = proposed value for each direction. For example, 10 - 2 = 8.
A result outside 0–99 is rejected. Before writing, the backend reads the source
values again and aborts if they changed. Reads and edits are separate actions.

**Last applied change** retains the confirmed request and verification status;
subsequent reads do not overwrite it. A partial/uncertain write is labeled as such.
The local reference panel separately retains the encoder reading, known position,
applied offset and timestamp, rather than changing its history as the scope moves.
No hardware-default reset is provided: zeros are not assumed to be factory defaults.

Celestron documents 0–99 backlash settings in its
[mount manual](https://celestron-site-support-files.s3.us-east-1.amazonaws.com/support_files/11068-11069_6SE-8SE_Manual_5lang_2023-Web.pdf).
This supports the UI range; actual COSMOS writes and persistence still require
hardware validation. Angle entries over five decimals currently reject with an
explanation. A user-confirmed rounding offer remains future work.

### Speed table and estimated degree jog

The table displays measured pulse-average degrees/second separately for each
axis, speed and direction, when a matching calibration configuration is present.
Use **Reload calibration** after generating a new file. **Estimate degree jog…**
converts the requested relative angle into a timed jog using the matching sample.
It sets direction-related duration guidance and the timed-jog duration; it does
not move the telescope. Press the appropriate direction to execute the jog.

The estimate accepts only durations in the supported 0.1–2 second range. Ramps,
backlash and network delays affect accuracy. It is not an exact relative-angle
GOTO or a continuous tracking-rate calibration. Inspect actual encoder movement
afterward. A missing or different-endpoint profile cannot supply a reliable estimate.

## Control Bridge

This feature allows your local computer to create a proxy link between the
SkyQLink telescope and control software that uses modern Celestron Wi-Fi
connectivity/protocol. It relays commands and replies for one control application at a
time. The control application remains responsible for alignment and tracking.

There are two different addresses:

| GUI term | What it identifies |
| --- | --- |
| Telescope Wi-Fi interface IP address, at the top | The SkyQLink module that this computer connects to |
| This computer’s IP on the control-device network | The local adapter address on the network used by your astronomy app; not a MAC address or the telescope’s IP |

The first on-screen connection step follows the selected mode:

- **Direct / ad hoc:** join the telescope's SkyQLink network with this computer's
  telescope-facing Wi-Fi adapter; use `1.2.3.4:2000`. Follow Two Interface Mode for
  a control device on a separate shared LAN.
- **Infrastructure:** join the access point/LAN shared with the telescope. If your
  control application runs on another computer, tablet or phone, put that device
  on the same shared LAN. No separate control device is needed when the control
  application runs here. Enter/discover the telescope's assigned IP at the top.

Then choose where
your control application runs (e.g., SkySafari, CPWI, KStars/INDI, etc.):

- **On this computer:** no other computer is needed. Use the bridge address shown
  after startup. For local-only access, type `127.0.0.1` into the bridge IP box
  before starting, then configure the control app with `127.0.0.1` and port 2000.
  A bridge bound only to its LAN address does not also listen on localhost.
- **On another computer, tablet or phone:** join that device and this computer to
  the same shared LAN segment. In Local System Network Interfaces select this
  computer's adapter on that LAN, or enter its IPv4 address in the bridge IP box.
  Do not enter the other device's IP. The network must permit communication
  between devices. With two interfaces, this is the control-device LAN; the
  telescope-facing link is separate. This program relays telescope traffic,
  not general network bridging or Internet sharing.

Before starting, click **Disconnect** on Motor control if connected. Check that
all requested diagnostics, discovery, recovery and settings operations have finished.

Switch **Control Bridge ON in this program on this computer**. Wait for Bridge ON
and its address/port readback. No bridge needs to run on the other device. Configure
your control application's compatible Celestron Wi-Fi/AUX network connection with
that displayed bridge address and TCP port (normally 2000), not the telescope's IP.
In the tested SkySafari configuration, select Celestron WiFi and Access Point mode;
other applications have their own driver/settings menus. `localhost` always refers
to the device running the control application, so never use it from another device
to reach this computer. **Refresh Adapter IPs** only refreshes the adapter list.

The bridge also provides discovery on UDP 55555 and limited management on TCP
3000. Allow local-network firewall access; opening a local port does not prove
that another device can reach it.

### Local jogging while Control Bridge is ON

The Motor control tab remains available with an amber marker and a warning panel.
Local jogging starts **OFF**. With clear travel and the external app no longer
slewing, turn **Enable local jogging through bridge** ON and confirm the warning.
This attempts Stop, then waits for fresh position replies from both axes.
Use the arrow buttons or the configured keyboard controls; keyboard control must
also be ON. Hold-to-move stops on release and is capped at **2 seconds per press**;
timed jogs accept **0.1–2 seconds**. O/P do not open or close a second motor connection
while the bridge is active. Controller angle/backlash settings remain unavailable.

**External commands have priority.** A conflicting external command first cancels
the local jog and attempts Stop, then passes through to the telescope. Position
reads continue normally. Unknown commands also interrupt local jogging rather
than being assumed harmless. If tracking updates repeatedly interrupt your jog,
pause tracking in your control application before trying again. Stop here does not
block future movement requested by the external app. The bridge never replays an
old local jog or pretends an external command succeeded.

Turn the local-jog switch OFF when finished; this attempts Stop and leaves the
external application connected. Switch Control Bridge OFF to close the telescope
connection. Lost feedback locks local jogging; inspect the telescope before
switching local jogging OFF and ON again. Network failure can prevent Stop from
reaching the mount. Live coexistence with SkySafari remains pending validation.

### Direct/ad hoc: why Control Bridge is disabled

When **Direct / ad hoc** is selected, Control Bridge cannot start until **Two
Interface Mode** is checked. A notice beside the disabled switch explains this
and tells you what to do. Checking the box does not create network connections:
configure both adapters in the operating system first, then select the correct
IPv4 address in the program.

1. Connect one compatible Wi-Fi adapter on this computer to the telescope's
   SkyQLink network. Use the telescope address `1.2.3.4`, TCP port `2000`.
2. Connect a second adapter to the network used by your astronomy app. Choose
   one arrangement from the table below.
3. Check **Two Interface Mode**. In **Local System Network Interfaces**, select
   this computer's adapter on the astronomy app's network. Its IPv4 address fills
   **This computer’s IP on the control-device network**. An address is required;
   do not select the adapter connected to SkyQLink.
4. Switch **Control Bridge ON**. In the astronomy app select Celestron WiFi /
   Access Point mode. If asked, enter this computer's displayed IPv4 address and
   TCP port. The app connects to this computer, which forwards commands to SkyQLink.

| Second adapter on this computer | How the control device connects |
| --- | --- |
| Ethernet to a router/access point | Phone/tablet uses that router's Wi-Fi; another computer can use Ethernet or Wi-Fi |
| Ethernet directly to a control device | Both ends need compatible IP/subnet settings configured outside this program |
| Second Wi-Fi adapter joining a router/hotspot | Phone/tablet joins the same network; local device-to-device communication must be permitted |
| Second Wi-Fi adapter providing a hotspot | Control device joins that hotspot; adapter/OS must support hosting it and be configured outside this program |

A phone or tablet does **not** require two Wi-Fi adapters in this computer when
Ethernet connects the computer to the phone's access-point network. Two Wi-Fi
adapters are an alternative when no suitable Ethernet path is available. The
SkyQLink-facing adapter must support its legacy ad hoc network; do not assume any
modern Wi-Fi adapter supports it.

Router/hotspot guest or client isolation must not block the astronomy app from
reaching this computer. Configure local firewall access for TCP 2000/3000 and
UDP discovery as described above. Networks should use non-overlapping subnets.

Internet access is not required for telescope control. This application proxies
commands; it does not join/merge network segments, enable OS network bridging,
create hotspots, configure DHCP, or provide routing/NAT. If you also want Internet
sharing from a third interface, configure that separately in your operating system
or router. Such setup is outside this application and is not required for the
basic telescope bridge. A third interface is an optional design, not a requirement.

Ethernet plus SkyQLink Wi-Fi has earlier hardware evidence; two-Wi-Fi, hosted-hotspot
and direct-Ethernet arrangements are described options, not newly tested setups.


ON reserves the telescope connection and disables Diagnostics and Wi-Fi provisioning.
Motor control remains available for optional mediated local jogging; its controller
settings are unavailable while the bridge owns the connection. OFF attempts Stop
on both motors and closes the bridge; consult acknowledgements in the log.
Reported positions use incoming replies. Optional polling and keep-alive controls
on Control Bridge can request missing samples, and local jogging requires safety
feedback through the same scheduler. See [recording and polling controls](#record-motor-positions-and-optional-idle-heartbeat).

SkySafari use has been tested in documented configurations. This is selected
discovery/management emulation, not a full modern-module replacement. Compatibility
with other applications and long-duration reliability remain unverified. If your
application already connects directly to the telescope, the bridge is unnecessary.
See [bridge details](../BRIDGE-MODE.md).

## Diagnostics and time settings

Disconnect motors/bridge and other controllers, then select **Run read-only
diagnostics**. Select a result row to inspect raw hex and the known interpretation.
Unknown replies remain unknown. A queried address does not prove that a focuser,
light, GPS or RTC is physically present. Missing optional devices can time out.
Available WiFly clock state, uptime/counters, timezone, time-server settings,
and responding AUX readings are reported; unset time is not a valid calendar date.

**Deep Diagnostics Read** starts unchecked and requires a warning confirmation. It
adds allowlisted reads that can be more intrusive to the shared connection; it
does not brute-force every command number. **Abort diagnostics** stops new
queries and retains completed results. The active bounded query and connection
cleanup can take time to finish. Coverage is described in [Diagnostic coverage](DIAGNOSTIC-COVERAGE.md).

**Time / Time Server Settings…** can test a common or custom server from this computer
and request that the WiFly module use its IPv4 address. Choose disabled, once at
startup, or every 2–1440 minutes; Sync WiFly from time server now requests an immediate synchronization.
A recent successful computer test is required before pushing a new server.
The telescope itself also needs a route to that server over UDP 123; a successful
computer test does not prove this. Saving to flash is optional and saves ALL
current WiFly RAM settings. Timezone is read-only because a supported setter on
2.40-CEL has not been established. Module time synchronization and writes remain
unverified on the telescope. These settings do not give the motor controller a
celestial alignment or enable autonomous sky tracking. No verified general CPU
site-location/time write endpoint is claimed.

## Logs and connection troubleshooting

Session events are saved under `~/.cosmos90gt/logs` by default, with a summary
when an operation finishes. `COSMOS90GT_DATA_DIR` can select another data directory.
**Open Saved Logs** opens the current recorded session. **Clear displayed log…**
asks for confirmation and clears only on-screen text, not saved files.
Review logs before sharing: redaction is not a reason to publish private network data.

Below the log, **Allow one Wi-Fi module restart if Connect Motors fails** permits
a single recovery attempt after initial motor verification fails. This is enabled
by default. Use it if you click **Connect Motors** but the program receives no valid response
from one or both motors. Leave telescope power on and disconnect other controlling
apps before retrying. It identifies the legacy
RN-171/2.40-CEL module, reboots it, checks both motor positions and retries the
connection if those checks succeed. It retains saved Wi-Fi settings; unsaved RAM
settings can be lost. It is not a factory reset or motion command. DHCP may assign
a new address; rediscover if the previous address stops responding. Uncheck it
to prevent automatic restart. A manual restart/recheck is also in Diagnostics.

| Symptom | Action |
| --- | --- |
| Intentional idle release | Reconnect; select a different idle period before the next connection |
| Missing motor feedback | Stop using movement controls; check power, other controllers and network; read the log |
| Keys do nothing | Set Keyboard control to ON, select Motor control, click the motor panel, verify connection before direction keys |
| Module not discovered | Match switch/mode/network; check DHCP address and firewall/client isolation |
| Bridge ON but app cannot connect | Use the computer's control app connection address, not the telescope IP; check firewall/profile |
| Settings write has uncertain readback | Read current values before retrying |

The feedback-delay root cause is unresolved. Retrying idle feedback improved
tolerance in a recorded stationary run; this does not prove a built-in 30-second
hardware timeout or reliable unattended control.

### Bridge works only after connecting Motor control first

Connecting Motor control first is **not a required setup step**. Control Bridge
performs its own motor startup checks. Direct Motor control and the bridge cannot
own the telescope connection simultaneously: switch Control Bridge OFF before
connecting Motor control, then click Disconnect on Motor control before restarting
the bridge. Also disconnect any other application connected directly to the adapter.

If that sequence appears to restore operation, it may reflect temporary recovery
from missing motor replies or closing/reopening the connection; coincidence has
not been ruled out. It does not prove Motor control initialized a missing alignment
or required telescope setting. Do not treat it as a guaranteed workaround.

If it recurs, stop jogging and check the telescope is stationary. Preserve the
bridge and direct-motor logs, and note the times and order of actions so startup
replies, timeouts and disconnects can be compared. Verify the telescope address,
power and network access before reconnecting. A successful startup check does not
guarantee uninterrupted feedback afterward.

## Generate the telescope configuration

`calibrate_telescope.py` is a standalone utility, not a GUI wizard. Its module
docstring and `--help` describe the operation. Run it with the same Python
environment as the application. Replace the example IP with your telescope's
current address and disconnect other controllers first.

Read current settings without requesting movement:

```console
python calibrate_telescope.py --host 192.168.1.231 --snapshot
```

This saves available settings such as backlash, positions and time-server
configuration, with raw replies and interpretations. `--deep` adds the diagnostic
allowlist. A current snapshot is **not factory defaults**. Only if you have
manually reset the device and intend to record that state, add
`--device-reset-confirmed`; it labels the snapshot as user-declared reset state,
does not reset anything and does not independently verify factory defaults.

To measure speeds, supervise the mount with at least 5 degrees of clear travel
in both directions on both axes, including cables, and run:

```console
python calibrate_telescope.py --host 192.168.1.231 --move --clearance-deg 5
```

**This command physically moves the telescope.** It uses positive/negative pulses
at rates 1–9, one axis at a time, at most one second each. It checks encoder
movement and Stop, aborts on uncertainty, and saves partial evidence. No automatic
return-to-origin follows a failure. Ctrl+C requests cleanup/Stop, whose delivery
can fail if the connection is lost. Maintain physical clearance and supervision.

Default output: `~/.cosmos90gt/telescope-calibration.json`. `--config PATH`
chooses a different file. Writes are atomic, retain a `.previous` backup, and keep
baseline history. A snapshot preserves rate samples. A movement run or
`--import-report FILE.json` replaces the current calibration with the new report's
valid samples and preserves the previous calibration/history. Profiles identify the WiFly adapter by its full MAC address, not its changing IP.
After DHCP changes the address, run Diagnostics or `--snapshot` at the new
address to verify the same MAC and update the saved address. A different MAC
is rejected. Older profiles migrate an identity only from a recorded successful
`get mac` reply; an SSID suffix is never used as a unique key. The MAC identifies
the adapter, not a mount serial number: recalibrate if the adapter moves to another
mount. Do not apply one telescope's measurements to another.

The GUI reads the default configuration for its speed table and estimated jogs;
if you used a custom path, place the reviewed profile at the configured data
directory's default filename to use it in the GUI. The configuration records
observed values; it is not an automatic restoration script. No snapshot is pushed
back to the telescope automatically.

## Optional automation

The [MCP interface](MCP-CONTROL.md) exposes backend operations without screen
automation. The [tracking plan](TRACKING-DESIGN.md) separates implemented simulation
and experimental native control from future Orbitron/TLE/launch producers.
Native streaming is unverified on this device and disabled by default. Do not
interpret this interface as a completed ISS or rocket tracker.

Each copy button names its source: **Copy status message**, **Copy motor table**,
**Copy diagnostics table**, **Copy selected reply**, **Copy network adapter table**,
and **Copy transfer log**, for example. Table copies contain headings and quoted
tab-separated cells for direct Excel paste. Free-form messages/logs remain plain
text. Copying neither clears the display nor includes hidden password fields.

**Clock semantics:** Test from this computer queries the selected server; it does
not set either clock. Sync WiFly from time server now asks WiFly to synchronize with its configured
SNTP server, not the PC clock. The server timestamp includes date and time; the
RTC is UTC-based Unix seconds. The application does not add a timezone offset.
WiFly documents Zone=7 as UTC-7 for its displayed clock, not an automatic daylight-
saving rule. Calendar UTC is derived from RTC; raw Time text is kept separate.
Custom 2.40-CEL display/synchronization behavior still requires live verification.
See [WiFly manual, section 3.11](https://ww1.microchip.com/downloads/en/DeviceDoc/50002230B.pdf).

Button naming: a trailing ellipsis (**…**) means another dialog or confirmation
opens before the action is completed. Immediate actions such as Read current
values, Disconnect, STOP and Copy to Clipboard have no ellipsis.


### Read current WiFly settings and compare clocks

In **Diagnostics > Time / Time Server Settings…**, click **Read current board
settings and clock**. Disconnect Motor control and turn Control Bridge off first;
leave telescope power on. This reads settings without writing or requesting sync.
The scrollable snapshot shows the board's server, mode, zone, reported time,
uptime, restart/wake counts and RTC/RAW counters, followed by PC local/UTC time,
WiFly UTC and the same timestamp in the PC's local timezone. **Copy clock/settings table**
includes this readback. Refresh explicitly; this is not a continuously ticking clock.

The difference is WiFly minus PC time, calculated from RTC Unix seconds in UTC.
No zone correction is applied twice. An unset clock, missing date or invalid RTC
gets an explanatory message instead of an invented date. Differences exceeding
24 hours are flagged. This is an approximate comparison, including network delay
and one-second clock resolution; it does not establish that the PC clock is correct.

**Sync WiFly from time server now…** asks the module to fetch its configured
server. **Set WiFly clock from this computer…** is visibly disabled pending
verification of the custom firmware's clock-write command. PC clock copying is
not implemented; neither existing action changes the computer clock.

Uptime observations from diagnostics and this dialog are compared within the
current app session for the same adapter MAC. A falling uptime or changed restart
count clears active local references and warns in Motor control and the log;
time-dialog readbacks also show the result. History remains inactive. This is
possible adapter-reset evidence, not proof of motor-controller power loss.
Rollover cannot yet be distinguished reliably on this firmware. No additional
WiFly polling interrupts motor traffic; no warning can occur without a new sample.

### Planned SkySafari time/location investigation

The vendor says time/location are always sent with Celestron Wi-Fi connections,
but this does not identify a WiFly clock-write command. Capture a controlled
connect through Control Bridge and compare fresh WiFly reads before and after.
Bridge logs already retain valid AUX frames in both directions, with source,
destination and command bytes available in the raw packet. Non-AUX traffic is
not retained as a complete byte capture; absence from these logs is not proof
that nothing was sent. Distinguish requests, matching replies and persistent
readback. Keep other controllers disconnected and do not align or slew during
this observation. Full sanitized transport capture remains an investigation task.


Motor control shows the loaded profile name and its configuration filename,
`telescope-calibration.json`. **Profile file details…** shows the full
resolved path, format and schema version, with **Copy profile file details**. The Motor
control table copy also includes the profile and configuration path. The file
contains structured JSON, not a proprietary format; it holds device identity and
calibration evidence. Loading it does not push settings to the telescope. After
updating the file, click **Reload calibration**. If no usable profile is loaded,
the GUI identifies the expected filename rather than claiming calibration is active.


### Editing the JSON keyboard map

Merge this object into the existing profile without replacing its other fields:

```json
"keymap": {
  "elevation_up": "i",
  "elevation_down": "m",
  "azimuth_left": "j",
  "azimuth_right": "l",
  "stop": "k",
  "connect": "o",
  "disconnect": "p"
}
```

All seven actions must be present. Each uses a distinct single letter A–Z; case is
normalized. Missing actions, duplicate letters or unsupported keys disable the
optional keyboard controls. No hardcoded letter-key fallback is applied. The
[example JSON fragment](../examples/keymap.example.json) is not a complete telescope
profile. **Reload calibration** reloads both calibration and keymap, stops active
keyboard control and returns the rocker to OFF. Calibration updates preserve an
existing keymap. The **Esc key** remains a fixed Stop control while the main window
is active, independent of the profile. Removing the keymap does not remove Esc.

### Measured slew rates and clearer status displays

The main Motor control page no longer embeds the nine-row rate table. Click
**Measured slew rates…** to inspect it. The button is disabled without usable
profile measurements; partial datasets show blank cells for missing measurements.
The dialog identifies the source profile and shows speed plus four separate
columns: azimuth positive/negative and elevation positive/negative, in degrees
per second. These are measured pulse averages, not guaranteed tracking speeds.
**Copy CSV to Clipboard** uses commas and CSV quoting. **Copy table for Excel**
uses tabs for direct spreadsheet paste. Neither operation commands motion.
Reloading calibration closes an old rate dialog so it cannot appear current.

The shaded **Connection status:** box beside Connect Motors/Disconnect contains
feedback, not a button. **Current operation status** above the transfer log is a
separate labeled message area; **Copy status message** copies that message only.
Tab height follows the selected page to avoid the blank block caused by reserving
space for a larger inactive page. Tabs and section headings use larger bold type.
For mouse movement, select **Hold to move**, put the pointer over an on-screen
direction button, and hold the left mouse button. Release the mouse button to stop.

### Selecting the bridge network address

On a shared infrastructure network, the telescope, bridge computer and control device use the same local network. The address field may be left blank: the program uses this computer’s adapter used to reach the telescope. Select an adapter in the table or enter its IPv4 address to choose explicitly.

In Two Interface Mode, the address field must not be blank. Select or enter this computer’s IPv4 address on the network used by the phone, tablet or other control computer. The bridge needs this address to accept connections from that network and forward commands to the telescope. Do not select the adapter connected directly to SkyQLink. Configure the adapter’s network connection in the operating system first; selecting it in the app does not connect it to a network.

Wi-Fi provisioning uses **Infrastructure / Router Wi-Fi Settings** for new values.
**Connect & Read Settings** reads the stored SSID and network configuration without changing them; the **Settings read from telescope** panel shows the SSID in bold, separately from instructions and editable fields. Full replies appear in the Transfer log. Password fields are redacted before display and saving; provisioning logs do not provide password recovery. **Show password** reveals only entered text. Password recovery through other tools is unverified for RN-171 / 2.40-CEL.

For the original SkyQLink RN-171, use the physical slider **LEFT** for Direct/ad hoc: connect this computer to SkyQLink-xx and read at `1.2.3.4:2000`. Use **RIGHT** for Infrastructure: connect this computer to the telescope’s current network and discover its assigned IP. Power OFF before moving the slider, then power ON. The app’s mode selector does not move the switch or join Wi-Fi. Readback describes stored settings, not a sensed physical switch position.

Adapter-generation terminology: **Celestron Version 1 Wi-Fi — SkyQLink RN-171** uses `SkyQLink-xx`; **Version 2 and later Celestron Wi-Fi** use `Celestron-xxxx`. The current provisioning workflow and LEFT/RIGHT switch instructions apply only to the Version 1 RN-171 / 2.40-CEL. Future adapter support must provide model-specific connection and provisioning instructions; a network name alone does not verify device capabilities. Newer-adapter provisioning is not implemented by this wording change.

### Wi-Fi address and port reference

Version 1 — SkyQLink RN-171: Direct / ad hoc normally uses 1.2.3.4, TCP port 2000 for telescope commands. WiFly settings are read through command mode on that same TCP connection. Do not assume newer-adapter management or discovery ports are available on Version 1.

Version 2 and later — Celestron Wi-Fi / SkyPortal: the established direct-connect convention is also 1.2.3.4, TCP port 2000 for telescope commands. TCP 3000 is used for configuration/management; UDP 55555 (five 5s, not 5555 or 5000) is used for discovery advertisements. Availability depends on the adapter and firmware; these are reference defaults, not a guarantee for every future model.

Infrastructure: use the adapter’s actual address assigned by your router, for example 192.168.1.x or 10.0.0.x; the subnet and address depend on your network and may change. Do not use 1.2.3.4 unless that is the address actually configured.

Control Bridge: control software connects to THIS COMPUTER’s selected local-network IP, normally TCP 2000. The bridge also provides TCP 3000 management and UDP 55555 discovery; it forwards telescope commands to SkyQLink on TCP 2000. UDP 123 is for optional WiFly time-server requests, not telescope control or discovery.

Protocol references: [ESP SkyPortal implementation](https://github.com/alex-vg/esp-skyportal-module), [HomeBrew Wi-Fi implementation](https://github.com/g7ltt/Celestron-GPS-WiFi-BT-Interface/blob/main/esp32_wifi-V3.8.ino). These community implementations document the established newer-adapter conventions; they do not certify every Celestron hardware revision. Bridge defaults are implemented in `bridge_mode.py`.

For KStars/INDI address selection and connection ownership, see the optional [KStars application note](KSTARS-BRIDGE-NOTE.md).

In Control Bridge, click an adapter row in **Local System Network Interfaces** to fill the IP box automatically, or type this computer’s IP on the control device’s network. Do not enter the telescope IP in that box. **Bridge status** is a shaded readout. The second-interface options are grouped separately: they apply to Direct/ad hoc or deliberately separate networks, not an ordinary shared infrastructure connection. The **Applies to all options** note explains that telescope control needs no Internet; hotspot/Internet sharing setup belongs to the operating system.

The bridge IP is this computer’s address on the same network as the system (computer, tablet or phone) running your control software (e.g., SkySafari, CPWI, KStars/INDI, etc.). These are examples; check the validation record for each tested configuration. Use this computer’s address on the network where that software is running. For example, SkySafari on home Wi-Fi connects to this computer’s home-network address, not its SkyQLink-network address. Type that address in the bridge IP box, or click the matching adapter row to fill it automatically.

Use this system’s IP on the network shared with the device running your control software. If that software runs on this same system, use localhost (`127.0.0.1`) when the bridge is explicitly bound there, or use the specific IP shown by the bridge. A LAN-only listener does not also accept localhost connections.

For an ordinary shared infrastructure network, leave the **Two Interface Mode** checkbox **unchecked**. For a direct SkyQLink connection bridged to a separate control-software network, **check** that checkbox and supply the bridge computer’s IP on the control-software network.

### Pi desktop and optional control clients

See the [desktop installer and zoom actions](RASPBERRY-PI-DESKTOP.md#portable-desktop-installer-and-zoom-actions), [start/stop guide](TELESCOPE-CONTROL-START-HERE.md), and optional [KStars application note](KSTARS-BRIDGE-NOTE.md). Celestron AUX is a device tab in KStars' INDI Control Panel. Manual alignment uses eyepiece centering and Sync; no camera workflow is included.


## Technical appendix: interpreting external application traffic

The bridge log retains raw AUX hexadecimal bytes and adds a parenthesized
interpretation for known commands: firmware and position reads, GoTo, tracking
rates, movement/Stop, backlash, and cord-wrap commands. Unknown commands or payload
meanings are explicitly left unknown. An echoed request is not a device reply;
a reply is not proof of physical movement, permanent settings, or sky alignment.

The [SkySafari AUX observation record](engineering/2026-11-17-skysafari-aux-observations.md)
lists observed addresses, command IDs, payloads and decoded values, including
commands without GUI controls and unknown commands reserved for later research.
It also records the absence of recognized encoder-reset/time/location writes in
the reviewed capture, without claiming those features cannot exist.


**Control Bridge has no inactivity cutoff**, for either the control connection or
management connection. Quiet clients remain connected. The idle-release preference
applies only to the direct Motor control connection. Explicit disconnects, socket
failures, and bounded local-jog/feedback safeguards remain in effect. The former
15-second control and 10-second management cutoffs were removed on November 18. Startup accessory probes
can also delay connection: the observed SkySafari sequence spent about 36 seconds
retrying nonresponding accessories. See the observation record for startup order,
shutdown handling and evidence limits.


A later screenshot/reference comparison identifies the GoTo-approach write command
and records candidate maximum-slew-rate commands. Their uncertain scaling and
readback field order remain qualified in the engineering note; no GUI controls
were added for those candidate commands. Menu visibility alone does not establish
onboard enforcement of slew limits or storage of alignment/hibernation settings.


### Bridge forwarding and timestamped motion records

The bridge forwards complete AUX client frames and telescope reply bytes before
packet logging/interpretation and screen updates. A separate event worker writes
logs and supplies UI events. TCP_NODELAY disables small-packet batching on local
bridge TCP sockets. This reduces avoidable overhead; it is not a measured guarantee
of end-to-end latency or tracking accuracy. AUX framing and local-jog arbitration
still precede client-command dispatch.

Events retain UTC and monotonic timestamps captured when queued after forwarding,
not when the disk writer later flushes. They identify bridge observations, not the
exact instant a motor executed a command. Encoder replies can reconstruct sampled
raw-axis motion, while commands describe intended motion. Do not treat either as
aligned celestial coordinates without a valid alignment model.

If the worker backlog reaches 8192 queued events, high-volume packet/readback
telemetry may be omitted to keep relay traffic moving. An explicit warning and
final dropped-event count identify incomplete recordings; lifecycle/safety events
are retained. CSV/JSON recording export is available; plotting and trajectory replay are not implemented. Keep
original logs and distinguish gaps, clock changes, resets and reconnections.


### Record motor positions and optional idle heartbeat

Open **Control Bridge → Connection keep-alive and motor-position polling**.
These two options share one scheduler and one telescope connection:

- **Poll and record motor positions**: OFF by default. Check it, enter the number
  of seconds between motor-position reads, then click **Apply intervals**. The
  default is 1 second; 5 means one sample about every five seconds, and 0.2 means
  up to five per second. The accepted range is 0.2–300 seconds. Smaller intervals
  add traffic; start with 1–10 seconds. Incoming position replies are reused;
  requests are added only for axes whose samples are missing. This records motion
  caused by external AUX controllers even when their commands do not cross Wi-Fi.
- **Keep connection alive (heartbeat)**: OFF by default. Check it and set the
  quiet interval (1–300 seconds, default 5), then click **Apply intervals**.
  Communication in either direction or a scheduled position read resets the quiet
  timer. This does not send duplicate requests alongside position recording.

Both controls apply with or without a connected control application. There is no
separate automatic one-second polling loop or three-missed-polls bridge shutdown.
Both unchecked means no optional position queries; received replies are still
logged. Startup still verifies both motor controllers before declaring the bridge
ready. Discovery broadcasts are separate from motor polling. If no control app is
requesting positions and all polling/jogging options are OFF, the last readback
will age and show STALE. That is expected: it means no recent measurement, not
proof of a disconnected transport. Enable position polling for current readbacks.

**Local jogging safety exception:** enabling local jogging in Motor control requires
fresh encoder feedback at a 0.4-second interval, even between jogs so the buttons
are ready. This uses the same scheduler, reuses external replies, and waits for
pending position queries instead of injecting duplicates. It can override a slower
recording interval. Turn local jogging OFF when using only SkySafari or another
control app to avoid these extra safety reads. Active jogging still attempts Stop
if feedback becomes stale; heartbeat settings cannot disable movement safeguards.

Checkbox changes also apply the displayed intervals. A validation message indicates
when a change was rejected. Settings last for this app session, not in hardware.
Configure them before starting the bridge or adjust them while it runs. Polling
intervals cannot change the external application's own query rate.

Intervals are best-effort sample spacing, not exact hardware execution timestamps.
Subsecond sampling is experimental on RN-171; use 1–10 seconds initially. Only one
bridge-generated read per axis is outstanding at a time; pending external position
requests also suppress injected reads. External commands are always forwarded. A missing reply is reported
as a gap after two seconds rather than a fabricated position or a flood of retries.
Replies are logged with actual observation timestamps, encoder counts and raw motor
angles. Software cannot recover motion between samples without making assumptions.
No successful heartbeat or position read proves physical stop, celestial alignment,
or immunity to connection failures. Replies to injected reads are forwarded to the
control app; compatibility with each app requires testing.


### Export packets, measured positions or both

On **Control Bridge**, click **Export bridge recording…** below the bridge log.
Choose an `events.jsonl` file (the latest operation is prefilled), or choose the
logs folder to include multiple sessions. Click **Refresh available range** to
display the earliest/latest times and prefill the start/end date-time fields.
Edit these to the desired range; values outside the displayed bounds are rejected.
The end includes the entire selected second. There is no whole-day minimum. Then choose **Wi-Fi packets and commands**, **Measured
motor positions**, or **Both in one timestamped file**. Select CSV or JSON and **Local time with UTC offset** or **Unix time**, then click
**Export…** to choose the destination. This copies data; it does not move the mount
or change/delete the source log. Exporting an active recording is a snapshot of
already-written data; stop the recording normally first for a finalized capture.

CSV uses one header row and conventional quoted fields, with UTF-8 BOM for Excel.
The first data row has `record_type=export_metadata`; subsequent records have type
`packet`, `position` or `status`. JSON has `metadata` and `records` fields and schema
version 1. Both include session identifiers, original source line numbers, UTC and monotonic seconds,
encoder counts/raw angle degrees for position records, and source/destination,
command, payload, full hex and interpretation for packet records. `details_json`
preserves the original event, including fields not represented in dedicated columns.
Status/gap/reconnect notices remain in all three selections. Metadata includes a
SHA-256 for each source snapshot and any partial-final-line warning.

Use `record_type=position` to construct measured motion and `record_type=packet`
to examine observed commands/replies. Positions do not identify which external
controller caused a movement. Do not treat requested GoTo targets as measured
positions, or raw encoders as aligned sky coordinates. The exporter does not
interpolate gaps, unwrap angles, combine different clock sessions, create plots,
or replay a trajectory; those remain separate analysis tasks.

Offline command examples (no telescope connection required):

```console
python -m export_recording events.jsonl motor-positions.csv --select positions --format csv
python -m export_recording events.jsonl wifi-packets.json --select packets --format json
python -m export_recording events.jsonl combined.json --select both --format json
```


Time is explicitly labeled: local output uses `timestamp_local_iso8601` with the
per-event UTC offset; Unix output uses `timestamp_unix_seconds_utc` (seconds since
1970-01-01T00:00:00Z). Metadata names the selected convention. Date/time bounds in
the GUI are shown with this computer's local offset, independent of export choice.
Across sessions, records are ordered by UTC and retain their source session;
monotonic times from different boot sessions are not assumed comparable.

### SkySafari disconnects when switching away from the phone app

In the 2026-11-18 test, the user observed that switching away from SkySafari
closed its connection. The bridge log recorded `control app closed its TCP stream
(EOF)` while the bridge remained running. This is consistent with app/background
lifecycle behavior; it does not identify whether SkySafari or iOS initiates it.
Keep SkySafari in the foreground for a controlled idle comparison. A bridge
heartbeat cannot keep a socket open after the phone closes it. The bridge currently
attempts Stop on client disconnect and waits for a new connection; reconnecting
does not replay old motion commands or establish alignment. Long-duration tracking
through app switches has not been verified.


### Direct motor connection: keep-alive and idle release

Before clicking **Connect Motors**, use **Direct motor connection settings**:

- **Keep connection alive** defaults ON, reading both encoders every 1 second
  while idle. Enter 1–300 seconds; larger values reduce idle traffic. This uses
  the existing motor polling loop, not a second heartbeat. Uncheck it to stop
  idle reads; startup and movement feedback checks still run. Idle readings will
  age, and connection faults may only be detected on the next operation.
- **Idle release** defaults to **30 seconds** without movement activity. Choose
  10/20/30 seconds, 1/2/5 minutes, or **Never**. Keep-alive does not extend this timer.
  Never keeps the connection until you click Disconnect or a fault releases it.
  Beyond 30 seconds or Never with keep-alive can keep the adapter occupied and
  lock out other control apps. Disconnect before switching to another app.

These settings apply on the next direct connection. They are greyed out while
connected and whenever Control Bridge is active, even with local bridge jogging
ON. Their saved selections return when the connection is released. Configure bridge
polling on Control Bridge instead. No setting guarantees a persistent Wi-Fi link
or bypasses movement feedback safety checks.

Before a direct jog, the worker reads **both encoders** even if keep-alive is OFF
or the idle readback is stale. If either reply is missing, no movement command is
sent. Idle polling interval changes therefore do not bypass this safety check.

The entire Direct motor connection settings section dims together while unavailable,
including its heading, labels and explanation. When editable, all fields remain
available: the interval can be prepared even with keep-alive unchecked, but is used
only when that checkbox is checked. Click Connect Motors to apply the displayed
settings; Enter is not required. To change an active direct connection, Disconnect,
edit, then Connect Motors again. Bridge controls remain separate.

The section subtitle is **Applied on next connection**: the settings take effect
when Connect Motors opens a new direct connection, not immediately while editing.


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
hardware-or-proxy unknown. See the [proxy identity protocol](PROXY-DISCOVERY.md)
for fields, compatibility limits and future ESP32 integration considerations.
