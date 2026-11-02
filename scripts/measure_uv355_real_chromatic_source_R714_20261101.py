"""Fresh real-ray color residuals/J85, using the original soft normalizations."""
import argparse,datetime,math,os,shutil,traceback
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from atomic_progress import read_json_retry as read,write_json_atomic as write
from run_uv355_multistart_campaign import sha
from uv355_verification_priority import process_identity
ROOT=Path(__file__).resolve().parents[1]


def make_measure(system,ZOSAPI,bridge,apply,active):
    from compiled_batch_bridge import trace_bridge
    from chromatic_control import ZONES,FIELDS,AXIAL_SCALE_UM,LATERAL_SCALE_UM,metrics,best_focus
    nodes,weights=np.polynomial.legendre.leggauss(32);pupil=[]
    for node,weight in zip(nodes,weights):
        r=math.sqrt((node+1.)/2.)
        for arm in range(64):
            a=2*math.pi*arm/64;pupil.append((r*math.cos(a),r*math.sin(a),float(weight)/(2*64)))
    requests=sorted({(w,0.,x,y)for w in(1,2,3)for x,y,_ in pupil}
        |{(w,h,0.,0.)for w in(1,2,3)for h in(0.,*FIELDS)}
        |{(w,0.,0.,z)for w in(1,2,3)for z in ZONES})
    op=ZOSAPI.Editors.MFE.MeritOperandType;transport_verified=False
    def measure(y,independent=False):
        nonlocal transport_verified
        active();apply(y);system.MFE.CalculateMeritFunction();ray=system.Tools.OpenBatchRayTrace()
        try:
            rows=trace_bridge(bridge,ray,36,[(w,0.,h,x,z)for w,h,x,z in requests]);assert np.isfinite(rows).all()
            cache=dict(zip(requests,rows));transport=0.
            if not transport_verified:
                for request in(requests[0],requests[len(requests)//2],requests[-1]):
                    w,h,x,z=request;r=ray.SingleRayNormUnpol(ZOSAPI.Tools.RayTrace.RaysType.Real,36,w,0.,h,x,z,False,0,0,*([0.]*11))
                    assert r[0]and not r[1]and not r[2];transport=max(transport,float(np.max(abs(np.array(r[3:9])-cache[request]))))
                assert transport<1e-10;transport_verified=True
            axial=[float(system.MFE.GetOperandValue(op.AXCL,1,w,zone,0.,0.,0.,0.,0.))for zone in ZONES for w in(2,3)]
            chiefs={(w,h):cache[w,h,0.,0.][:3]for w in(1,2,3)for h in FIELDS}
            focus={w:best_focus([(cache[w,0.,x,z][:3],cache[w,0.,x,z][3:],weight)for x,z,weight in pupil])for w in(1,2,3)}
            report=metrics(axial,chiefs,focus)
            lateral=np.array([chiefs[w,h][:2]-chiefs[1,h][:2]for h in FIELDS for w in(2,3)])*1000.
            residual=np.r_[np.asarray(axial)*1000./AXIAL_SCALE_UM/np.sqrt(3*12),
                np.array([focus[w]-focus[1]for w in(2,3)])*1000./AXIAL_SCALE_UM/np.sqrt(3*2),
                lateral.ravel()/LATERAL_SCALE_UM/np.sqrt(3*32)]
            assert residual.shape==(78,)and abs(float(residual@residual)-report['chromatic_score'])<1e-10
            if independent:
                from independent_chromatic_audit import measure as verify
                def trace(surface,w,h,x,z):
                    assert surface==36;row=cache[w,h,x,z];return row[:3],row[3:]
                check=verify(system,ZOSAPI,trace,rings=32,arms=64);assert check['calculation_verified']
                assert abs(check['chromatic_score']-report['chromatic_score'])<1e-10
                report['independent32x64']=check;report['batch_native_max_error']=transport
            return residual,report
        finally:ray.Close()
    return measure


def main(model,review,out):
    import run_uv355_direct_native_hard_geometry_R406_20261101 as method
    from verification_capacity import verification_slot
    from uv355_extended_thickness_audit_R351_20261031 import install
    from uv355_orthogonal_asphere_coordinates_R679_20261101 import OrthogonalGaussianFocusCoordinates
    from run_uv355_fourmm_derivatives_recovery_R126_20261028 import dependencies
    install();os.environ['UV355_FORMAL_POLICY_FILE']=str(ROOT/'results/uv355_height_lt15_policy_20261018/formal_policy.json')
    assert not out.exists();rs=read(review/'trial_progress.json');proof=read(review/'INDEPENDENT_NATIVE_METHOD_VERIFICATION_R442_20261101.json')
    assert rs['all_saved_candidates_reviewed']and proof['all_saved_candidates_verified']
    assert len(rs['reviews'])==1 and rs['reviews'][0]['sha256']==sha(model)==proof['candidates'][0]['sha256']
    out.mkdir();(out/'ISOLATED_SOURCE').mkdir();source=out/'ISOLATED_SOURCE/SOURCE.zmx'
    shutil.copy2(model,source);shutil.copy2(model.with_suffix('.MF'),source.with_suffix('.MF'))
    sourcehash,mfhash=sha(source),sha(source.with_suffix('.MF'))
    pins=dependencies([Path(__file__)]);pins.update([source,source.with_suffix('.MF'),review/'trial_progress.json',
        review/'INDEPENDENT_NATIVE_METHOD_VERIFICATION_R442_20261101.json',Path(rs['reviews'][0]['review'])])
    write(out/'preparation.json',dict(source_model=str(source),source_sha256=sourcehash,source_MF_sha256=mfhash,
        source_review=str(review),soft_color_zero_targets_only=True,axial_normalization_um=20.,lateral_normalization_um=.02,
        no_new_chromatic_acceptance_limits=True,qualified=False,pinned_files=[dict(path=str(p),sha256=sha(p))for p in sorted(pins)]))
    state=dict(status='waiting_readonly_real_chromatic_J85',active=True,read_only=True,pid=os.getpid(),
        process_creation_identity=process_identity(os.getpid()),source_sha256=sourcehash,evaluations=0,completed_columns=[],qualified=False)
    sp=method.CHAT/'progress.json'
    def save():state['utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();write(out/'progress.json',state)
    def active():assert not read(sp).get('user_task_paused')and not(out/'STOP_REQUEST').exists()
    active();session=read(sp);session['routes'].append(dict(state,root=str(out),progress=str(out/'progress.json'),kind='readonly_real_chromatic_source_J85'))
    write(sp,session);save();app=None
    try:
        with verification_slot():
            app,ZOSAPI,bridge=method.make_application();system=app.PrimarySystem
            evaluate,native_apply,initial,scales,variables,_,_=method.context(system,ZOSAPI,bridge,source,out,state,save,active)
            base=evaluate(np.zeros(85));assert base['physical_pass']
            chart=OrthogonalGaussianFocusCoordinates(system,ZOSAPI,source,initial,scales,variables)
            measure=make_measure(system,ZOSAPI,bridge,lambda y:native_apply(chart.to_native(y)),active)
            zero=np.zeros(85);r0,report=measure(zero,independent=True);write(out/'INDEPENDENT_BASELINE.json',report)
            jacobian=np.full((78,85),np.nan);steps=[]
            for col in range(85):
                active();h=.001;direction=np.eye(85)[col]
                for attempt in range(10):
                    try:minus,_=measure(-h*direction);plus,_=measure(h*direction);break
                    except Exception:
                        if attempt==9:raise
                        h*=.5
                jacobian[:,col]=(plus-minus)/(2*h);steps.append(h);state['completed_columns'].append(col)
                state.update(status='real_chromatic_source_columns_collecting');save()
                np.savez(out/'PARTIAL_REAL_CHROMATIC_J85.npz',source_sha256=sourcehash,initial=initial,scales=scales,
                    variables=variables,baseline=r0,Jsearch=jacobian,T=chart.T,columns=state['completed_columns'])
            checks=[]
            for k in range(3):
                direction=np.sin((k+1.)*(np.arange(85)+1.));direction/=np.linalg.norm(direction);h=.0005
                minus,_=measure(-h*direction);plus,_=measure(h*direction);observed=(plus-minus)/(2*h);predicted=jacobian@direction
                error=float(np.max(abs(observed-predicted)));relative=float(np.linalg.norm(observed-predicted)/max(np.linalg.norm(observed),1e-15))
                check=dict(direction=k,maximum_normalized_direction_error=error,relative_L2_error=relative,
                    passed=error<5e-5 and relative<.03);checks.append(check);assert check['passed'],check
            restored,final=measure(zero,independent=True);assert np.max(abs(restored-r0))<1e-8
            physical=jacobian@np.linalg.inv(chart.T);error=float(np.max(abs(physical@chart.T-jacobian)));assert error<1e-7
            np.savez(out/'FRESH_REAL_CHROMATIC_J85.npz',source_sha256=sourcehash,initial=initial,scales=scales,
                variables=variables,baseline=r0,Jphysical=physical,Jsearch=jacobian,T=chart.T,steps=steps,
                axial_normalization_um=20.,lateral_normalization_um=.02,all85_at_actual_source=True)
            state.update(status='fresh_real_chromatic_source_J85_complete',all85_columns_measured=True,
                native_direction_checks=checks,source_replay_pass=True,frame_roundtrip_error=error,
                no_previous_source_Jacobian_used=True,no_chromatic_acceptance_limits_added=True)
    except BaseException:state.update(status='real_chromatic_J85_failure_preserved',error=traceback.format_exc());raise
    finally:
        if app is not None:app.CloseApplication()
        assert all(sha(q['path'])==q['sha256']for q in read(out/'preparation.json')['pinned_files'])
        state['active']=False;save();session=read(sp)
        for r in session['routes']:
            if r.get('pid')==os.getpid()and r.get('process_creation_identity')==state['process_creation_identity']:r.update(active=False,status=state['status'])
        write(sp,session)
    print(dict(status=state['status'],source_sha256=sourcehash,checks=state['native_direction_checks']),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--review',type=Path,required=True);p.add_argument('--profile',type=Path,required=True);a=p.parse_args()
    main(a.model.resolve(),a.review.resolve(),a.profile.resolve())
