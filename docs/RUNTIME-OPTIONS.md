# Runtime options and launch reference

This reference covers every command-line option in the desktop GUI, installed bridge entry point, calibration utility and shipped top-level diagnostic/verification CLIs. It describes the current source, not planned features. Options belong to the named command: do not pass bridge/calibration flags to the GUI. Quote paths and SSIDs containing spaces. `IP` below means a numeric IPv4 address, not a MAC address or Wi-Fi network name.

## Desktop GUI: all options

Run `cosmos90gt` or `python -m skyqlink_setup` from the installed environment. With no arguments, it opens disconnected, at 100% size, without the View menu, with telescope address `1.2.3.4` and TCP port `2000`. Opening the GUI does not move the telescope, start Control Bridge or launch an MCP server. Launch options apply to that process; they are not saved telescope settings.

| Option | Default / accepted value | Function and when to use | When not to use / limitations |
| --- | --- | --- | --- |
| `-h`, `--help` | No value | Print the actual command syntax and exit; use before scripting a launch. | Does not start the GUI or test hardware. |
| `--host IP` | `1.2.3.4` | Prefill **Telescope Wi-Fi interface IP address**. Use the adapter's current infrastructure address, or the legacy direct address. Exact `1.2.3.4` selects Direct/ad hoc; other addresses initially select Infrastructure. | Do not put this computer's bridge/listener address here. It does not join Wi-Fi, discover the adapter or connect by itself. Host validity is checked when an operation uses it. |
| `--port NUMBER` | `2000`; integer, service operations require 1–65535 | Prefill the telescope TCP port. Change only for a deliberately configured adapter endpoint. | Do not substitute UDP discovery `55555`, management TCP `3000` or INDI server `7624`. Those have different roles. |
| `--connect` | Absent: remain disconnected | Automatically start Motor control connection and encoder reads after startup. Use only when this process should own the telescope. No slew is requested by the flag. | Omit for bridge/KStars use, offline review, shared-controller handoff or unverified addresses. Connection/recovery/Stop handling can still send protocol commands; this is not an offline flag. It does not start Control Bridge. |
| `--zoom-controls` | Absent: no View menu | Add View → Zoom in/out, Actual size and Fit width. Useful on small screens or when changing display size during a session. | Not required to use `--ui-scale`; does not change telescope settings. Fit width is manual, not continuous auto-fit. |
| `--ui-scale FACTOR` | `1.0`; finite number from `0.5` through `2.0` | Set initial UI size: `0.8` = 80%, `1.0` = 100%, `1.25` = 125%. Use smaller values for compact displays. | Not a percentage integer: use `0.8`, not `80`. Invalid/out-of-range values are rejected. Small values can reduce readability; scrollbars remain available. It does not enable the View menu by itself. |
| `--diagnostic-report PATH` | Absent | Display a previously saved diagnostic JSON report and select Diagnostics, without automatically connecting. The report supplies its recorded host/port, overriding the initial fields. Use for reviewing captured output. | This is historical data, not a live refresh. Do not combine with `--connect` for offline review: that flag would request a live connection. Use a report produced by this program with its expected schema, not an arbitrary JSON file. |
| `--smoke-test` | Absent | Construct/check/close the GUI and print success, without contacting the telescope. Use to verify Tk/environment and a display-scale choice. Requires a graphical display even though it exits. | Not a normal launch or a network/motion test. It does not prove hardware, firewall or KStars operation. Do not combine with saved-report review; report-loaded host/port can conflict with startup assertions. `--connect` is not executed in this branch. |

Examples (replace the infrastructure address with the actual telescope address):

```sh
# Normal disconnected launch
python -m skyqlink_setup
# Small display, View menu, known telescope address; still disconnected
python -m skyqlink_setup --host 192.168.1.50 --zoom-controls --ui-scale 0.8
# Offline startup test
python -m skyqlink_setup --zoom-controls --ui-scale 0.8 --smoke-test
# View an existing report, without connecting
python -m skyqlink_setup --diagnostic-report "/path/to/report.json"
```

