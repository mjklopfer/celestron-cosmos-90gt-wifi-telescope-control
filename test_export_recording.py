import csv
import json
import tempfile
import unittest
from pathlib import Path
from export_recording import export_recording


class ExportTests(unittest.TestCase):
    def test_scopes_timestamps_raw_data_and_gaps(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'events.jsonl'
            events = [
                {'event': 'bridge_packet', 'utc': '2026-11-18T08:00:00+00:00', 'monotonic': 100.25, 'direction': 'client', 'hex': '3b03201001cc'},
                {'event': 'bridge_values', 'utc': '2026-11-18T08:00:01+00:00', 'monotonic': 101.25, 'axis': 16, 'encoder': 123, 'angle': .002},
                {'event': 'bridge_log_overflow', 'message': 'two events omitted, "gap"'},
            ]
            source.write_text(''.join(json.dumps(e) + '\n' for e in events), encoding='utf-8')
            original = source.read_bytes()
            for scope, expected in (('packets', ['packet', 'status']), ('positions', ['position', 'status']), ('both', ['packet', 'position', 'status'])):
                output = root / 'out.json'
                metadata = export_recording(source, output, scope, 'json')
                parsed = json.loads(output.read_text(encoding='utf-8'))
                self.assertEqual([r['record_type'] for r in parsed['records']], expected)
                self.assertEqual(metadata['records'], len(expected))
            self.assertEqual(parsed['records'][0]['monotonic_seconds'], 100.25)
            self.assertIn('Read position', parsed['records'][0]['interpretation'])
            output = root / 'out.csv'
            export_recording(source, output)
            with output.open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]['record_type'], 'export_metadata')
            self.assertEqual(rows[2]['encoder_counts'], '123')
            self.assertEqual(rows[3]['message'], events[2]['message'])
            self.assertEqual(source.read_bytes(), original)
            with self.assertRaises(ValueError):
                export_recording(source, source)

    def test_partial_active_tail_warns_but_bad_complete_record_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            source, dest = Path(folder) / 'events.jsonl', Path(folder) / 'out.json'
            source.write_bytes(b'{"event":"bridge_status"}\n{"event":')
            report = export_recording(source, dest, format='json')
            self.assertEqual(report['records'], 1)
            self.assertTrue(report['warnings'])
            source.write_bytes(b'broken\n')
            with self.assertRaises(ValueError):
                export_recording(source, dest)


    def test_multisession_range_and_explicit_time_designators(self):
        from export_recording import recording_bounds
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, stamp, count in (('session-b', '2026-11-18T08:02:00+00:00', 20), ('session-a', '2026-11-18T08:01:00+00:00', 10)):
                (root / name).mkdir()
                (root / name / 'events.jsonl').write_text(json.dumps({'event': 'bridge_values', 'utc': stamp, 'axis': 16, 'encoder': count}) + '\n')
            bounds = recording_bounds(root)
            self.assertEqual(bounds['sessions'], 2)
            self.assertEqual(bounds['first'], '2026-11-18T08:01:00+00:00')
            output = root / 'export.json'
            export_recording(root, output, 'positions', 'json', start='2026-11-18T08:02:00+00:00', end='2026-11-18T08:03:00+00:00', time_format='unix')
            result = json.loads(output.read_text())
            self.assertEqual(len(result['records']), 1)
            self.assertEqual(result['records'][0]['encoder_counts'], 20)
            self.assertIsInstance(result['records'][0]['timestamp_unix_seconds_utc'], float)
            self.assertEqual(result['metadata']['timestamp_field'], 'timestamp_unix_seconds_utc')
            export_recording(root, output, 'positions', 'json', time_format='local')
            result = json.loads(output.read_text())
            self.assertEqual([r['encoder_counts'] for r in result['records']], [10, 20])
            self.assertIn('timestamp_local_iso8601', result['records'][0])
            self.assertEqual(len(result['metadata']['source_snapshots']), 2)
            with self.assertRaises(ValueError):
                export_recording(root, output, start='2026-11-18T09:00:00Z', end='2026-11-18T08:00:00Z')


class ArchiveTests(unittest.TestCase):
    def test_zip_sessions_and_json_export_round_trip(self):
        from log_archive import save_logs_zip
        from export_recording import recording_bounds
        import zipfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logs = root / 'logs'
            for index in range(3):
                session = logs / f'session{index}'
                session.mkdir(parents=True)
                event = {'utc': f'2026-11-18T08:00:0{index}+00:00', 'event': 'bridge_status', 'message': 'Notice'}
                (session / 'events.jsonl').write_text(json.dumps(event) + '\n')
                (session / 'report.json').write_text('{"summary": true}')
            archive = root / 'saved.zip'
            self.assertEqual(save_logs_zip(logs, archive), 6)
            with zipfile.ZipFile(archive) as z:
                self.assertIn('logs/session2/events.jsonl', z.namelist())
            self.assertEqual(recording_bounds(archive)['sessions'], 3)
            exported = root / 'export.json'
            self.assertEqual(export_recording(archive, exported, format='json')['records'], 3)
            self.assertEqual(export_recording(exported, root / 'again.csv')['records'], 3)
            with self.assertRaises(ValueError):
                save_logs_zip(logs, logs / 'recursive.zip')

    def test_unsafe_zip_path_rejected_without_extracting(self):
        from log_archive import archive_logs
        import zipfile
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('../events.jsonl', '{}\n')
            with self.assertRaises(ValueError):
                archive_logs(archive)
