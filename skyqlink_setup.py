#!/usr/bin/env python3
"""Tkinter motor control and Wi-Fi setup for the Celestron Gen-1 SkyQLink RN-171."""
import argparse
import datetime as dt
from pathlib import Path
import queue
import threading
import time
import json
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from setup_backend import operate, validate_endpoint, validate_port
from wifly_configure import make_plan, SECURITY
from motor_control import MotorController, AXES, relative_counts, relative_angle
from discover_modules import scan_modules
from diagnostics import diagnose
from recover_link import recover
from bridge_mode import Bridge
from network_info import network_interfaces, open_directory

APP_TITLE = 'Celestron COSMOS 90GT — Version 1 Wi-Fi Control Management Application'
WIFI_SWITCH_HELP = (
    'Physical Wi-Fi mode switch — on the telescope mount, beside its power socket\n'
    'LEFT — Direct / ad hoc: the telescope provides its own SkyQLink-xx Wi-Fi network '
    'Connect your computer to that network and use 1.2.3.4:2000.\n'
    'RIGHT — Infrastructure: with router settings saved, the telescope joins that Wi-Fi network. '
    'Connect your computer to the same router LAN and use the telescope’s assigned IP, port 2000.\n'
    'After saving router settings: stop and disconnect motor control, power OFF the telescope, '
    'move this physical slider to RIGHT, then power ON. If it is already RIGHT, leave it there. '
    'Discover the telescope’s new IP after it joins the router.\n'
    'The Direct / Infrastructure selector in this app only selects connection settings; '
    'it does not move the physical switch or change your computer’s Wi-Fi. '
    'Wi-Fi provisioning does not command motor movement.'
)


class BridgeRocker(tk.Canvas):
    """Two-position OFF/ON control with mouse and keyboard operation."""
    def __init__(self, parent, variable, command):
        super().__init__(parent, width=184, height=46, highlightthickness=1,
                         highlightbackground='#777777', takefocus=True, background='#30343b')
        self.variable, self.command = variable, command
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
        result = super().configure(*args, **kwargs)
        if 'state' in kwargs and hasattr(self, 'variable'):
            self.redraw()
        return result

    def redraw(self):
        self.delete('all')
        enabled = str(self.cget('state')) == 'normal'
        on = self.variable.get()
        for left, label, selected in ((2, 'OFF', not on), (93, 'ON', on)):
            fill = ('#197442' if on else '#8c3434') if selected and enabled else '#454951'
            self.create_rectangle(left, 2, left + 89, 44, fill=fill,
                                  outline='#dddddd' if selected and enabled else '#666666', width=2)
            self.create_text(left + 44, 22, text=label, fill='white' if enabled else '#aaaaaa',
                             font=('TkDefaultFont', 14, 'bold'))

    def choose(self, on):
        if str(self.cget('state')) == 'normal' and bool(on) != self.variable.get():
            self.variable.set(bool(on))
            self.command()
        return 'break'

    def click(self, event):
        self.focus_set()
        return self.choose(event.x >= 92)

    def destroy(self):
        self.variable.trace_remove('write', self.trace_id)
        super().destroy()


