# Bridge feedback and polling UI history — 2026-11-18

Users observed encoder updates continuing while local-jog buttons remained locked.
The bridge connection could still be healthy: the old local safety fault was
latched after a brief single-axis reply gap, and subsequent Stop text hid the fault.

Implemented in 892de51: stable two-axis feedback automatically unlocks future jogs
without resuming interrupted motion; configurable local feedback timeout 1–10s,
default 2s; red Restart local jogging cycles OFF for one second then ON, requires
fresh readings, and preserves the bridge. Explicit OFF cancels pending restart.
75ec0e6 adds an OK acknowledgment when Apply timeout is used while jogging is OFF.

The latest UI explains the existing shared scheduler rather than silently changing
options. Required local-jog feedback has a 0.4s target; optional heartbeat and
position polling retain their settings. Incoming replies are reused. The bridge
readout identifies the active source, and the Motor control summary appears beside
Direct motor connection settings only while bridge jogging is ON. That summary is
readable even though direct-mode controls are disabled.

The encoder display's former fixed three-second STALE rule is replaced by
max(10 seconds, active request interval + 3 seconds), using the shortest enabled
request interval. This does not modify the separate local-motion safety watchdog.
Slower optional polling therefore need not make otherwise expected readings appear
prematurely stale. No enabled polling means a ten-second display threshold.

Validation: 14 focused GUI tests, lint, whitespace and package builds passed.
Earlier bridge recovery validation included 47 bridge/GUI tests. No new physical
movement was commanded for these UI changes. Hardware transport delays, live
SkySafari recovery and long-duration tracking stability remain unverified.


## Follow-up: user-adjustable local feedback polling and timed jogs

Added Control Bridge's Local-jog feedback polling interval, default 0.4s, range
0.2–5s, with an explicit Apply button and tuning guidance. It must be shorter than
the local-jog feedback timeout; neither value silently changes the other. The
shared scheduler and automatic recovery now account for slower intervals. Freshness
for recovery is the interval plus 0.6s, capped by the timeout; the stable window is
at least one second or one polling interval, with newer samples on both axes.
Recovery status now says to press a direction to move instead of the unclear
previous-movement-cancelled phrase.

User selected timed jogs up to 5s. Added 0.1, 3, 4 and 5s choices, changed direct,
bridge and MCP bounded-jog validation/documentation, and retained the 2s bridge
hold cap and conservative calibration-estimator limit. No physical five-second
movement was commanded for development tests.

Direct-session logs showed keep-alive at 1s successfully returning both axes until
a configured 10s idle release intentionally disconnected. The display now labels
retained readings NOT LIVE — disconnected instead of implying a live feedback
fault. Diagnostics cord-wrap is read-only; backlash editing remains under Motor
control's Controller Angle / Backlash Settings, requiring exclusive ownership.


## Log scope, AUX decoding and IP routes

Transfer log is for this program's outgoing commands/queries and operation status,
including polling, Stop, idle release, feedback retry/restoration and connection
policy. It no longer duplicates external client/received bridge packets. Local
bridge-generated commands are included. Raw AUX hex gains conservative decoded
meaning; no unknown payload is assigned a guessed interpretation.

Control Bridge now has a prominent Communications Log header. Its entries cover
both external and local actions plus telescope traffic, with origin, source IP,
destination IP and route metadata. Forwarded-return labels require a successful
socket write; no client means not forwarded. AUX lacks transaction IDs, so these
labels describe network routing, not causal matching of a reply to a requester.
New CSV/JSON exports preserve the route fields, while old recordings remain usable.
Packet forwarding precedes asynchronous logging/decoding. No new telescope queries
or movement are added by the display changes. Local raw logs are not committed.
