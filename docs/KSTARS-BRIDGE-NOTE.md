# Application note: KStars through Control Bridge

Use KStars/Ekos with the **Celestron AUX** INDI driver, configured for a TCP network connection to the computer running Control Bridge, port **2000**. The INDI server address and telescope TCP address are separate settings: a local INDI server normally uses `127.0.0.1:7624`; that does not automatically make the telescope endpoint localhost.

For both programs on one computer, explicitly bind Control Bridge to `127.0.0.1` and set the INDI telescope endpoint to `127.0.0.1:2000`. A bridge bound to a LAN IP only does not listen on localhost; use that same LAN IP in INDI instead. Loopback binding excludes remote phones/computers. If Control Bridge runs on another computer, use that computer's selected LAN IP and TCP 2000. Enter the real telescope IP in the bridge's upstream connection field.

Disconnect Motor control, then turn Control Bridge ON before connecting the INDI mount. Motor control's idle release can free its connection, but it does not start the bridge or transfer ownership automatically. Keep Control Bridge ON while KStars controls the telescope. Disconnect other direct telescope clients. Do not depend on a WiFly transport timeout to hand over control cleanly.

The Pi's legacy KStars/INDI versions may require a separately installed Celestron AUX driver. A saved profile or open TCP socket is not proof of working encoder feedback, alignment or motion. Verify read-only position and driver status before attempting alignment or movement. This app's local offsets and raw encoder references do not supply INDI celestial alignment.

Both-axis manual movement, Stop and fresh readback are verified. See the [versioned results and limitations](engineering/2026-11-16-pi-kstars-validation.md) and [desktop startup/shutdown guide](TELESCOPE-CONTROL-START-HERE.md). Real-star alignment, GoTo accuracy and sustained tracking remain unverified.

## Where to find the controls

**Celestron AUX is a device tab in the INDI Control Panel window opened from KStars/Ekos**, not a separate application. Its Connection and Options tabs contain mount connection and saved-configuration settings. Load the saved configuration before connecting after server startup; confirm the address matches the bridge's listening address. The [example configuration](../examples/indi-celestron-bridge.xml) contains a placeholder bridge address to replace locally.

KStars 3.0.0 requires **CCD Simulator** in this profile to satisfy its CCD/guider requirement. Only the camera is simulated; the mount is real. This workaround is not a physical alignment method.

## Manual eyepiece alignment

1. Set the correct observing location, date and time in KStars. Confirm Alt-Az mount type.
2. After telescope power cycling or changing raw encoder references, clear the old INDI alignment model using its alignment controls. Do not blindly reload a model tied to previous encoder origins.
3. Use manual movement controls to center an identified bright star in the eyepiece.
4. Right-click that same star on the KStars sky map, open the connected telescope's menu, and select **Sync**. This sky-map menu is separate from the INDI connection-settings window; exact labels depend on version.
5. Repeat with additional well-separated stars, centering each before Sync. Three points provide an initial multi-star model.
6. Right-click another visible object and select **GoTo/Slew**, supervise the first movement, and verify actual centering before relying on accuracy.

RA pairs with declination; azimuth pairs with elevation. Selecting an identified star avoids manual coordinate entry. Our utility's local offsets change its display only; writing controller angles changes raw motor references, not INDI's sky model, and can invalidate an existing alignment. There is no verified shared-alignment flag or import from our utility. No camera or star-image workflow is required or included here.

The installed driver exposes Sync and includes the INDI alignment subsystem, but this manual sequence has not yet been verified on real stars in this deployment. References: [INDI alignment documentation](https://docs.indilib.org/interfaces/alignment-subsystem.html) and [Celestron AUX documentation](https://drivers.indilib.org/mounts/celestron/celestron-aux/celestron-aux/). Current upstream documentation can show controls absent in older versions.

## Other control applications

Applications such as SkySafari, CPWI, KStars/INDI and others need their own compatible Celestron Wi-Fi connection settings. If the client accepts an explicit endpoint, use the bridge computer's listening IP and TCP 2000, not the upstream telescope address. CPWI uses its Celestron Wi-Fi connection workflow; discovery and alignment need separate end-to-end verification with this bridge. Consult its documentation if manual address entry is unavailable. These examples are neither an exhaustive list nor a universal compatibility guarantee.

## Reading bridge log routing notices

A telescope reply marked **not forwarded** was received by this program but was
not relayed to an external control client. For example, when bridge position
polling is enabled before KStars connects its Celestron AUX device, the bridge
itself requests the readings and records the replies locally. This does not
mean the reply was unsolicited or that forwarding failed. Check the Connection
property of Celestron AUX, not just whether KStars has connected to INDI.

Once the mount device connects, the route includes **External control app** in
both directions. Verify fresh position replies for both axes; the driver's
Online/Connected status and displayed coordinates alone do not establish live
feedback. After a power cycle, zero encoder counts are raw startup references,
not celestial alignment.

An observed failed session lost telescope network reachability before KStars
connected. Recommissioning/reconnecting the adapter restored communication.
The operator reported possible loss of saved SSID settings, but this has not
been independently confirmed and its cause is unknown. The checked bridge
session did not issue WiFly SSID/password/save commands. Do not infer loss of
configuration from a failed ping alone.
