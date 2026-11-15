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
