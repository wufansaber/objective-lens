"""Fresh-source squared-RMS native85 model followed by validated finite corrections.

J85 is freshly measured at the source hash in preparation.json. Local Jacobians at finite poses are only
approximations, calibrated with native directions at that pose, never relabelled
as a newly measured full85 Jacobian. Every retained prescription needs full review.
"""
from datetime import datetime,timezone
import os
from pathlib import Path
import traceback
import io
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from atomic_progress import read_json_retry as read,write_json_atomic as write
from run_uv355_multistart_campaign import sha
from optimize_until_stable import mf_signature
from uv355_verification_priority import process_identity
from uv355_optimizer_capacity import optimizer_slot
import run_uv355_phase_bounded_design_R950_20261102 as variant
from uv355_focal_runtime_R944_20261102 import context,vector,method,policy

# Every optical row is unconditional, including rows already outside a limit.
# Minimize coordinate movement only; all finite-step acceptance uses native data.
SEARCH_DAMPING=1.
def proposal(base,jac,radius,color0=None,jcolor=None):
    import clarabel
    from scipy import sparse
    n=85;g=base['physical'];o=base['optical']
    reserve=np.asarray([.005 if l.startswith(('heightP_','heightN_')) else 1e-5 if l.startswith('front_') else min(1e-6,max(float(v),0.)*.1) for l,v in zip(base['optical_labels'],o)])
    rhs=[np.full(n,radius),np.full(n,radius),g-np.minimum(1e-5,np.maximum(g,0.)*.1),o-reserve]
    blocks=[sparse.eye(n),-sparse.eye(n),-sparse.csc_matrix(jac['physical']),-sparse.csc_matrix(jac['optical'])]
    A=sparse.vstack(blocks,format='csc');b=np.concatenate(rhs)
    cones=[clarabel.NonnegativeConeT(len(b))];phase_bounds=[]
    for indices,factor in variant.GROUPS:
        c=jac['phase_curvature_residual'][indices]*factor
        A=sparse.vstack((A,sparse.vstack((sparse.csc_matrix((1,n)),-sparse.csc_matrix(c)))),format='csc')
        b=np.r_[b,.005*radius,np.zeros(len(c))]
        cones.append(clarabel.SecondOrderConeT(len(c)+1));phase_bounds.append(c)
    settings=clarabel.DefaultSettings();settings.verbose=False;settings.max_threads=1;settings.max_iter=300;settings.time_limit=45.
    settings.tol_gap_abs=settings.tol_gap_rel=settings.tol_feas=1e-10
    sol=clarabel.DefaultSolver(sparse.eye(n,format='csc'),np.zeros(n),A,b,cones,settings).solve()
    x=np.asarray(sol.x);assert str(sol.status) in ('Solved','AlmostSolved'),str(sol.status)
    assert np.isfinite(x).all() and min(b[:sum(map(len,rhs))]-A[:sum(map(len,rhs))]@x)>=-1e-8
    assert all(np.linalg.norm(c@x)<=.005*radius+1e-8 for c in phase_bounds)
    return x,dict(status=str(sol.status),radius=radius,LM_search_damping=SEARCH_DAMPING,all_optical_guards_unconditional=True,optical_guard_count=len(o),physical_guard_count=len(g),image_height_search_margin_um=.05,front_search_margin_mrad=1e-5,formal_WFE_limit=.055,formal_Airy_limit=1.,MTF_constraints=0,MTF_objective_terms=0,objective='minimum_coordinate_movement',step_norm=float(np.linalg.norm(x)))
variant.proposal=proposal
_namespace={'SEARCH_DAMPING':SEARCH_DAMPING}

ROOT=method.ROOT;FD=ROOT/'results/uv355_refreshed_squared_model_R960_20261102';OUT=ROOT/'results/uv355_height_margin_design_R974_20261102'


def merit(v):
    reserve=np.asarray([.005 if l.startswith(('heightP_','heightN_')) else 0. for l in v['optical_labels']])
    return 1000*float(np.sum(np.minimum(v['optical']-reserve,0.)**2))+1000*float(np.sum(np.minimum(v['physical'],0.)**2))


