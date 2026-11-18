# SkySafari AUX observations and bridge jogging — 2026-11-17

## Evidence and limits

Read-only inspection of an existing Windows bridge capture while the user operated
SkySafari Plus against a COSMOS 90GT with SkyQLink RN-171 / WiFly 2.40-CEL.
Reviewed interval: 2026-11-18 07:26:43–07:54:32 UTC (November 17 Pacific time).
This is an observed command inventory, not an exhaustive AUX bus specification.
Private raw logs stay on the local computer; no addresses, usernames or credentials
are needed in this published record. The installed running process predates the
new decoder and local-jog implementation. These observations do not validate
live local jogging alongside SkySafari.

A request or its echoed copy is not a device reply. Requests used source 0x20;
actual motor replies used source 0x10 (azimuth) or 0x11 (elevation), destination
0x20. Reply payload 01 is recorded as a reply, not proof of physical motion,
persistence across power cycles, or a successful celestial alignment.

## Observed commands and values

| Device / command | Interpretation | Observed value or limitation |
| --- | --- | --- |
| Both motors, 0xFE | Read firmware version | Reply 05 18 = 5.24 |
| Both motors, 0x01 | Read encoder position | Three-byte counts; degrees = counts × 360 / 2^24; raw motor angles, not aligned sky coordinates |
| Azimuth, 0x05 | Read model | Reply 15 83; model encoding left unverified |
| Both motors, 0x02 / 0x17 | Fast / slow GoTo | Three-byte motor-angle targets; replies 01 |
| Both motors, 0x06 / 0x07 | Positive / negative guide or tracking rate | Changing three-byte values; raw rate integers retained, no assumed degrees/second conversion |
| Both motors, 0x13 | Read slew-complete status | Replies 00 and FF |
| Both motors, 0x24 / 0x25 | Positive / negative fixed-rate movement | Speed levels 5, 7, 9 observed; 0x24 payload 00 requests Stop |
| Both motors, 0x10 / 0x11 | Write positive / negative backlash compensation | Payloads 00 and later 07; compensation units, not degrees; replies 01 |
| Both motors, 0x40 | Read positive backlash compensation | Reply initially 00, later 07 on both axes: session readback matches the changed value; power-cycle persistence untested |
| Both motors, 0xFC | Read GoTo approach | Azimuth 00 (positive), elevation 01 (negative) |
| Azimuth, 0x38 / 0x39 | Enable / disable cord-wrap protection | Replies 01; no claim that mechanical limits or cable travel were verified |
| Azimuth, 0x3A | Set cord-wrap position | Payload 7F FF FF, approximately 180° raw motor angle; reply 01 |
| Devices 0x12, 0xB4, 0xB9, 0xBD, command 0xFE | Firmware-version probes | Requests and echoes observed; no matching device replies in reviewed interval. A probe does not establish accessory presence |

### Initially unknown commands: subsequent research and remaining uncertainty

| Device / command | Request data | Actual reply data | Interpretation |
| --- | --- | --- | --- |
| Both motors, 0x20 | 0C B2 | 01 | Candidate: set maximum slew rate; see correlation below |
| Azimuth, 0x21 | Empty | 0A BD 0C B2; later 0C B2 0C B2 | Candidate: read maximum slew rates; see correlation below |
| Both motors, 0x22 | 00 or 01 | 01 | Candidate: enable maximum slew rate; see correlation below |
| Azimuth, 0x23 | Empty | 00 or 01 | Candidate: read maximum-rate enable state; see correlation below |
| Azimuth / elevation, 0xFD | 00 / 01 respectively | 01 | Now identified from the AUX reference as Set GoTo approach: 00 positive, 01 negative |

Do not add controls for these unknown commands merely because replies exist.
Command identifiers are device-specific: motor command 0x04 means encoder-reference
write, while GPS 0x04 is a year read. Never substitute one interpretation for another.

## What was not established

- No motor 0x04 encoder-reference writes were observed in the reviewed interval.
  GoTo changes and changing position replies are not global coordinate resets.
- No recognized AUX GPS/RTC time, date or geographic-location writes were observed.
  This does not exclude settings stored inside SkySafari, other protocols, or
  commands outside the captured interval. The AUX recorder does not capture all
  possible WiFly ASCII configuration traffic.
- SkySafari sent nonzero tracking-rate commands after a Stop sequence. Stop does
  not prevent a controlling application from commanding subsequent movement.
