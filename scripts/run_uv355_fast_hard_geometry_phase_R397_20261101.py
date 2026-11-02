"""Fresh phase/physical SQP, with actual solid geometry required at every step."""
import argparse,datetime,math,os,shutil,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.environ['UV355_FORMAL_POLICY_FILE']=str(ROOT/'results/uv355_height_lt15_policy_20261018/formal_policy.json')
import numpy as np
from atomic_progress import read_json_retry as read,write_json_atomic as write
from run_uv355_multistart_campaign import sha
from optimize_until_stable import mf_signature
from uv355_hard_geometry_phase_QP_R396_20261101 import projection,propose
from uv355_extended_thickness_audit_R351_20261031 import install
install()
from physical_prescription_audit import audit as physical_audit,parse_model
from formal_optical_policy import limits as formal_limits,air_cap
from compiled_batch_bridge import trace_bridge
from chromatic_control import pupil
from field_continuation_policy_20261012 import invariants
from zos_probe import INSTALL
OUT=ROOT/'results/uv355_fast_hard_geometry_phase_R397_20261101'
CHAT=ROOT/'results/uv355_chat_continuation_R4_20261025'


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def prepare():
    from run_uv355_fourmm_derivatives_recovery_R126_20261028 import dependencies
    assert not OUT.exists()
    base=read(ROOT/'results/uv355_extended_private_derivatives_R355_20261031/preparation.json')
    source=Path(base['source_model']);assert sha(source)==base['source_sha256']
    OUT.mkdir();folder=OUT/'ISOLATED_SOURCE';folder.mkdir();model=folder/'SOURCE.zmx'
    shutil.copy2(source,model);shutil.copy2(source.with_suffix('.MF'),model.with_suffix('.MF'))
    raw=ROOT/'results/uv355_wavefront_multistart_20261007_103318/HEIGHT15_EXTENDED_PRIVATE_DERIVATIVES_R355_20261031/ACTUAL_REDUCED_GUARD_JACOBIAN_001.npz'
    proof=ROOT/'results/uv355_extended_private_derivatives_R355_20261031/INDEPENDENT_EXTENDED_PRIVATE_FULL85_VERIFICATION_R357.json'
    pv=read(proof);assert pv['source_sha256']==sha(model)
    assert all(sha(p['path'])==p['sha256'] for p in pv['artifacts'])
    # Only source coordinates, scales and the source phase baseline are read.
    # No cached Jacobian is used by this method.
    with np.load(raw) as z:np.savez(OUT/'SOURCE_COORDINATES_AND_PHASE_ONLY.npz',initial=z['initial'],scales=z['scales'],variables=z['variables'],phase=z['phase'][:840])
    paths=dependencies([Path(__file__)])
    paths.update([model,model.with_suffix('.MF'),OUT/'SOURCE_COORDINATES_AND_PHASE_ONLY.npz',Path(base['source_review']),proof,Path(base['authorized_estimated_thickness_policy']),ROOT/'scripts/CircularBatchTraceBridge.dll',ROOT/'results/uv355_new_design_20260911/447_same_mf_magnification_independent_audit/independent_audit.json'])
    prep=dict(status='fresh_phase_hard_geometry_private_search_prepared',source_model=str(model),source_sha256=sha(model),source_MF_sha256=sha(model.with_suffix('.MF')),source_review=base['source_review'],
        source_phase_coordinate_proof=str(proof),original85_and_full8794_MF_retained=True,
        no_old_pose_Jacobian_reused=True,all85_columns_fresh_at_every_accepted_pose=True,
        maximum_iterations=6,native_instance_cap=1,optimizer_cap=3,total_SDK_cap=4,automatic_adoption=False,qualified=False,
        geometry_uses_formal_work_strictly_above4mm_not_extra4p02_research_buffer=True,
        final_full129_513_and_both_native_MTF_scopes_and_all35_required=True,
        pinned_files=[dict(path=str(p),sha256=sha(p))for p in sorted(paths)])
    write(OUT/'preparation.json',prep);print(dict(status=prep['status'],pins=len(paths)),flush=True)


