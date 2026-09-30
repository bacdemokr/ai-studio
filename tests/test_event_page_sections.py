"""Named page edits and real assembly, with no live services or model calls."""
import copy
from html import escape
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import agent_runtime
import event_page_sections as sections
import morgan_page
from test_agent_workflow import AgentToolsAdapter
from test_researched_event import SOURCES
from studio import Studio
from telemetry import Reply


def card(theme):
    return ('<article class="theme-card"><div class="theme-body"><h3>' + escape(theme['demo']) +
            '</h3><p>Try Dylan’s demo — it\'s hands-on.</p><a href="' + escape(theme['source'], quote=True) +
            '">Read the research</a></div></article>')


def apply(work, section, content):
    path = work / 'artifacts/patch.json'
    path.write_text(json.dumps({'section': section, 'content': content}, ensure_ascii=False))
    return sections.run(work, 'apply', 'artifacts/patch.json')


def fill(work):
    contract = json.loads((work / 'inbox/morgan-page.json').read_text())
    text = {'headline': 'Explore agents together', 'intro': 'Try practical AI workflows.',
            'cta': 'Explore demos', 'program-title': 'Hands-on program', 'promotion-title': 'Join us'}
    if contract.get('sectionEditor') == 2:
        files = contract['sectionFiles']
        (work/files['copy']).write_text(json.dumps(text))
        for i, theme in enumerate(contract['themes'], 1):
            (work/files['card-' + str(i)]).write_text(card(theme))
    else:
        for section, content in text.items():
            apply(work, section, content)
        for i, theme in enumerate(contract['themes'], 1):
            apply(work, 'card-' + str(i), card(theme))


class PageFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        (self.work / 'inbox').mkdir(); (self.work / 'artifacts').mkdir()
        self.contract = {'sectionEditor': 1, 'files': {'html': 'artifacts/page.html'},
                         'themes': [{'demo': 'Dylan’s demo', 'source': 'https://example.com/research'}]}
        (self.work / 'inbox/morgan-page.json').write_text(json.dumps(self.contract))
        self.template = ('<style>unchanged CSS</style><h1>MORGAN_HEADLINE</h1><p>MORGAN_INTRO</p>'
                         '<a>MORGAN_CTA</a><h2>MORGAN_PROGRAM_TITLE</h2>' + sections.PROGRAM_SLOT +
                         '<h2>MORGAN_PROMOTION_TITLE</h2><!-- BAC:SCHEDULE -->fixed<!-- /BAC:SCHEDULE -->')
        (self.work / 'inbox/morgan-page-starter.html').write_text(self.template)
        (self.work / 'artifacts/page.html').write_text(self.template)


class SectionTests(PageFixture):
    def test_quotes_newlines_and_repeat_edits_preserve_other_sections(self):
        fill(self.work)
        text = 'It’s Dylan\'s "demo"\n& <ideas>'
        result = apply(self.work, 'intro', text)
        page = (self.work / 'artifacts/page.html').read_text()
        self.assertEqual(result['status'], 'complete')
        self.assertIn(escape(text), page)
        self.assertIn(card(self.contract['themes'][0]), page)
        self.assertIn('<style>unchanged CSS</style>', page)
        self.assertIn('<!-- BAC:SCHEDULE -->fixed<!-- /BAC:SCHEDULE -->', page)
        apply(self.work, 'intro', text)
        self.assertEqual((self.work / 'artifacts/page.html').read_text(), page)

    def test_invalid_card_does_not_damage_saved_work(self):
        fill(self.work)
        original = (self.work / 'artifacts/page.html').read_bytes()
        saved = (self.work / 'artifacts/page.html.sections.json').read_bytes()
        valid = card(self.contract['themes'][0])
        for bad in (valid.replace('h3', 'h2'), valid.replace('https:', 'javascript:'),
                    valid.replace('</article>', ''), valid + '<script>alert(1)</script>',
                    valid.replace('<div', '<div onclick="alert(1)"'),
                    valid + '<!-- BAC:SCHEDULE -->', valid * 30):
            with self.subTest(bad=bad[:80]), self.assertRaises(ValueError):
                apply(self.work, 'card-1', bad)
            self.assertEqual((self.work / 'artifacts/page.html').read_bytes(), original)
            self.assertEqual((self.work / 'artifacts/page.html.sections.json').read_bytes(), saved)
        apply(self.work, 'card-1', valid.replace('hands-on', 'interactive'))
        self.assertIn('interactive', (self.work / 'artifacts/page.html').read_text())

    def test_status_recovers_interrupted_assembly_and_lists_only_missing(self):
        apply(self.work, 'headline', 'Saved headline')
        (self.work / 'artifacts/page.html').write_text('interrupted')
        result = sections.run(self.work)
        self.assertNotIn('headline', result['missing'])
        self.assertIn('card-1', result['missing'])
        self.assertIn('Saved headline', (self.work / 'artifacts/page.html').read_text())

    def test_paths_and_unknown_regions_are_rejected(self):
        with self.assertRaises(ValueError): apply(self.work, 'schedule', 'overwrite')
        with self.assertRaises(ValueError): sections.run(self.work, 'apply', '../outside.json')
        output = self.work / 'artifacts/page.html'
        output.unlink(); output.symlink_to(self.work / 'inbox/morgan-page-starter.html')
        with self.assertRaises(ValueError): apply(self.work, 'headline', 'Changed')
        self.assertEqual((self.work / 'inbox/morgan-page-starter.html').read_text(), self.template)

    def test_workspace_installs_standalone_tool_and_registration_grants_exec(self):
        profile = {'name': 'Morgan', 'persona': 'guide', 'skills': ['nvidia-webpage']}
        with patch.object(agent_runtime, 'root', return_value=self.work / 'native'), \
             patch.object(agent_runtime, 'config_path', return_value=self.work / 'config.json'), \
             patch.object(agent_runtime, 'gateway_config_patch') as publish:
            (self.work / 'config.json').write_text(json.dumps(agent_runtime.initial_config()))
            agent_runtime.register('test-morgan', self.work, profile, 'Marketing producer')
        entry = publish.call_args.args[0]['agents']['entries']['test-morgan']
        self.assertIn('exec', entry['tools']['allow'])
        command = self.work / 'skills/bac-nvidia-webpage/scripts/event_page_sections.py'
        fill(self.work)
        result = subprocess.run([sys.executable, '-B', str(command), 'status'], cwd=self.work,
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['status'], 'complete')


