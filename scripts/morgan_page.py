"""Morgan authors HTML; the studio validates it and inserts the supplied timetable."""
import hashlib
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

from nvidia_event_page import render

MODE = 'agent-html-v1'
TOKENS = ('MORGAN_HEADLINE', 'MORGAN_INTRO', 'MORGAN_CTA', 'MORGAN_PROGRAM_TITLE', 'MORGAN_PROMOTION_TITLE', 'MORGAN_SOCIAL_POST')
SCHEDULE_MOUNT='<section class="section" id="schedule"><h2>Presenter timetable</h2><!-- The app inserts Alex’s validated timetable here. Keep this block unchanged. --></section>'
POST_MOUNT='<!-- BAC:SOCIAL_POST -->'
SCHEDULE_MOUNT_ASCII=SCHEDULE_MOUNT.replace('Alex’s','Alex\'s')


def protected_pattern(key):
    return r'<!-- BAC:'+key+r' -->.*?<!-- /BAC:'+key+r' -->'


def repair_blocks(payload, error):
    """Give the model the exact trusted block it must restore, not a vague hint."""
    original=starter(payload)
    blocks=[]
    for key in ('LOGISTICS','SCHEDULE'):
        if 'Restore the exact BAC:'+key+' block' in str(error):
            blocks.extend(re.findall(protected_pattern(key),original,re.S))
    return ('\nRestore these exact original blocks; preserve all other authored content:\n'
            + '\n'.join('```html\n'+block+'\n```' for block in blocks)) if blocks else ''


def enabled(payload):
    return payload.get('pageMode') == MODE


def paths(job):
    return {'html': 'artifacts/'+job+'-event-page.html', 'post': 'artifacts/'+job+'-linkedin-post.txt'}


def starter(payload):
    import agent_workflow
    if agent_workflow.enabled(payload):
        from event_dates import date_label
        b=payload['brief'];css=(__import__('pathlib').Path(__file__).resolve().parents[1]/'skills/bac-nvidia-webpage/assets/event.css').read_text()
        logistics='<p class="logistics">'+escape(' · '.join([b['city'],date_label(b),b['startTime'],b.get('venue') or 'Venue TBC']))+'</p>'
        return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            '<title>Build-a-Claw</title><style>'+css+'</style></head><body>'
            '<header class="hero"><div class="wrap"><h1>MORGAN_HEADLINE</h1><!-- BAC:LOGISTICS -->'+logistics+'<!-- /BAC:LOGISTICS -->'
            '<p>MORGAN_INTRO</p><a class="cta" href="#program">MORGAN_CTA</a></div></header>'
            '<main class="wrap"><section class="section" id="program"><h2>MORGAN_PROGRAM_TITLE</h2><!-- Author the demo cards here from Dylan’s themes. --></section>'
            '<!-- BAC:SCHEDULE -->'+SCHEDULE_MOUNT+'<!-- /BAC:SCHEDULE -->'
            '<section class="section" id="promotion"><h2>MORGAN_PROMOTION_TITLE</h2><div class="social-post"><div class="social-content"><p style="white-space:pre-line">'+POST_MOUNT+'</p></div></div></section></main></body></html>')
    campaign = dict(headline=TOKENS[0], intro=TOKENS[1], body=TOKENS[5], hashtags=[])
    html = render(payload['brief'], payload['capacity'], payload['outputs'], campaign, payload.get('decisionNotes'))
    html = html.replace('Explore the experiences', TOKENS[2]).replace('Choose what sparks your curiosity', TOKENS[3]).replace('A reason to join. A story to share.', TOKENS[4])
    # These two fragments are source data, not model-authored calculations/logistics.
    for key, pattern in [('LOGISTICS', r'<p class="logistics">.*?</p>'), ('SCHEDULE', r'<section class="section" id="schedule">.*?</section>')]:
        html = re.sub(pattern, lambda m:'<!-- BAC:'+key+' -->'+m[0]+'<!-- /BAC:'+key+' -->', html, count=1, flags=re.S)
    html = html.replace('schedule and page assembled by the studio.', 'page authored by Morgan using a starter; verified schedule supplied by the studio.')
    # This starter does not include later roundtable replies. Results displays those separately.
    html = html.replace('<a href="#agents">Your agents</a>', '')
    return html


