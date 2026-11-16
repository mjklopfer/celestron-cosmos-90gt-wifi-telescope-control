"""Clock comparison and conservative reboot evidence; no telescope I/O."""
import unittest
from time_settings import compare_clock, UptimeEvidence
from diagnostics import clock_summary


class ClockTests(unittest.TestCase):
    def test_utc_comparison_ignores_display_zone(self):
        r = compare_clock({'show t t': 'Time=16:00:00\nRTC=1794870000\nZone=7'}, 1794870002)
        self.assertEqual(r['Difference seconds (WiFly minus computer)'], -2)
        self.assertIn('behind', r['Comparison'])

    def test_unset_and_missing_date_do_not_invent_delta(self):
        for raw in ('Time NOT SET\nRTC=1794870000', 'Time=16:00:00', 'RTC=123'):
            r = compare_clock({'show t t': raw}, 1794870002)
            self.assertNotIn('Difference seconds (WiFly minus computer)', r)

    def test_day_threshold_and_bad_calendar(self):
        for delta in (-86401, 86401):
            r = compare_clock({'show t t': f'Time=16:00:00\nRTC={1794870000+delta}'}, 1794870000)
            self.assertIn('greater than 1 day', r['Comparison'])
        r = compare_clock({'show t t': 'Time=16:00:00\nRTC=9999999999999999999999999'}, 1794870000)
        self.assertNotIn('Difference seconds (WiFly minus computer)', r)

    def test_summary_aliases_and_unset_priority(self):
        r = clock_summary({'get time': 'ENA=1\nADDR=192.0.2.1:123\nZONE=7', 'show time': 'Time=01:00:00', 'show t t': 'Time NOT SET\nRTC=123'})
        self.assertEqual(r['Status'], 'Unset')
        self.assertEqual(r['Calendar UTC'], 'Not reported')
        self.assertEqual(r['Time sync enable'], '1')
        self.assertEqual(r['Zone setting (raw)'], '7')

    def test_uptime_is_identity_scoped_and_does_not_guess_rollover(self):
        monitor = UptimeEvidence()
        mac = '00:01:02:03:04:05'
        self.assertFalse(monitor.observe(mac, {'Uptime': '4294967295 s'}, 1)['warning'])
        self.assertTrue(monitor.observe(mac, {'Uptime': '1 s'}, 3)['warning'])
        self.assertFalse(monitor.observe('00:01:02:03:04:06', {'Uptime': '0 s'}, 4)['warning'])
        self.assertFalse(monitor.observe(mac, {'Uptime': '2 s'}, 4)['warning'])
        self.assertFalse(monitor.observe('', {'Uptime': '0 s'}, 5)['warning'])

    def test_restart_counter_change_warns_even_with_increased_uptime(self):
        monitor = UptimeEvidence()
        monitor.observe('00:01:02:03:04:05', {'Uptime': '100', 'Restarts': '1'}, 1)
        self.assertTrue(monitor.observe('00:01:02:03:04:05', {'Uptime': '200', 'Restarts': '2'}, 2)['warning'])
