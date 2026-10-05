"""Captain native tool boundaries, restoration and safe failure diagnosis."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import agent_runtime as runtime
from agent_activity import model_failure
import test_collaboration_plan as fixture


class CaptainControlsTests(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start
    job = fixture.CollaborationTests.job

    def test_plan_modes_and_normal_chat_restore(self):
        original = self.adapter.respond
        modes = []
        def respond(agent, session, prompt, **kwargs):
            if agent.endswith('-r0'):
                mode = self.adapter.profiles[agent].get('_planControl')
                modes.append(mode)
                expected = 'read' if '-checking-' in session or session.endswith('-reviewing') else 'none'
                if session.startswith('bac-plan-'):
                    self.assertEqual(mode, expected)
                    self.assertIn('compact JSON', prompt)
                    self.assertTrue(kwargs.get('json_response'))
                else:
                    self.assertNotIn('json_response', kwargs)
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        result = self.start()
        self.app.execute(self.app.next_job())
        self.assertEqual(modes, ['none', 'read', 'read', 'read'])
        team = self.app.crew_owner(self.owner)
        self.app.enqueue(team, {'kind':'crew-chat','crewRole':0,'prompt':'Create a short note.'})
        self.app.execute(self.app.next_job())
        self.assertIsNone(modes[-1])
        self.assertEqual(self.job(result)['status'], 'done')

    def test_failed_checkpoint_returns_saved_partial_without_retry(self):
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if '-checking-' in session:
                raise runtime.GatewayError('The model returned an invalid tool call.', 'malformed-tool-call')
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        result = self.start()
        self.app.execute(self.app.next_job())
        job = self.job(result);plan = job['payload']['collaboration']
        self.assertEqual(job['status'], 'done')
        self.assertEqual(plan['outcome'], 'partial')
        self.assertEqual(plan['calledRoles'], [8])
        self.assertIn('Verified contribution from Scout', job['result']['answer'])
        self.assertEqual(plan['failure']['reason'], 'malformed-tool-call')
        self.assertEqual(self.adapter.reaction_calls, [])

    def test_prose_checkpoint_preserves_results_without_inventing_dispatch(self):
        original = self.adapter.respond
        def respond(agent, session, prompt, **kwargs):
            if '-checking-' in session:
                return 'I will assign the remaining agents now.'
            return original(agent, session, prompt, **kwargs)
        self.adapter.respond = respond
        result = self.start()
        self.app.execute(self.app.next_job())
        job = self.job(result)
        self.assertEqual(job['payload']['collaboration']['calledRoles'], [8])
        self.assertEqual(job['payload']['collaboration']['failure']['reason'], 'invalid-decision')
        self.assertEqual(job['payload']['collaboration']['outcome'], 'partial')
        self.assertIn('Verified contribution from Scout', job['result']['answer'])

    def test_specialists_keep_editing_tools_without_patch_retries(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runtime, 'root', return_value=Path(folder)):
            runtime.save_config(runtime.initial_config())
            for role in (5, 7, 8):
                agent = 'bac-' + 'f'*24 + '-r' + str(role)
                try:
                    with patch.object(runtime, 'gateway_config_patch') as publish:
                        runtime.register(agent, Path(folder)/str(role),
                                         {'name':'Specialist','persona':'maker','skills':[]}, 'Specialist')
                        tools = publish.call_args.args[0]['agents']['entries'][agent]['tools']
                        self.assertTrue({'read','write','edit'}.issubset(tools['allow']))
                        self.assertIn('apply_patch',tools['deny'])
                        self.assertTrue(tools['loopDetection']['enabled'])
                finally:runtime._expected_identity.pop(agent,None)

    def test_native_config_restricts_tools_and_workspace_then_restores(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runtime, 'root', return_value=Path(folder)):
            runtime.save_config(runtime.initial_config())
            agent = 'bac-' + 'f'*24 + '-r0'
            profile = {'name':'Casey','persona':'guide','skills':['event-tools']}
            try:
                with patch.object(runtime, 'gateway_config_patch') as publish:
                    for mode in ('none', 'read', None):
                        current = dict(profile)
                        if mode:current['_planControl'] = mode
                        runtime.register(agent, Path(folder)/'workspace', current, 'BaC Captain')
                        entry = publish.call_args.args[0]['agents']['entries'][agent]
                        if mode:
                            self.assertEqual(entry['tools']['allow'], ['read'] if mode=='read' else [])
                            self.assertEqual(entry['tools']['deny'], [] if mode=='read' else ['*'])
                            self.assertTrue(entry['tools']['fs']['workspaceOnly'])
                            self.assertEqual(entry['skills'], [])
                        else:
                            self.assertIn('write', entry['tools']['allow'])
                            self.assertIn('bac-event-tools', entry['skills'])
                            self.assertFalse(entry['tools']['fs']['workspaceOnly'])
            finally:runtime._expected_identity.pop(agent,None)

    def test_claimed_completion_cannot_skip_required_page_or_independent_review(self):
        self.adapter.plan['tasks'] = [{'role':6,'task':'Analyze'}, {'role':5,'task':'Build HTML'}, {'role':4,'task':'Review'}]
        original = self.adapter.respond
        def respond(agent,session,prompt,**kwargs):
            answer = original(agent,session,prompt,**kwargs)
            if '-checking-' in session:
                return json.dumps({'done':True,'reason':'All done','answer':'Complete'})
            if agent.endswith('-r5'):
                (self.adapter.agents[agent]/'artifacts/report.html').write_text('<html><body>450</body></html>')
            return answer
        self.adapter.respond = respond
        result = self.start('/plan Build an HTML dashboard. Independent review is required.')
        self.app.execute(self.app.next_job())
        self.assertEqual(self.job(result)['payload']['collaboration']['calledRoles'],[6,5,4])

    def test_only_explicit_manifest_ids_fill_an_omitted_input_field(self):
        from plan_inputs import validate_assignments
        tasks=[{'task':'Read document-0'}, {'task':'Use the previous analysis'},
               {'task':'Read document-0','inputs':[]}, {'task':'Read document-01'}]
        validate_assignments(tasks,[{'id':'document-0'},{'id':'document-1'}],False)
        self.assertEqual([t['inputs'] for t in tasks],[['document-0'],[],[],[]])


class ModelFailureTests(unittest.TestCase):
    def test_json_format_applies_only_to_control_requests(self):
        def gateway(path,*args,**kwargs):
            if path=='/v1/models':return {'data':[{'id':'openclaw/a'}]}
            return {'choices':[{'message':{'content':'{"done":false,"reason":"next task"}'}}]}
        with patch.object(runtime,'gateway',side_effect=gateway) as call, patch.object(runtime,'observed_activity',return_value={'calls':[]}), patch('user_location.context',return_value=''), patch('telemetry.measure',return_value={}):
            for structured in (True,False):
                runtime.respond('a','s','hello',json_response=structured)
                payload=call.call_args.args[1]
                self.assertEqual(payload.get('response_format'), {'type':'json_object'} if structured else None)

    def test_diagnosis_is_scoped_and_never_leaks_raw_content(self):
        with tempfile.TemporaryDirectory() as folder:
            dbpath = Path(folder)/'agents/a/agent/openclaw-agent.sqlite'
            dbpath.parent.mkdir(parents=True)
            with sqlite3.connect(dbpath) as db:
                db.executescript('CREATE TABLE session_windows(session_id TEXT, session_key TEXT); CREATE TABLE transcript_events(session_id TEXT,seq INTEGER,created_at INTEGER,event_json TEXT);')
                db.execute('INSERT INTO session_windows VALUES (?,?)', ('one','agent:a:openai-user:s'))
                def insert(seq,stamp,message):
                    db.execute('INSERT INTO transcript_events VALUES (?,?,?,?)', ('one',seq,stamp,json.dumps({'message':message})))
                    db.commit()
                insert(1,1100,{'role':'assistant','errorMessage':'Provider returned an incomplete or malformed tool call','usage':{'output':8192},'content':[{'type':'text','text':'SECRET_DO_NOT_RETURN'}]})
                diagnosis = model_failure(folder,'a','s',1,8192)
                self.assertEqual(diagnosis['code'],'tool-call-output-limit')
                self.assertNotIn('SECRET',json.dumps(diagnosis))
                self.assertIsNone(model_failure(folder,'a','other',1,8192))
                self.assertIsNone(model_failure(folder,'a','s',2,8192))
                insert(2,1200,{'role':'assistant','stopReason':'stop','content':[]})
                self.assertIsNone(model_failure(folder,'a','s',1,8192))
                insert(3,1300,{'role':'assistant','errorMessage':'Provider returned an incomplete or malformed tool call','usage':{'output':15}})
                self.assertEqual(model_failure(folder,'a','s',1,8192)['code'],'malformed-tool-call')
                insert(4,1400,{'role':'assistant','errorMessage':'PRIVATE_PROVIDER_RESPONSE'})
                self.assertIsNone(model_failure(folder,'a','s',1,8192))

                for seq, text, code in [
                    (5, 'HTTP 401 Authentication Error: FATAL: remaining connection slots are reserved for roles with the SUPERUSER attribute PRIVATE_DETAIL', 'provider-capacity'),
                    (6, 'Model provider returned HTTP 503 PRIVATE_DETAIL', 'provider-unavailable'),
                    (7, 'HTTP 429 PRIVATE_DETAIL', 'provider-rate-limit'),
                    (8, 'HTTP 401 Authentication Error: FATAL: sorry, too many clients already PRIVATE_DETAIL', 'provider-capacity')]:
                    insert(seq, 1400 + seq, {'role':'assistant', 'errorMessage':text})
                    diagnosis = model_failure(folder,'a','s',1,8192)
                    self.assertEqual(diagnosis['code'], code)
                    self.assertNotIn('PRIVATE_DETAIL', json.dumps(diagnosis))

    def test_gateway_error_enriched_without_repeating_model_request(self):
        error = runtime.GatewayError('Generic 500','request_failed')
        def gateway(path,*args,**kwargs):
            if path=='/v1/models':return {'data':[{'id':'openclaw/a'}]}
            raise error
        diagnosis={'code':'malformed-tool-call','message':'The model returned an invalid tool call.'}
        with patch.object(runtime,'gateway',side_effect=gateway) as call, patch('agent_activity.model_failure',return_value=diagnosis), patch.object(runtime,'observed_activity',return_value={'calls':[]}), patch('user_location.context',return_value=''):
            with self.assertRaises(runtime.GatewayError) as raised:runtime.respond('a','s','hello')
            self.assertEqual(raised.exception.reason,'malformed-tool-call')
            self.assertEqual(raised.exception.activity,{'calls':[]})
            self.assertEqual(sum(x.args[0]=='/v1/chat/completions' for x in call.call_args_list),1)


if __name__=='__main__':unittest.main()
