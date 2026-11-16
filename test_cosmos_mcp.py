import time
import unittest
from unittest.mock import patch
try:
    import cosmos_mcp as api
except ImportError:
    api = None


@unittest.skipIf(api is None, 'Optional MCP extra is not installed')
class McpTests(unittest.TestCase):
    def test_write_and_movement_require_explicit_intent(self):
        with self.assertRaises(ValueError):
            api.motor_jog('Azimuth', 1, 6, .5)
        with self.assertRaises(ValueError):
            api.controller_settings('Azimuth', encoder_degrees=10)
        with self.assertRaises(ValueError):
            api.set_wifly_time(enable=1)
        with self.assertRaises(ValueError):
            api.run_diagnostics(deep=True)

    def test_cancellation_preserves_job_result_and_blocks_overlap(self):
        service = api.ControlService()
        def operation(cancel):
            cancel.wait(2)
            return {'aborted': cancel.is_set(), 'rows': ['retained']}
        with patch.object(api, 'service', service):
            job = service.start_job('diagnostics', operation, True)
            with self.assertRaises(RuntimeError):
                api.motor_connect()
            api.abort_diagnostics(job['job_id'])
            deadline = time.monotonic() + 2
            while api.job_status(job['job_id'])['status'] == 'running' and time.monotonic() < deadline:
                time.sleep(.01)
            result = api.job_status(job['job_id'])
            self.assertEqual(result['status'], 'aborted')
            self.assertEqual(result['result']['rows'], ['retained'])


if __name__ == '__main__':
    unittest.main()
