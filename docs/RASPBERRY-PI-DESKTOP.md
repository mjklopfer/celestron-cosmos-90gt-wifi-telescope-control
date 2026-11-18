# Raspberry Pi OS / Raspbian desktop setup

This guide runs the Python/Tk application in an existing graphical desktop.
It is a source installation with a desktop shortcut, not a standalone binary.
Real telescope and bridge operation require separate hardware validation.

## Version 1.1 deployment — November 18, 2026

Updated from GitHub, installed into the existing Python 3.12.16 environment, and
passed startup smoke plus 36 focused offline tests. Tcl/Tk 8.6.9 and psutil 7.2.2
were present. The desktop app launched successfully; shortcut display actions
and the Desktop Start Here guide were refreshed. No new live telescope/GoTo
validation is implied. See [validation](VALIDATION.md).

## Recorded environment

Validation date: November 16, 2026. Application baseline: `d0b92c9`.

| Component | Recorded value |
| --- | --- |
| Hardware | Raspberry Pi 3 Model B Plus Rev 1.3 |
| OS | Raspbian GNU/Linux 10 (Buster) |
| Architecture | 32-bit ARM, `armv7l`, armhf packages |
| Kernel | `5.10.103-v7+` |
| RAM | Approximately 1 GB (915 MiB reported usable) |
| X desktop size | 912 x 492 pixels |
| Desktop packages | PCManFM `1.3.1-1+rpt27`; lxsession `0.5.4-1+rpt1` |
| Original system Python | 3.7.3; below the application's minimum 3.10 |
| Separate application Python | 3.12.16, installed under `/opt/python3.12` |
| Compiler package | GCC `4:8.3.0-1+rpi2` |
| libc6 package | `2.28-10+rpt2+rpi1+deb10u2` |
| OpenSSL development package | `1.1.1n-0+deb10u6` |
| Tcl development package | `8.6.9+dfsg-2+b1` |
| Tk development package | `8.6.9-2` |
| Application package | `cosmos90gt-control 1.0.0` |
| Runtime dependency | `psutil 7.2.2`, built locally as an armv7l wheel |
| Environment packaging tools | pip `26.3`, setuptools `84.2.1`, wheel `0.48.0`, packaging `26.3` |

## Confirmed results

- Python 3.12.16 rebuilt and installed successfully with SSL, Tk and SQLite imports.
- Runtime SSL reported `OpenSSL 1.1.1n 15 Mar 2022`; Tk reported 8.6.
- pip successfully downloaded over HTTPS and installed the editable application
  and `psutil` in `.venv312`.
- Default 100% GUI smoke test passed without the zoom switch.
- Zoom-enabled 80% GUI smoke test passed on the actual X display.
- All four `test_ui_zoom` tests passed in 8.675 seconds: invalid-scale rejection,
  narrow-window scrolling/Fit width, scaled switch hit testing, and size reset
  with preservation of entered settings.
- The desktop entry was launched through GLib's `Gio.DesktopAppInfo` API.
  An X window titled **Celestron Cosmos 90GT Telescope Wi-Fi Control** appeared;
  its 80% interface and View menu were visually checked. It remained running,
  disconnected, without new startup errors in the launcher log.
- The desktop file passed `desktop-file-validate` after using a single main
  menu category. The system `/usr/bin/python3` remained at 3.7.3.

The complete 92-test suite was previously run on Windows, not on this Pi during
this validation. Real telescope connectivity, motor control, provisioning,
bridge operation, and long-duration operation remain unverified on this Pi.

Python 3.12 was selected for this machine; the app does not require 3.14.
Installing another Python does not upgrade Buster or its underlying libraries.
For a new deployment, prefer a supported Raspberry Pi OS release. This legacy
recipe preserves an existing Buster installation.

## 1. Check the system and package repositories

Run in a terminal on the Pi:

```sh
cat /etc/os-release
uname -m
python3 --version
sudo apt update
```

On the tested Buster machine, the old Raspbian repository returned HTTP 404 and
APT refused it because it had no Release file. The fix was to back up
`/etc/apt/sources.list` and change only the Buster Raspbian entry from:

```text
deb http://raspbian.raspberrypi.org/raspbian/ buster main contrib non-free rpi
```

to:

```text
deb https://legacy.raspbian.org/raspbian/ buster main contrib non-free rpi
```

Do this only if that exact obsolete entry exists on a Buster machine. Do not
apply it to newer OS releases or change the separate `archive.raspberrypi.org`
repository. Then rerun `sudo apt update`. Signature verification remained
enabled in the tested setup; no `trusted=yes`, insecure-repository options,
certificate bypasses, or unsigned-package overrides were used.

