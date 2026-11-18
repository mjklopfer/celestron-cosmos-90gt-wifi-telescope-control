# Distinguishing a COSMOS software proxy from a telescope module

Control Bridge makes this computer a software proxy, not a physical Celestron
Wi-Fi module. The GUI states that role explicitly. Another instance can identify
it through its management connection without claiming its motor-control socket.
This is preparation for future physical ESP32/Celestron interfaces; it does not
implement the future hardware mode or certify third-party firmware compatibility.

## Read-only identification

The bridge keeps its existing TCP management listener (default **3000**):

1. Send ASCII `version\n`. Our version family begins `COSMOSBridge-AMW007-`.
2. Only after receiving that prefix, send `get cosmos.proxy\n`.
3. The proxy returns one JSON object followed by the usual CRLF/prompt. Neither
   command is forwarded to AUX or WiFly. No movement, Stop, provisioning or clock
   command is sent by identity discovery.

Example fields (port values follow the running bridge configuration):

```json
{
  "schema": 1,
  "product": "cosmos90gt-control",
  "role": "software_proxy",
  "physical_module": false,
  "instance_id": "02:11:22:33:44:55",
  "version": "COSMOSBridge-AMW007-0.1.0.0, Python proxy",
  "data_port": 2000,
  "management_port": 3000,
  "ready": true
}
```

The instance ID is the proxy's locally administered synthetic MAC, generated for
that bridge instance. It is not the telescope MAC or a permanent hardware ID.
`ready` means bridge startup succeeded and shutdown has not been requested, not
proof of alignment, tracking health or fresh motor feedback.

Existing UDP discovery advertisements retain `mac` and `version`, adding a
`cosmos_proxy` object with the same schema. Advertisements keep their existing
idle/no-control-client schedule. Desktop discovery currently uses management TCP,
so it can identify the proxy while a control client is connected. The structured
command is never blindly sent to an unidentified physical module. We do not assume
that every physical module safely ignores arbitrary vendor commands.

## Discovery results and GUI behavior

- `software_proxy`: shown as **COSMOS software proxy — not a physical module**.
  `proxy_verified=true`, but `adapter_verified=false` and `motors_verified=false`:
  identity checking deliberately does not test the motors.
- `physical_wifly`: established only from the existing recognized WiFly firmware
  identification, not from a vendor MAC hint alone.
- `unclassified_aux`: valid AUX replies but hardware identity not established;
  this may be physical hardware or another proxy. Do not guess.

Discovery checks management identity before opening the motor port. Legacy
COSMOSBridge versions are still classified as proxies even if they reject the new
structured command. Infrastructure scans check remaining hosts for proxies even
when a physical adapter was found first. A discovered proxy remains listed, but
selecting it does **not** replace the GUI's telescope address or load it as a WiFly
provisioning target. Use its displayed data address in your control application.
With only proxies found, the previous telescope address remains unchanged.

## Limits and verification

Identity is self-reported, unauthenticated classification, not a security boundary.
A busy/unreachable management port, firewall, timeout or unsupported product can
prevent recognition. Failure to identify a proxy is not proof of physical hardware;
unknown AUX endpoints remain explicitly unclassified. The fallback AUX discovery
may still open an unrecognized endpoint, so disconnect controllers when scanning
unknown hardware as otherwise instructed. Recognized proxies avoid that path.

Automatic management probing uses port 3000. The helper accepts an explicit custom
management port for controlled use; scanning arbitrary management ports is not
implemented. LAN scan scope/budget and local-address exclusions remain in effect.
No passwords, upstream telescope address or network configuration are exposed in
the structured identity. Added UDP fields preserve the existing keys, but live
compatibility with every external control application remains unverified.

Mock and loopback tests cover structured/legacy proxy recognition, no private
query to nonproxy versions, no motor-port connection for recognized proxies,
physical-plus-proxy discovery, unchanged GUI hardware targets, and identification
while a simulated control client continues using the bridge. No live telescope
scan or movement is required for these tests.
