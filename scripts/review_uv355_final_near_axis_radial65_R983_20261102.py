"""Additional 65-radius native audit to check extrema between the 33-radius rings."""
from datetime import datetime, timezone
from pathlib import Path
import os
import subprocess
import sys
import time
import traceback
from atomic_progress import read_json_retry as read, write_json_atomic as write
from run_uv355_multistart_campaign import sha
from uv355_verification_priority import process_identity
from uv355_acceptance_revision_R943_20261102 import reassess

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT/'results/uv355_near_axis_design_R981_20261102'
OUT = ROOT/'results/uv355_final_near_axis_radial65_R983_20261102'
CHAT = ROOT/'results/uv355_chat_continuation_R4_20261025'


def main():
    assert not OUT.exists()
    OUT.mkdir()
    prep = read(UP/'preparation.json')
    candidate = read(UP/'progress.json')['best_candidate']
    model = Path(candidate['model'])
    assert sha(model) == candidate['sha256']
    state = dict(status='additional_radial65_native_confirmation', active=True,
                 read_only=True, pid=os.getpid(), process_creation_identity=process_identity(os.getpid()),
                 model=str(model), sha256=sha(model), qualified=False, child=None)

    def save():
        state['utc'] = datetime.now(timezone.utc).isoformat()
        write(OUT/'progress.json', state)

    session = read(CHAT/'progress.json')
    assert not session['user_task_paused']
    session['routes'].append(dict(state, root=str(OUT), progress=str(OUT/'progress.json'),
                                  role='radial65_readonly_confirmation', kind='additional_between_ring_extrema_check'))
    write(CHAT/'progress.json', session)
    child = None
    save()
    try:
        with (OUT/'native_audit.log').open('wb') as log:
            child = subprocess.Popen([sys.executable, '-B', str(ROOT/'scripts/audit_uv355_extended_thickness_R352_20261031.py'),
                                      '--model', str(model), '--out', str(OUT/'CIRCLE1025'),
                                      '--radial-count', '65', '--azimuth-count', '16'],
                                     cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
            state['child'] = dict(pid=child.pid, process_creation_identity=process_identity(child.pid))
            save()
            while child.poll() is None:
                assert not read(CHAT/'progress.json')['user_task_paused'] and not (OUT/'STOP_REQUEST').exists()
                time.sleep(2)
            assert child.returncode == 0
        raw = OUT/'CIRCLE1025/circle_audit.json'
        assert sha(model) == candidate['sha256']
        result = reassess(read(raw), read(prep['policy']))
        assert result['field_count'] == 1025 and result['source_sha256'] == sha(model)
        write(OUT/'R943_ACCEPTANCE.json', result)
        state.update(status='additional_radial65_confirmation_complete', result=result,
                     original_stopping_rounds_not_established=True, manufacturing_release_not_established=True)
    except BaseException:
        state.update(status='additional_confirmation_failure_preserved', error=traceback.format_exc())
        raise
    finally:
        # A user pause is coordinated by the central process-identity-aware pauser.
        state['active'] = False
        save()
        session = read(CHAT/'progress.json')
        for route in session['routes']:
            if route.get('pid') == os.getpid() and route.get('process_creation_identity') == state['process_creation_identity']:
                route.update(active=False, status=state['status'])
        write(CHAT/'progress.json', session)


def finalize_existing():
    """Recover postprocessing only, preserving the native audit and error receipt."""
    state = read(OUT/'progress.json')
    assert not state['active']
    if state.get('error'):
        receipt = OUT/'POSTPROCESSING_FAILURE_PRESERVED.json'
        assert not receipt.exists()
        write(receipt, state)
    prep = read(UP/'preparation.json')
    native = OUT/'CIRCLE1025/circle_audit.json'
    result = reassess(read(native), read(prep['policy']))
    assert result['field_count'] == 1025 and result['source_sha256'] == sha(state['model'])
    result.update(original_review=str(native), original_review_sha256=sha(native))
    write(OUT/'R943_ACCEPTANCE.json', result)
    state.pop('error', None)
    state.update(status='additional_radial65_confirmation_complete', result=result,
                 postprocessing_recovered=True, native_audit_not_repeated_or_changed=True,
                 original_stopping_rounds_not_established=True, manufacturing_release_not_established=True,
                 utc=datetime.now(timezone.utc).isoformat())
    write(OUT/'progress.json', state)
    session = read(CHAT/'progress.json')
    for route in session['routes']:
        if route.get('pid') == state['pid'] and route.get('process_creation_identity') == state['process_creation_identity']:
            route.update(active=False, status=state['status'])
    write(CHAT/'progress.json', session)


if __name__ == '__main__':
    if '--finalize-existing' in sys.argv:
        finalize_existing()
    else:
        main()
