import tempfile
from pathlib import Path
import unittest
from telescope_calibration import from_report, save_config, load_config, estimate_seconds, relative_target, identify_profile, profile_label


class CalibrationTests(unittest.TestCase):
    def test_keymap_has_no_defaults_and_rejects_conflicts(self):
        from telescope_calibration import profile_keymap, KEYMAP_ACTIONS
        self.assertEqual(profile_keymap({}), {})
        self.assertEqual(profile_keymap({'keymap': {}}), {})
        mapping = dict(zip(KEYMAP_ACTIONS, 'abcdefg', strict=True))
        self.assertEqual(profile_keymap({'keymap': mapping}), mapping)
        for invalid in ({'stop': 'k'}, {**mapping, 'connect': 'a'}, {**mapping, 'stop': 'Escape'}, {**mapping, 'stop': 4}):
            with self.assertRaises(ValueError):
                profile_keymap({'keymap': invalid})

    def test_mac_identity_survives_address_change_and_rejects_other_adapter(self):
        config = from_report({}, '192.0.2.1')
        report = {'host': '192.0.2.1', 'port': 2000, 'rows': [
            {'endpoint': 'get mac', 'status': 'REPLY', 'reply': 'Mac Addr=02:00:00:00:00:bb'}]}
        identify_profile(config, report)
        report['host'] = '192.0.2.2'
        identify_profile(config, report)
        self.assertEqual(config['telescope']['host'], '192.0.2.2')
        self.assertIn('02:00:00:00:00:BB', profile_label(config))
        report['rows'][0]['reply'] = 'Mac Addr=02:00:00:00:00:cc'
        with self.assertRaises(ValueError):
            identify_profile(config, report)
        self.assertEqual(config['telescope']['adapter_mac'], '02:00:00:00:00:BB')
        report['saved_report'] = True
        with self.assertRaises(ValueError):
            identify_profile(config, report)

    def test_direction_specific_rates_and_endpoint_guard(self):
        config = from_report({'results': [
            {'axis': 16, 'rate': 7, 'direction': 1, 'elapsed_seconds': 1,
             'measured_degrees': 1, 'stationary_verified': True},
            {'axis': 16, 'rate': 7, 'direction': -1, 'elapsed_seconds': 1,
             'measured_degrees': -.5, 'stationary_verified': True}]}, '192.0.2.1')
        self.assertEqual(estimate_seconds(config, 16, 7, .5, '192.0.2.1'), .5)
        self.assertEqual(estimate_seconds(config, 16, 7, -.5, '192.0.2.1'), 1)
        for degrees, host in ((3, '192.0.2.1'), (.5, '192.0.2.2'), (0, '192.0.2.1')):
            with self.assertRaises(ValueError):
                estimate_seconds(config, 16, 7, degrees, host)
        self.assertFalse(config['encoder']['independently_measured_physical_scale'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'calibration.json'
            save_config(config, path)
            self.assertEqual(load_config(path), config)
            save_config(config, path)
            self.assertTrue(path.with_suffix('.json.previous').exists())

    def test_relative_encoder_wrap_and_no_invalid_scale(self):
        self.assertEqual(relative_target(0, -90), 3 * (1 << 22))
        self.assertEqual(relative_target(3 * (1 << 22), 90), 0)
        with self.assertRaises(ValueError):
            relative_target(0, float('nan'))


if __name__ == '__main__':
    unittest.main()
