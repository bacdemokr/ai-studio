"""Packaging regressions; live Docker/OpenShell acceptance is a separate smoke test."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import agent_runtime as runtime
import container_runtime as container
import container_release as release
import container_remove as resources
import ops_common as common
import runtime_settings as settings


class ContainerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {
            'BAC_DATA_DIR': str(self.root/'data'), 'HOME': str(self.root/'home'),
            'XDG_CONFIG_HOME': str(self.root/'home/.config'), 'BAC_CONTAINER': '1',
            'BAC_OPENCLAW_PORT': '28689', 'BAC_OPENSHELL_PORT': '28680',
            'BAC_OPENSHELL_HEALTH_PORT': '28681', 'PORT': '8080'})
        self.env.start()
        self.paths = patch.multiple(container, IMAGE_RUNTIME=self.root/'image',
                                    GATEWAY_STATE=self.root/'gateway', CLIENT_CERTS=self.root/'client')
        self.paths.start()

    def tearDown(self):
        self.paths.stop()
        self.env.stop()
        self.temp.cleanup()

    def fake_certgen(self, command, **_kwargs):
        tls = container.GATEWAY_STATE/'tls'
        for name in ('ca.crt', 'ca.key', 'client/tls.crt', 'client/tls.key', 'server/tls.crt', 'server/tls.key'):
            file = tls/name
            file.parent.mkdir(parents=True, exist_ok=True)
            if not file.exists():
                file.write_text('original-cert')
        return subprocess.CompletedProcess(command, 0)

    def test_repeated_init_preserves_agents_and_credentials(self):
        with patch.object(container.os, 'chown'), patch.object(container.subprocess, 'run', side_effect=self.fake_certgen):
            container.init()
            saved = common.home()/'saved-agent'
            saved.write_text('keep')
            container.init()
        self.assertEqual(saved.read_text(), 'keep')
        self.assertEqual((container.CLIENT_CERTS/'tls.key').read_text(), 'original-cert')
        config = (container.GATEWAY_STATE/'gateway.toml').read_text()
        self.assertIn('127.0.0.1:28680', config)
        self.assertIn('[openshell.gateway.mtls_auth]\nenabled = true', config)
        self.assertNotIn(':latest', config)
        self.assertNotIn('disable_tls = true', config)

    def test_init_refuses_foreign_gateway_directory(self):
        container.GATEWAY_STATE.mkdir()
        sentinel = container.GATEWAY_STATE/'foreign.db'
        sentinel.write_text('keep')
        with patch.object(container.os, 'chown'), patch.object(container.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'unmanaged'):
                container.init()
            run.assert_not_called()
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_initialization_accepts_recorded_image_history_and_preserves_it(self):
        resources.record_images({'images':{'gateway':'gateway:old'}},'bac-studio:old',container.GATEWAY_STATE)
        with patch.object(container.os,'chown'), patch.object(container.subprocess,'run',side_effect=self.fake_certgen):
            container.init()
        self.assertEqual(resources.image_history(container.GATEWAY_STATE),{'gateway:old','bac-studio:old'})

    def test_runtime_links_do_not_replace_host_install(self):
        runtime.root().mkdir(parents=True)
        (runtime.root()/'package').mkdir()
        sentinel = runtime.root()/'package/keep'
        sentinel.write_text('host')
        with self.assertRaisesRegex(RuntimeError, 'host-installed'):
            container.link_runtime('package')
        self.assertEqual(sentinel.read_text(), 'host')
        container.link_runtime('node')
        container.link_runtime('node')
        self.assertEqual((runtime.root()/'node').readlink(), container.IMAGE_RUNTIME/'node')

    def test_duplicate_ports_rejected_before_initialization(self):
        with patch.dict(os.environ, {'PORT': '28689'}):
            with self.assertRaisesRegex(RuntimeError, 'different ports'):
                container.init()
        self.assertFalse(common.home().exists())

    def test_container_does_not_spawn_an_unmanaged_gateway_from_settings(self):
        binary = runtime.root()/'package/node_modules/.bin/openclaw'
        binary.parent.mkdir(parents=True)
        binary.touch()
        runtime.save_config(runtime.initial_config())
        with patch.object(runtime, 'gateway', side_effect=RuntimeError('starting')), \
             patch.object(settings.subprocess, 'Popen') as spawn, patch.object(common, 'systemd_available') as systemd:
            self.assertTrue(settings.start_gateway()['started'])
            spawn.assert_not_called()
            systemd.assert_not_called()

    def test_prepare_preserves_model_and_agent_config_across_image_updates(self):
        common.initialize()
        runtime.root().mkdir()
        for package in ('openclaw', '@openclaw/openshell-sandbox', '@openclaw/parallel-plugin'):
            directory = container.IMAGE_RUNTIME/'package/node_modules'/package
            directory.mkdir(parents=True)
            (directory/'package.json').write_text(json.dumps({'version': '2026.7.1' if package == '@openclaw/parallel-plugin' else runtime.VERSION}))
        (container.IMAGE_RUNTIME/'node').mkdir()
        container.CLIENT_CERTS.mkdir()
        for name in ('ca.crt', 'tls.crt', 'tls.key'):
            (container.CLIENT_CERTS/name).write_text('certificate')
        config = runtime.initial_config()
        config['agents']['entries']['bac-existing'] = {'name': 'Keep me', 'heartbeat': {'every': '30s', 'target': 'none'}}
        config['models']['providers']['test'] = {'baseUrl': 'http://127.0.0.1:11434/v1'}
        runtime.save_config(config)
        # Preparation precedes Gateway startup: RPCs must be unavailable here.
        def cli(*args, **kwargs):
            if args[:2] == ('gateway', 'call'):
                raise RuntimeError('Gateway has not started')
            return 'valid'
        with patch.object(container, 'register_gateway'), patch.object(runtime, 'cli', side_effect=cli):
            container.prepare()
            container.prepare()
        result = common.read_json(runtime.config_path())
        self.assertEqual(result['agents']['entries']['bac-existing']['name'], 'Keep me')
        self.assertEqual(result['agents']['entries']['bac-existing']['heartbeat'], {'every': '0m', 'target': 'none'})
        self.assertEqual(result['models']['providers']['test'], config['models']['providers']['test'])
        self.assertEqual(result['gateway']['port'], 28689)
        self.assertEqual(result['tools']['web']['search']['provider'], 'parallel-free')
        self.assertEqual(result['tools']['web']['search']['maxResults'], 3)
        self.assertTrue(runtime.search_enabled())
        self.assertEqual(len(result['plugins']['load']['paths']), 3)
        self.assertTrue(result['plugins']['entries']['bac-research-guard']['enabled'])
        plugin = result['plugins']['entries']['openshell']['config']
        self.assertEqual(plugin['gateway'], 'bac-demo')
        self.assertEqual(plugin['workspace'], 'default')
        self.assertNotIn('installs', result['plugins'])
        self.assertIn('bac-host', result['agents']['entries'])
        self.assertIn('@sha256:', plugin['from'])
        self.assertFalse(plugin['autoProviders'])

    def test_gateway_registration_is_idempotent(self):
        result = subprocess.CompletedProcess([], 0, stdout=json.dumps([
            {'name': 'bac-demo', 'endpoint': 'https://127.0.0.1:28680'}]))
        with patch.object(container.subprocess, 'run', return_value=result) as run:
            container.register_gateway('https://127.0.0.1:28680')
        self.assertEqual(run.call_count, 1)
        self.assertIn('list', run.call_args.args[0])

    def test_bundled_dependencies_match_application(self):
        lock = common.read_json(container.LOCK_PATH)
        self.assertEqual(lock['openclaw'], runtime.VERSION)
        self.assertEqual(set(lock['downloads']), {'amd64', 'arm64'})
        for image in lock['images'].values():
            self.assertRegex(image, r'@sha256:[a-f0-9]{64}$')

    def test_release_kit_is_portable_and_cannot_overwrite_an_existing_release(self):
        destination = self.root/'release'
        # Reading the guide is not needed for testing reference/Compose safety.
        release.bundle('bac-studio:0.1.0-rc.1', '0.1.0-rc.1', destination)
        compose = (destination/'compose.yaml').read_text()
        self.assertNotIn('  build:', compose)
        self.assertIn('./shared:/host-files', compose)
        self.assertNotIn(str(self.root), compose)
        self.assertTrue((destination/'src/assets/build-a-claw-workshop.png').stat().st_mode & 0o004)
        self.assertTrue((destination/'src/studio.js').exists())
        self.assertIn('.:/opt/bac/source:ro', compose)
        self.assertEqual((destination/'remove.py').read_bytes(), (release.ROOT/'scripts/container_remove.py').read_bytes())
        with self.assertRaisesRegex(ValueError, 'not overwritten'):
            release.bundle('bac-studio:0.1.0-rc.1', '0.1.0-rc.1', destination)
        with self.assertRaisesRegex(ValueError, 'immutable'):
            release.bundle('ghcr.io/example/studio:latest', '0.1.0', self.root/'other')


if __name__ == '__main__':
    unittest.main()
