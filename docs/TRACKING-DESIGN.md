# AI-assisted tracking design and implementation plan

## Scope and current state

The AI chooses targets, prepares trajectories, supervises alignment and explains
status. A deterministic local producer handles frequent updates; AI response
latency must not be part of the motor timing loop. The [engineering log](engineering/2026-11-16-tracking-constraints.md)
preserves the operator's ISS and Oceanside launch scenarios and their limitations.

| Capability | Current implementation / boundary |
| --- | --- |
| Timed motor jogs and encoder readback | Production motor backend; 36 calibration pulses completed on this device |
| MCP supervision | Status, discovery, diagnostics, jobs, motor/bridge control, deliberate settings writes |
| High-rate target ingress | Authenticated localhost HTTP, sequence and UTC validation, bounded latest samples |
| Simulation | Rate-limited local model; stale/invalid input stops simulation; not hardware validation |
| Native position targets | Experimental AUX 0x02, explicit commissioning override and arm; at most 4 Hz dispatch, no timing guarantee |
| Connection recovery | Experimental worker retries with backoff; needs both fresh encoders and a new target after reconnection |
| Local reference | Paused worker can map encoder position to known AZ/EL; does not create shared celestial alignment |
| Divergence detection | Prototype pauses/disarms when target error increases beyond its guard |
| Predictive hardware velocity / arrive-by-time | Not implemented or advertised as supported |
| Orbitron, Flight Club, TLE, rotctld adapters / pass graphics | Planned external producers, not implemented |
| Whole-pass mechanical safety | Not verified; prototype limited to at most 5 degrees from initial encoder position |

Native hardware commissioning could not obtain a fresh encoder pair; it stopped
before sending a target. The 5-degree tracking test remains pending. A working
TCP connection, passing simulator test or successful timed jog is insufficient
to mark native tracking supported.

## Control contract

Call `control_capabilities` before selecting a mode. MCP manages connection,
reference, explicit arming, status and stop. For sustained input use the URL and
token file returned by `target_stream_start`; send POST /target JSON:

```json
{"sequence": 1, "utc": 1794866400.0, "azimuth_deg": 123.4, "elevation_deg": 35.6}
```

The timestamp is Unix UTC seconds and must be replaced with the current target
time. AZ is north-zero/east-increasing in the producer's agreed reference;
elevation is above the local horizon. The controller only knows the local
reference supplied to it. A single reference cannot correct mount tilt or build
a full sky model. No endpoint for shared COSMOS celestial alignment is claimed.

Start in simulation. Stream limits default to elevation 0–80 degrees and 2.5
deg/s on each axis; these are software defaults, not certified hardware limits.
The server rejects malformed/nonfinite samples, old or non-increasing sequence
and timestamps, samples more than 0.2 seconds ahead, samples older than the
configured stale threshold (default 0.5 seconds), and excessive per-axis rates.
Two samples are retained; simulated extrapolation is bounded. No queued replay
of old trajectories is allowed. Hardware updates are serialized and may be much
slower than the incoming sample rate. Report encoder age and connection state
alongside every decision; an accepted target is not proof of movement or arrival.

The experimental native worker requires an explicit travel envelope, fresh
feedback, reference and arming. After a link loss it attempts Stop and reconnects
with 0.5–2 second backoff. Fresh feedback plus a new post-reconnection target is
required before resuming. The last position remains visible with age. Suspected
power cycles invalidate reference assumptions and require realignment. A finite
last target can still complete if Stop cannot be delivered; software limits do
not replace mechanical stops or operator clearance.

## Producer plan

1. **Live AZ/EL:** normalize current UTC, sequence, frame conventions and source
   age. Keep only the latest useful sample and short bounded lookahead.
2. **Orbitron/WispDDE:** validate actual local DDE service/topic/item and payload;
   timestamp on acquisition and preserve source age when provided. Translate to
   the stream. Never replay a buffered DDE backlog after reconnect.
3. **Orbital satellites:** use a tested SGP4 implementation with TLE/OMM epoch,
   UTC and observer latitude/longitude/height. Archive element set and site for
   reproducibility; evaluate azimuth unwrap, acceleration and near-zenith rates.
4. **Powered launch:** consume actual CSV/ephemeris schema; use T+ plus separately
   editable UTC liftoff T0, stage identity and observer coordinates. A hold stops
   timeline advancement. T0 or stage changes require continuity checks before
   motion resumes. Do not substitute a parking-orbit TLE for powered ascent.
5. **Plots:** generate sky track, axis rates/accelerations, visibility windows,
   forbidden travel, encoder age and pointing-error plots outside the GUI/MCP
   motor backend. Highlight infeasible sections before a pass.

## Feasibility, catch-up and drift

Use both axis derivatives, not only total angular speed. Check acceleration,
transport latency, reversal backlash, braking distance, cable wrap and zenith
singularity. Reserve rate margin for catching up. For one axis moving in the
same direction, a first-order estimate is error / (available rate - target rate),
only when the denominator is positive; it omits acceleration and other limits.
Reject deadlines that cannot be met rather than increasing rate beyond hardware
limits. Do not hard-code the provisional launch table as an operating envelope.

Future variable-rate control needs verified AUX command semantics and measured
tracking accuracy before a predictive feed-forward mode can be enabled. A future
`arrive_by_utc` contract must return accepted/rejected feasibility and achieved
error; the current UTC field is freshness, not an arrival deadline. On divergence,
pause/stop, notify the supervisor, correct the reference or trajectory, and
explicitly re-arm. Do not silently rewrite hardware encoder references to chase
drift. A dedicated drift-offset API remains planned.

## Acceptance work remaining

- Verify native 0x02 acknowledgement and actual encoder motion with a small
  supervised target, then bounded 5-degree sweep; current attempt sent no motion.
- Measure sustained update latency, paired-axis sampling skew, target error,
  acceleration/braking and reversal response across speed/load/direction.
- Exercise producer loss, corrupt/stale/future targets, disconnect mid-motion,
  controller restart and target changes during recovery; verify no stale replay.
- Validate actual mechanical clearance and cable limits independently of encoder
  values; reject unsafe route choices and zenith crossings.
- Test acquisition and reacquisition below measured limits with bounded error;
  test impossible rates/deadlines are rejected and reported.
- Validate Orbitron/CSV/TLE adapters against reference trajectories and correct
  observer/time/stage; keep those adapters outside this project's current GUI scope.
