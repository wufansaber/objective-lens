"""Give pending read-only reviews priority at the next existing SDK release."""
import ctypes
from ctypes import wintypes
from pathlib import Path
from atomic_progress import read_json_retry

CAPACITY=Path(__file__).resolve().parents[1]/'results/uv355_optimizer_capacity'


def process_identity(pid):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return None
    try:
        code=wintypes.DWORD()
        times=[wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)) or code.value!=259:return None
        if not kernel.GetProcessTimes(handle,*[ctypes.byref(value) for value in times]):return None
        return (times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
    finally:kernel.CloseHandle(handle)


def pending_review():
    for path in CAPACITY.glob('verification_request_*.json'):
        request=read_json_retry(path)
        if request.get('status')!='waiting':continue
        pid=request['pid']
        if process_identity(pid)!=request['process_creation_identity']:continue
        lease=CAPACITY/f'verification_lease_{pid}.json'
        if lease.exists():
            held=read_json_retry(lease)
            same_process=(held.get('process_creation_identity')==request['process_creation_identity']
                          or lease.stat().st_mtime_ns//100+116444736000000000>=request['process_creation_identity'])
            if same_process and held.get('status')=='held':continue
        return True
    return False
