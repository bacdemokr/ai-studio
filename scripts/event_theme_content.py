"""Validate researched themes against retrieved sources; never fabricate gaps."""
import json
import re
import unicodedata


DESCRIPTION_LIMIT = 600

def normalized(value):
    return re.sub(r'[^\w]+', ' ', unicodedata.normalize('NFKC', value).casefold()).strip()


def theme_issues(brief, demos, research):
    """Bounded mechanical checks; semantic demo quality still needs human review."""
    sources = {s['id']: s for s in research.get('sources', [])}
    errors = {}; titles = set(); themes = set(); seen = set()
    for item in demos if isinstance(demos, list) else []:
        if not isinstance(item, dict) or item.get('topic') not in brief['topics']:
            continue
        key = item['topic']; reasons = []
        if key in seen: reasons.append('Return one activity per topic slot.')
        seen.add(key)
        for field in ('action','outcome','why','proof','risk','presenterExpertise'):
            if not isinstance(item.get(field),str) or not 0 < len(item[field].strip()) <= DESCRIPTION_LIMIT:
                reasons.append(f'{field}: provide 1–{DESCRIPTION_LIMIT} characters (received {len(item[field].strip()) if isinstance(item.get(field), str) else "non-text"}).')
        title = item.get('title', ''); theme = item.get('theme', '')
        if not isinstance(title, str) or not isinstance(theme, str):
            errors[key] = ['Provide a text title and theme.']; continue
        if not 1 <= len(theme.strip()) <= 100: reasons.append('theme: provide 1–100 characters.')
        source = sources.get(item.get('sourceId'))
        if not source: reasons.append('Cite a supplied source ID.')
        if not 5 <= len(title.strip()) <= 100: reasons.append('Use a clear title of 5–100 characters.')
        if normalized(title) in titles or normalized(theme) in themes: reasons.append('Use a distinct activity and theme, not a duplicate.')
        if re.fullmatch(r'(?:.*?agent\s*[-:—]?\s*)?(?:brief.to.plan(?: agent)?|(?:two|three|\d+).role brief check|agent handoff review|local task agents)', title.strip(), re.I):
            reasons.append('Name the concrete activity and its object instead of a workflow label.')
        activity = str(item.get('action', '')) + ' ' + str(item.get('outcome', ''))
        source_text = ' '.join(str(source.get(k, '')) for k in ('title', 'excerpt', 'article')) if source else ''
        for brand in ('Nemotron', 'Cosmos', 'Isaac', 'CUDA', 'TensorRT', 'NIM', 'RTX', 'DGX'):
            if re.search(r'\b'+brand+r'\b', title, re.I) and (not re.search(r'\b'+brand+r'\b', source_text, re.I) or not re.search(r'\b'+brand+r'\b', activity, re.I)):
                reasons.append('Use '+brand+' in the title only when the source and proposed activity actually concern it.')
        titles.add(normalized(title)); themes.add(normalized(theme))
        if reasons: errors[key] = reasons
    for key in brief['topics']:
        if key not in seen:errors[key]=['Return an activity for this slot, using supplied evidence.']
    return errors


def validate_saved_themes(brief, output, research):
    """Shared preflight and handoff checks; preserve authored text verbatim."""
    demos = output.get('demos') if isinstance(output, dict) else None
    if not isinstance(demos, list) or any(not isinstance(d, dict) for d in demos):
        raise ValueError('Save a JSON object with a demos array of objects.')
    for item in demos:
        if not isinstance(item.get('topic'), str) or item['topic'] not in brief['topics']:
            raise ValueError('Each demo topic must be one of: '+', '.join(brief['topics']))
        if not isinstance(item.get('sourceId'), str):
            raise ValueError('Each demo sourceId must be a retrieved source ID string.')
    issues = theme_issues(brief, demos, research)
    sources = {s['id']: s for s in research.get('sources', [])}
    for demo in demos:
        source = sources.get(demo['sourceId'], {})
        if not source.get('readAt') or not source.get('article') or source.get('readError'):
            issues.setdefault(demo['topic'], []).append('Read the cited article successfully before selecting it.')
    if issues:
        raise ValueError(json.dumps(issues, ensure_ascii=False))
    return output


def apply_themes(brief,calc,demos,research):
    sources={s['id']:s for s in research.get('sources',[])}
    valid={};titles=set();issues=theme_issues(brief,demos,research)
    for item in demos if isinstance(demos,list) else []:
        if not isinstance(item,dict):continue
        key=item.get('topic');source=sources.get(item.get('sourceId'))
        title=item.get('title');theme=item.get('theme')
        fields=('action','outcome','why','proof','risk','presenterExpertise')
        if key not in brief['topics'] or key in valid or not source or key in issues:continue
        if not all(isinstance(item.get(f),str) and 0<len(item[f].strip())<=DESCRIPTION_LIMIT for f in fields):continue
        if not isinstance(title,str) or not 0<len(title.strip())<=160 or not isinstance(theme,str) or not 0<len(theme.strip())<=100:continue
        if theme.strip().casefold() in titles:continue
        titles.add(theme.strip().casefold());valid[key]=item
    for topic in calc['topics']:
        item=valid.get(topic['id'])
        if not item:
            topic.update(researchStatus='unverified',risk='A complete source-backed theme was not returned. This booth is awaiting research.')
            continue
        source=sources[item['sourceId']]
        topic.update(topic=item['theme'].strip(),demo=item['title'].strip(),source=source['url'],sourceTitle=source['title'],sourceDate=source['published'],researchStatus='sourced')
        for field in ('action','outcome','why','proof','risk','presenterExpertise'):topic[field]=item[field].strip()
        for row in calc['booths']+calc['schedule']+calc.get('presenterDuty',[]):
            if row.get('topicId')==topic['id']:
                row.update(topic=topic['topic'])
                if 'demo' in row:row.update(demo=topic['demo'],presenterExpertise=topic['presenterExpertise'])
    calc['demoSource']='%d of %d themes grounded in retrieved NVIDIA sources.'%(len(valid),brief['themeCount'])
    calc['research']=research
    calc['themeChecks']=issues
