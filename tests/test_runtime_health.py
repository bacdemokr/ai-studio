"""Local gateway health transitions and transport errors; no live model calls."""
import sys
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from runtime_health import RuntimeHealth
import agent_runtime as rt
from studio import Studio
from test_studio import Adapter


class RuntimeHealthTests(unittest.TestCase):
    def setUp(self):
        self.health = RuntimeHealth()

    def observe(self, probe, now, model=True):
        return self.health.observe({'gatewayProbe':probe, 'model':model}, now)

    def test_single_delay_is_quiet_repeated_delay_is_slow_and_recovers(self):
        self.assertTrue(self.observe('ok', 0)['ready'])
        self.assertEqual(self.observe('timeout', 10)['gatewayState'], 'ready')
        slow = self.observe('timeout', 20)
        self.assertEqual(slow['gatewayState'], 'slow')
        self.assertTrue(slow['ready'])
        self.assertEqual(self.observe('ok', 25)['gatewayState'], 'ready')
        self.assertEqual(self.observe('timeout', 28)['gatewayState'], 'ready')

    def test_timeout_cannot_keep_enabling_jobs_indefinitely(self):
        self.observe('ok', 0)
        self.observe('timeout', 10)
        self.observe('timeout', 20)
        self.assertFalse(self.observe('timeout', 30)['ready'])
        result = self.observe('timeout', 40)
        self.assertEqual(result['gatewayState'], 'unavailable')
        self.assertFalse(result['gateway'])

    def test_cold_start_timeout_never_claims_ready(self):
        for now in (0, 10, 20):
            state = self.observe('timeout', now)
            self.assertEqual(state['gatewayState'], 'slow')
            self.assertFalse(state['ready'])
        self.assertEqual(self.observe('timeout', 30)['gatewayState'], 'unavailable')

    def test_hard_failure_has_no_grace_or_timeout_resurrection(self):
        self.observe('ok', 0)
        self.assertEqual(self.observe('unavailable', 1)['gatewayState'], 'unavailable')
        self.assertFalse(self.observe('timeout', 2)['ready'])
        self.assertTrue(self.observe('ok', 3)['ready'])

    def test_model_and_gateway_states_stay_independent(self):
        good = self.observe('ok', 0, False)
        self.assertTrue(good['gateway'])
        self.assertFalse(good['ready'])
        self.assertFalse(self.observe('timeout', 5, False)['ready'])

    def test_stale_success_is_not_hidden_and_legacy_adapter_is_preserved(self):
        self.observe('ok', 0)
        self.assertEqual(self.observe('timeout', 100)['gatewayState'], 'slow')
        self.assertFalse(self.observe('timeout', 110)['ready'])
        self.assertEqual(self.health.observe({'ready': True}, 120), {'ready':True})

    def test_transport_distinguishes_direct_wrapped_timeouts_and_refusal(self):
        for error, reason in ((TimeoutError(), 'timeout'),
                              (urllib.error.URLError(TimeoutError()), 'timeout'),
                              (urllib.error.URLError(ConnectionRefusedError()), 'unavailable'),
                              (urllib.error.HTTPError('http://localhost', 401, 'unauthorized', {}, None), 'unavailable')):
            with self.subTest(reason=reason), patch.object(rt.c, 'read_json', return_value={'gateway':{'auth':{'token':'fixture'}}}), patch.object(rt.urllib.request, 'build_opener') as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(rt.GatewayError) as caught:
                    rt.gateway('/v1/models', timeout=2)
                self.assertEqual(caught.exception.reason, reason)

    def test_retries_share_cached_observation_and_do_not_count_as_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Studio(Path(folder), Adapter(), start_worker=False)
            with patch('studio.time.monotonic', return_value=100), patch.object(app.adapter, 'status', return_value={'gatewayProbe':'ok', 'model':True}) as probe:
                app.runtime_status()
                app.runtime_status(retry=True)
                probe.assert_called_once()
            with patch('studio.time.monotonic', return_value=103), patch.object(app.adapter, 'status', return_value={'gatewayProbe':'timeout', 'model':True}) as probe:
                self.assertEqual(app.runtime_status(retry=True)['gatewayState'], 'ready')
                for _ in range(5):app.runtime_status(retry=True)
                probe.assert_called_once()
                self.assertEqual(app.runtime_health.failures, 1)
            with patch('studio.time.monotonic', return_value=106), patch.object(app.adapter, 'status', return_value={'gatewayProbe':'timeout', 'model':True}):
                self.assertEqual(app.runtime_status(retry=True)['gatewayState'], 'slow')


if __name__ == '__main__':unittest.main()