class SetupApp(ttk.Frame):
    def __init__(self, root, operation=operate, motor_factory=MotorController, scanner=scan_modules,
                 diagnostic=diagnose, recovery=recover, bridge_factory=Bridge):
        shell = ttk.Frame(root)
        shell.pack(fill='both', expand=True)
        canvas = tk.Canvas(shell, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(shell, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        super().__init__(canvas, padding=16)
        self.scroll_canvas = canvas
        content = canvas.create_window((0, 0), window=self, anchor='nw')
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(content, width=event.width))
        self.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
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
        self.bridge_status = tk.StringVar(value='Bridge OFF — experimental; infrastructure mode only')
        self.bridge_bind = tk.StringVar()
        self.bridge_dual = tk.BooleanVar(value=False)
        self.bridge_last_error = None
        self.interface_rows = []
        self.interface_refreshing = False
        self.network_provider = network_interfaces
        self.bridge_listener = None
        self.bridge_upstream_local = None
        self.bridge_endpoint = tk.StringVar(value='Computer listener: OFF — TCP 2000 / 3000 start with Bridge ON')
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
        self.held = False
        self.drive_mode = tk.StringVar(value='hold')
        self.discovered = []
        self.selected_module = tk.StringVar()
        self.closing = False
        self.last_positions = {}
        self.speed = tk.StringVar(value='6')
        self.duration = tk.StringVar(value='0.5')
        self.motor_status = tk.StringVar(value='Disconnected')
        self.motion_status = tk.StringVar(value='No movement measured yet')
        self.values = {axis: {field: tk.StringVar(value='—') for field in
                             ('encoder', 'angle', 'relative', 'firmware', 'age', 'before', 'after',
                              'delta_counts', 'delta_degrees', 'stationary')} for axis in AXES}
        self.log_directory = None
        self.host = tk.StringVar(value='1.2.3.4')
        self.port = tk.StringVar(value='2000')
        self.ssid = tk.StringVar()
        self.password = tk.StringVar()
        self.security = tk.StringVar(value='WPA2-Personal (AES)')
        self.provision_notice = tk.StringVar(value='You can configure this adapter through either direct/ad hoc Wi-Fi or its current infrastructure IP. '
            'Uploading replaces the stored SSID, password and security settings so it can join a different network. '
            'A factory reset is not required. Restart afterward and discover its new IP.')
        self.status = tk.StringVar(value='Ready — connect to the telescope, then read or upload settings.')
        self.show_password = tk.BooleanVar(value=False)
        root.title(APP_TITLE)
        window_height = min(950, root.winfo_screenheight() - 90)
        root.geometry(f'980x{window_height}')
        root.minsize(900, min(650, window_height))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(6, weight=1)
        ttk.Label(self, text='Celestron COSMOS 90GT', font=('TkDefaultFont', 20, 'bold')).grid(sticky='w')
        ttk.Label(self, text='Version 1 Wi-Fi Control Management Application · Gen 1 SkyQLink', foreground='#666666').grid(row=1, sticky='w', pady=(2, 8))

        connection = ttk.LabelFrame(self, text='Telescope connection', padding=8)
        connection.grid(row=2, sticky='ew')
        connection.columnconfigure(1, weight=1)
        ttk.Label(connection, text='Telescope IP address').grid(row=0, column=0, sticky='w', padx=(0, 12))
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
        self.direct_button.pack(side='left')
        self.home_button = ttk.Radiobutton(presets, text='Infrastructure / house Wi-Fi', variable=self.connection_mode,
                                           value='infrastructure', command=lambda: self.preset(True))
        self.home_button.pack(side='left', padx=8)
        self.scan_button = ttk.Button(presets, text='Discover Modules on LAN', command=self.scan_lan)
        self.scan_button.pack(side='left', padx=8)
        self.scan_started = None
        self.scan_tick_id = None
        self.scan_indicator = tk.Label(connection, text='● Discovery idle', foreground='#666666', anchor='w')
        self.scan_indicator.grid(row=4, column=0, columnspan=4, sticky='w', pady=(4, 0))
        self.module_box = ttk.Combobox(connection, textvariable=self.selected_module, state='disabled')
        self.module_box.grid(row=3, column=0, columnspan=4, sticky='ew', pady=(8, 0))
        self.module_box.bind('<<ComboboxSelected>>', lambda event: self.select_module())

        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=3, sticky='nsew', pady=(12, 0))
        self.motor_tab = ttk.Frame(self.tabs, padding=8)
        self.provision_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.motor_tab, text='Motor control')
        self.diagnostic_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.diagnostic_tab, text='Diagnostics')
        self.bridge_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.bridge_tab, text='Bridge')
        self.tabs.add(self.provision_tab, text='Wi-Fi provisioning')
        self.build_bridge_tab()
        self.build_diagnostics_tab()
        self.provision_tab.columnconfigure(0, weight=1)
        self.build_motor_tab()

        wifi = ttk.LabelFrame(self.provision_tab, text='Router Wi-Fi settings', padding=12)
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
        self.show = ttk.Checkbutton(wifi, text='Show', variable=self.show_password,
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

        buttons = ttk.Frame(self.provision_tab)
        buttons.grid(row=1, sticky='ew', pady=(16, 0))
        self.read_button = ttk.Button(buttons, text='Connect & Read Settings', command=lambda: self.start(False))
        self.read_button.pack(side='left')
        self.upload_button = ttk.Button(buttons, text='Upload & Save Wi-Fi Settings', command=lambda: self.start(True))
        self.upload_button.pack(side='left', padx=10)
        self.progress = ttk.Progressbar(buttons, mode='indeterminate', length=100)
        self.progress.pack(side='right')
        ttk.Label(self, textvariable=self.status, wraplength=760).grid(row=5, sticky='w', pady=(0, 10))

        transfer = ttk.LabelFrame(self, text='Transfer log — credentials redacted', padding=8)
        transfer.grid(row=6, sticky='nsew')
        transfer.rowconfigure(0, weight=1)
        transfer.columnconfigure(0, weight=1)
        self.console = ScrolledText(transfer, height=6, wrap='word', state='disabled',
                                   font=('TkFixedFont', 11), background='#17212b', foreground='#e7edf3',
                                   insertbackground='white', relief='flat')
        self.console.grid(sticky='nsew')
        footer = ttk.Frame(self)
        footer.grid(row=7, sticky='ew', pady=(10, 0))
        self.logs_button = ttk.Button(footer, text='Open Saved Logs', state='disabled', command=self.open_logs)
        self.logs_button.pack(side='left')
        self.clear_button = ttk.Button(footer, text='Clear View', command=self.clear)
        self.clear_button.pack(side='left', padx=10)
        self.switch_help_label = ttk.Label(self.provision_tab, text=WIFI_SWITCH_HELP,
                                          wraplength=820)
        self.switch_help_label.grid(row=2, sticky='w', pady=(12, 0))
        self.append('Ready. Close CFM / CPWI before connecting here; the adapter shares one command stream.')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Escape>', lambda event: self.stop_motors())
        root.bind('<ButtonRelease-1>', lambda event: self.release_direction(), add='+')
        root.bind('<FocusOut>', lambda event: root.after(50, self.stop_if_unfocused))
        root.bind('<MouseWheel>', self.scroll_window, add='+')
        root.bind('<Button-4>', self.scroll_window, add='+')
        root.bind('<Button-5>', self.scroll_window, add='+')
        self.poll_id = self.after(100, self.poll)

    def scroll_window(self, event):
        # Reply text, transfer text and the endpoint table retain their own scroll.
        if event.widget in (self.console, self.diagnostic_details, self.diagnostic_rows):
            return
        delta = getattr(event, 'delta', 0)
        if getattr(event, 'num', None) in (4, 5):
            delta = 120 if event.num == 4 else -120
        if delta:
            units = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
            self.scroll_canvas.yview_scroll(units, 'units')

    def build_motor_tab(self):
        tab = self.motor_tab
        tab.columnconfigure(1, weight=1)
        controls = ttk.Frame(tab)
        controls.grid(row=0, column=0, columnspan=2, sticky='ew')
        self.motor_connect_button = ttk.Button(controls, text='Connect Motors', command=self.connect_motors)
        self.motor_connect_button.pack(side='left')
        self.motor_disconnect_button = ttk.Button(controls, text='Disconnect', command=self.disconnect_motors, state='disabled')
        self.motor_disconnect_button.pack(side='left', padx=8)
        ttk.Label(controls, textvariable=self.motor_status).pack(side='left', padx=8)

        recovery_option = ttk.Frame(tab)
        recovery_option.grid(row=4, column=0, columnspan=2, sticky='w', pady=6)
        self.auto_recover_button = ttk.Checkbutton(recovery_option,
            text='Recover a stalled adapter on Connect (one restart; saved Wi-Fi retained)', variable=self.auto_recover)
        self.auto_recover_button.pack(side='left')

        pad = ttk.LabelFrame(tab, text='Four-direction motor control', padding=8)
        pad.grid(row=1, column=0, sticky='nsew', padx=(0, 12), pady=(12, 0))
        self.jog_buttons = []
        for text, row, col, axis, direction in (
                ('Up / ALT +', 0, 1, 0x11, 1), ('Left / AZ −', 1, 0, 0x10, -1),
                ('Right / AZ +', 1, 2, 0x10, 1), ('Down / ALT −', 2, 1, 0x11, -1)):
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
        ttk.Label(pad, text='Seconds / click').grid(row=4, column=0, sticky='w')
        self.duration_box = ttk.Combobox(pad, textvariable=self.duration, values=('0.25', '0.5', '1.0', '2.0'), state='readonly', width=5)
        self.duration_box.grid(row=4, column=1, sticky='w')
        ttk.Radiobutton(pad, text='Hold to move', variable=self.drive_mode, value='hold', command=self.stop_motors).grid(row=5, column=0, columnspan=2, sticky='w', pady=(8, 0))
        ttk.Radiobutton(pad, text='Timed jog', variable=self.drive_mode, value='jog', command=self.stop_motors).grid(row=5, column=2, sticky='w', pady=(8, 0))

        readout = ttk.LabelFrame(tab, text='Motor values', padding=8)
        readout.grid(row=1, column=1, sticky='nsew', pady=(12, 0))
        for column, label in enumerate(('Value', 'Azimuth', 'Altitude')):
            ttk.Label(readout, text=label, font=('TkDefaultFont', 12, 'bold')).grid(row=0, column=column, sticky='w', padx=(0, 14), pady=(0, 8))
        for row, (field, label) in enumerate((('encoder', 'Encoder counts'), ('angle', 'Raw angle'),
                                             ('relative', 'Since connect'), ('firmware', 'Firmware'),
                                             ('age', 'Last update'), ('before', 'Before jog'),
                                             ('after', 'After jog'), ('delta_counts', 'Jog Δ counts'),
                                             ('delta_degrees', 'Jog Δ angle'), ('stationary', 'Stop check')), 1):
            ttk.Label(readout, text=label, font=('TkDefaultFont', 11)).grid(row=row, column=0, sticky='w', pady=2, padx=(0, 12))
            for column, axis in enumerate(AXES, 1):
                ttk.Label(readout, textvariable=self.values[axis][field], font=('TkFixedFont', 11)).grid(row=row, column=column, sticky='w', padx=(0, 12))
        ttk.Label(tab, text='Hold an arrow to drive; release to stop. Escape stops both axes. Encoder angles are not aligned sky coordinates.',
                  wraplength=780).grid(row=2, column=0, columnspan=2, sticky='w', pady=(10, 0))
        ttk.Label(tab, textvariable=self.motion_status, wraplength=780,
                  font=('TkDefaultFont', 12, 'bold')).grid(row=3, column=0, columnspan=2, sticky='w', pady=8)

    def build_diagnostics_tab(self):
        tab = self.diagnostic_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        self.diagnostic_status = tk.StringVar(value='Not tested — run diagnostics to verify adapter and motor replies.')
        diagnostic_controls = ttk.Frame(tab)
        diagnostic_controls.grid(row=0, columnspan=2, sticky='ew')
        self.diagnostic_button = ttk.Button(diagnostic_controls, text='Run read-only diagnostics', command=self.start_diagnostics)
        self.diagnostic_button.pack(side='left')
        self.recovery_button = ttk.Button(diagnostic_controls, text='Restart Wi-Fi adapter & recheck motors', command=self.start_recovery)
        self.recovery_button.pack(side='left', padx=12)
        ttk.Label(tab, textvariable=self.diagnostic_status, wraplength=800).grid(row=1, sticky='w', pady=6)
        self.diagnostic_rows = ttk.Treeview(tab, columns=('device', 'endpoint', 'status', 'reply'), show='headings', height=7)
        for key, label, width in (('device', 'Device', 110), ('endpoint', 'Query / endpoint', 210),
                                  ('status', 'Result', 105), ('reply', 'Reply data', 355)):
            self.diagnostic_rows.heading(key, text=label)
            self.diagnostic_rows.column(key, width=width)
        self.diagnostic_rows.grid(row=2, sticky='nsew')
        scrollbar = ttk.Scrollbar(tab, orient='vertical', command=self.diagnostic_rows.yview)
        scrollbar.grid(row=2, column=1, sticky='ns')
        self.diagnostic_rows.configure(yscrollcommand=scrollbar.set)
        self.diagnostic_details = ScrolledText(tab, height=5, wrap='word', state='disabled', font=('TkFixedFont', 10))
        self.diagnostic_details.grid(row=3, columnspan=2, sticky='ew', pady=6)
        self.diagnostic_replies = {}
        self.diagnostic_rows.bind('<<TreeviewSelect>>', self.show_diagnostic_reply)
        ttk.Label(tab, text='Select a row for the full response. Read-only diagnostics sends no motion or configuration writes.\n'
                  'Restart & recheck restarts the RN-171, retains saved Wi-Fi settings, and checks motor replies. Disconnect motors first.',
                  wraplength=800).grid(row=4, columnspan=2, sticky='w')

    def build_bridge_tab(self):
        tab = self.bridge_tab
        tab.columnconfigure(0, weight=1)
        self.bridge_switch = BridgeRocker(tab, variable=self.bridge_enabled, command=self.toggle_bridge)
        self.bridge_switch.grid(row=0, sticky='w')
        ttk.Label(tab, textvariable=self.bridge_status, wraplength=820).grid(row=1, sticky='w', pady=6)
        settings = ttk.Frame(tab)
        settings.grid(row=2, sticky='ew')
        self.bridge_ip_help = tk.StringVar()
        ttk.Label(settings, textvariable=self.bridge_ip_help).pack(side='left')
        self.bridge_bind_entry = ttk.Entry(settings, textvariable=self.bridge_bind, width=20)
        self.bridge_bind_entry.pack(side='left', padx=8)
        self.bridge_dual_box = ttk.Checkbutton(tab, text='Two interfaces: direct SkyQLink upstream + separate router LAN for phone',
                                              variable=self.bridge_dual, command=self.update_controls)
        self.bridge_dual_box.grid(row=3, sticky='w', pady=4)
        self.bridge_interface_help = tk.StringVar()
        inventory = ttk.LabelFrame(tab, text='Computer network interfaces', padding=6)
        ttk.Label(inventory, textvariable=self.bridge_interface_help, wraplength=780).pack(anchor='w')
        inventory.grid(row=4, sticky='ew', pady=5)
        self.interface_table = ttk.Treeview(inventory, columns=('interface', 'name', 'ip', 'state', 'role'),
                                            show='headings', height=4, selectmode='browse')
        for field, label, width in (('interface', 'Interface', 70), ('name', 'Adapter / connection', 180),
                                    ('ip', 'Current IPv4', 140), ('state', 'State', 90), ('role', 'Bridge listener', 240)):
            self.interface_table.heading(field, text=label)
            self.interface_table.column(field, width=width)
        self.interface_table.pack(fill='x')
        self.interface_table.bind('<<TreeviewSelect>>', self.select_bridge_interface)
        self.interface_refresh_button = ttk.Button(inventory, text='Refresh computer IPs', command=self.refresh_network_interfaces)
        self.interface_refresh_button.pack(anchor='w', pady=4)
        ttk.Label(inventory, textvariable=self.bridge_endpoint, wraplength=800).pack(anchor='w')
        ttk.Label(tab, text='Default: use the same home/router LAN for the computer, telescope and phone. '
                  'In a compatible control app choose Celestron WiFi and Access Point mode. SkySafari is a tested example. The bridge advertises on UDP 55555 '
                  'and listens on this computer’s TCP 2000 (management: TCP 3000). '
                  'The telescope IP above remains the upstream destination.\n'
                  'ON locks the other tabs. OFF sends Stop and closes the bridge. '
                  'Clients can command real movement while connected. '
                  'App compatibility is experimental; router client isolation or blocked broadcasts can prevent discovery.',
                  wraplength=820).grid(row=5, sticky='w', pady=8)
        self.bridge_firewall_label = ttk.Label(tab, foreground='#b36b00', wraplength=820,
                  text='FIREWALL / LOCAL NETWORK: allow this Python application incoming TCP 2000 and 3000 '
                  'from your local network, and outgoing UDP broadcasts to port 55555. '
                  'Allow incoming connections in the computer’s firewall when prompted; enable Local Network access for SkySafari/SkyPortal on iOS. '
                  'Do not forward these ports from the Internet. A listening socket does not verify firewall access.\n'
                  'Two-interface option: manually connect one Wi-Fi adapter to SkyQLink and another Wi-Fi/Ethernet adapter '
                  'to the router LAN. Enter the computer’s router-LAN IP above. The app does not configure or share networks.')
        self.bridge_firewall_label.grid(row=6, sticky='w', pady=6)
        readout = ttk.LabelFrame(tab, text='Observed encoder feedback — no injected polling while client connected', padding=6)
        readout.grid(row=7, sticky='ew')
        for row, axis in enumerate(AXES):
            ttk.Label(readout, text=AXES[axis]).grid(row=row, column=0, padx=8)
            for column, field in enumerate(('encoder', 'angle', 'firmware', 'age'), start=1):
                ttk.Label(readout, textvariable=self.values[axis][field], width=17).grid(row=row, column=column)
        self.bridge_console = ScrolledText(tab, height=8, wrap='word', state='disabled', font=('TkFixedFont', 10))
        self.bridge_console.grid(row=8, sticky='ew', pady=8)

    def refresh_network_interfaces(self):
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
        self.interface_table.delete(*self.interface_table.get_children())
        for row in self.interface_rows:
            role = (f'TCP {self.bridge_listener[1]} / {self.bridge_listener[2]}'
                    if self.bridge_listener and row['ip'] == self.bridge_listener[0] else 'Not listening')
            if self.bridge_upstream_local and row['ip'] == self.bridge_upstream_local[0]:
                role += ' · to telescope'
            self.interface_table.insert('', 'end', values=(row['interface'], row['name'], row['ip'], row['state'], role))

    def select_bridge_interface(self, event=None):
        if self.bridge is not None:
            return
        selected = self.interface_table.selection()
        if selected:
            ip = self.interface_table.item(selected[0], 'values')[2]
            if ip == '—':
                self.bridge_status.set('This interface has no IPv4 address. Connect it to the router LAN first.')
            elif ip.startswith('127.'):
                self.bridge_status.set('Loopback is local to this computer. Choose a router-LAN interface for the phone.')
            else:
                self.bridge_bind.set(ip)

    def toggle_bridge(self):
        if not self.bridge_enabled.get():
            if self.bridge:
                self.bridge.stop()
                self.bridge_status.set('Turning bridge OFF — sending Stop and draining replies…')
            return
        if self.bridge is not None:
            self.bridge_enabled.set(False)
            return
        if self.busy or self.motor is not None or (self.connection_mode.get() != 'infrastructure' and not self.bridge_dual.get()):
            self.bridge_enabled.set(False)
            self.bridge_status.set('Select Infrastructure / house Wi-Fi and disconnect motor control first.')
            return
        if self.bridge_dual.get() and not self.bridge_bind.get().strip():
            self.bridge_enabled.set(False)
            self.bridge_status.set('Two interfaces requires this computer’s IP on the network shared with the control app. Select a row or enter that IP, for example Ethernet on the house LAN.')
            return
        try:
            self.bridge_last_error = None
            self.bridge = self.bridge_factory(self.host.get(), self.port.get(), self.events.put,
                                               bind_host=self.bridge_bind.get().strip(),
                                               allow_direct_upstream=self.bridge_dual.get())
            self.last_positions.clear()
            for values in self.values.values():
                for value in values.values():
                    value.set('—')
            self.bridge_status.set('Starting bridge — checking telescope communication…')
            self.bridge.start()
        except Exception as error:
            self.bridge = None
            self.bridge_enabled.set(False)
            self.bridge_status.set(str(error))
        self.update_controls()

    def handle_bridge_event(self, event):
        kind = event['event']
        if kind == 'bridge_values':
            self.handle_motor_event({**event, 'event': 'motor_values'})
            return
        if event.get('log_directory'):
            self.log_directory = event['log_directory']
            self.logs_button.configure(state='normal')
        message = event.get('message')
        if kind == 'bridge_error' and self.bridge_last_error is None:
            self.bridge_last_error = message
        if kind == 'bridge_ready' and event.get('bind_host'):
            self.bridge_listener = (event['bind_host'], event['listen_port'], event['management_port'])
            self.bridge_upstream_local = event.get('upstream_local')
            self.bridge_endpoint.set(f'Computer IP: {event["bind_host"]} — telescope control TCP {event["listen_port"]}; '
                                     f'management TCP {event["management_port"]}; discovery UDP 55555. Firewall access unverified.')
            if self.bridge_upstream_local:
                self.bridge_endpoint.set(self.bridge_endpoint.get() +
                    f'\nOutbound telescope connection: {self.bridge_upstream_local[0]}:{self.bridge_upstream_local[1]}'
                    f' → {self.host.get()}:{self.port.get()}')
            self.show_network_interfaces()
        if kind == 'bridge_off':
            self.bridge = None
            self.bridge_listener = None
            self.bridge_upstream_local = None
            self.bridge_enabled.set(False)
            self.bridge_endpoint.set('Computer listener: OFF — no bridge ports open')
            self.show_network_interfaces()
            message = 'Bridge OFF — ' + (self.bridge_last_error or 'telescope connection closed; see Stop/readback log.')
            if event.get('stop_replies') and not all(event['stop_replies'].values()):
                message += ' One or more Stop acknowledgements were not received; physical rest is unverified.'
        if message:
            self.bridge_status.set(message)
        line = message or (f'{event.get("direction", "")} AUX {event["hex"]}' if kind == 'bridge_packet'
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
        if self.busy or self.motor is not None or self.bridge is not None:
            self.status.set('Disconnect motors before restarting the Wi-Fi adapter.')
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
        selected = self.diagnostic_rows.selection()
        if selected:
            self.diagnostic_details.configure(state='normal')
            self.diagnostic_details.delete('1.0', 'end')
            self.diagnostic_details.insert('end', self.diagnostic_replies.get(selected[0], ''))
            self.diagnostic_details.configure(state='disabled')

    def start_diagnostics(self):
        if self.busy or self.motor is not None or self.bridge is not None:
            self.status.set('Disconnect motors before running diagnostics.')
            return
        try:
            host, port = validate_endpoint(self.host.get(), self.port.get())
        except ValueError as error:
            self.status.set(str(error))
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
        self.diagnostic_status.set(f'Testing {host}:{port} — waiting for replies…')
        self.tabs.select(self.diagnostic_tab)
        def worker():
            try:
                report = self.diagnostic(host, port, callback=self.events.put)
            except Exception as error:
                report = {'error': str(error)}
            self.events.put({'event': 'diagnostic_done', 'report': report})
        threading.Thread(target=worker, daemon=True).start()

    def preset(self, home):
        if self.busy or self.motor is not None or self.bridge is not None:
            return
        address = '1.2.3.4'
        self.connection_mode.set('infrastructure' if home else 'direct')
        self.update_mode_help()
        if home:
            address = self.last_infrastructure_host or ''
        self.host.set(address)
        self.port.set('2000')
        self.status.set('House-network IP is a saved DHCP snapshot; it may change.' if home else
                        'Direct / ad hoc: connect this computer to SkyQLink-xx. No SSID-prefix discovery is used.')

    def update_mode_help(self):
        if self.connection_mode.get() == 'direct':
            text = 'Direct / ad hoc: connect this computer to SkyQLink-xx, then use 1.2.3.4:2000.'
        else:
            text = 'Infrastructure: connect to the same local Wi-Fi or wired LAN; use the telescope’s assigned IP and port 2000.'
        self.mode_help.set(text + '\nThis selects connection settings; it does not change the telescope switch or this computer’s Wi-Fi.')
        self.update_controls()

    def scan_lan(self):
        if self.busy or self.motor is not None or self.bridge is not None:
            self.status.set('Disconnect motor control before starting discovery.')
            return
        if self.connection_mode.get() == 'infrastructure' and self.host.get().strip() == '1.2.3.4':
            self.status.set('1.2.3.4 is the direct-connect address. Select Direct / ad hoc mode, or enter the telescope’s house-network IP.')
            return
        self.set_busy(True)
        try:
            port = validate_port(self.port.get())
        except ValueError as e:
            self.set_busy(False)
            self.status.set(str(e))
            return
        self.status.set(f'Discovering Celestron modules on TCP {port}… Close CPWI / other telescope connections.')
        self.scan_started = time.monotonic()
        self.scan_button.configure(text='Scanning…')
        self.tick_scan()
        self.append(f'SCAN LAN — verify motor/adapter firmware replies on TCP {port}; no movement or setting changes.')
        def worker():
            try:
                report = self.scanner(port=port, callback=self.events.put)
            except Exception as e:
                report = {'error': str(e)}
            self.events.put({'event': 'scan_done', 'report': report})
        threading.Thread(target=worker, daemon=True).start()

    def tick_scan(self):
        if self.scan_started is None:
            return
        elapsed = time.monotonic() - self.scan_started
        text = (f'● Scanning — {elapsed:.0f}s / 60s search period' if elapsed < 60 else
                f'● Search period reached — finishing active probes ({elapsed:.0f}s)')
        self.scan_indicator.configure(text=text, foreground='#b36b00' if int(elapsed * 2) % 2 else '#d99a00')
        self.scan_tick_id = self.root.after(250, self.tick_scan)

    def select_module(self):
        if self.busy or self.motor is not None or self.bridge is not None:
            return
        index = self.module_box.current()
        if 0 <= index < len(self.discovered):
            match = self.discovered[index]
            self.connection_mode.set('infrastructure')
            self.update_mode_help()
            self.host.set(match['ip'])
            self.port.set(str(match.get('port', 2000)))
            self.last_infrastructure_host = match['ip']
            self.status.set(f'Verified {match.get("module_type", "Celestron AUX")}: {match["ip"]}:{match.get("port", 2000)}')

    def update_controls(self):
        self.bridge_ip_help.set('Computer IP on the app’s network — required' if self.bridge_dual.get() else 'Computer LAN IP (blank = automatic)')
        self.bridge_interface_help.set(
            'Select this computer’s IP on the network shared with your phone/control app. For example, select Ethernet when the phone uses house Wi-Fi. Do not select telescope-facing Wi-Fi.'
            if self.bridge_dual.get() else
            'Select this computer’s local IP reachable from the control app. This chooses the bridge listening address, not a Wi-Fi network or the telescope IP.')
        locked = self.busy or self.motor is not None or self.bridge is not None
        for tab in (self.motor_tab, self.diagnostic_tab, self.provision_tab):
            self.tabs.tab(tab, state='disabled' if self.bridge is not None else 'normal')
        if self.bridge is not None:
            self.tabs.select(self.bridge_tab)
        bridge_allowed = self.connection_mode.get() == 'infrastructure' or self.bridge_dual.get()
        self.bridge_switch.configure(state='normal' if self.bridge is not None or (not locked and bridge_allowed) else 'disabled')
        self.bridge_bind_entry.configure(state='disabled' if locked else 'normal')
        self.bridge_dual_box.configure(state='disabled' if locked else 'normal')
        for widget in self.inputs:
            widget.configure(state='disabled' if locked else 'normal')
        for widget in (self.read_button, self.upload_button, self.show):
            widget.configure(state='disabled' if locked else 'normal')
        self.diagnostic_button.configure(state='disabled' if locked else 'normal')
        self.recovery_button.configure(state='disabled' if locked else 'normal')
        self.auto_recover_button.configure(state='disabled' if locked else 'normal')
        self.security_box.configure(state='disabled' if locked else 'readonly')
        self.motor_connect_button.configure(state='disabled' if locked else 'normal')
        self.module_box.configure(state='readonly' if self.discovered and not locked else 'disabled')
        self.motor_disconnect_button.configure(state='normal' if self.motor is not None else 'disabled')
        for button in self.jog_buttons:
            button.configure(state='normal' if self.motor_ready and (not self.jogging or self.held) else 'disabled')
        self.stop_button.configure(state='normal' if self.motor is not None else 'disabled')
        self.speed_box.configure(state='disabled' if self.jogging else 'readonly')
        self.duration_box.configure(state='disabled' if self.jogging else 'readonly')
        self.refresh_password()

    def connect_motors(self, recover_attempted=False):
        if self.busy or self.motor is not None or self.bridge is not None:
            return
        try:
            host, port = validate_endpoint(self.host.get(), self.port.get())
            self.motor = self.motor_factory(host, port, self.events.put)
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
        if not self.motor_ready or self.motor is None or self.jogging:
            return
        try:
            self.motor.jog(axis, direction, int(self.speed.get()), float(self.duration.get()))
            self.jogging = True
            self.update_controls()
        except (ValueError, RuntimeError) as e:
            self.status.set(str(e))

    def timed_direction(self, axis, direction):
        if self.drive_mode.get() == 'jog':
            self.jog(axis, direction)

    def press_direction(self, axis, direction):
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
        if self.held:
            self.stop_motors()

    def stop_motors(self):
        self.held = False
        if self.motor:
            self.motor.stop()
            self.motor_status.set('Stopping…')

    def disconnect_motors(self):
        self.connect_request_active = False
        if self.motor:
            self.motor_ready = False
            self.motor.disconnect()
            self.motor_status.set('Stopping and disconnecting…')
            self.update_controls()

    def stop_if_unfocused(self):
        if self.motor and self.jogging and self.root.focus_get() is None:
            self.stop_motors()

    def refresh_password(self):
        enabled = not self.busy and self.motor is None and self.bridge is None and self.security.get() != 'Open (no password)'
        self.password_entry.configure(show='' if self.show_password.get() else '•',
                                      state='normal' if enabled else 'disabled')

    def show_provisioned_network(self, report):
        before = report.get('readback') or report.get('before', {})
        wlan = before.get('wlan', before.get('get wlan', ''))
        ip = before.get('ip', before.get('get ip', ''))
        fields = dict(line.split('=', 1) for line in wlan.splitlines() if '=' in line)
        if fields.get('Join', '').strip() == '1' and 'DHCP=ON' in ip:
            ssid = fields.get('SSID', '(network name unavailable)').strip()
            self.provision_notice.set(f'Current configuration: infrastructure network “{ssid}”. '
                'Upload & Save replaces this network name, password and security with the values entered here. '
                'You can change networks over this existing infrastructure connection; no ad hoc switch or factory reset is required. '
                'Restart afterward, join the new network and discover the new telescope IP.')

    def append(self, text):
        self.console.configure(state='normal')
        self.console.insert('end', dt.datetime.now().strftime('%H:%M:%S') + '  ' + text.replace('\r', '') + '\n')
        self.console.see('end')
        if int(self.console.index('end-1c').split('.')[0]) > 1200:
            self.console.delete('1.0', '200.0')
        self.console.configure(state='disabled')

    def clear(self):
        self.console.configure(state='normal')
        self.console.delete('1.0', 'end')
        self.console.configure(state='disabled')

    def set_busy(self, value):
        self.busy = value
        self.clear_button.configure(state='disabled' if value else 'normal')
        self.update_controls()
        if value:
            self.progress.start(12)
        else:
            self.progress.stop()

    def start(self, apply):
        if self.busy or self.motor is not None or self.bridge is not None:
            self.status.set('Disconnect motor control before entering Wi-Fi command mode.')
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
        try:
            while True:
                event = self.events.get_nowait()
                kind = event['event']
                if kind == 'network_interfaces':
                    self.interface_refreshing = False
                    self.interface_refresh_button.configure(state='normal')
                    self.interface_rows = event['rows']
                    self.show_network_interfaces()
                    if event.get('error'):
                        self.append('COMPUTER NETWORK: ' + event['error'])
                elif kind.startswith('bridge_'):
                    self.handle_bridge_event(event)
                elif kind.startswith('motor_'):
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
                    self.set_busy(False)
                    report = event['report']
                    text = ('Wi-Fi: ' + ('VERIFIED' if report.get('wifi_verified') else 'NOT VERIFIED') +
                            ' | Motor firmware: ' + ('VERIFIED' if report.get('motor_firmware_verified') else 'NOT VERIFIED') +
                            ' | Both motor positions: ' + ('VERIFIED' if report.get('motor_positions_verified') else 'NOT VERIFIED'))
                    if report.get('saved_report'):
                        text = 'SAVED TEST RESULT — ' + text
                    if report.get('error'):
                        text += ' | ' + report['error']
                    self.diagnostic_status.set(text)
                    self.status.set(text)
                    self.append(text)
                    self.log_directory = report.get('log_directory')
                    self.logs_button.configure(state='normal' if self.log_directory else 'disabled')
                elif kind == 'scan_done':
                    self.scan_started = None
                    if self.scan_tick_id is not None:
                        self.root.after_cancel(self.scan_tick_id)
                        self.scan_tick_id = None
                    self.scan_button.configure(text='Discover Modules on LAN')
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
                        self.connection_mode.set('infrastructure')
                        self.update_mode_help()
                        self.host.set(match['ip'])
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
                        text = 'No Celestron replies verified. Close other telescope apps and check the router LAN; enter the IP manually if discovery is blocked.'
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
            self.root.destroy()
            return
        self.poll_id = self.after(100, self.poll)

    def handle_motor_event(self, event):
        kind = event['event']
        if kind == 'motor_values':
            axis = event['axis']
            values = self.values[axis]
            values['encoder'].set(str(event['encoder']))
            values['angle'].set(f'{event["angle"]:.5f}°')
            values['relative'].set(f'{event["relative"]:+.5f}°')
            values['firmware'].set(event['firmware'])
            if self.current_motion_axis == axis:
                before = values['before'].get()
                if before.isdigit():
                    values['delta_counts'].set(f'{relative_counts(event["encoder"], int(before)):+d}')
                    values['delta_degrees'].set(f'{relative_angle(event["encoder"], int(before)):+.5f}°')
            self.last_positions[axis] = event['monotonic']
        elif kind == 'motor_connected':
            self.connect_request_active = False
            self.motor_ready = True
            self.motor_status.set('Motor encoder connection verified')
            self.status.set(f'Motor connection verified at {event["host"]}:{event["port"]}; both encoders are live.')
            self.motion_status.set('Live encoder feedback verified on both axes. Ready for movement.')
            self.append(f'MOTORS connected to {event["host"]}:{event["port"]}')
        elif kind == 'motor_disconnected':
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
        if self.log_directory:
            try:
                open_directory(self.log_directory)
            except OSError:
                self.status.set('Saved logs: ' + self.log_directory)

    def close(self):
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
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true', help='Build and check the window without hardware, then close')
    parser.add_argument('--diagnostic-report', type=Path, help='Display a saved diagnostic report without connecting')
    parser.add_argument('--host', default='1.2.3.4', help='Initial telescope IP (default: 1.2.3.4)')
    parser.add_argument('--port', type=int, default=2000, help='Initial TCP port (default: 2000)')
    parser.add_argument('--connect', action='store_true', help='Connect and read encoders on startup; no movement')
    args = parser.parse_args()
    root = tk.Tk()
    app = SetupApp(root)
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
