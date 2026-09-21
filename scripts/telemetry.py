"""Observed run usage and host utilization; never inferred token counts."""
import json
import math
import platform
import re
import subprocess
import threading
import time
from pathlib import Path

class Reply(str):
    def __new__(cls, text, metrics):
        value = super().__new__(cls, text)
        value.metrics = metrics
        return value


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def measure(result, state_dir, agent, session, started):
    usage = result.get('usage') or {}
    tokens = {key: number(usage.get(source)) for key, source in [('input','prompt_tokens'),('output','completion_tokens'),('total','total_tokens')]}
    # Gateway can return an all-zero placeholder when the provider reports nothing.
    if not any(value for value in tokens.values()):
        tokens = dict.fromkeys(tokens)
    context = limit = model = None
    try:
        entries = json.loads((Path(state_dir) / 'agents' / agent / 'sessions/sessions.json').read_text())
        entry = entries.get('agent:' + agent + ':openai-user:' + session, {})
        if entry.get('updatedAt', 0) >= started * 1000 and entry.get('totalTokensFresh') is True and entry.get('totalTokensVersion') == 1:
            context = number(entry.get('totalTokens'))
            limit = number(entry.get('contextTokens'))
            model = entry.get('model')
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return {**tokens, 'context': context, 'limit': limit, 'model': model, 'measuredAt': time.time()}

_lock = threading.Lock()
_cached = {'cpu': None, 'memory': None, 'sampledAt': 0}
_previous = None


def host():
    global _cached, _previous
    with _lock:
        if time.time() - _cached['sampledAt'] < 8:
            return dict(_cached)
        cpu = memory = None
        try:
            if platform.system() == 'Linux':
                values = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
                current = (sum(values), values[3] + values[4])
                if _previous and current[0] > _previous[0]:
                    cpu = 100 * (1 - (current[1] - _previous[1]) / (current[0] - _previous[0]))
                _previous = current
                mem = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
                memory = 100 * (1 - mem['MemAvailable'] / mem['MemTotal'])
            elif platform.system() == 'Darwin':
                # One host snapshot. top's CPU is system-wide, not this Python process.
                out = subprocess.run(['/usr/bin/top','-l','2','-s','1','-n','0'], capture_output=True, text=True, timeout=4).stdout
                matches = re.findall(r'CPU usage:.*?([\d.]+)% idle', out)
                if len(matches) > 1: cpu = 100 - float(matches[-1])
                vm = subprocess.run(['/usr/bin/vm_stat'], capture_output=True, text=True, timeout=2).stdout
                page = int(re.search(r'page size of (\d+)', vm)[1])
                counts = {k: int(v) for k,v in re.findall(r'^([^:\n]+):\s+(\d+)\.', vm, re.M)}
                total = int(subprocess.check_output(['/usr/sbin/sysctl','-n','hw.memsize'], text=True, timeout=2))
                # Physical footprint: active + wired + compressor pages; exclude reclaimable inactive cache.
                memory = 100 * page * sum(counts[k] for k in ['Pages active','Pages wired down','Pages occupied by compressor']) / total
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            pass
        _cached = {'cpu': None if cpu is None else round(max(0,min(100,cpu)),1), 'memory': None if memory is None else round(max(0,min(100,memory)),1), 'sampledAt': time.time()}
        return dict(_cached)


def report(studio, owner):
    agents = {}
    total = 0
    measured = missing = 0
    with studio.db() as db:
        # Histories can contain large research/handoff payloads. Read only measured
        # usage instead of decoding every saved task body on each meter refresh.
        rows = db.execute("SELECT json_extract(payload,'$.metrics') AS metrics,kind FROM jobs WHERE owner IN (SELECT id FROM agents WHERE participant=(SELECT participant FROM agents WHERE id=?)) AND json_type(payload,'$.metrics')='object' ORDER BY created", (owner,))
        for row in rows:
            for record in json.loads(row['metrics']).values():
                key = (record['agent'], row['kind']=='crew')
                previous = agents.get(key, {'total':0, 'calls':0})
                amount = number(record.get('total'))
                if amount is None: missing += 1
                else: total += amount; measured += 1
                agents[key] = {**record, 'total': previous['total'] + (amount or 0), 'calls': previous['calls'] + (amount is not None), 'crew': row['kind']=='crew'}
    return {'host':host(), 'agents':list(agents.values()), 'total':total if measured else None, 'measuredCalls':measured, 'unreportedCalls':missing}
