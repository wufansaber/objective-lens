"""Source-specific fresh85 model with squared-RMS chain derivatives at all945 points.

Reuses the R945 native ray/solid/focal measurements, fixes every derived native
WFE/Airy/order/residual row consistently, and preserves raw derivatives for audit.
"""
import argparse
import ast
import os
from pathlib import Path
import numpy as np
from atomic_progress import read_json_retry as read,write_json_atomic as write
from run_uv355_multistart_campaign import sha
import run_uv355_focal_design_R945_20261102 as original
from uv355_direct_native_objective_QP_R405_20261101 import sample_points

ROOT=original.ROOT;ENV='UV355_SQUARED_CURRENT_FD_PROFILE';OUT=None


def pins():
    p=read(OUT/'preparation.json')
    assert all(sha(q['path'])==q['sha256'] for q in p['pinned_files'])
    return p


def active():
    assert not read(original.CHAT/'progress.json')['user_task_paused'] and not(OUT/'STOP_REQUEST').exists()
    original.policy()


def correct_native_column(labels,points,jo,dw,da):
    index={(q['method'],q['wave'],q['radius_normalized'],float(q['azimuth_deg'])):i for i,q in enumerate(points)}
    axes={(q['method'],q['wave']):i for i,q in enumerate(points)if not q['radius_normalized']}
    targets={}
    native=sample_points();ids=[];axis_ids={}
    for method,size,w,r,a in native:
        i=index[method,w,r,a];axis=axes[method,w];ids.append(i)
        tag=f'{method}_{w}_{r:.8f}_{a:.1f}'
        targets['native_WFE_'+tag]=-dw[i]/(.04 if r==0 else .055)
        targets['native_spot_'+tag]=-da[i]
        if r:
            targets['native_axisWFE_'+tag]=(dw[i]-dw[axis])/.02
            targets['native_axisSpot_'+tag]=(da[i]-da[axis])/.2
        else:axis_ids[method,w]=len(ids)-1
    for i,q in enumerate(points):
        axis=axes[q['method'],q['wave']]
        targets[f'current_WFE_{i}']=-dw[i]/(.04 if q['radius_normalized']==0 else .055)
        targets[f'current_Airy_{i}']=-da[i]
        if q['radius_normalized']:
            targets[f'current_axisWFE_{i}']=(dw[i]-dw[axis])/.055
            targets[f'current_axisAiry_{i}']=da[i]-da[axis]
    result=jo.copy();located=0
    for i,label in enumerate(labels):
        if label in targets:result[i]=targets[label];located+=1
    assert located==len(targets)
    ids=np.asarray(ids);ia=np.asarray(list(axis_ids.values()),dtype=int)
    spectral=np.asarray([{1:1.,2:.5625,3:.5625}[p[2]]for p in native]);mass=spectral/spectral.sum();amass=spectral[ia]/spectral[ia].sum()
    jr=np.r_[np.sqrt(mass)*dw[ids]/.05,np.sqrt(.25*mass)*da[ids],np.sqrt(amass)*dw[ids[ia]]/.025]
    assert jr.shape==(339,) and np.isfinite(result).all()
    return result,jr


def function(name):
    text=Path(original.__file__).read_text(encoding='utf-8-sig');tree=ast.parse(text)
    return ast.get_source_segment(text,next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name==name))


def functions():
    ns=dict(vars(original),OUT=OUT,pins=pins,active=active,__file__=str(Path(__file__).resolve()),correct_native_column=correct_native_column)
    baseline=function('baseline_check')
    old="ROOT/'results/uv355_c628_pending_dense_R936_20261102/ACTUAL_FULL513_BASELINE.json'"
    assert baseline.count(old)==1;baseline=baseline.replace(old,"OUT/'ACTUAL_FULL513_BASELINE.json'")
    exec(compile(baseline,str(Path(__file__)),'exec'),ns)
    part=function('part')
    needle='            jc=np.full((78,85),np.nan)';assert part.count(needle)==1
    part=part.replace(needle,needle+"\n            raww=np.full((len(base['dense_WFE']),85),np.nan);rawa=raww.copy()")
    needle="                for key in jac:jac[key][:,col]=(vector(plus)[key]-vector(minus)[key])/(2*h)";assert part.count(needle)==1
    patch="""
                raww[:,col]=jac['dense_WFE'][:,col];rawa[:,col]=jac['dense_Airy'][:,col]
                dw=(plus['dense_WFE']**2-minus['dense_WFE']**2)/(4*h*base['dense_WFE'])
                da=(plus['dense_Airy']**2-minus['dense_Airy']**2)/(4*h*base['dense_Airy'])
                jac['dense_WFE'][:,col]=dw;jac['dense_Airy'][:,col]=da
                jac['optical'][:,col],jac['residual'][:,col]=correct_native_column(base['optical_labels'],points,jac['optical'][:,col],dw,da)
"""
    part=part.replace(needle,needle+patch)
    old="J_color=jc,columns=state['completed_columns'],";assert part.count(old)==1
    part=part.replace(old,"J_color=jc,J_raw_dense_WFE=raww,J_raw_dense_Airy=rawa,columns=state['completed_columns'],")
    # Keep one slot available for independent reviews while these read-only
    # workers collect a new model. The global lease still enforces the cap of4.
    part=part.replace('with verification_slot():','with throttled_slot() as intake_released:')
    old='active();app,api,bridge=method.make_application();system=app.PrimarySystem';assert part.count(old)==1
    part=part.replace(old,'active();app,api,bridge=method.make_application();intake_released();system=app.PrimarySystem')
    ns['throttled_slot']=throttled_slot
    exec(compile(part,str(Path(__file__)),'exec'),ns)
    run=function('run');needle="state['all85_current_source_columns_complete']=True;save();optimize(state,save)";assert run.count(needle)==1
    run=run.replace(needle,"state['all85_current_source_columns_complete']=True;state.update(status='fresh_source_squared_RMS_J85_complete',squared_RMS_chain_rule=True);save()")
    run=run.replace("read_only=False,pid=os.getpid()","read_only=True,pid=os.getpid()")
    exec(compile(run,str(Path(__file__)),'exec'),ns)
    return ns


