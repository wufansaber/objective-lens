"""Independent full-field native review of the R943 design; no MTF pass-count gate."""
from datetime import datetime,timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import numpy as np
from atomic_progress import read_json_retry as read,write_json_atomic as write
from run_uv355_multistart_campaign import sha
from physical_prescription_audit import parse_model
from optimize_until_stable import mf_signature
from uv355_acceptance_revision_R943_20261102 import reassess
from uv355_verification_priority import process_identity

ROOT=Path(__file__).resolve().parents[1]
UP=ROOT/'results/uv355_C628_focal_design_R945_20261102'
OUT=ROOT/'results/uv355_R943_independent_review_R946_20261102'
CHAT=ROOT/'results/uv355_chat_continuation_R4_20261025'


def now():return datetime.now(timezone.utc).isoformat()


def active():
    assert not read(CHAT/'progress.json')['user_task_paused'] and not(OUT/'STOP_REQUEST').exists()


def coordinates(model,source):
    with np.load(model.with_suffix('.npz')) as z:
        x=z['coordinates']; initial=z['initial'];scales=z['scales'];variables=z['variables'].tolist()
        assert len(x)==85 and len(variables)==85 and np.linalg.matrix_rank(z['T'])==85
        surfaces=parse_model(model)[2]
        values=np.array([surfaces[sn]['curvature'] if col==2 else surfaces[sn]['thickness'] if col==3 else
                         surfaces[sn]['conic'] if col==9 else surfaces[sn]['parameters'].get(col-11,0.) for sn,col in variables])
        error=float(np.max(abs((values-initial)/scales-x)));assert error<1e-7
    assert mf_signature(model.with_suffix('.MF'))==mf_signature(source.with_suffix('.MF'))
    assert len(mf_signature(model.with_suffix('.MF')))==8794
    return dict(saved_original85_normalized_error=error,all8794_MF_rows_preserved=True,
                native_original85_flags_checked_separately_in_both_reviews=True)


def main():
    assert not OUT.exists();OUT.mkdir(); prep=read(UP/'preparation.json');policy=read(prep['policy'])
    assert sha(prep['policy'])==prep['policy_sha256'] and not policy['MTF_hard_acceptance_requirement']
    write(OUT/'preparation.json',dict(source_profile=str(UP),policy=prep['policy'],policy_sha256=prep['policy_sha256'],
          MTF_comparison_gates=0,native_auditor='audit_uv355_extended_thickness_R352_20261031.py',
          historical_native_checks_reinterpreted_in_separate_R943_reports=True,no_old_report_overwritten=True))
    state=dict(status='waiting_for_new_policy_candidate',active=True,read_only=True,pid=os.getpid(),
               process_creation_identity=process_identity(os.getpid()),reviews=[],child=None,qualified=False)
    def save():state['utc']=now();write(OUT/'progress.json',state)
    session=read(CHAT/'progress.json');session['routes'].append(dict(state,root=str(OUT),progress=str(OUT/'progress.json'),
             role='R943_independent_candidate_review',kind='readonly_new_policy_full129_513_review'))
    write(CHAT/'progress.json',session);save()
    reviewed=set()
    try:
        while True:
            active();up=read(UP/'progress.json')
            records=[r for r in up.get('trials',[]) if r.get('model') and r.get('sha256') not in reviewed]
            if not records:
                if not up['active']:break
                time.sleep(4);continue
            # Review the best available complete saved candidate first. Others
            # remain explicitly pending until their full native audits finish.
            row=min(records,key=lambda r:r['score']);model=Path(row['model']);digest=row['sha256']
            assert sha(model)==digest
            folder=OUT/f'CANDIDATE_{len(reviewed)+1:02d}';folder.mkdir()
            check=coordinates(model,Path(prep['source_model']));write(folder/'COORDINATE_AND_MF_PROOF.json',check)
            reports=[];state.update(status='native_full_field_candidate_review',current_sha256=digest);save()
            for tag,args,count in [('CIRCLE129',[],129),('EXTENDED513',['--radial-count','33','--azimuth-count','16'],513)]:
                destination=folder/tag
                with (folder/f'{tag}.log').open('w',encoding='utf-8') as log:
                    child=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/audit_uv355_extended_thickness_R352_20261031.py'),
                          '--model',str(model),'--out',str(destination),*args],stdout=log,stderr=subprocess.STDOUT,cwd=str(ROOT),creationflags=0x08000000)
                    state['child']=dict(pid=child.pid,process_creation_identity=process_identity(child.pid),tag=tag);save()
                    while child.poll() is None:active();time.sleep(2)
                    assert child.returncode==0,f'{tag} failed; inspect preserved native log'
                native=read(destination/'circle_audit.json');assert native['sha256']==digest and native['field_count']==count
                result=reassess(native,policy);result.update(original_review=str(destination/'circle_audit.json'),
                       original_review_sha256=sha(destination/'circle_audit.json'))
                write(destination/'R943_ACCEPTANCE.json',result);reports.append(result)
            assert sha(model)==digest and sha(prep['policy'])==prep['policy_sha256']
            complete=dict(model=str(model),sha256=digest,policy=prep['policy'],policy_sha256=prep['policy_sha256'],
                          native_reviews=reports,coordinate_proof=check,source_trial=row,
                          MTF_used_for_acceptance=False,full_field_review_complete=True,qualified=False,
                          full_4mm_design_accepted=False,stopping_and_manufacturing_evidence_not_established=True,
                          MTF_curves_for_user_judgment_still_to_be_delivered=True)
            write(folder/'FULL_R943_REVIEW.json',complete);state['reviews'].append(complete);reviewed.add(digest);save()
            if all(all(r['checks'][k] for k in r['checks'] if k not in ('worst_wavefront','spot_airy')) for r in reports):
                pointer=ROOT/'key_results/LATEST_R943_REVIEWED.json'
                previous=read(pointer) if pointer.exists() else None
                if previous is None or row['score']<previous['source_trial']['score']:
                    key=ROOT/'key_results/FOV_4p0mm'/f'R943_REVIEWED_{digest[:12]}';key.mkdir(exist_ok=False)
                    for path,name in [(model,'prescription.zmx'),(model.with_suffix('.MF'),'prescription.MF'),
                                      (folder/'FULL_R943_REVIEW.json','FULL_R943_REVIEW.json'),
                                      (folder/'COORDINATE_AND_MF_PROOF.json','COORDINATE_AND_MF_PROOF.json'),
                                      (Path(prep['policy']),'formal_policy.json')]:
                        shutil.copy2(path,key/name);assert sha(key/name)==sha(path)
                    complete['key_result_directory']=str(key);write(pointer,complete)
                    root=read(ROOT/'CONTINUATION.json');root['latest_R943_reviewed_candidate']=complete;write(ROOT/'CONTINUATION.json',root)
            state['child']=None;save()
        state['status']='all_saved_R943_candidates_fully_reviewed' if reviewed else 'design_ended_without_saved_candidate'
    except BaseException:state.update(status='R943_independent_review_failure_preserved',error=traceback.format_exc());raise
    finally:
        state['active']=False;save()
        session=read(CHAT/'progress.json')
        for r in session['routes']:
            if r.get('pid')==os.getpid() and r.get('process_creation_identity')==state['process_creation_identity']:
                r.update(active=False,status=state['status'])
        write(CHAT/'progress.json',session)


if __name__=='__main__':main()
