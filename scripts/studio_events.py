"""Event package artifacts and anonymous, owner-scoped audience feedback."""
import hashlib
import json
import re
import secrets
import time
from html import escape
from email.message import EmailMessage
from email.policy import SMTP

import event_planner as planner


def object_reply(answer):
    candidates = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', answer, re.S) + [answer]
    for raw in candidates:
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                return value
        except (ValueError, TypeError):
            pass
    return {}


def short(value, default, limit=500):
    return value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= limit and '\x00' not in value else default


class EventControls:
    def event_plan(self, data):
        from studio import Problem
        try:
            brief, calc = planner.plan(data.get('brief', data))
            return {'brief': brief, 'capacity': calc}
        except ValueError as error:
            raise Problem(str(error))

    def event_stage_files(self, owner, job_id, payload, stage, answer):
        from studio import safe_file
        b, calc = payload['brief'], payload['capacity']
        if b.get('schema') != 2:
            return
        files = payload.setdefault('packageFiles', [])
        stem = job_id[:6]
        def save(name, content):
            relative = 'artifacts/' + stem + '-' + name
            target = safe_file(self.workspace(owner), relative)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content, encoding='utf-8')
            if relative not in files:
                files.append(relative)
            return relative
        if stage == 1:
            demos=object_reply(answer).get('demos', [])
            refined={}
            if isinstance(demos,list):
                for item in demos[:6]:
                    if isinstance(item,dict) and item.get('topic') in b['topics'] and isinstance(item.get('title'),str) and 0 < len(item['title']) <= 200:
                        refined[item['topic']]=item
            for topic in calc['topics']:
                item=refined.get(topic['id'])
                if not item:
                    continue
                topic['demo']=item['title']
                topic['presenterExpertise']=short(item.get('presenterExpertise'),'Topic specialist',200)
                for row in calc['booths']+calc['schedule']:
                    if row['topic']==topic['topic']:
                        row['demo']=topic['demo']
                        row['presenterExpertise']=topic['presenterExpertise']
            calc['demoSource']='Demo producer refined %d of %d concepts; other concepts use catalog starting points.' % (len(refined),len(b['topics']))
        if stage == 2:
            save('presenter-rota.xlsx', planner.workbook(b, calc))
            save('presenter-rota.csv', planner.rota_csv(calc))
            save('booth-plan.json', json.dumps({'brief': b, 'capacity': calc}, indent=2))
        if stage == 3:
            content = object_reply(answer)
            subject = short(content.get('subject'), 'Build a Claw · '+b['city'], 160).replace('\r',' ').replace('\n',' ')
            body = short(content.get('body'), answer, 20000)
            venue = content.get('venue') if isinstance(content.get('venue'), dict) else {}
            url = short(venue.get('url'), '', 500)
            if not re.match(r'^https://[^\s<>]+$', url):
                url = ''
            campaign = {'subject': subject, 'body': body, 'venue': {'name': short(venue.get('name'), 'Venue to be researched', 150), 'url': url, 'status': 'Candidate only · booking and capacity unconfirmed'}, 'structured': bool(content.get('body'))}
            payload['campaign'] = campaign
            mail=EmailMessage(policy=SMTP)
            mail['Subject']=subject;mail['X-Unsent']='1'
            mail.set_content('DRAFT — recipients, date, venue booking and registration link need review. Nothing has been sent.\n\n'+body)
            save('invitation.eml', mail.as_bytes())
            save('invitation.html', '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Invitation draft</title><style>body{font:18px/1.7 system-ui;max-width:760px;margin:40px auto;padding:24px;color:#17232a;background:#f4f7fa}small{color:#4b6341}article{white-space:pre-wrap}h1{line-height:1.2}</style><small>INVITATION DRAFT · NOT SENT · VENUE UNCONFIRMED</small><h1>'+escape(subject)+'</h1><article>'+escape(body)+'</article></html>')
        if stage == 4:
            draft = object_reply(answer).get('survey', {})
            if not isinstance(draft, dict):
                draft = {}
            definition = {'title': short(draft.get('title'), 'Your BaC interests · '+b['city'], 160),
                'intro': short(draft.get('intro'), 'Help us shape the demos. No name or email is collected.'),
                'topicQuestion': short(draft.get('topicQuestion'), 'Which demo would you most like to explore?', 160),
                'experienceQuestion': short(draft.get('experienceQuestion'), 'How familiar are you with AI agents?', 160),
                'ratingQuestion': short(draft.get('ratingQuestion'), 'How useful does this event sound?', 160),
                'topics': [{'id': t, 'title': planner.TOPICS[t]['title']} for t in b['topics']],
                'language': b['language'], 'authorship': 'Agent-drafted questions' if draft else 'Built-in fallback questions · English'}
            with self.db() as db:
                existing = db.execute('SELECT token FROM event_surveys WHERE job=?', (job_id,)).fetchone()
                token = existing['token'] if existing else secrets.token_urlsafe(24)
                db.execute('INSERT OR REPLACE INTO event_surveys VALUES (?,?,?,?,?)', (token, owner, job_id, json.dumps(definition), time.time()))
            payload['survey'] = {'path': '/survey/'+token, 'authorship': definition['authorship']}
            save('survey-questions.json', json.dumps(definition, ensure_ascii=False, indent=2))

    def survey_definition(self, token):
        from studio import Problem
        if not isinstance(token, str) or not re.fullmatch(r'[\w-]{32}', token):
            raise Problem('Survey not found.', 404)
        with self.db() as db:
            row=db.execute('SELECT s.* FROM event_surveys s JOIN agents a ON a.id=s.owner WHERE s.token=? AND a.deleting=0', (token,)).fetchone()
        if not row:
            raise Problem('Survey not found.', 404)
        return json.loads(row['definition'])

    def survey_answer(self, token, data):
        from studio import Problem
        definition = self.survey_definition(token)
        visitor=data.get('visitor')
        if not isinstance(visitor, str) or not re.fullmatch(r'[a-f0-9]{32}', visitor):
            raise Problem('Reload the survey to create an anonymous response ID.')
        topic=data.get('topic');experience=data.get('experience');rating=data.get('rating')
        if topic not in [t['id'] for t in definition['topics']] or experience not in ('new','some','experienced') or type(rating) is not int or not 1 <= rating <= 5:
            raise Problem('Answer all three questions.')
        fingerprint=hashlib.sha256((token+visitor).encode()).hexdigest()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT count(*) FROM survey_responses WHERE token=?', (token,)).fetchone()[0] >= 5000 and not db.execute('SELECT 1 FROM survey_responses WHERE token=? AND visitor=?', (token, fingerprint)).fetchone():
                raise Problem('This survey has reached its response limit.', 429)
            db.execute('INSERT OR REPLACE INTO survey_responses VALUES (?,?,?,?,?,?)', (token,fingerprint,topic,experience,rating,time.time()))
        return {'saved': True}

    def survey_report(self, owner, job_id):
        from studio import Problem
        with self.db() as db:
            row=db.execute('SELECT * FROM event_surveys WHERE owner=? AND job=?', (owner,job_id)).fetchone()
            if not row:
                raise Problem('This mission has no survey yet.', 404)
            definition=json.loads(row['definition'])
            counts=dict(db.execute('SELECT topic,count(*) FROM survey_responses WHERE token=? GROUP BY topic', (row['token'],)).fetchall())
            total, rating=db.execute('SELECT count(*),avg(rating) FROM survey_responses WHERE token=?', (row['token'],)).fetchone()
        return {'total': total, 'rating': round(rating,1) if rating is not None else None,
                'topics': [{**t,'count':counts.get(t['id'],0)} for t in definition['topics']], 'path':'/survey/'+row['token']}

    def survey_replan(self, owner, data):
        from studio import Problem
        job_id=data.get('id')
        report=self.survey_report(owner, job_id)
        if not report['total']:
            raise Problem('Collect at least one response before replanning.')
        with self.db() as db:
            row=db.execute('SELECT payload,status FROM jobs WHERE owner=? AND id=?', (owner,job_id)).fetchone()
        if not row or row['status'] != 'done':
            raise Problem('Finish the original mission before replanning.',409)
        payload=json.loads(row['payload']);brief=dict(payload['brief'])
        counts={t['id']:t['count'] for t in report['topics']}
        brief['topicWeights']=[counts.get(t,0) for t in brief['topics']]
        members={str(i):m['key'] for i,m in enumerate(payload.get('roster',[])) if i and m.get('key')}
        # A fresh mission preserves the original package and uses the same chosen crew.
        result=self.enqueue(owner, {'kind':'crew','brief':brief,'members':members,'preset':payload.get('preset',False)}, source='survey:'+job_id)
        self.event(result['id'], 'Audience interests received', str(report['total'])+' anonymous responses inform this plan. Small samples are directional; total attendance is unchanged.')
        return result


