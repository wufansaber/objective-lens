"""Optional identical native batch transport; optical calculation stays in ZOSAPI."""
import ctypes
import hashlib
from pathlib import Path
import numpy as np


def load_bridge():
    import clr
    assembly = Path(__file__).with_name('BatchTraceBridge.dll')
    clr.AddReference(str(assembly))
    from ObjectiveLensBridge import BatchTraceBridge
    return BatchTraceBridge, hashlib.sha256(assembly.read_bytes()).hexdigest()


def trace_bridge(bridge, ray, surface, requests):
    from System import Array, Double
    from System.Runtime.InteropServices import GCHandle, GCHandleType
    packed = Array[Double]([value for request in requests for value in request])
    values = bridge.Trace(ray, surface, packed)
    handle = GCHandle.Alloc(values, GCHandleType.Pinned)
    try:
        # Copy while pinned; no managed-memory pointer escapes this function.
        raw = ctypes.string_at(handle.AddrOfPinnedObject().ToInt64(), values.Length * 8)
        return np.frombuffer(raw, dtype=np.float64).reshape(-1, 6).copy()
    finally:
        handle.Free()
