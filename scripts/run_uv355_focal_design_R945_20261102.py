"""C628 fresh native85 collection and R943 WFE/Airy minimax design, no MTF gate."""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from atomic_progress import read_json_retry as read,write_json_atomic as write
from run_uv355_multistart_campaign import sha
from uv355_verification_priority import process_identity
from inspect_uv355_host_processes_20261020 import inventory
from uv355_focal_runtime_R944_20261102 import ROOT,POLICY,policy,context,vector,proposal,method

CHAT=method.CHAT
OUT=ROOT/'results/uv355_C628_focal_design_R945_20261102'
REVIEW=ROOT/'results/uv355_fa620_smaller_snapshot_review_R934_20261102'


def now():return datetime.now(timezone.utc).isoformat()


def active():
    assert not read(CHAT/'progress.json')['user_task_paused'] and not (OUT/'STOP_REQUEST').exists()
    policy()


def pins():
    p=read(OUT/'preparation.json')
    assert all(sha(q['path'])==q['sha256'] for q in p['pinned_files'])
    return p


def prepare():
    from run_uv355_fourmm_derivatives_recovery_R126_20261028 import dependencies
    assert not OUT.exists()
    p=policy();report=read(REVIEW/'trial_progress.json')['reviews'][0]
    proof=read(REVIEW/'INDEPENDENT_NATIVE_METHOD_VERIFICATION_R442_20261101.json')
    assert proof['all_saved_candidates_verified'] and proof['candidates'][0]['sha256']==report['sha256']==sha(report['model'])
    offline=read(POLICY.parent/'ACCEPTANCE_REASSESSMENT.json')['candidates'][1]
    assert offline['sha256']==report['sha256']
    OUT.mkdir()
    paths=dependencies([Path(__file__),ROOT/'scripts/uv355_focal_runtime_R944_20261102.py'])
    paths.update([POLICY,POLICY.parent/'ACCEPTANCE_REASSESSMENT.json',Path(report['model']),Path(report['model']).with_suffix('.MF'),
                  REVIEW/'trial_progress.json',REVIEW/'INDEPENDENT_NATIVE_METHOD_VERIFICATION_R442_20261101.json',Path(report['review']),
                  ROOT/'results/uv355_c628_pending_dense_R936_20261102/BOUNDARY_POINTS.json',
                  ROOT/'results/uv355_c628_pending_dense_R936_20261102/ACTUAL_FULL513_BASELINE.json',
                  ROOT/'scripts/measure_uv355_real_chromatic_source_R714_20261101.py'])
    write(OUT/'preparation.json',dict(status='R943_fresh_C628_design_prepared',source_model=report['model'],
        source_sha256=report['sha256'],source_review=report['review'],policy=str(POLICY),policy_sha256=sha(POLICY),
        WFE_limit=.055,axis_limit=.04,curvature_object_limit_um=.493,astigmatism_object_limit_um=.493,
        MTF_constraints=0,MTF_objective_terms=0,all85_newly_measured_at_C628=True,
        previous_four_valid_columns_retained_but_not_reused_due_to_changed_metric_and_focal_sampling=True,
        max_total_SDKs=4,max_optimizer_SDKs=3,qualified=False,
        pinned_files=[dict(path=str(q),sha256=sha(q)) for q in sorted(paths)]))


def baseline_check(value,points):
    ref=read(ROOT/'results/uv355_c628_pending_dense_R936_20261102/ACTUAL_FULL513_BASELINE.json')
    errors=dict(WFE=float(np.max(abs(value['dense_WFE']-ref['WFE']))),Airy=float(np.max(abs(value['dense_Airy']-ref['Airy']))))
    assert max(errors.values())<1e-8,errors
    native=read(pins()['source_review']); focal={(r['wave'],r['radius_normalized']):r for r in native['focus_samples'] if r['azimuth_deg']==0}
    f=value['focus_object_signed'];errs=[]
    for w in (1,2,3):
        for j in range(33):
            r=focal[w,j/32]
            errs.extend([abs(f[w-1,j].mean()-r['field_curvature_object_um']),abs(f[w-1,j,1]-f[w-1,j,0]-r['astigmatism_object_um'])])
    errors['field_curvature_astigmatism_object_um']=max(errs)
    assert max(errs)<1e-8,errors
    return errors


