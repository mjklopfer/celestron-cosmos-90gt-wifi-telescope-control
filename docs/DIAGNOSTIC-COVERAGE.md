# Diagnostic coverage and live verification

Development and hardware polling were performed from the Windows local Python application on 2026-11-16.

## Modes

Normal diagnostics polls the core WiFly, motor, and optional GPS/RTC fields.
**Deep diagnostics** is unchecked by default and requires confirmation each run.
It adds extended WiFly configuration/status/file listings and model-dependent AUX
queries. Extra polling can interrupt controller traffic and takes longer; keep the
mount stationary and other controllers disconnected.

Both modes are destination-whitelisted. Neither performs an arbitrary 256-command
sweep. AUX command numbers have different meanings on different devices.

## Audited additions

| Interface | Deep-mode reads |
| --- | --- |
| WiFly | get apmode, broadcast, dns, ftp, everything, ip a; show connection, io, net n; ls |
| Both motors | PEC record-completion status |
| Azimuth only | Index status, cordwrap enabled, cordwrap position |
| Altitude only | Level-completion status |
| GPS | Receiver status bits and hardware identification byte |

All standard configuration-get families in the referenced WiFly manual are covered
by individual reads or the complete settings dump. `show q` analog sampling is
excluded because sampling may operate sensor power; neither sensor wiring nor that
behavior has been verified on this customized module. Active scan, ping, DNS lookup,
clock sync, network changes, reset, storage changes, and firmware operations are
excluded. AUX commands of unknown purpose and modern accessory-specific operations
without a verified device/decoder are excluded. These exclusions are not evidence
that the endpoints do not exist.

## Actual COSMOS results

- WiFly RN-171 firmware 2.40-CEL answered all 24 WiFly queries in the expanded run.
- Both motor controllers returned version 5.24 and position/backlash/approach values.
- Azimuth cordwrap reported disabled, position zero.
- PEC completion (both axes), azimuth index, and altitude level completion returned
  raw `01`. The cited reference specifies `00`/`FF`; these are retained as unknown
  encodings, not interpreted as affirmative status.
- Optional GPS/RTC and other cataloged AUX addresses did not return matching replies.
  This does not prove absence or permanently unsupported commands.

## Clock and site provenance

The WiFly clock summary reports set/unset status, reported clock text, uptime,
RTC and raw counters, restart/wake counts, time-server enable/address and raw zone
setting. This device reported **Time NOT SET**, **TimeEna=0**, and **Zone=7**.
With the clock unset, uptime/RTC/RAW values are counters, not valid calendar dates.
WiFly manual section 3.11 explicitly maps Zone=7 to GMT-7 (UTC-07:00); this
does not identify a geographic site or establish a daylight-saving rule. When clock
text and an RTC value are reported without the unset flag, the summary can derive
a labeled UTC date from documented Unix seconds, without assuming clock accuracy. No geographic latitude or
longitude was found in the WiFly settings dump. GPS/RTC reads had no reply.

Host local time/UTC offset/timezone name are recorded separately as host metadata;
they are never substituted for telescope time. No observing-site cache is assumed.
The main-board version read had no reply; no other main-CPU date/site interface has
been established. Missing data means not reported through these interfaces, not
proof that no internal storage exists.

## References and scope

- [Microchip WiFly reference DS50002230B](https://ww1.microchip.com/downloads/en/DeviceDoc/50002230B.pdf), sections 4.4–4.7; newer than customized 2.40-CEL.
- [NexStar AUX observations](https://paquettefamily.ca/nexstar/NexStar_AUX_Commands_10.pdf), motor/GPS command tables.

Coverage is exhaustive only with respect to the explicitly listed, documented safe
query catalog. It cannot establish every private endpoint or every firmware variant.
Credential fields are redacted; private live captures are not committed.


## Follow-up read-only pass, 2026-11-16

The existing deep catalog completed without an operation error; WiFly identity
and both motor positions were verified. Optional GPS/compass and RTC queries
again had no matching replies. No newly verified endpoint was added. A missing
reply cannot establish physical absence or prove that private commands do not
exist. The wider documentation audit is not a claim of exhaustive firmware coverage.

Unlike the earlier unset-clock snapshot, this pass reported a calendar RTC value,
startup synchronization enabled, and a configured time server. A subsequent
read-only time-dialog backend check reported WiFly approximately 1.6 seconds ahead
of the computer using UTC Unix seconds, with no setting write, sync request or
motion command. This verifies reading/comparison, not the mechanism that set the
clock. The device's displayed zone and the PC's local zone differed; UTC comparison
avoids treating that display difference as a clock error.

SkySafari's [vendor setup guide](https://support.simulationcurriculum.com/hc/en-us/articles/115015943188-Scope-Setup-Help)
says time/location are always sent for Celestron Wi-Fi. Destination, packet format,
COSMOS behavior and whether this modifies the RN-171 clock remain to be observed.
Existing bridge logs capture checksummed AUX frames in both directions, not all
non-AUX bytes. Do not infer absence of a transfer from absent AUX records alone.