def prepare(workspace, job, payload):
    import json
    from studio import safe_file
    files = paths(job)
    html = starter(payload)
    for key in files:
        target = safe_file(workspace, files[key])
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise RuntimeError('Morgan output path is a symbolic link.')
    safe_file(workspace, files['html']).write_text(html, encoding='utf-8')
    safe_file(workspace, 'inbox/morgan-page-starter.html').write_text(html, encoding='utf-8')
    safe_file(workspace, files['post']).write_text('MORGAN_SOCIAL_POST\n', encoding='utf-8')
    contract = {'files': files, 'brief': payload['brief'], 'themes': payload['capacity']['topics'],
                'replaceAll': TOKENS, 'protectedBlocks': ['BAC:LOGISTICS', 'BAC:SCHEDULE'],
                'programLayout': 'Use .cards > article.theme-card > .theme-body. In each body: small topic label, h3 exact demo title, p.demo-meta for booth and visit minutes, action paragraph, div.outcome for the result, p.source with a short Read the research link (full source title in title and aria-label), and closed details.demo-reason for the limitation. Localize labels. Keep supplied CSS. No theme-art, oversized numbers, decorative banners or repeated topic labels.',
                'instructions': 'Edit the HTML file itself. Preserve both protected blocks exactly. Write the LinkedIn post file. No publishing. Final reply: a short human-readable summary.'}
    import agent_workflow
    if agent_workflow.enabled(payload):
        from event_page_sections import draft_files
        contract['sectionEditor'] = 2
        contract['sectionFiles'] = draft_files(files['html'], len(contract['themes']))
        contract['instructions'] = ('Write sectionFiles.copy once as a JSON object with headline, intro, cta, program-title and promotion-title. Write each sectionFiles.card-N as raw HTML: one article.theme-card under 6000 characters, in themes order. Use native write calls only; distinct files can be written together. The app collects and applies these files after your turn, escapes text, removes card IDs and retains aria-hidden. No patch file, apply/status command, shell, full-page read or manual assembly. Preserve the saved LinkedIn post. Stop after successful writes with a brief receipt. On repair, rewrite only files/fields named in the errors; accepted sections remain saved.')
        contract['scheduleSummary']={k:payload['capacity'].get(k) for k in ('session','boothCount','presenterCount','scheduleCriteria','staffingPolicy')}
        contract['scheduleSelected']='2' in payload.get('outputs',{})
    safe_file(workspace, 'inbox/morgan-page.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')
    payload['pageDraft'] = {'sectionEditor':contract.get('sectionEditor'), 'files':files, 'starterSHA256':hashlib.sha256(html.encode()).hexdigest(), 'status':'writing', 'attempts':0}


class PageError(RuntimeError):
    pass


def collect_draft(workspace, payload):
    if payload.get('pageDraft', {}).get('sectionEditor') != 2:
        return
    from event_page_sections import collect
    try:
        result = collect(workspace)
    except (ValueError, OSError, TypeError, KeyError) as error:
        raise PageError('Could not collect page sections: ' + str(error)) from error
    if result['status'] != 'complete':
        errors = [key + ': ' + value + ' [' + result['files'].get(key, result['files']['copy']) + ']'
                  for key, value in result['errors'].items()]
        if result['missing']:
            errors.append('Missing sections: ' + ', '.join(result['missing']))
        raise PageError('\n'.join(errors)[:2500])