def part(which):
    from verification_capacity import verification_slot
    p=pins();out=OUT/f'PART_{which}';out.mkdir()
    state=dict(status='waiting_current_policy_native_measurement_seat',active=True,read_only=True,pid=os.getpid(),
               process_creation_identity=process_identity(os.getpid()),completed_columns=[],evaluations=0,source_sha256=p['source_sha256'])
    def save():state['utc']=now();write(out/'progress.json',state)
    app=None;save()
    try:
        with verification_slot():
            active();app,api,bridge=method.make_application();system=app.PrimarySystem
            evaluate,apply,initial,scales,variables,template,signature,chart,points,color=context(system,api,bridge,Path(p['source_model']),out,state,save,active)
            base=evaluate(np.zeros(85));state['baseline_errors']=baseline_check(base,points)
            color0,colorproof=color(np.zeros(85),independent=True);write(out/'INDEPENDENT_COLOR_BASELINE.json',colorproof)
            write(out/'LABELS.json',dict(optical=base['optical_labels'],physical=base['physical_labels']))
            basevec=vector(base);jac={k:np.full((len(v),85),np.nan) for k,v in basevec.items()}
            jc=np.full((78,85),np.nan)
            np.savez(out/'BASELINE.npz',**basevec,color=color0,initial=initial,scales=scales,variables=variables,T=chart.T,source_sha256=p['source_sha256'])
            state.update(status='collecting_fresh_R943_native85_columns');save()
            for col in range(which,85,3):
                active();tick=time.monotonic();h=5e-5;direction=np.eye(85)[col]
                for retry in range(10):
                    try:minus=evaluate(-h*direction);plus=evaluate(h*direction);break
                    except Exception:
                        if retry==9:raise
                        h*=.5
                for key in jac:jac[key][:,col]=(vector(plus)[key]-vector(minus)[key])/(2*h)
                # Colour differences are tiny: use the established larger step
                # and Richardson extrapolation, in this exact source frame.
                cm,_=color(-.01*direction);cp,_=color(.01*direction)
                cmm,_=color(-.02*direction);cpp,_=color(.02*direction)
                jc[:,col]=(4*(cp-cm)/.02-(cpp-cmm)/.04)/3
                state['completed_columns'].append(col);state['latest_column_seconds']=time.monotonic()-tick
                state.setdefault('actual_steps',{})[str(col)]=h
                np.savez(out/'PARTIAL_J85.npz',**{'J_'+k:v for k,v in jac.items()},J_color=jc,columns=state['completed_columns'],
                         source_sha256=p['source_sha256'],T=chart.T,initial=initial,scales=scales,variables=variables)
                save()
            replay=evaluate(np.zeros(85));state['source_replay_error']=max(float(np.max(abs(vector(replay)[k]-v))) for k,v in basevec.items())
            assert state['source_replay_error']<1e-8
            state['status']='fresh_R943_native_part_complete'
    except BaseException:state.update(status='fresh_R943_native_part_failed',error=traceback.format_exc());raise
    finally:
        if app is not None:app.CloseApplication()
        state['active']=False;save();pins()


def merit(value):
    return 1000*max(0,value['current_worst_WFE']/.055-1)**2+500*max(0,value['current_worst_Airy']-1)**2


