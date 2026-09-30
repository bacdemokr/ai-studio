"""Short-lived, process-memory credentials. No filesystem persistence."""
import copy
import socket
import ssl
import errno
import logging
import json
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TTL = 90
_lock = threading.RLock()
_values = {}
_closed = {}
_proxy = None


def put(key, value, lease):
    with _lock:
        if lease in _closed:
            from studio import Problem
            raise Problem('This credential session has ended. Refresh and reconnect.',409)
        _values[str(key)] = (copy.deepcopy(value), lease, time.monotonic() + TTL)


def get(key, lease=None):
    with _lock:
        item = _values.get(str(key))
        if not item:return {}
        value, owner, expires = item
        if expires <= time.monotonic():
            _values.pop(str(key), None);return {}
        if lease is not None and owner != lease:return {}
        return copy.deepcopy(value)


def renew(lease):
    with _lock:
        for key,(value,owner,expires) in list(_values.items()):
            if expires <= time.monotonic():_values.pop(key,None)
            elif owner == lease:_values[key]=(value,owner,time.monotonic()+TTL)


def release(lease):
    with _lock:
        _closed[lease]=time.monotonic()+300
        for key,(_,owner,_) in list(_values.items()):
            if owner == lease:_values.pop(key,None)


def remove(key, lease=None):
    with _lock:
        item = _values.get(str(key))
        if item and (lease is None or item[1] == lease):
            _values.pop(str(key), None)


def _reap():
    while True:
        time.sleep(5)
        with _lock:
            for lease,expires in list(_closed.items()):
                if expires <= time.monotonic():_closed.pop(lease,None)
            for key,(_,_,expires) in list(_values.items()):
                if expires <= time.monotonic():_values.pop(key,None)
threading.Thread(target=_reap,daemon=True,name='credential-expiry').start()


class CredentialExpired(ValueError):
    pass


TRANSPORT_MESSAGES = {
    'model-credential-expired': 'The model API session credential has expired. Reconnect the model API.',
    'model-dns-failed': 'The host could not resolve the model API address. Check network, DNS and VPN connectivity.',
    'model-connection-timeout': 'The model API connection timed out. The network or model service may be slow; an internet outage is not confirmed.',
    'model-tls-failed': 'The secure connection to the model API failed. Check certificates and any network proxy.',
    'model-network-unreachable': 'The host network could not reach the model API. Check the internet connection and VPN.',
    'model-connection-failed': 'The host could not establish or maintain its connection to the model API. Check network, VPN and service availability.',
    'model-proxy-failed': 'The local model API connection failed. Check the host runtime logs.',
}


def connection_failure(error):
    """Fixed, credential-free diagnostics for the model transport only."""
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    status,code=502,'model-proxy-failed'
    if isinstance(error, CredentialExpired):status,code=401,'model-credential-expired'
    elif isinstance(reason, socket.gaierror):code='model-dns-failed'
    elif isinstance(reason, (TimeoutError, socket.timeout)):status,code=504,'model-connection-timeout'
    elif isinstance(reason, ssl.SSLError):code='model-tls-failed'
    elif isinstance(reason, OSError) and reason.errno in (errno.ENETUNREACH, errno.ENETDOWN, errno.EHOSTUNREACH):code='model-network-unreachable'
    elif isinstance(reason, ConnectionError) or isinstance(error, urllib.error.URLError):code='model-connection-failed'
    return status,code,TRANSPORT_MESSAGES[code]


