"""Match native sandbox creation across OpenShell CLI capabilities."""
import json
import subprocess
import unittest
from unittest.mock import patch

import agent_policy as policy
import agent_runtime as runtime


class CreateCompatibilityTests(unittest.TestCase):
    def prepare(self, help_text, exists=False, failure=None):
        native = subprocess.CompletedProcess([], 0, json.dumps({'backend':'openshell', 'runtimeId':'oc-test'}), '')
        def shell(*args, **kwargs):
            if args == ('sandbox','create','--help'):return help_text
            if failure:raise failure
            return ''
        with patch.object(runtime.subprocess, 'run', return_value=native), \
             patch.object(policy, 'sandbox_names', return_value={'oc-test'} if exists else set()), \
             patch.object(policy, 'plugin_config', return_value={'config':{'from':'openclaw'}}), \
             patch.object(policy, 'shell', side_effect=shell) as calls:
            if failure and not exists:
                with self.assertRaises(type(failure)):runtime.policy_prepare('bac-'+'a'*24)
            else:runtime.policy_prepare('bac-'+'a'*24)
            return calls.call_args_list

    def test_old_cli_keeps_sandbox_without_hanging_on_sleep(self):
        calls = self.prepare('FLAGS:\n  --no-keep  Delete after exit\n')
        self.assertEqual(calls[0].args, ('sandbox','create','--help'))
        self.assertEqual(calls[1].args[-2:], ('--','true'))
        self.assertNotIn('--detach', calls[1].args)
        self.assertIn('--no-auto-providers', calls[1].args)
        self.assertIn('--policy', calls[1].args)
        self.assertNotIn('--no-keep', calls[1].args)

    def test_detach_capable_cli_uses_native_detached_command(self):
        calls = self.prepare('FLAGS:\n    --detach  Create without connecting\n')
        self.assertEqual(calls[1].args[-4:], ('--detach','--','sleep','infinity'))

    def test_existing_sandbox_is_not_recreated(self):
        self.assertEqual(self.prepare('', exists=True), [])

    def test_failed_create_is_not_retried_with_other_flags(self):
        calls = self.prepare('  --detach\n', failure=RuntimeError('failed after creation'))
        self.assertEqual(len(calls), 2)

    def test_failed_help_never_sends_create(self):
        native = subprocess.CompletedProcess([], 0, json.dumps({'backend':'openshell','runtimeId':'oc-test'}), '')
        with patch.object(runtime.subprocess,'run',return_value=native), \
             patch.object(policy,'sandbox_names',return_value=set()), \
             patch.object(policy,'plugin_config',return_value={'config':{}}), \
             patch.object(policy,'shell',side_effect=RuntimeError('help failed')) as calls:
            with self.assertRaises(RuntimeError):runtime.policy_prepare('bac-'+'a'*24)
        self.assertEqual(calls.call_args.args, ('sandbox','create','--help'))
        self.assertEqual(calls.call_count, 1)


if __name__ == '__main__':unittest.main()
