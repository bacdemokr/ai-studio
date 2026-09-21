import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import runtime_preflight as preflight

class PreflightTests(unittest.TestCase):
    def collect(self, docker='28.1.0', plugin_status='loaded', gateway_error=False):
        def command(args, **kwargs):
            if args[0] == 'docker':
                if docker is None:
                    raise PermissionError('secret must not leak')
                return type('Result', (), {'stdout': docker})()
            return type('Result', (), {'stdout': 'No sandboxes found.'})()
        with patch('runtime_preflight.platform.system', return_value='Linux'), \
             patch('runtime_preflight.common.systemd_available', return_value=True), \
             patch('runtime_preflight.common.read_json', return_value={'version':preflight.runtime.VERSION}), \
             patch('runtime_preflight.runtime.cli', return_value=json.dumps({'plugins':[{'id':'openshell','enabled':True,'status':plugin_status}]})), \
             patch('runtime_preflight.runtime.gateway', side_effect=RuntimeError('private detail') if gateway_error else None), \
             patch('runtime_preflight.subprocess.run', side_effect=command), \
             patch('runtime_preflight.shutil.which', return_value='/usr/bin/ssh'), \
             patch('agent_policy.configured', return_value=True), \
             patch('agent_policy.plugin_config', return_value={'config':{'command':'openshell'}}):
            return preflight.collect(protected=True)

    def test_infrastructure_pass_never_claims_live_protected_success(self):
        report=self.collect()
        self.assertTrue(report['infrastructurePassed'])
        self.assertFalse(report['liveProtectedRunVerified'])
        self.assertEqual(len(report['checks']),6)

    def test_old_docker_permission_plugin_and_gateway_failures(self):
        for args in [{'docker':'27.4.0'}, {'docker':None}, {'plugin_status':'error'}, {'gateway_error':True}]:
            report=self.collect(**args)
            self.assertFalse(report['infrastructurePassed'])
            self.assertNotIn('secret',json.dumps(report))
            self.assertNotIn('private detail',json.dumps(report))
            for check in report['checks']:
                if not check['passed']:self.assertTrue(check['remedy'])

    def test_failed_report_exits_unsuccessfully(self):
        with patch('runtime_preflight.collect', return_value={'infrastructurePassed':False}), redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):preflight.run(True)
