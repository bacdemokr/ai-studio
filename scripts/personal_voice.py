"""Personal-agent voice contract shared by workspace files, chat and reactions."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESET_UPDATES = {
    'Summarize uploaded PDFs, slide decks and notes in 3 key points and one next step. Cite pages or slides, flag missing evidence, and keep the answer under 150 words.':
    'Turn any question, document or event into exactly three concise takeaways, numbered 1, 2 and 3. Keep my chosen tone. Cite sources when supplied, and include any next step within the three points.',
    'Polish short messages for my audience while keeping my facts and intent. Give me one concise, ready-to-use draft.':
    'Answer in the style of a concise Slack announcement: an emoji-led headline and short, useful lines. Keep my chosen tone and the supplied facts. Draft only; never send or publish.',
}


def signature(profile):
    skills = profile.get('skills', [])
    parts=[]
    for key in ('documents','writer'):
        if key in skills:
            source=(ROOT/'skills'/('bac-'+key)/'SKILL.md').read_text()
            parts.append(source.split('## Signature\n',1)[1].split('\n## ',1)[0].strip())
    if 'documents' in skills and 'writer' in skills:
        parts.append('COMBINED FORMAT: exactly 1., 2., 3. is the outer structure. Start each point with a relevant emoji and use short Slack-style phrasing. No separate headline or unnumbered text.')
    return '\n'.join(parts)


def contract(profile):
    purpose=PRESET_UPDATES.get(profile.get('purpose'),profile.get('purpose')) or profile.get('persona','helper')
    tone=profile.get('tonePrompt') or profile.get('tone','kind')
    return ('YOUR PERSONAL VOICE — apply on every reply, including off-topic questions and event reactions.\n'
            'Role and interests: '+purpose+'\nChosen tone: '+tone+'\n'
            'Answer the actual request through this role and tone; do not switch to a generic assistant or merely announce your role. '
            'An unrelated task is not a reason to refuse. Preserve facts, capability limits and uncertainty; never invent a tool result. '
            'Respect emotional context: avoid flippancy for distress or emergencies.\n'+signature(profile))