class Proxy(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):self.forward()
    def do_POST(self):self.forward()
    def forward(self):
        import runtime_settings as settings
        # No credentials from the gateway are forwarded. Destinations come only from validated profiles.
        sent=False
        try:
            if self.headers.get('Authorization')!='Bearer session-only' and self.headers.get('x-api-key')!='session-only':raise ValueError()
            _, prefix, provider, suffix = self.path.split('/',3)
            if prefix!='provider' or provider not in (*settings.PROVIDERS, 'team'):raise ValueError()
            profile=get(settings.secret_key(provider))
            provider = 'nvidia' if provider == 'team' else provider
            if not profile:raise CredentialExpired()
            base=urllib.parse.urlsplit(profile['baseUrl'])
            path='/'+suffix
            if not path.startswith(base.path.rstrip('/')+'/'):raise ValueError()
            relative=path[len(base.path):]
            if relative.split('?')[0] not in ['/models','/chat/completions','/responses','/v1/models','/v1/messages','/v1/messages/count_tokens']:raise ValueError()
            size=int(self.headers.get('Content-Length','0'))
            if not 0<=size<=8*1024*1024:raise ValueError()
            payload=self.rfile.read(size) if size else None
            headers={'Content-Type':'application/json','Accept':self.headers.get('Accept','application/json')}
            if provider=='anthropic':
                headers['x-api-key']=profile['apiKey'];headers['anthropic-version']=self.headers.get('anthropic-version','2023-06-01')
                if self.headers.get('anthropic-beta'):headers['anthropic-beta']=self.headers['anthropic-beta']
            elif profile['apiKey']:headers['Authorization']='Bearer '+profile['apiKey']
            request=urllib.request.Request(profile['baseUrl']+relative,data=payload,headers=headers,method=self.command)
            with settings.provider_opener(provider).open(request,timeout=180) as response:
                self.send_response(200);self.send_header('Content-Type',response.headers.get('Content-Type','application/json'));self.send_header('Connection','close');self.end_headers();sent=True
                while chunk := response.read1(65536):self.wfile.write(chunk);self.wfile.flush()
                self.close_connection=True
        except urllib.error.HTTPError as error:
            if sent:
                self.close_connection=True
                return
            # Preserve actionable provider failures instead of calling every 400/429
            # an expired credential. Never expose its raw body or headers.
            detail = settings.provider_error_detail(error, profile.get('apiKey',''))
            message = 'Model provider returned HTTP %s.' % error.code
            if detail:message += ' ' + detail
            body = json.dumps({'error':{'message':message}}).encode()
            try:
                self.send_response(error.code)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body)
            except OSError:pass
            finally:error.close()
        except Exception as error:
            # Never log exception text: URLs and headers may contain credentials.
            status,code,message=connection_failure(error)
            logging.warning('Model transport failure: %s (%s)',code,type(error).__name__)
            if sent:
                self.close_connection=True
                return
            body=json.dumps({'error':{'code':code,'message':code+': '+message}}).encode()
            try:
                self.send_response(status);self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body)
            except OSError:pass


def proxy_url(provider, base_url):
    global _proxy
    with _lock:
        if _proxy is None:
            _proxy=ThreadingHTTPServer(('127.0.0.1',0),Proxy)
            threading.Thread(target=_proxy.serve_forever,daemon=True,name='credential-proxy').start()
        return 'http://127.0.0.1:%d/provider/%s%s' % (_proxy.server_port,provider,urllib.parse.urlsplit(base_url).path)


def purge_legacy(home):
    """Remove previously persisted external credentials in app-owned configuration copies."""
    from pathlib import Path
    home=Path(home)
    candidates=list(home.glob('host-settings.*'))
    state=home/'openclaw/state'
    if state.exists():
        candidates += [p for p in state.rglob('*') if p.is_file() and ('.json' in p.name or p.name.endswith(('.bak','.new')))]
    removed=set()
    def scrub(value):
        if isinstance(value,dict):
            for k,v in list(value.items()):
                if (k=='apiKey' or (value.get('type')=='api_key' and k=='key')) and isinstance(v,str) and v not in ('local-only','session-only',''):
                    removed.add(v);value[k]=''
                else:scrub(v)
        elif isinstance(value,list):
            for v in value:scrub(v)
    for target in candidates:
        try:
            original=target.read_text();data=json.loads(original);scrub(data)
            updated=json.dumps(data,indent=2)
            if json.loads(original)!=data:target.write_text(updated)
        except (OSError,ValueError,UnicodeError):continue
    # Invitation credentials were previously written by the app; drop, never restore into memory.
    studio=home/'studio'
    for target in [*studio.glob('marketing-telegram-*'), studio/'telegram.json']:
        if target.suffix not in ('.json','.new'):continue
        try:
            value=json.loads(target.read_text()).get('token')
            if value:removed.add(value)
            target.unlink()
        except (OSError,ValueError):continue
    (home/'openclaw/search-enabled').unlink(missing_ok=True)
    # Redact known removed values in this app's runtime logs/backups, without displaying them.
    if removed:
        for target in (home/'openclaw').glob('*.log*'):
            try:
                original=target.read_text();updated=original
                for value in removed:updated=updated.replace(value,'[removed]')
                if updated!=original:target.write_text(updated)
            except (OSError,UnicodeError):pass
        for parent in (home/'openclaw/state',):
            if not parent.exists():continue
            for target in parent.rglob('*'):
                if not target.is_file() or not any(x in target.name for x in ('.json','.log','.bak','.new')):continue
                try:
                    original=target.read_text();updated=original
                    for value in removed:updated=updated.replace(value,'[removed]')
                    if updated!=original:target.write_text(updated)
                except (OSError,UnicodeError):continue
