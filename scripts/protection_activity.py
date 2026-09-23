"""Short-lived visual evidence from native policy logs."""
from contextlib import contextmanager
from collections import deque
import hashlib
import threading
import time


class ProtectionActivity:
    def __init__(self):
        self.lock = threading.Lock()
        self.events = deque(maxlen=128)

    def observe(self, owner, role, agent_id, logs, started):
        now = time.time()
        with self.lock:
            known = {e['id'] for e in self.events}
            for log in logs:
                stamp = log.get('time')
                # Allow subsecond host/sandbox clock skew; fingerprints still deduplicate reads.
                # Native policy decisions only. An allow is permission to connect,
                # not proof that the remote service returned a successful response.
                decision = ((log.get('action') == 'deny' and log.get('reason') in ('policy-denied', 'destination-blocked'))
                            or (log.get('action') == 'allow' and log.get('reason') is None))
                if (not decision or not log.get('host')
                        or not isinstance(stamp, (int, float)) or not started - 1 <= stamp <= now + 2):
                    continue
                if log['action'] == 'allow':
                    # Only website destinations belong in the external-world visual.
                    # Local runtime/health connections must not appear as web access.
                    from agent_policy import destination_permission
                    try:
                        destination_permission(log['host'])
                    except ValueError:
                        continue
                identity = hashlib.sha256((agent_id + ':' + str(log.get('fingerprint') or (stamp, log.get('host')))).encode()).hexdigest()[:24]
                if identity in known:
                    continue
                known.add(identity)
                self.events.append({'id':identity, 'owner':owner, 'role':role, 'host':log.get('host', ''),
                                    'time':stamp, 'observedAt':now, 'source':'OpenShell policy log', 'action':log['action']})

    def snapshot(self, owners, crew_owner):
        now = time.time()
        with self.lock:
            return [dict(e) for e in self.events if now-e['observedAt'] < 30
                    and ((e['role'] is None and e['owner'] in owners)
                         or (e['role'] is not None and e['owner'] == crew_owner))]

    @contextmanager
    def watch(self, owner, role, agent_id, reader):
        started = time.time()
        finished = threading.Event()
        def read():
            try:
                self.observe(owner, role, agent_id, reader(agent_id), started)
            except Exception:
                pass  # Missing evidence never produces a shield hit or fails the task.
        def sample():
            while not finished.wait(3):
                read()
            # Native log delivery can lag a fast rejected request. Drain briefly in
            # the background instead of making the model response wait for logs.
            read()
            for delay in (.75, 1.5):
                time.sleep(delay)
                read()
        threading.Thread(target=sample, daemon=True, name='bac-policy-observer').start()
        try:
            yield
        finally:
            finished.set()  # One final read; don't delay the model result or UI for native log I/O.
