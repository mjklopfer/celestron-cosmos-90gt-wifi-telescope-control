"""Tk desktop checks using a fake backend; no hardware writes or network connections."""
import time
import threading
import tkinter as tk
import unittest
from skyqlink_setup import SetupApp


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.motor_calls = []
        self.motors = []
        owner = self
        class FakeMotor:
            def __init__(self, host, port, callback):
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
                                                                  'module_type': 'Celestron AUX Wi-Fi bridge', 'verified': True}]})

        self.app.last_infrastructure_host = '192.168.1.42'

    def tearDown(self):
        self.app.busy = False
        self.app.motor = None
        self.app.close()

    def drain_ui(self):
        self.root.after(150, self.root.quit)
        self.root.mainloop()

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
        self.assertEqual(self.app.scan_indicator.cget('foreground'), '#b22b2b')
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
        self.assertIn('verified module', app.status.get())
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

    def test_diagnostics_present_replies_and_partial_verification(self):
        def diagnostic(host, port, callback):
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
        self.assertIn('COSMOS 90GT', self.root.title())
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
            {'ip': '192.168.1.42', 'port': 2000, 'module_type': 'SkyQLink RN-171',
             'verified': True, 'motors_verified': False,
             'verification_note': 'SkyQLink adapter identified; motors not responding'}]}
        self.app.scan_lan()
        self.finish_worker()
        self.assertEqual(self.app.module_box.current(), 0)
        self.assertNotIn('motors not responding', self.app.module_box.get())
        self.assertIn('motors not responding', self.app.console.get('1.0', 'end'))
        self.assertEqual(self.app.host.get(), '192.168.1.42')
        self.assertFalse(self.app.motor_ready)

    def test_requested_tab_order_and_infrastructure_reprovisioning_notice(self):
        self.assertEqual([self.app.tabs.tab(t, 'text') for t in self.app.tabs.tabs()],
                         ['Motor control', 'Diagnostics', 'Bridge', 'Wi-Fi provisioning'])
        self.app.preset(True)
        self.app.show_provisioned_network({'before': {'get wlan': 'SSID=ExistingNetwork\r\nJoin=1\r\nAuth=WPA2',
                                                    'get ip': 'DHCP=ON'}})
        self.assertIn('ExistingNetwork', self.app.provision_notice.get())
        self.assertIn('no ad hoc switch or factory reset', self.app.provision_notice.get())
        self.assertEqual(str(self.app.upload_button['state']), 'normal')

    def test_discovery_does_not_require_an_ip_address(self):
        self.app.host.set('')
        self.app.scan_lan()
        self.finish_worker()
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
        def factory(host, port, callback):
            attempts.append(host)
            return FirstFailure(callback) if len(attempts) == 1 else original(host, port, callback)
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
            def __init__(self, host, port, callback):
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
        app.preset(True)
        app.bridge_enabled.set(True)
        app.toggle_bridge()
        self.drain_ui()
        for tab in (app.motor_tab, app.diagnostic_tab, app.provision_tab):
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
        for tab in (app.motor_tab, app.diagnostic_tab, app.provision_tab):
            self.assertEqual(app.tabs.tab(tab, 'state'), 'normal')

    def test_bridge_requires_infrastructure_and_shows_firewall_ports(self):
        app = self.app
        app.bridge_enabled.set(True)
        app.toggle_bridge()
        self.assertFalse(app.bridge_enabled.get())
        self.assertIsNone(app.bridge)
        self.assertIn('Infrastructure', app.bridge_status.get())
        for text in ('TCP 2000', '3000', '55555', 'Local Network', 'does not verify firewall'):
            self.assertIn(text, app.bridge_firewall_label.cget('text'))

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

    def test_two_interfaces_require_explicit_shared_network_ip(self):
        app = self.app
        app.bridge_dual.set(True)
        app.update_controls()
        self.assertIn('required', app.bridge_ip_help.get())
        self.assertIn('shared', app.bridge_interface_help.get())
        app.bridge_enabled.set(True)
        app.toggle_bridge()
        self.assertIsNone(app.bridge)
        self.assertFalse(app.bridge_enabled.get())
        self.assertIn('Select a row', app.bridge_status.get())

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
