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
