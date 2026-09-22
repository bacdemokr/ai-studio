"""One policy activation for exactly the displayed pending permission set."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
from studio import Studio,Problem
from test_studio import Adapter
from agent_policy import CATALOG, individual_permissions, network_rows, policy_document


class BulkPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.adapter=Adapter();self.studio=Studio(self.temp.name,self.adapter,start_worker=False)
        self.owner=self.studio.session()[0]['id']
        self.profile={'name':'Shield','persona':'guide','skills':['web'],'protection':'openshell'}
        self.studio.onboard(self.owner,self.profile)
        self.keys=['host:api.open-meteo.com','host:wttr.in']

    def request(self,text='Check https://api.open-meteo.com and https://wttr.in'):
        job=self.studio.enqueue(self.owner,{'prompt':text})
        self.studio.decision(self.owner,job['id'],'cancel')

    def saved(self):
        with self.studio.db() as db:
            row=db.execute('select approved,updating from agent_policies where owner=?',(self.owner,)).fetchone()
        return (json.loads(row['approved']),row['updating']) if row else ([],0)

    def test_two_hosts_activate_once_and_prepare_once_without_granting_presets(self):
        self.request()
        with patch.object(self.adapter,'policy_apply',wraps=self.adapter.policy_apply) as apply,patch.object(self.adapter,'policy_prepare',wraps=self.adapter.policy_prepare) as prepare:
            self.assertEqual(self.studio.policy_change(self.owner,{'permissions':self.keys,'allow':True}),{'applied':True})
            self.assertEqual(apply.call_count,1);self.assertEqual(prepare.call_count,1)
            self.assertEqual(apply.call_args.args[1],self.keys)
        report=self.studio.policy_report(self.owner)
        self.assertEqual(report['status'],'applied');self.assertEqual(report['pendingAccess'],[])
        self.assertEqual(report['requested'],self.keys)
        self.assertEqual(report['history'][-1]['title'],'Permissions approved')
        self.assertEqual(self.saved(),(self.keys,0))

    def test_existing_approvals_and_other_agents_are_preserved(self):
        self.studio.policy_change(self.owner,{'permission':'papers','allow':True})
        other=self.studio.add_agent(self.owner,{**self.profile,'name':'Other'})['agentId']
        self.request()
        with patch.object(self.adapter,'policy_apply',wraps=self.adapter.policy_apply) as apply:
            self.studio.policy_change(self.owner,{'permissions':self.keys,'allow':True})
            self.assertEqual(apply.call_count,1)
        self.assertEqual(self.saved()[0],sorted(self.keys+['host:arxiv.org','host:export.arxiv.org']))
        with self.assertRaises(Problem):self.studio.policy_change(other,{'permissions':self.keys,'allow':True})
        self.assertEqual(self.studio.policy_report(other)['requested'],[])

    def test_exact_host_then_preset_deduplicates_and_individual_revoke_preserves_others(self):
        self.request()
        self.studio.policy_change(self.owner, {'permission': self.keys[0], 'allow': True})
        self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': True})
        expected = ['host:' + host for host in CATALOG['weather']['hosts']]
        self.assertEqual(self.saved()[0], sorted(expected))
        report = self.studio.policy_report(self.owner)
        self.assertEqual(report['requested'], sorted(expected))
        self.assertEqual(len(report['rules']), 3)
        self.studio.policy_change(self.owner, {'permission': self.keys[0], 'allow': False})
        remaining = sorted(set(expected) - {self.keys[0]})
        self.assertEqual(self.saved()[0], remaining)
        self.assertEqual(self.adapter.permissions['bac-' + self.owner], remaining)
        self.assertNotIn('api.open-meteo.com', [r['host'] for r in self.studio.policy_report(self.owner)['rules']])
        self.studio.policy_change(self.owner, {'permission': 'weather', 'allow': True})
        self.assertEqual(self.saved()[0], sorted(expected))

    def test_legacy_overlapping_presets_display_without_mutation_and_can_revoke_one_host(self):
        self.studio.ensure_agent(self.owner, self.studio.profile(self.owner))
        legacy = ['weather', self.keys[0], 'papers']
        with self.studio.db() as db:
            db.execute('INSERT INTO agent_policies (owner,approved) VALUES (?,?)', (self.owner, json.dumps(legacy)))
        self.adapter.permissions['bac-' + self.owner] = legacy[:]
        with patch.object(self.adapter, 'policy_apply', wraps=self.adapter.policy_apply) as apply:
            report = self.studio.policy_report(self.owner)
            self.assertEqual(report['status'], 'applied')
            self.assertEqual(len(report['requested']), 5)
            self.assertTrue(all(key.startswith('host:') for key in report['requested']))
            self.assertEqual(self.saved()[0], legacy)
            apply.assert_not_called()
            self.studio.policy_change(self.owner, {'permission': self.keys[0], 'allow': False})
            apply.assert_called_once()
        remaining = sorted(set(individual_permissions(legacy)) - {self.keys[0]})
        self.assertEqual(self.saved()[0], remaining)
        self.assertEqual(self.studio.policy_report(self.owner)['status'], 'applied')

    def test_all_presets_have_same_scope_when_expanded_and_no_duplicate_rules(self):
        for key in CATALOG:
            with self.subTest(preset=key):
                hosts = CATALOG[key]['hosts']
                expanded = individual_permissions([key, 'host:' + hosts[0]])
                self.assertEqual(expanded, sorted('host:' + host for host in hosts))
                before = {r['host'] for r in network_rows(policy_document([key]))}
                after = network_rows(policy_document(expanded))
                self.assertEqual({r['host'] for r in after}, before)
                self.assertEqual(len(after), len(before))

    def test_invalid_or_old_requests_never_partially_apply(self):
        self.request()
        for payload in ({'permissions':[],'allow':True},{'permissions':self.keys,'allow':False},
                        {'permissions':[self.keys[0],self.keys[0]],'allow':True},
                        {'permissions':[self.keys[0],{}],'allow':True},
                        {'permissions':self.keys,'retry':True,'allow':True},
                        {'permissions':[self.keys[0],'papers'],'allow':True}):
            with self.subTest(payload=payload),patch.object(self.adapter,'policy_apply') as apply:
                with self.assertRaises(Problem):self.studio.policy_change(self.owner,payload)
                apply.assert_not_called();self.assertEqual(self.saved(),([],0))
        self.request('Read https://arxiv.org')
        with self.assertRaisesRegex(Problem,'list changed'):
            self.studio.policy_change(self.owner,{'permissions':self.keys,'allow':True})
        self.assertEqual(self.saved(),([],0))

    def test_pending_work_and_other_policy_update_fence_batch(self):
        job=self.studio.enqueue(self.owner,{'prompt':'Check https://api.open-meteo.com and https://wttr.in'})
        with self.assertRaises(Problem):self.studio.policy_change(self.owner,{'permissions':self.keys,'allow':True})
        self.studio.decision(self.owner,job['id'],'cancel')
        with self.studio.db() as db:db.execute('insert into agent_policies(owner,updating) values(?,1)',(self.owner,))
        with patch.object(self.adapter,'policy_apply') as apply:
            with self.assertRaises(Problem):self.studio.policy_change(self.owner,{'permissions':self.keys,'allow':True})
            apply.assert_not_called()
        self.assertEqual(self.saved(),([],1))

    def test_failed_activation_saves_whole_intent_as_unverified_and_retries_once(self):
        self.request()
        with patch.object(self.adapter,'policy_apply',side_effect=RuntimeError('fixture failure')) as apply:
            with self.assertRaises(Problem):self.studio.policy_change(self.owner,{'permissions':self.keys,'allow':True})
            self.assertEqual(apply.call_count,1)
        report=self.studio.policy_report(self.owner)
        self.assertEqual(report['status'],'needs-review');self.assertEqual(report['rules'],[])
        self.assertEqual(self.saved(),(self.keys,0))
        with patch.object(self.adapter,'policy_apply',wraps=self.adapter.policy_apply) as apply:
            self.studio.policy_change(self.owner,{'retry':True});self.assertEqual(apply.call_count,1)
        self.assertEqual(self.studio.policy_report(self.owner)['status'],'applied')

    def test_retired_file_grants_reject_whole_batch_before_native_io(self):
        for path in [Path(self.temp.name)/'missing.txt', Path(self.temp.name)/'notes.txt']:
            if path.name=='notes.txt':path.write_text('unchanged')
            self.request('Read '+str(path)+' and https://wttr.in')
            with patch.object(self.adapter,'policy_apply') as apply:
                with self.assertRaisesRegex(Problem,'permission'):
                    self.studio.policy_change(self.owner,{'permissions':['host:wttr.in','file:read:'+str(path)],'allow':True})
                apply.assert_not_called()
            self.assertEqual(self.saved(),([],0))

if __name__=='__main__':unittest.main()
