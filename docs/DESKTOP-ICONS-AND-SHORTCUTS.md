# Desktop icons and application launchers

Preferred displayed name: **Celestron Telescope Network Control**.
The shared telescope icon has **WiFi** written on its body. The README displays
this same icon near the project title.

## Published assets

All formats are committed under [assets/icons](../assets/icons/README.md):

| File | Intended use |
| --- | --- |
| [SVG](../assets/icons/cosmos90gt.svg) | Editable source and Linux desktop icon |
| [512 px PNG](../assets/icons/cosmos90gt.png) | Transparent general-purpose icon |
| [1024 px PNG](../assets/icons/cosmos90gt-1024.png) | Larger raster source |
| [ICO](../assets/icons/cosmos90gt.ico) | Windows shortcut/application icon container |
| [ICNS](../assets/icons/cosmos90gt.icns) | macOS application icon container |

Providing an icon file is not the same as providing an executable, installer,
macOS application bundle, or tested desktop shortcut for that platform.

## Linux / Raspberry Pi — implemented

Install the application into its Python environment first, then run the existing
installer from the checkout using that environment's interpreter:

```sh
python tools/install_linux_shortcut.py
```

For the documented Pi environment, use `.venv312/bin/python` instead of `python`.
The installer derives the current checkout and interpreter paths, installs the
icon and launcher, and backs up existing launchers. It supplies 80% zoom, 100%
zoom and standard-view desktop actions. Right-click action visibility depends
on the desktop/file manager. These are launch options for new processes; close
an existing app before starting another instance.

The resulting icon is a desktop shortcut to the Python application, not a
standalone binary. See [the complete Pi desktop instructions](RASPBERRY-PI-DESKTOP.md)
for prerequisites, logs, installed paths, launch actions and validation history.
Linux/Pi installation and launch were tested on the recorded Buster system.

## Windows — asset available; complete recipe pending

The ICO is published. An existing Windows shortcut can select it through
**Properties → Change Icon**. This changes the shortcut's image; it does not
install the application or automatically change its taskbar/window icon.

Remaining work:

- Document creating a shortcut with the correct virtual-environment interpreter,
  application arguments and working directory, including paths containing spaces.
- Cover optional zoom arguments and a console-visible troubleshooting launch.
- Verify desktop/Start menu shortcut appearance and behavior on Windows 11.
- Document window/taskbar icon behavior separately from shortcut appearance.

The application has Windows runtime validation, but that is not validation of a
new shortcut installer or packaged executable. No such installer is supplied here.

## macOS — asset available; complete recipe pending

The ICNS is published for use in macOS application packaging. No new `.app`
bundle or complete Finder/Dock launcher recipe is currently supplied.

Remaining work:

- Choose and document a lightweight launcher or app-bundle approach that uses the
  installed Python environment and finds the application reliably.
- Explain how to attach the supplied icon and how desktop aliases/Dock entries
  relate to that launcher.
- Document launch arguments, working directory, logs and troubleshooting.
- Verify native Finder/Dock icon appearance and launch behavior on macOS.

SVG/PNG appearance was reviewed and ICO/ICNS decoding was checked. Native
Windows/macOS shortcut appearance remains a separate validation item. Existing
macOS GUI rendering fixes are not being reopened by this launcher work.

## Scope of this note

This document records published assets, implemented Linux support and explicitly
unfinished Windows/macOS instructions. It does not claim those remaining recipes
or installers exist. Future work should reuse the shared assets and preferred
name rather than introducing another icon or legacy application label.