def main():
    assert not OUT.exists();OUT.mkdir();p=read(FD/'preparation.json');assert all(sha(q['path'])==q['sha256']for q in p['pinned_files']);policy()
    seed=read(ROOT/'results/uv355_unconditional_repair_review_R971_20261102/CANDIDATE_01/FULL_R943_REVIEW.json');model=Path(seed['model'])
    assert sha(model)==seed['sha256'] and seed['policy_sha256']==sha(p['policy'])
    p.update(status='unconditional_native_all_rows_minimum_step_repair_prepared',seed_model=str(model),seed_sha256=seed['sha256'],
             initial_LM_search_damping=50.,adaptive_LM_search_damping=True,maximum_finite_corrections=20,cached_derivative_origin_sha256=p['source_sha256'],
             all85_fresh_at_initial_source=False,all_optical_rows_unconditional=True,minimum_coordinate_repair=True,image_height_search_margin_um=.05,all85_fresh_at_finite_linearization_poses=False,local_J_are_approximations=True,squared_RMS_chain_rule=True,
             finite_corrections_not_counted_as_original_successful_interior_rounds=True)
    data=FD/'FRESH_CURRENT_POLICY_J85.npz'
    p['pinned_files'] += [dict(path=str(data),sha256=sha(data)),dict(path=str(model),sha256=sha(model)),
                         dict(path=str(model.with_suffix('.MF')),sha256=sha(model.with_suffix('.MF'))),
                         dict(path=str(model.with_suffix('.npz')),sha256=sha(model.with_suffix('.npz'))),
                         dict(path=str(Path(variant.__file__).resolve()),sha256=sha(Path(variant.__file__))),
                         dict(path=str(Path(__file__).resolve()),sha256=sha(Path(__file__)))]
    write(OUT/'preparation.json',p)
    rows=[r for r in mf_signature(Path(p['source_model']).with_suffix('.MF')) if r[0]=='OPDX'];groups={}
    for i,row in enumerate(rows):
        if int(row[2]) in (1,2,3):groups.setdefault((int(row[2]),float(row[4])),[]).append(i)
    for (wave,radius),indices in groups.items():
        variant.GROUPS.append((indices,.02/((2. if radius==0. else 1.)*np.sqrt(sum(rows[i][-1] for i in indices)))))
    state=dict(status='waiting_frozen_native_optimizer_seat',active=True,read_only=False,pid=os.getpid(),
               process_creation_identity=process_identity(os.getpid()),source_sha256=p['source_sha256'],
               seed_sha256=seed['sha256'],evaluations=0,trials=[],iterations=[],qualified=False,
               full_4mm_design_accepted=False,MTF_gate=False,local_J_are_approximations=True)
    def save():state['utc']=datetime.now(timezone.utc).isoformat();write(OUT/'progress.json',state)
    def active():
        assert not read(method.CHAT/'progress.json')['user_task_paused'] and not(OUT/'STOP_REQUEST').exists();policy()
    session=read(method.CHAT/'progress.json');session['routes'].append(dict(state,root=str(OUT),progress=str(OUT/'progress.json'),
          role='unconditional_all_rows_minimum_step_optimizer',kind='R943_frozen_origin_native_corrections'))
    write(method.CHAT/'progress.json',session);save();app=None
    try:
        with optimizer_slot():
            active();app,api,bridge=method.make_application();system=app.PrimarySystem
            evaluate,apply,initial,scales,variables,template,signature,chart,points,color=context(system,api,bridge,Path(p['source_model']),OUT,state,save,active)
            with np.load(data) as z:
                assert str(z['source_sha256'])==p['source_sha256'] and np.max(abs(chart.T-z['T']))<1e-10
                keys=('residual','physical','optical','phase_curvature_residual','dense_WFE','dense_Airy')
                jac={k:z['J_'+k].copy() for k in keys};jcolor=z['J_color'].copy()
            with np.load(FD/'PART_0/BASELINE.npz') as z:
                assert np.max(abs(initial-z['initial']))<1e-12 and np.max(abs(scales-z['scales']))<1e-15
                assert variables==[tuple(v) for v in z['variables'].tolist()]
                assert np.max(abs(chart.T-z['T']))<1e-10
            with np.load(model.with_suffix('.npz')) as z:
                assert np.max(abs(initial-z['initial']))<1e-12 and np.max(abs(scales-z['scales']))<1e-15
                assert np.max(abs(chart.T-z['T']))<1e-10
                y=z['search_coordinates'].copy();assert np.max(abs(chart.to_native(y)-z['coordinates']))<1e-7
            base=evaluate(y);native=seed['native_reviews'][1]
            errors=dict(WFE=abs(base['current_worst_WFE']-native['wfe_worst_waves']),Airy=abs(base['current_worst_Airy']-native['rms_over_airy_worst']))
            assert max(errors.values())<1e-8 and base['physical_pass'] and min(base['physical'])>=-1e-8
            state['seed_replay_errors']=errors;state['baseline_score']=merit(base);save()
            assert abs(base['maximum_height_error_um']-14.989999012421151)<1e-6
            warm_path=model.parent/'APPROXIMATE_LOCAL_J_01.npz'
            blob=warm_path.read_bytes()
            with np.load(io.BytesIO(blob),allow_pickle=False) as warm:
                assert str(warm['frozen_derivative_origin_sha256'])==p['source_sha256']
                assert np.max(abs(warm['linearization_pose']-y))<.001
                state['warm_J_pose_distance']=float(np.linalg.norm(warm['linearization_pose']-y))
                assert not bool(warm['all85_fresh_at_this_pose'])
                jac={k:warm['J_'+k].copy()for k in keys};jcolor=warm['J_color'].copy()
            snapshot=OUT/'WARM_START_APPROXIMATE_J.npz';snapshot.write_bytes(blob)
            state['warm_start_approximate_J']=dict(snapshot=str(snapshot),sha256=sha(snapshot),original_file=str(warm_path),all85_fresh_at_this_pose=False,nearby_pose_approximation=True);save()

            for iteration in range(1,9):
                active();state.update(status='frozen_origin_native_sequential_correction',active_iteration=iteration,linearization_pose=y.tolist());save()
                c0,cp=color(y,independent=True);write(OUT/f'COLOR_BASE_{iteration:02d}.json',cp)
                reference={k:v.copy() for k,v in jac.items()};color_reference=jcolor.copy();basis=[];observed_history={};color_history=[];accepted=None
                for radius in (.25,.125,.5,1.):
                    direction_passed=False
                    for qc_round in range(6):
                        step,proof=variant.proposal(base,jac,radius,c0,jcolor);h=.005
                        for retry in range(8):
                            try:minus=evaluate(y-h*step);plus=evaluate(y+h*step);break
                            except Exception:
                                if retry==7:raise
                                h*=.5
                        observed={k:(vector(plus)[k]-vector(minus)[k])/(2*h) for k in keys}
                        check={k:float(np.linalg.norm(observed[k]-jac[k]@step)/max(np.linalg.norm(observed[k]),1e-12)) for k in ('optical','physical','dense_WFE','dense_Airy')}
                        cm,_=color(y-h*step);cp,_=color(y+h*step);dc=(cp-cm)/(2*h)
                        color_error=float(np.max(abs(dc-jcolor@step)))
                        record=dict(iteration=iteration,radius=radius,round=qc_round,h=h,relative_errors=check,color_absolute_error=color_error,
                                    pose=y.tolist(),LM_search_damping=_namespace['SEARCH_DAMPING'],frozen_derivative_origin_sha256=p['source_sha256'])
                        state.setdefault('native_direction_QC',[]).append(record);save()
                        if max(check.values())<.03 and color_error<5e-5:direction_passed=True;break
                        if qc_round in (2,4):_namespace['SEARCH_DAMPING']=min(500.,_namespace['SEARCH_DAMPING']*10.)
                        basis.append(step.copy());lengths=np.linalg.norm(np.column_stack(basis),axis=0);B=np.column_stack(basis)/lengths
                        for key,obs in observed.items():
                            observed_history.setdefault(key,[]).append(obs.copy());Y=np.column_stack(observed_history[key])/lengths
                            jac[key]=reference[key]+(Y-reference[key]@B)@np.linalg.pinv(B,rcond=.001)
                        color_history.append(dc.copy());Yc=np.column_stack(color_history)/lengths
                        jcolor=color_reference+(Yc-color_reference@B)@np.linalg.pinv(B,rcond=.001)
                    if not direction_passed:continue
                    np.savez(OUT/f'APPROXIMATE_LOCAL_J_{iteration:02d}.npz',**{'J_'+k:v for k,v in jac.items()},J_color=jcolor,
                             linearization_pose=y,frozen_derivative_origin_sha256=p['source_sha256'],all85_fresh_at_this_pose=False)
                    for fraction in (1.,.75,.5,.25,.125,.0625,.03125,.015625):
                        candidate=y+fraction*step
                        if max(abs(candidate))>2.:continue
                        try:v=evaluate(candidate)
                        except Exception as error:
                            state['trials'].append(dict(iteration=iteration,radius=radius,fraction=fraction,error=repr(error)));save();continue
                        safe=bool(v['physical_pass'] and min(v['physical'])>=-1e-8 and min(v['optical'])>=0.)
                        row=dict(iteration=iteration,radius=radius,fraction=fraction,safe=safe,score=merit(v),
                                 WFE=v['current_worst_WFE'],Airy=v['current_worst_Airy'],
                                 curvature_object_um=v['current_curvature_object_um'],astigmatism_object_um=v['current_astigmatism_object_um'],maximum_height_error_um=v['maximum_height_error_um'],front_mrad=v['front_mrad'])
                        row['failed_physical_guards']=sorted([dict(label=l,value=float(vv))for l,vv in zip(v['physical_labels'],v['physical'])if vv < -1e-8],key=lambda q:q['value'])[:8]
                        row['lost_passed_optical_guards']=sorted([dict(label=v['optical_labels'][i],value=float(v['optical'][i]))for i in range(len(base['optical']))if v['optical'][i] < 0],key=lambda q:q['value'])[:8]
                        state['trials'].append(row);save()
                        if safe and row['score']<merit(base)-1e-8:
                            accepted=(candidate,v,row,proof);break
                    if accepted is not None:break
                if accepted is None:
                    state.update(status='frozen_native_correction_stalled_requires_new_model_assessment');break
                y,base,row,proof=accepted;apply(y);system.MFE.LoadMeritFunction(str(Path(p['source_model']).with_suffix('.MF')))
                path=OUT/f'UNQUALIFIED_NATIVE_CORRECTION_{iteration:02d}.zmx';system.SaveAs(str(path));system.MFE.SaveMeritFunction(str(path.with_suffix('.MF')))
                assert method.geom.mf_signature(path.with_suffix('.MF'))==signature and method.geom.invariants(path)['static_invariants_pass']
                current=[(sn,c) for sn in range(system.LDE.NumberOfSurfaces-1)for c in range(2,20)if system.LDE.GetSurfaceAt(sn).GetCellAt(c).Solve==api.Editors.SolveType.Variable]
                assert current==variables
                physical=method.geom.physical_audit(path,16385);assert physical['passed'];write(path.with_suffix('.physical.json'),physical)
                np.savez(path.with_suffix('.npz'),coordinates=chart.to_native(y),search_coordinates=y,initial=initial,scales=scales,variables=variables,T=chart.T)
                # The accepted fraction controls the next proposal regularization.
                # The actual candidate still has to satisfy every hard guard.
                row['LM_search_damping']=proof['LM_search_damping']
                if fraction>=.5:_namespace['SEARCH_DAMPING']=max(5.,_namespace['SEARCH_DAMPING']/2.)
                elif fraction<=.125:_namespace['SEARCH_DAMPING']=min(500.,_namespace['SEARCH_DAMPING']*2.)
                row.update(model=str(path),sha256=sha(path),full129_513_review_required=True,proposal=proof,qualified=False,
                           frozen_derivative_origin_sha256=p['source_sha256'],local_J_are_approximations=True)
                state['best_candidate']=dict(row);state['iterations'].append(dict(row));save()
                system.MFE.LoadMeritFunction(str(template));system.MFE.CalculateMeritFunction()
                if min(base['optical'])>=0:
                    state.update(status='local_native_numerical_limits_met_requires_full_review',all_original_stopping_and_manufacturing_evidence_still_required=True);break
            else:state['status']='frozen_native_20_corrections_complete_not_original_stopping_rounds'
    except BaseException:state.update(status='frozen_native_corrections_failure_preserved',error=traceback.format_exc());raise
    finally:
        if app is not None:app.CloseApplication()
        assert all(sha(q['path'])==q['sha256'] for q in p['pinned_files'])
        state['active']=False;save();session=read(method.CHAT/'progress.json')
        for r in session['routes']:
            if r.get('pid')==os.getpid() and r.get('process_creation_identity')==state['process_creation_identity']:r.update(active=False,status=state['status'])
        write(method.CHAT/'progress.json',session)


if __name__=='__main__':main()
