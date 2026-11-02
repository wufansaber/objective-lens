"""Fresh original85 native WFE/spot/ordering SQP with hard physical geometry."""
import argparse,ast,datetime,math,os,shutil,time,traceback
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
import run_uv355_fast_hard_geometry_phase_R397_20261101 as geom
from uv355_direct_native_objective_QP_R405_20261101 import augment_native,cost,propose
from atomic_progress import read_json_retry as read,write_json_atomic as write
from run_uv355_multistart_campaign import sha
from uv355_verification_priority import process_identity
ROOT=geom.ROOT;CHAT=geom.CHAT;OUT=ROOT/'results/uv355_direct_native_hard_geometry_R406_20261101'
PREFLIGHT=ROOT/'results/uv355_direct_native_hard_geometry_preflight_R411_20261101'
REVIEW=ROOT/'results/uv355_hard_geometry_phase_candidates_review_R399_20261101'

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def make_application():
    from pythonnet import load
    load('netfx');import clr
    clr.AddReference(str(geom.INSTALL/'ZOSAPI_NetHelper.dll'));import ZOSAPI_NetHelper
    assert ZOSAPI_NetHelper.ZOSAPI_Initializer.Initialize(str(geom.INSTALL))
    clr.AddReference(str(geom.INSTALL/'ZOSAPI_Interfaces.dll'));clr.AddReference(str(geom.INSTALL/'ZOSAPI.dll'));import ZOSAPI
    clr.AddReference(str(ROOT/'scripts/CircularBatchTraceBridge.dll'));from ObjectiveLensCircularBridge import CircularBatchTraceBridge as bridge
    app=ZOSAPI.ZOSAPI_Connection().CreateNewApplication();assert app and app.IsValidLicenseForAPI
    return app,ZOSAPI,bridge

def context(system,ZOSAPI,bridge,source,out,state,save,active):
    system.LoadFile(str(source),False);system.MFE.CalculateMeritFunction();signature=geom.mf_signature(source.with_suffix('.MF'));assert len(signature)==8794
    variables=[(sn,c)for sn in range(system.LDE.NumberOfSurfaces-1)for c in range(2,20)if system.LDE.GetSurfaceAt(sn).GetCellAt(c).Solve==ZOSAPI.Editors.SolveType.Variable];assert len(variables)==85
    with np.load(geom.OUT/'SOURCE_COORDINATES_AND_PHASE_ONLY.npz')as z:
        scales=z['scales'].copy();assert variables==[tuple(v)for v in z['variables'].tolist()]
    initial=np.asarray([1./system.LDE.GetSurfaceAt(sn).GetCellAt(c).DoubleValue if c==2 else system.LDE.GetSurfaceAt(sn).GetCellAt(c).DoubleValue for sn,c in variables])
    assert np.isfinite(initial).all()
    phase_rows=[(i,r)for i,r in enumerate(signature,1)if r[0]=='OPDX'];assert len(phase_rows)==840
    original_phase=np.asarray([float(system.MFE.GetOperandAt(i).Value)for i,r in phase_rows])
    lines=source.with_suffix('.MF').read_text(encoding='utf-16').splitlines();compact=[lines[0],*lines[1:12]]
    compact.extend('OPDX '+' '.join(format(v,'.16g')for v in r[1:9])+f' 0 {r[-1]:.16g} 0'for i,r in phase_rows)
    template=out/'NATIVE_CALLBACK_ONLY.MF';template.write_text('\n'.join(compact)+'\n',encoding='utf-16');system.MFE.LoadMeritFunction(str(template));system.MFE.CalculateMeritFunction()
    assert np.max(abs(np.asarray([float(system.MFE.GetOperandAt(i).Value)for i in range(12,852)])-original_phase))<1e-8
    transform=geom.projection(signature);fields=np.linspace(0.,1.,33);mesh=geom.pupil(8,16);weights=np.asarray([p[2]for p in mesh]);weights/=weights.sum()
    uniform=[(0.,0.)]+[(r*math.cos(k*2*math.pi/64),r*math.sin(k*2*math.pi/64))for r in np.linspace(1/32,1.,32)for k in range(64)]
    focus_requests=[(w,0.,float(f),px,py)for w in (1,2,3)for f in fields for px,py in [(0.,0.),*[(x,y)for x,y,wt in mesh]]]
    chiefs=[(w,0.,float(f),0.,0.)for w in (1,2,3)for f in fields]
    fronts=[(w,0.,float(f),px,py)for w in (1,2,3)for f in fields for px,py in uniform]
    sine_requests=[(w,0.,0.,px,py)for w in (1,2,3)for px,py in uniform]
    def apply(x):
        for (sn,c),v in zip(variables,initial+scales*x):system.LDE.GetSurfaceAt(sn).GetCellAt(c).DoubleValue=(1./v if abs(v)>1e-16 else 1e18)if c==2 else float(v)
    ns=dict(vars(geom));ns.update(locals());ns['OUT']=out
    tree=ast.parse(Path(geom.__file__).read_text(encoding='utf-8-sig'));node=next(n for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)and n.name=='evaluate')
    exec(compile(ast.Module(body=[node],type_ignores=[]),geom.__file__,'exec'),ns)
    geometry_callback=ns['evaluate'];op=ZOSAPI.Editors.MFE.MeritOperandType
    def evaluate(x):
        tick=time.monotonic();result=augment_native(geometry_callback(x),system,op,bridge,uniform)
        result['total_seconds']=time.monotonic()-tick
        state['latest_direct_native']={k:result[k]for k in('direct_native_WFE_peak','direct_native_axis_WFE','direct_native_Airy_peak','direct_native_seconds','total_seconds')}
        state['latest_cost']=cost(result);save();return result
    return evaluate,apply,initial,scales,variables,template,signature

