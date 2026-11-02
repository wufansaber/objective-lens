"""Fresh, serialized original85 derivative recovery after explicit 2026-10-28 resume."""
import argparse
import ast
import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
from atomic_progress import read_json_retry as read, write_json_atomic as write
from run_uv355_multistart_campaign import sha

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / 'scripts'
OUT = ROOT / 'results/uv355_fourmm_derivatives_recovery_R126_20261028'
OLD = ROOT / 'results/uv355_fourmm_derivatives_R119_20261027'
CHAT = ROOT / 'results/uv355_chat_continuation_R4_20261025'
LABEL = 'HEIGHT15_FOURMM_GUARD_DERIVATIVES_R126_20261028'
NATIVE = ROOT / 'results/uv355_wavefront_multistart_20261007_103318' / LABEL
os.environ['UV355_FORMAL_POLICY_FILE'] = str(ROOT / 'results/uv355_height_lt15_policy_20261018/formal_policy.json')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def dependencies(paths):
    pending = list(paths)
    found = set()
    while pending:
        p = Path(pending.pop()).resolve()
        if p in found:
            continue
        found.add(p)
        for node in ast.walk(ast.parse(p.read_text(encoding='utf-8-sig'))):
            names = ([q.name.split('.')[0] for q in node.names] if isinstance(node, ast.Import)
                     else [node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) and node.module else [])
            for name in names:
                q = S / (name + '.py')
                if q.is_file():
                    pending.append(q)
    return found


def prepare():
    assert not OUT.exists() and not NATIVE.exists()
    prep = read(OLD / 'preparation.json')
    assert all(sha(p['path']) == p['sha256'] for p in prep['pinned_files'])
    archived = ROOT / 'exports/UV355_USER_PAUSE_20261027_194417'
    supplement = ROOT / 'exports/UV355_USER_PAUSE_20261027_194417_METHOD_SUPPLEMENT'
    assert sha(archived / 'sha256_manifest.json') == 'db3c639e52d9d93d054dc90069a0c9195e4629254f6b5fadc1af0874dd55aebc'
    assert sha(supplement / 'sha256_manifest.json') == '2416b98493f06a4d6bc09ee0e5c56e60dc4abc80e8395d2825b876cc70c527b5'
    previous = read(Path(prep['jobs'][0]['output']))
    assert len(previous['partial_native_derivative_checkpoint']['completed_columns']) == 5
    assert not any(x.get('accepted') for x in previous.get('actual_guarded_steps', []))
    args = list(prep['jobs'][0]['arguments'])
    args[args.index('--folder') + 1] = LABEL
    assert '--derivatives-only' in args and '--cached-guard-jacobian' not in args
    OUT.mkdir()
    shutil.copy2(OLD / 'counterexample_fields.json', OUT / 'counterexample_fields.json')
    prep.update(status='fresh_original85_derivatives_recovery_prepared', run_root=str(OUT),
                recovery_parent=str(OLD), no_partial_cache_reused=True,
                preparation_script_sha256=sha(__file__), source_summary=read(prep['source_review'])['summary'],
                jobs=[dict(script=prep['dispatcher'], arguments=args, output=str(NATIVE / 'staged_fit_progress.json'))])
    paths = dependencies([Path(__file__), Path(prep['worker']), Path(prep['dispatcher'])])
    paths.update(Path(p['path']) for p in prep['pinned_files'])
    paths.add(OUT / 'counterexample_fields.json')
    prep['pinned_files'] = [dict(path=str(p), sha256=sha(p)) for p in sorted(paths)]
    write(OUT / 'preparation.json', prep)
    print(dict(status=prep['status'], pins=len(paths), source=prep['source_sha256']), flush=True)