There is currently **no** GUI `--noapi`, `--api`, `--bridge`, `--keymap`, `--profile`, `--idle-timeout` or `--two-interfaces` switch. Do not use proposed options as if implemented. The GUI does not start a general HTTP control API. Its optional MCP server is a separate process; experimental target-stream ingress is a separate MCP-controlled feature, not full GUI control.

## On-screen switches are not command-line switches

| Control | Meaning and use | Avoid / limitations |
| --- | --- | --- |
| Direct / ad hoc versus Infrastructure | Select the connection instructions/address convention matching the physical adapter and computer network. | Does not move the telescope switch or join a network. |
| Control Bridge OFF/ON | Start/stop this computer's relay for one control application. Start only after Motor control is disconnected. | Turning it off releases control and sends Stop; do not turn it off during intended external tracking. |
| Two Interface Mode checkbox | Check for a direct SkyQLink upstream bridged to another network; select/enter this system's address facing the control software. Leave unchecked for an ordinary shared infrastructure network. | Not Internet sharing, an OS router, or automatic interface configuration. |
| Keyboard control OFF/ON | Enable the JSON profile's displayed letter map while Motor control has focus outside text fields. Starts OFF. Uppercase labels match keycaps; Shift/Caps Lock are not needed. | Missing/invalid keymap disables it. Esc remains a fixed Stop key in the active main window. Does not act as global system hotkeys. |
| Hold to move / Timed jog | Hold and release a direction button/key, or request the selected bounded jog duration. | These request real movement after connection. Keep physical clearance; time estimates are not alignment. |
| Idle release | Off, 10, 20 or 30 seconds; default 30, applied on the next motor connection. Releases after no movement activity. | Does not automatically start a bridge or hand over to KStars. It is distinct from lost-feedback handling and adapter TCP timeouts. |
| Recover a stalled adapter on Connect | Optional one-time identified legacy WiFly restart when motor feedback is missing; disconnect other clients first. | Not a routine connect requirement. Unsaved module settings can be lost; it does not fix every transport failure. |
| Deep Diagnostics Read checkbox | Opt into the additional allowlisted reads after the warning. | Reads can occupy/interrupt the legacy link; not an unrestricted register scan and not safe to run concurrently with another controller. |
| Show password | Show only the password entered in the editable box. | Does not recover the telescope's saved password; credential fields are redacted from provisioning logs. |

## Separate bridge command: all options

Use `cosmos90gt-bridge` or `python -m bridge_mode`. This starts the relay immediately without a GUI. Close Motor control and other direct clients first. Ctrl+C requests Stop and bridge shutdown. Listening ports are TCP 2000 (control), TCP 3000 (management) and UDP 55555 advertisement; this CLI does not offer switches to change those listener ports.

| Option | Default | Function / when to use | When not to use |
| --- | --- | --- | --- |
| `-h`, `--help` | — | Show syntax and exit. | Not a live test. |
| `--host IP` | Required | Telescope Wi-Fi interface IP to connect upstream. | Not the control software's computer IP. |
| `--port NUMBER` | `2000` | Telescope's upstream TCP port. | Not an INDI/discovery/listener port selector. |
| `--bind IP` | Empty: OS route-to-telescope adapter address | This system's local IP accepting control clients. Use the shared/control-software LAN address; `127.0.0.1` restricts control clients to this computer. | A LAN-only listener does not also accept localhost. Loopback does not serve remote phones/computers. Must be an address actually assigned to this system. |
| `--two-interfaces` | Off | Permit a direct `1.2.3.x` SkyQLink upstream with explicit `--bind`; requires a separate control-side address. | Not needed for ordinary infrastructure. Does not configure adapters, hotspot, routing or Internet sharing. |

```sh
# Same-machine control software: INDI telescope endpoint is 127.0.0.1:2000
python -m bridge_mode --host 192.168.1.50 --bind 127.0.0.1
# Direct telescope link plus a second LAN for external control software
python -m bridge_mode --host 1.2.3.4 --two-interfaces --bind 192.168.1.20
```