## 2. Install build dependencies

If Python 3.10 or newer with working SSL and Tk is already available, a source
build may be unnecessary. The following is the path used for Python 3.12 on
Buster:

```sh
sudo apt install -y build-essential pkg-config wget ca-certificates \
  libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
  libsqlite3-dev libffi-dev liblzma-dev libncursesw5-dev \
  libgdbm-dev uuid-dev tk-dev
pkg-config --modversion openssl tk
```

The tested versions were OpenSSL 1.1.1n and Tk 8.6.9. Python 3.12 requires
OpenSSL 1.1.1 or newer. Install these development packages **before** configuring
Python. Installing Buster's `python3-tk` alone does not add Tk to a separately
compiled Python 3.12.

## 3. Build Python alongside the system Python

```sh
mkdir -p ~/src
cd ~/src
wget https://www.python.org/ftp/python/3.12.16/Python-3.12.16.tgz
tar -xzf Python-3.12.16.tgz
cd Python-3.12.16
./configure --prefix=/opt/python3.12 \
  --with-ensurepip=install --with-openssl=/usr
make -j2
./python -c 'import ssl, tkinter, sqlite3; print(ssl.OPENSSL_VERSION); print("Tk:", tkinter.TkVersion)'
sudo make altinstall
/opt/python3.12/bin/python3.12 -c 'import ssl, tkinter; print(ssl.OPENSSL_VERSION); print("Tk:", tkinter.TkVersion)'
```

Run each step only after the previous step succeeds. The two-worker build is
deliberate for the tested 1 GB Pi; compilation can take many minutes. Do not
replace `/usr/bin/python3` or point the system Python symlink at this build.

For repair of an existing incomplete build, install the missing development
packages, rerun `configure` in the source tree, then rebuild and repeat the
import checks before `make altinstall`. The verified repair reused the source
tree and reconfigured it after adding OpenSSL and Tk headers.

## 4. Install or update the application

For a fresh checkout:

```sh
cd ~
git clone https://github.com/mjklopfer/celestron-telescope-network-control.git celestron-cosmos-90gt-wifi-telescope-control
cd celestron-cosmos-90gt-wifi-telescope-control
```

For an existing checkout with no conflicting local changes:

```sh
cd ~/celestron-cosmos-90gt-wifi-telescope-control
git checkout main
git pull --ff-only origin main
```

Buster's older Git may not provide `git switch`; `git checkout` works here.
Create a separate environment, preserving any old `.venv`:

```sh
/opt/python3.12/bin/python3.12 -m venv .venv312
. .venv312/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
python --version
python -m pip show cosmos90gt-control psutil
```

After repairing an existing `/opt/python3.12` installation, the tested workflow
refreshed its existing environment with `python3.12 -m venv --upgrade .venv312`.

## 5. Test in the graphical desktop

Use a terminal inside the Pi's X desktop, with the virtual environment active:

```sh
python -m skyqlink_setup --smoke-test
python -m skyqlink_setup --zoom-controls --ui-scale 0.8 --smoke-test
python -m unittest test_ui_zoom -v
python -m skyqlink_setup --zoom-controls --ui-scale 0.8
```

Smoke tests construct and close the window without contacting the telescope.
Zoom tests use no real telescope. The normal launch remains disconnected until
the user chooses a connection operation.

At 80%, the **View** menu provides Zoom in, Zoom out, Actual size (100%), and
Fit width. Fit width is manual; use it again after resizing. Scrollbars keep
oversized content accessible. Omit both options for the original 100% size
without a View menu; Python 3.10 or newer is still required.

An ordinary SSH shell has no graphical session by default. A `no display name`
error is different from a Python/Tk import failure. Run from the logged-in
desktop for this guide; do not use `sudo` to launch the GUI.

## 6. Add a clickable desktop launcher

After the normal launch works, create an entry pointing directly to the
environment's interpreter. No shell activation is needed when clicking it.
The following assumes the checkout path used above:

