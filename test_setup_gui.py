"""Tk desktop checks using a fake backend; no hardware writes or network connections."""
import time
import threading
import tkinter as tk
import unittest
from skyqlink_setup import SetupApp


class GuiTests(unittest.TestCase):
    def test_missing_rate_data_disables_dialog_and_csv_has_separate_columns(self):
        from unittest.mock import patch
        import csv
        import io
        with patch('skyqlink_setup.load_config', return_value={'schema_version': 1, 'telescope': {}, 'samples': []}):
            self.app.reload_calibration()
        self.assertFalse(self.app.has_slew_rates)
        self.assertEqual(str(self.app.slew_rates_button.cget('state')), 'disabled')
        self.app.open_slew_rates()
        self.assertIsNone(self.app.slew_rates_window)
        self.app.slew_rate_cells[(0x10, 1)].set('0.1250 / 0.2500')
        rows = self.app.slew_rate_rows()
        self.assertEqual(rows[1], [1, '0.1250', '0.2500', '', ''])
        parsed = list(csv.reader(io.StringIO(self.app.spreadsheet_output(rows, delimiter=','))))
        self.assertEqual(len(parsed), 10)
        self.assertTrue(all(len(row) == 5 for row in parsed))

    def test_profile_keymap_controls_switch_help_and_dispatch(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        self.app.calibration['keymap']['connect'] = 'c'
        self.app.refresh_profile_keymap()
        self.assertIn('C: connect', self.app.keyboard_help.get())
        self.app.keyboard_toggle.invoke()
        self.app.connect_motors = Mock()
        event = SimpleNamespace(keysym='o', state=0, widget=self.app.motor_tab)
        self.app.motor_key_press(event)
        self.app.connect_motors.assert_not_called()
        event.keysym = 'c'
        self.app.motor_key_press(event)
        self.app.connect_motors.assert_called_once()
        del self.app.calibration['keymap']
        self.app.refresh_profile_keymap()
        self.assertFalse(self.app.keyboard_enabled.get())
        self.assertEqual(self.app.keyboard_help.get(), '')
        self.assertEqual(self.app.keyboard_toggle.cget('state'), 'disabled')
        self.app.keyboard_toggle.invoke()
        self.assertFalse(self.app.keyboard_enabled.get())

    def test_spreadsheet_copy_preserves_cells_and_multiline_values(self):
        import csv
        import io
        rows = [['Field', 'Value'], ['quoted, text', 'line 1\nline 2\t"quoted"']]
        text = self.app.spreadsheet_output(rows)
        self.assertEqual(list(csv.reader(io.StringIO(text), delimiter='\t')), rows)
        motor = list(csv.reader(io.StringIO(self.app.motor_output()), delimiter='\t'))
        self.assertEqual(motor[0], ['Measurement', 'Azimuth', 'Elevation'])
        self.assertTrue(all(len(row) == 3 for row in motor))

    def test_time_dialog_readback_and_read_only_request(self):
        from unittest.mock import patch
        self.app.open_time_settings()
        self.app.time_mode.set('Every N minutes')
        self.app.time_enable.set('invalid unused edit')
        with patch('skyqlink_setup.configure_time', return_value={'clock': {'Uptime': '12 s'}}) as read, patch('skyqlink_setup.messagebox.askyesno') as confirm:
            self.app.start_time_settings(read_only=True)
            deadline = time.monotonic() + 2
            while not read.called and time.monotonic() < deadline:
                self.root.update()
                time.sleep(.01)
            self.assertTrue(read.called)
            self.assertIsNone(read.call_args.kwargs['enable'])
            self.assertFalse(read.call_args.kwargs['sync_now'])
            self.assertFalse(read.call_args.kwargs['persist'])
            self.assertIsNone(read.call_args.kwargs['server_ip'])
            confirm.assert_not_called()
        self.assertTrue(self.app.time_readback_widget.winfo_exists())

    def setUp(self):
        self.calls = []
        self.motor_calls = []
        self.motors = []
        owner = self
        class FakeMotor:
            def __init__(self, host, port, callback, *, idle_release=30, heartbeat_enabled=True, heartbeat_interval=1.0):
                self.idle_release = idle_release
                self.callback = callback
                self.host, self.port = host, port
                owner.motors.append(self)
            def start(self):
                self.callback({'event': 'motor_connected', 'host': self.host, 'port': self.port})
                self.callback({'event': 'motor_values', 'axis': 0x10, 'encoder': 12345,
                               'angle': .265, 'relative': .01, 'firmware': '5.24', 'monotonic': time.monotonic()})
            def jog(self, *args):
                owner.motor_calls.append(args)
            def stop(self):
                owner.motor_calls.append('stop')
            def hold(self, *args):
                owner.motor_calls.append(('hold',) + args)
            def renew_hold(self):
                pass
            def disconnect(self):
                self.callback({'event': 'motor_disconnected', 'log_directory': '/tmp/simulated-motor-test'})
        def operation(*args, callback):
            self.calls.append(args)
            callback({'event': 'tx', 'command': 'set wlan phrase [REDACTED]'})
            return {'saved': args[5], 'exit_confirmed': True}
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = SetupApp(self.root, operation, motor_factory=FakeMotor,
                            scanner=lambda **kwargs: {'matches': [{'ip': '192.168.1.42', 'port': kwargs['port'],
                                                                  'module_type': 'SkyQLink RN-171', 'endpoint_kind': 'physical_wifly', 'verified': True}]})

        self.app.last_infrastructure_host = '192.168.1.42'
        self.app.calibration = {'telescope': {'host': '192.168.1.42', 'port': 2000}, 'samples': []}
        self.app.calibration['keymap'] = {'elevation_up': 'i', 'elevation_down': 'm', 'azimuth_left': 'j', 'azimuth_right': 'l', 'stop': 'k', 'connect': 'o', 'disconnect': 'p'}
        self.app.refresh_profile_keymap()

    def tearDown(self):
        self.app.busy = False
        self.app.motor = None
        self.app.close()

    def drain_ui(self):
        # Rendering is time-budgeted. Wait for the queued events, not a fixed
        # delay that can expire between connected and encoder-value events.
        deadline = time.monotonic() + 3
        def check():
            if self.app.events.empty() or time.monotonic() >= deadline:
                self.root.quit()
            else:
                self.root.after(10, check)
        self.root.after(150, check)
        self.root.mainloop()
        self.assertTrue(self.app.events.empty(), 'GUI event queue did not drain')

    def finish_worker(self):
        end = time.monotonic() + 2
        def check():
            if not self.app.busy or time.monotonic() >= end:
                self.root.quit()
            else:
                self.root.after(10, check)
        self.root.after(10, check)
        self.root.mainloop()
        self.assertFalse(self.app.busy)

    def test_clear_display_requires_confirmation(self):
        from unittest.mock import patch
        self.app.append('Keep this until confirmed')
        with patch('skyqlink_setup.messagebox.askyesno', return_value=False):
            self.app.clear()
        self.assertIn('Keep this until confirmed', self.app.console.get('1.0', 'end'))
        with patch('skyqlink_setup.messagebox.askyesno', return_value=True):
            self.app.clear()
        self.assertEqual(self.app.console.get('1.0', 'end').strip(), '')

    def test_signed_elevation_settings_readback(self):
        self.app.events.put({'event': 'motor_settings_done', 'report': {
            'axis': 0x11, 'values': {'degrees': 299.69,
            'positive_backlash': 0, 'negative_backlash': 0}}})
        self.drain_ui()
        self.assertAlmostEqual(float(self.app.controller_fields[0x11]['angle'].get()), -60.31)
        self.assertEqual(self.app.idle_release.get(), '30 seconds')

    def test_local_reference_connection_indicator_and_disconnect_button(self):
        from unittest.mock import Mock
        app = self.app
        app.open_motor_settings()
        self.assertEqual(app.reference_connection_indicator.cget('text'), '● Disconnected')
        self.assertEqual(app.reference_disconnect_button.cget('state'), 'disabled')
        app.motor = Mock()
        app.motor_ready = False
        app.update_controls()
        self.assertEqual(app.reference_connection_indicator.cget('text'), '● Connected -- Link Unconfirmed')
        app.motor_ready = True
        app.last_positions = {axis: time.monotonic() for axis in (0x10, 0x11)}
        app.update_controls()
        self.assertEqual(app.reference_connection_indicator.cget('text'), '● Connected -- Link Confirmed')
        self.assertEqual(app.reference_connect_button.cget('background'), '#146b39')
        self.assertEqual(app.reference_disconnect_button.cget('state'), 'normal')
        app.last_positions[0x10] = time.monotonic() - 1000
        app.refresh_reference_connection_controls()
        self.assertIn('Connected -- Link Unconfirmed', app.reference_connection_indicator.cget('text'))
        self.assertEqual(app.reference_connect_button.cget('background'), app.reference_connection_indicator.cget('background'))
        app.direct_polling_applied = (False, 1.0, 30)
        app.refresh_reference_connection_controls()
        self.assertIn('Periodic polling is off', app.reference_connection_detail.get())
        app.handle_motor_event({'event': 'motor_error', 'message': 'Simulated connection failure'})
        self.assertEqual(app.reference_connection_indicator.cget('text'), '● Disconnected')
        self.assertEqual(app.reference_disconnect_button.cget('background'), '#b52b2b')
        self.assertEqual(app.reference_disconnect_button.cget('relief'), 'sunken')
        self.assertIn('Simulated connection failure', app.reference_connection_detail.get())
        self.assertEqual(app.reference_disconnect_button.cget('state'), 'normal')
        app.motor = None
        app.motor_ready = False
        app.update_controls()
        self.assertEqual(app.reference_disconnect_button.cget('state'), 'disabled')
        self.assertEqual(app.reference_connection_indicator.cget('text'), '● Disconnected')

    def test_local_reference_read_apply_and_clear_in_both_profiles(self):
        from unittest.mock import Mock
        app = self.app
        for profile in ('SkyQLink', 'Celestron module'):
            with self.subTest(profile=profile):
                app.interface_mode.set(profile)
                app.motor = Mock()
                app.motor_ready = True
                app.clear_local_references()
                app.poll_local_reference(0x10)
                app.motor.request_position.assert_called_once_with(0x10)
                app.poll_local_reference(0x11)
                self.assertEqual(app.motor.request_position.call_count, 1)
                for axis, count, known in ((0x10, 0, '100'), (0x11, 0, '-20')):
                    app.handle_motor_event({'event': 'motor_values', 'axis': axis,
                        'encoder': count, 'angle': 0, 'relative': 0, 'firmware': 'test',
                        'monotonic': time.monotonic()})
                    app.reference_inputs[axis].set(known)
                    app.set_position_reference(axis)
                    self.assertEqual(app.position_references[axis], (count, float(known)))
                    app.handle_motor_event({'event': 'motor_values', 'axis': axis,
                        'encoder': 0, 'angle': 0, 'relative': 0, 'firmware': 'test',
                        'monotonic': time.monotonic()})
                    self.assertAlmostEqual(float(app.values[axis]['referenced'].get().rstrip('°')), float(known))
                self.assertFalse(app.reference_poll_pending)
                app.clear_local_references()
                self.assertFalse(app.position_references)
                app.motor.jog.assert_not_called()
                app.motor = None

    def test_two_axis_readouts_and_applied_local_history(self):
        self.app.open_motor_settings()
        for axis, degrees, positive in ((0x10, 123.0, 4), (0x11, 299.0, 7)):
            self.app.events.put({'event': 'motor_settings_done', 'report': {'axis': axis,
                'values': {'degrees': degrees, 'positive_backlash': positive, 'negative_backlash': 2}}})
        self.drain_ui()
        self.assertIn('123.00000', self.app.controller_readout[0x10].get())
        self.assertIn('-61.00000', self.app.controller_readout[0x11].get())
        self.assertIn('Read current values result at', self.app.controller_readout[0x10].get())
        self.app.motor_ready = True
        self.app.values[0x10]['encoder'].set('0')
        self.app.last_positions[0x10] = time.monotonic()
        self.app.reference_inputs[0x10].set('10')
        self.app.set_position_reference(0x10)
        original = self.app.local_history[0x10].get()
        self.app.values[0x10]['encoder'].set('100')
        self.app.refresh_reference_preview(0x10)
        self.assertEqual(self.app.local_history[0x10].get(), original)
        self.app.clear_local_references()
        self.assertFalse(self.app.position_references)
        self.assertTrue(self.app.local_history[0x10].get().startswith('Inactive'))
        self.assertEqual(self.app.reference_inputs[0x10].get(), '0')

    def test_upload_worker_and_masked_transfer_log(self):
        app = self.app
        app.host.set('192.168.1.150')
        app.port.set('2222')
        app.ssid.set('Example network')
        app.password.set('testSecret42')
        app.start(True)
        self.finish_worker()
        self.assertEqual(self.calls[0][:2], ('192.168.1.150', 2222))
        self.assertTrue(self.calls[0][5])
        self.assertEqual(app.password.get(), '')
        self.assertNotIn('testSecret42', app.console.get('1.0', 'end'))
        self.assertIn('not yet verified', app.status.get())

    def test_read_does_not_require_wifi_credentials(self):
        self.app.start(False)
        self.finish_worker()
        self.assertFalse(self.calls[0][5])
        self.assertIn('no settings changed', self.app.status.get())

    def test_scan_indicator_runs_then_shows_timeout_and_unlocks(self):
        resume = threading.Event()
        def scanner(**kwargs):
            resume.wait(2)
            return {'matches': [], 'timed_out': True, 'elapsed_seconds': 60}
        self.app.scanner = scanner
        self.app.scan_lan()
        try:
            self.assertTrue(self.app.busy)
            self.assertIn('Scanning', self.app.scan_indicator.cget('text'))
            self.assertIsNotNone(self.app.scan_tick_id)
        finally:
            resume.set()
        self.finish_worker()
        self.assertIn('timed out', self.app.scan_indicator.cget('text'))
        self.assertEqual(str(self.app.scan_indicator.cget('foreground')), '#b22b2b')
        self.assertIsNone(self.app.scan_tick_id)
        self.assertEqual(str(self.app.scan_button.cget('state')), 'normal')

    def test_invalid_input_never_calls_backend(self):
        self.app.port.set('bad')
        self.app.start(True)
        self.assertFalse(self.calls)
        self.assertFalse(self.app.busy)

    def test_physical_wifi_switch_instructions_are_explicit(self):
        text = self.app.switch_help_label.cget('text')
        for required in ('Physical Wi-Fi mode switch', 'beside its power socket',
                         'LEFT — Direct / ad hoc', 'RIGHT — Infrastructure',
                         'already RIGHT, leave it there', 'does not move the physical switch'):
            self.assertIn(required, text)

    def test_motor_values_jog_stop_and_provision_lock(self):
        app = self.app
        app.connect_motors()
        self.drain_ui()
        self.assertTrue(app.motor_ready)
        self.assertEqual(app.values[0x10]['encoder'].get(), '12345')
        self.assertEqual(app.values[0x10]['firmware'].get(), '5.24')
        self.assertEqual(str(app.upload_button['state']), 'disabled')
        app.start(False)
        self.assertFalse(self.calls)
        app.jog(0x10, -1)
        self.assertEqual(self.motor_calls[-1], (0x10, -1, 6, .5))
        app.stop_motors()
        self.assertEqual(self.motor_calls[-1], 'stop')
        app.disconnect_motors()
        self.drain_ui()
        self.assertIsNone(app.motor)
        self.assertEqual(str(app.upload_button['state']), 'normal')

    def test_provisioning_blocks_motor_connect(self):
        self.app.set_busy(True)
        self.app.connect_motors()
        self.assertFalse(self.motors)

    def test_connection_modes_and_lan_scan(self):
        app = self.app
        app.preset(False)
        self.assertEqual(app.host.get(), '1.2.3.4')
        self.assertIn('SkyQLink-xx', app.mode_help.get())
        app.preset(True)
        self.assertEqual(app.connection_mode.get(), 'infrastructure')
        self.assertIn('same local Wi-Fi', app.mode_help.get())
        app.scan_lan()
        self.finish_worker()
        self.assertEqual(app.host.get(), '192.168.1.42')
        self.assertEqual(app.port.get(), '2000')
        self.assertIn('endpoint(s) found', app.status.get())
        app.use_module_button.invoke()
        self.assertFalse(self.motors)
        self.assertFalse(self.calls)

    def test_hold_arrows_release_and_stop(self):
        app = self.app
        app.connect_motors()
        self.drain_ui()
        self.assertEqual(app.drive_mode.get(), 'hold')
        app.press_direction(0x11, -1)
        self.assertEqual(self.motor_calls[-1], ('hold', 0x11, -1, 6))
        self.assertTrue(app.held)
        app.release_direction()
        self.assertFalse(app.held)
        self.assertEqual(self.motor_calls[-1], 'stop')

    def test_deep_diagnostics_requires_confirmation(self):
        from unittest.mock import Mock, patch
        self.assertFalse(self.app.deep_diagnostics.get())
        self.app.deep_diagnostics.set(True)
        self.app.diagnostic = Mock(return_value={})
        with patch('skyqlink_setup.messagebox.askyesno', return_value=False) as warning:
            self.app.start_diagnostics()
            warning.assert_called_once()
        self.app.diagnostic.assert_not_called()
        self.assertFalse(self.app.busy)
        with patch('skyqlink_setup.messagebox.askyesno', return_value=True):
            self.app.start_diagnostics()
            self.finish_worker()
        self.assertTrue(self.app.diagnostic.call_args.kwargs['deep'])

    def test_real_tk_keyboard_dispatch_and_focus_recovery(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        self.root.deiconify()
        self.app.tabs.select(self.app.motor_tab)
        self.root.update()
        self.app.keyboard_toggle.invoke()
        self.app.host_entry.focus_force()
        self.app.connect_motors = Mock()
        self.app.host_entry.event_generate('<KeyPress-o>')
        self.app.connect_motors.assert_not_called()
        self.app.focus_motor_shortcuts(SimpleNamespace(widget=self.app.motor_tab))
        self.root.update()
        self.assertEqual(self.root.focus_get(), self.app.motor_tab)
        self.app.motor_tab.event_generate('<KeyPress-o>')
        self.app.connect_motors.assert_called_once()
        self.app.motor_ready = True
        self.app.press_direction = Mock()
        self.app.release_direction = Mock()
        for key, axis, direction in [('i', 0x11, 1), ('j', 0x10, -1), ('l', 0x10, 1), ('m', 0x11, -1)]:
            releases_before = self.app.release_direction.call_count
            self.app.motor_tab.event_generate(f'<KeyPress-{key}>')
            self.app.press_direction.assert_called_with(axis, direction)
            self.app.motor_tab.event_generate(f'<KeyRelease-{key}>')
            self.drain_ui()
            self.assertIsNone(self.app.keyboard_direction)
            # Mouse releases/focus events in an interactive desktop may also
            # request a safe Stop. Each key release must request one itself.
            self.assertGreater(self.app.release_direction.call_count, releases_before)
        self.assertEqual(self.app.press_direction.call_count, 4)
        self.app.stop_motors = Mock()
        self.app.disconnect_motors = Mock()
        self.app.motor_tab.event_generate('<KeyPress-k>')
        self.app.stop_motors.assert_called_once()
        self.app.motor_tab.event_generate('<KeyPress-p>')
        self.app.disconnect_motors.assert_called_once()
        self.app.keyboard_toggle.invoke()
        self.assertFalse(self.app.keyboard_enabled.get())
        self.app.connect_motors.reset_mock()
        self.app.motor_tab.event_generate('<KeyPress-o>')
        self.app.connect_motors.assert_not_called()

    def test_tabs_and_keyboard_entry_guards(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        self.assertEqual([self.app.tabs.tab(t, 'text') for t in self.app.tabs.tabs()],
                         ['Motor control', 'Control Bridge', 'Diagnostics', 'Wi-Fi provisioning'])
        self.app.tabs.select(self.app.motor_tab)
        self.app.keyboard_enabled.set(True)
        self.app.connect_motors = Mock()
        self.app.disconnect_motors = Mock()
        self.app.stop_motors = Mock()
        e = SimpleNamespace(keysym='o', widget=self.app, state=0)
        self.app.motor_key_press(e)
        self.app.connect_motors.assert_called_once()
        e.keysym = 'p'
        self.app.motor_key_press(e)
        self.app.stop_motors.assert_called_once()
        self.app.disconnect_motors.assert_called_once()
        e.keysym = 'o'
        e.widget = self.app.host_entry
        self.app.motor_key_press(e)
        self.app.connect_motors.assert_called_once()

    def test_windows_numlock_does_not_block_shortcuts(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        if self.root.tk.call('tk', 'windowingsystem') != 'win32':
            self.skipTest('Windows modifier mapping')
        self.app.tabs.select(self.app.motor_tab)
        self.app.keyboard_enabled.set(True)
        self.app.connect_motors = Mock()
        self.app.motor_key_press(SimpleNamespace(keysym='o', widget=self.app, state=0x0008))
        self.app.connect_motors.assert_called_once()
        for modifiers in (0x0004, 0x20000, 0x20008):
            self.app.motor_key_press(SimpleNamespace(keysym='o', widget=self.app, state=modifiers))
        self.app.connect_motors.assert_called_once()

    def test_reference_is_local_and_requires_fresh_feedback(self):
        self.app.motor_ready = True
        self.app.values[0x10]['encoder'].set(str((1 << 24) - 100))
        self.app.last_positions[0x10] = time.monotonic()
        self.app.reference_inputs[0x10].set('10')
        self.app.set_position_reference(0x10)
        self.assertEqual(self.app.position_references[0x10][1], 10)
        self.assertFalse(self.motor_calls)
        self.app.handle_motor_event({'event': 'motor_values', 'axis': 0x10, 'encoder': 100,
            'angle': 0.002, 'relative': 0.004, 'firmware': '5.24', 'monotonic': time.monotonic()})
        self.assertTrue(self.app.values[0x10]['referenced'].get().startswith('10.004'))
        self.app.last_positions[0x11] = time.monotonic() - 5
        self.app.set_position_reference(0x11)
        self.assertNotIn(0x11, self.app.position_references)

    def test_diagnostics_present_replies_and_partial_verification(self):
        def diagnostic(host, port, callback, **options):
            callback({'event': 'diagnostic_row', 'device': 'Wi-Fi adapter', 'endpoint': 'ver',
                      'status': 'REPLY', 'reply': 'WiFly 2.40-CEL RN-171'})
            callback({'event': 'diagnostic_row', 'device': 'Azimuth', 'endpoint': 'GET_POSITION',
                      'status': 'NO VALID REPLY', 'reply': 'Timed out'})
            return {'wifi_verified': True, 'motor_positions_verified': False, 'log_directory': '/tmp/diag'}
        self.app.diagnostic = diagnostic
        self.app.start_diagnostics()
        self.finish_worker()
        self.assertEqual(len(self.app.diagnostic_rows.get_children()), 2)
        first = self.app.diagnostic_rows.get_children()[0]
        self.assertIn('RN-171', self.app.diagnostic_rows.item(first, 'values')[3])
        self.assertIn('RN-171', self.app.diagnostic_details.get('1.0', 'end'))
        self.assertIn('RN-171', self.app.console.get('1.0', 'end'))
        self.assertIn('Both motor positions: NOT VERIFIED', self.app.diagnostic_status.get())
        self.assertFalse(self.app.motor_ready)
        self.assertEqual(self.root.title(), 'Celestron Telescope Network Control')
        self.app.diagnostic_rows.selection_set(self.app.diagnostic_rows.get_children()[0])
        self.app.show_diagnostic_reply()
        self.assertIn('RN-171', self.app.diagnostic_details.get('1.0', 'end'))

    def test_missing_encoder_reply_keeps_no_reply_visible(self):
        app = self.app
        app.connect_motors()
        self.drain_ui()
        app.handle_motor_event({'event': 'motor_telemetry_missing', 'axis': 0x10})
        self.drain_ui()
        self.assertEqual(app.values[0x10]['age'].get(), 'No reply')

    def test_measured_jog_values_are_visible_in_motor_box(self):
        self.app.handle_motor_event({'event': 'motor_motion_result', 'axis': 0x10,
                                    'start_encoder': 100000, 'end_encoder': 112800,
                                    'measured_counts': 12800, 'measured_degrees': .274658,
                                    'stationary_verified': True, 'message': 'Measured encoder change'})
        values = self.app.values[0x10]
        self.assertEqual(values['before'].get(), '100000')
        self.assertEqual(values['after'].get(), '112800')
        self.assertEqual(values['delta_counts'].get(), '+12800')
        self.assertEqual(values['delta_degrees'].get(), '+0.27466°')
        self.assertEqual(values['stationary'].get(), 'Verified')

    def test_discovery_lists_adapter_with_silent_motors(self):
        self.app.scanner = lambda **kwargs: {'matches': [
            {'ip': '192.168.1.42', 'port': 2000, 'module_type': 'SkyQLink RN-171', 'endpoint_kind': 'physical_wifly',
             'verified': True, 'motors_verified': False,
             'verification_note': 'SkyQLink adapter identified; motors not responding'}]}
        self.app.scan_lan()
        self.finish_worker()
        self.app.use_module_button.invoke()
        self.assertEqual(self.app.module_box.current(), 0)
        self.assertNotIn('motors not responding', self.app.module_box.get())
        self.assertIn('motors not responding', self.app.console.get('1.0', 'end'))
        self.assertEqual(self.app.host.get(), '192.168.1.42')
        self.assertFalse(self.app.motor_ready)

    def test_direct_discovery_preserves_mode_and_house_address(self):
        calls = []
        def scanner(**kwargs):
            calls.append(kwargs)
            return {'matches': [{'ip': '1.2.3.4', 'verified': True}]}
        self.app.scanner = scanner
        self.app.connection_mode.set('direct')
        previous = self.app.last_infrastructure_host
        self.app.scan_lan()
        self.finish_worker()
        self.app.use_module_button.invoke()
        self.assertEqual(calls[0]['mode'], 'direct')
        self.assertEqual(self.app.connection_mode.get(), 'direct')
        self.assertEqual(self.app.last_infrastructure_host, previous)

    def test_requested_tab_order_and_infrastructure_reprovisioning_notice(self):
        self.assertEqual([self.app.tabs.tab(t, 'text') for t in self.app.tabs.tabs()],
                         ['Motor control', 'Control Bridge', 'Diagnostics', 'Wi-Fi provisioning'])
        self.app.preset(True)
        self.app.show_provisioned_network({'before': {'get wlan': 'SSID=ExistingNetwork\r\nJoin=1\r\nAuth=WPA2',
                                                    'get ip': 'DHCP=ON'}})
        self.assertEqual('ExistingNetwork', self.app.provision_ssid_readback.get())
        self.assertIn('no ad hoc switch or factory reset', self.app.provision_notice.get())
        self.assertEqual(str(self.app.upload_button['state']), 'normal')

    def test_discovery_does_not_require_an_ip_address(self):
        self.app.host.set('')
        self.app.scan_lan()
        self.finish_worker()
        self.app.use_module_button.invoke()
        self.assertEqual(self.app.host.get(), '192.168.1.42')

    def test_connection_failure_retains_reason_after_stop_and_disconnect(self):
        app = self.app
        reason = 'No valid encoder replies from either motor'
        app.handle_motor_event({'event': 'motor_error', 'message': reason})
        app.handle_motor_event({'event': 'motor_stopped', 'message': 'Stop attempted'})
        app.handle_motor_event({'event': 'motor_disconnected', 'log_directory': '/tmp/test'})
        self.assertEqual(app.motion_status.get(), reason)
        self.assertIn('Connection failed', app.motor_status.get())
        self.assertEqual(str(app.recovery_button['state']), 'normal')

    def test_recovery_returns_verified_position_result(self):
        self.app.recovery = lambda *args, **kwargs: {'motor_positions_verified': True,
                                                    'positions': {'0x10': 31809, '0x11': 16767271}}
        self.app.start_recovery()
        self.finish_worker()
        self.assertIn('both motor encoders replied', self.app.status.get())
        self.assertIn('31809', self.app.console.get('1.0', 'end'))

    def test_initial_encoder_failure_recovers_once_then_reconnects(self):
        original = self.app.motor_factory
        attempts = []
        class FirstFailure:
            def __init__(self, callback):
                self.callback = callback
            def start(self):
                self.callback({'event': 'motor_error', 'message': 'Motor connection NOT verified'})
                self.callback({'event': 'motor_disconnected', 'log_directory': '/tmp/first'})
        def factory(host, port, callback, **options):
            attempts.append(host)
            return FirstFailure(callback) if len(attempts) == 1 else original(host, port, callback, **options)
        self.app.motor_factory = factory
        self.app.recovery = lambda *args, **kwargs: {'motor_positions_verified': True, 'positions': {}}
        self.app.connect_motors()
        for _ in range(5):
            self.drain_ui()
            if self.app.motor_ready:
                break
        self.assertEqual(len(attempts), 2)
        self.assertTrue(self.app.motor_ready)
        self.assertTrue(self.app.connect_recovery_attempted)

    def test_failed_reconnect_does_not_restart_forever(self):
        attempts = []
        class FailingMotor:
            def __init__(self, host, port, callback, **options):
                self.callback = callback
                attempts.append(host)
            def start(self):
                self.callback({'event': 'motor_error', 'message': 'Motor connection NOT verified'})
                self.callback({'event': 'motor_disconnected', 'log_directory': '/tmp/failure'})
        self.app.motor_factory = FailingMotor
        self.app.recovery = lambda *args, **kwargs: {'motor_positions_verified': True}
        self.app.connect_motors()
        for _ in range(6):
            self.drain_ui()
        self.assertEqual(len(attempts), 2)
        self.assertIsNone(self.app.motor)
        self.assertFalse(self.app.motor_ready)



class BridgeGuiTests(unittest.TestCase):
    setUp = GuiTests.setUp
    tearDown = GuiTests.tearDown
    drain_ui = GuiTests.drain_ui

    def test_rocker_changes_mode_and_cannot_enable_when_disabled(self):
        calls = []
        rocker = self.app.bridge_switch
        rocker.command = lambda: calls.append(self.app.bridge_enabled.get())
        rocker.configure(state='disabled')
        rocker.choose(True)
        self.assertFalse(self.app.bridge_enabled.get())
        self.assertEqual(calls, [])
        rocker.configure(state='normal')
        rocker.choose(True)
        self.assertTrue(self.app.bridge_enabled.get())
        rocker.choose(False)
        self.assertFalse(self.app.bridge_enabled.get())
        self.assertEqual(calls, [True, False])
    def test_bridge_locks_tabs_preserves_readback_and_off_restores_controls(self):
        owner = self
        class FakeBridge:
            def __init__(self, host, port, callback, **options):
                self.callback = callback
                owner.bridge_options = options
            def start(self):
                self.callback({'event': 'bridge_ready', 'message': 'Bridge ON at 192.168.1.20:2000'})
                self.callback({'event': 'bridge_values', 'axis': 16, 'encoder': 23456,
                               'angle': .5, 'relative': .1, 'firmware': '5.24', 'monotonic': time.monotonic()})
            def stop(self):
                self.callback({'event': 'bridge_off', 'log_directory': '/tmp/simulated-bridge'})
        app = self.app
        app.bridge_factory = FakeBridge
        self.assertIn(str(app.bridge_off_mark), str(app.tabs.tab(app.bridge_tab, 'image')))
        app.preset(True)
        app.bridge_enabled.set(True)
        app.toggle_bridge()
        # GUI event handling is deliberately time-budgeted; allow multiple ticks.
        deadline = time.monotonic() + 2
        while app.values[16]['encoder'].get() != '23456' and time.monotonic() < deadline:
            self.drain_ui()
        self.assertEqual(app.tabs.tab(app.motor_tab, 'state'), 'normal')
        self.assertFalse(app.bridge_jog_requested.get())
        self.assertIn(str(app.bridge_on_mark), str(app.tabs.tab(app.bridge_tab, 'image')))
        self.assertIn(str(app.bridge_tab_mark), str(app.tabs.tab(app.motor_tab, 'image')))
        self.assertEqual(str(app.motor_settings_button.cget('state')), 'disabled')
        for tab in (app.diagnostic_tab, app.provision_tab):
            self.assertEqual(app.tabs.tab(tab, 'state'), 'disabled')
        self.assertEqual(app.tabs.select(), str(app.bridge_tab))
        self.assertEqual(app.values[16]['encoder'].get(), '23456')
        self.assertIn('Bridge ON', app.bridge_console.get('1.0', 'end'))
        app.connect_motors()
        self.assertEqual(self.motors, [])
        app.bridge_enabled.set(False)
        app.toggle_bridge()
        self.drain_ui()
        self.assertIsNone(app.bridge)
        self.assertIn(str(app.bridge_off_mark), str(app.tabs.tab(app.bridge_tab, 'image')))
        for tab in (app.motor_tab, app.diagnostic_tab, app.provision_tab):
            self.assertEqual(app.tabs.tab(tab, 'state'), 'normal')

    def test_bridge_jog_requires_feedback_and_fault_stays_locked(self):
        from unittest.mock import Mock, patch
        app = self.app
        app.bridge = Mock(local_fault=False)
        app.bridge_jog_requested.set(True)
        with patch('skyqlink_setup.messagebox.askyesno', return_value=True):
            app.toggle_bridge_jog()
        app.bridge.set_local_jog.assert_called_once_with(True)
        self.assertFalse(app.bridge_jog_ready)
        app.handle_bridge_event({'event': 'bridge_local_mode', 'enabled': True, 'message': 'Enabled'})
        for axis in (16, 17):
            app.handle_bridge_event({'event': 'bridge_values', 'axis': axis, 'encoder': 123,
                                    'angle': .01, 'relative': 0, 'firmware': '5.24', 'monotonic': time.monotonic()})
        self.assertTrue(app.bridge_jog_ready)
        app.bridge_jog(16, 1, held=True)
        app.bridge.jog.assert_called_once_with(16, 1, int(app.speed.get()), 2.0)
        app.bridge.local_fault = True
        app.handle_bridge_event({'event': 'bridge_local_motion', 'moving': False, 'message': 'Feedback lost'})
        self.assertFalse(app.bridge_jog_ready)
        app.handle_bridge_event({'event': 'bridge_values', 'axis': 16, 'encoder': 123,
                                'angle': .01, 'relative': 0, 'firmware': '5.24', 'monotonic': time.monotonic()})
        self.assertFalse(app.bridge_jog_ready)
        app.handle_bridge_event({'event': 'bridge_packet', 'direction': 'client', 'hex': '3b0420102400a8', 'interpretation': 'Move positive request/echo: STOP'})
        self.assertIn('3b0420102400a8 | (AUX header: Move positive request/echo: STOP)', app.bridge_console.get('1.0', 'end'))
        app.bridge = None

    def test_bridge_polling_summary_uses_applied_values_and_stale_margin(self):
        from unittest.mock import Mock
        app = self.app
        app.bridge = Mock(local_fault=False)
        app.bridge_is_ready = True
        app.bridge_polling_applied = (True, 15.0, False, 1.0)
        app.bridge_heartbeat_interval.set('99')  # Unapplied edit must not appear.
        app.update_controls()
        self.assertIn('15s', app.bridge_polling_source.get())
        self.assertNotIn('99s', app.bridge_polling_source.get())
        self.assertEqual(app.encoder_stale_after(), 18)
        self.assertEqual(app.motor_bridge_polling_label.winfo_manager(), '')
        app.bridge_jog_active = True
        app.update_controls()
        self.assertIn('Local-jog feedback polling is active', app.bridge_polling_source.get())
        self.assertIn('Heartbeat waits', app.bridge_polling_source.get())
        self.assertIn('Control Bridge', app.motor_bridge_polling_text.get())
        self.assertEqual(app.motor_bridge_polling_label.winfo_manager(), 'grid')
        self.assertEqual(app.encoder_stale_after(), 10)
        self.assertEqual(app.bridge_polling_applied, (True, 15.0, False, 1.0))
        app.bridge_jog_active = False
        app.bridge_polling_applied = (False, 5.0, True, 20.0)
        app.update_controls()
        self.assertEqual(app.encoder_stale_after(), 23)
        app.bridge_polling_applied = (False, 5.0, False, 1.0)
        app.update_controls()
        self.assertIn('No bridge-generated periodic', app.bridge_polling_source.get())
        self.assertEqual(app.encoder_stale_after(), 10)
        app.bridge = None

    def test_direct_aux_log_decodes_outgoing_commands_without_received_traffic(self):
        app = self.app
        app.handle_motor_event({'event': 'motor_tx', 'command': 0x24, 'hex': '3b0420102400a8'})
        app.handle_motor_event({'event': 'motor_reply', 'command': 1, 'hex': '3b0610200140000089'})
        app.handle_motor_event({'event': 'motor_tx', 'command': 0xaa, 'hex': '3b032010aa23'})
        text = app.console.get('1.0', 'end')
        self.assertIn('SEND AUX  3b0420102400a8 (This control app', text)
        self.assertIn('STOP', text)
        self.assertNotIn('RECEIVE AUX', text)
        self.assertNotIn('3b0610200140000089', text)
        self.assertIn('Unknown command 0xAA', text)

    def test_transfer_log_includes_local_bridge_packets_and_idle_timeout_only(self):
        app = self.app
        for direction, raw in [('local', '3b03201001cc'), ('client', '3b03201101cb')]:
            app.handle_bridge_event({'event': 'bridge_packet', 'direction': direction,
                                     'hex': raw, 'route': 'Route example', 'interpretation': 'Read position'})
        app.handle_motor_event({'event': 'motor_idle_release', 'seconds': 10})
        text = app.console.get('1.0', 'end')
        self.assertIn('3b03201001cc', text)
        self.assertNotIn('3b03201101cb', text)
        self.assertIn('*** Idle Timeout ***', text)
        bridge = app.bridge_console.get('1.0', 'end')
        self.assertIn('3b03201001cc', bridge)
        self.assertIn('3b03201101cb', bridge)

    def test_csv_copy_preserves_timestamp_and_multiline_notice(self):
        import csv
        import io
        app = self.app
        app.append('Notice, "quoted"\nSecond line')
        rows = list(csv.DictReader(io.StringIO(app.log_csv(app.transfer_log_rows))))
        self.assertEqual(rows[-1]['message'], 'Notice, "quoted"\nSecond line')
        self.assertIn('T', rows[-1]['timestamp_local_iso8601'].replace(' ', 'T'))
        app.handle_bridge_event({'event': 'bridge_status', 'utc': '2026-11-18T19:00:00+00:00', 'message': 'Bridge ON'})
        rows = list(csv.DictReader(io.StringIO(app.log_csv(app.bridge_log_rows))))
        self.assertEqual(rows[-1]['entry_type'], 'NOTICE')
        self.assertIn('[NOTICE]', app.bridge_console.get('1.0', 'end'))

    def test_disconnected_polling_state_does_not_claim_checkbox_is_active(self):
        from unittest.mock import Mock
        app = self.app
        app.motor_heartbeat.set(True)
        app.motor_heartbeat_interval.set('3')
        app.update_controls()
        self.assertIn('Polling stopped', app.direct_polling_status.get())
        self.assertIn('Connect Motors', app.direct_polling_status.get())
        app.motor = Mock()
        app.direct_polling_applied = (True, 1.0, 10)
        app.update_controls()
        self.assertIn('every 1s', app.direct_polling_status.get())
        self.assertIn('10s', app.direct_polling_status.get())
        app.motor = None

    def test_local_polling_control_applies_to_summary_and_rejects_conflict(self):
        from unittest.mock import Mock
        app = self.app
        app.bridge = Mock(local_fault=False)
        app.bridge_is_ready = app.bridge_jog_active = True
        self.assertEqual(app.bridge_local_polling_applied, .4)
        app.bridge_local_polling.set('1')
        app.apply_bridge_local_polling()
        app.bridge.configure_local_polling.assert_called_once_with(1.0)
        self.assertIn('Local-jog feedback: 1s target', app.motor_bridge_polling_text.get())
        app.bridge_local_polling.set('2')
        app.apply_bridge_local_polling()
        self.assertEqual(app.bridge_local_polling_applied, 1)
        self.assertIn('not applied', app.bridge_background_status.get())
        app.bridge = None

    def test_bridge_restart_button_and_timeout_controls(self):
        from unittest.mock import Mock, patch
        app = self.app
        app.update_controls()
        self.assertEqual(str(app.bridge_reset_button['state']), 'disabled')
        app.bridge = Mock(local_fault=True)
        app.bridge_is_ready = True
        app.bridge_jog_active = True
        app.bridge_jog_requested.set(True)
        app.update_controls()
        self.assertEqual(str(app.bridge_reset_button['state']), 'normal')
        self.assertEqual(app.bridge_reset_button['background'], '#b52b2b')
        app.reset_bridge_jog()
        app.bridge.restart_local_jog.assert_called_once()
        self.assertEqual(str(app.bridge_reset_button['state']), 'disabled')
        app.bridge_feedback_timeout.set('5')
        with patch('skyqlink_setup.messagebox.showinfo') as notice:
            app.apply_bridge_feedback_timeout()
        notice.assert_called_once()
        self.assertIn('next time you enable', notice.call_args.args[1])
        app.bridge.configure_local_feedback.assert_called_once_with(5.0)
        self.assertEqual(app.bridge_feedback_applied, 5)
        app.bridge_feedback_timeout.set('nan')
        app.apply_bridge_feedback_timeout()
        self.assertEqual(app.bridge_feedback_applied, 5)
        self.assertIn('not applied', app.bridge_jog_note.get())
        app.bridge = None

    def test_direct_idle_and_keep_alive_locked_for_all_bridge_jog_states(self):
        from unittest.mock import Mock
        app = self.app
        app.idle_release.set('Never')
        app.update_controls()
        self.assertIn('lock out', app.motor_connection_help.get())
        app.bridge = Mock()
        for jogging in (False, True):
            app.bridge_jog_requested.set(jogging)
            app.bridge_jog_ready = jogging
            app.update_controls()
            self.assertEqual(str(app.idle_release_box.cget('state')), 'disabled')
            self.assertEqual(str(app.motor_heartbeat_box.cget('state')), 'disabled')
            self.assertEqual(str(app.motor_heartbeat_box_interval.cget('state')), 'disabled')
            self.assertIn('Not used during bridge', app.motor_connection_help.get())
            self.assertTrue(app.direct_policy_title.instate(['disabled']))
            self.assertTrue(all(w.instate(['disabled']) for w in app.direct_policy_frame.winfo_children()))
        app.bridge = None
        app.update_controls()
        self.assertEqual(app.idle_release.get(), 'Never')
        self.assertEqual(str(app.idle_release_box.cget('state')), 'readonly')
        self.assertFalse(app.direct_policy_title.instate(['disabled']))
        self.assertIn('click Connect Motors to apply', app.motor_connection_help.get())
        app.motor_heartbeat.set(False)
        app.update_controls()
        self.assertEqual(str(app.motor_heartbeat_box_interval.cget('state')), 'normal')

    def test_modern_mode_disables_legacy_operations_and_restores_them(self):
        app = self.app
        app.interface_mode.set('Celestron module')
        app.update_mode_help()
        self.assertEqual(str(app.read_button.cget('state')), 'disabled')
        self.assertEqual(str(app.motor_connect_button.cget('state')), 'normal')
        app.toggle_bridge()
        self.assertIsNone(app.bridge)
        app.interface_mode.set('SkyQLink')
        app.update_mode_help()
        self.assertEqual(str(app.read_button.cget('state')), 'normal')

    def test_profile_recommendation_allows_override_without_changing_active_target(self):
        app = self.app
        app.discovered = [{'ip': '192.0.2.4', 'endpoint_kind': 'modern_module'}]
        app.module_box.configure(values=['Modern module'])
        app.module_box.current(0)
        old_host = app.host.get()
        app.recommend_module_profile()
        self.assertEqual(app.recommended_profile.get(), 'Celestron module')
        self.assertEqual(app.host.get(), old_host)
        app.recommended_profile.set('SkyQLink')
        app.select_module()
        self.assertEqual(app.interface_kind(), 'legacy')
        self.assertEqual(app.host.get(), '192.0.2.4')
        app.discovered[0]['endpoint_kind'] = 'software_proxy'
        app.recommended_profile.set('Celestron module')
        app.select_module()
        self.assertEqual(app.interface_kind(), 'proxy')

    def test_nonlegacy_bridge_settings_and_descriptions_disabled(self):
        app = self.app
        for profile in ('Celestron module', 'Controller proxy (diagnostic)'):
            app.interface_mode.set(profile)
            app.update_controls()
            self.assertEqual(str(app.bridge_dual_box.cget('state')), 'disabled')
            self.assertEqual(str(app.bridge_bind_entry.cget('state')), 'disabled')
            for widget in app.bridge_polling_frame.winfo_children():
                if hasattr(widget, 'instate'):
                    self.assertTrue(widget.instate(['disabled']))
            old = app.bridge_local_polling_applied
            app.bridge_local_polling.set('0.8')
            app.apply_bridge_local_polling()
            self.assertEqual(app.bridge_local_polling_applied, old)
        app.interface_mode.set('SkyQLink')
        app.update_controls()
        self.assertEqual(str(app.bridge_dual_box.cget('state')), 'normal')
        for widget in app.bridge_polling_frame.winfo_children():
            if hasattr(widget, 'instate'):
                self.assertFalse(widget.instate(['disabled']))

    def test_nonlegacy_diagnostics_replaces_bridge_tab_and_icon(self):
        app = self.app
        app.tabs.select(app.bridge_tab)
        for profile in ('Celestron module', 'Controller proxy (diagnostic)'):
            app.interface_mode.set(profile)
            app.update_controls()
            self.assertEqual(app.tabs.tab(app.bridge_tab, 'state'), 'disabled')
            self.assertFalse(app.tabs.tab(app.bridge_tab, 'image'))
            self.assertEqual(app.tabs.select(), str(app.diagnostic_tab))
            self.assertTrue(app.profile_diagnostics.grid_info())
            app.append('Diagnostic example')
            self.assertIn('Diagnostic example', app.diagnostic_console.get('1.0', 'end'))
        app.interface_mode.set('SkyQLink')
        app.update_controls()
        self.assertEqual(app.tabs.tab(app.bridge_tab, 'state'), 'normal')
        self.assertTrue(app.tabs.tab(app.bridge_tab, 'image'))
        self.assertFalse(app.profile_diagnostics.grid_info())

    def test_modern_motor_connect_uses_modern_transport_and_settings_remain_available(self):
        from unittest.mock import Mock
        app = self.app
        app.interface_mode.set('Celestron module')
        app.update_controls()
        self.assertEqual(str(app.motor_connect_button.cget('state')), 'normal')
        self.assertEqual(str(app.motor_settings_button.cget('state')), 'normal')
        self.assertTrue(app.modern_motor_help.grid_info())
        factory = app.motor_factory = Mock()
        app.connect_motors()
        self.assertEqual(factory.call_args.kwargs['interface_mode'], 'modern')
        factory.return_value.start.assert_called_once()
        app.motor = None

    def test_modern_diagnostics_polling_shares_motor_connection_settings(self):
        from unittest.mock import Mock
        app = self.app
        app.interface_mode.set('Celestron module')
        app.update_controls()
        self.assertTrue(app.modern_polling_frame.grid_info())
        self.assertFalse(app.motor_heartbeat_box.grid_info())
        app.motor_heartbeat_interval.set('5')
        app.update_controls()
        self.assertIn('5s', app.direct_polling_status.get())
        factory = app.motor_factory = Mock()
        app.connect_motors()
        self.assertEqual(factory.call_args.kwargs['heartbeat_interval'], 5)
        self.assertTrue(factory.call_args.kwargs['heartbeat_enabled'])
        self.assertTrue(app.modern_polling_toggle.instate(['disabled']))
        self.assertIsNone(app.bridge)
        app.motor = None
        app.interface_mode.set('SkyQLink')
        app.update_controls()
        self.assertTrue(app.motor_heartbeat_box.grid_info())
        self.assertTrue(app.motor_polling_interval_label.grid_info())
        self.assertFalse(app.modern_polling_frame.grid_info())

    def test_extended_settings_disable_unreported_endpoints(self):
        app = self.app
        app.interface_mode.set('Celestron module')
        app.open_motor_settings()
        app.open_extended_motor_settings()
        for widgets in app.extended_widgets[0x10].values():
            self.assertTrue(all(str(w.cget('state')) == 'disabled' for w in widgets))
        app.controller_reads[0x10] = {'endpoint': (app.host.get(), int(app.port.get())), 'values': {'approach': 0, 'cordwrap_enabled': 0, 'cordwrap_position': 0}}
        app.refresh_extended_motor_settings()
        self.assertEqual(str(app.extended_widgets[0x10]['approach'][0].cget('state')), 'readonly')
        self.assertEqual(str(app.extended_widgets[0x10]['cordwrap'][1].cget('state')), 'normal')
        self.assertNotIn('cordwrap', app.extended_widgets[0x11])
        app.host.set('192.0.2.9')
        app.refresh_extended_motor_settings()
        self.assertEqual(str(app.extended_widgets[0x10]['cordwrap'][1].cget('state')), 'disabled')

    def test_bridge_setup_steps_follow_network_and_profile(self):
        app = self.app
        app.preset(True)
        self.assertIn('Infrastructure:', app.bridge_network_step.get())
        self.assertTrue(app.bridge_setup_panel.grid_info())
        app.preset(False)
        self.assertIn('Direct / ad hoc:', app.bridge_network_step.get())
        app.interface_mode.set('Celestron module')
        app.update_controls()
        self.assertFalse(app.bridge_setup_panel.grid_info())
        app.interface_mode.set('SkyQLink')
        app.update_controls()
        self.assertTrue(app.bridge_setup_panel.grid_info())

    def test_bridge_restart_reopens_only_same_idle_target(self):
        from unittest.mock import patch
        app = self.app
        app.bridge_restart_pending = True
        app.bridge_restart_target = (app.host.get(), app.port.get())
        with patch.object(app, 'toggle_bridge') as toggle:
            app.finish_bridge_restart()
            toggle.assert_called_once()
            self.assertTrue(app.bridge_enabled.get())
            self.assertFalse(app.bridge_jog_requested.get())
        app.bridge_restart_pending = True
        app.selection_pending = True
        with patch.object(app, 'toggle_bridge') as toggle:
            app.finish_bridge_restart()
            toggle.assert_not_called()

    def test_pending_profile_locks_tabs_until_apply_or_cancel(self):
        app = self.app
        app.discovered = [{'ip': '192.0.2.74', 'endpoint_kind': 'modern_module'}]
        app.module_box.configure(values=['Modern module'])
        app.module_box.current(0)
        app.recommend_module_profile()
        self.assertEqual(app.use_module_button.cget('background'), '#b3261e')
        self.assertIn('changes pending', app.use_module_button.cget('text'))
        for tab in app.tabs.tabs():
            self.assertEqual(app.tabs.tab(tab, 'state'), 'disabled')
        app.connect_motors()
        self.assertIsNone(app.motor)
        self.assertTrue(app.selection_controls.grid_info())
        app.select_module()
        self.assertFalse(app.selection_pending)
        self.assertEqual(app.use_module_button.cget('background'), '#19733d')
        self.assertEqual(app.use_module_button.cget('text'), 'Module & Profile Selected')
        self.assertEqual(app.tabs.tab(app.motor_tab, 'state'), 'normal')
        self.assertEqual(app.tabs.tab(app.bridge_tab, 'state'), 'disabled')
        app.mark_profile_pending()
        app.cancel_profile_selection()
        self.assertEqual(app.tabs.tab(app.motor_tab, 'state'), 'normal')
        self.assertFalse(app.selection_controls.grid_info())

    def test_queued_events_resume_promptly_without_unbounded_gui_batch(self):
        from unittest.mock import patch
        app = self.app
        for _ in range(500):
            app.events.put({'event': 'test_noop'})
        before = app.events.qsize()
        with patch.object(app, 'after', return_value=app.poll_id) as after:
            app.poll()
        self.assertGreater(app.events.qsize(), 0)
        self.assertLessEqual(before - app.events.qsize(), 64)
        after.assert_called_once_with(1, app.poll)

    def test_modern_diagnostics_places_controls_before_results(self):
        app = self.app
        app.interface_mode.set('Celestron module')
        app.update_controls()
        self.assertEqual(int(app.modern_diagnostic_controls.grid_info()['row']), 0)
        self.assertLess(int(app.modern_diagnostic_controls.grid_info()['row']), int(app.diagnostic_rows.grid_info()['row']))
        self.assertFalse(hasattr(app, 'diagnostic_motor_settings_button'))
        self.assertEqual(str(app.motor_settings_button.cget('state')), 'normal')
        app.interface_mode.set('Controller proxy (diagnostic)')
        app.update_controls()
        self.assertFalse(app.modern_diagnostic_controls.grid_info())

    def test_selecting_proxy_sets_read_only_target(self):
        app = self.app
        app.discovered = [{'ip':'192.0.2.33', 'port':2000, 'endpoint_kind':'software_proxy'}]
        app.module_box.configure(values=['COSMOS software proxy'])
        app.module_box.current(0)
        app.select_module()
        self.assertEqual(app.host.get(), '192.0.2.33')
        self.assertEqual(app.interface_kind(), 'proxy')
        self.assertEqual(str(app.motor_connect_button.cget('state')), 'disabled')
        self.assertEqual(str(app.motor_settings_button.cget('state')), 'disabled')
        app.connect_motors()
        self.assertIsNone(app.motor)
        self.assertIn('diagnostics only', app.status.get())

    def test_bridge_poll_controls_live_on_bridge_and_validate_before_connect(self):
        app = self.app
        groups = [w for w in app.bridge_tab.winfo_children()
                  if w.winfo_class() == 'TLabelframe' and 'motor-position polling' in w.cget('text')]
        self.assertEqual(len(groups), 1)
        app.bridge_heartbeat.set(True)
        app.bridge_monitor.set(True)
        app.bridge_monitor_interval.set('5')
        app.apply_bridge_background_reads()
        self.assertIn('5s sample interval', app.bridge_background_status.get())
        app.bridge_monitor_interval.set('nan')
        app.apply_bridge_background_reads()
        self.assertIn('Not applied', app.bridge_background_status.get())

    def test_bridge_requires_infrastructure_and_shows_firewall_ports(self):
        app = self.app
        app.bridge_enabled.set(True)
        app.toggle_bridge()
        self.assertFalse(app.bridge_enabled.get())
        self.assertIsNone(app.bridge)
        self.assertIn('Infrastructure', app.bridge_status.get())
        for text in ('TCP 2000', '3000', '55555', 'Local Network', 'does not prove that your firewall'):
            self.assertIn(text, app.bridge_firewall_label.cget('text'))

    def test_connection_network_inventory_preserves_telescope_address(self):
        app = self.app
        rows = [{'interface': 'en0', 'name': 'Ethernet', 'ip': '192.168.1.20',
                 'netmask': '255.255.255.0', 'state': 'active'}]
        app.network_provider = lambda: rows
        app.interface_rows = rows
        before = app.host.get()
        app.open_connection_networks()
        table = app.connection_network_table
        self.assertEqual(table.item(table.get_children()[0], 'values'),
                         ('Ethernet', '192.168.1.20', '192.168.1.0/24', 'active'))
        self.assertEqual(app.host.get(), before)
        app.connection_network_window.destroy()
        app.show_network_interfaces()  # Refresh is safe after the dialog closes.

    def test_computer_ips_interfaces_and_bound_outbound_ports_are_visible(self):
        app = self.app
        app.network_provider = lambda: [
            {'interface':'en0', 'name':'Ethernet', 'ip':'192.168.1.20', 'state':'active'},
            {'interface':'en1', 'name':'Wi-Fi', 'ip':'1.2.3.10', 'state':'active'}]
        app.refresh_network_interfaces()
        self.drain_ui()
        rows = app.interface_table.get_children()
        self.assertEqual(len(rows), 2)
        self.assertEqual(app.interface_table.item(rows[0], 'values')[0:3], ('en0', 'Ethernet', '192.168.1.20'))
        app.interface_table.selection_set(rows[0])
        app.select_bridge_interface()
        self.assertEqual(app.bridge_bind.get(), '192.168.1.20')
        app.handle_bridge_event({'event':'bridge_ready', 'bind_host':'192.168.1.20',
                                 'listen_port':2000, 'management_port':3000,
                                 'upstream_local':('1.2.3.10', 49123), 'message':'Ready'})
        self.assertIn('192.168.1.20', app.bridge_endpoint.get())
        self.assertIn('1.2.3.10:49123', app.bridge_endpoint.get())
        self.assertIn('2000', app.interface_table.item(app.interface_table.get_children()[0], 'values')[-1])
        self.assertIn('to telescope', app.interface_table.item(app.interface_table.get_children()[1], 'values')[-1])


class ReleaseGuidanceTests(unittest.TestCase):
    setUp = GuiTests.setUp
    tearDown = GuiTests.tearDown

    def test_direct_mode_explains_disabled_switch_and_two_interface_unlock(self):
        app = self.app
        app.preset(False)
        self.assertEqual(str(app.bridge_switch.cget('state')), 'disabled')
        self.assertIn('Direct/ad hoc requires Two Interface Mode', app.bridge_requirement.get())
        app.bridge_enabled.set(True)
        app.toggle_bridge()
        self.assertIsNone(app.bridge)
        self.assertFalse(app.bridge_enabled.get())
        self.assertIn('second adapter', app.bridge_status.get())
        app.bridge_dual.set(True)
        app.update_controls()
        self.assertEqual(str(app.bridge_switch.cget('state')), 'normal')
        self.assertIn('astronomy app', app.bridge_requirement.get())
        app.bridge_dual.set(False)
        app.preset(True)
        self.assertEqual(str(app.bridge_switch.cget('state')), 'normal')
        self.assertNotIn('disabled', app.bridge_requirement.get())

    def test_two_interfaces_require_explicit_shared_network_ip(self):
        app = self.app
        app.bridge_dual.set(True)
        app.update_controls()
        self.assertIn('control-device', app.bridge_ip_help.get())
        self.assertIn('do not leave this field blank', app.bridge_interface_help.get())
        self.assertIn('network used by your phone, tablet or other control computer', app.bridge_interface_help.get())
        app.bridge_enabled.set(True)
        app.toggle_bridge()
        self.assertIsNone(app.bridge)
        self.assertFalse(app.bridge_enabled.get())
        self.assertIn('Select that adapter in Local System Network Interfaces', app.bridge_status.get())

    def test_selecting_discovered_direct_module_keeps_direct_mode(self):
        app = self.app
        app.discovered = [{'ip': '1.2.3.4', 'port': 2000}]
        app.module_box.configure(values=['Direct telescope'])
        app.module_box.current(0)
        app.select_module()
        self.assertEqual(app.connection_mode.get(), 'direct')
        self.assertEqual(app.host.get(), '1.2.3.4')
        self.assertEqual(app.last_infrastructure_host, '192.168.1.42')

    def test_infrastructure_discovery_rejects_direct_address(self):
        app = self.app
        app.connection_mode.set('infrastructure')
        app.host.set('1.2.3.4')
        app.scanner = lambda **kwargs: self.fail('Discovery must not start')
        app.scan_lan()
        self.assertFalse(app.busy)
        self.assertIn('direct-connect address', app.status.get())

if __name__ == '__main__':
    unittest.main()
