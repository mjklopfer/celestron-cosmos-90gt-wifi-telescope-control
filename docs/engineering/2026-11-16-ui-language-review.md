# UI wording and navigation review, 2026-11-16

User authorized final validation, local commit and GitHub push on November 16, 2026. Earlier pending-review notes below describe intermediate states.

User requirement: name the control/key, state the action and explain its result.
Avoid shorthand such as "Escape stops", "Default:" and unnamed connection addresses.
Changes staged in the working tree include explicit Esc-key instructions scoped
to the main window, raw encoder-angle explanations, clear timed-jog/readout labels,
and a numbered Control Bridge workflow. The bridge input identifies this computer's
IPv4 address on the astronomy app's network, explains adapter selection and automatic
route selection, and distinguishes that address from the telescope and MAC addresses.
OFF/ON status messages now include the next action and connection fields.

Navigation uses larger bold tabs and section headings. Tab color distinguishes
selection; size and labels remain useful without color. Zoom scales tab padding
and both heading fonts. The discovery label anticipates both module families but
does not claim that the future physical ESP32 backend is implemented.

Table clipboard output uses tab-separated cells with CSV quoting, CRLF rows and
headings for direct Excel paste. Quotes, tabs and embedded newlines are escaped.
Plain log/detail text remains plain text. This is TSV, not comma-separated CSV;
no separate CSV-file export was added in this action.

After review, reconcile README/user-guide terms: actual tab order and Control
Bridge name; discovery button; network IPv4 field; Esc key and focus scope; raw
encoder/local-reference meanings; enlarged headings/tabs; spreadsheet clipboard.
Retain older validation records as dated history and append new results. Physical
AUX compatibility, PC-clock writing and full SkySafari traffic capture remain pending.


Review build checklist:
- Main GUI text now says Press the Esc key, scoped to the active main window.
- Raw encoder angles and locally offset display angles have separate labels.
- Control Bridge presents numbered setup steps and names this computer's IPv4
  address, operating-system route selection, and the control-app network adapter.
- OFF and ON messages identify the next action and the address/port to enter.
- Discovery button: Discover SkyQLink / Celestron Modules.
- Bold 12-point tabs with extra padding and selected-state color; bold 12-point
  section headings; both scale with the optional View zoom controls.
- Spreadsheet table copies use quoted TSV with headers; free-form logs stay text.
- ESP32 handoff: ESP32-RESUME.md and linked architecture/wiring documentation.

Changes remain in the working tree pending user review. No new physical telescope
motion or setting writes were needed for this UI batch. Excel-compatible delimiter
and quoting behavior is tested through parsing; a live Excel paste is not yet
verified. The prior 136-test record belongs to the preceding clock-update commit,
not automatically to this later UI batch.

Validation: 42 GUI/zoom tests passed after updating obsolete wording assertions.
Ruff and git diff whitespace checks passed. GUI launch is disconnected; no bridge
or motor connection is started automatically.


Direct/ad hoc follow-up: added an automatically updated, non-modal notice beside
Control Bridge's switch. It explains the Two Interface Mode requirement and the
next step, rather than leaving a disabled control unexplained. Start validation
now distinguishes an occupied connection from missing Two Interface Mode. The
README and guide document Ethernet/router, wired peer, second Wi-Fi and optional
hosted-hotspot arrangements, client isolation and the limits of this application.
Phone/tablet control does not inherently require two Wi-Fi adapters on the PC;
Ethernet to the phone's access point is also valid. Internet sharing and third
interfaces remain optional external configuration, not telescope requirements.

Profile follow-up: show the JSON filename beside the loaded profile. Profile file
details displays the resolved path and schema version; motor table copies include
the source path. Existing JSON storage and device-identity rules are unchanged.


Final review follow-ups: screenshot inspection confirmed the notebook reserved
height for the tallest inactive tab. Selected-page sizing removes that empty block.
Current operation status is now a labeled group; connection status is shaded and
labeled beside the motor buttons. Copy buttons name their sources. Movement help
names the left mouse button and release action. Recovery help states that clicking
Connect Motors produced no valid response from one or both motors.

The existing private JSON profile received an explicit keymap, backed up by the
profile writer. Runtime loading never invents a missing keymap. Missing/invalid
maps disable the rocker and clear the mapping text; Esc remains fixed. Calibration
regeneration preserves the map. Rate measurements now live in a separate dialog;
no usable measurements disables its button. CSV and Excel/TSV copying are separate.
README and user guide reflect these changes. User visual review and commit/push
remain outstanding; do not describe this batch as published.

Follow-up: bridge connection options now use separate indented bullets. Direct/ad hoc guidance dims in Infrastructure mode; option descriptions remain active when Two Interface Mode is selected because they can still apply. Provisioning includes a port/address Note separating legacy TCP 2000, modern TCP 3000 and UDP 55555 discovery, and optional UDP 123 time sync. GUI smoke test and lint passed; visual review remains pending.

Release validation: full Windows suite passed 142 tests after correcting a stale label assertion. Follow-up bridge layout tests cover the latest address guidance; lint, smoke and package build results are recorded in VALIDATION.md. The user requested publication before any Raspberry Pi deployment. No new hardware movement was performed in this UI review.
