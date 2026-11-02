"""Native near-axis ordering diagnostic; no model writes or tolerance relaxation."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import os
import traceback
from atomic_progress import read_json_retry as read, write_json_atomic as write
from run_uv355_multistart_campaign import sha
from uv355_verification_priority import process_identity
from verification_capacity import verification_slot
import uv355_focal_runtime_R944_20261102 as runtime
from uv355_batched_boundary_and_ordering_R741_20261101 import configure, measure


def main(model, out):
    assert not out.exists()
    out.mkdir()
    digest = sha(model)
    state = dict(status='near_axis_ordering_diagnostic', active=True, read_only=True,
                 pid=os.getpid(), process_creation_identity=process_identity(os.getpid()),
                 model=str(model), sha256=digest)
    chat = runtime.method.CHAT/'progress.json'
    session = read(chat)
    assert not session['user_task_paused']
    session['routes'].append(dict(state, root=str(out), progress=str(out/'progress.json'), role='near_axis_readonly_diagnostic'))
    write(chat, session)
    app = None
    try:
        with verification_slot():
            app, api, bridge = runtime.method.make_application()
            system = app.PrimarySystem
            system.LoadFile(str(model), False)
            points = [dict(method=method, wave=w, radius_normalized=r, azimuth_deg=angle)
                      for method in ('GQ20', 'RECT32', 'RECT64') for w in (1, 2, 3)
                      for r in (0., .005, .01, .015625, .03125)
                      for angle in ((0.,) if not r else (0., 22.5, 45.))]
            configure(model, out, model.with_suffix('.MF'))
            wf, airy = measure(system, api, bridge, points)
            axes = {(p['method'], p['wave']): i for i, p in enumerate(points) if not p['radius_normalized']}
            rows = [dict(p, WFE=float(wf[i]), Airy=float(airy[i]),
                         WFE_minus_axis=float(wf[i]-wf[axes[p['method'], p['wave']]]),
                         Airy_minus_axis=float(airy[i]-airy[axes[p['method'], p['wave']]]))
                    for i, p in enumerate(points)]
            assert sha(model) == digest
            result = dict(model=str(model), sha256=digest, rows=rows,
                          strict_ordering_pass=all(r['WFE_minus_axis'] >= 0 and r['Airy_minus_axis'] >= 0 for r in rows))
            write(out/'NEAR_AXIS_ORDERING.json', result)
            state.update(status='near_axis_diagnostic_complete', result=str(out/'NEAR_AXIS_ORDERING.json'), strict_ordering_pass=result['strict_ordering_pass'])
    except BaseException:
        state.update(status='near_axis_diagnostic_failure_preserved', error=traceback.format_exc())
        raise
    finally:
        if app is not None:
            app.CloseApplication()
        state.update(active=False, utc=datetime.now(timezone.utc).isoformat())
        write(out/'progress.json', state)
        session = read(chat)
        for route in session['routes']:
            if route.get('pid') == os.getpid() and route.get('process_creation_identity') == state['process_creation_identity']:
                route.update(active=False, status=state['status'])
        write(chat, session)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    main(args.model.resolve(), args.out.resolve())
