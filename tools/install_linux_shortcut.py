#!/usr/bin/env python3
"""Install Linux desktop launch actions using this checkout and interpreter.

Run with the application's virtual-environment Python. No telescope connection
is opened. Existing entries are backed up outside the desktop. Paths are derived
from this script, the interpreter and the current user's XDG directories.
"""
import datetime
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def desktop_quote(value):
    """Quote one Desktop Entry Exec argument, including literal percent signs."""
    text = str(value).replace('%', '%%')
    for char in ('\\', '"', '`', '$'):
        text = text.replace(char, '\\' + char)
    return '"' + text + '"'


def main():
    if not sys.platform.startswith('linux'):
        raise SystemExit('This installer is for Linux desktops; use the shared icon assets on other systems.')
    repo = Path(__file__).resolve().parents[1]
    home = Path.home()
    data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
    state = Path(os.environ.get('XDG_STATE_HOME', home / '.local/state')) / 'cosmos90gt'
    desktop = home / 'Desktop'
    if shutil.which('xdg-user-dir'):
        found = subprocess.check_output(['xdg-user-dir', 'DESKTOP'], text=True).strip()
        if found:
            desktop = Path(found)
    backup = state / 'desktop-backups' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    launcher = home / '.local/bin/launch-cosmos90gt'
    icon = data / 'icons/cosmos90gt-wifi.svg'
    for folder in (desktop, backup, launcher.parent, icon.parent, data / 'applications', data / 'file-manager/actions'):
        folder.mkdir(parents=True, exist_ok=True)
    for label, path in (('launcher', launcher), ('desktop', desktop / 'Cosmos90GT.desktop'),
                        ('application', data / 'applications/Cosmos90GT.desktop')):
        if path.exists():
            shutil.copy2(path, backup / label)
    shutil.copy2(repo / 'assets/icons/cosmos90gt.svg', icon)
    # Do not resolve a venv interpreter symlink to the underlying system Python.
    python = Path(sys.executable).absolute()
    launcher.write_text(
        '#!/bin/sh\nset -eu\ncd ' + shlex.quote(str(repo)) + '\n'
        'mkdir -p ' + shlex.quote(str(state)) + '\n'
        'if [ "$#" -eq 0 ]; then set -- --zoom-controls --ui-scale 0.8; fi\n'
        'exec ' + shlex.quote(str(python)) + ' -m skyqlink_setup "$@" >> '
        + shlex.quote(str(state / 'desktop.log')) + ' 2>&1\n', encoding='utf-8')
    launcher.chmod(0o755)
    choices = [('Compact', 'Open with zoom controls at 80%', '--zoom-controls --ui-scale 0.8'),
               ('Zoom', 'Open with zoom controls at 100%', '--zoom-controls --ui-scale 1.0'),
               ('Standard', 'Open standard view without zoom menu', '--ui-scale 1.0')]
    command = desktop_quote(launcher)
    entry = ('[Desktop Entry]\nVersion=1.0\nType=Application\n'
             'Name=Celestron Telescope Network Control\n'
             'Comment=Telescope Wi-Fi control; right-click for display launch options\n'
             f'Exec={command}\nPath={repo}\nIcon={icon}\nTerminal=false\n'
             'Categories=Education;Astronomy;\nStartupNotify=false\nActions=Compact;Zoom;Standard;\n')
    for key, name, args in choices:
        entry += f'\n[Desktop Action {key}]\nName={name}\nExec={command} {args}\n'
        action = data / 'file-manager/actions' / f'cosmos90gt-{key.lower()}.desktop'
        action.write_text('[Desktop Entry]\nType=Action\n'
                          f'Name={name}\nProfiles=default;\n\n[X-Action-Profile default]\n'
                          f'Basenames=Cosmos90GT.desktop;\nSelectionCount==1\nExec={command} {args}\n',
                          encoding='utf-8')
    for path in (desktop / 'Cosmos90GT.desktop', data / 'applications/Cosmos90GT.desktop'):
        path.write_text(entry, encoding='utf-8')
        path.chmod(0o755)
    print('Installed:', desktop / 'Cosmos90GT.desktop')
    print('Backups:', backup)
    print('Right-click menu visibility depends on the desktop; reopen its menu or refresh PCManFM if needed.')


if __name__ == '__main__':
    main()
