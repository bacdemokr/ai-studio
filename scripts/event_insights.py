"""Explain planning assumptions and distinguish calculations from agent opinions."""
from html import escape
import math
import event_planner


CSS = '''
.insight-grid,.reflection-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.insight,.reflection{padding:22px;border:1px solid #425560;border-radius:14px;background:#172630;overflow-wrap:anywhere}
.insight h3{margin:8px 0}.insight strong{color:#bee68c}.insight small,.reflection small{letter-spacing:1px}
.demo-reason{border-top:1px solid #425560;padding-top:12px;margin-top:18px}.demo-reason summary{cursor:pointer;color:#d4e9a9}
.demo-reason p{font-size:13px}.reflection blockquote{white-space:pre-wrap;margin:12px 0 0;color:#e0e9ef;font-size:17px}
.reflection .voice{display:block;margin-top:6px;color:#b7c7d0;font-size:12px}
'''


def design_notes(topic):
    notes = [(label, topic.get(key)) for label,key in [('Why this experience','why'),('What would prove it worked','proof'),('What still needs checking','risk')]]
    if not any(value for _,value in notes):
        return ''
    return '<details class="demo-reason" open><summary>Behind the choice</summary>'+''.join('<p><b>'+label+'</b><br>'+escape(value)+'</p>' for label,value in notes if value)+'</details>'


def insights(b, c, notes=None):
    e = lambda value: escape(str(value), quote=True)
    notes = notes or {}
    unused = c['boothCount'] * c['slots'] - len(c['schedule'])
    larger = math.ceil(b['attendees'] * 1.2)
    try:
        _, alternate = event_planner.plan({**b, 'attendees':larger})
        change = '%s attendees → %s booths, %s minutes per visit.' % (larger, alternate['boothCount'], alternate['session'])
    except ValueError:
        change = ('%s attendees exceeds the supported planning range.' if larger > 3000 else '%s attendees cannot fit within these limits, even with five-minute visits.') % larger
    cards = [
        ('THE VISITOR PROMISE', 'One visit, not every booth', 'The calculation gives each attendee one interest-based experience across the whole event. It does not promise a tour of all topics.'),
        ('SCHEDULE MARGIN', str(max(0, unused))+' unused booth slots', 'Calculated from the current rota. Spare slots are not guaranteed presenter breaks or measured model capacity.'),
        ('WHAT IF ATTENDANCE GROWS 20%?', change, 'Recalculated with the same event window, group size and booth limit. This is a planning scenario, not an attendance forecast.')]
    result = '<section class="section event-insights"><div class="sectionhead"><h2>The decisions behind this plan</h2><span class="badge">Calculated scenarios</span></div><div class="insight-grid">'
    result += ''.join('<article class="insight"><small>'+e(label)+'</small><h3>'+e(title)+'</h3><p>'+e(detail)+'</p></article>' for label,title,detail in cards)+'</div>'
    authored = [('Alex’s conclusion',notes.get('summary')),('The tradeoff',notes.get('tradeoff')),('Before opening',notes.get('check'))]
    if any(value for _,value in authored):
        result += '<div class="insight-grid" style="margin-top:14px">'+''.join('<article class="insight"><small>AGENT INTERPRETATION</small><h3>'+e(title)+'</h3><p>'+e(value)+'</p></article>' for title,value in authored if value)+'</div>'
    return result+'</section>'


def reflections(meeting):
    if not meeting or not meeting.get('members'):
        return ''
    result = '<section class="section event-reflections"><div class="sectionhead"><h2>Your agents’ take</h2><span class="badge">Personal perspectives</span></div><p>The Captain invited your hired agents to react to this package. These are opinions about the supplied plan, not independent tests.</p><div class="reflection-grid">'
    for member in meeting['members']:
        reply = meeting.get('replies', {}).get(member['key'], {})
        answer = reply.get('answer') or reply.get('error') or ('Roundtable stopped before this reaction.' if meeting.get('status') == 'cancelled' else 'Waiting for the completed package.' if meeting.get('status') == 'invited' else 'Reaction pending.')
        result += '<article class="reflection"><strong>'+escape(member['name'])+'</strong><span class="voice">'+escape(member.get('tonePrompt') or member.get('tone',''))+'</span><blockquote>'+escape(answer)+'</blockquote></article>'
    return result+'</div></section>'
