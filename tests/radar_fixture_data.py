"""Explicit technical-feed test fixtures, never application data."""
from datetime import datetime, timezone
from xml.sax.saxutils import escape


def feed(source, articles):
    return ('<feed xmlns="http://www.w3.org/2005/Atom">'+''.join(
        '<entry><title>'+escape(title)+'</title><link href="https://'+source['host']+'/blog/'+slug+'/"/>'
        '<published>'+datetime.fromtimestamp(stamp,timezone.utc).isoformat()+'</published>'
        '<summary>'+escape(description)+'</summary></entry>'
        for slug,title,description,stamp in articles)+'</feed>').encode()


def sample(source, now):
    return feed(source,[('test-sdk','A new open-source developer SDK','A tutorial showing how to run an inference model with a Python SDK.',now-60),
                        ('old-guide','An older training tutorial','How to train a model.',now-500)])
