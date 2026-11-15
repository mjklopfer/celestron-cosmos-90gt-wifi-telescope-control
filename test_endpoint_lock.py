"""Regression checks for endpoint lock. No real telescope is connected."""
import unittest
from endpoint_lock import EndpointLease, EndpointBusy


class EndpointLockTests(unittest.TestCase):
    def test_same_endpoint_excluded_and_released_on_error(self):
        with self.assertRaisesRegex(ValueError, 'operation failed'):
            with EndpointLease('192.0.2.17', 2000):
                with self.assertRaises(EndpointBusy):
                    with EndpointLease('192.0.2.17', 2000):
                        self.fail('Acquired occupied endpoint')
                with EndpointLease('192.0.2.17', 2001):
                    pass
                raise ValueError('operation failed')
        with EndpointLease('192.0.2.17', 2000):
            pass
