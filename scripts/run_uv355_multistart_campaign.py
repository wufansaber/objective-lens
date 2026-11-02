"""Validated pilot then queued structured multistart. Never infer acceptance from search MF."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from atomic_progress import read_json_retry, write_json_atomic
from field_stage_4mm import invariants
from physical_prescription_audit import parse_model
from optimize_until_stable import mf_signature
from wavefront_repair_policy import repair_cost

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts'


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def maximum_shift(record):
    return max(abs(r['object_focus_shift_um']) for r in record['field_depth_guard']['comparisons'])


def metrics(record):
    return dict(wfe=max(record['worst_wfe'],record.get('rectangular_worst_wfe',0.)),
                axis=record['on_axis_worst_wfe'], depth=maximum_shift(record),
                airy=max(record['worst_airy'],record.get('rectangular_worst_airy',0.)),
                front=record['front_mrad'])


def command(model, out, profile, mode='baseline', iterations=3, penalty=2., audit_lane=False):
    cmd=[sys.executable,str(SCRIPTS/'edge_constrained_polish.py'),'--model',str(model),'--out-dir',str(out),
         '--object-field-radius-mm','2','--continuous-quality','--quality-priority','wavefront',
         '--objective','all_field_wavefront','--edge-wfe-limit','.05','--full-field-wfe-limit','.05',
         '--on-axis-wfe-limit','.04','--axis-best-guard','--simplified-mechanical-guards',
         '--allow-uncovered-band','--chromatic-control','--aberration-focus','--chromatic-objective-weight','0',
         '--optical-field-count','17','--front-field-count','17','--front-limit-mrad','.499',
         '--front-ray-rings','16','--front-ray-arms','32','--focus-pupil-rings','32','--focus-pupil-arms','64',
         '--batch-rays','--cache-front-rays','--radius','16','--fd-step','.00005',
         '--curvature-coordinate-scale','20','--image-distance-coordinate-scale','5',
         '--iterations',str(iterations),'--repair-penalty',str(penalty)]
    if profile in ('full','full-circle','full-disk'):cmd+=['--rectangular-guard','--rectangular-grid64-guard']
    if profile in ('full-circle','full-disk'):cmd+=['--rectangular-diagonal-guard']
    if profile=='full-disk':
        cmd+=['--rectangular-intermediate-guard']
        cmd[cmd.index('--optical-field-count')+1]='33'
    if mode=='baseline':cmd+=['--baseline-only']
    else:cmd+=['--wavefront-repair']
    if audit_lane:
        if mode!='baseline':raise ValueError('Audit lane is read-only for profile and seed screening')
        cmd+=['--read-only-audit-lane']
    return cmd


def run_worker(model, out, profile, mode='baseline', iterations=3, penalty=2., audit_lane=False):
    out.mkdir(parents=True,exist_ok=True)
    cmd=command(model,out,profile,mode,iterations,penalty,audit_lane)
    write_json_atomic(out/'launch.json',dict(command=cmd,profile=profile,mode=mode,source_sha256=sha(model)))
    with (out/'output.log').open('w',encoding='utf-8') as stream:
        child=subprocess.Popen(cmd,stdout=stream,stderr=subprocess.STDOUT)
        write_json_atomic(out/'process.json',dict(worker_pid=child.pid,controller_pid=os.getpid()))
        code=child.wait()
    data=read_json_retry(out/'minimax_progress.json')
    if code or data['status']=='error' or data.get('error'):
        raise RuntimeError(f'Worker failed; preserved logs at {out}: {data.get("error",code)}')
    assert data['optical_variable_count']==85 and data['source_MF_count']==8794
    assert data['evaluation_failure_count']==0 and data['baseline_repeatability_max_abs_constraint_change']<=1e-6
    return data


def freeze(record,out):
    out.mkdir(parents=True,exist_ok=True)
    source=Path(record['model']);model=out/'UNQUALIFIED_CANDIDATE.zmx'
    shutil.copy2(source,model);shutil.copy2(source.with_suffix('.MF'),model.with_suffix('.MF'))
    assert sha(source)==sha(model) and invariants(model)['static_invariants_pass']
    assert mf_signature(source.with_suffix('.MF'))==mf_signature(model.with_suffix('.MF'))
    write_json_atomic(out/'freeze_receipt.json',dict(record=record,model=str(model),sha256=sha(model),MF_sha256=sha(model.with_suffix('.MF')),qualified=False))
    return model


def independent(model,out,extended=False):
    cmd=[sys.executable,str(SCRIPTS/'audit_uv355_circle4mm.py'),'--model',str(model),'--out',str(out)]
    if extended:cmd+=['--radial-count','33','--azimuth-count','16']
    out.mkdir(parents=True,exist_ok=True)
    with (out/'output.log').open('w',encoding='utf-8') as stream:
        code=subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT).returncode
    a=read_json_retry(out/'circle_audit.json')
    assert code==0 and a['status']=='complete' and a['sha256']==sha(model)
    assert a['checks']['transport_verified'] and a['checks']['source_unchanged'] and a['ray_failure_count']==0
    return a


def perturb(source,target,variables,rng,amplitude,group,scaled_coordinates=False):
    raw,text,surfaces=parse_model(source)
    chunks=re.split(r'(?m)^SURF ',text)
    sections={int(s.splitlines()[0]):i for i,s in enumerate(chunks[1:],1)}
    direction=rng.normal(size=85)
    changes=[]
    for i,v in enumerate(variables):
        if 'surface' not in v:continue
        sn=v['surface'];col=v['column_name']
        if group=='front' and sn>11:continue
        if group=='tube' and sn<=11:continue
        if group=='shape' and col=='Thickness':continue
        scale=v['scale'] if scaled_coordinates else v.get('original_scale',v['scale'])
        delta=float(amplitude*direction[i]*scale)
        s=surfaces[sn]
        if col=='Radius': key='CURV'; old=s['curvature'];pattern=r'(?m)^(\s*CURV\s+)(\S+)'
        elif col=='Thickness': key='DISZ';old=s['thickness'];pattern=r'(?m)^(\s*DISZ\s+)(\S+)'
        elif col=='Conic': key='CONI';old=s['conic'];pattern=r'(?m)^(\s*CONI\s+)(\S+)'
        else:
            order=v['zmx_parameter_order'];key=f'PARM {order}';old=s['parameters'].get(order,0.)
            pattern=rf'(?m)^(\s*PARM\s+{order}\s+)(\S+)'
        section=chunks[sections[sn]]
        section,count=re.subn(pattern,lambda m:m.group(1)+format(old+delta,'.16E'),section,count=1)
        if count!=1:raise RuntimeError(f'Cannot mutate existing variable {sn} {key}')
        chunks[sections[sn]]=section
        changes.append(dict(surface=sn,column=col,old=old,new=old+delta))
    target.write_bytes('SURF '.join(chunks).encode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8'))
    shutil.copy2(source.with_suffix('.MF'),target.with_suffix('.MF'))
    assert invariants(target)['static_invariants_pass']
    return changes


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);args=p.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    progress=out/'campaign_progress.json'
    if progress.exists():raise RuntimeError('Existing campaign: refuse duplicate launch')
    plan=read_json_retry(out/'campaign_plan.json')
    state=dict(status='validating_profiles',controller_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
               phase='three_anchor_profile_comparison',completed=[],numerical_failures=[],
               max_parallel_optimizer_branches=3,FFT_checks_run=False,full_4mm_design_accepted=False,
               scheduled_automation_status='DELETED',continuous_until_explicit_user_stop=True)
    def write():
        state['updated_utc']=datetime.now(timezone.utc).isoformat();write_json_atomic(progress,state)
    def stopped():return (out/'STOP_REQUEST').exists()
    write()
    try:
        anchors=plan['anchors']
        def compare(item):
            model=Path(item['model']);name=item['name'];assert sha(model)==item['sha256']
            full=run_worker(model,out/'VALIDATION'/name/'FULL','full')
            light=run_worker(model,out/'VALIDATION'/name/'GQ','light')
            a=metrics(full['baseline']);b=metrics(light['baseline'])
            passed=(abs(a['wfe']-b['wfe'])<=.001 and abs(a['axis']-b['axis'])<=.0005
                    and abs(a['depth']-b['depth'])<=.01 and abs(a['airy']-b['airy'])<=.08
                    and abs(a['front']-b['front'])<=.001)
            receipt=dict(name=name,source_sha256=sha(model),full=a,light=b,passed=passed,
                full_seconds=full['elapsed_seconds'],light_seconds=light['elapsed_seconds'],
                variables_preserved=85,original_MF_preserved=8794,acceptance_limits_unchanged=True)
            write_json_atomic(out/'VALIDATION'/name/'profile_comparison.json',receipt)
            return receipt
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            comparisons=list(pool.map(compare,anchors[:3]))
        profile='light' if all(x['passed'] for x in comparisons) else 'full'
        state.update(profile_validation=comparisons,selected_search_profile=profile,phase='pilot_short_optimization',status='running')
        write()
        def pilot(item):
            name=item['name'];folder=out/'PILOT'/name
            result=run_worker(Path(item['model']),folder,profile,'search',3)
            record=result.get('best_wavefront_repair')
            return dict(name=name,folder=str(folder),record=record,callbacks=result.get('wavefront_repair_iterations',[]),
                        baseline=metrics(result['baseline']),evaluation_count=result['evaluations'])
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            for result in pool.map(pilot,anchors[:3]):
                state['completed'].append(result);write()
        if stopped():state['status']='stopped_by_user';write();return
        # Always verify a new strategy independently before queue expansion.
        verified=[]
        for item in state['completed']:
            if not item['record']:continue
            model=freeze(item['record'],Path(item['folder'])/'FROZEN')
            a=independent(model,Path(item['folder'])/'CIRCLE129')
            item['audit']=str(Path(item['folder'])/'CIRCLE129/circle_audit.json')
            item['independent_summary']=a['summary'];item['sampled_pass']=a['sampled_requirements_pass']
            if a['summary']['axis_wfe_worst_waves']<=.04 and item['callbacks'] and a['summary']['wfe_worst_waves']<item['baseline']['wfe']-1e-5:
                verified.append(item)
            write()
        if not verified:
            state.update(status='pilot_no_verified_wavefront_gain_requires_strategy_review',phase='pilot_evidence_preserved',
                         queue_expansion_enabled=False,no_convergence_claim=True)
            write();return
        state.update(phase='structured_100_seed_queue',queue_expansion_enabled=True);write()
        variables=read_json_retry(Path(verified[0]['folder'])/'minimax_progress.json')['variables']
        rng=np.random.default_rng(20261007);candidates=[];hashes=set()
        for i in range(100):
            anchor=anchors[0 if i<40 else 1 if i<70 else 2 if i<90 else 3]
            folder=out/'SEED_POOL'/f'{i+1:03d}';folder.mkdir(parents=True)
            model=folder/'UNQUALIFIED_SEED.zmx';amplitude=(.003,.01,.03,.08)[i%4]
            group=('tube','shape','front','all')[i%4]
            changes=perturb(Path(anchor['model']),model,variables,rng,amplitude,group)
            identity=sha(model)
            assert identity not in hashes;hashes.add(identity)
            item=dict(index=i+1,model=str(model),sha256=identity,source=anchor['name'],amplitude=amplitude,group=group,changes=changes)
            write_json_atomic(folder/'seed_receipt.json',item);candidates.append(item)
        write_json_atomic(out/'seed_pool_manifest.json',candidates)
        screened=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures={pool.submit(run_worker,Path(c['model']),out/'SCREEN'/f'{c["index"]:03d}',profile):c for c in candidates}
            for future in concurrent.futures.as_completed(futures):
                if stopped():break
                item=futures[future]
                try:
                    d=future.result();r=d['baseline'];ep=d['epigraph']['constraint_count'];g=np.array(d['baseline_constraint_values'])
                    cost=repair_cost(g[:-ep],d['constraint_labels'][:-ep],r['epigraph_t']-g[-ep:],2.)
                    screened.append(dict(candidate=item,metrics=metrics(r),score=cost))
                except Exception as exc:state['numerical_failures'].append(dict(index=item['index'],error=str(exc)))
                state['screened_count']=len(screened);write()
        ranked=sorted(screened,key=lambda c:(c['metrics']['axis']>.04,c['score']))[:20]
        write_json_atomic(out/'screen_ranking.json',ranked)
        state.update(phase='top20_local_search');write()
        def refine(item):
            c=item['candidate'];folder=out/'REFINE'/f'{c["index"]:03d}'
            d=run_worker(Path(c['model']),folder,profile,'search',8)
            return dict(index=c['index'],folder=str(folder),record=d.get('best_wavefront_repair'),callbacks=d.get('wavefront_repair_iterations',[]))
        refined=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures={pool.submit(refine,c):c for c in ranked}
            for future in concurrent.futures.as_completed(futures):
                try:refined.append(future.result())
                except Exception as exc:state['numerical_failures'].append(dict(stage='refine',error=str(exc)))
                state['refined_count']=len(refined);write()
        finalists=sorted([r for r in refined if r['record']],key=lambda r:(r['record']['on_axis_worst_wfe']>.04,r['record']['strategy_cost']))[:5]
        state.update(phase='finalist_independent_review');write()
        for item in finalists:
            model=freeze(item['record'],Path(item['folder'])/'FROZEN')
            a=independent(model,Path(item['folder'])/'CIRCLE129')
            item['summary']=a['summary'];item['sampled_pass']=a['sampled_requirements_pass']
            if a['sampled_requirements_pass']:
                b=independent(model,Path(item['folder'])/'EXTENDED513',True)
                item['extended_sampled_pass']=b['sampled_requirements_pass']
                if b['sampled_requirements_pass']:
                    destination=ROOT/'exports'/('UV355_MULTISTART_SAMPLED_PASS_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
                    shutil.copytree(Path(item['folder']),destination)
            state['finalists']=finalists;write()
        # Continue improving independently reviewed finalists; finite pools do not mean convergence.
        cycle=0
        while not stopped() and finalists:
            cycle+=1;state.update(phase='continuous_finalist_refinement',cycle=cycle);write()
            for item in finalists:
                model=Path(item['folder'])/'FROZEN/UNQUALIFIED_CANDIDATE.zmx'
                folder=out/'CONTINUATION'/f'CYCLE_{cycle:03d}'/f'{item["index"]:03d}'
                d=run_worker(model,folder,'full','search',8,penalty=(2.,5.,10.)[(cycle-1)%3])
                if d.get('best_wavefront_repair'):
                    candidate=freeze(d['best_wavefront_repair'],folder/'FROZEN');a=independent(candidate,folder/'CIRCLE129')
                    if a['summary']['axis_wfe_worst_waves']<=.04 and a['summary']['wfe_worst_waves']<item['summary']['wfe_worst_waves']:
                        item.update(folder=str(folder),summary=a['summary'])
                        if a['sampled_requirements_pass']:independent(candidate,folder/'EXTENDED513',True)
                state['finalists']=finalists;write()
    except BaseException as exc:
        state.update(status='campaign_error_preserved',error=str(exc),no_convergence_claim=True);write();raise


if __name__=='__main__':main()