- No shared celestial alignment, new geographic-location setter, autonomous
  onboard tracking model, or new accessory presence was established.

## Implementation and operating contract

The bridge remains the sole owner of the upstream TCP connection. The experimental
local-jog toggle starts OFF and uses the same worker; there is no second socket
competing with SkySafari. Complete, checksum-valid AUX commands are relayed in
order. Fragmented external frames are retained across local-jog toggle changes.
Malformed/non-AUX client data is not relayed by the framed AUX data path; TCP 3000
management handling is separate.

A conflicting external command cancels pending/current local motion, attempts Stop
on both axes, then passes through. A small allowlist of read requests does not
interrupt local motion; unknown commands conservatively do. External commands are
never falsely acknowledged or stored for later replay. This is priority arbitration,
not addition of two independent angular velocities. Frequent external tracking
commands can make local jogging impractical until tracking is paused in that app.

Enabling/disabling local jogging attempts Stop. Local jogs require fresh feedback
from both motors, expire if queued for more than 0.5 seconds, and run for 0.1–2 seconds.
Hold-to-move is capped at two seconds per press. Stale feedback during local motion
attempts Stop and locks local jogging until the toggle is disabled and enabled again.
A transport failure can prevent Stop delivery; no physical-rest guarantee is implied.
External commands continue even if local jogging is locked.

The new log description appears in parentheses after raw hex. Interpretation is
limited to known, device-scoped meanings and valid payload shapes. Unknown payloads
remain raw. A command description does not prove it executed successfully. No new
controls were added for the observed cord-wrap or unknown commands.

## Follow-up work

- Live supervised local jog while SkySafari is connected: verify both axes, Stop,
  external-command preemption, fresh feedback and the app's displayed position.
- Check manual centering followed by SkySafari alignment/Sync; do not assume raw
  encoder changes create or preserve a shared alignment model.
- Validate new GUI behavior on Pi and macOS; preserve existing native Mac styling.
- Investigate unknown commands only from reliable documentation and bounded tests.
- Repeat capture with SkySafari's time-setting option explicitly exercised; compare
  requests with actual replies before claiming a supported time/location endpoint.

