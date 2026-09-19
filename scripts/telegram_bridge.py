"""Opt-in Telegram transport to the SAME OpenClaw agent/session as the web UI."""
import hashlib
import json
import time
import urllib.request

from studio import Problem


def telegram(studio, method, payload):
    path = studio.directory / 'telegram.json'
    if not path.exists():
        raise Problem('Telegram is not configured.', 503)
    token = json.loads(path.read_text())['token']
    request = urllib.request.Request('https://api.telegram.org/bot' + token + '/' + method,
                                     data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        if not result.get('ok'):
            raise ValueError('Telegram rejected the request')
        return result['result']
    except Exception:
        # Never propagate URLs containing bot tokens into logs or browser errors.
        raise Problem('Telegram could not complete the request. The host should check the bot configuration.', 502) from None


def reply_to_owner(studio, owner, answer):
    with studio.db() as db:
        row = db.execute('SELECT chat FROM phones WHERE owner=?', (owner,)).fetchone()
    if row:
        for i in range(0, min(len(answer), 12000), 3800):
            telegram(studio, 'sendMessage', {'chat_id': row['chat'], 'text': answer[i:i + 3800]})


def accept_message(studio, message):
    chat = message.get('chat', {})
    if chat.get('type') != 'private' or not isinstance(message.get('text'), str):
        return
    content = message['text'].strip()
    chat_id = str(chat['id'])
    if content.startswith('/start '):
        code = hashlib.sha256(content.split(' ', 1)[1].encode()).hexdigest()
        with studio.db() as db:
            db.execute('BEGIN IMMEDIATE')
            pair = db.execute('SELECT * FROM pairs WHERE code=? AND expires>?', (code, time.time())).fetchone()
            if not pair:
                return
            db.execute('DELETE FROM phones WHERE chat=? OR owner=?', (chat_id, pair['owner']))
            db.execute('INSERT INTO phones VALUES (?,?)', (pair['owner'], chat_id))
            db.execute('DELETE FROM pairs WHERE code=?', (code,))
        telegram(studio, 'sendMessage', {'chat_id': chat_id, 'text': 'Connected to your BaC agent. Your web and phone messages use the same OpenClaw conversation. Ask what it remembers. Send /stop to disconnect.'})
        return
    with studio.db() as db:
        phone = db.execute('SELECT owner FROM phones WHERE chat=?', (chat_id,)).fetchone()
        if not phone:
            return
        if content == '/stop':
            db.execute('DELETE FROM phones WHERE chat=?', (chat_id,))
            return
    try:
        studio.enqueue(phone['owner'], {'kind': 'chat', 'prompt': content}, source='telegram')
        telegram(studio, 'sendMessage', {'chat_id': chat_id, 'text': 'Your agent received the task. It will reply here; progress also appears in your web workspace.'})
    except Problem as error:
        telegram(studio, 'sendMessage', {'chat_id': chat_id, 'text': str(error)})


def poll(studio):
    while not studio.stop.is_set():
        if not (studio.directory / 'telegram.json').exists():
            studio.stop.wait(5)
            continue
        try:
            with studio.db() as db:
                row = db.execute("SELECT value FROM metadata WHERE key='telegram-offset'").fetchone()
            offset = int(row['value']) if row else 0
            updates = telegram(studio, 'getUpdates', {'offset': offset, 'timeout': 15, 'allowed_updates': ['message']})
            for update in updates:
                # Persist the claim before handling: no duplicate outgoing replies on restart.
                # A crash during handling can lose one inbound message; the user can retry it.
                with studio.db() as db:
                    db.execute("INSERT OR REPLACE INTO metadata VALUES ('telegram-offset',?)", (str(update['update_id'] + 1),))
                accept_message(studio, update.get('message', {}))
        except Exception:
            studio.stop.wait(5)