def run():
    from inspect_uv355_host_processes_20261020 import inventory
    from uv355_verification_priority import process_identity
    assert not (OUT / 'trial_progress.json').exists()
    prep = read(OUT / 'preparation.json')
    assert all(sha(p['path']) == p['sha256'] for p in prep['pinned_files'])
    host = inventory()
    assert host['query_success'] and host['visible_process_count'] > 20
    assert not any(p['name'].lower() == 'opticstudio.exe' for p in host['processes'])
    sp = CHAT / 'progress.json'
    hp = CHAT / 'CONTINUOUS_ACTIVE_HANDOFF_20261022.json'
    session, handoff = read(sp), read(hp)
    live = {p['pid']: p for p in host['processes']}
    assert all(not r.get('active') for r in session['routes'])
    assert not handoff.get('current_finite_trial', {}).get('active')
    for r in [*session['routes'], handoff.get('current_finite_trial', {})]:
        if r:
            assert live.get(r['pid'], {}).get('process_creation_identity') != r['process_creation_identity']
    write(OUT / 'PRELAUNCH_HOST_INVENTORY.json', host)
    write(OUT / 'SESSION_BEFORE_RESUME.json', session)
    write(OUT / 'HANDOFF_BEFORE_RESUME.json', handoff)
    # Preserve old pause markers and only clear the shared batch marker required by this new run.
    marker = NATIVE.parent / 'STOP_REQUEST'
    if marker.exists():
        shutil.copy2(marker, OUT / 'PREVIOUS_SHARED_STOP_REQUEST.txt')
        marker.unlink()
    birth = process_identity(os.getpid())
    assert birth is not None
    state = dict(status='fresh_original85_derivative_recovery_registered', pid=os.getpid(),
                 process_creation_identity=birth, source_sha256=prep['source_sha256'],
                 no_optimization=True, qualified=False, jobs=[], native_instance_cap=1)

    def save():
        state['utc'] = now()
        write(OUT / 'trial_progress.json', state)

    session.update(status=state['status'], active=True, user_task_paused=False, paused_by_user=False,
                   user_latest='\u7ee7\u7eed', resume_requires_explicit_user_instruction=False,
                   conversation_should_remain_active=True, continuous_optimization=False,
                   current_method_root=str(OUT), updated_utc=now())
    handoff.update(status=state['status'], active=True, user_task_paused=False, paused_by_user=False,
                   user_latest='\u7ee7\u7eed', resume_requires_explicit_user_instruction=False,
                   conversation_should_remain_active=True, updated_utc=now())
    old_finite = handoff.pop('current_finite_trial', None)
    if old_finite:
        handoff['previous_paused_R119_preserved'] = old_finite
    handoff['method_rebuild_R119']['active'] = False
    handoff['current_finite_trial'] = dict(root=str(OUT), pid=os.getpid(), process_creation_identity=birth,
        progress=str(OUT / 'trial_progress.json'), active=True, kind='fresh_derivatives_only_R126',
        automatic_adoption=False, qualified=False)
    handoff['method_rebuild_R126'] = dict(root=str(OUT), script=str(Path(__file__)),
        source_sha256=prep['source_sha256'], active=True, qualified=False)
    save()
    write(sp, session)
    write(hp, handoff)
    process = None
    try:
        assert not (OUT / 'STOP_REQUEST').exists() and not read(sp).get('user_task_paused')
        job = prep['jobs'][0]
        dest = OUT / 'JOB_1'
        dest.mkdir()
        with (dest / 'stdout.log').open('w') as so, (dest / 'stderr.log').open('w') as se:
            process = subprocess.Popen([sys.executable, job['script'], *job['arguments']], cwd=ROOT,
                env=dict(os.environ, UV355_METHOD_REBUILD_PARENT_PID=str(os.getpid()),
                         UV355_COUPLED_SPOT_RUN_ROOT=str(OUT)),
                stdout=so, stderr=se, creationflags=subprocess.CREATE_NO_WINDOW)
            state.update(status='collecting_fresh_original85_guard_spot_front_phase_derivatives',
                child_pid=process.pid, child_process_creation_identity=process_identity(process.pid),
                child_script=job['script'], current_native_progress=job['output'])
            save()
            print(dict(status=state['status'], pid=os.getpid(), birth=birth, child_pid=process.pid), flush=True)
            code = process.wait()
            assert code == 0, 'Native derivative job failed; preserve all evidence'
        fit = read(job['output'])
        assert fit['status'] == 'original85_native_derivative_collection_complete_no_optimization'
        assert fit['partial_native_derivative_checkpoint']['completed_columns'] == list(range(85))
        assert fit['initial_sha256'] == prep['source_sha256']
        assert not any(x.get('accepted') for x in fit.get('actual_guarded_steps', []))
        assert all(sha(p['path']) == p['sha256'] for p in prep['pinned_files'])
        for _ in range(60):
            post = inventory()
            assert post['query_success']
            if not any(p['name'].lower() == 'opticstudio.exe' for p in post['processes']):
                break
            time.sleep(.5)
        assert not any(p['name'].lower() == 'opticstudio.exe' for p in post['processes'])
        write(OUT / 'POST_DIAGNOSTIC_HOST_INVENTORY.json', post)
        state.update(status='fresh_original85_derivatives_complete_requires_independent_review',
                     completed_columns=85, native_count_after=0, source_and_dependency_bytes_unchanged=True)
        state['jobs'].append(dict(index=1, output=job['output'], exit_code=code))
    except BaseException:
        state.update(status='derivative_recovery_failure_preserved', error=traceback.format_exc())
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait()
        raise
    finally:
        save()
        handoff = read(hp)
        if handoff.get('current_finite_trial', {}).get('pid') == os.getpid():
            finished = handoff.pop('current_finite_trial')
            finished.update(active=False, status=state['status'])
            handoff['completed_or_interrupted_R126'] = finished
            handoff['method_rebuild_R126'].update(active=False, status=state['status'])
            handoff.update(active=False, status=state['status'], updated_utc=now())
            write(hp, handoff)
        session = read(sp)
        if not session.get('user_task_paused'):
            session.update(active=False, status=state['status'], updated_utc=now())
            write(sp, session)
    print(dict(status=state['status'], qualified=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'run'])
    {'prepare': prepare, 'run': run}[parser.parse_args().mode]()
