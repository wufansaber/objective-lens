"""OS-released leases cap active optimizer SDK sessions, including validation."""
import argparse
import ctypes
import msvcrt
import os
import time
from contextlib import contextmanager
from pathlib import Path
from atomic_progress import write_json_atomic

CAPACITY=Path(__file__).resolve().parents[1]/'results/uv355_optimizer_capacity'


@contextmanager
def optimizer_slot(reference_pid=None):
    CAPACITY.mkdir(exist_ok=True)
    from uv355_optimizer_fifo_20261016 import register,is_turn,update
    ticket,identity=register()
    selected=None
    while selected is None:
        from uv355_verification_priority import pending_review
        if pending_review():
            time.sleep(1.);continue
        if not is_turn(os.getpid(),identity):
            time.sleep(1.);continue
        for index in range(3):
            stream=(CAPACITY/f'slot_{index+1}.lock').open('a+b')
            stream.seek(0,2)
            if stream.tell()==0:stream.write(b'0');stream.flush()
            stream.seek(0)
            try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:stream.close();continue
            selected=(index,stream);break
        if selected is None:time.sleep(2.)
    index,stream=selected
    receipt=CAPACITY/f'lease_{os.getpid()}.json'
    write_json_atomic(receipt,dict(status='held',pid=os.getpid(),reference_pid=reference_pid,slot=index+1,maximum=3))
    update(ticket,identity,'held',slot=index+1)
    try:yield
    finally:
        stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1);stream.close()
        write_json_atomic(receipt,dict(status='released',pid=os.getpid(),reference_pid=reference_pid,slot=index+1,maximum=3))
        update(ticket,identity,'released',slot=index+1)


def main():
    p=argparse.ArgumentParser();p.add_argument('--existing-worker-pid',type=int,required=True);a=p.parse_args()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x00100000,False,a.existing_worker_pid)
    if not handle:raise OSError(ctypes.get_last_error(),'Cannot track existing worker')
    try:
        with optimizer_slot(a.existing_worker_pid):
            while kernel.WaitForSingleObject(handle,2000)==258:pass
    finally:kernel.CloseHandle(handle)


if __name__=='__main__':main()
