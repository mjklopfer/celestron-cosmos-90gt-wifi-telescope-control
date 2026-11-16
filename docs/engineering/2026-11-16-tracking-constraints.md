# Engineering log: satellite and launch tracking constraints

Date: 2026-11-16. Source: operator-supplied engineering considerations during development.
Status: **provisional design inputs, not measured mount performance or validated mission predictions**.
These inputs inform the [tracking implementation plan](../TRACKING-DESIGN.md).

## ISS scenario supplied by the operator

Assumed altitude approximately 408 km, orbital speed 7.66 km/s, illustrative
observer-relative speed 7.3–7.4 km/s. Supplied apparent angular-speed envelope:
0.17–1.05 degrees/s; elevation rates up to approximately 1.05 degrees/s;
azimuth may greatly exceed this near zenith. Preserve the following estimates
for simulation scenarios; recalculate from an actual pass before operational use.

| Peak elevation | Slant km | Total deg/s | Supplied maximum elevation deg/s | Peak azimuth deg/s |
| --- | ---: | ---: | ---: | ---: |
| 0 degrees | 2315 | 0.17 | 0.17 | 0.05–0.17 |
| 30 degrees | 753 | 0.56 | 0.35 | 0.65 |
| 45 degrees | 561 | 0.75 | 0.52 | 1.06 |
| 60 degrees | 467 | 0.90 | 0.72 | 1.81 |
| 75 degrees | 422 | 1.00 | 0.92 | 3.86 |
| 85 degrees | 410 | 1.03 | 1.01 | 11.8 |
| 90 degrees | 408 | 1.03–1.05 | 1.03–1.05 | Coordinate singularity / 180-degree azimuth change |

Engineering corrections: the maximum elevation-rate column describes a possible
maximum elsewhere in a pass, not the rate at culmination. For a smooth pass below
zenith, elevation rate is zero at its maximum. At exact zenith, conventional
azimuth is undefined and elevation can have a cusp; an instantaneous 180-degree
coordinate change is not an executable motion request. There is no universal
180-degrees/s bound or safe peak-elevation cutoff.

Use angular speed = transverse relative velocity / slant range, not full relative
speed unless it is perpendicular to the line of sight. Away from zenith:

`omega_sky^2 = elevation_rate^2 + (cos(elevation) * azimuth_rate)^2`.

Thus `azimuth_rate = omega_sky / cos(elevation)` in magnitude only when elevation
rate is zero. Evaluate both axes and acceleration over the whole pass. The
operator's illustrative solar/lunar transit estimates (0.6–1.0 degrees/s across
roughly 0.5 degrees in 0.5–0.9 seconds) are scenarios, not timing predictions.

## Oceanside / Vandenberg launch scenario supplied by the operator

Approximate observer-to-launch-site separation 338 km, bearing 299 degrees WNW.
Proposed polar/SSO heading approximately 190 degrees; southeast/53-degree-orbit
scenario approximately 145 degrees. Launch heading is mission dependent and is
not uniquely determined by orbital inclination.

| Scenario | Proposed closest slant range | Proposed peak elevation | Total apparent rate | Peak azimuth rate |
| --- | --- | --- | --- | --- |
| Polar / SSO | 330–400+ km | 18–20 degrees | up to 0.40–0.42 deg/s | about -0.42 to -0.44 deg/s |
| Southeast / Starlink illustration | 200–220 km | 35–45 degrees | up to 0.85–0.90 deg/s | about -0.95 to -1.10 deg/s |

| Flight phase, T+ seconds | Polar: total / elevation / azimuth deg/s | Southeast: total / elevation / azimuth deg/s |
| --- | --- | --- |
| 60–90, clearing horizon | 0.04–0.10 / +0.03–+0.08 / -0.01–-0.05 | 0.04–0.09 / +0.03–+0.09 / -0.01–-0.03 |
| 120–150, late first stage | 0.17–0.28 / +0.12–+0.15 / -0.13–-0.23 | 0.15–0.25 / +0.13–+0.21 / -0.07–-0.14 |
| 210–250, closest approach/apex | 0.40–0.42 / +0.10 through 0 / -0.42–-0.44 | 0.80–0.90 / +0.35 through 0 / -0.95–-1.10 |
| 360–480, late second stage | 0.10–0.15 / -0.07–-0.08 / -0.07–-0.12 | 0.10–0.17 / -0.09–-0.13 / -0.05–-0.11 |

Additional supplied estimates: horizon clearance around T+60 seconds; 10–22 km
altitude during T+60–90; stage separation around T+150; visual apex T+230–250;
overall elevation-rate range -0.25 to +0.40 deg/s; azimuth sweeps counterclockwise
from WNW toward S/SSE. A returning booster was estimated to slow to 0.02–0.05
deg/s near the launch-site bearing. These are all **unverified mission-specific
assumptions**. They must not become fixed timing, elevation, or slew limits.
Lower-elevation trajectories avoid the zenith singularity, but do not establish
trackability without telemetry quality, rate, acceleration and travel checks.

