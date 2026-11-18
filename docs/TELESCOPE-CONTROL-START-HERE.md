# Telescope Control — Start Here

## Start from a fresh desktop session

1. Power on the telescope. Connect this computer to the network that can reach its Wi-Fi interface.
2. Open **Celestron Telescope Network Control** (older shortcuts may say Cosmos 90GT). Right-click the shortcut for 80% zoom, 100% zoom, or the standard view. These menu actions depend on desktop support.
3. Select **Infrastructure** when the telescope and computer are connected to the common access point. Click **Discover SkyQLink / Celestron Modules** and select the discovered telescope, then click **Apply Module & Profile**. Alternatively, enter its confirmed current **Telescope Wi-Fi interface IP address**. The app's mode selector does not move the telescope's physical switch or join a network. Leave Motor control disconnected while using KStars.
4. Confirm the applied profile is **SkyQLink** for the legacy COSMOS 90GT. Open **Control Bridge**. Select this computer's IP address on the network shared with the system running your control application. Turn the bridge ON and check the displayed listening address. For software on this same computer, you may explicitly bind the bridge to `127.0.0.1`; otherwise use its selected LAN address. A bridge bound only to a LAN address is not available through localhost.
5. Open **KStars - Celestron Control Bridge**. This shortcut starts the installed INDI server before KStars. Open Ekos and select **COSMOS 90GT - Local Control Bridge**. The INDI server is `127.0.0.1`, port `7624`; the mount is **Celestron AUX**.
6. Start the Ekos profile. In the INDI control panel, select Celestron AUX. Under Options, load the saved configuration. Check its TCP connection address: it must match the bridge's listening address, with port `2000`. This is the bridge computer's address, not the telescope's address. Select TCP and Alt-Az mode; disable automatic LAN search if using this explicit address. Save configuration after changes.
7. Connect the mount. Check that position values are received before commanding movement. Keep the telescope clear of mechanical stops and cable snags. Use a small manual movement only with adequate clearance, then Stop/Abort and verify that it stops.

The three connections are distinct: KStars to INDI uses port 7624; INDI to Control Bridge uses port 2000; Control Bridge to the telescope uses the telescope's IP and port 2000.

## Legacy KStars requirement

KStars 3.0.0/Ekos requires a CCD or guider in the profile. This installation uses **CCD Simulator** solely to satisfy that requirement. The telescope and Celestron AUX driver are real, not simulated. No physical camera is required for this workaround.

The tested setup uses Raspberry Pi 3B+, Raspbian 10 Buster (32-bit armv7l), Python 3.12.16, Tcl/Tk 8.6.9, KStars 3.0.0, custom INDI core/Celestron AUX sources v1.9.4, and the system INDI 1.7.5 CCD Simulator. The simulator wrapper clears the custom driver's library path so each uses its matching libraries.

## What has been verified

KStars manual movement on both axes, position readback, and Stop were verified through Control Bridge. Fresh raw encoder readings confirmed both axes stopped. This driver updates its displayed horizontal coordinates only after approximately 0.1 degree of change; small movements may not immediately change the displayed value.

A fresh Pi session was also checked after reboot: the bridge initially received no motor replies. After the telescope was power-cycled, the bridge started, KStars connected, and four successive samples returned fresh, stationary encoder readings on both axes. No movement was requested in that reboot check. Power cycling the telescope reset its raw encoder counts to zero; this does not establish a sky alignment.

Celestial alignment, accurate GoTo, and sustained tracking have not been verified. Raw encoder angles and this application's local position offsets do not establish celestial alignment in KStars.

## Manual alignment and the INDI window

**Celestron AUX is a device tab in KStars' INDI Control Panel**, not a separate application. Its Connection and Options tabs contain connection settings. Star selection and Sync are in the KStars sky-map telescope menu.

Set the observing location, date and time correctly. Center a known star in the eyepiece using movement controls, then right-click that star in KStars and choose the connected telescope menu → **Sync**. Repeat with additional well-separated stars before checking **GoTo/Slew**. Clear the previous INDI alignment model after telescope power cycling or changing encoder references. Our local offsets and controller angle writes do not establish KStars alignment. RA pairs with declination; azimuth pairs with elevation. No camera workflow is required. See docs/KSTARS-BRIDGE-NOTE.md in the checkout for details.

The subsequent authorized post-reboot movement test moved azimuth by -0.049074° and elevation by +0.062935° through KStars. Both stopped with stable fresh encoder readings. Actual star alignment and GoTo accuracy remain untested.

## Shut down

1. Stop/Abort motion in KStars and confirm the telescope is stationary.
2. Disconnect devices in Ekos, then stop the Ekos profile.
3. Turn Control Bridge OFF, then close KStars and the telescope application.
4. Power off the telescope as needed. Shut down the Pi normally before removing power.

Do not rely on an idle timeout to transfer control between applications. Disconnect the current controller explicitly before another application takes over.

## Troubleshooting

- No mount connection: check that Control Bridge is ON and the INDI telescope address exactly matches its listening address, port 2000. Load saved INDI settings if it reverted to `1.2.3.4` after restart.
- No telescope replies: check telescope power, its current IP, network connectivity, and that other controllers are disconnected.
- If the bridge reports missing encoder replies, leave it OFF. In Diagnostics, the adapter-restart action can recover a stalled legacy module without changing saved settings. If it cannot confirm command mode, it will not restart the module; disconnect other controllers and power-cycle the telescope, then retry. Rebooting only the Pi does not restart the telescope's Wi-Fi module.
- Ekos asks for a camera: select CCD Simulator in this legacy profile.
- No small position change on screen: allow for the driver's display threshold and polling delay. Do not increase movement beyond available clearance merely to force an update.
- Other control applications (for example SkySafari, CPWI, KStars/INDI, and others) need their own compatible Celestron connection settings. These examples are not a compatibility guarantee. See the project's application note for guidance.

This portable guide contains no account-specific paths, credentials, or installation-specific IP addresses.