class Inspect(HTMLParser):
    VOID_TAGS={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.errors=[];self.ids=set();self.anchors=[];self.text=[];self.h1=[];self.in_h1=False;self.h1_count=0;self.paragraphs=[];self.paragraph=None;self.source_paragraphs=[];self.paragraph_source=False;self.tags=set();self.viewport=False;self.csp=False
        self.elements=[];self.section_text={};self.section_links={};self.post_mounts=[]
    def content_sections(self):
        tags={tag for tag,_ in self.elements}
        if 'body' not in tags or tags.intersection({'head','style','script','template'}):return set()
        return {identifier for _,identifier in self.elements if identifier}
    def handle_starttag(self,tag,attrs):
        self.tags.add(tag)
        d=dict(attrs)
        if tag not in self.VOID_TAGS:self.elements.append((tag,d.get('id')))
        if tag=='a' and d.get('href'):
            for section in self.content_sections():self.section_links.setdefault(section,set()).add(d['href'])
        if tag in ('script','iframe','object','embed','base','form','input','button','textarea','select','link','audio','video','source'):
            self.errors.append('Remove active or external element: '+tag)
        if tag=='meta' and d.get('http-equiv','').lower() not in ('','content-security-policy'):
            self.errors.append('Remove redirect/refresh metadata.')
        if tag=='meta' and d.get('name','').lower()=='viewport':self.viewport=True
        if tag=='meta' and d.get('http-equiv','').lower()=='content-security-policy':
            self.csp = d.get('content')=="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
        if tag=='h1':self.in_h1=True;self.h1_count+=1
        if tag=='p':self.paragraph=[];self.paragraph_source='source' in d.get('class','').split()
        if tag=='a' and self.paragraph is not None and urlsplit(d.get('href','')).hostname=='blogs.nvidia.com':self.paragraph_source=True
        if 'id' in d:
            if d['id'] in self.ids:self.errors.append('Duplicate section ID: '+d['id'])
            self.ids.add(d['id'])
        for key,value in attrs:
            value=value or ''
            if key.lower().startswith('on') or key in ('srcdoc','action','formaction'):
                self.errors.append('Remove active HTML attribute: '+key)
            if key in ('href','xlink:href','src','srcset'):
                if tag=='a' and key=='href':
                    if value.startswith('#'):self.anchors.append(value[1:])
                    elif urlsplit(value).scheme!='https' or not urlsplit(value).hostname:self.errors.append('Use HTTPS or an existing section anchor for links.')
                elif not (tag=='img' and key=='src' and re.match(r'^data:image/(png|jpeg|webp);base64,',value)):
                    self.errors.append('Keep the page self-contained; remove external resources.')
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in self.VOID_TAGS:self.handle_endtag(tag)
    def handle_endtag(self,tag):
        if tag=='h1':self.in_h1=False
        if tag=='p' and self.paragraph is not None:
            value=' '.join(''.join(self.paragraph).split());self.paragraphs.append(value)
            if self.paragraph_source:self.source_paragraphs.append(value)
            self.paragraph=None
        for i in range(len(self.elements)-1,-1,-1):
            if self.elements[i][0]==tag:
                del self.elements[i:]
                break
    def handle_comment(self,value):
        if value.strip()=='BAC:SOCIAL_POST':self.post_mounts.append(self.content_sections())
    def handle_data(self,value):
        self.text.append(value)
        for section in self.content_sections():self.section_text.setdefault(section,[]).append(value)
        if self.paragraph is not None:self.paragraph.append(value)
        if self.in_h1:self.h1.append(value)


def read_output(workspace, relative, limit):
    from studio import safe_file, Problem
    try:
        path=safe_file(workspace,relative,exists=True)
        if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:
            raise ValueError('Invalid output size or file type')
        return path.read_bytes().decode('utf-8')
    except (OSError, ValueError, Problem) as error:
        raise PageError('Write a valid UTF-8 file at '+relative+'.') from error


def validate(workspace,job,payload):
    import agent_workflow
    assembled=agent_workflow.enabled(payload)
    files=paths(job)
    html=read_output(workspace,files['html'],512000)
    post=read_output(workspace,files['post'],16000).strip()
    errors=[]
    if any(t in html or t in post for t in TOKENS):errors.append('Replace every MORGAN_* placeholder in both files.')
    if len(post)<40:errors.append('Write the LinkedIn post, not only a title.')
    if payload.get('socialDraft',{}).get('status')=='ready' and post!=payload['socialDraft']['text']:
        errors.append('Restore the already shared LinkedIn draft unchanged in the post file.')
    original=starter(payload)
    for key in ('LOGISTICS','SCHEDULE'):
        pattern=protected_pattern(key)
        expected=re.findall(pattern,original,re.S)
        actual=re.findall(pattern,html,re.S)
        if assembled and key=='SCHEDULE':
            # Only this known inert comment variant is equivalent. Keep markup,
            # visible text, marker count, and schedule data strictly protected.
            actual=[block.replace(SCHEDULE_MOUNT_ASCII,SCHEDULE_MOUNT) for block in actual]
        if not expected or actual!=expected:errors.append('Restore the exact BAC:'+key+' block from the starter; do not recalculate or change it.')
    parser=Inspect()
    try:parser.feed(html);parser.close()
    except Exception:errors.append('Write parseable HTML.')
    errors+=parser.errors
    if not {'html','head','title','body','h1','style'}.issubset(parser.tags) or not parser.viewport:
        errors.append('Keep a complete HTML document with title, inline CSS, viewport metadata and a visible h1.')
    if not {'program','schedule','promotion'}.issubset(parser.ids):errors.append('Keep program, schedule and promotion section IDs for Results navigation.')
    if any(anchor and anchor not in parser.ids for anchor in parser.anchors):errors.append('Fix broken in-page anchor links.')
    if re.search(r'@import|url\s*\(|expression\s*\(',html,re.I):errors.append('Do not load external CSS/resources or use CSS expressions.')
    if not parser.csp:errors.append('Keep the exact starter Content-Security-Policy metadata.')
    visible=' '.join(' '.join(parser.text).split())
    if assembled:
        if html.count(POST_MOUNT)!=1 or len(parser.post_mounts)!=1 or 'promotion' not in parser.post_mounts[0]:
            errors.append('Keep one BAC:SOCIAL_POST marker in the promotion section; write the post to its text file.')
    elif ' '.join(post.split()) not in visible:errors.append('Include the same LinkedIn post in the page promotion section.')
    headline=' '.join(''.join(parser.h1).split())
    if not headline:errors.append('Write a nonempty visible headline.')
    if len(headline)>100 or len(headline.split())>16:errors.append('Shorten the headline to at most 100 characters and 16 words.')
    if parser.h1_count!=1:errors.append('Use exactly one main h1 headline.')
    # Ignore exact schedule/source text: check Morgan-authored prose only.
    protected_text=Inspect();protected_text.feed(original)
    paragraphs=[t for t in parser.paragraphs if len(t)>100 and t not in protected_text.paragraphs and t not in parser.source_paragraphs]
    if len(paragraphs)!=len(set(paragraphs)):errors.append('Remove duplicated promotional paragraphs; each section needs a distinct purpose.')
    if '@media' not in html:errors.append('Keep responsive CSS for narrow screens.')
    if not re.search(r'</html>\s*$',html,re.I):errors.append('Complete the document through its closing html tag.')
    program_text=' '.join(' '.join(parser.section_text.get('program',[])).split()) if assembled else visible
    for topic in payload['capacity']['topics']:
        if ' '.join(topic['demo'].split()) not in program_text:errors.append('Preserve Dylan’s demo title in the program section: '+topic['demo'])
        source_present=topic.get('source') in parser.section_links.get('program',set()) if assembled else escape(topic.get('source',''),quote=True) in html
        if topic.get('source') and not source_present:errors.append('Preserve the supplied research source link for '+topic['demo'])
    if assembled and '2' in payload.get('outputs',{}) and not payload.get('scheduleFragment'):
        errors.append('Alex’s selected timetable is missing; restore the validated schedule before completing the page.')
    if hashlib.sha256(html.encode()).hexdigest()==payload['pageDraft']['starterSHA256']:errors.append('Edit the actual HTML starter before handing it over.')
    if errors:raise PageError('\n'.join(dict.fromkeys(errors))[:2500])
    source=html
    if assembled:
        schedule=payload.get('scheduleFragment') or '<section class="section" id="schedule"><h2>Timetable</h2><p>No scheduling contribution was selected.</p></section>'
        html=html.replace(SCHEDULE_MOUNT,schedule).replace(SCHEDULE_MOUNT_ASCII,schedule).replace(POST_MOUNT,escape(post))
        final=Inspect();final.feed(html);final.close()
        if final.errors or not {'program','schedule','promotion'}.issubset(final.section_text):
            raise PageError('The assembled webpage is incomplete or invalid. '+ '; '.join(final.errors))
        if ' '.join(post.split()) not in ' '.join(' '.join(final.section_text['promotion']).split()):
            raise PageError('The assembled webpage is missing the LinkedIn post in its promotion section.')
    return {'html':html,'sourceHtml':source,'sourceSHA256':hashlib.sha256(source.encode()).hexdigest(),'post':post,'headline':''.join(parser.h1).strip()[:160], 'sha256':hashlib.sha256(html.encode()).hexdigest()}