## Calibration utility: all options

Run `python calibrate_telescope.py`. At least one of `--snapshot`, `--move` or `--import-report` is required. The script documents its own operation at its top. Disconnect other telescope controllers before live operations. JSON writes retain a `.previous` backup; do not confuse a captured baseline with independently verified factory defaults.

| Option | Default | Function / when to use | When not to use / interactions |
| --- | --- | --- | --- |
| `-h`, `--help` | — | Print usage and exit. | Does not create a profile. |
| `--host IP` | Required, including imports | Telescope address associated with the profile/report. | If an existing profile address changes, use `--snapshot` to verify adapter MAC first. |
| `--port NUMBER` | `2000` | Telescope TCP port/profile endpoint. | Do not use unrelated service ports. |
| `--config PATH` | `telescope-calibration.json` in the program data directory | Choose output/input profile file. | Does not make the GUI load that custom path automatically; GUI loads its default profile. |
| `--snapshot` | Off | Read available diagnostic/settings values and add a baseline with raw/decoded evidence. Preserves rate samples. | Captures current state, not guaranteed factory defaults. Live reads occupy the connection. |
| `--deep` | Off | Add deep allowlisted reads to `--snapshot`. | Has no effect without `--snapshot`; do not use while another application controls the mount. |
| `--device-reset-confirmed` | Off | With `--snapshot`, label state as reset by the user. | Does not reset or verify a reset. Rejected without `--snapshot`; use only if a reset was actually performed. |
| `--move` | Off | Physically measure positive/negative jog rates for both axes, rates 1–9. Saves measurements/partial evidence. | Requires supervision and clearance; mutually exclusive with `--import-report`. Not an offline test. |
| `--clearance-deg NUMBER` | `0` | With `--move`, declare at least 5° of physically clear travel. Values below 5 are rejected. | Not a sensed limit or permission to exceed mechanical stops. Has no movement role without `--move`. |
| `--seconds NUMBER` | `1.0` | Movement pulse length, accepted 0.1–1.0 seconds for `--move`. | Not total run duration. Has no effect on read-only snapshots/imports. |
| `--import-report PATH` | Off | Build rate data from an existing measurement JSON report without performing that measurement again. | Replaces current rate samples; not for arbitrary diagnostic JSON. Cannot combine with `--move`. Combined `--snapshot` still performs live reads before import. |

Snapshots can be combined with a movement run or import; the snapshot occurs first. Existing keymaps and baseline history are preserved. A movement error retains partial evidence and returns failure; Stop delivery cannot be guaranteed after connection loss.

## MCP launch and environment

`cosmos90gt-mcp` / `python -m cosmos_mcp` has **no argparse command-line switches**, including no implemented `--help`, `--host` or `--noapi` parser. It runs stdio MCP until the client closes it. Install `.[mcp]` only when using it; ordinary GUI/Pi desktop use does not need that extra.

| Environment variable | Default / purpose | Use / limitation |
| --- | --- | --- |
| `COSMOS90GT_HOST` | `1.2.3.4` | MCP's initial telescope endpoint; change while idle through `set_endpoint` if needed. Not a GUI address override. |
| `COSMOS90GT_PORT` | `2000` | MCP's initial telescope TCP port. |
| `COSMOS90GT_DATA_DIR` | `~/.cosmos90gt` | Shared program data/log/profile root; set before starting processes. A different root means a different default profile and local lease location. Keep controllers using the same root when relying on local exclusion. |
| `COSMOS_WIFI_*` | None | A specifically named password environment variable referenced by the provisioning MCP tool; supply through a secure local mechanism. Not a generic autoload prefix or a reason to log environment values. |
| `COSMOS90GT_QUIET_REPORTS` | Set internally to `1` by MCP | Keeps report output out of stdio protocol. Normally no user action required. |

MCP operates backend services, not arbitrary widgets in an already running GUI. Its tool schemas document confirmation flags, defaults and motion limits; see [MCP control](MCP-CONTROL.md). Do not assume shared live GUI/MCP state or global Stop across independent applications.