def preflight():
    from verification_capacity import verification_slot
    from inspect_uv355_host_processes_20261020 import inventory
    assert not PREFLIGHT.exists();PREFLIGHT.mkdir();out=PREFLIGHT
    source=geom.OUT/'UNQUALIFIED_PHYSICAL_PHASE_STEP_03.zmx';hashes={str(p):sha(p)for p in(source,source.with_suffix('.MF'),Path(__file__),ROOT/'scripts/uv355_direct_native_objective_QP_R405_20261101.py',Path(geom.__file__))}
    state=dict(status='direct_native_geometry_callback_preflight',pid=os.getpid(),process_creation_identity=process_identity(os.getpid()),active=True,read_only=True,evaluations=0,qualified=False,source=str(source),source_sha256=sha(source),derivative_checks=[])
    sp=CHAT/'progress.json';session=read(sp);assert not session.get('user_task_paused');session['routes'].append(dict(state,root=str(out),progress=str(out/'progress.json')));write(sp,session)
    def save():write(out/'progress.json',state)
    def active():assert not read(sp).get('user_task_paused')
    app=None;save()
    try:
        with verification_slot():
            host=inventory();assert host['query_success']and sum(p['name'].lower()=='opticstudio.exe'for p in host['processes'])<=3
            app,ZOSAPI,bridge=make_application();evaluate,apply,initial,scales,variables,template,signature=context(app.PrimarySystem,ZOSAPI,bridge,source,out,state,save,active)
            x=np.zeros(85);base=evaluate(x);repeat=evaluate(x)
            assert base['physical_pass']and min(base['physical'])>=-1e-8
            repeat_error=max(float(np.max(abs(base[k]-repeat[k])))for k in('residual','optical','physical','phase'));assert repeat_error<1e-8
            np.savez(out/'BASELINE.npz',initial=initial,scales=scales,variables=variables,residual=base['residual'],optical=base['optical'],physical=base['physical'],phase=base['phase'],native_WFE=base['native_WFE'],native_Airy=base['native_Airy'])
            check_columns=(variables.index((3,3)),0,42);assert len(set(check_columns))==3
            for col in check_columns:
                derivatives=[]
                for h in (1e-4,5e-5):
                    delta=np.zeros(85);delta[col]=h;minus=evaluate(x-delta);plus=evaluate(x+delta)
                    derivatives.append({k:(plus[k]-minus[k])/(2*h)for k in('residual','optical','physical','phase')})
                errors={k:float(np.max(abs(derivatives[0][k]-derivatives[1][k])))/max(1.,float(np.max(abs(derivatives[1][k]))))for k in derivatives[0]}
                assert max(errors.values())<.03,errors
                state['derivative_checks'].append(dict(column=col,variable=variables[col],maximum_relative_scaled_derivative_errors=errors));save()
            restored=evaluate(x);assert np.max(abs(restored['phase']-base['phase']))<1e-8
            state.update(status='direct_native_geometry_callback_and_three_centered_columns_verified',direct_native_point_count=len(base['native_points']),physical_guard_count=len(base['physical']),optical_guard_count=len(base['optical']),repeat_maximum_error=repeat_error,all_original85_flags_verified=True,source8794_MF_and840_OPDX_unchanged=True,signed_phase_not_objective=True,source_and_MF_unchanged=True,pinned_preflight_files=[dict(path=p,sha256=h)for p,h in hashes.items()])
            print({k:state[k]for k in('status','direct_native_point_count','physical_guard_count','optical_guard_count','derivative_checks')},flush=True)
    finally:
        if app is not None:app.CloseApplication()
        assert all(sha(p)==h for p,h in hashes.items());state['active']=False;save();session=read(sp)
        for r in session['routes']:
            if r.get('pid')==os.getpid()and r.get('process_creation_identity')==state['process_creation_identity']:r.update(active=False,status=state['status'])
        write(sp,session)

