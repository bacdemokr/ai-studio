"""Host-side lifecycle tests: no GPU, model download, systemd writes or network."""
import contextlib
import io
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / 'scripts'))
import ops_common as c
import ops_deploy as deploy
import ops_llm as llm
import ops_runtime as runtime
import manage


def git(directory, *args):
    return subprocess.run(['git', '-C', str(directory), *args], check=True, capture_output=True, text=True).stdout.strip()


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / 'state'
        self.environment = patch.dict(os.environ, {'BAC_DATA_DIR': str(self.data), 'XDG_CONFIG_HOME': str(self.root / 'config')})
        self.environment.start()
        c.initialize()
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()

    def tearDown(self):
        self.output.__exit__(None, None, None)
        self.environment.stop()
        self.temp.cleanup()

    def model_files(self, name):
        target = self.data / 'models' / name
        target.mkdir(parents=True)
        (target / 'weights.bin').write_text('keep me')
        return target

    def test_remove_is_preview_until_explicit_and_scoped(self):
        qwen = self.model_files('qwen')
        gemma = self.model_files('gemma')
        runtime = self.data / 'runtime/vllm-env'
        runtime.mkdir(parents=True)
        llm.remove('qwen')
        self.assertTrue(qwen.exists())
        llm.remove('qwen', yes=True)
        self.assertFalse(qwen.exists())
        self.assertTrue(gemma.exists())
        self.assertTrue(runtime.exists())

    def test_delete_refuses_symlink_and_unowned_root(self):
        other = self.root / 'other'
        other.mkdir()
        sentinel = other / 'important'
        sentinel.write_text('unrelated')
        (self.data / 'models').mkdir()
        (self.data / 'models/qwen').symlink_to(other)
        with self.assertRaises(RuntimeError):
            llm.remove('qwen', yes=True)
        self.assertTrue(sentinel.exists())
        (self.data / c.MARKER).unlink()
        with self.assertRaises(RuntimeError):
            c.remove_directory(self.data / 'models')

    def test_model_switch_only_stops_managed_llm(self):
        for name in ('qwen','gemma'):
            folder = self.data / 'models' / name
            (folder / 'weights').mkdir(parents=True)
            (folder / 'weights/config.json').write_text('{}')
            c.write_json(folder / 'installed.json', {**llm.profile(name), 'environment': llm.profiles()['environment']})
        executable = self.data / 'runtime/vllm-env/bin/vllm'
        executable.parent.mkdir(parents=True)
        executable.touch()
        c.write_json(self.data / 'llm.json', {'profile':'qwen'})
        with patch.object(llm, 'require_spark'), patch.object(c, 'require_systemd'), \
             patch.object(c, 'active', return_value=True), patch.object(c, 'is_owned_unit', return_value=True), \
             patch.object(c, 'port_free', return_value=True), patch.object(c, 'install_unit') as install, \
             patch.object(c, 'service') as service:
            llm.start('gemma')
            self.assertEqual(service.call_args_list[0].args, ('bac-llm','stop'))
            self.assertTrue(all(call.args[0]=='bac-llm' for call in service.call_args_list))
            command = install.call_args.args[1]
            self.assertIn('bac-local', command)
            self.assertIn('--chat-template', command)
            self.assertEqual(c.read_json(self.data / 'llm.json')['profile'], 'gemma')

    def test_installed_profile_survives_changed_checkout_profile(self):
        folder = self.data / 'models/qwen'
        (folder / 'weights').mkdir(parents=True)
        (folder / 'weights/config.json').write_text('{}')
        spec = {**llm.profile('qwen'), 'environment': llm.profiles()['environment']}
        c.write_json(folder / 'installed.json', spec)
        with patch.object(llm, 'profile', side_effect=AssertionError('must use installed snapshot')):
            command, loaded = llm.command('qwen', installed=True)
        self.assertEqual(loaded, spec)
        self.assertIn('flashinfer_b12x', command)

    def fixture_repo(self):
        origin = self.root / 'origin.git'
        seed = self.root / 'seed'
        checkout = self.root / 'checkout'
        origin.mkdir(); seed.mkdir()
        git(origin, 'init', '--bare')
        git(seed, 'init', '-b', 'main')
        git(seed, 'config', 'user.name', 'Test')
        git(seed, 'config', 'user.email', 'test@example.invalid')
        shutil.copytree(SOURCE / 'src', seed / 'src')
        shutil.copytree(SOURCE / 'scripts', seed / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(SOURCE / 'bac', seed / 'bac')
        shutil.copy2(SOURCE / 'launch.sh', seed / 'launch.sh')
        (seed / '.gitignore').write_text('app/version.json\n__pycache__/\n')
        git(seed, 'add', '.')
        git(seed, 'commit', '-m', 'first version')
        git(seed, 'remote', 'add', 'origin', str(origin))
        git(seed, 'push', 'origin', 'main')
        git(self.root, 'clone', '-b', 'main', str(origin), str(checkout))
        return seed, checkout

    def test_update_and_rollback_preserve_models_and_checkout(self):
        seed, checkout = self.fixture_repo()
        model = self.model_files('qwen')
        c.write_json(self.data / 'llm.json', {'profile':'qwen'})
        with patch.object(c, 'REPO', checkout), patch.object(c, 'active', return_value=False), patch.object(c, 'service') as service:
            first = deploy.stage()
            self.assertTrue(os.access(first / 'bac', os.X_OK))
            self.assertTrue(os.access(first / 'launch.sh', os.X_OK))
            deploy.activate(first)
            with (seed / 'src/studio.html').open('a') as output:
                output.write('\n<!-- second version -->\n')
            git(seed, 'add', '.'); git(seed, 'commit', '-m', 'second version'); git(seed, 'push', 'origin', 'main')
            deploy.update()
            second = deploy.release_target('current')
            self.assertNotEqual(first, second)
            self.assertIn('second version', (second / 'app/index.html').read_text())
            self.assertEqual(c.read_json(second / 'app/version.json')['version'], git(checkout, 'rev-parse', 'HEAD'))
            self.assertEqual(git(checkout, 'status', '--porcelain'), '')
            deploy.update()
            self.assertEqual(deploy.release_target('current'), second)
            self.assertEqual(deploy.release_target('previous'), first)
            deploy.rollback()
            self.assertEqual(deploy.release_target('current'), first)
            self.assertEqual(git(checkout, 'rev-parse', 'HEAD'), git(seed, 'rev-parse', 'HEAD'))
            self.assertTrue(model.exists())
            self.assertEqual(c.read_json(self.data / 'llm.json'), {'profile':'qwen'})
            service.assert_not_called()

    def test_build_failure_and_dirty_checkout_leave_current_running_copy(self):
        seed, checkout = self.fixture_repo()
        with patch.object(c, 'REPO', checkout), patch.object(c, 'active', return_value=False):
            first = deploy.stage(); deploy.activate(first)
            (checkout / 'src/studio.html').write_text('local edits')
            with self.assertRaises(RuntimeError): deploy.update()
            self.assertEqual((checkout / 'src/studio.html').read_text(), 'local edits')
            git(checkout, 'restore', 'src/studio.html')
            (seed / 'scripts/build.py').write_text('raise SystemExit(7)\n')
            git(seed, 'add', '.'); git(seed, 'commit', '-m', 'broken build'); git(seed, 'push', 'origin', 'main')
            with self.assertRaises(subprocess.CalledProcessError): deploy.update()
            self.assertEqual(deploy.release_target('current'), first)

    def test_health_failure_restores_previous_release_and_only_restarts_app(self):
        releases = self.data / 'demo/releases'
        for name in ('old','new'):
            directory = releases / name
            directory.mkdir(parents=True)
            c.write_json(directory / '.bac-release.json', {'commit':name})
        deploy.point('current', releases / 'old')
        with patch.object(c, 'service') as service, patch.object(deploy, 'wait_ready', side_effect=[RuntimeError('failed'), None]):
            with self.assertRaises(RuntimeError): deploy.activate(releases / 'new', restart=True)
            self.assertEqual(deploy.release_target('current'), releases / 'old')
            self.assertEqual([call.args for call in service.call_args_list], [('bac-demo','restart'),('bac-demo','restart')])

    def test_refuses_foreign_unit(self):
        target = c.unit_path('bac-demo')
        target.parent.mkdir(parents=True)
        target.write_text('[Service]\nExecStart=/some/other/app\n')
        with patch.object(c, 'require_systemd'):
            with self.assertRaises(RuntimeError): c.install_unit('bac-demo', ['/bin/true'])
        self.assertIn('/some/other/app', target.read_text())

    def test_setup_existing_endpoint_does_not_download_a_model(self):
        with patch.object(runtime,'setup') as setup, patch.object(llm,'setup') as weights, patch.object(c,'require_systemd'):
            manage.setup_stack()
        setup.assert_called_once();weights.assert_not_called()
        with patch.object(llm,'require_spark',side_effect=RuntimeError('Not Spark')), patch.object(runtime,'setup') as setup:
            with self.assertRaises(RuntimeError):manage.setup_stack('qwen')
        setup.assert_not_called()

    def test_start_orders_services_and_does_not_claim_ready_after_model_failure(self):
        calls=[]
        args=SimpleNamespace(model='qwen',wait=600,host=None,port=None)
        with patch.object(deploy,'validate_start'), patch.object(runtime,'require_installed'), \
             patch.object(llm,'start',side_effect=lambda name:calls.append('model')), \
             patch.object(llm,'check',side_effect=lambda wait:calls.append('model-ready')), \
             patch.object(runtime,'start',side_effect=lambda:calls.append('runtime')), \
             patch.object(runtime,'check',side_effect=lambda **kw:calls.append('runtime-ready')), \
             patch.object(deploy,'start',side_effect=lambda *a:calls.append('app')):
            manage.start_stack(args)
            self.assertEqual(calls,['model','model-ready','runtime','runtime-ready','app'])
            calls.clear()
            with patch.object(llm,'check',side_effect=RuntimeError('Model still loading')):
                with self.assertRaises(RuntimeError):manage.start_stack(args)
            self.assertEqual(calls,['model'])

    def test_repeated_app_start_keeps_current_connection(self):
        current=self.data/'demo/releases/current';current.mkdir(parents=True)
        with patch.object(deploy,'validate_start',return_value=(current,{'host':'127.0.0.1','port':8080},True)), \
             patch.object(deploy,'wait_ready') as ready, patch.object(c,'install_unit') as install, patch.object(c,'service') as service:
            deploy.start()
        ready.assert_called_once_with(current);install.assert_not_called();service.assert_not_called()

    def test_repeated_runtime_start_does_not_restart_reachable_gateway(self):
        with patch.object(runtime,'require_installed'), patch.object(runtime.r,'gateway',return_value={}), patch.object(c,'service') as service:
            runtime.start()
        service.assert_not_called()

    def test_runtime_check_fails_when_the_gateway_is_unreachable(self):
        with patch.object(runtime,'require_installed'),patch.object(runtime.r,'cli'), \
             patch.object(runtime.r,'gateway',side_effect=RuntimeError('Disconnected')),patch.object(c,'is_owned_unit',return_value=False):
            with self.assertRaisesRegex(RuntimeError,'not ready'):runtime.check()

    def test_readiness_wait_retries_but_stops_on_service_failure(self):
        with patch.object(c,'get_json',side_effect=[OSError('loading'),{'data':[{'id':'bac-local'}]}]) as get, \
             patch.object(c,'is_owned_unit',return_value=False), patch.object(c.time,'sleep'):
            llm.check(wait=10)
        self.assertEqual(get.call_count,2)
        with patch.object(c,'get_json',side_effect=OSError('failed')), patch.object(c,'is_owned_unit',return_value=True), \
             patch.object(c,'systemd_available',return_value=True), patch.object(c.subprocess,'run',return_value=SimpleNamespace(stdout='failed\n')), \
             patch.object(c.time,'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError,'service stopped'):llm.check(wait=600)
        sleep.assert_not_called()
        with patch.object(c,'get_json',return_value={'data':[{'id':'unrelated-model'}]}),patch.object(c,'is_owned_unit',return_value=False):
            with self.assertRaisesRegex(RuntimeError,'not ready'):llm.check()

    def test_service_changes_refuse_pending_missions_and_policy_updates(self):
        folder=self.data/'studio';folder.mkdir()
        with sqlite3.connect(folder/'studio.sqlite') as db:
            db.executescript("CREATE TABLE jobs(status TEXT); CREATE TABLE agent_policies(updating INTEGER);")
            db.execute("INSERT INTO jobs VALUES ('running')")
        with self.assertRaisesRegex(RuntimeError,'Nothing was restarted'):c.require_idle()
        with patch.object(deploy,'clean_checkout'),patch.object(deploy,'git') as git_call:
            with self.assertRaises(RuntimeError):deploy.update()
        git_call.assert_not_called()
        model=self.model_files('qwen')
        c.write_json(self.data/'llm.json',{'profile':'qwen'})
        with patch.object(c,'service') as service:
            with self.assertRaises(RuntimeError):llm.remove('qwen',yes=True)
            with self.assertRaises(RuntimeError):llm.remove_runtime(yes=True)
        service.assert_not_called()
        self.assertTrue(model.exists())
        with sqlite3.connect(folder/'studio.sqlite') as db:
            db.execute("UPDATE jobs SET status='done'")
            db.execute('INSERT INTO agent_policies VALUES (1)')
        with self.assertRaises(RuntimeError):c.require_idle()
        with sqlite3.connect(folder/'studio.sqlite') as db:db.execute('UPDATE agent_policies SET updating=0')
        c.require_idle()


if __name__ == '__main__':
    unittest.main()
