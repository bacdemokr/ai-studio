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
                # HTTP 403 answers, DNS failures, and missing timestamps aren't evidence of policy denial.
                if (log.get('action') != 'deny' or log.get('reason') not in ('policy-denied', 'destination-blocked')
                        or not isinstance(stamp, (int, float)) or not started - 1 <= stamp <= now + 2):
                    continue
                identity = hashlib.sha256((agent_id + ':' + str(log.get('fingerprint') or (stamp, log.get('host')))).encode()).hexdigest()[:24]
                if identity in known:
                    continue
                known.add(identity)
                self.events.append({'id':identity, 'owner':owner, 'role':role, 'host':log.get('host', ''),
                                    'time':stamp, 'observedAt':now, 'source':'OpenShell policy log', 'action':'deny'})

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
