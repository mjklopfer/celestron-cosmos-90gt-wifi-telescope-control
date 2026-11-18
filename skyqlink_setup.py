#!/usr/bin/env python3
"""Python/Tk interface for Celestron Cosmos 90GT Telescope Wi-Fi Control.

Worker services own network operations and publish events; only the Tk thread
updates widgets. Network-mode controls do not join Wi-Fi or move the mount switch."""
import argparse
import math
import datetime as dt
from pathlib import Path
import queue
import threading
import time
import json
import csv
import io
import tkinter as tk
from tkinter import ttk, messagebox, font, filedialog
from tkinter.scrolledtext import ScrolledText
from setup_backend import operate, validate_endpoint, validate_port
from wifly_configure import make_plan, SECURITY
from motor_settings import motor_settings, parse_degrees, parse_backlash
from motor_control import MotorController, AXES, relative_counts, relative_angle
from discover_modules import scan_modules
from diagnostics import diagnose
from time_settings import configure_time, test_time_server, COMMON_TIME_SERVERS, UptimeEvidence
from recover_link import recover
from bridge_mode import Bridge
from export_recording import export_recording, recording_bounds, parse_timestamp
from network_info import network_interfaces, open_directory
from ui_zoom import UiZoom, scale_argument
from telescope_calibration import load_config, measured_rate, estimate_seconds, DEFAULT_CONFIG, profile_label, identify_profile, save_config, profile_keymap

APP_TITLE = 'Celestron Cosmos 90GT Telescope Wi-Fi Control'
WIFI_SWITCH_HELP = (
    'Physical Wi-Fi mode switch — on the telescope mount, beside its power socket\n'
    'LEFT — Direct / ad hoc: a Celestron Version 1 Wi-Fi telescope provides its own SkyQLink-xx Wi-Fi network. '
    'Connect your computer to that network and use 1.2.3.4:2000.\n'
    'RIGHT — Infrastructure: with router settings saved, the telescope joins that Wi-Fi network. '
    'Connect your computer to the same router LAN and use the telescope’s assigned IP, port 2000.\n'
    'After saving router settings: on Motor control click STOP, then Disconnect if connected; switch Control Bridge OFF if running. Power OFF the telescope, '
    'move this physical slider to RIGHT, then power ON. If it is already RIGHT, leave it there. '
    'Discover the telescope’s new IP after it joins the router.\n'
    'The Direct / Infrastructure selector in this app only selects connection settings; '
    'it does not move the physical switch or change your computer’s Wi-Fi. '
    'Version 2 and later Celestron Wi-Fi adapters use Celestron-xxxx network names. The LEFT/RIGHT switch and provisioning instructions here apply to the Version 1 SkyQLink RN-171, not those newer adapters. '
    'Wi-Fi provisioning does not command motor movement.'
)


class BridgeRocker(tk.Canvas):
    """Two-position OFF/ON control with mouse and keyboard operation."""
    def __init__(self, parent, variable, command, compact=False):
        """Create the accessible OFF/ON canvas and watch its BooleanVar."""
        super().__init__(parent, width=184, height=46, highlightthickness=1,
                         highlightbackground='#777777', takefocus=True, background='#30343b')
        self.variable, self.command = variable, command
        self.base_scale = .65 if compact else 1.0
        self.ui_scale = self.base_scale
        self.configure(width=round(184 * self.ui_scale), height=round(46 * self.ui_scale))
        self.trace_id = variable.trace_add('write', lambda *args: self.redraw())
        self.bind('<Button-1>', self.click)
        self.bind('<Left>', lambda event: self.choose(False))
        self.bind('<Right>', lambda event: self.choose(True))
        self.bind('<space>', lambda event: self.choose(not self.variable.get()))
        self.bind('<Return>', lambda event: self.choose(not self.variable.get()))
        self.bind('<FocusIn>', lambda event: self.configure(highlightbackground='#4488ff'))
        self.bind('<FocusOut>', lambda event: self.configure(highlightbackground='#777777'))
        self.redraw()

    def configure(self, *args, **kwargs):
        """Update rocker options and redraw the control."""
        result = super().configure(*args, **kwargs)
        if 'state' in kwargs and hasattr(self, 'variable'):
            self.redraw()
        return result

    def redraw(self):
        """Render the rocker with its current selection and enabled state."""
        self.delete('all')
        enabled = str(self.cget('state')) == 'normal'
        on = self.variable.get()
        scale = self.ui_scale
        for left, label, selected in ((2, 'OFF', not on), (93, 'ON', on)):
            fill = ('#197442' if on else '#8c3434') if selected and enabled else '#454951'
            self.create_rectangle(left * scale, 2 * scale, (left + 89) * scale, 44 * scale, fill=fill,
                                  outline='#dddddd' if selected and enabled else '#666666', width=2)
            self.create_text((left + 44) * scale, 22 * scale, text=label, fill='white' if enabled else '#aaaaaa',
                             font=('TkDefaultFont', max(1, round(14 * scale)), 'bold'))

    def set_scale(self, scale):
        """Resize both the drawing and its pointer hit boundary."""
        self.ui_scale = scale * self.base_scale
        self.configure(width=round(184 * self.ui_scale), height=round(46 * self.ui_scale))
        self.redraw()

    def invoke(self):
        """Toggle the current selection, matching other toggle widgets."""
        return self.choose(not self.variable.get())

    def choose(self, on):
        """Apply an enabled rocker selection and invoke its callback."""
        if str(self.cget('state')) == 'normal' and bool(on) != self.variable.get():
            self.variable.set(bool(on))
            self.command()
        return 'break'

    def click(self, event):
        """Map a pointer position to the rocker’s OFF or ON selection."""
        self.focus_set()
        return self.choose(event.x >= 92 * self.ui_scale)

    def destroy(self):
        """Remove the variable trace before destroying the rocker widget."""
        self.variable.trace_remove('write', self.trace_id)
        super().destroy()