def optimize(state,save):
    from uv355_optimizer_capacity import optimizer_slot
    p=pins();out=OUT/'OPTIMIZER';out.mkdir();app=None
    try:
        with optimizer_slot():
            active();app,api,bridge=method.make_application();system=app.PrimarySystem
            evaluate,apply,initial,scales,variables,template,signature,chart,points,color=context(system,api,bridge,Path(p['source_model']),out,state,save,active)
            base=evaluate(np.zeros(85));baseline_check(base,points)
            with np.load(OUT/'FRESH_CURRENT_POLICY_J85.npz') as z:data={k:z[k].copy() for k in z.files}
            for key,value in vector(base).items():assert np.max(abs(value-data['baseline_'+key]))<1e-8
            assert np.max(abs(chart.T-data['T']))<1e-10
            jac={key:data['J_'+key] for key in vector(base)}
            color0,_=color(np.zeros(85),independent=True);assert np.max(abs(color0-data['color0']))<1e-8
            jcolor=data['J_color'];checks=[]
            for k in range(3):
                d=np.sin((k+1)*(np.arange(85)+1.));d/=np.linalg.norm(d)
                m,_=color(-.005*d);v,_=color(.005*d);observed=(v-m)/.01;pred=jcolor@d
                absolute=float(np.max(abs(observed-pred)));relative=float(np.linalg.norm(observed-pred)/max(np.linalg.norm(observed),1e-15))
                checks.append(dict(direction=k,absolute=absolute,relative=relative,passed=absolute<5e-5 and relative<.03))
            state['color_direction_QC']=checks;save();assert all(q['passed'] for q in checks),checks
            state.update(status='optimizing_new_policy_without_MTF_gate',trials=[]);save()
            oldscore=merit(base);bestscore=oldscore
            for radius in (.5,1.,.25,2.):
                step,proof=proposal(base,jac,radius,color0,jcolor)
                h=.001
                for retry in range(8):
                    try:minus=evaluate(-h*step);plus=evaluate(h*step);break
                    except Exception:
                        if retry==7:raise
                        h*=.5
                check={}
                for key in ('optical','physical','dense_WFE','dense_Airy'):
                    observed=(vector(plus)[key]-vector(minus)[key])/(2*h);pred=jac[key]@step
                    check[key]=float(np.linalg.norm(observed-pred)/max(np.linalg.norm(observed),1e-12))
                state.setdefault('whole_direction_QC',[]).append(dict(radius=radius,h=h,relative_errors=check));save()
                assert max(check.values())<.03,check
                for fraction in (1.,.75,.5,.25,.125,.0625):
                    x=fraction*step
                    try:value=evaluate(x)
                    except Exception as error:
                        state['trials'].append(dict(radius=radius,fraction=fraction,error=repr(error)));save();continue
                    passed=base['optical']>=0
                    safe=bool(value['physical_pass'] and min(value['physical'])>=-1e-8 and min(value['optical'][passed])>=-1e-8)
                    row=dict(radius=radius,fraction=fraction,safe=safe,score=merit(value),WFE=value['current_worst_WFE'],Airy=value['current_worst_Airy'],
                             curvature_object_um=value['current_curvature_object_um'],astigmatism_object_um=value['current_astigmatism_object_um'])
                    state['trials'].append(row);save()
                    if safe and row['score']<bestscore-1e-7 and row['WFE']<base['current_worst_WFE']-1e-7:
                        apply(x);system.MFE.LoadMeritFunction(str(Path(p['source_model']).with_suffix('.MF')))
                        name=out/f'UNQUALIFIED_R943_CANDIDATE_{len(state["trials"]):03d}.zmx'
                        system.SaveAs(str(name));system.MFE.SaveMeritFunction(str(name.with_suffix('.MF')))
                        assert method.geom.mf_signature(name.with_suffix('.MF'))==signature
                        assert method.geom.invariants(name)['static_invariants_pass']
                        dense=method.geom.physical_audit(name,16385);assert dense['passed'];write(name.with_suffix('.physical.json'),dense)
                        np.savez(name.with_suffix('.npz'),coordinates=chart.to_native(x),search_coordinates=x,initial=initial,scales=scales,variables=variables,T=chart.T)
                        row.update(model=str(name),sha256=sha(name),full129_513_review_required=True,qualified=False,proposal=proof)
                        bestscore=row['score'];state['best_candidate']=dict(row);save()
                        system.MFE.LoadMeritFunction(str(template));system.MFE.CalculateMeritFunction()
            state['status']='R943_native_design_batch_complete_full_review_required'
    finally:
        if app is not None:app.CloseApplication()


