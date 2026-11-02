"""Atomic progress JSON with bounded retry for transient Windows file locks."""
import json
import time
from pathlib import Path


def read_json_retry(path):
    """Retry transient Windows sharing locks without hiding persistent errors."""
    path=Path(path)
    for attempt in range(12):
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (PermissionError,json.JSONDecodeError):
            if attempt==11:raise
            time.sleep(min(.01*2**attempt,.5))


def write_json_atomic(path,data):
    path=Path(path)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
    for attempt in range(12):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt==11:raise
            time.sleep(min(.01*2**attempt,.5))