def survey_page(token, definition):
    """Standalone LAN page; no model HTML runs with access to the participant API."""
    title=escape(definition['title'])
    options=''.join('<option value="'+escape(t['id'])+'">'+escape(t['title'])+'</option>' for t in definition['topics'])
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+title+'''</title><style>body{font:18px/1.6 system-ui;background:#0d141b;color:#eef4fa;margin:0;padding:30px}main{max-width:620px;margin:5vh auto}small{color:#a9cf83}h1{font-size:34px;line-height:1.2}label{display:block;margin:24px 0 8px}select,button{box-sizing:border-box;font:inherit;padding:14px;width:100%;border-radius:5px;border:1px solid #526577;background:#182631;color:#eff5fc}button{background:#76b900;color:#101809;font-weight:700;margin-top:30px;cursor:pointer}p{color:#b9cbd9}#notice{color:#d4eab4}</style><main><small>BUILD A CLAW / YOUR VOICE</small><h1>'''+title+'''</h1><p>'''+escape(definition['intro'])+'''</p><form id="survey"><label for="topic">'''+escape(definition['topicQuestion'])+'''</label><select id="topic" required><option value="">Choose a topic</option>'''+options+'''</select><label for="experience">'''+escape(definition['experienceQuestion'])+'''</label><select id="experience" required><option value="">Choose one</option><option value="new">New to agents</option><option value="some">Tried a few</option><option value="experienced">Build them regularly</option></select><label for="rating">'''+escape(definition['ratingQuestion'])+'''</label><select id="rating" required><option value="">Choose a rating</option><option value="5">5 · Very useful</option><option value="4">4</option><option value="3">3</option><option value="2">2</option><option value="1">1 · Not useful yet</option></select><button>Share my feedback</button></form><p id="notice" role="status"></p><p>No name or email is collected. Resubmitting from this browser updates your response. The event host sees aggregate results. This link works while the event’s Spark server is reachable.</p></main><script>
let visitor;const key='''+json.dumps('bac-survey-'+token)+''';try{visitor=localStorage.getItem(key);}catch{}if(!/^[a-f0-9]{32}$/.test(visitor||'')){visitor=Array.from(crypto.getRandomValues(new Uint8Array(16)),x=>x.toString(16).padStart(2,'0')).join('');try{localStorage.setItem(key,visitor);}catch{}}
document.querySelector('form').onsubmit=async event=>{event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;try{const response=await fetch(location.pathname,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({visitor,topic:document.getElementById('topic').value,experience:document.getElementById('experience').value,rating:Number(document.getElementById('rating').value)})});const result=await response.json();if(!response.ok)throw Error(result.error||'Please try again.');document.getElementById('notice').textContent='Thank you. Your response is saved.';}catch(error){document.getElementById('notice').textContent=error.message;}finally{button.disabled=false;}};
</script></html>'''