## Other shipped diagnostic/verification CLIs

These are developer/commissioning tools, not alternate GUI launch switches. All argparse commands below support `-h`/`--help`. Use their own `--help` before running. Live tools need exclusive telescope access; a successful offline test is not hardware validation.

| Command | Every option and default | Appropriate use / avoid |
| --- | --- | --- |
| `python -m celestron_probe discover` | `--interface NAME` optional; `--subnet 1.2.3.0/24` default; help | Probe the selected local interface/subnet for legacy discovery. Limit to your attached network; not a general Internet scanner. |
| `python -m celestron_probe diagnose` | `--host 1.2.3.4`; `--port 2000`; `--map-aux` off; help | Legacy read probes; `--map-aux` adds AUX address probing. Prefer GUI allowlisted diagnostics for routine use; do not run during control. |
| `python -m wifly_configure` | `--ssid TEXT` optional; mutually exclusive `--inspect` / `--apply`, both off; help | With neither mode, preview only. `--inspect` reads the directly attached `1.2.3.4:2000` adapter. `--apply --ssid NAME` prompts for the password, writes/verifies/saves WPA2 configuration. No host/port flags; use the GUI for infrastructure addressing/security selection. Do not use `--apply` merely to read settings. |
| `python -m recover_link` | `--host IP` required; `--port 2000`; help | Restart an identified stalled legacy adapter. It is disruptive and can discard unsaved settings; not a harmless read-only command. |
| `python -m verify_motors` | `--host 1.2.3.4`; `--port 2000`; `--move` off; help | Default reads/checks; `--move` requests half-second forward/reverse tests per axis. Do not enable motion without clearance and supervision. |
| `python -m verify_bridge` | `--host IP` required; `--port 2000`; help | Live loopback relay/read/reconnect verification with temporary listener ports and no advertisements. Requests no slew, but Stop is sent on cleanup. Not a persistent control bridge. |
| `python -m gui_hardware_check` | `--host IP` required; `--port 2000`; `--move` off; `--soak-seconds 0`; help | Live GUI/feedback check; `--move` performs 0.7-second directional holds; `--soak-seconds` extends feedback monitoring. Not the offline GUI smoke test; requires a display and exclusive hardware access. |
| `python -m discover_modules` | No parsed command-line switches | Runs default attached-network discovery immediately. Prefer the GUI for mode/timeout choices; do not assume `--help` prevents its scan. |

Modules such as `diagnostics`, `time_settings`, `motor_settings`, `position_control` and `tracking_stream` are backend APIs, not independently configurable argparse launchers. Experimental firmware/build tools under `hardware/` have their own project documentation and are outside these desktop runtime options.

## Raspberry Pi desktop actions

The deployed launcher defaults to `--zoom-controls --ui-scale 0.8`. Right-click choices, where supported by the desktop/file manager, are:

| Menu choice | Arguments | When to use |
| --- | --- | --- |
| Open with zoom controls at 80% | `--zoom-controls --ui-scale 0.8` | Compact Pi display; View menu available. |
| Open with zoom controls at 100% | `--zoom-controls --ui-scale 1.0` | Larger display or normal-size text with View menu. |
| Open standard view without zoom menu | `--ui-scale 1.0` | Original-size interface without View menu. |

Close an existing app before using a launch action; actions start a new process rather than change the open window. They do not use `--connect`, move the telescope or start a bridge automatically. For host/port/report options use a terminal or a separately configured launcher; the fixed display menu is not an editor for every possible CLI value. Desktop Actions support varies; PCManFM custom actions supplement the standard desktop entry. See the [Pi desktop guide](RASPBERRY-PI-DESKTOP.md) for installation and verification scope.

`python tools/install_linux_shortcut.py` is a Linux installation helper with no parsed switches. Run with the application's virtual-environment interpreter. It installs desktop actions and backs up existing launchers; it does not start the app or connect to a telescope. See the [desktop installation guide](RASPBERRY-PI-DESKTOP.md#portable-desktop-installer-and-zoom-actions).
