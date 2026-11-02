"""Independent read-only reviews borrow idle existing SDK seats, never add seats."""
import os
import time
import msvcrt
from pathlib import Path
from contextlib import contextmanager
from atomic_progress import write_json_atomic

ROOT=Path(__file__).resolve().parents[1]
CAPACITY=ROOT/'results/uv355_optimizer_capacity'

@contextmanager
def verification_slot():
    CAPACITY.mkdir(exist_ok=True)
    from uv355_verification_priority import process_identity
    request_path=CAPACITY/f'verification_request_{os.getpid()}.json'
    request=dict(status='waiting',pid=os.getpid(),process_creation_identity=process_identity(os.getpid()),maximum_total_SDK_seats=4)
    assert request['process_creation_identity'] is not None
    write_json_atomic(request_path,request)
    paths=[('independent_audit',ROOT/'tmp/independent_zemax_audit.lock')]+[
        (f'optimizer_{index}',CAPACITY/f'slot_{index}.lock') for index in range(1,4)]
    selected=None
    while selected is None:
        for name,path in paths:
            path.parent.mkdir(exist_ok=True)
            stream=path.open('a+b');stream.seek(0,2)
            if stream.tell()==0:stream.write(b'0');stream.flush()
            stream.seek(0)
            try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:stream.close();continue
            selected=(name,stream);break
        if selected is None:time.sleep(1.)
    name,stream=selected
    request['status']='acquired';write_json_atomic(request_path,request)
    receipt=CAPACITY/f'verification_lease_{os.getpid()}.json'
    write_json_atomic(receipt,dict(status='held',pid=os.getpid(),process_creation_identity=request['process_creation_identity'],slot=name,maximum_total_SDK_seats=4,
        read_only=True,borrowed_existing_optimizer_slot=name!='independent_audit'))
    try:yield
    finally:
        stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1);stream.close()
        write_json_atomic(receipt,dict(status='released',pid=os.getpid(),slot=name,maximum_total_SDK_seats=4,
            read_only=True,borrowed_existing_optimizer_slot=name!='independent_audit'))
        request['status']='released';write_json_atomic(request_path,request)