from contextlib import contextmanager
@contextmanager
def throttled_slot():
    import msvcrt,time
    from verification_capacity import verification_slot
    from inspect_uv355_host_processes_20261020 import inventory
    lock=(OUT/'FD_INTAKE.lock').open('a+b');lock.seek(0,2)
    if not lock.tell():lock.write(b'0');lock.flush()
    held=False
    try:
        while not held:
            active();lock.seek(0)
            try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);held=True
            except OSError:time.sleep(.3)
        while True:
            active();h=inventory();assert h['query_success']
            if sum(p['name'].lower()=='opticstudio.exe'for p in h['processes'])<3:break
            time.sleep(.5)
        with verification_slot():
            def release():
                nonlocal held
                if held:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);held=False
            yield release
    finally:
        if held:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()


def prepare():
    from run_uv355_fourmm_derivatives_recovery_R126_20261028 import dependencies
    assert not OUT.exists();record=read(ROOT/'key_results/LATEST_R943_REVIEWED.json')
    source=Path(record['model']);assert sha(source)==record['sha256']
    ref=record['native_reviews'][1];review=Path(ref['original_review']);assert sha(review)==ref['original_review_sha256']
    assert not any(k not in ('worst_wavefront','spot_airy')for k in ref['failed_numerical_checks'])
    native=read(review);assert native['field_count']==513 and native['sha256']==record['sha256']
    pointfile=ROOT/'results/uv355_c628_pending_dense_R936_20261102/BOUNDARY_POINTS.json'
    points=read(pointfile)['points'];lookup={(r['method'],r['wave'],r['radius_normalized'],float(r['azimuth_deg'])):r for r in native['optical']}
    selected=[lookup[q['method'],q['wave'],q['radius_normalized'],float(q['azimuth_deg'])]for q in points]
    OUT.mkdir();write(OUT/'REFERENCE_SOURCE.json',record)
    write(OUT/'ACTUAL_FULL513_BASELINE.json',dict(source_sha256=record['sha256'],WFE=[r['wfe_waves']for r in selected],Airy=[r['rms_over_airy']for r in selected]))
    paths=dependencies([Path(__file__),Path(original.__file__)])|{source,source.with_suffix('.MF'),review,Path(record['policy']),pointfile,
           OUT/'REFERENCE_SOURCE.json',OUT/'ACTUAL_FULL513_BASELINE.json'}
    write(OUT/'preparation.json',dict(status='source_specific_squared_RMS_native85_prepared',source_model=str(source),source_sha256=record['sha256'],
          source_review=str(review),policy=record['policy'],policy_sha256=record['policy_sha256'],
          original85_all_new_at_this_source=True,no_previous_source_derivatives_transferred=True,
          old_C628_used_for_native_point_identities_only=True,full945_squared_WFE_Airy_and_order_chain=True,
          raw_derivatives_also_saved=True,MTF_constraints=0,MTF_objective_terms=0,max_total_SDKs=4,
          pinned_files=[dict(path=str(p),sha256=sha(p))for p in sorted(paths)]))
    functions();print(dict(status='fresh_squared_RMS_source_prepared',source_sha256=record['sha256'],source_WFE=ref['wfe_worst_waves'],source_Airy=ref['rms_over_airy_worst']))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','run','part']);parser.add_argument('--out',type=Path);parser.add_argument('--part',type=int)
    args=parser.parse_args();value=args.out or os.environ.get(ENV);assert value
    OUT=Path(value).resolve();assert OUT.is_relative_to(ROOT/'results');os.environ[ENV]=str(OUT)
    if args.mode=='prepare':prepare()
    else:
        fn=functions()
        if args.mode=='run':fn['run']()
        else:assert args.part in (0,1,2);fn['part'](args.part)
