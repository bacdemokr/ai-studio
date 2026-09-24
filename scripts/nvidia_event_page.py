"""NVIDIA-public-page-informed template, rendered from validated event data."""
from html import escape
from event_dates import date_label, day_label
from pathlib import Path
import event_insights
from event_rotation import duty_grids, PRESENTER_COLORS

CSS=(Path(__file__).resolve().parents[1]/'skills/bac-nvidia-webpage/assets/event.css').read_text()
COLORS=PRESENTER_COLORS
e=lambda v:escape(str(v),quote=True)

from event_timetable import tables


def theme_card(topic, index, minutes):
    """Compact session card; all factual copy still comes from the handoff."""
    source = ('<p class="source"><a href="'+e(topic['source'])+'" target="_blank" rel="noopener noreferrer" title="'+e(topic['sourceTitle'])+'" aria-label="Read research: '+e(topic['sourceTitle'])+'">Read the research <span class="link-arrow" aria-hidden="true">↗</span></a></p>') if topic.get('sourceTitle') else '<p class="pending">Source-backed theme pending.</p>'
    return ('<article class="theme-card"><div class="theme-body"><small>'+e(topic['topic'])+'</small>'
            '<h3>'+e(topic['demo'])+'</h3><p class="demo-meta">Booth '+str(index+1)+' · '+e(minutes)+' min</p>'
            '<p>'+e(topic.get('action','Dylan is reviewing current NVIDIA themes.'))+'</p>'
            '<div class="outcome"><b>What you’ll take away</b><p>'+e(topic.get('outcome','A concrete participant outcome will appear with the researched theme.'))+'</p></div>'
            +source+event_insights.design_notes(topic).replace(' open','')+'</div></article>')


def render(b,c,outputs,campaign=None,decision_notes=None,roundtable=None):
    campaign=campaign or {}
    title=campaign.get('headline') or 'Build Your Next AI Agent'
    intro=campaign.get('intro') or 'Explore practical agent workflows, try a focused demo, and see what it takes to make the result trustworthy.'
    cards=[theme_card(t,i,c['session']) for i,t in enumerate(c['topics'])]
    research=c.get('research',{})
    note=' · '.join(filter(None,[c.get('demoSource','Live theme research has not completed.'),'Retrieved '+research['retrieved'][:10] if research.get('retrieved') else '']))
    post=('<article class="social-post"><div class="social-author"><div class="social-avatar">BaC</div><div><b>Build-a-Claw · '+e(b['city'])+'</b><small>LinkedIn post draft · not published</small></div></div><div class="social-content"><h3>'+e(title)+'</h3><p>'+e(campaign['body'])+'</p><div class="hashtags">'+e(' '.join(campaign.get('hashtags',[])))+'</div></div></article>') if campaign.get('body') else '<div class="social-post social-placeholder">Morgan’s event headline and LinkedIn post will appear here after the research and operations handoffs.</div>'
    production='<div class="production"><span>CREW HANDOFFS</span>'+''.join('<span class="'+('complete' if str(i) in outputs else '')+'">'+('✓ ' if str(i) in outputs else '○ ')+label+'</span>' for i,label in enumerate(['Brief','Theme research' if all(t.get('researchStatus')=='sourced' for t in c['topics']) else 'Theme research incomplete','Rotation review','Social post']))+'</div>'
    sections=[
        '<section class="section" id="overview"><div class="wrap"><div class="kicker">Hands-on. Practical. Yours.</div><h2>Your visit, at a glance</h2><div class="facts">'+''.join('<div><b>'+str(v)+'</b><span>'+label+'</span></div>' for v,label in [(b['themeCount'],'themes / dedicated booths'),(c['session'],'minutes per visit'),(c['presenterCount'],'rotating presenters'),(b['attendees'],'attendees')])+'</div></div></section>',
        '<section class="section soft" id="program"><div class="wrap"><div class="sectionhead"><h2>Choose what sparks your curiosity</h2><span class="badge">Research → theme → booth</span></div><p class="lead">One focused experience per visitor, built around current NVIDIA topics. OpenClaw is the agent harness.</p><p class="research-note">'+e(note)+'</p><div class="cards">'+''.join(cards)+'</div></div></section>',
        '<section class="section" id="schedule"><div class="wrap"><h2>Your booth timetable</h2><p>Same assignments as the Excel rota. Colors identify presenters, so every handover is visible. Numbers are staffing placeholders, not confirmed people.</p>'+tables(b,c)+'</div></section>',
        '<section class="section soft" id="insights"><div class="wrap">'+event_insights.insights(b,c,decision_notes)+'</div></section>',
        '<section class="section" id="promotion"><div class="wrap social-layout"><div><div class="kicker">Bring the program to your audience</div><h2>A reason to join. A story to share.</h2><p>Morgan turns the researched themes and agreed schedule into a concise event announcement.</p></div>'+post+'</div></section>',
        '<section class="section soft" id="agents"><div class="wrap">'+event_insights.reflections(roundtable)+'</div></section>' if roundtable and roundtable.get('members') else '']
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><title>'+e(title)+' · '+e(b['city'])+'</title><style>'+CSS+'</style></head><body><div class="masthead"><div class="wrap"><div class="wordmark">BUILD-A-CLAW</div><div class="draft">EVENT PREVIEW · '+e(b['city'])+'</div></div></div><header class="hero"><div class="wrap"><div class="hero-copy"><div class="kicker">Build-a-Claw · Hands-on AI experiences</div><h1>'+e(title)+'</h1><p class="logistics">'+e(b['city'])+' · '+e(date_label(b))+' · '+e(b.get('venue') or 'Venue TBC')+' · '+e(b['startTime'])+' local time</p><p>'+e(intro)+'</p><a class="cta" href="#program">Explore the experiences</a></div></div></header><nav class="anchors"><div class="wrap">'+''.join('<a href="#'+id+'">'+label+'</a>' for id,label in [('overview','Overview'),('program','Experiences'),('schedule','Schedule'),('insights','Planning insights'),('promotion','Social post'),('agents','Your agents')])+'</div></nav><main>'+''.join(sections)+'</main><footer><div class="wrap">'+production+'Planning draft · Venue: '+e(b.get('venue') or 'TBC')+'. Agent-authored themes and promotional copy; schedule and page assembled by the studio. Based on public NVIDIA sources, not an official NVIDIA announcement. No messages published.</div></footer></body></html>'