def run():
    from inspect_uv355_host_processes_20261020 import inventory
    from uv355_verification_priority import process_identity
    from uv355_optimizer_capacity import optimizer_slot
    assert not (OUT/'trial_progress.json').exists()
    prep=read(OUT/'preparation.json');assert all(sha(p['path'])==p['sha256']for p in prep['pinned_files'])
    host=inventory();assert host['query_success'] and not any(p['name'].lower()=='opticstudio.exe'for p in host['processes'])
    hp,sp=CHAT/'CONTINUOUS_ACTIVE_HANDOFF_20261022.json',CHAT/'progress.json'
    handoff,session=read(hp),read(sp);assert not session.get('user_task_paused') and not handoff.get('current_finite_trial',{}).get('active')
    state=dict(status='connecting_fresh_phase_geometry_native_search',pid=os.getpid(),process_creation_identity=process_identity(os.getpid()),iterations=[],evaluations=0,qualified=False,full_4mm_design_accepted=False,FFT_checks_run=False)
    def save():state['utc']=now();write(OUT/'trial_progress.json',state)
    def active():assert not read(sp).get('user_task_paused') and not (OUT/'STOP_REQUEST').exists()
    handoff['current_finite_trial']=dict(root=str(OUT),pid=os.getpid(),process_creation_identity=state['process_creation_identity'],progress=str(OUT/'trial_progress.json'),active=True,kind='fresh_phase_hard_geometry_R397',automatic_adoption=False,qualified=False)
    handoff.update(active=True,status=state['status'],updated_utc=now());write(hp,handoff)
    session.update(active=True,status=state['status'],current_method_root=str(OUT),updated_utc=now());write(sp,session);save()
    from pythonnet import load
    load('netfx');import clr
    clr.AddReference(str(INSTALL/'ZOSAPI_NetHelper.dll'));import ZOSAPI_NetHelper
    assert ZOSAPI_NetHelper.ZOSAPI_Initializer.Initialize(str(INSTALL))
    clr.AddReference(str(INSTALL/'ZOSAPI_Interfaces.dll'));clr.AddReference(str(INSTALL/'ZOSAPI.dll'));import ZOSAPI
    clr.AddReference(str(ROOT/'scripts/CircularBatchTraceBridge.dll'));from ObjectiveLensCircularBridge import CircularBatchTraceBridge as bridge
    source=Path(prep['source_model']);signature=mf_signature(source.with_suffix('.MF'));assert len(signature)==8794
    pr=[(i,r)for i,r in enumerate(signature,1)if r[0]=='OPDX'];assert len(pr)==840
    with np.load(OUT/'SOURCE_COORDINATES_AND_PHASE_ONLY.npz') as z:
        initial=z['initial'].copy();scales=z['scales'].copy();variables=z['variables'].tolist();original_phase=z['phase'].copy()
    transform=projection(signature);fields=np.linspace(0.,1.,33);mesh=pupil(8,16);weights=np.array([r[2]for r in mesh]);weights/=weights.sum()
    uniform=[(0.,0.)]+[(r*math.cos(k*2*math.pi/64),r*math.sin(k*2*math.pi/64))for r in np.linspace(1/32,1.,32)for k in range(64)]
    focus_requests=[(w,0.,float(f),px,py)for w in (1,2,3)for f in fields for px,py in [(0.,0.),*[(x,y)for x,y,wt in mesh]]]
    chiefs=[(w,0.,float(f),0.,0.)for w in (1,2,3)for f in fields]
    fronts=[(w,0.,float(f),px,py)for w in (1,2,3)for f in fields for px,py in uniform]
    sine_requests=[(w,0.,0.,px,py)for w in (1,2,3)for px,py in uniform]
    app=None
    try:
        with optimizer_slot():
            active();app=ZOSAPI.ZOSAPI_Connection().CreateNewApplication();assert app and app.IsValidLicenseForAPI
            system=app.PrimarySystem;system.LoadFile(str(source),False);system.MFE.CalculateMeritFunction()
            actual_variables=[(sn,c)for sn in range(system.LDE.NumberOfSurfaces-1)for c in range(2,20)if system.LDE.GetSurfaceAt(sn).GetCellAt(c).Solve==ZOSAPI.Editors.SolveType.Variable]
            assert actual_variables==[tuple(v)for v in variables] and len(variables)==85
            assert np.max(abs(np.array([float(system.MFE.GetOperandAt(i).Value)for i,r in pr])-original_phase))<1e-8
            lines=source.with_suffix('.MF').read_text(encoding='utf-16').splitlines();compact=[lines[0],*lines[1:12]]
            compact.extend('OPDX '+' '.join(format(v,'.16g')for v in r[1:9])+f' 0 {r[-1]:.16g} 0'for i,r in pr)
            template=OUT/'PHASE_EVALUATION_ONLY.MF';template.write_text('\n'.join(compact)+'\n',encoding='utf-16');assert len(mf_signature(template))==851
            system.MFE.LoadMeritFunction(str(template));system.MFE.CalculateMeritFunction()
            assert np.max(abs(np.array([float(system.MFE.GetOperandAt(i).Value)for i in range(12,852)])-original_phase))<1e-8
            def apply(x):
                for (sn,c),value in zip(variables,initial+scales*x):system.LDE.GetSurfaceAt(sn).GetCellAt(c).DoubleValue=(1./value if abs(value)>1e-16 else 1e18)if c==2 else float(value)
            def evaluate(x):
                active();tick=time.monotonic();apply(x);system.MFE.CalculateMeritFunction()
                phase=np.asarray([float(system.MFE.GetOperandAt(i).Value)for i in range(12,852)]);efl=float(system.MFE.GetOperandAt(11).Value)
                ray=system.Tools.OpenBatchRayTrace()
                try:
                    images=trace_bridge(bridge,ray,36,focus_requests).reshape(3,33,1+len(mesh),6)
                    front=trace_bridge(bridge,ray,10,fronts).reshape(3,33,len(uniform),6)[...,3:]
                    incoming=trace_bridge(bridge,ray,0,chiefs).reshape(3,33,6)[...,3:]
                    sin0=trace_bridge(bridge,ray,0,sine_requests).reshape(3,len(uniform),6)
                    sin11=trace_bridge(bridge,ray,11,sine_requests).reshape(3,len(uniform),6)
                    para=trace_bridge(bridge,ray,36,[(w,0.,1e-5,0.,0.)for w in (1,2,3)])
                finally:ray.Close()
                probe=OUT/'GEOMETRY_CALLBACK_ONLY.zmx';system.SaveAs(str(probe));physical=physical_audit(probe);surfaces=parse_model(probe)[2]
                if physical['issues']:raise ValueError(physical['issues'])
                gp=[];lp=[]
                def geom(label,value):lp.append(label);gp.append(float(value))
                for l in physical['lenses']:
                    assert l['required_center_mm']is not None and l['required_radial_min_mm']is not None
                    geom(f'S{l["front"]}_center_max',(30.-l['center_mm'])/.02)
                    geom(f'S{l["front"]}_center_min',(l['center_mm']-l['required_center_mm'])/.02)
                    geom(f'S{l["front"]}_radial_min',(l['minimum_mm']-l['required_radial_min_mm'])/.02)
                for g in physical['gaps']:
                    geom(f'gap{g["left_rear"]}_minimum',(g['minimum_mm']-g['required_mm'])/.02)
                    geom(f'gap{g["left_rear"]}_rim',(g['rim_mm']-g['required_mm'])/.02)
                for sn,s in surfaces.items():
                    if sn in (0,11,25,35,36)or s.get('glas'):continue
                    geom(f'air{sn}_minimum',s['thickness']/.02);geom(f'air{sn}_maximum',(air_cap(sn,formal_limits())-s['thickness'])/.02)
                for sn in (10,12):geom(f'long{sn}_minimum',(surfaces[sn]['thickness']-20.)/.02)
                geom('work',(physical['work_clearance_mm']-4.000001)/.02)
                geom('track',(899.999999-physical['track_mm'])/.02)
                geom('contact',(physical['first_two_lens_common_contact_ring']['width_mm']-1.)/.1)
                optical=[];lo=[]
                def opt(label,value):lo.append(label);optical.append(float(value))
                opt('EFL_lower',(efl-49.9)/.1);opt('EFL_upper',(50.1-efl)/.1)
                front_chief=front[:,:,0,None,:]
                divergence=np.arctan2(np.linalg.norm(np.cross(front,front_chief),axis=-1),np.sum(front*front_chief,axis=-1))*1000.
                object_angle=np.degrees(np.arctan2(np.linalg.norm(incoming[...,:2],axis=-1),incoming[...,2]))
                image_angle=np.degrees(np.arctan2(np.linalg.norm(images[:,:,0,3:5],axis=-1),images[:,:,0,5]))
                heights=images[:,:,0,1]+20.*fields[None,:]
                depth=[]
                for wi,w in enumerate((1,2,3)):
                    pos=images[wi,:,1:,:2];slope=images[wi,:,1:,3:5]/images[wi,:,1:,5,None]
                    pc=pos-np.einsum('n,fnc->fc',weights,pos)[:,None,:];sc=slope-np.einsum('n,fnc->fc',weights,slope)[:,None,:]
                    focus=-np.einsum('n,fnc,fnc->fc',weights,pc,sc)/np.einsum('n,fnc,fnc->fc',weights,sc,sc)
                    shifts=(focus-float(focus[0].mean()))*1000./(para[wi,1]/.00002)**2;depth.extend(shifts.ravel())
                    for fi in range(33):
                        opt(f'front_{w}_{fi}',1.-float(divergence[wi,fi].max()))
                        opt(f'object_{w}_{fi}',1.-object_angle[wi,fi]/.02)
                        opt(f'image_{w}_{fi}',1.-image_angle[wi,fi]/.08)
                        opt(f'heightP_{w}_{fi}',(.014999999-heights[wi,fi])/.01)
                        opt(f'heightN_{w}_{fi}',(.014999999+heights[wi,fi])/.01)
                sine=float(np.max(np.linalg.norm(sin11[...,:2]-30.71792153*sin0[...,3:5],axis=-1)))
                opt('sine',(.05-sine)/.05)
                for i,z in enumerate(depth):opt(f'depth_{i}',1.-abs(z)/.493)
                result=dict(x=x.copy(),phase=phase,residual=transform@phase,physical=np.asarray(gp),physical_labels=lp,optical=np.asarray(optical),optical_labels=lo,
                    physical_pass=bool(physical['passed']),physical_report=physical,
                    geometry_minimum=float(min(gp)),optical_minimum=float(min(optical)),maximum_height_error_um=float(np.max(abs(heights)))*1000.,front_mrad=float(divergence.max()),object_chief_deg=float(object_angle.max()),image_chief_deg=float(image_angle.max()),maximum_ST_object_um=float(max(abs(np.asarray(depth)))),seconds=time.monotonic()-tick)
                assert all(np.isfinite(result[k]).all()for k in ('phase','residual','physical','optical'))
                state['evaluations']+=1;state['latest_evaluation']={k:result[k]for k in ('physical_pass','geometry_minimum','optical_minimum','maximum_height_error_um','front_mrad','object_chief_deg','image_chief_deg','maximum_ST_object_um','seconds')};save()
                return result
            pose=np.zeros(85);a=variables.index([3,3]);b=variables.index([35,3]);delta=max(0.,3.31-initial[a]);pose[a]=delta/scales[a];pose[b]=(-delta-.02)/scales[b]
            base=evaluate(pose);assert base['physical_pass'] and base['geometry_minimum']>=-1e-8,'Repair seed must have actual feasible solids'
            state['seed_geometry_pass']=True;state['source_phase_baseline_verified']=True;state['no_old_pose_derivatives_used']=True;save()
            for iteration in range(prep['maximum_iterations']):
                active();state.update(status='collecting_fresh_phase_and_hard_geometry_columns',active_iteration=iteration+1,completed_columns=[]);save()
                jp=np.zeros((840,85));jg=np.zeros((len(base['physical']),85));jo=np.zeros((len(base['optical']),85));h=1e-4
                for col in range(85):
                    d=np.zeros(85);d[col]=h
                    minus=evaluate(pose-d);plus=evaluate(pose+d)
                    assert minus['physical_labels']==plus['physical_labels']==base['physical_labels'] and minus['optical_labels']==plus['optical_labels']==base['optical_labels']
                    jp[:,col]=(plus['residual']-minus['residual'])/(2*h)
                    jg[:,col]=(plus['physical']-minus['physical'])/(2*h);jo[:,col]=(plus['optical']-minus['optical'])/(2*h)
                    state['completed_columns'].append(col);save()
                restored=evaluate(pose);assert np.max(abs(restored['phase']-base['phase']))<1e-8
                np.savez(OUT/f'FRESH_PHASE_PHYSICAL_MODEL_{iteration+1:02d}.npz',pose=pose,phase=base['phase'],residual=base['residual'],Jresidual=jp,physical=base['physical'],Jphysical=jg,optical=base['optical'],Joptical=jo,initial=initial,scales=scales,variables=variables)
                oldcost=float(np.mean(base['residual']**2)+10.*np.mean(np.minimum(base['optical'],0.)**2));accepted=None;trials=[]
                for radius in (1.,.5,.25,.125):
                    try:step,proof=propose(base['residual'],jp,base['physical'],jg,base['optical'],jo,radius)
                    except AssertionError as error:trials.append(dict(radius=radius,model_rejected=str(error)));continue
                    for fraction in (1.,.5,.25,.125,.0625,.03125):
                        candidate=pose+fraction*step
                        try:trial=evaluate(candidate)
                        except Exception as error:trials.append(dict(radius=radius,fraction=fraction,failed_native_evaluation=repr(error)));continue
                        cost=float(np.mean(trial['residual']**2)+10.*np.mean(np.minimum(trial['optical'],0.)**2))
                        passed=np.flatnonzero(base['optical']>=0.)
                        safe=trial['physical_pass'] and trial['geometry_minimum']>=-1e-8 and np.min(trial['optical'][passed])>=-1e-8
                        row=dict(radius=radius,fraction=fraction,cost=cost,physical_pass=trial['physical_pass'],safe=bool(safe),phase_RMS=float(np.sqrt(np.mean(trial['residual']**2)))*.02)
                        trials.append(row);state['latest_trial']=row;save()
                        if safe and cost<oldcost-1e-7:accepted=(candidate,trial,proof);break
                    if accepted is not None:break
                record=dict(iteration=iteration+1,trials=trials,accepted=accepted is not None);state['iterations'].append(record);save()
                if accepted is None:break
                pose,base,proof=accepted;apply(pose);system.MFE.LoadMeritFunction(str(source.with_suffix('.MF')))
                model=OUT/f'UNQUALIFIED_PHYSICAL_PHASE_STEP_{iteration+1:02d}.zmx';system.SaveAs(str(model));system.MFE.SaveMeritFunction(str(model.with_suffix('.MF')))
                assert mf_signature(model.with_suffix('.MF'))==signature and invariants(model)['static_invariants_pass']
                assert [(sn,c)for sn in range(system.LDE.NumberOfSurfaces-1)for c in range(2,20)if system.LDE.GetSurfaceAt(sn).GetCellAt(c).Solve==ZOSAPI.Editors.SolveType.Variable]==[tuple(v)for v in variables]
                dense=physical_audit(model,16385);assert dense['passed'],'Do not retain a nonphysical candidate'
                write(OUT/f'PHYSICAL_{iteration+1:02d}.json',dense);np.savez(model.with_suffix('.npz'),coordinates=pose,initial=initial,scales=scales,variables=variables)
                record.update(model=str(model),sha256=sha(model),proof=proof,phase_RMS=float(np.sqrt(np.mean(base['residual']**2)))*.02,full_native_reviews_required=True,qualified=False);save()
                system.MFE.LoadMeritFunction(str(template));system.MFE.CalculateMeritFunction()
                print(dict(iteration=iteration+1,phase_RMS=record['phase_RMS'],physical_pass=True,qualified=False),flush=True)
            state.update(status='fresh_hard_geometry_phase_search_complete_full_native_reviews_required')
    except BaseException:
        state.update(status='hard_geometry_phase_search_failure_preserved',error=traceback.format_exc());raise
    finally:
        if app is not None:app.CloseApplication()
        assert sha(source)==prep['source_sha256'] and sha(source.with_suffix('.MF'))==prep['source_MF_sha256']
        save();handoff=read(hp)
        if handoff.get('current_finite_trial',{}).get('pid')==os.getpid():
            done=handoff.pop('current_finite_trial');done.update(active=False,status=state['status']);handoff['completed_or_interrupted_phase_geometry_R397']=done;handoff.update(active=False,status=state['status'],updated_utc=now());write(hp,handoff)
        session=read(sp)
        if not session.get('user_task_paused'):session.update(active=False,status=state['status'],updated_utc=now());write(sp,session)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run']);{'prepare':prepare,'run':run}[p.parse_args().mode]()