def prepare():
    from run_uv355_fourmm_derivatives_recovery_R126_20261028 import dependencies
    assert not OUT.exists();proof=read(PREFLIGHT/'progress.json');assert proof['status']=='direct_native_geometry_callback_and_three_centered_columns_verified'
    assert len({r['column']for r in proof['derivative_checks']})==3 and all(sha(p['path'])==p['sha256']for p in proof['pinned_preflight_files'])
    completed=read(REVIEW/'trial_progress.json');assert completed['status']=='all_saved_native_DLS_candidates_fully_reviewed_requires_assessment'
    candidates=completed['reviews'];assert candidates
    def score(c):
        s=c['summary'];return sum(max(0.,s[k]/limit-1.)**2 for k,limit in [('wfe_worst_waves',.05),('axis_wfe_worst_waves',.04),('rms_over_airy_worst',1.),('front_divergence_mrad',1.),('max_individual_focus_shift_object_um',.493)])
    selected=min(candidates,key=score);original=Path(selected['model']);assert sha(original)==selected['sha256']
    dense=geom.physical_audit(original,16385);assert dense['passed']
    OUT.mkdir();folder=OUT/'ISOLATED_SOURCE';folder.mkdir();source=folder/'SOURCE.zmx';shutil.copy2(original,source);shutil.copy2(original.with_suffix('.MF'),source.with_suffix('.MF'))
    paths=dependencies([Path(__file__)]);paths.update([Path(geom.__file__),source,source.with_suffix('.MF'),Path(selected['review']),REVIEW/'trial_progress.json',PREFLIGHT/'progress.json',PREFLIGHT/'BASELINE.npz',geom.OUT/'SOURCE_COORDINATES_AND_PHASE_ONLY.npz',ROOT/'scripts/CircularBatchTraceBridge.dll',ROOT/'results/uv355_authorized_extended_thickness_R350_20261031/AUTHORIZED_DERIVED_THICKNESS_POLICY.json',ROOT/'results/uv355_height_lt15_policy_20261018/formal_policy.json'])
    write(OUT/'preparation.json',dict(status='direct_native_hard_geometry_search_prepared',source_model=str(source),source_sha256=sha(source),source_MF_sha256=sha(source.with_suffix('.MF')),source_review=selected['review'],selected_source=selected['model'],selection_score=score(selected),maximum_iterations=4,native_instance_cap=1,total_SDK_cap=4,optimizer_cap=3,no_old_Jacobian_reused=True,all85_columns_fresh_at_every_accepted_pose=True,original8794_and_all85_retained=True,signed_phase_target_used=False,source_is_unqualified=True,automatic_adoption=False,qualified=False,pinned_files=[dict(path=str(p),sha256=sha(p))for p in sorted(paths)]))
    write(OUT/'SOURCE_DENSE_PHYSICAL.json',dense);print(dict(status='prepared',source=selected['model'],score=score(selected),pins=len(paths)),flush=True)

