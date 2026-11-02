"""Read-only Toolhelp inventory; never infer exit from an inaccessible query."""
import ctypes
from ctypes import wintypes
import datetime
import json
import os
from pathlib import Path


class ProcessEntry(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
                ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]


def inventory():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = kernel.Process32FirstW.argtypes
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    rows = []
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        success = kernel.Process32FirstW(handle, ctypes.byref(entry))
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())
        while success:
            rows.append(dict(pid=entry.th32ProcessID, parent_pid=entry.th32ParentProcessID,
                             name=entry.szExeFile))
            success = kernel.Process32NextW(handle, ctypes.byref(entry))
        error = ctypes.get_last_error()
        if error != 18:  # ERROR_NO_MORE_FILES is the only valid termination.
            raise ctypes.WinError(error)
    finally:
        kernel.CloseHandle(handle)
    from uv355_verification_priority import process_identity
    matches = []
    for row in rows:
        if any(word in row['name'].lower() for word in ('python', 'opticstudio', 'zemax')):
            row['process_creation_identity'] = process_identity(row['pid'])
            row['identity_query_error'] = ctypes.get_last_error() if row['process_creation_identity'] is None else 0
            matches.append(row)
    assert any(row['pid'] == os.getpid() for row in rows), 'Inventory omitted the querying process'
    return dict(query_success=True, method='Toolhelp32 process snapshot with checked enumeration',
                utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), self_pid=os.getpid(),
                visible_process_count=len(rows), processes=matches,
                recorded_controllers_present=[row for row in rows if row['pid'] in (20300, 43104, 27996)])


if __name__ == '__main__':
    result = inventory()
    path = Path(__file__).resolve().parents[1] / 'tmp/migration_actual_processes_20261020.json'
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