## Trajectory inputs and corrections

Prefer UTC-stamped or T+-indexed launch ephemerides with azimuth, elevation and
optional range, linked to an exact observing site. Keep T0 separately adjustable
for launch holds and timing correction. Preserve stage identity: booster and
upper-stage tracks must not be spliced automatically after separation.

TLE/SGP4 is suitable for orbital satellite prediction, not a general powered-ascent
model. SGP4 is not purely Keplerian: it includes perturbations and an approximate
atmospheric drag model. The statement that it assumes zero drag is incorrect.
A universal "hundreds of kilometers within seconds" error is not established;
error depends on the trajectory and fit. Predicted post-SECO elements are not
automatically accurate at cutoff or deployment; verify epoch, object and orbit.

Operator-proposed sources/adapters to evaluate:

- Flight Club path-tracker/CSV: verify current export schema, units, timestamps,
  observing-site conventions, license/access and stage selection using an actual file.
- RocketTraker-style time-indexed trajectories with T0 adjustment and manual nudges:
  design inspiration, not a dependency or established compatibility claim.
- Orbitron WispDDE rotor feed: capture and timestamp azimuth/elevation, use a bounded
  buffer, reject stale samples, translate to the local stream interface.
- TLE/OMM + SGP4 for orbital objects, with observer latitude/longitude/height and UTC.
- Piecewise synthetic TLE fits (suggested 3–4 arcs of 90–120 seconds) are an
  unvalidated workaround; require fit-error and transition checks. Prefer ephemerides.
- Hamlib rotctld or EasyComm/GS-232 adapters are possible future external producers.
  Proposed 0.5–1 second updates require measured pointing-error validation; they
  are not sufficient by assumption for narrow-field telescope tracking.

Taking finite differences of azimuth/elevation does not establish that this
COSMOS firmware supports a corresponding variable-rate command. Unwrap azimuth,
filter prediction noise, and independently verify command units/ranges first.

## Evidence and decisions

36 supervised one-second timed jogs (rates 1–9, both directions on both axes)
completed on this device. Rate-9 pulse averages were approximately 2.76 deg/s AZ
and 3.06 deg/s EL, with direction-dependent differences. They include startup,
backlash and transport effects; they are not certified continuous tracking rates.
The encoder scale is protocol-derived, not externally surveyed angular accuracy.

Native target commissioning failed to obtain a fresh encoder pair before motion.
No native target was sent; the proposed 5-degree sweep was not performed.
Default hardware streaming remains blocked pending supervised commissioning.

Plan: per-axis rate/acceleration feasibility, conservative margin for catch-up,
latency/age reporting, explicit zenith exclusion, mechanical/cable envelopes,
manual reference and drift correction, and stale-data stop/reacquisition tests.
Never assume that a 1-degree/s sky track fits within a 3-degree/s azimuth axis.

## Source pointers and verification scope

- [NASA orbit teaching material](https://www.nasa.gov/wp-content/uploads/2018/06/stemonstrations_orbits.pdf)
  supports approximate ISS altitude/speed, not the detailed tables above.
- [Skyfield satellite documentation](https://rhodesmill.org/skyfield/earth-satellites.html)
  explains SGP4-specific elements, observer calculations and epoch/accuracy limits.
- [CelesTrak SGP4 reference](https://celestrak.org/publications/AIAA/2006-6753/)
  is the propagation-model reference, including drag/perturbation treatment.
- [Flight Club path tracker](https://flightclub.io/path-tracker) was reachable but
  required JavaScript; export capability/schema was not verified in this audit.
- Operator also supplied ISSInfo, community/forum and video examples. Those
  have not been used as validated numerical specifications.

## Geographic-location endpoint audit and UI decision

Recorded 2026-11-16 at the operator's request. We have not established a writable
geographic-location endpoint on this COSMOS. No latitude/longitude setting is
verified for WiFly RN-171 / 2.40-CEL, and no motor-controller command accepting an
observing site for onboard tracking calculations has been verified.

The documented AUX GPS interface provides latitude/longitude read commands;
that is not evidence of a general site-location write command. The recorded
COSMOS diagnostic run received no matching optional GPS/RTC replies. This does
not prove those devices or undiscovered endpoints can never exist.

Decision: do not add a hardware geographic-location settings menu without a
verified endpoint. Future computer-side observing-site configuration for orbit
or launch prediction must be clearly labeled local to the application; it must
not imply that coordinates were written to the telescope or that autonomous
tracking/shared celestial alignment was established.