class SetupApp(ttk.Frame):
    def __init__(self, root, operation=operate, motor_factory=MotorController, scanner=scan_modules,
                 diagnostic=diagnose, recovery=recover, bridge_factory=Bridge,
                 ui_scale=1.0, zoom_controls=False):
        """Build the desktop controls and event queue around injectable backend services."""
        # Query Tk's actual window system, not the machine name or Python path.
        # Aqua needs native tabs and shorter control rows; preserve the verified
        # Windows/Linux theme and widget arrangement on all other window systems.
        self.macos_ui = root.tk.call('tk', 'windowingsystem') == 'aqua'
        self.normal_text = (ttk.Style(root).lookup('TLabel', 'foreground') or 'systemLabelColor') if self.macos_ui else '#111111'
        self.muted_text = self.normal_text if self.macos_ui else '#777777'
        shell = ttk.Frame(root)
        shell.pack(fill='both', expand=True)
        canvas = tk.Canvas(shell, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(shell, orient='vertical', command=canvas.yview)
        horizontal = ttk.Scrollbar(shell, orient='horizontal', command=canvas.xview)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)
        scrollbar.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        canvas.grid(row=0, column=0, sticky='nsew')
        canvas.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        super().__init__(canvas, padding=16)
        self.scroll_canvas = canvas
        content = canvas.create_window((0, 0), window=self, anchor='nw')
        self.content_window = content
        canvas.bind('<Configure>', lambda event: self.resize_content())
        self.bind('<Configure>', lambda event: self.resize_content())
        self.root, self.operation = root, operation
        self.events = queue.Queue()
        self.busy = False
        self.motor_factory = motor_factory
        self.scanner = scanner
        self.diagnostic = diagnostic
        self.recovery = recovery
        self.bridge_factory = bridge_factory
        self.bridge = None
        self.bridge_enabled = tk.BooleanVar(value=False)
        self.bridge_status = tk.StringVar(value='Control Bridge is OFF. Follow the setup steps below before switching it ON.')
        self.bridge_bind = tk.StringVar()
        self.bridge_dual = tk.BooleanVar(value=False)
        self.bridge_last_error = None
        self.interface_rows = []
        self.interface_refreshing = False
        self.network_provider = network_interfaces
        self.bridge_listener = None
        self.bridge_upstream_local = None
        self.bridge_endpoint = tk.StringVar(value='Control Bridge is OFF. Select this computer’s network adapter in the table, then switch Control Bridge ON. The IPv4 address and TCP port to enter in your astronomy app will appear here.')
        self.connection_mode = tk.StringVar(value='direct')
        self.last_infrastructure_host = None
        self.mode_help = tk.StringVar(value='Direct / ad hoc: connect this computer to SkyQLink-xx, then use 1.2.3.4:2000.\nThe mode selector chooses connection settings; it does not change the telescope switch or your computer’s Wi-Fi.')
        self.motor = None
        self.motor_ready = False
        self.jogging = False
        self.current_motion_axis = None
        self.measuring_motion = False
        self.last_motor_error = None
        self.connect_request_active = False
        self.connect_recovery_attempted = False
        self.reconnect_after_recovery = False
        self.auto_recover = tk.BooleanVar(value=True)
        self.keyboard_direction = None
        self.keyboard_release_id = None
        self.keymap = {}
        self.keyboard_help = tk.StringVar(value='')
        self.keyboard_enabled = tk.BooleanVar(value=False)
        self.keyboard_status = tk.StringVar(value='Keyboard control OFF')
        self.held = False
        self.drive_mode = tk.StringVar(value='hold')
        self.discovered = []
        self.selected_module = tk.StringVar()
        self.closing = False
        self.last_positions = {}
        self.position_references = {}
        self.reference_inputs = {axis: tk.StringVar(value="0") for axis in AXES}
        self.idle_release = tk.StringVar(value='30 seconds')
        self.motor_heartbeat = tk.BooleanVar(value=True)
        self.motor_heartbeat_interval = tk.StringVar(value='1')
        self.motor_connection_help = tk.StringVar()
        self.speed = tk.StringVar(value='6')
        self.duration = tk.StringVar(value='0.5')
        self.motor_status = tk.StringVar(value='Disconnected')
        self.motion_status = tk.StringVar(value='No movement measured yet')
        self.values = {axis: {field: tk.StringVar(value='—') for field in
                             ('encoder', 'angle', 'relative', 'firmware', 'age', 'before', 'after',
                              'delta_counts', 'delta_degrees', 'stationary', 'referenced')} for axis in AXES}
        self.log_directory = None
        self.host = tk.StringVar(value='1.2.3.4')
        self.port = tk.StringVar(value='2000')
        self.ssid = tk.StringVar()
        self.password = tk.StringVar()
        self.provision_ssid_readback = tk.StringVar(value='Not read yet — click Connect & Read Settings.')
        self.provision_mode_readback = tk.StringVar(value='Configuration: not read yet')
        self.security = tk.StringVar(value='WPA2-Personal (AES)')
        self.provision_notice = tk.StringVar(value='You can configure this adapter through either direct/ad hoc Wi-Fi or its current infrastructure IP. '
            'Uploading replaces the stored SSID, password and security settings so it can join a different network. '
            'A factory reset is not required. Restart afterward and discover its new IP.')
        self.status = tk.StringVar(value='Ready. Choose a tab below: Motor control, Control Bridge, Diagnostics or Wi-Fi provisioning.')
        self.show_password = tk.BooleanVar(value=False)
        root.title(APP_TITLE)
        window_height = min(950, root.winfo_screenheight() - 90)
        root.geometry(f'{min(980, root.winfo_screenwidth() - 40)}x{window_height}')
        root.minsize(480, 320)
        self.section_heading_font = font.Font(root=root, family=font.nametofont('TkDefaultFont', root=root).actual('family'), size=12, weight='bold')
        ttk.Style(root).configure('TLabelframe.Label', font=self.section_heading_font)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(6, weight=1)
        ttk.Label(self, text=APP_TITLE, font=('TkDefaultFont', 20, 'bold')).grid(sticky='w')
        ttk.Label(self, text='Celestron Wi-Fi Control Version 1 - SkyQLink RN-171', foreground=self.normal_text if self.macos_ui else '#666666').grid(row=1, sticky='w', pady=(2, 8))

        connection = ttk.LabelFrame(self, text='Telescope connection', padding=8)
        connection.grid(row=2, sticky='ew')
        connection.columnconfigure(1, weight=1)
        ttk.Label(connection, text='Telescope Wi-Fi interface IP address').grid(row=0, column=0, sticky='w', padx=(0, 12))
        self.host_entry = ttk.Entry(connection, textvariable=self.host)
        self.host_entry.grid(row=0, column=1, sticky='ew')
        ttk.Label(connection, text='Port').grid(row=0, column=2, padx=(18, 10))
        self.port_entry = ttk.Entry(connection, textvariable=self.port, width=8)
        self.port_entry.grid(row=0, column=3)
        ttk.Label(connection, textvariable=self.mode_help,
                  wraplength=830).grid(row=1, column=0, columnspan=4, sticky='w', pady=(8, 0))
        presets = ttk.Frame(connection)
        presets.grid(row=2, column=0, columnspan=4, sticky='w', pady=(8, 0))
        self.direct_button = ttk.Radiobutton(presets, text='Direct / ad hoc', variable=self.connection_mode,
                                             value='direct', command=lambda: self.preset(False))
        self.direct_button.grid(row=0, column=0, sticky='w') if self.macos_ui else self.direct_button.pack(side='left')
        self.home_button = ttk.Radiobutton(presets, text='Infrastructure / shared router Wi-Fi' if self.macos_ui else 'Infrastructure: Telescope and computer on a common access point', variable=self.connection_mode,
                                           value='infrastructure', command=lambda: self.preset(True))
        self.home_button.grid(row=0, column=1, sticky='w', padx=(12, 0)) if self.macos_ui else self.home_button.pack(side='left', padx=8)
        self.scan_button = ttk.Button(presets, text='Discover SkyQLink / Celestron Modules', command=self.scan_lan)
        self.scan_button.grid(row=1, column=0, columnspan=2, sticky='w', pady=(8, 0)) if self.macos_ui else self.scan_button.pack(side='left', padx=8)
        self.scan_started = None
        self.scan_tick_id = None
        self.scan_indicator = ttk.Label(connection, text='● Discovery idle', anchor='w') if self.macos_ui else tk.Label(connection, text='● Discovery idle', foreground='#666666', anchor='w')
        self.scan_indicator.grid(row=4, column=0, columnspan=4, sticky='w', pady=(4, 0))
        self.module_box = ttk.Combobox(connection, textvariable=self.selected_module, state='disabled')
        self.module_box.grid(row=3, column=0, columnspan=4, sticky='ew', pady=(8, 0))
        self.module_box.bind('<<ComboboxSelected>>', lambda event: self.select_module())

        self.mode_tab_font = font.Font(root=root, family=font.nametofont('TkDefaultFont', root=root).actual('family'), size=12, weight='bold')
        self.mode_tab_padding = (16, 10)
        style = ttk.Style(root)
        # Use a colorable tab element without changing the app's native theme.
        if not self.macos_ui and 'clam' in style.theme_names():
            if 'ModeNotebook.tab' not in style.element_names():
                style.element_create('ModeNotebook.tab', 'from', 'clam', 'Notebook.tab')
            layout = style.layout('TNotebook.Tab')
            layout = [('ModeNotebook.tab' if name == 'Notebook.tab' else name, options)
                      for name, options in layout]
            style.layout('Mode.TNotebook.Tab', layout)
        # Do not mix clam-colored tabs into Aqua: in dark appearance that
        # combines mismatched colors and geometry. Native tabs inherit macOS
        # appearance and selection contrast. Other hosts keep the existing map.
        if self.macos_ui:
            style.configure('Mode.TNotebook', tabposition='n')
            style.configure('Mode.TNotebook.Tab', font=self.mode_tab_font, padding=self.mode_tab_padding)
        else:
            style.configure('Mode.TNotebook.Tab', font=self.mode_tab_font,
                            padding=self.mode_tab_padding, background='#e5e7eb', foreground='#263445')
            style.map('Mode.TNotebook.Tab',
                      background=[('disabled', '#eeeeee'), ('selected', '#c9e0ff'), ('active', '#deebfc')],
                      foreground=[('disabled', '#777777'), ('selected', '#102f55')])
        self.tabs = ttk.Notebook(self, style='Mode.TNotebook')
        self.tabs.grid(row=3, sticky='nsew', pady=(12, 0))
        self.motor_tab = ttk.Frame(self.tabs, padding=8)
        self.provision_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.motor_tab, text='Motor control')
        self.diagnostic_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.diagnostic_tab, text='Diagnostics')
        self.bridge_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.bridge_tab, text='Control Bridge')
        self.tabs.insert(1, self.bridge_tab)
        self.tabs.add(self.provision_tab, text='Wi-Fi provisioning')
        self.build_bridge_tab()
        self.build_diagnostics_tab()
        self.provision_tab.columnconfigure(0, weight=1)
        self.build_motor_tab()

        wifi = ttk.LabelFrame(self.provision_tab, text='Infrastructure / Router Wi-Fi Settings', padding=12)
        wifi.grid(row=0, sticky='ew')
        wifi.columnconfigure(1, weight=1)
        self.inputs = [self.host_entry, self.port_entry, self.direct_button, self.home_button, self.scan_button]
        for row, (label, variable) in enumerate((('Network name / SSID', self.ssid), ('Password', self.password))):
            ttk.Label(wifi, text=label).grid(row=row, column=0, sticky='w', padx=(0, 14), pady=5)
            entry = ttk.Entry(wifi, textvariable=variable, show='•' if row == 1 else '')
            entry.grid(row=row, column=1, sticky='ew', pady=5)
            self.inputs.append(entry)
            if row == 1:
                self.password_entry = entry
        self.show = ttk.Checkbutton(wifi, text='Show password', variable=self.show_password,
                                    command=self.refresh_password)
        self.show.grid(row=1, column=2, padx=(10, 0))
        ttk.Label(wifi, text='Security').grid(row=2, column=0, sticky='w', pady=5)
        self.security_box = ttk.Combobox(wifi, textvariable=self.security, values=list(SECURITY), state='readonly')
        self.security_box.grid(row=2, column=1, sticky='ew', pady=5)
        self.security_box.bind('<<ComboboxSelected>>', lambda event: self.refresh_password())
        ttk.Label(wifi, text='2.4 GHz networks. WPA2-Personal (AES) recommended. WPA3 and enterprise are unsupported.',
                  wraplength=700).grid(row=3, column=0, columnspan=3, sticky='w', pady=(8, 0))
        ttk.Label(wifi, textvariable=self.provision_notice, wraplength=780).grid(row=4, column=0, columnspan=3,
                                                                              sticky='w', pady=(12, 0))

        readback = ttk.LabelFrame(self.provision_tab, text='Settings read from telescope', padding=10)
        readback.grid(row=3, sticky='ew', pady=(10, 0))
        ttk.Label(readback, textvariable=self.provision_mode_readback).pack(anchor='w')
        ttk.Label(readback, text='Stored network name (SSID):').pack(anchor='w', pady=(6, 0))
        ttk.Label(readback, textvariable=self.provision_ssid_readback,
                  font=self.section_heading_font, wraplength=780).pack(anchor='w')

        buttons = ttk.Frame(self.provision_tab)
        buttons.grid(row=1, sticky='ew', pady=(16, 0))
        self.read_button = ttk.Button(buttons, text='Connect & Read Settings', command=lambda: self.start(False))
        self.read_button.pack(side='left')
        self.upload_button = ttk.Button(buttons, text='Upload & Save Wi-Fi Settings…', command=lambda: self.start(True))
        self.upload_button.pack(side='left', padx=10)
        ttk.Label(self.provision_tab, text='This provisioning page supports Celestron Version 1 Wi-Fi: SkyQLink RN-171 / 2.40-CEL. Version 2 and later use Celestron-xxxx network names; provisioning support for those adapters is future work. Connect & Read Settings reads the stored SSID and network settings through either connection mode; it does not change them. The readback appears below, with full command replies in the Transfer log. It does not fill in or reveal the saved password. Credential fields are redacted before display and log saving; this app does not keep a recoverable password in its provisioning logs. Show password reveals only what you type. Recovery through another tool has not been verified for this firmware.',
                  wraplength=780).grid(row=2, sticky='w', pady=(8, 0))
        provisioning_help = ttk.LabelFrame(self.provision_tab, text='Celestron Version 1 Wi-Fi — SkyQLink RN-171 / 2.40-CEL: connection and switch instructions', padding=10)
        provisioning_help.grid(row=4, sticky='ew', pady=10)
        self.provision_direct_help = ttk.Label(provisioning_help, wraplength=790, text='LEFT SWITCH POSITION — Direct / ad hoc (initial setup, reset unit or recovery)\n1. With telescope power off, set the physical Wi-Fi slider LEFT; power on. Join SkyQLink-xx from this computer.\n2. Select Direct / ad hoc above; use 1.2.3.4, port 2000. Disconnect other controllers and click Connect & Read Settings.\n3. Enter the target 2.4 GHz network name, security and password; click Upload & Save and check the verified save result.\n4. Power off, move the slider RIGHT, then power on. Join the same access point/LAN from this computer, select Infrastructure, and Discover SkyQLink / Celestron Modules. Read settings again at the discovered address.\nA factory reset may erase saved credentials. This application does not perform a factory reset.')
        self.provision_direct_help.pack(anchor='w', pady=(0, 10))
        self.provision_infrastructure_help = ttk.Label(provisioning_help, wraplength=790, text='RIGHT SWITCH POSITION — Infrastructure (read settings or change networks)\n1. The physical slider must be RIGHT. If changing its position, turn telescope power OFF first, move the slider, then power ON. Connect this computer to the telescope’s current access point/LAN. Select Infrastructure and discover its current address.\n2. Click Disconnect on Motor control if connected; switch Control Bridge OFF if running. Disconnect the telescope in other controlling apps. Read settings, enter the NEW network credentials, then Upload & Save.\n3. After the save is verified, power-cycle with the slider still RIGHT. The old address/connection may disappear.\n4. Connect this computer to the new access point/LAN, discover the new telescope address, and read back settings.\nNo ad hoc switch or factory reset is needed when the current network connection works. If access is lost, use the Direct / ad hoc procedure to recover access.')
        self.provision_infrastructure_help.pack(anchor='w')
        network_note = ttk.LabelFrame(self.provision_tab, text='Note — Wi-Fi addresses and ports', padding=10)
        network_note.grid(row=5, sticky='ew', pady=(0, 10))
        ttk.Label(network_note, text='Version 1 — SkyQLink RN-171: Direct / ad hoc normally uses 1.2.3.4, TCP port 2000 for telescope commands. WiFly settings are read through command mode on that same TCP connection. Do not assume newer-adapter management or discovery ports are available on Version 1.\n\nVersion 2 and later — Celestron Wi-Fi / SkyPortal: the established direct-connect convention is also 1.2.3.4, TCP port 2000 for telescope commands. TCP 3000 is used for configuration/management; UDP 55555 (five 5s, not 5555 or 5000) is used for discovery advertisements. Availability depends on the adapter and firmware; these are reference defaults, not a guarantee for every future model.\n\nInfrastructure: use the adapter’s actual address assigned by your router, for example 192.168.1.x or 10.0.0.x; the subnet and address depend on your network and may change. Do not use 1.2.3.4 unless that is the address actually configured.\n\nControl Bridge: control software connects to THIS COMPUTER’s selected local-network IP, normally TCP 2000. The bridge also provides TCP 3000 management and UDP 55555 discovery; it forwards telescope commands to SkyQLink on TCP 2000. UDP 123 is for optional WiFly time-server requests, not telescope control or discovery.', wraplength=790, justify='left').pack(anchor='w')
        def highlight_provisioning(*args):
            direct = self.connection_mode.get() == 'direct'
            self.provision_direct_help.configure(foreground=self.normal_text if direct else self.muted_text)
            self.provision_infrastructure_help.configure(foreground=self.muted_text if direct else self.normal_text)
        self.connection_mode.trace_add('write', highlight_provisioning)
        highlight_provisioning()
        status_area = ttk.LabelFrame(self, text='Current operation status', padding=8)
        status_area.grid(row=5, sticky='ew', pady=(0, 10))
        ttk.Label(status_area, textvariable=self.status, wraplength=760).pack(side='left', fill='x', expand=True)
        self.copy_button(status_area, self.status.get, 'Copy status message').pack(side='right', padx=4)
        self.progress = ttk.Progressbar(status_area, mode='indeterminate', length=100)

        transfer = ttk.LabelFrame(self, text='Transfer log — credentials redacted', padding=8)
        transfer.grid(row=6, sticky='nsew')
        transfer.rowconfigure(0, weight=1)
        transfer.columnconfigure(0, weight=1)
        self.console = ScrolledText(transfer, height=6, wrap='word', state='disabled',
                                   font=('TkFixedFont', 11), background='#17212b', foreground='#e7edf3',
                                   insertbackground='white', relief='flat')
        self.console.grid(sticky='nsew')
        self.copy_button(transfer, lambda: self.console.get('1.0', 'end-1c'), 'Copy transfer log').grid(row=1, sticky='w', pady=4)
        footer = ttk.Frame(self)
        footer.grid(row=7, sticky='ew', pady=(10, 0))
        self.logs_button = ttk.Button(footer, text='Open Saved Logs', state='disabled', command=self.open_logs)
        self.logs_button.pack(side='left')
        self.clear_button = ttk.Button(footer, text='Clear displayed log…', command=self.clear)
        self.clear_button.pack(side='left', padx=10)
        recovery_option = ttk.LabelFrame(self, text='Motor connection troubleshooting', padding=6)
        recovery_option.grid(row=8, sticky='ew', pady=6)
        self.auto_recover_button = ttk.Checkbutton(recovery_option,
            text='Allow one Wi-Fi module restart if Connect Motors fails', variable=self.auto_recover)
        self.auto_recover_button.pack(anchor='w')
        ttk.Label(recovery_option, text='Use this option if you click Connect Motors but the program receives no valid response from one or both motors. First, leave the telescope powered on and disconnect it in other control apps. When this option is checked, a failed connection check can restart the identified SkyQLink Wi-Fi module once, then read both motor positions and try connecting again. The restart keeps saved Wi-Fi settings but can discard unsaved changes. It does not reset the telescope to factory settings or send a movement command. If the telescope’s IP address changes, click Discover SkyQLink / Celestron Modules. Uncheck this option to prevent automatic restarts.', wraplength=820).pack(anchor='w')
        self.switch_help_label = ttk.Label(self.provision_tab, text=WIFI_SWITCH_HELP,
                                          wraplength=820)
        self.switch_help_label.grid(row=2, sticky='w', pady=(12, 0))
        self.append('Ready. Disconnect other connected apps (for example CFM or CPWI) before connecting here; the adapter shares one command stream.')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Escape>', lambda event: self.stop_motors())
        root.bind('<KeyPress>', self.motor_key_press, add='+')
        root.bind('<KeyRelease>', self.motor_key_release, add='+')
        root.bind('<ButtonRelease-1>', self.focus_motor_shortcuts, add='+')
        self.tabs.bind('<<NotebookTabChanged>>', lambda event: self.stop_motors() if self.keyboard_direction else None, add='+')
        self.tabs.bind('<<NotebookTabChanged>>', lambda event: self.resize_content(), add='+')
        root.bind('<ButtonRelease-1>', lambda event: self.release_direction(), add='+')
        root.bind('<FocusOut>', lambda event: root.after(50, self.stop_if_unfocused))
        root.bind('<MouseWheel>', self.scroll_window, add='+')
        root.bind('<Button-4>', self.scroll_window, add='+')
        root.bind('<Button-5>', self.scroll_window, add='+')
        self.poll_id = self.after(100, self.poll)
        self.zoom = None
        if zoom_controls or ui_scale != 1.0:
            self.zoom = UiZoom(self, controls=zoom_controls)
            self.zoom.apply(ui_scale)

    def resize_content(self):
        """Expand to the viewport, but scroll instead of clipping wide controls."""
        if hasattr(self, 'tabs') and self.tabs.select():
            page = self.nametowidget(self.tabs.select())
            height = page.winfo_reqheight()
            if height > 1 and int(self.tabs.cget('height') or 0) != height:
                self.tabs.configure(height=height)
        self.scroll_canvas.itemconfigure(self.content_window,
                                         width=max(self.scroll_canvas.winfo_width(), self.winfo_reqwidth()))
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox('all'))

    def scroll_window(self, event):
        # Reply text, transfer text and the endpoint table retain their own scroll.
        """Scroll the main form while leaving nested log/table scrolling independent."""
        if event.widget in (self.console, self.diagnostic_details, self.diagnostic_rows,
                            self.bridge_console, self.interface_table):
            return
        delta = getattr(event, 'delta', 0)
        if getattr(event, 'num', None) in (4, 5):
            delta = 120 if event.num == 4 else -120
        if delta:
            units = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
            self.scroll_canvas.yview_scroll(units, 'units')

    def build_motor_tab(self):
        """Create manual movement controls and encoder readback fields."""
        tab = self.motor_tab
        tab.columnconfigure(1, weight=1)
        controls = ttk.Frame(tab)
        controls.grid(row=0, column=0, columnspan=2, sticky='ew')
        self.motor_connect_button = ttk.Button(controls, text='Connect Motors', command=self.connect_motors)
        self.motor_connect_button.pack(side='left')
        self.motor_disconnect_button = ttk.Button(controls, text='Disconnect', command=self.disconnect_motors, state='disabled')
        self.motor_disconnect_button.pack(side='left', padx=8)
        self.motor_status_box = tk.Frame(controls, background='#e2ebf5', highlightbackground='#97abc2', highlightthickness=1, padx=10, pady=6)
        self.motor_status_box.pack(side='left', padx=12, fill='x', expand=True)
        tk.Label(self.motor_status_box, text='Connection status:', background='#e2ebf5', foreground='#172b44', font=('TkDefaultFont', 10, 'bold')).pack(side='left', padx=(0, 8))
        tk.Label(self.motor_status_box, textvariable=self.motor_status, background='#e2ebf5', foreground='#172b44', wraplength=490, anchor='w', justify='left').pack(side='left', fill='x', expand=True)

        pad = ttk.LabelFrame(tab, text='Four-direction motor control', padding=8)
        pad.grid(row=1, column=0, sticky='nsew', padx=(0, 12), pady=(12, 0))
        self.jog_buttons = []
        for text, row, col, axis, direction in (
                ('Up / EL +', 0, 1, 0x11, 1), ('Left / AZ −', 1, 0, 0x10, -1),
                ('Right / AZ +', 1, 2, 0x10, 1), ('Down / EL −', 2, 1, 0x11, -1)):
            button = ttk.Button(pad, text=text, command=lambda a=axis, d=direction: self.timed_direction(a, d), state='disabled')
            button.bind('<ButtonPress-1>', lambda event, a=axis, d=direction: self.press_direction(a, d))
            button.bind('<ButtonRelease-1>', lambda event: self.release_direction())
            button.bind('<Leave>', lambda event: self.release_direction())
            button.bind('<KeyPress-space>', lambda event, a=axis, d=direction: self.press_direction(a, d))
            button.bind('<KeyRelease-space>', lambda event: self.release_direction())
            button.grid(row=row, column=col, padx=3, pady=4)
            self.jog_buttons.append(button)
        self.stop_button = ttk.Button(pad, text='STOP', command=self.stop_motors, state='disabled')
        self.stop_button.grid(row=1, column=1, padx=3, pady=4)
        ttk.Label(pad, text='Speed (1–9)').grid(row=3, column=0, sticky='w', pady=(10, 4))
        self.speed_box = ttk.Combobox(pad, textvariable=self.speed, values=list(range(1, 10)), state='readonly', width=5)
        self.speed_box.grid(row=3, column=1, sticky='w', pady=(10, 4))
        rate_frame = ttk.Frame(pad)
        rate_frame.grid(row=4, column=0, columnspan=3, sticky='ew', pady=6)
        self.slew_rate_cells = {(axis, rate): tk.StringVar(value='— / —') for axis in AXES for rate in range(1, 10)}
        self.has_slew_rates = False
        self.slew_rates_window = None
        self.calibration_note = tk.StringVar()
        ttk.Label(rate_frame, textvariable=self.calibration_note, wraplength=310, font=('TkDefaultFont', 9)).grid(row=0, columnspan=2, sticky='w')
        self.slew_rates_button = ttk.Button(rate_frame, text='Measured slew rates…', command=self.open_slew_rates, state='disabled')
        self.slew_rates_button.grid(row=1, column=0, sticky='w', pady=4)
        ttk.Button(rate_frame, text='Estimate degree jog…', command=self.open_degree_estimate).grid(row=1, column=1)
        ttk.Button(rate_frame, text='Reload calibration', command=self.reload_calibration).grid(row=2, column=0, sticky='w')
        ttk.Button(rate_frame, text='Profile file details…', command=self.open_profile_details).grid(row=2, column=1, sticky='w', pady=4)
        self.reload_calibration()

        ttk.Label(pad, text='Timed jog duration (seconds)').grid(row=5, column=0, sticky='w')
        self.duration_box = ttk.Combobox(pad, textvariable=self.duration, values=('0.25', '0.5', '1.0', '2.0'), state='readonly', width=5)
        self.duration_box.grid(row=5, column=1, sticky='w')
        ttk.Radiobutton(pad, text='Hold to move', variable=self.drive_mode, value='hold', command=self.stop_motors).grid(row=6, column=0, columnspan=2, sticky='w', pady=(8, 0))
        ttk.Radiobutton(pad, text='Timed jog', variable=self.drive_mode, value='jog', command=self.stop_motors).grid(row=6, column=2, sticky='w', pady=(8, 0))

        self.direct_policy_title = ttk.Label(pad, text='Direct motor connection settings')
        policy = self.direct_policy_frame = ttk.LabelFrame(pad, labelwidget=self.direct_policy_title, padding=4)
        policy.grid(row=7, column=0, columnspan=3, sticky='ew', pady=5)
        ttk.Label(policy, text='Applied on next connection').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 4))
        ttk.Label(policy, text='Idle release').grid(row=1, column=0, sticky='w')
        self.idle_release_box = ttk.Combobox(policy, textvariable=self.idle_release,
            values=('10 seconds', '20 seconds', '30 seconds', '1 minute', '2 minutes', '5 minutes', 'Never'), state='readonly', width=12)
        self.idle_release_box.grid(row=1, column=1, sticky='w')
        self.idle_release_box.bind('<<ComboboxSelected>>', lambda event: self.update_controls())
        self.motor_heartbeat_box = ttk.Checkbutton(policy, text='Keep connection alive',
            variable=self.motor_heartbeat, command=self.update_controls)
        self.motor_heartbeat_box.grid(row=2, column=0, sticky='w')
        self.motor_heartbeat_box_interval = ttk.Spinbox(policy, from_=1, to=300,
            textvariable=self.motor_heartbeat_interval, width=7)
        self.motor_heartbeat_box_interval.grid(row=2, column=1, sticky='w')
        ttk.Label(policy, text='seconds (1–300)').grid(row=3, column=1, sticky='w')
        ttk.Label(policy, textvariable=self.motor_connection_help, wraplength=310).grid(
            row=4, column=0, columnspan=2, sticky='w', pady=3)

        readout = ttk.LabelFrame(tab, text='Motor values', padding=8)
        readout.grid(row=1, column=1, sticky='nsew', pady=(12, 0))
        for column, label in enumerate(('Value', 'Azimuth', 'Elevation')):
            ttk.Label(readout, text=label, font=('TkDefaultFont', 12, 'bold')).grid(row=0, column=column, sticky='w', padx=(0, 14), pady=(0, 8))
        for row, (field, label) in enumerate((('encoder', 'Encoder counts'), ('angle', 'Raw encoder angle'),
                                             ('relative', 'Change since connection'), ('referenced', 'Angle with local offset'), ('firmware', 'Firmware'),
                                             ('age', 'Time since last reading'), ('before', 'Before jog'),
                                             ('after', 'After jog'), ('delta_counts', 'Jog change (counts)'),
                                             ('delta_degrees', 'Jog change (degrees)'), ('stationary', 'Stop check')), 1):
            ttk.Label(readout, text=label, font=('TkDefaultFont', 11)).grid(row=row, column=0, sticky='w', pady=2, padx=(0, 12))
            for column, axis in enumerate(AXES, 1):
                ttk.Label(readout, textvariable=self.values[axis][field], font=('TkFixedFont', 11)).grid(row=row, column=column, sticky='w', padx=(0, 12))
        self.copy_button(readout, self.motor_output, 'Copy motor table').grid(row=12, columnspan=3, sticky='w', pady=5)
        ttk.Label(tab, text='Select Hold to move. Move the pointer over an on-screen direction button, then press and hold the left mouse button to move the telescope. Release the mouse button to stop. With the main program window active, press the Esc key to stop both motors. Encoder angles are raw motor positions converted to degrees. They do not show the telescope’s aligned sky-pointing azimuth/elevation or the coordinates of a celestial object.',
                  wraplength=780).grid(row=2, column=0, columnspan=2, sticky='w', pady=(10, 0))
        ttk.Label(tab, textvariable=self.motion_status, wraplength=780,
                  font=('TkDefaultFont', 12, 'bold')).grid(row=3, column=0, columnspan=2, sticky='w', pady=8)

        self.reference_current = {axis: tk.StringVar(value='—') for axis in AXES}
        self.reference_delta = {axis: tk.StringVar(value='—') for axis in AXES}
        for axis in AXES:
            self.reference_inputs[axis].trace_add('write', lambda *_args, a=axis: self.refresh_reference_preview(a))

        ttk.Label(pad, text='Keyboard control').grid(row=8, column=0, sticky='w', pady=(8, 0))
        self.keyboard_toggle = BridgeRocker(pad, variable=self.keyboard_enabled,
                                           command=self.toggle_keyboard_control, compact=True)
        self.keyboard_toggle.grid(row=8, column=1, columnspan=2, sticky='w', pady=(8, 0))
        ttk.Label(pad, textvariable=self.keyboard_status, wraplength=320).grid(row=9, column=0, columnspan=3, sticky='w')
        ttk.Label(pad, textvariable=self.keyboard_help, wraplength=320).grid(row=10, column=0, columnspan=3, sticky='w', pady=4)
        self.refresh_profile_keymap()

        self.motor_settings_window = None
        self.controller_fields = {axis: {key: tk.StringVar(value='0' if key.startswith('delta') else '')
            for key in ('angle', 'positive', 'negative', 'delta_positive', 'delta_negative')} for axis in AXES}
        self.controller_readout = {axis: tk.StringVar(value='Not read. Press Read current values for this axis.') for axis in AXES}
        self.controller_history = {axis: tk.StringVar(value='No change applied in this app session.') for axis in AXES}
        self.controller_reads = {}
        self.local_history = {axis: tk.StringVar(value='No local reference applied in this session.') for axis in AXES}
        self.last_local_reference = {}
        self.reference_poll_pending = set()
        self.motor_setting_status = tk.StringVar(value='To read hardware settings, click Disconnect on the Motor control tab if connected, and switch Control Bridge OFF if running. Leave the telescope powered on.')
        self.motor_settings_button = ttk.Button(tab, text='Controller Angle / Backlash Settings…', command=self.open_motor_settings)
        self.motor_settings_button.grid(row=6, column=0, columnspan=2, sticky='w', pady=6)
        for child in tab.grid_slaves():
            child.grid_configure(row=int(child.grid_info()['row']) + 1)
        self.bridge_jog_requested = tk.BooleanVar(value=False)
        self.bridge_jog_active = False
        self.bridge_jog_ready = False
        self.bridge_jog_note = tk.StringVar(value='Bridge jogging is available only while Control Bridge is ON.')
        self.bridge_jog_box = tk.Frame(tab, background='#fff0c2', padx=8, pady=6)
        self.bridge_jog_box.grid(row=0, columnspan=2, sticky='ew')
        tk.Label(self.bridge_jog_box, text='Enable local jogging through bridge',
                 background='#fff0c2', foreground='#513800', font=('TkDefaultFont', 11, 'bold')).pack(anchor='w')
        self.bridge_jog_switch = BridgeRocker(self.bridge_jog_box, variable=self.bridge_jog_requested,
                                             command=self.toggle_bridge_jog, compact=True)
        self.bridge_jog_switch.pack(anchor='w')
        tk.Label(self.bridge_jog_box, textvariable=self.bridge_jog_note, background='#fff0c2',
                 foreground='#513800', wraplength=800, justify='left').pack(anchor='w')
        self.bridge_jog_box.grid_remove()
        self.bridge_tab_mark = tk.PhotoImage(master=self.root, width=12, height=12)
        self.bridge_tab_mark.put('#e5a329', to=(0, 0, 12, 12))

    def apply_bridge_background_reads(self):
        try:
            heartbeat_interval = float(self.bridge_heartbeat_interval.get())
            monitor_interval = float(self.bridge_monitor_interval.get())
            if not math.isfinite(heartbeat_interval) or not 1 <= heartbeat_interval <= 300:
                raise ValueError('Keep-alive interval must be 1–300 seconds')
            if not math.isfinite(monitor_interval) or not .2 <= monitor_interval <= 300:
                raise ValueError('Motor-position interval must be 0.2–300 seconds')
            if self.bridge is not None:
                self.bridge.configure_background_reads(self.bridge_heartbeat.get(), heartbeat_interval,
                                                       self.bridge_monitor.get(), monitor_interval)
            self.bridge_background_status.set(
                ('Heartbeat ON after ' + f'{heartbeat_interval:g}s quiet' if self.bridge_heartbeat.get() else 'Heartbeat OFF') + '; ' +
                (f'position recording ON, {monitor_interval:g}s sample interval' if self.bridge_monitor.get() else 'position recording OFF') + '.')
        except (ValueError, TypeError) as error:
            self.bridge_background_status.set(f'Not applied: {error}. Use heartbeat 1–300s and recording 0.2–300s, then click Apply intervals.')

    def toggle_bridge_jog(self):
        if self.bridge is None:
            self.bridge_jog_requested.set(False)
            return
        enabled = self.bridge_jog_requested.get()
        if enabled and not messagebox.askyesno('Enable local jogging through bridge?',
                'Confirm the telescope has clear travel and the external app is not slewing. '
                'Enabling stops current motion. External commands continue and have priority: '
                'a conflicting external command stops the local jog and is then forwarded. '
                'Hold is capped at 2 seconds; timed jogs at the selected duration. '
                'Frequent tracking updates can interrupt a jog; pause tracking in the external app if needed. Enable?', parent=self.root):
            self.bridge_jog_requested.set(False)
            return
        try:
            self.bridge.set_local_jog(enabled)
            self.bridge_jog_ready = False
            self.bridge_jog_note.set('Waiting for fresh motor positions before enabling local jogging…' if enabled else 'Stopping local movement and disabling local jogging…')
        except (RuntimeError, ValueError) as error:
            self.bridge_jog_requested.set(False)
            self.bridge_jog_note.set(str(error))
        self.update_controls()

    def bridge_jog(self, axis, direction, held=False):
        if not self.bridge or not self.bridge_jog_active or not self.bridge_jog_ready or self.jogging:
            return
        try:
            self.bridge.jog(axis, direction, int(self.speed.get()), 2.0 if held else float(self.duration.get()))
            self.jogging = True
            self.held = held
        except (RuntimeError, ValueError) as error:
            self.bridge_jog_note.set(str(error))
        self.update_controls()

    def reload_calibration(self):
        self.calibration = None
        self.has_slew_rates = False
        try:
            self.calibration = load_config()
            for (axis, rate), value in self.slew_rate_cells.items():
                parts = []
                for direction in (1, -1):
                    try:
                        parts.append(f'{measured_rate(self.calibration, axis, rate, direction):.4f}')
                        self.has_slew_rates = True
                    except (ValueError, KeyError, TypeError):
                        parts.append('—')
                value.set(' / '.join(parts))
            self.calibration_note.set('Profile: '
                                      + profile_label(self.calibration) + '\nConfiguration file: ' + DEFAULT_CONFIG.name)
        except (OSError, ValueError, KeyError, TypeError):
            self.calibration = None
            self.calibration_note.set('No usable calibration loaded from ' + DEFAULT_CONFIG.name + '. Open Profile file details for its location. Run calibrate_telescope.py separately to create a measured profile.')
            for value in self.slew_rate_cells.values():
                value.set('— / —')

        self.slew_rates_button.configure(state='normal' if self.has_slew_rates else 'disabled')
        if self.slew_rates_window is not None and self.slew_rates_window.winfo_exists():
            self.slew_rates_window.destroy()
            self.slew_rates_window = None
        self.refresh_profile_keymap()

    def slew_rate_rows(self):
        rows = [['Speed', 'Azimuth positive (deg/s)', 'Azimuth negative (deg/s)', 'Elevation positive (deg/s)', 'Elevation negative (deg/s)']]
        for rate in range(1, 10):
            row = [rate]
            for axis in AXES:
                row.extend(value if value != '—' else '' for value in self.slew_rate_cells[(axis, rate)].get().split(' / '))
            rows.append(row)
        return rows

    def open_slew_rates(self):
        if not self.has_slew_rates:
            return
        if self.slew_rates_window is not None and self.slew_rates_window.winfo_exists():
            self.slew_rates_window.lift()
            return
        window = self.slew_rates_window = tk.Toplevel(self)
        window.title('Measured slew rates')
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=self.calibration_note.get(), wraplength=760).pack(anchor='w', pady=(0, 8))
        rows = self.slew_rate_rows()
        table = ttk.Treeview(frame, columns=tuple(range(5)), show='headings', height=9)
        for i, heading in enumerate(rows[0]):
            table.heading(i, text=heading)
            table.column(i, width=65 if i == 0 else 180, anchor='center')
        for row in rows[1:]:
            table.insert('', 'end', values=row)
        table.pack(fill='both', expand=True)
        ttk.Label(frame, text='Measured average movement during calibration pulses, in degrees per second. Positive and negative identify the motor command direction. Values include acceleration, gear play and network delay; they are not guaranteed steady tracking speeds. Blank cells mean no usable measurement is available.', wraplength=760).pack(anchor='w', pady=8)
        buttons = ttk.Frame(frame)
        buttons.pack(anchor='w')
        self.copy_button(buttons, lambda: self.spreadsheet_output(rows, delimiter=','), 'Copy CSV to Clipboard').pack(side='left', padx=(0, 8))
        self.copy_button(buttons, lambda: self.spreadsheet_output(rows), 'Copy table for Excel').pack(side='left')

    def refresh_profile_keymap(self):
        if not hasattr(self, 'keyboard_toggle'):
            return
        if self.keyboard_enabled.get() or self.keyboard_direction:
            self.stop_motors()
        self.keyboard_enabled.set(False)
        self.keymap = {}
        try:
            self.keymap = profile_keymap(self.calibration)
            reason = 'Keyboard control unavailable: this JSON profile has no keymap.'
        except ValueError as error:
            reason = 'Keyboard control unavailable: ' + str(error)
        self.keyboard_toggle.configure(state='normal' if self.keymap else 'disabled')
        if not self.keymap:
            self.keyboard_help.set('')
            self.keyboard_status.set(reason)
            return
        labels = {'elevation_up': 'elevation up', 'elevation_down': 'elevation down',
                  'azimuth_left': 'azimuth left', 'azimuth_right': 'azimuth right',
                  'stop': 'stop both motors', 'connect': 'connect', 'disconnect': 'disconnect'}
        self.keyboard_help.set('\n'.join(f'{self.keymap[action].upper()}: {label}' for action, label in labels.items())
            + '\nLetters are shown in uppercase to match the labels on your keyboard. You do not need to hold Shift or turn on Caps Lock.\nTurn Keyboard control ON to use these keys on this tab, outside text fields. Release a held direction key to stop. After editing, click a blank area of the motor panel before using letter keys.')
        self.keyboard_status.set('Keyboard control OFF — keymap loaded from JSON profile')

    def open_profile_details(self):
        window = tk.Toplevel(self)
        window.title('Profile configuration file')
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill='both', expand=True)
        profile = profile_label(self.calibration) if self.calibration else 'No usable profile loaded'
        schema = self.calibration.get('schema_version', 'Not reported') if self.calibration else 'Unavailable'
        details = (f'Profile: {profile}\nConfiguration file: {DEFAULT_CONFIG.name}\n'
                   f'Full path: {DEFAULT_CONFIG.resolve()}\nFormat: JSON\nSchema version: {schema}\n\n'
                   'This is the file used by the Motor control calibration table and timed-jog estimates. '
                   'The file identifies the adapter and stores measurements; loading it does not write settings to the telescope. '
                   'After updating this file, click Reload calibration on Motor control.')
        output = ScrolledText(frame, height=10, width=85, wrap='word')
        output.pack(fill='both', expand=True)
        output.insert('1.0', details)
        output.configure(state='disabled')
        self.copy_button(frame, lambda: details, 'Copy profile file details').pack(anchor='w', pady=6)

    def open_degree_estimate(self):
        window = tk.Toplevel(self)
        window.title('Estimate timed degree jog')
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill='both', expand=True)
        axis_name = tk.StringVar(value='Azimuth')
        degrees = tk.StringVar(value='0.1')
        result = tk.StringVar(value='Calculates duration only; no movement is sent.')
        ttk.Label(frame, text='Axis').grid(row=0, column=0)
        ttk.Combobox(frame, textvariable=axis_name, values=tuple(AXES.values()), state='readonly').grid(row=0, column=1)
        ttk.Label(frame, text='Relative degrees (+ or −)').grid(row=1, column=0)
        ttk.Entry(frame, textvariable=degrees).grid(row=1, column=1)
        def apply_duration():
            if self.jogging or self.busy or self.bridge is not None:
                result.set('Stop current activity before changing the jog duration.')
                return
            try:
                axis = next(a for a, name in AXES.items() if name == axis_name.get())
                delta = parse_degrees(degrees.get(), -180, 180)
                host, port = validate_endpoint(self.host.get(), self.port.get())
                if self.calibration is None:
                    raise ValueError(f'Load a measured profile from {DEFAULT_CONFIG}')
                seconds = estimate_seconds(self.calibration, axis, int(self.speed.get()), delta, host, port)
                self.duration.set(f'{seconds:.6f}')
                self.drive_mode.set('jog')
                direction = ('Right' if delta > 0 else 'Left') if axis == 0x10 else ('Up' if delta > 0 else 'Down')
                result.set(f'Approx. {seconds:.4f}s at speed {self.speed.get()}. Timed jog selected. Close this dialog and use {direction}; no movement sent yet.')
            except (ValueError, KeyError, TypeError) as error:
                result.set(str(error))
        ttk.Button(frame, text='Calculate and use duration', command=apply_duration).grid(row=2, columnspan=2, pady=8)
        ttk.Label(frame, textvariable=result, wraplength=500).grid(row=3, columnspan=2, sticky='w')
        self.copy_button(frame, result.get).grid(row=5, columnspan=2, sticky='w')
        ttk.Label(frame, text='Approximate only: one-second calibration includes ramps, backlash and network delay. Actual encoder movement is shown after a jog. Duration is limited to 0.1–2 seconds. Encoder-target GOTO commands are not enabled.', wraplength=500).grid(row=4, columnspan=2, sticky='w', pady=8)

    def build_reference_controls(self, parent):
        refs = ttk.LabelFrame(parent, text='Set Alignment Using Known Position Reference', padding=8)
        refs.pack(fill='x', pady=8)
        for column, label in enumerate(('Axis / range', 'Current (polled)', 'Known position', 'Proposed offset', '')):
            ttk.Label(refs, text=label).grid(row=0, column=column, sticky='w', padx=5)
        for row, axis in enumerate(AXES, 1):
            bounds = '0 to 360°' if axis == 0x10 else '-90 to +90°'
            ttk.Label(refs, text=f'{AXES[axis]} ({bounds})').grid(row=row, column=0, sticky='w', padx=5)
            ttk.Label(refs, textvariable=self.reference_current[axis], width=15).grid(row=row, column=1)
            ttk.Entry(refs, textvariable=self.reference_inputs[axis], width=12).grid(row=row, column=2)
            ttk.Label(refs, textvariable=self.reference_delta[axis], width=18).grid(row=row, column=3)
            ttk.Button(refs, text='Set local reference', command=lambda a=axis: self.set_position_reference(a)).grid(row=row, column=4, padx=8)
        ttk.Label(refs, text='Connect Motors to poll positions. Point at a known object and enter its current azimuth/elevation. Offset = known minus current encoder angle, wrapped to ±180°. This sets LOCAL coordinates only; it does not program shared celestial alignment or tracking into the mount. Clears on disconnect.', wraplength=780).grid(row=3, column=0, columnspan=5, sticky='w', pady=5)
        ttk.Label(refs, text='Examples: azimuth 100.52 or 060.84; elevation -60.31. Up to 5 decimals; leading zeros OK. Coordinate ranges are NOT safe mechanical travel limits.', wraplength=780).grid(row=4, column=0, columnspan=5, sticky='w')
        for row, axis in enumerate(AXES, 5):
            ttk.Button(refs, text=f'Read {AXES[axis]} position now', command=lambda a=axis: self.poll_local_reference(a)).grid(row=row, column=0, sticky='w', pady=5)
            ttk.Label(refs, textvariable=self.local_history[axis], wraplength=470).grid(row=row, column=1, columnspan=3, sticky='w')
            ttk.Button(refs, text='Reapply previous offset…', command=lambda a=axis: self.reapply_local_reference(a)).grid(row=row, column=4)
        ttk.Button(refs, text='Clear local references (zero offsets)', command=self.clear_local_references).grid(row=7, columnspan=3, sticky='w', pady=5)
        self.copy_button(refs, self.reference_output, 'Copy reference table').grid(row=7, column=3, columnspan=2, sticky='w')
        ttk.Label(refs, text='Local mode changes only this app’s displayed coordinates. Disconnect or lost feedback clears active offsets; previous applied values remain inactive history until this app closes. No hardware settings are reset. Reapply only if the mount has not been powered off, moved manually or realigned. Otherwise establish a new known-position reference.', wraplength=780).grid(row=8, columnspan=5, sticky='w')



    def copy_button(self, parent, provider, label='Copy text to Clipboard'):
        return ttk.Button(parent, text=label, command=lambda: self.copy_output(provider))

    def copy_output(self, provider):
        # Preserve the original output/status; copying must not erase the error
        # the operator is trying to report. Providers snapshot on the Tk thread.
        text = str(provider())
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    @staticmethod
    def spreadsheet_output(rows, delimiter='\t'):
        """Excel clipboard convention: tab-separated cells with CSV quoting."""
        output = io.StringIO(newline='')
        csv.writer(output, delimiter=delimiter, lineterminator='\r\n').writerows(rows)
        return output.getvalue()

    def table_output(self, table):
        columns = table['columns']
        rows = [[table.heading(c, 'text') for c in columns]]
        rows.extend(table.item(item, 'values') for item in table.get_children())
        return self.spreadsheet_output(rows)

    def diagnostics_output(self):
        rows = [['Device', 'Query / endpoint', 'Result', 'Full response / interpretation']]
        for item in self.diagnostic_rows.get_children():
            values = self.diagnostic_rows.item(item, 'values')
            rows.append([*values[:3], self.diagnostic_replies.get(item, values[3] if len(values) > 3 else '')])
        return self.spreadsheet_output(rows)

    def motor_output(self):
        rows = [['Measurement', *AXES.values()]]
        labels = {'encoder': 'Encoder counts', 'angle': 'Raw encoder angle (degrees)',
                  'relative': 'Change since connection (degrees)', 'referenced': 'Angle with local offset (degrees)',
                  'firmware': 'Motor firmware', 'age': 'Time since last reading',
                  'before': 'Encoder counts before jog', 'after': 'Encoder counts after jog',
                  'delta_counts': 'Jog change (counts)', 'delta_degrees': 'Jog change (degrees)',
                  'stationary': 'Stop check'}
        for field, label in labels.items():
            rows.append([label, *(self.values[axis][field].get() for axis in AXES)])
        rows.extend([['Profile', profile_label(self.calibration) if self.calibration else 'No usable profile loaded', ''],
                     ['Configuration file (JSON)', str(DEFAULT_CONFIG.resolve()), ''],
                     ['Connection status', self.motor_status.get(), ''],
                     ['Movement status', self.motion_status.get(), '']])
        for rate in range(1, 10):
            rows.append([f'Speed {rate} measured degrees/second (positive / negative)',
                         *(self.slew_rate_cells[(axis, rate)].get() for axis in AXES)])
        return self.spreadsheet_output(rows)

    def reference_output(self):
        rows = [['Axis', 'Current encoder angle', 'Entered known position', 'Proposed local offset', 'Applied reference history']]
        rows.extend([AXES[a], self.reference_current[a].get(), self.reference_inputs[a].get(),
                     self.reference_delta[a].get(), self.local_history[a].get()] for a in AXES)
        return self.spreadsheet_output(rows)

    def controller_output(self, axis):
        rows = [['Field', AXES[axis]], ['Axis', AXES[axis]]]
        for line in self.controller_readout[axis].get().splitlines():
            pair = line.split(': ', 1)
            rows.append(pair if len(pair) == 2 else ['Read status', line])
        rows.append(['Last applied change', self.controller_history[axis].get()])
        return self.spreadsheet_output(rows)

    def time_output(self):
        rows = [['Field', 'Value']]
        for line in self.time_readback.get().splitlines():
            pair = line.split(': ', 1)
            rows.append(pair if len(pair) == 2 else ['Read status', line])
        rows.append(['Operation status', self.time_status.get()])
        return self.spreadsheet_output(rows)

    def open_motor_settings(self):
        if self.motor_settings_window and self.motor_settings_window.winfo_exists():
            self.motor_settings_window.lift()
            return
        window = self.motor_settings_window = tk.Toplevel(self)
        window.title('Controller Angle / Backlash Settings')
        shell = ttk.Frame(window, padding=12)
        shell.pack(fill='both', expand=True)
        mode = tk.StringVar(value='local')
        modes = ttk.Frame(shell)
        modes.pack(fill='x')
        local = ttk.Frame(shell)
        self.build_reference_controls(local)
        frame = ttk.Frame(shell)
        def select_mode():
            local.pack_forget()
            frame.pack_forget()
            (local if mode.get() == 'local' else frame).pack(fill='both', expand=True)
        ttk.Radiobutton(modes, text='Local reference (this app only)', variable=mode, value='local', command=select_mode).pack(side='left', padx=6)
        ttk.Radiobutton(modes, text='Telescope controller (shared raw encoder / backlash)', variable=mode, value='controller', command=select_mode).pack(side='left', padx=6)
        select_mode()
        ttk.Label(frame, text='Telescope controller mode changes settings stored in each motor controller. Other apps can observe those settings. Setting an encoder angle changes its coordinate origin without moving the telescope; it does not create a celestial alignment. Backlash compensates gear play when direction changes. Before reading or writing, click Disconnect on the Motor control tab if connected. In any other controlling app, disconnect its telescope connection. Leave the telescope powered on.', wraplength=860).grid(row=0, column=0, columnspan=2, sticky='w', pady=8)
        for column, axis in enumerate(AXES):
            panel = ttk.LabelFrame(frame, text=AXES[axis], padding=10)
            panel.grid(row=1, column=column, sticky='nsew', padx=5)
            frame.columnconfigure(column, weight=1, uniform='controller_axes')
            ttk.Label(panel, text='Current values from telescope', font=('TkDefaultFont', 11, 'bold')).grid(row=0, columnspan=2, sticky='w')
            # Fixed-height readouts keep corresponding controls aligned when one
            # axis has a reply and the other is unread, busy or reporting an error.
            readout = ScrolledText(panel, height=5, width=45, wrap='word',
                                   font=('TkDefaultFont', 9), relief='flat', borderwidth=1)
            readout.grid(row=1, columnspan=2, sticky='ew', pady=5)
            variable = self.controller_readout[axis]
            def render_readout(*_args, widget=readout, value=variable):
                widget.configure(state='normal')
                widget.delete('1.0', 'end')
                widget.insert('1.0', value.get())
                widget.configure(state='disabled')
            render_readout()
            trace_id = variable.trace_add('write', render_readout)
            def remove_readout_trace(event, widget=readout, value=variable, trace=trace_id):
                if event.widget == widget:
                    value.trace_remove('write', trace)
            readout.bind('<Destroy>', remove_readout_trace, add='+')
            ttk.Button(panel, text='Read current values', command=lambda a=axis: self.run_motor_settings(axis=a)).grid(row=2, columnspan=2, sticky='w', pady=5)
            ttk.Label(panel, text='New values to send (editing does not write)', font=('TkDefaultFont', 10, 'bold')).grid(row=3, columnspan=2, sticky='w', pady=5)
            fields = self.controller_fields[axis]
            for row, key, label in ((4, 'angle', 'Encoder angle (degrees)'), (6, 'positive', 'Positive-direction backlash'), (7, 'negative', 'Negative-direction backlash'), (9, 'delta_positive', 'Positive-direction delta'), (10, 'delta_negative', 'Negative-direction delta')):
                ttk.Label(panel, text=label).grid(row=row, column=0, sticky='w', pady=3)
                ttk.Entry(panel, textvariable=fields[key], width=14).grid(row=row, column=1, padx=5)
            ttk.Button(panel, text='Set encoder angle…', command=lambda a=axis: self.run_motor_settings('position', a)).grid(row=5, columnspan=2, sticky='w')
            ttk.Button(panel, text='Apply absolute backlash…', command=lambda a=axis: self.run_motor_settings('backlash', a)).grid(row=8, columnspan=2, sticky='w', pady=4)
            ttk.Button(panel, text='Preview / apply backlash delta…', command=lambda a=axis: self.run_motor_settings('delta', a)).grid(row=11, columnspan=2, sticky='w', pady=4)
            ttk.Label(panel, text='Last applied change (retained until app closes)', font=('TkDefaultFont', 10, 'bold')).grid(row=12, columnspan=2, sticky='w', pady=5)
            ttk.Label(panel, textvariable=self.controller_history[axis], wraplength=390, justify='left').grid(row=13, columnspan=2, sticky='w')
            self.copy_button(panel, lambda a=axis: self.controller_output(a), 'Copy axis settings').grid(row=14, columnspan=2, sticky='w', pady=4)
        ttk.Label(frame, text='Angles: Azimuth 0–360°; Elevation -90 to +90°. Up to 5 decimals; examples 100.52, 060.84, -60.31 (elevation only). These are coordinate ranges, not mechanical travel limits.\nBacklash: 0–99 whole-number controller units, NOT degrees. Positive/negative names identify travel direction; both absolute settings are nonnegative. Deltas may be -99 to +99, but the result must stay 0–99. Spaces, leading zeros and integral decimals (2.0 → 2) normalize; fractions and invalid signs are rejected. Delta writes recheck the source values before writing.', wraplength=860).grid(row=2, columnspan=2, sticky='w', pady=8)
        status_box = ttk.LabelFrame(frame, text='Settings operation status', padding=6)
        status_box.grid(row=3, columnspan=2, sticky='ew', pady=(6, 0))
        ttk.Label(status_box, textvariable=self.motor_setting_status, wraplength=840).pack(anchor='w')
        self.copy_button(status_box, self.motor_setting_status.get, 'Copy settings status').pack(anchor='w', pady=3)

    def run_motor_settings(self, operation=None, axis=0x10):
        if self.busy or self.motor is not None or self.bridge is not None:
            self.motor_setting_status.set('Settings are unavailable during another operation. Wait for it to finish; if Motor control is connected, click Disconnect on that tab. If Control Bridge is running, switch it OFF. Leave the telescope powered on.')
            return
        expected = None
        try:
            host, port = validate_endpoint(self.host.get(), self.port.get())
            fields = self.controller_fields[axis]
            changes = {}
            preview = ''
            if operation == 'position':
                changes = {4: parse_degrees(fields['angle'].get(), *((0, 360) if axis == 0x10 else (-90, 90)))}
                fields['angle'].set(f'{changes[4]:.5f}'.rstrip('0').rstrip('.'))
                preview = f'New encoder angle: {changes[4]:.5f}°'
            elif operation in ('backlash', 'delta'):
                keys = ('delta_positive', 'delta_negative') if operation == 'delta' else ('positive', 'negative')
                numbers = [parse_backlash(fields[k].get(), delta=operation == 'delta') for k in keys]
                for key, value in zip(keys, numbers, strict=True):
                    fields[key].set(str(value))
                if operation == 'delta':
                    previous = self.controller_reads.get(axis)
                    if not previous or previous['endpoint'] != (host, port) or time.monotonic() - previous['time'] > 60:
                        raise ValueError('Read current values for this axis first (within 60 seconds), then apply the delta.')
                    expected = (previous['values']['positive_backlash'], previous['values']['negative_backlash'])
                    resulting = [old + delta for old, delta in zip(expected, numbers, strict=True)]
                    preview = f'Positive: {expected[0]} {numbers[0]:+d} → {resulting[0]}; Negative: {expected[1]} {numbers[1]:+d} → {resulting[1]}'
                    numbers = resulting
                changes = dict(zip((0x10, 0x11), numbers, strict=True))
                preview = preview or f'Positive backlash → {numbers[0]}; Negative backlash → {numbers[1]}'
            from motor_settings import setting_packet
            for command, value in changes.items():
                setting_packet(axis, command, value)
        except (ValueError, KeyError) as error:
            self.motor_setting_status.set(str(error))
            return
        if changes and not messagebox.askyesno('Confirm controller change',
                f'{AXES[axis]}\n{preview}\nKeep stationary with other apps disconnected. Encoder changes invalidate alignment assumptions. Backlash changes motion compensation. Write and verify these values?', parent=self.motor_settings_window or self.root):
            return
        self.set_busy(True)
        self.motor_setting_status.set(f'{AXES[axis]}: reading current values…' if not changes else f'{AXES[axis]}: applying and verifying change…')
        self.controller_readout[axis].set('Reading telescope… Previous values are not current.')
        self.controller_reads.pop(axis, None)
        def worker():
            try:
                options = {'expected_backlash': expected} if expected is not None else {}
                report = motor_settings(host, port, axis, changes=changes, callback=self.events.put, **options)
            except Exception as error:
                report = {'error': str(error), 'axis': axis}
            self.events.put({'event': 'motor_settings_done', 'report': report,
                             'operation': operation, 'preview': preview, 'endpoint': (host, port)})
        threading.Thread(target=worker, daemon=True).start()

    def clear_local_references(self):
        self.position_references.clear()
        for axis in AXES:
            self.values[axis]['referenced'].set('—')
            self.reference_inputs[axis].set('0')
            if axis in self.last_local_reference:
                self.local_history[axis].set('Inactive — ' + self.last_local_reference[axis]['description'])
        self.motion_status.set('No local reference — showing raw motor coordinates.')

    def poll_local_reference(self, axis):
        if not self.motor_ready or self.motor is None:
            self.motion_status.set('Click Connect Motors on the Motor control tab, then click the axis Read button to request a fresh position.')
            return
        self.reference_poll_pending.add(axis)
        self.reference_current[axis].set('Waiting for next poll…')
        self.motion_status.set(f'Waiting for the next fresh {AXES[axis]} reading from the motor polling loop.')

    def reapply_local_reference(self, axis):
        previous = self.last_local_reference.get(axis)
        if not previous or not self.motor_ready or self.jogging or time.monotonic() - self.last_positions.get(axis, 0) > 3:
            self.motion_status.set('Previous reference and fresh stationary motor feedback are required.')
            return
        if previous['endpoint'] != (self.host.get(), self.port.get()):
            self.motion_status.set('Previous reference belongs to a different connection address; establish a new reference.')
            return
        if not messagebox.askyesno('Reapply previous local offset?', 'Confirm the telescope has NOT been powered off, moved manually or realigned. This restores only the previous local offset; it does not restore hardware alignment.', parent=self.motor_settings_window or self.root):
            return
        current = int(self.values[axis]['encoder'].get()) * 360 / (1 << 24)
        known = (current + previous['offset']) % 360
        if axis == 0x11 and known > 180:
            known -= 360
        self.reference_inputs[axis].set(f'{known:.5f}')
        self.set_position_reference(axis)

    def refresh_reference_preview(self, axis):
        try:
            current = int(self.values[axis]['encoder'].get()) * 360 / (1 << 24)
        except ValueError:
            self.reference_current[axis].set('—')
            self.reference_delta[axis].set('—')
            return
        if axis == 0x11 and current > 180:
            current -= 360
        self.reference_current[axis].set(f'{current:.5f}°')
        try:
            low, high = (0, 360) if axis == 0x10 else (-90, 90)
            known = parse_degrees(self.reference_inputs[axis].get(), low, high)
            delta = (known - current + 180) % 360 - 180
            self.reference_delta[axis].set(f'{delta:+.5f}°')
        except ValueError:
            self.reference_delta[axis].set('Invalid input')

    def set_position_reference(self, axis):
        if not self.motor_ready or self.jogging or self.held or self.bridge is not None:
            self.motion_status.set('Connect motors and stop movement before setting a reference.')
            return
        if time.monotonic() - self.last_positions.get(axis, 0) > 3:
            self.motion_status.set('Fresh encoder feedback is required for a reference.')
            return
        try:
            low, high = (0, 360) if axis == 0x10 else (-90, 90)
            degrees = parse_degrees(self.reference_inputs[axis].get(), low, high)
            self.reference_inputs[axis].set(f'{degrees:.5f}'.rstrip('0').rstrip('.'))
            encoder = int(self.values[axis]['encoder'].get())
        except ValueError as error:
            self.motion_status.set(str(error))
            return
        self.position_references[axis] = (encoder, degrees)
        offset = (degrees - encoder * 360 / (1 << 24) + 180) % 360 - 180
        description = f"Applied {dt.datetime.now().strftime('%H:%M:%S')}: encoder {encoder}, known {degrees:.5f}°, offset {offset:+.5f}°"
        self.last_local_reference[axis] = {'offset': offset, 'description': description, 'endpoint': (self.host.get(), self.port.get())}
        self.local_history[axis].set('Active — ' + description)

        self.values[axis]['referenced'].set(f'{degrees:.5f}°')
        self.motion_status.set(f'{AXES[axis]} reference set locally. No movement or encoder write sent.')
        self.append(f'{AXES[axis]} local reference: encoder {encoder} = {degrees:.5f} degrees')

    def start_time_settings(self, sync_now=False, read_only=False):
        if self.busy or self.motor is not None or self.bridge is not None:
            self.status.set('Time settings are unavailable during another operation. Wait for it to finish; click Disconnect on Motor control if connected, or switch Control Bridge OFF if running. Leave the telescope powered on.')
            self.time_status.set(self.status.get())
            return
        try:
            host, port = validate_endpoint(self.host.get(), self.port.get())
            mode = self.time_mode.get()
            enable = None if sync_now or read_only else (0 if mode == 'Disabled' else 1 if mode == 'At startup' else int(self.time_enable.get()))
            if mode == 'Every N minutes' and not sync_now and not read_only and not 2 <= enable <= 1440:
                raise ValueError('Use an interval between 2 and 1440 minutes')
            server_ip = None
            if not sync_now and not read_only and enable != 0:
                tested = self.tested_time_server
                if not tested or tested['host'] != self.time_server.get().strip() or time.monotonic() - tested['tested_at'] > 300:
                    raise ValueError('Test the selected server successfully within five minutes before pushing it')
                server_ip = tested['ip']
        except ValueError as error:
            self.status.set(str(error))
            self.time_status.set(str(error))
            return
        persist = self.time_persist.get() and not sync_now and not read_only
        message = ('Request WiFly time from its configured SNTP server now? Internet/UDP 123 access is required.'
                   if sync_now else f'Write WiFly time enable={enable}? 0=off, 1=startup, larger values=minutes. This does not align the telescope.')
        if server_ip:
            message += f'\nServer: {self.time_server.get()} → {server_ip}:123'
        if persist:
            message += '\nSave writes ALL current WiFly RAM settings to flash, not just time settings.'
        if not read_only and not messagebox.askyesno('Change WiFly clock', message, parent=self.winfo_toplevel()):
            return
        self.set_busy(True)
        def worker():
            try:
                result = configure_time(host, port, enable=enable, sync_now=sync_now,
                                        persist=persist, server_ip=server_ip, callback=self.events.put)
            except Exception as error:
                result = {'error': str(error)}
            self.events.put({'event': 'time_settings_done', 'report': result})
        threading.Thread(target=worker, daemon=True).start()

    def build_diagnostics_tab(self):
        """Create query results and the full-response inspection panel."""
        tab = self.diagnostic_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        self.diagnostic_status = tk.StringVar(value='Not tested — run diagnostics to verify adapter and motor replies.')
        diagnostic_controls = ttk.Frame(tab)
        diagnostic_controls.grid(row=0, columnspan=2, sticky='ew')
        self.diagnostic_button = ttk.Button(diagnostic_controls, text='Run read-only diagnostics', command=self.start_diagnostics)
        self.diagnostic_button.pack(side='left')
        self.diagnostic_cancel = threading.Event()
        self.diagnostic_running = False
        self.diagnostic_abort_button = ttk.Button(diagnostic_controls, text='Abort diagnostics', state='disabled', command=self.abort_diagnostics)
        self.diagnostic_abort_button.pack(side='left', padx=8)
        self.deep_diagnostics = tk.BooleanVar(value=False)
        ttk.Checkbutton(diagnostic_controls, text='Deep Diagnostics Read', variable=self.deep_diagnostics).pack(side='left', padx=8)
        self.recovery_button = ttk.Button(diagnostic_controls, text='Restart Wi-Fi adapter & recheck motors', command=self.start_recovery)
        self.recovery_button.pack(side='left', padx=12)
        ttk.Label(tab, textvariable=self.diagnostic_status, wraplength=800).grid(row=1, sticky='w', pady=6)
        self.diagnostic_rows = ttk.Treeview(tab, columns=('device', 'endpoint', 'status', 'reply'), show='headings', height=7)
        for key, label, width in (('device', 'Device', 110), ('endpoint', 'Query / endpoint', 210),
                                  ('status', 'Result', 105), ('reply', 'Interpretation / raw hex', 355)):
            self.diagnostic_rows.heading(key, text=label)
            self.diagnostic_rows.column(key, width=width)
        self.diagnostic_rows.grid(row=2, sticky='nsew')
        scrollbar = ttk.Scrollbar(tab, orient='vertical', command=self.diagnostic_rows.yview)
        scrollbar.grid(row=2, column=1, sticky='ns')
        self.diagnostic_rows.configure(yscrollcommand=scrollbar.set)
        detail_panel = ttk.LabelFrame(tab, text='Selected diagnostic result — full response', padding=6)
        detail_panel.grid(row=3, columnspan=2, sticky='ew', pady=6)
        ttk.Label(detail_panel, text='Select a row in the table above to view its complete reply here.').pack(anchor='w')
        self.diagnostic_details = ScrolledText(detail_panel, height=5, wrap='word', state='disabled', font=('TkFixedFont', 10))
        self.diagnostic_details.pack(fill='x')
        self.copy_button(detail_panel, lambda: self.diagnostic_details.get('1.0', 'end-1c'), 'Copy selected reply').pack(anchor='w', pady=4)
        self.copy_button(diagnostic_controls, self.diagnostics_output, 'Copy diagnostics table').pack(side='left', padx=6)
        if self.macos_ui:
            # The five-button toolbar made even hidden Diagnostics force the
            # entire notebook wider than a Mac laptop window. Two rows keep
            # the tab strip centered within the visible form, not offscreen.
            controls = diagnostic_controls.winfo_children()
            for control in controls:
                control.pack_forget()
            for index, control in enumerate(controls):
                control.grid(row=index // 3, column=index % 3, sticky='w', padx=(0, 8), pady=4)

        self.diagnostic_replies = {}
        self.diagnostic_rows.bind('<<TreeviewSelect>>', self.show_diagnostic_reply)
        ttk.Label(tab, text='Select a row for raw hex and decoded values. Optional AUX devices may not reply. No motion or configuration writes.\n'
                  'The Restart Wi-Fi adapter & recheck motors button restarts the radio module and then reads motor positions. It retains saved Wi-Fi settings. Before using it, click Disconnect on the Motor control tab if connected; leave telescope power on.',
                  wraplength=800).grid(row=4, columnspan=2, sticky='w')

        self.time_window = None
        self.uptime_evidence = UptimeEvidence()
        self.time_readback_widget = None
        self.time_enable = tk.StringVar(value='60')
        self.time_mode = tk.StringVar(value='At startup')
        self.time_server = tk.StringVar(value=COMMON_TIME_SERVERS[0])
        self.time_zone = tk.StringVar(value='Not read')
        self.time_readback = tk.StringVar(value='No board values read in this session. Click Read current board settings and clock.')
        self.time_status = tk.StringVar(value='Test a server from this computer before pushing a new server address.')
        self.time_persist = tk.BooleanVar(value=False)
        self.tested_time_server = None
        self.time_apply_button = ttk.Button(tab, text='Time / Time Server Settings…', command=self.open_time_settings)
        self.time_apply_button.grid(row=5, sticky='w', pady=6)
        self.time_sync_button = self.time_apply_button

    def open_time_settings(self):
        if self.time_window and self.time_window.winfo_exists():
            self.time_window.lift()
            return
        window = self.time_window = tk.Toplevel(self)
        window.title('Time / Time Server Settings')
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Time server (hostname or IPv4)').grid(row=0, column=0, sticky='w')
        ttk.Combobox(frame, textvariable=self.time_server, values=COMMON_TIME_SERVERS, width=30).grid(row=0, column=1)
        ttk.Button(frame, text='Test from this computer', command=self.test_selected_time_server).grid(row=1, column=1, sticky='w', pady=6)
        ttk.Label(frame, text='Automatic sync').grid(row=2, column=0, sticky='w')
        ttk.Combobox(frame, textvariable=self.time_mode, values=('Disabled', 'At startup', 'Every N minutes'), state='readonly').grid(row=2, column=1)
        ttk.Label(frame, text='Interval (2–1440 minutes)').grid(row=3, column=0, sticky='w')
        ttk.Spinbox(frame, from_=2, to=1440, textvariable=self.time_enable, width=10).grid(row=3, column=1, sticky='w')
        ttk.Label(frame, text='WiFly timezone number (readback)').grid(row=4, column=0, sticky='w')
        ttk.Entry(frame, textvariable=self.time_zone, state='readonly', width=15).grid(row=4, column=1, sticky='w')
        ttk.Label(frame, text='7 = UTC−07:00 in WiFly documentation. Changing this timezone is not supported yet. Click Read current board settings and clock to refresh it.', wraplength=500).grid(row=5, columnspan=2, sticky='w', pady=6)
        ttk.Checkbutton(frame, text='Save ALL current WiFly settings to flash', variable=self.time_persist).grid(row=6, columnspan=2, sticky='w')
        ttk.Button(frame, text='Push server and sync mode…', command=self.start_time_settings).grid(row=7, column=0, pady=8)
        ttk.Button(frame, text='Sync WiFly from time server now…', command=lambda: self.start_time_settings(True)).grid(row=7, column=1)
        ttk.Label(frame, textvariable=self.time_status, wraplength=500).grid(row=8, columnspan=2, sticky='w')
        self.copy_button(frame, self.time_output, 'Copy clock/settings table').grid(row=10, columnspan=2, sticky='w')
        ttk.Label(frame, text='The telescope needs its own route to UDP 123. A successful PC test does not prove telescope access. Names are resolved and pushed as IPv4 addresses.', wraplength=500).grid(row=9, columnspan=2, sticky='w', pady=8)

        ttk.Button(frame, text='Read current board settings and clock', command=lambda: self.start_time_settings(read_only=True)).grid(row=11, columnspan=2, sticky='w', pady=6)
        self.time_readback_widget = ScrolledText(frame, height=10, width=82, wrap='word', state='disabled')
        self.time_readback_widget.grid(row=12, columnspan=2, sticky='ew')
        self.refresh_time_readback()
        ttk.Button(frame, text='Set WiFly clock from this computer…', state='disabled').grid(row=13, columnspan=2, sticky='w', pady=6)
        ttk.Label(frame, text='PC-to-WiFly sync is not available yet: the clock-write command for 2.40-CEL still needs verification. Time-server sync queries the configured server; neither action changes the PC clock.', wraplength=650).grid(row=14, columnspan=2, sticky='w')

    def refresh_time_readback(self):
        widget = self.time_readback_widget
        if widget is not None and widget.winfo_exists():
            widget.configure(state='normal')
            widget.delete('1.0', 'end')
            widget.insert('1.0', self.time_readback.get())
            widget.configure(state='disabled')

    def check_uptime_evidence(self, identity, clock):
        # Only diagnostics/time-dialog samples reach this check: do not claim
        # continuous power-cycle detection. Adapter restart/rollover evidence
        # cannot prove a motor reset, and clearing our display offsets does not
        # invalidate a separate client's INDI alignment model. See the Pi/KStars
        # 2026-11-16 validation note before changing cross-client reset handling.
        result = self.uptime_evidence.observe(identity, clock)
        if result['warning']:
            self.clear_local_references()
            self.motion_status.set(result['message'])
            self.append(result['message'])
        return result['message']

    def test_selected_time_server(self):
        host = self.time_server.get().strip()
        self.tested_time_server = None
        self.time_status.set('Testing SNTP from this computer…')
        def worker():
            try:
                result = test_time_server(host)
            except Exception as error:
                result = {'error': str(error), 'host': host}
            self.events.put({'event': 'time_server_test_done', 'report': result})
        threading.Thread(target=worker, daemon=True).start()

    def build_bridge_tab(self):
        """Create bridge controls, interface selection and relay status readbacks."""
        tab = self.bridge_tab
        tab.columnconfigure(0, weight=1)
        ttk.Label(tab, text='This feature allows your local computer to create a proxy link between the SkyQLink telescope and control software that uses modern Celestron Wi-Fi connections. It relays telescope commands and replies for one controlling application at a time. Alignment and tracking calculations remain the responsibility of the control software.', wraplength=820).grid(row=0, sticky='w', pady=(0, 8))
        self.bridge_switch = BridgeRocker(tab, variable=self.bridge_enabled, command=self.toggle_bridge)
        self.bridge_switch.grid(row=1, sticky='nw')
        self.bridge_requirement = tk.StringVar()
        ttk.Label(tab, textvariable=self.bridge_requirement, wraplength=590, foreground='#8a4400', font=('TkDefaultFont', 11, 'bold')).grid(row=1, sticky='w', padx=(195, 0), pady=4)
        bridge_status_box = tk.Frame(tab, background='#e2ebf5', highlightbackground='#9aabbf', highlightthickness=1, padx=10, pady=8)
        bridge_status_box.grid(row=2, sticky='ew', pady=8)
        tk.Label(bridge_status_box, text='Bridge status:', background='#e2ebf5', foreground='#172b44' if self.macos_ui else None, font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')
        tk.Label(bridge_status_box, textvariable=self.bridge_status, background='#e2ebf5', foreground='#172b44' if self.macos_ui else None, font=('TkDefaultFont', 10, 'bold'), wraplength=800, justify='left').pack(anchor='w')
        settings = ttk.Frame(tab)
        settings.grid(row=3, sticky='ew')
        self.bridge_ip_help = tk.StringVar()
        ttk.Label(settings, textvariable=self.bridge_ip_help).pack(side='left')
        self.bridge_bind_entry = ttk.Entry(settings, textvariable=self.bridge_bind, width=20)
        self.bridge_bind_entry.pack(side='left', padx=8)

        self.bridge_dual_box = ttk.Checkbutton(tab, text='Two Interface Mode',
                                              variable=self.bridge_dual, command=self.update_controls)
        self.bridge_dual_box.grid(row=4, sticky='w', pady=4)
        self.bridge_direct_help = ttk.Label(tab,
            text='Direct/ad hoc setup: enable Two Interface Mode. Connect one compatible Wi-Fi adapter to SkyQLink, then choose a second network connection for your control device:', wraplength=780)
        self.bridge_direct_help.grid(row=4, column=0, sticky='w', pady=(30, 0))
        self.bridge_options = ttk.LabelFrame(tab, text='Second-interface connection options — Direct/ad hoc or separate networks', padding=8)
        self.bridge_options.grid(row=5, column=0, sticky='ew', padx=(18, 0), pady=(6, 10))
        self.bridge_option_labels = []
        for option in (
            '• Option 1 — Ethernet: connect to a router/access point; the control device can use that router’s Ethernet or Wi-Fi. A directly wired control device needs compatible IP settings.',
            '• Option 2 — Second Wi-Fi adapter: join the router/hotspot used by the phone or tablet. The network must allow communication between devices; disable client/guest isolation.',
            '• Option 3 — Computer-hosted hotspot: use a second Wi-Fi adapter to provide a hotspot, if supported. Configure the hotspot and firewall in your operating system.'):
            label = ttk.Label(self.bridge_options, text=option, wraplength=750)
            label.pack(anchor='w', pady=(0, 6))
            self.bridge_option_labels.append(label)
        self.bridge_options_note = ttk.Label(self.bridge_options,
            text='Applies to all options: telescope control does not require Internet access. These options connect the control device to the bridge computer. For Option 3, create the hotspot in your operating system first. Sharing Internet from a third adapter is a separate operating-system setup; this app does not configure hotspots, Internet sharing or network routing.', wraplength=730)
        self.bridge_options_note.pack(anchor='w', pady=(4, 0))
        self.bridge_dual_box.grid_configure(sticky='nw')
        self.bridge_interface_help = tk.StringVar()
        inventory = ttk.LabelFrame(tab, text='Local System Network Interfaces', padding=6)
        ttk.Label(inventory, text='Use this system’s IP address on the network shared with the device running your control software (e.g., SkySafari, CPWI, KStars/INDI, etc.). Type this system’s IP in the box above, or click its matching network adapter row below to fill it in. If the control software runs on this same system, use localhost (127.0.0.1) when the bridge is configured to listen there, or use the specific IP address shown by the bridge. Do not enter the telescope’s IP address in this box.', wraplength=780).pack(anchor='w', pady=(0, 6))
        ttk.Label(inventory, textvariable=self.bridge_interface_help, wraplength=780).pack(anchor='w')
        inventory.grid(row=6, sticky='ew', pady=5)
        self.interface_table = ttk.Treeview(inventory, columns=('interface', 'name', 'ip', 'state', 'role'),
                                            show='headings', height=4, selectmode='browse')
        for field, label, width in (('interface', 'Interface', 70), ('name', 'Adapter / connection', 180),
                                    ('ip', 'Current IPv4', 140), ('state', 'State', 90), ('role', 'Connection role', 240)):
            self.interface_table.heading(field, text=label)
            self.interface_table.column(field, width=width)
        self.interface_table.pack(fill='x')
        self.interface_table.bind('<<TreeviewSelect>>', self.select_bridge_interface)
        self.interface_refresh_button = ttk.Button(inventory, text='Refresh Adapter IPs', command=self.refresh_network_interfaces)
        self.interface_refresh_button.pack(anchor='w', pady=4)
        self.copy_button(inventory, lambda: self.table_output(self.interface_table), 'Copy network adapter table').pack(anchor='w')
        ttk.Label(inventory, textvariable=self.bridge_endpoint, wraplength=800).pack(anchor='w')
        ttk.Label(tab, text='Connect your control application on this computer or another device:\n'
                  '1. Connect this computer to the telescope’s network. At the top of this window, enter or discover the Telescope Wi-Fi Interface IP address. For a telescope on a separate direct/ad hoc link, follow Two Interface Mode above.\n'
                  '2. Choose where your control application runs (e.g., SkySafari, CPWI, KStars/INDI, etc.):\n'
                  '   • On THIS computer: use the bridge address displayed after startup. No second computer is needed. For local-only access, enter 127.0.0.1 in the bridge IP box before startup, then use 127.0.0.1 in your control application.\n'
                  '   • On ANOTHER computer, tablet or phone: connect that device and this computer to the same shared LAN segment. Select this computer’s adapter on that LAN in Local System Network Interfaces, or type that adapter’s IPv4 address in the bridge IP box. Do not enter the other device’s IP. The network must allow devices to communicate.\n'
                  '3. Switch Control Bridge ON here, in this window. Wait for Bridge ON and the address/port readback. This computer now relays between the control application and the telescope; no bridge needs to run on the other device.\n'
                  '4. In your control application, select its compatible Celestron Wi-Fi/AUX network connection and enter the displayed bridge IP address and TCP port (normally 2000). Do not use the telescope’s IP for this bridge connection. Use localhost only when this bridge listens on 127.0.0.1 AND the control application runs on this same computer. The tested SkySafari configuration uses Celestron WiFi and Access Point mode; other applications use their own connection menus.\n'
                  'While Control Bridge is ON, Diagnostics and Wi-Fi provisioning are disabled. Motor control remains available for optional local jogging; external commands have priority. Switching it OFF attempts Stop on both motors and closes the connection; check the Transfer log for replies. The connected control application can move the telescope.\n'
                  'This application relays telescope traffic, not general LAN traffic or Internet sharing. Compatibility and long-duration operation depend on the control application and network; see the documented validation results.',
                  wraplength=820).grid(row=7, sticky='w', pady=8)
        self.bridge_firewall_label = ttk.Label(tab, foreground='#b36b00', wraplength=820,
                  text='FIREWALL / LOCAL NETWORK: allow this Python application incoming TCP 2000 and 3000 '
                  'from your local network, and outgoing UDP broadcasts to port 55555. '
                  'Allow incoming connections in the computer’s firewall when prompted; enable Local Network access for your control app on iOS (for example SkySafari). '
                  'Do not forward these ports from the Internet. A running bridge does not prove that your firewall allows the control app to connect.\n'
                  'For Two Interface Mode, allow these connections on the adapter facing the astronomy app. The app forwards telescope commands between its connections; it does not enable operating-system network bridging or Internet sharing.')
        self.bridge_firewall_label.grid(row=8, sticky='w', pady=6)
        readout = ttk.LabelFrame(tab, text='Latest motor-position replies from the telescope', padding=6)
        readout.grid(row=9, sticky='ew')
        for row, axis in enumerate(AXES):
            ttk.Label(readout, text=AXES[axis]).grid(row=row, column=0, padx=8)
            for column, field in enumerate(('encoder', 'angle', 'firmware', 'age'), start=1):
                ttk.Label(readout, textvariable=self.values[axis][field], width=17).grid(row=row, column=column)
        self.copy_button(readout, self.motor_output, 'Copy motor table').grid(row=2, columnspan=5, sticky='w', pady=3)
        self.bridge_console = ScrolledText(tab, height=8, wrap='word', state='disabled', font=('TkFixedFont', 10))
        self.bridge_console.grid(row=10, sticky='ew', pady=8)
        ttk.Button(tab, text='Export bridge recording…', command=self.open_recording_export).grid(row=12, sticky='w', pady=6)
        self.copy_button(tab, lambda: self.bridge_status.get() + '\n' + self.bridge_endpoint.get() + '\n' + self.bridge_console.get('1.0', 'end-1c'), 'Copy bridge status and log').grid(row=11, sticky='w')

        self.bridge_heartbeat = tk.BooleanVar(value=False)
        self.bridge_heartbeat_interval = tk.StringVar(value='5')
        self.bridge_monitor = tk.BooleanVar(value=False)
        self.bridge_monitor_interval = tk.StringVar(value='1')
        self.bridge_background_status = tk.StringVar(value='Heartbeat OFF; position recording OFF. Existing replies are still logged.')
        background = ttk.LabelFrame(tab, text='Connection keep-alive and motor-position polling', padding=6)
        background.grid(row=13, sticky='ew', pady=(8, 0))
        ttk.Checkbutton(background, text='Keep connection alive (heartbeat)', variable=self.bridge_heartbeat,
                        command=self.apply_bridge_background_reads).grid(row=0, column=0, sticky='w')
        ttk.Spinbox(background, from_=1, to=300, increment=1, width=7, textvariable=self.bridge_heartbeat_interval).grid(row=0, column=1)
        ttk.Label(background, text='seconds without communication (1–300; default 5)').grid(row=0, column=2, sticky='w')
        ttk.Checkbutton(background, text='Poll and record motor positions', variable=self.bridge_monitor,
                        command=self.apply_bridge_background_reads).grid(row=1, column=0, sticky='w')
        ttk.Spinbox(background, from_=0.2, to=300, increment=0.2, width=7, textvariable=self.bridge_monitor_interval).grid(row=1, column=1)
        ttk.Label(background, text='seconds between motor-position reads (0.2–300; default 1)').grid(row=1, column=2, sticky='w')
        ttk.Button(background, text='Apply intervals', command=self.apply_bridge_background_reads).grid(row=2, column=0, sticky='w', pady=4)
        ttk.Label(background, textvariable=self.bridge_background_status, wraplength=760).grid(row=3, columnspan=3, sticky='w')
        ttk.Label(background, text='To record motion: check Poll and record motor positions, enter the interval in seconds, then click Apply intervals. 1 = about one sample per second; 5 = one every five seconds; 0.2 = up to five per second (experimental). Smaller numbers add traffic. Incoming position replies are reused; missing samples are requested.\nTo keep an otherwise quiet connection active: check Keep connection alive and set its quiet interval. Normal traffic or position polling satisfies it; a second set of requests is not sent. Both options work with or without a connected control app.\nBoth unchecked: no optional position queries; received replies are still logged. Local jogging, when enabled on Motor control, requires fresh feedback at 0.4-second intervals and shares this same scheduler. Turn local jogging OFF when using only your external control app to avoid those additional safety reads. Missing replies are logged as gaps; no idle timeout closes the bridge. These options cannot guarantee recovery from a stalled Wi-Fi adapter.', wraplength=760).grid(row=4, columnspan=3, sticky='w')

    def open_recording_export(self):
        window = tk.Toplevel(self.root)
        window.title('Export bridge recording')
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill='both', expand=True)
        source = tk.StringVar(value=str(Path(self.log_directory) / 'events.jsonl') if self.log_directory else '')
        selection, output_format = tk.StringVar(value='both'), tk.StringVar(value='csv')
        time_format = tk.StringVar(value='local')
        first, last = tk.StringVar(), tk.StringVar()
        status = tk.StringVar(value='Choose a recording to display its available time range.')
        availability = tk.StringVar(value='Available range: not loaded')
        bounds = {}
        ttk.Label(frame, text='Source: events.jsonl file or logs folder (multiple sessions)').grid(row=0, columnspan=3, sticky='w')
        ttk.Entry(frame, textvariable=source, width=78).grid(row=1, columnspan=3, sticky='ew')
        def refresh():
            chosen = source.get()
            availability.set('Reading available timestamps…')
            bounds.clear()
            def worker():
                try:
                    result = recording_bounds(chosen)
                except Exception as error:
                    result = {'error': str(error)}
                self.events.put({'event': 'recording_range_done', 'apply': apply_range, 'result': result, 'source': chosen})
            threading.Thread(target=worker, daemon=True).start()
        def apply_range(result, chosen):
            if not window.winfo_exists() or chosen != source.get():
                return
            if result.get('error'):
                availability.set('Available range: ' + result['error'])
                return
            lower = parse_timestamp(result['first']).astimezone().replace(microsecond=0)
            upper = parse_timestamp(result['last']).astimezone().replace(microsecond=0)
            bounds.update(first=lower, last=upper, source=chosen)
            first.set(lower.isoformat(sep=' ', timespec='seconds'))
            last.set(upper.isoformat(sep=' ', timespec='seconds'))
            availability.set(f'Available: {first.get()} through {last.get()} — {result["sessions"]} session file(s). Times shown in this computer’s local zone, with UTC offsets.')
            status.set('Prefilled with the complete available range. Choose start/end within these limits.')
        def browse(folder=False):
            chosen = filedialog.askdirectory(parent=window, title='Choose logs folder') if folder else filedialog.askopenfilename(parent=window, title='Choose recording', filetypes=[('JSONL log', '*.jsonl'), ('All files', '*')])
            if chosen:
                source.set(chosen)
                refresh()
        ttk.Button(frame, text='Choose file…', command=browse).grid(row=2, column=0, sticky='w')
        ttk.Button(frame, text='Choose sessions folder…', command=lambda: browse(True)).grid(row=2, column=1, sticky='w')
        ttk.Button(frame, text='Refresh available range', command=refresh).grid(row=2, column=2, sticky='w')
        ttk.Label(frame, textvariable=availability, wraplength=690).grid(row=3, columnspan=3, sticky='w', pady=8)
        ttk.Label(frame, text='Start date/time (inclusive):').grid(row=4, column=0, sticky='w')
        ttk.Entry(frame, textvariable=first, width=35).grid(row=4, column=1, columnspan=2, sticky='w')
        ttk.Label(frame, text='End date/time (inclusive second):').grid(row=5, column=0, sticky='w')
        ttk.Entry(frame, textvariable=last, width=35).grid(row=5, column=1, columnspan=2, sticky='w')
        ttk.Label(frame, text='Format: YYYY-MM-DD HH:MM:SS±HH:MM (UTC offset). Edit the prefilled values; dates outside the displayed range are rejected.', wraplength=690).grid(row=6, columnspan=3, sticky='w')
        for row, (label, value) in enumerate((('Wi-Fi packets and commands', 'packets'), ('Measured motor positions', 'positions'), ('Both in one timestamped file', 'both')), 7):
            ttk.Radiobutton(frame, text=label, variable=selection, value=value).grid(row=row, columnspan=3, sticky='w')
        ttk.Label(frame, text='File format:').grid(row=10, column=0, sticky='w')
        ttk.Combobox(frame, textvariable=output_format, values=('csv', 'json'), state='readonly', width=12).grid(row=10, column=1, sticky='w')
        ttk.Radiobutton(frame, text='Local time with UTC offset', variable=time_format, value='local').grid(row=11, columnspan=3, sticky='w')
        ttk.Radiobutton(frame, text='Unix time (seconds since epoch, UTC)', variable=time_format, value='unix').grid(row=12, columnspan=3, sticky='w')
        ttk.Label(frame, text='The timestamp column explicitly names local ISO 8601 or Unix seconds UTC. Original UTC and monotonic values remain available. Active logs export written data only; refresh the range to include newer data. Encoder angles are not aligned sky coordinates.', wraplength=690).grid(row=13, columnspan=3, sticky='w', pady=8)
        ttk.Label(frame, textvariable=status, wraplength=690).grid(row=15, columnspan=3, sticky='w')
        def save():
            try:
                if bounds.get('source') != source.get():
                    raise ValueError('Click Refresh available range for the selected source first.')
                start, end = parse_timestamp(first.get()), parse_timestamp(last.get())
                if not bounds['first'] <= start <= end <= bounds['last']:
                    raise ValueError('Start and end must be ordered and within the displayed available range.')
                end += dt.timedelta(seconds=1)
            except (ValueError, TypeError) as error:
                status.set(f'Not exported: {error}')
                return
            fmt, chosen_source, scope, clock_format = output_format.get(), source.get(), selection.get(), time_format.get()
            destination = filedialog.asksaveasfilename(parent=window, title='Save recording export', defaultextension='.' + fmt, filetypes=[(fmt.upper(), '*.' + fmt)])
            if not destination:
                return
            status.set('Exporting written log snapshot…')
            def worker():
                try:
                    report = export_recording(chosen_source, destination, scope, fmt, start, end, clock_format)
                    message = f'Saved {report["records"]} records to {destination}'
                    if report['warnings']:
                        message += ' — ' + '; '.join(report['warnings'])
                except Exception as error:
                    message = f'Export failed: {error}'
                self.events.put({'event': 'recording_export_done', 'status_variable': status, 'message': message})
            threading.Thread(target=worker, daemon=True).start()
        ttk.Button(frame, text='Export…', command=save).grid(row=14, column=0, sticky='w', pady=6)
        if source.get():
            refresh()

    def refresh_network_interfaces(self):
        """Request a fresh interface inventory on a worker thread."""
        if self.interface_refreshing:
            return
        self.interface_refreshing = True
        self.interface_refresh_button.configure(state='disabled')
        def worker():
            try:
                self.events.put({'event': 'network_interfaces', 'rows': self.network_provider()})
            except Exception as error:
                self.events.put({'event': 'network_interfaces', 'rows': [], 'error': str(error)})
        threading.Thread(target=worker, daemon=True).start()

    def show_network_interfaces(self):
        """Render current adapter addresses and active bridge socket roles."""
        self.interface_table.delete(*self.interface_table.get_children())
        for row in self.interface_rows:
            role = (f'TCP {self.bridge_listener[1]} / {self.bridge_listener[2]}'
                    if self.bridge_listener and row['ip'] == self.bridge_listener[0] else 'Not used for control app connections')
            if self.bridge_upstream_local and row['ip'] == self.bridge_upstream_local[0]:
                role += ' · connects to telescope'
            self.interface_table.insert('', 'end', values=(row['interface'], row['name'], row['ip'], row['state'], role))

    def select_bridge_interface(self, event=None):
        """Use the selected computer address as the phone-facing bridge listener."""
        if self.bridge is not None:
            return
        selected = self.interface_table.selection()
        if selected:
            ip = self.interface_table.item(selected[0], 'values')[2]
            if ip == '—':
                self.bridge_status.set('The selected adapter has no IPv4 address. Connect it to the astronomy app’s network in your operating system, then click Refresh Adapter IPs and select it again.')
            elif ip.startswith('127.'):
                self.bridge_status.set('Loopback is local to this computer. Choose the interface on the network used by telescope-control software.')
            else:
                self.bridge_bind.set(ip)

    def toggle_bridge(self):
        """Validate shared-network settings, then start or stop the exclusive relay."""
        if not self.bridge_enabled.get():
            if self.bridge:
                self.bridge.stop()
                self.bridge_status.set('Turning Control Bridge OFF — sending Stop to both motors and waiting briefly for replies…')
            return
        if self.bridge is not None:
            self.bridge_enabled.set(False)
            return
        if self.busy or self.motor is not None:
            self.bridge_enabled.set(False)
            self.bridge_status.set('Wait for the current operation to finish. If Motor control is connected, click Disconnect on that tab before switching Control Bridge ON.')
            return
        if self.connection_mode.get() != 'infrastructure' and not self.bridge_dual.get():
            self.bridge_enabled.set(False)
            self.bridge_status.set('Direct/ad hoc requires Two Interface Mode. Enable it, connect a second adapter to the astronomy app’s network, and select that adapter’s IPv4 address below. Alternatively, select Infrastructure when the telescope and control device share an access point.')
            return
        if self.bridge_dual.get() and not self.bridge_bind.get().strip():
            self.bridge_enabled.set(False)
            self.bridge_status.set('Two Interface Mode requires this computer’s IPv4 address on the astronomy app’s network. Select that adapter in Local System Network Interfaces, or enter its IPv4 address above.')
            return
        try:
            self.bridge_last_error = None
            self.bridge = self.bridge_factory(self.host.get(), self.port.get(), self.events.put,
                                               bind_host=self.bridge_bind.get().strip(),
                                               allow_direct_upstream=self.bridge_dual.get(),
                                               heartbeat_enabled=self.bridge_heartbeat.get(),
                                               heartbeat_interval=self.bridge_heartbeat_interval.get(),
                                               monitor_enabled=self.bridge_monitor.get(),
                                               monitor_interval=self.bridge_monitor_interval.get())
            self.last_positions.clear()
            for values in self.values.values():
                for value in values.values():
                    value.set('—')
            self.bridge_status.set('Starting bridge — checking telescope communication…')
            self.bridge_jog_note.set('Local jogging OFF. External app controls motion. Enable here only with clear travel; external commands have priority.')
            self.tabs.select(self.bridge_tab)
            self.bridge.start()
        except Exception as error:
            self.bridge = None
            self.bridge_enabled.set(False)
            self.bridge_status.set(str(error))
        self.update_controls()

    def handle_bridge_event(self, event):
        """Apply worker events to bridge status, tab locks and readbacks."""
        kind = event['event']
        if kind == 'bridge_local_mode':
            self.bridge_jog_active = event['enabled']
            self.bridge_jog_requested.set(event['enabled'])
            self.bridge_jog_ready = False
            self.last_positions.clear()
            self.clear_local_references()
            self.bridge_jog_note.set(event['message'])
            self.motor_status.set('Bridge connected — local jogging ' + ('ON; waiting for feedback' if event['enabled'] else 'OFF'))
        elif kind == 'bridge_local_motion':
            self.jogging = event['moving']
            if not self.jogging:
                self.held = False
            self.bridge_jog_note.set(event['message'])
            if getattr(self.bridge, 'local_fault', False):
                self.bridge_jog_ready = False
                self.motor_status.set('Bridge connected — local jogging locked after feedback loss')
        if kind == 'bridge_values':
            self.handle_motor_event({**event, 'event': 'motor_values'})
            self.bridge_jog_ready = self.bridge_jog_active and not getattr(self.bridge, 'local_fault', False) and all(time.monotonic() - self.last_positions.get(a, 0) < 2 for a in AXES)
            self.update_controls()
            return
        if event.get('log_directory'):
            self.log_directory = event['log_directory']
            self.logs_button.configure(state='normal')
        message = event.get('message')
        if kind == 'bridge_error' and self.bridge_last_error is None:
            self.bridge_last_error = message
        if kind == 'bridge_ready':
            self.motor_status.set('Bridge connected — local jogging OFF')
        if kind == 'bridge_ready' and event.get('bind_host'):
            self.bridge_listener = (event['bind_host'], event['listen_port'], event['management_port'])
            self.bridge_upstream_local = event.get('upstream_local')
            self.bridge_endpoint.set(f'Control Bridge is ON. In your astronomy app, enter this computer’s IPv4 address {event["bind_host"]} and TCP port {event["listen_port"]}.\n'
                                     f'Network details: adapter management uses TCP {event["management_port"]}; discovery uses UDP 55555. If the app cannot connect, check the firewall instructions below.')
            if self.bridge_upstream_local:
                self.bridge_endpoint.set(self.bridge_endpoint.get() +
                    f'\nComputer-to-telescope connection: {self.bridge_upstream_local[0]}:{self.bridge_upstream_local[1]}'
                    f' → {self.host.get()}:{self.port.get()}')
            self.show_network_interfaces()
        if kind == 'bridge_off':
            self.motor_status.set('Disconnected — Control Bridge is OFF')
            self.bridge_jog_active = self.bridge_jog_ready = False
            self.bridge_jog_requested.set(False)
            self.jogging = self.held = False
            self.bridge = None
            self.bridge_listener = None
            self.bridge_upstream_local = None
            self.bridge_enabled.set(False)
            self.bridge_endpoint.set('Control Bridge is OFF. To reconnect your astronomy app, switch Control Bridge ON and use the IPv4 address and TCP port shown here.')
            self.show_network_interfaces()
            message = 'Bridge OFF — ' + (self.bridge_last_error or 'the telescope connection is closed. Check the Transfer log for motor Stop replies before reconnecting.')
            if event.get('stop_replies') and not all(event['stop_replies'].values()):
                message += ' One or more Stop acknowledgements were not received; physical rest is unverified.'
        if message:
            self.bridge_status.set(message)
        line = message or (f'{event.get("direction", "")} AUX {event["hex"]} ({event.get("interpretation", "interpretation unavailable")})' if kind == 'bridge_packet'
                           else f'Management request: {event.get("operation", "")}' if kind == 'bridge_management' else kind)
        self.append('BRIDGE ' + line)
        self.bridge_console.configure(state='normal')
        self.bridge_console.insert('end', line + '\n')
        if int(self.bridge_console.index('end-1c').split('.')[0]) > 1000:
            self.bridge_console.delete('1.0', '100.0')
        self.bridge_console.see('end')
        self.bridge_console.configure(state='disabled')
        self.update_controls()

    def start_recovery(self, reconnect=False):
        """Queue a verified adapter restart, optionally followed by motor reconnection."""
        if self.busy or self.motor is not None or self.bridge is not None:
            self.status.set('Restart is unavailable during another operation. Wait for it to finish; click Disconnect on Motor control if connected, or switch Control Bridge OFF if running. Leave telescope power on.')
            return
        try:
            host, port = validate_endpoint(self.host.get(), self.port.get())
        except ValueError as error:
            self.status.set(str(error))
            return
        self.set_busy(True)
        self.reconnect_after_recovery = reconnect
        self.status.set('Restarting the Wi-Fi adapter, then checking motor positions…')
        def worker():
            try:
                report = self.recovery(host, port, callback=self.events.put)
            except Exception as error:
                report = {'error': str(error)}
            self.events.put({'event': 'recovery_done', 'report': report})
        threading.Thread(target=worker, daemon=True).start()

    def show_diagnostic_reply(self, event=None):
        """Display the selected diagnostic row’s full captured response."""
        selected = self.diagnostic_rows.selection()
        if selected:
            self.diagnostic_details.configure(state='normal')
            self.diagnostic_details.delete('1.0', 'end')
            self.diagnostic_details.insert('end', self.diagnostic_replies.get(selected[0], ''))
            self.diagnostic_details.configure(state='disabled')

    def abort_diagnostics(self):
        if self.diagnostic_running:
            self.diagnostic_cancel.set()
            self.diagnostic_abort_button.configure(state='disabled')
            self.diagnostic_status.set('Stopping diagnostics after the current query finishes or times out. Results already received will be kept…')

    def start_diagnostics(self):
        """Queue read-only adapter and motor checks under exclusive ownership."""
        if self.busy or self.motor is not None or self.bridge is not None:
            self.status.set('Diagnostics is unavailable during another operation. Wait for it to finish; click Disconnect on Motor control if connected, or switch Control Bridge OFF if running. Leave telescope power on.')
            return
        try:
            host, port = validate_endpoint(self.host.get(), self.port.get())
        except ValueError as error:
            self.status.set(str(error))
            return
        deep = self.deep_diagnostics.get()
        if deep and not messagebox.askyesno('Deep Diagnostics Read',
                'Poll additional model-dependent AUX registers and extended WiFly settings?\n'
                'This takes longer and may disrupt an older controller connection. Keep the mount stationary and other controllers disconnected.\n'
                'No motion, setting, reset, or firmware commands will be sent.', parent=self.winfo_toplevel()):
            return
        self.diagnostic_rows.delete(*self.diagnostic_rows.get_children())
        self.diagnostic_replies.clear()
        self.last_positions.clear()
        for values in self.values.values():
            for value in values.values():
                value.set('—')
        self.diagnostic_details.configure(state='normal')
        self.diagnostic_details.delete('1.0', 'end')
        self.diagnostic_details.configure(state='disabled')
        self.set_busy(True)
        self.diagnostic_cancel.clear()
        self.diagnostic_running = True
        self.diagnostic_abort_button.configure(state='normal')
        self.diagnostic_status.set(f'Testing {host}:{port} — waiting for replies…')
        self.tabs.select(self.diagnostic_tab)
        def worker():
            try:
                report = self.diagnostic(host, port, callback=self.events.put, cancel=self.diagnostic_cancel, **({'deep': True} if deep else {}))
            except Exception as error:
                report = {'error': str(error)}
            self.events.put({'event': 'diagnostic_done', 'report': report})
        threading.Thread(target=worker, daemon=True).start()

    def preset(self, home):
        """Select network-mode defaults without changing OS Wi-Fi or the mount switch."""
        if self.busy or self.motor is not None or self.bridge is not None:
            return
        address = '1.2.3.4'
        self.connection_mode.set('infrastructure' if home else 'direct')
        self.update_mode_help()
        if home:
            address = self.last_infrastructure_host or ''
        self.host.set(address)
        self.port.set('2000')
        self.status.set('Enter or discover the telescope’s router-assigned IP; DHCP addresses may change.' if home else
                        'Direct / ad hoc: connect this computer to SkyQLink-xx. Use Discover SkyQLink / Celestron Modules to check the connection.')

    def update_mode_help(self):
        """Explain the selected connection mode and refresh control availability."""
        if self.connection_mode.get() == 'direct':
            text = 'Direct / ad hoc: connect this computer to SkyQLink-xx, then use 1.2.3.4:2000.'
        else:
            text = 'Infrastructure: connect to the same local Wi-Fi or wired LAN; use the telescope’s assigned IP and port 2000.'
        self.mode_help.set(text + '\nThis selects connection settings; it does not change the telescope switch or this computer’s Wi-Fi.')
        self.update_controls()

    def scan_lan(self):
        """Validate discovery settings and start bounded module identification."""
        if self.busy or self.motor is not None or self.bridge is not None:
            self.status.set('Discovery is unavailable during another operation. Wait for it to finish; click Disconnect on Motor control if connected, or switch Control Bridge OFF if running.')
            return
        if self.connection_mode.get() == 'infrastructure' and self.host.get().strip() == '1.2.3.4':
            self.status.set('1.2.3.4 is the direct-connect address. Select Direct / ad hoc mode, or enter the telescope’s address on the shared access-point network.')
            return
        self.set_busy(True)
        try:
            port = validate_port(self.port.get())
        except ValueError as e:
            self.set_busy(False)
            self.status.set(str(e))
            return
        self.status.set(f'Discovering Celestron modules on TCP {port}… Disconnect any connected control apps (for example CPWI or SkySafari).')
        self.scan_started = time.monotonic()
        self.scan_button.configure(text='Scanning…')
        self.tick_scan()
        self.append(f'DISCOVERY — check motor/adapter firmware replies on TCP {port}; no movement or setting changes.')
        scan_mode = self.connection_mode.get()
        def worker():
            try:
                report = self.scanner(port=port, callback=self.events.put, mode=scan_mode)
            except Exception as e:
                report = {'error': str(e)}
            self.events.put({'event': 'scan_done', 'report': report})
        threading.Thread(target=worker, daemon=True).start()

    def tick_scan(self):
        """Update elapsed search-period feedback until discovery finishes."""
        if self.scan_started is None:
            return
        elapsed = time.monotonic() - self.scan_started
        text = (f'● Scanning — {elapsed:.0f}s / 60s search period' if elapsed < 60 else
                f'● Search period reached — finishing active probes ({elapsed:.0f}s)')
        self.scan_indicator.configure(text=text, foreground='#b36b00' if int(elapsed * 2) % 2 else '#d99a00')
        self.scan_tick_id = self.root.after(250, self.tick_scan)

    def select_module(self):
        """Apply the verified endpoint and preserve its direct or infrastructure mode."""
        if self.busy or self.motor is not None or self.bridge is not None:
            return
        index = self.module_box.current()
        if 0 <= index < len(self.discovered):
            match = self.discovered[index]
            self.connection_mode.set('direct' if match['ip'] == '1.2.3.4' else 'infrastructure')
            self.update_mode_help()
            self.host.set(match['ip'])
            self.port.set(str(match.get('port', 2000)))
            if match['ip'] != '1.2.3.4':
                self.last_infrastructure_host = match['ip']
            self.status.set(f'Verified {match.get("module_type", "Celestron AUX")}: {match["ip"]}:{match.get("port", 2000)}')

    def update_controls(self):
        """Refresh widget locks and conditional shared-network interface guidance."""
        separate_network = self.bridge_dual.get() or self.connection_mode.get() == 'direct'
        self.bridge_ip_help.set('This computer’s IP on the control-device network' if separate_network else 'This computer’s IP on the shared infrastructure network')
        self.bridge_interface_help.set(
            'Two Interface Mode: do not leave this field blank. Use this computer’s IP on the network used by your phone, tablet or other control computer, not its direct SkyQLink connection. The bridge needs this address to accept control connections. Connect the adapter to that network in your operating system before selecting its row here.'
            if separate_network else
            'Shared infrastructure network: the telescope, this computer and your control device are connected to the same local network. You may leave this field blank: the program automatically uses this computer’s network adapter used to reach the telescope. To choose explicitly, select that adapter in the table below or enter its IPv4 address. Enter this computer’s address, not the telescope’s address or a MAC address.')
        direct_mode = self.connection_mode.get() == 'direct'
        self.bridge_direct_help.configure(
            text=('Direct/ad hoc: check the Two Interface Mode checkbox. One Wi-Fi adapter connects to SkyQLink; choose a second connection below for a control device on another network.' if direct_mode else
                  'Shared Infrastructure: one adapter normally connects this computer, telescope and control device through the same network. Leave the Two Interface Mode checkbox unchecked. Use the options below only when deliberately bridging separate networks.'),
            foreground=self.normal_text)
        self.bridge_options_note.configure(foreground=self.normal_text if separate_network else self.muted_text)
        for label in self.bridge_option_labels:
            label.configure(foreground=self.normal_text if direct_mode or self.bridge_dual.get() else self.muted_text)
        locked = self.busy or self.motor is not None or self.bridge is not None
        for tab in (self.diagnostic_tab, self.provision_tab):
            self.tabs.tab(tab, state='disabled' if self.bridge is not None else 'normal')
        self.tabs.tab(self.motor_tab, state='normal', image=self.bridge_tab_mark if self.bridge else '', compound='left',
                      text='Motor control — bridge' if self.bridge else 'Motor control')
        if self.bridge:
            self.bridge_jog_box.grid()
        else:
            self.bridge_jog_box.grid_remove()
        self.bridge_jog_switch.configure(state='normal' if self.bridge else 'disabled')
        self.motor_settings_button.configure(state='disabled' if self.bridge else 'normal')
        direct_policy_locked = self.bridge is not None or self.motor is not None or self.busy
        for widget in self.direct_policy_frame.winfo_children():
            widget.state(['disabled'] if direct_policy_locked else ['!disabled'])
            if isinstance(widget, ttk.Label):
                widget.configure(foreground=self.muted_text if direct_policy_locked else self.normal_text)
        self.direct_policy_title.state(['disabled'] if direct_policy_locked else ['!disabled'])
        self.direct_policy_title.configure(foreground=self.muted_text if direct_policy_locked else self.normal_text)
        self.direct_policy_frame.state(['disabled'] if direct_policy_locked else ['!disabled'])
        self.idle_release_box.configure(state='disabled' if direct_policy_locked else 'readonly')
        self.motor_heartbeat_box.configure(state='disabled' if direct_policy_locked else 'normal')
        self.motor_heartbeat_box_interval.configure(state='disabled' if direct_policy_locked else 'normal')
        self.motor_connection_help.set(
            'Not used during bridge operation, including local bridge jogging. Use Control Bridge for bridge polling.'
            if self.bridge is not None else
            ('Click Disconnect, edit these settings, then click Connect Motors to apply them. ' if self.motor is not None else 'Choose settings here, then click Connect Motors to apply them. No Apply button or Enter key is needed. ') +
            'Default: release after 30 seconds without movement activity. Keep-alive reads positions while idle; it does not reset this timer. Never retains the connection until Disconnect or a fault. '
            + ('Caution: beyond 30 seconds or Never with keep-alive ON can keep the adapter occupied and lock out other control apps. Disconnect before switching apps. ' if self.motor_heartbeat.get() and self.idle_release.get() in ('1 minute', '2 minutes', '5 minutes', 'Never', 'Off') else '')
            + 'The interval is used only when Keep connection alive is checked. Movement feedback checks remain active.')
        bridge_allowed = self.connection_mode.get() == 'infrastructure' or self.bridge_dual.get()
        if self.bridge is not None:
            notice = 'Control Bridge is running. Switch it OFF to stop and release the connection.'
        elif self.busy or self.motor is not None:
            notice = 'Control Bridge cannot start during another operation. Wait for it to finish, or click Disconnect on Motor control.'
        elif not bridge_allowed:
            notice = 'Control Bridge is disabled: Direct/ad hoc requires Two Interface Mode. Enable it below and select the second adapter’s IPv4 address.'
        elif self.bridge_dual.get():
            notice = 'Two Interface Mode: select this computer’s IPv4 address on the astronomy app’s network, then switch Control Bridge ON.'
        else:
            notice = 'Connect this computer to the telescope network, then switch Control Bridge ON here. Your control app can run here or on another device on the shared LAN; see the steps below.'
        self.bridge_requirement.set(notice)
        self.bridge_switch.configure(state='normal' if self.bridge is not None or (not locked and bridge_allowed) else 'disabled')
        self.bridge_bind_entry.configure(state='disabled' if locked else 'normal')
        self.bridge_dual_box.configure(state='disabled' if locked else 'normal')
        for widget in self.inputs:
            widget.configure(state='disabled' if locked else 'normal')
        for widget in (self.read_button, self.upload_button, self.show):
            widget.configure(state='disabled' if locked else 'normal')
        self.diagnostic_button.configure(state='disabled' if locked else 'normal')
        self.recovery_button.configure(state='disabled' if locked else 'normal')
        self.time_apply_button.configure(state='disabled' if locked else 'normal')
        self.time_sync_button.configure(state='disabled' if locked else 'normal')
        self.auto_recover_button.configure(state='disabled' if locked else 'normal')
        self.security_box.configure(state='disabled' if locked else 'readonly')
        self.motor_connect_button.configure(state='disabled' if locked else 'normal')
        self.module_box.configure(state='readonly' if self.discovered and not locked else 'disabled')
        self.motor_disconnect_button.configure(state='normal' if self.motor is not None else 'disabled')
        for button in self.jog_buttons:
            can_jog = self.bridge_jog_ready if self.bridge else self.motor_ready
            button.configure(state='normal' if can_jog and (not self.jogging or self.held) else 'disabled')
        self.stop_button.configure(state='normal' if self.motor is not None or self.bridge is not None else 'disabled')
        self.speed_box.configure(state='disabled' if self.jogging else 'readonly')
        self.duration_box.configure(state='disabled' if self.jogging else 'readonly')
        self.refresh_password()

    def connect_motors(self, recover_attempted=False):
        """Start the motor service and wait for verified encoder feedback."""
        if self.busy or self.motor is not None or self.bridge is not None:
            return
        try:
            host, port = validate_endpoint(self.host.get(), self.port.get())
            idle = {'Off': 0, 'Never': 0, '10 seconds': 10, '20 seconds': 20, '30 seconds': 30, '1 minute': 60, '2 minutes': 120, '5 minutes': 300}[self.idle_release.get()]
            self.motor = self.motor_factory(host, port, self.events.put, idle_release=idle,
                heartbeat_enabled=self.motor_heartbeat.get(), heartbeat_interval=float(self.motor_heartbeat_interval.get()))
            self.connect_request_active = True
            self.connect_recovery_attempted = recover_attempted
            self.last_motor_error = None
            self.motor_status.set('Connecting…')
            self.motion_status.set('Waiting for valid encoder replies from BOTH motors')
            self.last_positions.clear()
            for values in self.values.values():
                for value in values.values():
                    value.set('—')
            self.motor.start()
            self.update_controls()
        except Exception as e:
            self.motor = None
            self.motor_status.set('Connection failed')
            self.status.set(str(e))
            self.update_controls()

    def jog(self, axis, direction):
        """Queue the selected bounded jog through the active motor service."""
        if self.bridge:
            self.bridge_jog(axis, direction)
            return
        if not self.motor_ready or self.motor is None or self.jogging:
            return
        try:
            self.motor.jog(axis, direction, int(self.speed.get()), float(self.duration.get()))
            self.jogging = True
            self.update_controls()
        except (ValueError, RuntimeError) as e:
            self.status.set(str(e))

    def toggle_keyboard_control(self):
        """Explicit opt-in takes focus; switching off releases any held motion."""
        if not self.keymap:
            self.keyboard_enabled.set(False)
            return
        if self.keyboard_enabled.get():
            self.keyboard_status.set('Keyboard control ON — click this panel after editing')
            self.motor_tab.focus_set()
        else:
            self.stop_motors()
            self.keyboard_status.set('Keyboard control OFF')

    def focus_motor_shortcuts(self, event):
        """Clicks outside editors release stale Entry/Combobox keyboard focus.

        ttk buttons/labels do not consistently take focus on all platforms. An
        IP or speed editor could therefore retain focus after clicking controls,
        causing the intentional text-entry guard to ignore every motor shortcut.
        Keep editors protected; focus only this main window's Motor tab.
        """
        if (self.keyboard_enabled.get() and self.tabs.select() == str(self.motor_tab)
                and event.widget.winfo_toplevel() == self.root
                and event.widget.winfo_class() not in
                ('Entry', 'TEntry', 'Text', 'TCombobox', 'Spinbox', 'TSpinbox')):
            self.motor_tab.focus_set()

    def motor_key_press(self, event):
        key = event.keysym.lower()
        # Tk on Windows uses Mod1 (0x0008) for Num Lock, not Alt. Blocking
        # 0x000C therefore disabled every shortcut with Num Lock enabled.
        # Windows Alt is 0x20000; X11 uses Mod1 for Alt. Keep Ctrl blocked.
        alt_mask = 0x20000 if self.root.tk.call('tk', 'windowingsystem') == 'win32' else 0x0008
        if (not self.keymap or not self.keyboard_enabled.get() or event.widget.winfo_toplevel() != self.root or self.tabs.select() != str(self.motor_tab) or self.busy
                or event.widget.winfo_class() in ('Entry', 'TEntry', 'Text', 'TCombobox', 'Spinbox', 'TSpinbox')
                or event.state & (0x0004 | alt_mask)):
            return
        action = next((action for action, value in self.keymap.items() if value == key), None)
        if self.bridge and action in ('connect', 'disconnect'):
            self.bridge_jog_note.set('Use the local-jog toggle to enable or disable local jogging. Use Control Bridge OFF to disconnect the bridge.')
            return 'break'
        if action == 'connect':
            self.connect_motors()
            return 'break'
        if action == 'disconnect':
            self.stop_motors()
            self.disconnect_motors()
            return 'break'
        if action == 'stop':
            self.stop_motors()
            return 'break'
        mapping = {'elevation_up': (0x11, 1), 'elevation_down': (0x11, -1), 'azimuth_left': (0x10, -1), 'azimuth_right': (0x10, 1)}
        if action not in mapping:
            return
        if self.keyboard_direction == key:
            if self.keyboard_release_id:
                self.after_cancel(self.keyboard_release_id)
                self.keyboard_release_id = None
            return 'break'
        if self.keyboard_direction or not (self.bridge_jog_ready if self.bridge else self.motor_ready) or self.jogging:
            return 'break'
        self.keyboard_direction = key
        if self.drive_mode.get() == 'hold':
            self.press_direction(*mapping[action])
        else:
            self.timed_direction(*mapping[action])
        return 'break'

    def motor_key_release(self, event):
        if event.keysym.lower() != self.keyboard_direction:
            return
        if self.keyboard_release_id:
            self.after_cancel(self.keyboard_release_id)
        def released():
            self.keyboard_release_id = None
            self.keyboard_direction = None
            self.release_direction()
        self.keyboard_release_id = self.after(30, released)
        return 'break'

    def timed_direction(self, axis, direction):
        """Run the chosen direction for the selected bounded duration."""
        if self.drive_mode.get() == 'jog':
            self.jog(axis, direction)

    def press_direction(self, axis, direction):
        """Start a held direction when validated motor controls are ready."""
        if self.bridge:
            if self.drive_mode.get() == 'hold':
                self.bridge_jog(axis, direction, held=True)
            return
        if self.drive_mode.get() != 'hold' or not self.motor_ready or self.motor is None or self.jogging:
            return
        try:
            self.motor.hold(axis, direction, int(self.speed.get()))
            self.held = True
            self.jogging = True
            self.update_controls()
        except (ValueError, RuntimeError) as e:
            self.status.set(str(e))

    def release_direction(self):
        """Release a manual direction and request Stop."""
        if self.held:
            self.stop_motors()

    def stop_motors(self):
        """Request priority Stop and clear held-button state."""
        self.keyboard_direction = None
        if self.keyboard_release_id:
            self.after_cancel(self.keyboard_release_id)
            self.keyboard_release_id = None
        self.held = False
        if self.bridge:
            self.bridge.stop_local_jog()
        if self.motor:
            self.motor.stop()
            self.motor_status.set('Stopping…')

    def disconnect_motors(self):
        """Stop renewing manual motion and request service disconnection."""
        self.connect_request_active = False
        if self.motor:
            self.motor_ready = False
            self.motor.disconnect()
            self.motor_status.set('Stopping and disconnecting…')
            self.update_controls()

    def stop_if_unfocused(self):
        """Stop a held direction when focus leaves the application."""
        if (self.motor or self.bridge) and self.jogging and self.root.focus_get() is None:
            self.stop_motors()

    def refresh_password(self):
        """Update password visibility and open-network input availability."""
        enabled = not self.busy and self.motor is None and self.bridge is None and self.security.get() != 'Open (no password)'
        self.password_entry.configure(show='' if self.show_password.get() else '•',
                                      state='normal' if enabled else 'disabled')

    def show_provisioned_network(self, report):
        """Present the current adapter’s provisioning status and overwrite notice."""
        before = report.get('readback') or report.get('before', {})
        wlan = before.get('wlan', before.get('get wlan', ''))
        ip = before.get('ip', before.get('get ip', ''))
        fields = dict(line.split('=', 1) for line in wlan.splitlines() if '=' in line)
        self.provision_ssid_readback.set(fields.get('SSID', '').strip() or 'SSID not returned by telescope')
        join = fields.get('Join', '').strip()
        mode = 'Infrastructure (automatic network joining)' if join == '1' else 'Join setting: ' + (join or 'not returned')
        self.provision_mode_readback.set('Configuration readback: ' + mode + ' — this is not a physical switch sensor.')
        if fields.get('Join', '').strip() == '1' and 'DHCP=ON' in ip:
            self.provision_notice.set(
                'Upload & Save replaces this network name, password and security with the values entered here. '
                'You can change networks over this existing infrastructure connection; no ad hoc switch or factory reset is required. '
                'Restart afterward, join the new network and discover the new telescope IP.')

    def append(self, text):
        """Append one line to the read-only on-screen transfer log."""
        self.console.configure(state='normal')
        self.console.insert('end', dt.datetime.now().strftime('%H:%M:%S') + '  ' + text.replace('\r', '') + '\n')
        self.console.see('end')
        if int(self.console.index('end-1c').split('.')[0]) > 1200:
            self.console.delete('1.0', '200.0')
        self.console.configure(state='disabled')

    def clear(self):
        """Clear the displayed transfer log without deleting saved evidence."""
        if not messagebox.askyesno('Clear displayed log?',
                'Clear the on-screen log? Saved session logs will NOT be deleted. '
                'Use Open Logs to access saved files.', parent=self.winfo_toplevel()):
            return
        self.console.configure(state='normal')
        self.console.delete('1.0', 'end')
        self.console.configure(state='disabled')

    def set_busy(self, value):
        """Mark an exclusive operation active and refresh UI controls."""
        self.busy = value
        self.clear_button.configure(state='disabled' if value else 'normal')
        self.update_controls()
        if value:
            self.progress.pack(side='right', padx=8)
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def start(self, apply):
        """Validate provisioning inputs and queue a read or explicitly confirmed settings upload."""
        if self.busy or self.motor is not None or self.bridge is not None:
            self.status.set('Wi-Fi settings are unavailable during another operation. Wait for it to finish; click Disconnect on Motor control if connected, or switch Control Bridge OFF if running.')
            return
        try:
            host, port = validate_endpoint(self.host.get(), self.port.get())
            security, ssid = self.security.get(), self.ssid.get()
            password = self.password.get() if security != 'Open (no password)' else ''
            if apply:
                make_plan(ssid, password, security)
        except ValueError as e:
            self.status.set(str(e))
            return
        self.set_busy(True)
        self.status.set('Uploading settings…' if apply else 'Connecting and reading settings…')
        self.append(('UPLOAD' if apply else 'READ ONLY') + f' — {host}:{port}')
        def worker():
            try:
                report = self.operation(host, port, ssid, password, security, apply,
                                        callback=self.events.put)
            except Exception:
                report = {'error': 'Operation could not start. Check endpoint and network connection.'}
            self.events.put({'event': 'done', 'report': report})
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        """Drain worker events on the Tk thread and refresh telemetry ages."""
        try:
            while True:
                event = self.events.get_nowait()
                kind = event['event']
                if kind == 'recording_range_done':
                    event['apply'](event['result'], event['source'])
                elif kind == 'recording_export_done':
                    event['status_variable'].set(event['message'])
                    self.append(event['message'])
                elif kind == 'network_interfaces':
                    self.interface_refreshing = False
                    self.interface_refresh_button.configure(state='normal')
                    self.interface_rows = event['rows']
                    self.show_network_interfaces()
                    if event.get('error'):
                        self.append('COMPUTER NETWORK: ' + event['error'])
                elif kind.startswith('bridge_'):
                    self.handle_bridge_event(event)
                elif kind.startswith('motor_') and kind != 'motor_settings_done':
                    self.handle_motor_event(event)
                elif kind == 'scan_progress':
                    self.status.set(event['message'])
                    self.append(event['message'])
                elif kind == 'recovery_done':
                    self.set_busy(False)
                    report = event['report']
                    text = ('Adapter restarted; both motor encoders replied. Connect Motors to control the telescope.'
                            if report.get('motor_positions_verified') else
                            'Motor replies still unavailable after adapter restart. Check power and other telescope clients.')
                    if report.get('error'):
                        text = report['error']
                    self.status.set(text)
                    self.diagnostic_status.set(text)
                    self.append(text)
                    for axis, count in report.get('positions', {}).items():
                        self.append(f'ENCODER {axis}: {count if count is not None else "No reply"}')
                    self.log_directory = report.get('log_directory')
                    self.logs_button.configure(state='normal' if self.log_directory else 'disabled')
                    reconnect = self.reconnect_after_recovery
                    self.reconnect_after_recovery = False
                    if reconnect and report.get('motor_positions_verified') and not self.closing:
                        self.connect_motors(recover_attempted=True)
                elif kind == 'diagnostic_row':
                    preview = ' | '.join(line.strip() for line in event['reply'].splitlines() if line.strip())
                    item = self.diagnostic_rows.insert('', 'end', values=(event['device'], event['endpoint'], event['status'], preview))
                    self.diagnostic_replies[item] = event['reply']
                    self.diagnostic_rows.see(item)
                    if not self.diagnostic_rows.selection():
                        self.diagnostic_rows.selection_set(item)
                        self.show_diagnostic_reply()
                    self.append(f'DIAGNOSTIC {event["device"]} / {event["endpoint"]}: {event["status"]}')
                    self.append('REPLY DATA  ' + event['reply'])
                elif kind == 'diagnostic_position':
                    values = self.values[event['axis']]
                    values['encoder'].set(str(event['encoder']))
                    values['angle'].set(f'{event["angle"]:.5f}°')
                    values['relative'].set('—')
                    values['firmware'].set(event['firmware'])
                    self.last_positions[event['axis']] = event['monotonic']
                elif kind == 'diagnostic_done':
                    self.diagnostic_running = False
                    self.diagnostic_abort_button.configure(state='disabled')
                    self.set_busy(False)
                    report = event['report']
                    if self.calibration is not None and not report.get('saved_report'):
                        try:
                            identify_profile(self.calibration, report)
                            save_config(self.calibration)
                            self.reload_calibration()
                            self.append('Calibration matched by adapter MAC; network address updated.')
                        except (ValueError, OSError, KeyError) as error:
                            self.append('Calibration identity: ' + str(error))
                    self.time_zone.set(report.get('wifly_clock', {}).get('Zone setting (raw)', 'Not reported'))
                    identity = next((row.get('reply', '') for row in report.get('rows', []) if row.get('endpoint') == 'get mac'), '')
                    evidence = self.check_uptime_evidence(identity, report.get('wifly_clock', {}))
                    self.append('Reset check: ' + evidence)
                    text = ('Wi-Fi: ' + ('VERIFIED' if report.get('wifi_verified') else 'NOT VERIFIED') +
                            ' | Motor firmware: ' + ('VERIFIED' if report.get('motor_firmware_verified') else 'NOT VERIFIED') +
                            ' | Both motor positions: ' + ('VERIFIED' if report.get('motor_positions_verified') else 'NOT VERIFIED'))
                    if report.get('aborted'):
                        text = 'ABORTED — partial results retained | ' + text
                    if report.get('saved_report'):
                        text = 'SAVED TEST RESULT — ' + text
                    if report.get('error'):
                        text += ' | ' + report['error']
                    self.diagnostic_status.set(text)
                    self.status.set(text)
                    self.append(text)
                    self.log_directory = report.get('log_directory')
                    self.logs_button.configure(state='normal' if self.log_directory else 'disabled')
                elif kind == 'motor_settings_done':
                    self.set_busy(False)
                    result = event['report']
                    text = result.get('error') or f"{AXES[result['axis']]} settings read back successfully"
                    self.motor_setting_status.set(text)
                    self.append(text)
                    axis = result['axis']
                    if result.get('values'):
                        values = result['values']
                        degrees = values['degrees']
                        if axis == 0x11 and degrees > 180:
                            degrees -= 360
                        stamp = dt.datetime.now().strftime('%H:%M:%S')
                        source = 'Verified after Apply' if result.get('writes') else 'Read current values result'
                        self.controller_readout[axis].set(f"{source} at {stamp}\nEncoder angle: {degrees:.5f}°\nPositive-direction backlash: {values['positive_backlash']}\nNegative-direction backlash: {values['negative_backlash']}")
                        fields = self.controller_fields[axis]
                        fields['angle'].set(f'{degrees:.5f}')
                        fields['positive'].set(str(values['positive_backlash']))
                        fields['negative'].set(str(values['negative_backlash']))
                        self.controller_reads[axis] = {'values': dict(values), 'time': time.monotonic(), 'endpoint': event.get('endpoint', (self.host.get(), int(self.port.get())))}
                    else:
                        self.controller_reads.pop(axis, None)
                        self.controller_readout[axis].set('Read failed — current telescope values unknown. ' + result.get('error', 'No values returned.'))
                    if result.get('writes'):
                        verified = not result.get('error') and all(w.get('verified') for w in result['writes'])
                        self.controller_history[axis].set(dt.datetime.now().strftime('%H:%M:%S') + ' — ' + ('Verified: ' if verified else 'UNCERTAIN / partial change: ') + event.get('preview', 'Controller setting write'))
                        self.clear_local_references()
                elif kind == 'time_server_test_done':
                    result = event['report']
                    if result['host'] != self.time_server.get().strip():
                        continue
                    self.tested_time_server = None if result.get('error') else result
                    self.time_status.set(result.get('error') or f"PC reply: {result['ip']} · {result['utc']} · {result['round_trip_ms']} ms. Telescope not tested.")
                elif kind == 'time_settings_done':
                    self.set_busy(False)
                    report = event['report']
                    self.log_directory = report.get('log_directory')
                    self.logs_button.configure(state='normal' if self.log_directory else 'disabled')
                    text = report.get('error') or ('WiFly clock text available' if report.get('clock_text_available') else 'WiFly operation completed; clock remains unset or unverified')
                    if report.get('applied'):
                        text += ' | setting read back; ' + ('saved to flash' if report.get('saved') else 'RAM only')
                    self.status.set(text)
                    self.diagnostic_status.set(text)
                    self.append(text)
                    self.time_status.set(text)
                    self.time_zone.set(report.get('clock', {}).get('Zone setting (raw)', 'Not reported'))
                    self.time_readback.set('Last board read (snapshot):\n' + '\n'.join(f'{key}: {value}' for key, value in {**report.get('clock', {}), **report.get('clock_comparison', {})}.items()) if report.get('clock') else 'Current read failed; no fresh board values available. ' + text)
                    if report.get('clock'):
                        evidence = self.check_uptime_evidence(report.get('adapter_identity', ''), report['clock'])
                        self.time_readback.set(self.time_readback.get() + '\nReset check: ' + evidence)
                    self.refresh_time_readback()
                    for field, value in report.get('clock', {}).items():
                        self.events.put({'event': 'diagnostic_row', 'device': 'WiFly clock', 'endpoint': field, 'status': 'READBACK', 'reply': str(value)})
                elif kind == 'scan_done':
                    self.scan_started = None
                    if self.scan_tick_id is not None:
                        self.root.after_cancel(self.scan_tick_id)
                        self.scan_tick_id = None
                    self.scan_button.configure(text='Discover SkyQLink / Celestron Modules')
                    self.set_busy(False)
                    report = event['report']
                    matches = report.get('matches', [])
                    if report.get('error'):
                        text = report['error']
                    elif matches:
                        self.discovered = matches
                        self.module_box.configure(values=[f'{m["ip"]}:{m.get("port", 2000)} — {m.get("module_type", "Celestron AUX")}' for m in matches])
                        self.module_box.current(0)
                        match = matches[0]
                        self.connection_mode.set('direct' if match['ip'] == '1.2.3.4' else 'infrastructure')
                        self.update_mode_help()
                        self.host.set(match['ip'])
                        if match['ip'] != '1.2.3.4':
                            self.last_infrastructure_host = match['ip']
                        self.port.set(str(match.get('port', 2000)))
                        text = f'{len(matches)} verified module(s). Selected {match["ip"]}:{match.get("port", 2000)} — {match.get("module_type", "Celestron AUX")}.'
                        if match.get('module_version'):
                            text += f' Firmware {match["module_version"]}.'
                        text += ' Adapter identified; connection closed after discovery.'
                        for found in matches:
                            self.append(f'DISCOVERY DETAILS {found["ip"]}:{found.get("port", 2000)} — '
                                        + found.get('verification_note', 'Module verified'))
                    else:
                        self.discovered = []
                        self.module_box.configure(values=[])
                        self.selected_module.set('')
                        text = report.get('no_match_reason') or 'No Celestron replies verified. Close other telescope apps and check the selected network; enter the IP manually if discovery is blocked.'
                    self.status.set(text)
                    found = bool(matches) and not report.get('error')
                    self.scan_indicator.configure(
                        text=('● Module found' if found else '● Scan timed out' if report.get('timed_out') else
                              '● Scan failed' if report.get('error') else '● No module verified')
                             + f' — {report.get("elapsed_seconds", 0):g}s',
                        foreground='#18743b' if found else '#b22b2b')
                    self.append(text)
                    if report.get('log_directory'):
                        self.log_directory = report['log_directory']
                        self.logs_button.configure(state='normal')
                    self.update_controls()
                elif kind == 'done':
                    report = event['report']
                    self.show_provisioned_network(report)
                    self.set_busy(False)
                    self.password.set('')
                    self.show_password.set(False)
                    self.refresh_password()
                    self.log_directory = report.get('log_directory')
                    self.logs_button.configure(state='normal' if self.log_directory else 'disabled')
                    if report.get('error'):
                        text = 'Failed: ' + report['error']
                        if report.get('recovery_note'):
                            text += ' ' + report['recovery_note']
                    elif report.get('saved'):
                        text = ('Settings saved. Power OFF the telescope; set its physical Wi-Fi slider beside the power socket '
                                'to RIGHT (infrastructure), then power ON. Leave it RIGHT if already there. '
                                'Router connection is not yet verified.')
                    else:
                        text = 'Connected. Adapter settings read successfully; no settings changed.'
                    if report.get('exit_error') or report.get('exit_confirmed') is False:
                        text += ' Command-mode exit was not confirmed.'
                    self.status.set(text)
                    self.append(text)
                    if self.log_directory:
                        self.append('Saved logs: ' + self.log_directory)
                elif kind == 'tx':
                    self.append('SEND  ' + event['command'])
                elif kind == 'rx_sanitized' and event['text']:
                    self.append('RECV  ' + event['text'].strip())
                elif kind in ('stage', 'failure'):
                    self.append(event['message'])
                elif kind == 'command_mode_escape':
                    self.append('SEND  $$$ (enter command mode)')
        except queue.Empty:
            pass
        for axis, last in self.last_positions.items():
            age = time.monotonic() - last
            self.values[axis]['age'].set(f'{age:.1f}s ago' + (' · STALE' if age > 3 else ''))
        if self.held and self.motor_ready and self.motor is not None:
            self.motor.renew_hold()
        if self.closing and self.motor is None and self.bridge is None:
            self.progress.stop()
            self.root.destroy()
            return
        self.poll_id = self.after(100, self.poll)

    def handle_motor_event(self, event):
        """Apply motor-service events to position, movement and connection state."""
        kind = event['event']
        if kind == 'motor_values':
            axis = event['axis']
            values = self.values[axis]
            values['encoder'].set(str(event['encoder']))
            if axis in self.position_references:
                origin, degrees = self.position_references[axis]
                referenced = degrees + relative_angle(event['encoder'], origin)
                if axis == 0x10:
                    referenced %= 360
                values['referenced'].set(f'{referenced:.5f}°')
            values['angle'].set(f'{event["angle"]:.5f}°')
            values['relative'].set(f'{event["relative"]:+.5f}°')
            values['firmware'].set(event['firmware'])
            if self.current_motion_axis == axis:
                before = values['before'].get()
                if before.isdigit():
                    values['delta_counts'].set(f'{relative_counts(event["encoder"], int(before)):+d}')
                    values['delta_degrees'].set(f'{relative_angle(event["encoder"], int(before)):+.5f}°')
            self.last_positions[axis] = event['monotonic']
            self.refresh_reference_preview(axis)
            if axis in self.reference_poll_pending:
                self.reference_poll_pending.discard(axis)
                self.motion_status.set(f'{AXES[axis]} position polled at {dt.datetime.now().strftime("%H:%M:%S")}.')
        elif kind == 'motor_feedback_retry':
            self.clear_local_references()
            self.motor_ready = False
            self.motor_status.set('Waiting for encoder feedback')
            self.motion_status.set(event['message'])
        elif kind == 'motor_feedback_restored':
            self.motor_ready = True
            self.motor_status.set('Motor encoder connection verified')
            self.motion_status.set(event['message'])
        elif kind == 'motor_idle_release':
            self.motor_ready = False
            self.motion_status.set(f'Idle release after {event["seconds"]} seconds. Reconnect to continue moving.')
            self.status.set(self.motion_status.get())
        elif kind == 'motor_connected':
            self.connect_request_active = False
            self.motor_ready = True
            self.motor_status.set('Motor encoder connection verified')
            self.status.set(f'Motor connection verified at {event["host"]}:{event["port"]}; both encoders are live.')
            self.motion_status.set('Live encoder feedback verified on both axes. Ready for movement.')
            self.append(f'MOTORS connected to {event["host"]}:{event["port"]}')
        elif kind == 'motor_disconnected':
            self.clear_local_references()
            self.controller_reads.clear()
            for axis in AXES:
                self.controller_readout[axis].set('Not current after disconnect. Press Read current values.')
            for values in self.values.values():
                values['referenced'].set('—')
            for axis in AXES:
                self.reference_current[axis].set('—')
                self.reference_delta[axis].set('—')
            retry_with_restart = (self.connect_request_active and self.auto_recover.get()
                                  and not self.connect_recovery_attempted and not self.closing
                                  and self.last_motor_error is not None
                                  and 'Motor connection NOT verified' in self.last_motor_error)
            self.connect_request_active = False
            self.motor = None
            self.motor_ready = False
            self.jogging = False
            self.held = False
            self.current_motion_axis = None
            self.measuring_motion = False
            self.motor_status.set('Connection failed — see reason below' if self.last_motor_error else 'Disconnected')
            if self.last_motor_error:
                self.motion_status.set(self.last_motor_error)
            self.log_directory = event['log_directory']
            self.logs_button.configure(state='normal' if self.log_directory else 'disabled')
            self.append('Motor connection closed. Logs: ' + self.log_directory)
            if retry_with_restart:
                self.append('Initial motor replies missing: attempting one verified RN-171 restart, then reconnecting.')
                self.start_recovery(reconnect=True)
        elif kind == 'motor_jog_started':
            self.measuring_motion = True
            self.current_motion_axis = event['axis']
            values = self.values[event['axis']]
            values['before'].set(str(event.get('start_encoder', '—')))
            for field in ('after', 'delta_counts', 'delta_degrees', 'stationary'):
                values[field].set('Awaiting reply')
            duration = 'hold until release' if event.get('hold') else f'{event["requested_seconds"]:g}s'
            self.motor_status.set(f'Command sent: {AXES[event["axis"]]} — {duration}')
            self.motion_status.set('Movement command sent — awaiting measured encoder change')
            self.append(f'DRIVE {AXES[event["axis"]]} {event["direction"]:+d}, rate {event["rate"]}, {duration}')
        elif kind == 'motor_jog_finished':
            self.current_motion_axis = None
            self.held = False
            self.motor_status.set('Jog ended; Stop sent — refreshing encoders')
        elif kind == 'motor_settling':
            self.motor_status.set('Waiting for motor to settle after Stop')
            self.motion_status.set(event['message'])
            self.append(event['message'])
        elif kind == 'motor_stopped':
            if not self.measuring_motion:
                self.jogging = False
            self.held = False
            if not self.last_motor_error:
                self.motor_status.set('Stop sent to both axes')
            self.append(event['message'])
        elif kind == 'motor_error':
            self.last_motor_error = event['message']
            self.measuring_motion = False
            self.jogging = False
            self.current_motion_axis = None
            self.motor_ready = False
            self.motor_status.set('Motor connection error — see details below')
            self.status.set(event['message'])
            self.motion_status.set(event['message'])
            self.append('MOTOR ERROR: ' + event['message'])
        elif kind == 'motor_telemetry_missing':
            self.last_positions.pop(event['axis'], None)
            self.values[event['axis']]['age'].set('No reply')
        elif kind == 'motor_motion_result':
            self.measuring_motion = False
            self.jogging = False
            values = self.values[event['axis']]
            values['before'].set(str(event.get('start_encoder', '—')))
            values['after'].set(str(event['end_encoder']) if event.get('end_encoder') is not None else 'No reply')
            counts, degrees = event.get('measured_counts'), event.get('measured_degrees')
            values['delta_counts'].set(f'{counts:+d}' if counts is not None else 'Unverified')
            values['delta_degrees'].set(f'{degrees:+.5f}°' if degrees is not None else 'Unverified')
            stationary = event.get('stationary_verified')
            values['stationary'].set('Verified' if stationary is True else 'Still moving' if stationary is False else 'Unverified')
            if stationary is True:
                self.motor_status.set('Motor encoder connection verified — ready')
            self.motion_status.set(AXES[event['axis']] + ': ' + event['message'])
            self.append('MEASURED ' + AXES[event['axis']] + ': ' + event['message'])
        elif kind == 'motor_connecting':
            self.append(event['message'])
            if event.get('log_directory'):
                self.log_directory = event['log_directory']
                self.logs_button.configure(state='normal')
        elif kind == 'motor_tx' and event['command'] in (0x24, 0x25):
            self.append('SEND AUX  ' + event['hex'])
        self.update_controls()

    def open_logs(self):
        """Open the latest operation folder in the host’s file browser."""
        if self.log_directory:
            try:
                open_directory(self.log_directory)
            except OSError:
                self.status.set('Saved logs: ' + self.log_directory)

    def close(self):
        """Request service shutdown and defer window destruction until workers release ownership."""
        if self.bridge is not None:
            self.closing = True
            self.bridge_enabled.set(False)
            self.bridge.stop()
            self.bridge_status.set('Closing bridge — sending Stop…')
            return
        if self.busy:
            self.status.set('Transfer in progress. Wait for completion before closing.')
            return
        if self.motor is not None:
            self.closing = True
            self.disconnect_motors()
            self.status.set('Sending Stop and closing the motor connection…')
            return
        self.after_cancel(self.poll_id)
        if self.scan_tick_id is not None:
            self.root.after_cancel(self.scan_tick_id)
        self.progress.stop()
        self.root.destroy()


def main():
    """Parse command-line options and run this module’s entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true', help='Build and check the window without hardware, then close')
    parser.add_argument('--diagnostic-report', type=Path, help='Display a saved diagnostic report without connecting')
    parser.add_argument('--host', default='1.2.3.4', help='Initial telescope IP (default: 1.2.3.4)')
    parser.add_argument('--port', type=int, default=2000, help='Initial TCP port (default: 2000)')
    parser.add_argument('--connect', action='store_true', help='Connect and read encoders on startup; no movement')
    parser.add_argument('--ui-scale', type=scale_argument, default=1.0,
                        help='Startup UI size, 0.5 to 2.0 (default: 1.0)')
    parser.add_argument('--zoom-controls', action='store_true',
                        help='Enable View menu zoom and Fit width controls')
    args = parser.parse_args()
    root = tk.Tk()
    app = SetupApp(root, ui_scale=args.ui_scale, zoom_controls=args.zoom_controls)
    app.host.set(args.host)
    app.port.set(str(args.port))
    app.connection_mode.set('direct' if args.host == '1.2.3.4' else 'infrastructure')
    app.update_mode_help()
    if args.diagnostic_report:
        from setup_backend import clean
        report = clean(json.loads(args.diagnostic_report.read_text()), ())
        report['saved_report'] = True
        for row in report.get('rows', []):
            app.events.put({'event': 'diagnostic_row', **row})
        app.events.put({'event': 'diagnostic_done', 'report': report})
        app.host.set(report['host'])
        app.port.set(str(report['port']))
        app.connection_mode.set('infrastructure' if report['host'] != '1.2.3.4' else 'direct')
        app.update_mode_help()
        app.tabs.select(app.diagnostic_tab)
        app.append('SAVED DIAGNOSTIC REPORT — results are from the recorded session, not a new live connection.')
    if args.smoke_test:
        root.update()
        assert app.host.get() == args.host and app.port.get() == str(args.port)
        assert app.password_entry.cget('show') == '•'
        assert str(app.security_box['state']) == 'readonly'
        app.close()
        print('Tkinter window smoke test passed; no network or hardware commands sent.')
    else:
        root.after(100, app.refresh_network_interfaces)
        if args.connect:
            root.after(300, app.connect_motors)
        root.mainloop()


if __name__ == '__main__':
    main()
