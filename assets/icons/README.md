# Desktop icon assets

Preferred shortcut name: **Celestron Cosmos 90GT WiFi Control**.
Use this exact label beneath desktop shortcuts. The spelling here follows the
requested shortcut name; descriptive documentation continues to use “Wi-Fi”.

The telescope-body label reads **WiFi**. The editable SVG is the source:

| File | Use |
| --- | --- |
| `cosmos90gt.svg` | Linux desktop icon and editable vector source |
| `cosmos90gt.png` | 512-pixel transparent PNG for general desktop use |
| `cosmos90gt-1024.png` | 1024-pixel transparent PNG/master raster |
| `cosmos90gt.ico` | Windows icon with 16/24/32/48/64/128/256-pixel sizes |
| `cosmos90gt.icns` | macOS icon container generated from the 1024-pixel image |

These assets do not install or change shortcuts automatically. On Linux, run
`python tools/install_linux_shortcut.py` from the checkout using the application
virtual environment. It derives paths locally and installs desktop actions.
For Windows shortcuts select the ICO through Properties → Change Icon. macOS
packaging can use the ICNS; no new macOS app bundle is supplied by this change.

The SVG and PNG were visually reviewed; ICO/ICNS decoding was checked. Native
Windows/macOS shortcut appearance for these new assets remains a separate check.
