# Future connection backends

Recorded 2026-11-16 from the operator's development direction. This is planned
work, not a claim of current ESP32/ESP8266 or modern-module support.

Today the application's provisioning and control path targets the legacy
SkyQLink RN-171 / 2.40-CEL. Its Control Bridge presents selected modern
Celestron Wi-Fi discovery/management behavior to clients while forwarding AUX
to that legacy adapter.

Future ESP32/ESP8266-to-AUX work may provide another transport and additional
features. The application should eventually support both direct motor control
and bridge roles with legacy SkyQLink and a modern Celestron Wi-Fi-compatible
interface. The name is **Celestron**, not Skytron. Compatibility must be verified
for each actual implementation, rather than inferred from an advertised identity.

## Proposed separation

- Connection backend: connect/disconnect, identity, transport, packet exchange,
  telemetry freshness, recovery and capability reporting.
- Motion service: stop, position, bounded jog/target, limits, calibration and
  reference handling, independent of WiFly provisioning commands.
- Adapter settings: legacy WiFly commands only for positively identified legacy
  hardware; future firmware configuration uses a separate adapter implementation.
- Bridge role: client-facing discovery/relay configured separately from the
  telescope-facing connection backend.
- GUI and MCP: share service contracts and capabilities. A future **Connection
  type** selector chooses the backend; unsupported controls are disabled with
  a clear explanation, not silently routed through legacy commands.

Profiles should identify hardware/firmware/backend and protocol capabilities,
not only an IP address. Maintain migration/versioning for calibration and site
settings. Do not mix pulse calibration, encoder reference or device defaults
between backends without verification. Endpoint ownership remains exclusive.

## Implementation gates

1. Bring up ESP-to-AUX transport and establish voltage/electrical behavior,
   framing, command/response integrity, latency and disconnect/Stop behavior.
2. Define a capability/version handshake and test a backend service contract.
3. Verify motion and limits with supervised bounded tests; calibrate per device.
4. Add GUI connection selection and capability-dependent controls, then MCP
   reporting and bridge integration; retain legacy regression tests.
5. Publish a tested hardware/firmware/client matrix. Shared celestial alignment,
   autonomous tracking, time/site persistence and higher-rate motion remain
   separate capabilities to establish, not assumptions of the new transport.
