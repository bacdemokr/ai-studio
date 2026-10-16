from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import openshell_runtime as runtime


class RuntimeTests(unittest.TestCase):
    def test_refuses_mismatched_system_cli(self):
        with patch.object(runtime.shutil,'which',return_value='/example/openshell'), patch.object(runtime.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'openshell 0.0.106\n','')):
            with self.assertRaisesRegex(RuntimeError,'0.1.4 is required'):runtime.command()

    def test_prefers_private_pinned_binary_over_system_install(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runtime.common,'home',return_value=Path(folder)):
            binary=Path(folder)/'openclaw/openshell/0.1.4/bin/openshell';binary.parent.mkdir(parents=True);binary.touch()
            with patch.object(runtime.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'openshell 0.1.4\n','')) as run:
                self.assertEqual(runtime.command(),str(binary));self.assertEqual(run.call_args.args[0][0],str(binary))

    def test_native_ssh_children_share_private_gateway_configuration(self):
        import os
        import agent_runtime
        with tempfile.TemporaryDirectory() as folder, patch.object(runtime.common,'home',return_value=Path(folder)), patch.dict(os.environ,{'BAC_CONTAINER':'0'}):
            config=Path(folder)/'openclaw/openshell/config';config.mkdir(parents=True)
            self.assertEqual(agent_runtime.environment()['XDG_CONFIG_HOME'],str(config))
            self.assertEqual(agent_runtime.environment()['OPENCLAW_STATE_DIR'],str(Path(folder)/'openclaw/state'))

    def test_native_and_docker_cli_share_digest(self):
        lock=runtime.lock()
        for arch in ('amd64','arm64'):self.assertEqual(lock['downloads'][arch]['openshell'],lock['nativeDownloads']['linux-'+arch])
        self.assertIn('@sha256:',lock['images']['sandbox'])