def run():
    from uv355_optimizer_capacity import optimizer_slot
    from inspect_uv355_host_processes_20261020 import inventory
    assert not(OUT/'trial_progress.json').exists();prep=read(OUT/'preparation.json');assert all(sha(p['path'])==p['sha256']for p in prep['pinned_files'])
    hp,sp=CHAT/'CONTINUOUS_ACTIVE_HANDOFF_20261022.json',CHAT/'progress.json';h,session=read(hp),read(sp);assert not session.get('user_task_paused')and not h.get('current_finite_trial',{}).get('active')
    host=inventory();assert host['query_success']and not any(p['name'].lower()=='opticstudio.exe'for p in host['processes'])
    state=dict(status='fresh_direct_native_geometry_search',pid=os.getpid(),process_creation_identity=process_identity(os.getpid()),iterations=[],evaluations=0,qualified=False,full_4mm_design_accepted=False,FFT_checks_run=False)
    def save():state['utc']=now();write(OUT/'trial_progress.json',state)
    def active():assert not read(sp).get('user_task_paused')and not(OUT/'STOP_REQUEST').exists()
    h['current_finite_trial']=dict(root=str(OUT),pid=os.getpid(),process_creation_identity=state['process_creation_identity'],progress=str(OUT/'trial_progress.json'),active=True,kind='direct_native_hard_geometry_R406',automatic_adoption=False,qualified=False);h.update(active=True,status=state['status'],updated_utc=now());write(hp,h)
    session.update(active=True,status=state['status'],current_method_root=str(OUT),updated_utc=now());write(sp,session);save();app=None;source=Path(prep['source_model'])
    try:
        with optimizer_slot():
            active();app,ZOSAPI,bridge=make_application();system=app.PrimarySystem
            evaluate,apply,initial,scales,variables,template,signature=context(system,ZOSAPI,bridge,source,OUT,state,save,active)
            pose=np.zeros(85);base=evaluate(pose);assert base['physical_pass']and min(base['physical'])>=-1e-8
            state['source_native_verified']=True;save()
            for iteration in range(prep['maximum_iterations']):
                state.update(status='collecting_fresh_direct_native_original85_columns',active_iteration=iteration+1,completed_columns=[]);save()
                jr=np.zeros((len(base['residual']),85));jg=np.zeros((len(base['physical']),85));jo=np.zeros((len(base['optical']),85));jc=np.zeros((840,85));step_size=1e-4
                for col in range(85):
                    delta=np.zeros(85);delta[col]=step_size;minus=evaluate(pose-delta);plus=evaluate(pose+delta)
                    assert minus['optical_labels']==plus['optical_labels']==base['optical_labels']and minus['physical_labels']==plus['physical_labels']==base['physical_labels']
                    for target,key in((jr,'residual'),(jg,'physical'),(jo,'optical'),(jc,'phase_curvature_residual')):target[:,col]=(plus[key]-minus[key])/(2*step_size)
                    state['completed_columns'].append(col);save()
                restored=evaluate(pose);assert max(np.max(abs(restored[k]-base[k]))for k in('residual','phase','physical','optical'))<1e-8
                np.savez(OUT/f'FRESH_NATIVE_LOCAL_MODEL_{iteration+1:02d}.npz',pose=pose,initial=initial,scales=scales,variables=variables,residual=base['residual'],Jresidual=jr,physical=base['physical'],Jphysical=jg,optical=base['optical'],Joptical=jo,Jphase_curvature=jc,native_WFE=base['native_WFE'],native_Airy=base['native_Airy'])
                oldcost=cost(base);trials=[];accepted=None
                for radius in(1.,.5,.25,.125,.0625):
                    try:step,proof=propose(base['residual'],jr,base['physical'],jg,base['optical'],jo,base['optical_labels'],jc,radius)
                    except AssertionError as error:trials.append(dict(radius=radius,model_rejected=str(error)));continue
                    for fraction in(1.,.5,.25,.125,.0625,.03125):
                        candidate=pose+fraction*step
                        try:trial=evaluate(candidate)
                        except Exception as error:trials.append(dict(radius=radius,fraction=fraction,failed_native_evaluation=repr(error)));continue
                        safe=trial['physical_pass']and min(trial['physical'])>=-1e-8 and min(trial['optical'][base['optical']>=0.])>=-1e-8
                        row=dict(radius=radius,fraction=fraction,cost=cost(trial),safe=bool(safe),WFE=trial['direct_native_WFE_peak'],axis_WFE=trial['direct_native_axis_WFE'],Airy=trial['direct_native_Airy_peak'],physical_pass=trial['physical_pass']);trials.append(row);state['latest_trial']=row;save()
                        if safe and row['cost']<oldcost-1e-7:accepted=candidate,trial,proof;break
                    if accepted is not None:break
                record=dict(iteration=iteration+1,trials=trials,accepted=accepted is not None);state['iterations'].append(record);save()
                if accepted is None:break
                pose,base,proof=accepted;apply(pose);system.MFE.LoadMeritFunction(str(source.with_suffix('.MF')));model=OUT/f'UNQUALIFIED_DIRECT_NATIVE_STEP_{iteration+1:02d}.zmx';system.SaveAs(str(model));system.MFE.SaveMeritFunction(str(model.with_suffix('.MF')))
                assert geom.mf_signature(model.with_suffix('.MF'))==signature and geom.invariants(model)['static_invariants_pass']
                assert variables==[(sn,c)for sn in range(system.LDE.NumberOfSurfaces-1)for c in range(2,20)if system.LDE.GetSurfaceAt(sn).GetCellAt(c).Solve==ZOSAPI.Editors.SolveType.Variable]
                dense=geom.physical_audit(model,16385);assert dense['passed'];write(OUT/f'PHYSICAL_{iteration+1:02d}.json',dense);np.savez(model.with_suffix('.npz'),coordinates=pose,initial=initial,scales=scales,variables=variables)
                record.update(model=str(model),sha256=sha(model),proof=proof,cost=cost(base),WFE=base['direct_native_WFE_peak'],axis_WFE=base['direct_native_axis_WFE'],Airy=base['direct_native_Airy_peak'],full_native_reviews_required=True,qualified=False);save();print({k:record[k]for k in('iteration','cost','WFE','axis_WFE','Airy')},flush=True)
                system.MFE.LoadMeritFunction(str(template));system.MFE.CalculateMeritFunction()
            state.update(status='fresh_direct_native_geometry_search_complete_full_reviews_required')
    except BaseException:state.update(status='direct_native_geometry_search_failure_preserved',error=traceback.format_exc());raise
    finally:
        if app is not None:app.CloseApplication()
        assert all(sha(p['path'])==p['sha256']for p in prep['pinned_files']);save();h=read(hp)
        if h.get('current_finite_trial',{}).get('pid')==os.getpid():
            done=h.pop('current_finite_trial');done.update(active=False,status=state['status']);h['completed_or_interrupted_direct_native_R406']=done;h.update(active=False,status=state['status'],updated_utc=now());write(hp,h)
        session=read(sp)
        if not session.get('user_task_paused'):session.update(active=False,status=state['status'],updated_utc=now());write(sp,session)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['preflight','prepare','run']);{'preflight':preflight,'prepare':prepare,'run':run}[p.parse_args().mode]()