Protocol reference: [INDI Celestron AUX command definitions](https://github.com/indilib/indi-3rdparty/blob/master/indi-celestronaux/auxproto.h).
Existing project `diagnostics.py` and `motor_settings.py` define the supported
backlash and approach-read interpretations. The trace is evidence for observed
behavior, not a replacement for firmware-specific protocol documentation.


## Observed startup sequence and timeout distinctions

The first recorded SkySafari connection probed 0xBD and 0xB9 with firmware command
0xFE, making three attempts per address about three seconds apart. It then read
azimuth firmware/model, sent Stop to both motors, and similarly probed 0xB4 and
0x12. Next came backlash/approach reads, unknown reads 0x21 and 0x23, both encoder
positions, cord-wrap configuration and tracking rates. Unanswered accessory probes
accounted for approximately 36 seconds before regular operation. This is an
observed sequence, not a required authentication handshake or a universal sequence
for every control application. No TCP 3000 management requests were logged in the
reviewed interval.

Historical bridge timers in the captured build (the inactivity cutoffs below
were removed on November 18; see the update below):

- Control-client inactivity: 15 seconds without incoming client data closes that
  client and attempts Stop. Position requests count as activity. Mount replies
  alone do not reset this timer. The upstream bridge remains available.
- Management-client inactivity: 10 seconds without incoming management data closes
  that management socket.
- Without a connected client and with local jogging OFF, the bridge polls motor
  positions. A query waits up to 1.2 seconds; three consecutive missed polls on an
  axis close the bridge with an error.
- Bridge shutdown attempts Stop and drains replies for up to 0.8 seconds, with a
  retry for missing Stop replies, then closes the upstream socket. Replies do not
  by themselves prove the telescope is physically stationary.
- New local-jog mediation separately requires feedback younger than two seconds
  and caps each jog at two seconds; these are not client inactivity timers.

The older running build logged client disconnects without a reason, so its trace
cannot distinguish a user disconnect, socket error and bridge inactivity expiry.
Commit bab0a0a added an explicit inactivity reason; the subsequent November 18
change removes the inactivity cutoffs entirely. This capture does
not establish SkySafari's complete internal timeout policy, a special AUX logout
command, or a natural 30-second WiFly inactivity timeout. Do not conflate the GUI's
direct-motor idle-release preference with these bridge timers.


## Screenshot correlation and reference follow-up

User screenshots show backlash 7 on each axis, azimuth approach Default, elevation
approach Reversed, maximum slew rate 3.25 (disabled), slew limits 7°/64°, Hibernate
ON, Manual Align and Sidereal selected. No screenshots or personal images are
published here; only their relevant settings are transcribed.

A follow-up read of [Andre Paquette's AUX reference, issue 1.0](https://paquettefamily.ca/nexstar/NexStar_AUX_Commands_10.pdf)
identifies motor 0xFD as Set GoTo approach, 00 positive / 01 negative. This supersedes
its earlier unknown classification; the decoder now labels it accordingly.

[Piotr Jochym's first-hand Evolution capture notes](https://github.com/jochym/nexstar-evo/blob/master/doc/notes.md)
associate 0x20 with a 16-bit maximum-slew-rate write, 0x21 with a pair of 16-bit
maximum-rate values, and 0x22/0x23 with write/read of its enable state (00 off,
01 on). The notes mark the 0.001 degree/second scale as tentative. Our payload
0C B2 equals 3250, consistent with the screenshot's 3.25 under that scale. The
reply 0A BD 0C B2 splits into 2749 and 3250; later both words were 3250. Exact
word roles/order on COSMOS remain unverified. These four commands retain unknown
labels in the live decoder until controlled menu-change correlation confirms them;
the candidate meanings are preserved here rather than discarded.

Backlash 7 directly matches both command payload 07 and later positive-backlash
readback 07. Approach settings match the documented 0xFD data. The screenshots do
not establish bus commands or onboard enforcement for 7°/64° slew limits,
hibernation or alignment selection. Do not treat software slew limits as physical
stops. Next useful passive test: change one named maximum-rate setting to a second
recorded value, then compare outgoing writes and subsequent reads; likewise toggle
the enable switch separately. No new write controls are added by this research.


## November 18: remove bridge inactivity cutoffs

The user requires a bridge that does not release quiet clients. Removed both the
15-second control-client cutoff and the 10-second management-client cutoff; no
replacement idle limit is enabled. Direct Motor control retains its idle-release
setting. Explicit socket closure/error, bridge OFF, missing-feedback handling and
bounded local-jog guards are unchanged. This is transport inactivity policy, not
permission to continue an unsafe local jog. The old capture contains two closes
15.001/15.031 seconds after the last client packet, consistent with the former
cutoff. Other closes occurred within fractions of a second of client commands and
motor replies; removing inactivity expiry does not explain or fix those cases.
The running old process must be restarted to acquire this change.


## Subsequent user-correlated tests, November 18 00:02–00:10 Pacific

- Maximum rate: at 00:03:17, 0x22 changed to 01 on both axes and 0x20 wrote
  08 DF (2271). The user confirmed the UI showed approximately 2.27 degrees/s.
  This corroborates the 0.001 degrees/s scale for the rate write, superseding
  the earlier single-value uncertainty. Subsequent 0x21 readback was 08 DF 0C B2:
  the first word tracks the changed setting, while the second remains 3250.
  Do not label these two fields as the two axes; their exact roles remain open.
  Physical speed enforcement and persistence across power cycling remain untested.
- Backlash: at 00:06:42, positive and negative writes changed to 15 hex (21)
  for azimuth and 1C hex (28) for elevation, with replies.
- Tracking Off: that same batch ended with 0x06 and three zero bytes on each
  axis. At 00:10:21, the user-reported Off-to-Sidereal change produced nonzero
  0x06 rates: azimuth 00 38 E2 (14562), elevation 00 15 87 (5511), both replied.
  These are per-axis rate values, not Sidereal mode identifiers. Separate solar
  and lunar mappings were not established by rapid menu cycling.
- SkyAlign/Manual Align changes: two batches at 00:04:27 and 00:04:33 carried
  identical ordinary settings; no distinct alignment-selection or encoder-reset
  command was observed. Possible app-local handling remains an inference.
- Hibernate OFF: ordinary settings were resent without a distinct Hibernate
  command. A later reconnect repeated full accessory probes whereas one preceding
  connection skipped them; one comparison does not establish causation.

These observations were recorded from the old running bridge without injecting
commands or restarting it. The decoder's maximum-rate labels still require a
follow-up change; this note preserves the stronger evidence without claiming that
new controls or physical validation have already been added.
