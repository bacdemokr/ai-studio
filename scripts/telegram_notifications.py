"""Opt-in, participant-scoped Telegram relay. Bot credentials only live in session memory."""
import json
import re
import time
import urllib.request
import session_secrets


def key(participant):return 'telegram:'+participant


def request(token,method,payload=None):
    if method not in ('getMe','sendMessage'):raise ValueError('Unsupported Telegram operation.')
    # A fixed origin, no redirects, no token-bearing exception/log output.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    req=urllib.request.Request('https://api.telegram.org/bot'+token+'/'+method,
        data=json.dumps(payload or {}).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=8) as response:
            result=json.loads(response.read(100000))
        if result.get('ok') is not True:raise ValueError()
        return result['result']
    except Exception:
        raise RuntimeError('Telegram could not confirm the request. Check the bot token, chat ID and whether you started the bot.') from None


def public(participant,lease=None):
    value=session_secrets.get(key(participant),lease)
    return {'connected':bool(value),'bot':value.get('bot',''),'chatId':value.get('chatId','')}


def configure(participant,data):
    from studio import Problem
    lease=data['_credentialSession']
    if data.get('disconnect') is True:
        if session_secrets.get(key(participant),lease):session_secrets.remove(key(participant))
        return public(participant,lease)
    token=data.get('token','');chat=str(data.get('chatId','')).strip()
    if not isinstance(token,str) or not re.fullmatch(r'[0-9]{5,15}:[A-Za-z0-9_-]{20,100}',token.strip()):raise Problem('Enter the bot token from BotFather.')
    if not re.fullmatch(r'-?[0-9]{1,20}',chat):raise Problem('Enter a numeric Telegram chat ID.')
    try:
        bot=request(token.strip(),'getMe')
        if not isinstance(bot,dict) or not isinstance(bot.get('username'),str):raise RuntimeError('Telegram did not return a bot identity.')
    except RuntimeError as error:raise Problem(str(error),502) from None
    session_secrets.put(key(participant),{'token':token.strip(),'chatId':chat,'bot':bot.get('username',''),'connectedAt':time.time()},lease)
    return public(participant,lease)


def send(participant,text,created):
    value=session_secrets.get(key(participant))
    # Connecting later never forwards earlier/private chat history to a new destination.
    if not value or created<value['connectedAt']:return 'not-connected'
    request(value['token'],'sendMessage',{'chat_id':value['chatId'],'text':text[:3500],
        'link_preview_options':{'is_disabled':True}})
    return 'sent'


def test(participant, lease):
    from studio import Problem
    value=session_secrets.get(key(participant),lease)
    if not value:raise Problem('Connect Telegram in this tab first.',409)
    try:request(value['token'],'sendMessage',{'chat_id':value['chatId'],'text':'BaC Telegram connected. New Notes Watcher updates will appear here.'})
    except RuntimeError as error:raise Problem(str(error),502) from None
    return {'sent':True}
