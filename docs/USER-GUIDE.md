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

## Connect to the telescope

Only one application should control the telescope at a time. **Disconnect** means clicking the Disconnect button on the Motor control tab to release this application’s connection; it does not mean unplugging motor cables or turning off telescope power. For the bridge, switch Control Bridge OFF. Wait for an active operation to finish before starting another. Disconnect phone
apps, other desktop controllers and this application's bridge before manual
motor control, diagnostics or settings work.

**Telescope IP address** identifies the telescope, not this computer. The normal
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

**Idle release (next connection)** offers Off, 10, 20 or 30 seconds. The default
is 30 seconds without movement activity; it releases the connection so another
application can use it. Reconnect to move again. This is application policy,
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
connections. It relays commands and replies for one control application at a
time. The control application remains responsible for alignment and tracking.

There are two different addresses:

| GUI term | What it identifies |
| --- | --- |
| Telescope IP address, at the top | The SkyQLink module that this computer connects to |
| This computer’s IP on the control-device network | The local adapter address on the network used by your astronomy app; not a MAC address or the telescope’s IP |

For a common network, leave the bridge address blank to select it automatically,
or choose this computer's relevant adapter in **Local System Network Interfaces**.
**Refresh Adapter IPs** refreshes that list; it does not change network settings.
Turn the bridge ON, then use the displayed control app connection address and
port 2000 in a compatible application. In the tested SkySafari configuration,
select Celestron WiFi and Access Point mode (the external app's spelling).
The bridge also provides discovery on UDP 55555 and limited management on TCP
3000. Allow local-network firewall access; opening a local port does not prove
that another device can reach it.

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


ON reserves the telescope connection and locks the other tabs. OFF attempts Stop
on both motors and closes the bridge; consult acknowledgements in the log.
Reported motor positions are observed from the control application's traffic;
the bridge does not insert extra position queries while a client is connected.

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

The bridge IP is this computer’s address on the same network as the system (computer, tablet or phone) running your control software (e.g., SkySafari, CPWI or KStars/INDI). These are examples; check the validation record for each tested configuration. Use this computer’s address on the network where that software is running. For example, SkySafari on home Wi-Fi connects to this computer’s home-network address, not its SkyQLink-network address. Type that address in the bridge IP box, or click the matching adapter row to fill it automatically.
