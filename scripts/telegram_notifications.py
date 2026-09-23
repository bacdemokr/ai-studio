"""Opt-in, participant-scoped Telegram relay. Bot credentials only live in session memory."""
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
import session_secrets


def key(participant):return 'telegram:'+participant


def response_error(method,status,result=None):
    # Never echo a server body/description: a proxy may include the token URL.
    if not isinstance(result,dict) or result.get('ok') is not False:
        return 'Telegram API returned an unexpected response (HTTP %s). Check whether your network, VPN or web filter blocks api.telegram.org.' % status
    code=result.get('error_code',status)
    description=str(result.get('description','')).lower()
    if code==401 or (method=='getMe' and code==404):
        return 'Telegram rejected the bot token. Copy the full current token from @BotFather, including the number and colon.'
    if code==429:return 'Telegram is receiving too many requests. Wait a moment, then try again.'
    if isinstance(code,int) and code>=500:return 'Telegram is temporarily unavailable. Try again shortly.'
    if method=='sendMessage':
        if code==400 and 'chat not found' in description:
            return 'Telegram could not find this chat. Check the Chat ID and send /start to your own bot before trying again.'
        if code==403 and 'blocked' in description:
            return 'This bot is blocked in Telegram. Unblock your bot, send /start, then try again.'
        if code==403:
            return 'This bot cannot post to the selected chat. Start the bot in a personal chat, or check its group permissions.'
    return 'Telegram rejected the %s request (error %s). %s' % (
        'bot verification' if method=='getMe' else 'message delivery',
        code if isinstance(code,int) else status,
        'Check the bot token in @BotFather.' if method=='getMe' else 'Check the Chat ID and the bot’s permission to post there.')


def request(token,method,payload=None):
    if method not in ('getMe','sendMessage'):raise ValueError('Unsupported Telegram operation.')
    # A fixed origin, no redirects, no token-bearing exception/log output.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    req=urllib.request.Request('https://api.telegram.org/bot'+token+'/'+method,
        data=json.dumps(payload or {}).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=8) as response:
            raw=response.read(100000)
            status=response.status
    except urllib.error.HTTPError as error:
        status=error.code
        try:raw=error.read(100000)
        except Exception:raw=b''
        finally:error.close()
    except (OSError,urllib.error.URLError) as error:
        reason=error.reason if isinstance(error,urllib.error.URLError) else error
        if isinstance(reason,ssl.SSLCertVerificationError):
            message='Telegram TLS certificate could not be verified. Check the server trust store or network proxy certificate.'
        elif isinstance(reason,TimeoutError):
            message='Telegram did not respond within 8 seconds. Check network access to api.telegram.org, then try again.'
        elif isinstance(reason,socket.gaierror):
            message='The server could not resolve api.telegram.org. Check its DNS or network connection.'
        else:message='The server could not connect to api.telegram.org. Check network, VPN or proxy access.'
        raise RuntimeError(message) from None
    except Exception:
        raise RuntimeError('Telegram connection could not be completed. Try again or check the server’s network connection.') from None
    try:result=json.loads(raw)
    except (ValueError,UnicodeError):result=None
    if 200<=status<300 and isinstance(result,dict) and result.get('ok') is True and 'result' in result:
        return result['result']
    raise RuntimeError(response_error(method,status,result)) from None


def public(participant,lease=None):
    value=session_secrets.get(key(participant),lease)
    return {'connected':bool(value),'bot':value.get('bot',''),'chatId':value.get('chatId','')}


def configure(participant,data):
    from studio import Problem
    lease=data['_credentialSession']
    if data.get('disconnect') is True:
        session_secrets.remove(key(participant), lease)
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
    try:request(value['token'],'sendMessage',{'chat_id':value['chatId'],'text':'BaC Telegram connected. New Tech Radar updates will appear here.'})
    except RuntimeError as error:raise Problem(str(error),502) from None
    return {'sent':True}
