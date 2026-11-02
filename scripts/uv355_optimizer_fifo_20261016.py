"""Fair waiting tickets; existing OS leases and three-SDK limit stay intact."""
import os
import time
from pathlib import Path
from atomic_progress import read_json_retry,write_json_atomic
from uv355_verification_priority import process_identity

CAPACITY=Path(__file__).resolve().parents[1]/'results/uv355_optimizer_capacity'


def register(pid=None,identity=None,capacity=CAPACITY):
    pid=os.getpid() if pid is None else pid
    identity=process_identity(pid) if identity is None else identity
    assert identity is not None,'Cannot register a dead or inaccessible process'
    capacity.mkdir(exist_ok=True)
    path=capacity/f'optimizer_request_{pid}.json'
    if path.exists():
        old=read_json_retry(path)
        if old.get('process_creation_identity')==identity and old.get('status')=='waiting':return path,identity
    write_json_atomic(path,dict(pid=pid,process_creation_identity=identity,status='waiting',
        requested_at_ns=time.time_ns(),ordering_identity=identity,concurrency_limit_unchanged=3))
    return path,identity


def is_turn(pid,identity,capacity=CAPACITY,identity_reader=process_identity):
    waiting=[]
    for path in capacity.glob('optimizer_request_*.json'):
        item=read_json_retry(path)
        if item.get('status')!='waiting':continue
        birth=item['process_creation_identity'];other=item['pid']
        if identity_reader(other)!=birth:continue
        lease=capacity/f'lease_{other}.json'
        if lease.exists():
            held=read_json_retry(lease)
            if held.get('status') in ('held','released') and lease.stat().st_mtime_ns>=item['requested_at_ns']:
                # Also recognize a seeded old worker whose loaded allocator has
                # no ticket support; its ordinary OS lease fulfills this ticket.
                continue
        waiting.append((item['ordering_identity'],other,birth))
    return bool(waiting and min(waiting)[1:]==(pid,identity))


def update(path,identity,status,**extra):
    item=read_json_retry(path)
    assert item['process_creation_identity']==identity
    item.update(status=status,**extra);write_json_atomic(path,item)
