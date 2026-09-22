"""Bounded, fresh public NVIDIA blog searches for the demo producer."""
import concurrent.futures
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
import re
import urllib.parse
from research_http import fetch
import xml.etree.ElementTree as ET

QUERIES = ('agent', 'physical AI', 'inference', 'Nemotron')

def search_one(query):
    url = 'https://blogs.nvidia.com/?' + urllib.parse.urlencode({'s': query, 'feed':'rss2'})
    raw = fetch(url, limit=1000000, timeout=8)
    if len(raw)>1000000:raise ValueError('Research response exceeds size limit')
    root=ET.fromstring(raw)
    rows=[]
    for item in root.findall('./channel/item')[:12]:
        link=item.findtext('link','').strip()
        u=urllib.parse.urlsplit(link)
        if u.scheme!='https' or u.hostname!='blogs.nvidia.com':continue
        title=unescape(item.findtext('title','')).strip()
        try:published=parsedate_to_datetime(item.findtext('pubDate','')).astimezone(timezone.utc)
        except (ValueError,TypeError,AttributeError):continue
        now=datetime.now(timezone.utc)
        if not now-timedelta(days=365)<=published<=now:continue
        summary=unescape(re.sub('<[^>]+>',' ',item.findtext('description','')))
        if not re.search(r'agent|nemotron|inference|physical AI|robot|reasoning|multimodal|open.?model|openclaw|openshell|cuda',title+' '+summary,re.I):continue
        rows.append({'title':title[:220], 'url':link, 'published':published.date().isoformat(), 'excerpt':re.sub(r'\s+',' ',summary).strip()[:420]})
    return rows

def discover():
    rows=[];failures=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(search_one,q):q for q in QUERIES}
        for f in concurrent.futures.as_completed(futures):
            try:rows.extend(f.result())
            except Exception:failures.append(futures[f])
    unique={r['url']:r for r in rows}
    candidates=sorted(unique.values(),key=lambda r:(r['published'],r['url']),reverse=True)[:18]
    for i,r in enumerate(candidates,1):r['id']='S'+str(i)
    return {'retrieved':datetime.now(timezone.utc).isoformat(), 'method':'NVIDIA public blog keyword searches (RSS)',
            'queries':list(QUERIES), 'sources':candidates, 'failedQueries':sorted(failures),
            'status':'available' if candidates else 'unavailable'}