```sh
mkdir -p "$HOME/.local/share/applications"
desktop_dir="$(xdg-user-dir DESKTOP)"
mkdir -p "$desktop_dir"
cat > "$HOME/.local/share/applications/Cosmos90GT.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Celestron Cosmos 90GT
Comment=Telescope Wi-Fi control with View menu zoom
Exec="$HOME/celestron-cosmos-90gt-wifi-telescope-control/.venv312/bin/python" -m skyqlink_setup --zoom-controls --ui-scale 0.8
Path=$HOME/celestron-cosmos-90gt-wifi-telescope-control
Icon=applications-science
Terminal=false
Categories=Education;Astronomy;
StartupNotify=false
EOF
cp "$HOME/.local/share/applications/Cosmos90GT.desktop" "$desktop_dir/Cosmos90GT.desktop"
chmod +x "$desktop_dir/Cosmos90GT.desktop"
```

Double-click **Celestron Cosmos 90GT** on the desktop. For a programmatic check
on the tested Buster image, the system Python's existing PyGObject installation
can launch the same desktop entry:

```sh
/usr/bin/python3 - <<'PY'
from gi.repository import Gio
entry = Gio.DesktopAppInfo.new('Cosmos90GT.desktop')
assert entry is not None, 'Desktop entry was not found'
print('Launch accepted:', entry.launch([], None))
PY
```

This uses the system Python only to ask the desktop to launch the entry; the
application still runs under `.venv312` Python 3.12. If PyGObject is not installed,
use the desktop icon directly. The tested Buster `gio` utility did **not** have
a `launch` subcommand, and `gtk-launch` was not installed; neither utility is
required for the icon itself to work. A successful launch request should still
be followed by checking that the application window appears.

The desktop launcher and application environment must stay in place. A desktop
may ask whether to execute/trust a newly created launcher. Close any existing
Cosmos window before testing the icon to avoid opening multiple instances.
The tested machine also used a custom telescope icon and a small wrapper that
captured launch errors to a local log; those are optional, not runtime requirements.

## Troubleshooting

| Symptom | Cause / next check |
| --- | --- |
| Python 3.7.3 does not satisfy `>=3.10` | Activate `.venv312`; upgrading pip cannot upgrade the interpreter. |
| `setup.py` not found during `pip install -e .` | Confirm `pyproject.toml` is in the current directory and update pip in the correct environment. |
| `No module named psutil` | Install the project into the same environment used to launch it. |
| `No module named _ssl` | Install `libssl-dev`, reconfigure/rebuild Python, then check `import ssl` before retrying pip. |
| `No module named _tkinter` | Install `tk-dev`, reconfigure/rebuild Python, then check `import tkinter`. |
| Desktop icon appears to do nothing | Run its interpreter command in a desktop terminal to see errors; confirm the environment and checkout paths still exist. |
| `gio launch` prints usage or `gtk-launch` is missing | These launcher commands were unavailable on the tested Buster image. Use the icon or the system PyGObject check above. |
| APT says a repository cannot be updated securely | Inspect the preceding error. The observed cause was a missing Buster Release file at the old URL, fixed by the signed legacy repository; do not disable verification. |

## Sources

- [Python 3.12.16 source release](https://www.python.org/downloads/release/python-31216/)
- [Python on Unix and altinstall](https://docs.python.org/3.12/using/unix.html)
- [Raspberry Pi OS package and Python environment guidance](https://www.raspberrypi.com/documentation/computers/os.html)
- [Raspbian legacy repository migration discussion](https://forums.raspberrypi.com/viewtopic.php?t=237469)

## Portable desktop installer and zoom actions

After installing the app in its virtual environment, run from the checkout:

```sh
.venv312/bin/python tools/install_linux_shortcut.py
```

Use `.venv/bin/python` instead if that is your environment name. This Linux installer takes no options and opens no telescope connection. It derives paths locally; rerun it if you move the checkout or environment. It installs a launcher for the source installation, not a standalone binary.

The preferred shortcut name is **Celestron Telescope Network Control**, with WiFi on the telescope icon. Default launch uses zoom controls at 80%. Right-click choices select 80% with zoom controls, 100% with zoom controls, or 100% without the zoom menu. Close the existing app first; each action starts a new process. Standard Desktop Actions and PCManFM custom actions are installed; `SelectionCount==1` is intentional. Menu support depends on the desktop. Existing launchers are backed up under the user's state directory. Launch logs go to `cosmos90gt/desktop.log` under that state directory.

Copy `docs/TELESCOPE-CONTROL-START-HERE.md` into your desktop folder as `Telescope-Control-Start-Here.txt`. See the [runtime reference](RUNTIME-OPTIONS.md), [icon formats](../assets/icons/README.md), and [KStars versions/workarounds](engineering/2026-11-16-pi-kstars-validation.md). INDI/KStars are optional companions, not prerequisites for this app's own motor control.
