"""Offline event landing page: agent-authored copy, authoritative event facts."""
from html import escape

LABELS = dict(program='Explore the demos', agenda='Your day, at a glance', agendaNote='First sessions at each booth. Groups rotate throughout the event.', venue='Meet us in',
              explore='Explore the program', draft='Event page draft', datePending='Date to be confirmed',
              venuePending='Venue to be confirmed', minutes='minutes / day', attendees='attendees',
              days='days', booth='Booth', day='Day', venueCandidate='Venue candidate · booking unconfirmed',
              registrationPending='Registration details coming soon')


def render_page(brief, capacity, campaign, content):
    for key, limit in [('headline', 120), ('intro', 700), ('highlight', 220)]:
        if not isinstance(content.get(key), str) or not 0 < len(content[key].strip()) <= limit:
            raise ValueError('Event page needs valid '+key+' copy from the web developer.')
    e = lambda value: escape(str(value), quote=True)
    supplied = content.get('labels', {})
    supplied = supplied if isinstance(supplied, dict) else {}
    labels = {key:e(supplied[key]) if isinstance(supplied.get(key),str) and 0<len(supplied[key])<=120 else e(value)
              for key,value in LABELS.items()}
    lang = {'English':'en','German':'de','French':'fr','Korean':'ko','Japanese':'ja'}.get(brief['language'],'en')
    cards = ''.join('<article><span class="index">0'+str(i+1)+'</span><h3>'+e(t['topic'])+'</h3><p>'+e(t['demo'])+'</p></article>'
                    for i,t in enumerate(capacity['topics']))
    # Present the first visit per day/booth; repeated rotations are in the downloadable rota.
    seen=set(); rows=[]
    for visit in capacity['schedule']:
        key=(visit['day'], visit['booth'])
        if key in seen: continue
        seen.add(key)
        rows.append('<div class="slot"><span>'+labels['day']+' '+e(visit['day'])+'<br><b>'+e(visit['start'])+'–'+e(visit['end'])+'</b></span><div><small>'+labels['booth']+' '+e(visit['booth'])+'</small><h3>'+e(visit['demo'])+'</h3><p>'+e(visit['topic'])+'</p></div></div>')
    venue=(campaign or {}).get('venue',{}).get('name') or brief.get('venue')
    venue_text=e(venue) if venue else labels['venuePending']
    facts=''.join('<div><strong>'+e(value)+'</strong><span>'+labels[label]+'</span></div>' for value,label in
                  [(brief['attendees'],'attendees'),(brief['duration'],'minutes'),(brief['days'],'day' if brief['days']==1 else 'days')])
    return '''<!doctype html>
<html lang="'''+lang+'''"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'">
<title>Build-a-Claw · '''+e(brief['city'])+'''</title><style>
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#0b0e11;color:#f4f6f8;font:17px/1.6 Arial,sans-serif}a{color:inherit}header,main,footer{max-width:1200px;margin:auto;padding:24px 6%}header{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #2c343d;gap:20px}header strong{font-size:23px;letter-spacing:-1px}header small{color:#b9c4cc}.hero{min-height:540px;display:grid;grid-template-columns:1.4fr 1fr;gap:40px;align-items:center;padding:68px 0}.eyebrow{color:#a4db3f;font-weight:bold;font-size:13px;letter-spacing:2px;text-transform:uppercase}h1{font-size:clamp(40px,6vw,76px);line-height:1.04;letter-spacing:-3px;margin:24px 0}p{color:#b9c4cc;max-width:700px}.cta{display:inline-block;text-decoration:none;background:#76b900;color:#081000;padding:13px 23px;font-weight:bold;margin-top:20px}.art{position:relative;height:340px;background:radial-gradient(ellipse at 50% 70%,#76b90024,transparent 65%);display:grid;place-items:center;overflow:hidden}.art span{position:absolute;width:190px;height:190px;border:1px solid #8ed327;transform:rotate(-30deg) skew(15deg,15deg);box-shadow:28px 28px 0 #253d15,56px 56px 0 #152514;background:linear-gradient(135deg,#76b90033,#76b90005)}.art span:nth-child(2){width:110px;height:110px;transform:translateY(-50px) rotate(-30deg) skew(15deg,15deg);background:#91c92e55}.art b{position:absolute;bottom:4px;left:15%;right:0;color:#9aacbd;font-size:12px;letter-spacing:4px}.facts{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #35404b;border-bottom:1px solid #35404b;padding:28px 0;gap:24px}.facts strong{display:block;font-size:38px;line-height:1.2}.facts span{color:#9caab7}section{padding:64px 0;border-bottom:1px solid #29313b}h2{font-size:34px;line-height:1.2;letter-spacing:-1px;margin:8px 0 28px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px}article{padding:24px;background:#151c23;border:1px solid #2b3742;min-height:230px}.index{color:#95d12b;font-size:14px}h3{font-size:22px;line-height:1.3}.highlight{border-left:3px solid #76b900;padding:16px 24px;font-size:22px;margin-top:35px;color:#e2e8ec}.slot{display:grid;grid-template-columns:160px 1fr;gap:24px;padding:24px 0;border-bottom:1px solid #29313b}.slot h3,.slot p{margin:5px 0}.slot small{color:#a4db3f}.venue{display:grid;grid-template-columns:1fr 1fr;gap:40px}.notice{background:#17220f;border:1px solid #3c5428;padding:24px}.notice p{margin:0}footer{font-size:13px;color:#9caab7;padding-block:30px}@media(max-width:650px){header small{max-width:130px;text-align:right}.hero{grid-template-columns:1fr;padding:44px 0;gap:12px}.art{height:210px}.art span{width:130px;height:130px}h1{letter-spacing:-1.7px}.facts strong{font-size:29px}.facts span{font-size:13px}.venue{grid-template-columns:1fr}.slot{grid-template-columns:100px 1fr;gap:12px}section{padding:44px 0}h2{font-size:28px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style></head><body><header><strong>Build-a-Claw</strong><small>'''+labels['draft']+'''</small></header><main>
<div class="hero"><div><div class="eyebrow">'''+e(brief['city'])+'''</div><h1>'''+e(content['headline'])+'''</h1><p>'''+e(content['intro'])+'''</p><a class="cta" href="#program">'''+labels['explore']+''' ↗</a></div><div class="art" aria-hidden="true"><span></span><span></span><b>BUILD / CONNECT / CREATE</b></div></div>
<div class="facts">'''+facts+'''</div><section id="program"><h2>'''+labels['program']+'''</h2><div class="cards">'''+cards+'''</div><p class="highlight">'''+e(content['highlight'])+'''</p></section>
<section id="agenda"><h2>'''+labels['agenda']+'''</h2><p>'''+labels['agendaNote']+'''</p>'''+''.join(rows)+'''</section>
<section class="venue"><div><div class="eyebrow">'''+labels['venue']+'''</div><h2>'''+e(brief['city'])+'''</h2><h3>'''+venue_text+'''</h3><p>'''+labels['venueCandidate']+'''</p></div><div class="notice"><h3>'''+labels['datePending']+'''</h3><p>'''+labels['registrationPending']+'''</p></div></section></main><footer>Build-a-Claw · '''+labels['draft']+'''</footer></body></html>'''
