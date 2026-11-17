# Application note: KStars through Control Bridge

Use KStars/Ekos with the **Celestron AUX** INDI driver, configured for a TCP network connection to the computer running Control Bridge, port **2000**. The INDI server address and telescope TCP address are separate settings: a local INDI server normally uses `127.0.0.1:7624`; that does not automatically make the telescope endpoint localhost.

For both programs on one computer, explicitly bind Control Bridge to `127.0.0.1` and set the INDI telescope endpoint to `127.0.0.1:2000`. A bridge bound to a LAN IP only does not listen on localhost; use that same LAN IP in INDI instead. Loopback binding excludes remote phones/computers. If Control Bridge runs on another computer, use that computer's selected LAN IP and TCP 2000. Enter the real telescope IP in the bridge's upstream connection field.

Disconnect Motor control, then turn Control Bridge ON before connecting the INDI mount. Motor control's idle release can free its connection, but it does not start the bridge or transfer ownership automatically. Keep Control Bridge ON while KStars controls the telescope. Disconnect other direct telescope clients. Do not depend on a WiFly transport timeout to hand over control cleanly.

The Pi's legacy KStars/INDI versions may require a separately installed Celestron AUX driver. A saved profile or open TCP socket is not proof of working encoder feedback, alignment or motion. Verify read-only position and driver status before attempting alignment or movement. This app's local offsets and raw encoder references do not supply INDI celestial alignment.

Deployment and end-to-end checks are recorded separately in the Raspberry Pi validation record; no full KStars hardware verification is implied by these instructions.
