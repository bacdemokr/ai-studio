"""First installation must work before the Gateway exists; live edits need RPC."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import agent_runtime as runtime
import ops_runtime as ops


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.override = patch.object(runtime, 'root', return_value=self.root)
        self.override.start()
        self.addCleanup(self.override.stop)

    def test_host_setup_without_running_gateway_and_repeat_preserves_config(self):
        manifest = self.root / 'package/node_modules/openclaw/package.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'version': runtime.VERSION}))
        from research_search import PACKAGE, VERSION
        plugin=self.root/'package/node_modules'/PACKAGE/'package.json'
        plugin.parent.mkdir(parents=True)
        plugin.write_text(json.dumps({'version':VERSION}))
        def cli(*args, **kwargs):
            self.assertEqual(args, ('config', 'validate'))
            return 'valid'
        with patch.object(ops.c, 'initialize'), patch.object(ops, 'install_node'), \
             patch.object(runtime, 'cli', side_effect=cli), \
             patch.object(runtime, 'gateway_config_patch', side_effect=AssertionError('No Gateway before start')):
            ops.setup()
            config = json.loads(runtime.config_path().read_text())
            self.assertIn('bac-host', config['agents']['entries'])
            config['agents']['entries']['bac-host']['name'] = 'Existing host'
            config['agents']['entries']['bac-existing'] = {'name': 'Keep me'}
            expected = json.loads(json.dumps(config))
            config.pop('skills')  # Upgrade a pre-fix installation as well.
            runtime.save_config(config)
            ops.setup()
            self.assertEqual(json.loads(runtime.config_path().read_text()), expected)

    def test_existing_radar_disables_unrelated_maintenance_without_changing_timer(self):
        config = runtime.initial_config()
        config.pop('skills')  # Existing installation with native auto defaults.
        agent = 'bac-'+'a'*24
        config['agents']['entries'][agent] = {'skills': ['bac-radar'], 'heartbeat': {'every': '20s'}}
        runtime.save_config(config)
        with patch.object(runtime, 'gateway_config_patch') as apply:
            self.assertTrue(runtime.set_radar_heartbeat(agent, True))
            apply.assert_called_once_with({'skills': {'workshop': {'autonomous': {'mode': 'off'}}}}, [])
        config['skills'] = {'workshop': {'autonomous': {'mode': 'off'}}}
        runtime.save_config(config)
        with patch.object(runtime, 'gateway_config_patch') as apply:
            self.assertTrue(runtime.set_radar_heartbeat(agent, True))
            apply.assert_not_called()

    def test_bootstrap_cannot_register_a_personal_or_protected_agent(self):
        runtime.save_config(runtime.initial_config())
        profile = {'name': 'Test', 'persona': 'guide', 'skills': ['documents']}
        for agent, overrides in [('bac-'+'a'*24, {}), ('bac-host', {'protection': 'openshell'})]:
            with self.subTest(agent=agent), self.assertRaises(ValueError):
                runtime.register(agent, self.root/'workspace', {**profile, **overrides}, bootstrap=True)
        self.assertFalse((self.root/'workspace').exists())
        self.assertEqual(json.loads(runtime.config_path().read_text())['agents']['entries'], {})

    def test_live_registration_failure_never_falls_back_to_disk(self):
        runtime.save_config(runtime.initial_config())
        before = runtime.config_path().read_bytes()
        agent = 'bac-'+'a'*24
        runtime._expected_identity.pop(agent, None)
        with patch.object(runtime, 'cli', side_effect=RuntimeError('Gateway unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'could not confirm'):
                runtime.register(agent, self.root/'workspace',
                                 {'name': 'Test', 'persona': 'guide', 'skills': ['documents']})
        self.assertEqual(runtime.config_path().read_bytes(), before)
        self.assertNotIn(agent, runtime._expected_identity)
        self.assertTrue((self.root/'workspace/.bac-prepared-only').exists())


if __name__ == '__main__':unittest.main()