def run():
    p=pins();active();assert not(OUT/'progress.json').exists()
    state=dict(status='starting_current_policy_design',active=True,read_only=False,pid=os.getpid(),process_creation_identity=process_identity(os.getpid()),
               source_sha256=p['source_sha256'],evaluations=0,qualified=False,full_4mm_design_accepted=False,MTF_gate=False,children=[])
    def save():state['utc']=now();write(OUT/'progress.json',state)
    session=read(CHAT/'progress.json');session['routes'].append(dict(state,root=str(OUT),progress=str(OUT/'progress.json'),role='current_policy_design_controller',kind='R943_focal_native_minimax'))
    write(CHAT/'progress.json',session);save();children=[]
    try:
        for k in range(3):
            stream=(OUT/f'part_{k}.log').open('w',encoding='utf-8')
            child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'part','--part',str(k)],stdout=stream,stderr=subprocess.STDOUT,cwd=str(ROOT),creationflags=0x08000000)
            children.append(child);state['children'].append(dict(pid=child.pid,process_creation_identity=process_identity(child.pid),part=k));save()
        while any(c.poll() is None for c in children):
            active();state['parts']=[read(OUT/f'PART_{k}/progress.json') if (OUT/f'PART_{k}/progress.json').exists() else dict(status='starting') for k in range(3)]
            if any(c.poll() not in (None,0) for c in children):raise RuntimeError('Native collection child failed; inspect preserved logs')
            save();time.sleep(2)
        assert all(c.returncode==0 for c in children)
        chunks=[];bases=[]
        for k in range(3):
            with np.load(OUT/f'PART_{k}/PARTIAL_J85.npz') as z:chunks.append({q:z[q].copy() for q in z.files})
            with np.load(OUT/f'PART_{k}/BASELINE.npz') as z:bases.append({q:z[q].copy() for q in z.files})
        assert sorted(np.concatenate([q['columns'] for q in chunks]).tolist())==list(range(85))
        combined={key:np.full_like(chunks[0][key],np.nan) for key in chunks[0] if key.startswith('J_')}
        for k,(chunk,baseline) in enumerate(zip(chunks,bases)):
            for key,value in bases[0].items():
                if value.dtype.kind in 'fiu':assert np.max(abs(value-baseline[key]))<1e-8
            assert str(chunk['source_sha256'])==p['source_sha256']
            for key in combined:combined[key][:,chunk['columns']]=chunk[key][:,chunk['columns']]
        assert all(np.isfinite(v).all() for v in combined.values())
        np.savez(OUT/'FRESH_CURRENT_POLICY_J85.npz',**combined,**{'baseline_'+key:bases[0][key] for key in ('residual','physical','optical','phase_curvature_residual','dense_WFE','dense_Airy')},
                 T=bases[0]['T'],color0=bases[0]['color'],source_sha256=p['source_sha256'])
        state['all85_current_source_columns_complete']=True;save();optimize(state,save)
    except BaseException:
        state.update(status='R943_design_failure_preserved',error=traceback.format_exc());save()
        for child in children:
            if child.poll() is None:child.terminate()
        raise
    finally:
        state['active']=False;save()
        session=read(CHAT/'progress.json')
        for route in session['routes']:
            if route.get('pid')==os.getpid() and route.get('process_creation_identity')==state['process_creation_identity']:
                route.update(active=False,status=state['status'])
        write(CHAT/'progress.json',session)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','run','part']);parser.add_argument('--part',type=int)
    args=parser.parse_args()
    if args.mode=='prepare':prepare()
    elif args.mode=='run':run()
    else:assert args.part in (0,1,2);part(args.part)