class SectionsAdapter(AgentToolsAdapter):
    def respond(self, agent, session, prompt):
        if agent.endswith('-r3') and not prompt.startswith('LINKEDIN-FIRST:'):
            fill(Path(self.agents[agent]))
            return Reply('Page sections saved.', {})
        return super().respond(agent, session, prompt)


class AutomaticSectionTests(PageFixture):
    def setUp(self):
        super().setUp()
        self.contract['sectionEditor'] = 2
        self.contract['sectionFiles'] = sections.draft_files('artifacts/page.html', 1)
        (self.work/'inbox/morgan-page.json').write_text(json.dumps(self.contract))

    def test_native_writes_are_collected_without_an_apply_call(self):
        fill(self.work)
        self.assertEqual((self.work/'artifacts/page.html').read_text(), self.template)
        result = sections.collect(self.work)
        self.assertEqual(result['status'], 'complete')
        self.assertIn('Explore agents together', (self.work/'artifacts/page.html').read_text())

    def test_harmless_attributes_are_normalized_without_reauthoring(self):
        fill(self.work)
        path = self.work/self.contract['sectionFiles']['card-1']
        source = card(self.contract['themes'][0]).replace('<article ', '<article id="schedule" ').replace(
            'Read the research</a>', 'Read the research<span aria-hidden="true" role="presentation">→</span></a>')
        path.write_text(source)
        self.assertEqual(sections.collect(self.work)['status'], 'complete')
        page = (self.work/'artifacts/page.html').read_text()
        self.assertNotIn('id="schedule"', page)
        self.assertIn('aria-hidden="true"', page)
        self.assertIn('role="presentation"', page)
        self.assertEqual(path.read_text(), source)  # The agent's original source is retained.

    def test_live_morgan_presentation_attributes_do_not_consume_a_repair(self):
        fill(self.work)
        path=self.work/self.contract['sectionFiles']['card-1']
        source=card(self.contract['themes'][0]).replace('<article ', '<article data-theme="agents" ').replace(
            '<a href=', '<a target="_blank" rel="noopener noreferrer" href=').replace(
            '</div>', '<section><details class="demo-reason" open="false"><summary>Limitation</summary><p>Keep this limitation.</p></details></section></div>')
        for attribute in ['open="false"','open="true"','open']:
            with self.subTest(attribute=attribute):
                original=source.replace('open="false"',attribute);path.write_text(original)
                self.assertEqual(sections.collect(self.work)['status'],'complete')
                page=(self.work/'artifacts/page.html').read_text()
                for extra in ['data-theme=','target=','rel=',' open']:self.assertNotIn(extra,page)
                self.assertIn('Keep this limitation.',page)
                self.assertIn(self.contract['themes'][0]['source'],page)
                self.assertEqual(path.read_text(),original)
        path.write_text(source.replace('<details ','<details onclick="alert(1)" '))
        result=sections.collect(self.work)
        self.assertEqual(result['status'],'incomplete')
        self.assertIn('onclick',result['errors']['card-1'])

    def test_invalid_card_retains_valid_copy_and_repair_changes_only_card(self):
        fill(self.work)
        path = self.work/self.contract['sectionFiles']['card-1']
        good = path.read_text(); path.write_text(good.replace('https:', 'javascript:'))
        first = sections.collect(self.work)
        self.assertEqual(set(first['errors']), {'card-1'})
        self.assertIn('headline', first['saved'])
        saved_copy = (self.work/self.contract['sectionFiles']['copy']).read_bytes()
        path.write_text(good)
        self.assertEqual(sections.collect(self.work)['status'], 'complete')
        self.assertEqual((self.work/self.contract['sectionFiles']['copy']).read_bytes(), saved_copy)

    def test_text_field_repair_keeps_other_valid_fields(self):
        fill(self.work)
        path = self.work/self.contract['sectionFiles']['copy']
        text = json.loads(path.read_text()); text['headline'] = 'x' * 101
        path.write_text(json.dumps(text))
        result = sections.collect(self.work)
        self.assertEqual(set(result['errors']), {'headline'})
        path.write_text(json.dumps({'headline': 'Fixed headline'}))
        self.assertEqual(sections.collect(self.work)['status'], 'complete')
        self.assertIn('Try practical AI workflows.', (self.work/'artifacts/page.html').read_text())

    def test_malformed_json_and_unsafe_card_cannot_pass_as_complete(self):
        fill(self.work); sections.collect(self.work)
        (self.work/self.contract['sectionFiles']['copy']).write_text('{"headline":')
        (self.work/self.contract['sectionFiles']['card-1']).write_text('<script>alert(1)</script>')
        result = sections.collect(self.work)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(set(result['errors']), {'copy', 'card-1'})
        self.assertNotIn('<script>', (self.work/'artifacts/page.html').read_text())
