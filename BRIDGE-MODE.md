# Bridge setup

See [README: bridge modes and addresses](README.md#bridge-two-addresses-with-different-purposes)
for setup, networking requirements, firewall permissions and limitations.

The bridge has two endpoints: a telescope destination and a computer listening
address reachable by the control app. In two-interface mode the listening IP is
required and must be on the phone's network, not the telescope-facing network.

Verified configurations include one infrastructure LAN and Ethernet plus direct
SkyQLink Wi-Fi. SkySafari is a tested control application, not the exclusive client.
Successful sessions do not establish long-duration reliability. Isolated idle
reply delays now retry; repeated missing replies still fail closed. This retry
change needs further live endurance verification.

The proxy emulates selected later-generation Celestron module discovery and
limited management behavior, then forwards native AUX traffic to the original
Version 1 adapter. It is not a complete newer-module firmware replacement.

If the control application already connects to the telescope directly through
the router network, leave Bridge OFF. This software can be used solely to upload
infrastructure Wi-Fi settings, then disconnected/closed before the control app
connects to the telescope's own assigned IP. See the README's provisioning-only
workflow; compatibility depends on the application version and configuration.

## When to use the bridge

Compatible phone and PC control applications can connect to the original adapter's
router-assigned IP after infrastructure provisioning; supported SkySafari
configurations and CPWI are examples. They do not inherently require this proxy.

The older direct/ad hoc SkyQLink connection can cause application compatibility
or connectivity issues. The bridge provides a later-module-style app-facing
interface while the computer handles the original adapter link. The verified
two-interface setup uses telescope-facing Wi-Fi plus house-network Ethernet;
the phone stays on house Wi-Fi. A functioning computer-to-adapter radio link is
still required. Use Celestron Wi-Fi as the scope type for the tested bridge path;
do not assume a serial NexStar/Advanced GT profile is interchangeable with it.
