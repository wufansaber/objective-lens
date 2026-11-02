"""Same fresh C628 native85 model, with measured phase trust bounds for finite steps.

The phase bounds guide the local model; native WFE/Airy and R943 focal/solid
checks remain the actual finite-step criteria. No MTF constraints or objectives.
"""
import ast
from datetime import datetime,timezone
import os
from pathlib import Path
import traceback
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from atomic_progress import read_json_retry as read,write_json_atomic as write
from run_uv355_multistart_campaign import sha
from optimize_until_stable import mf_signature
from uv355_verification_priority import process_identity
import uv355_focal_runtime_R944_20261102 as runtime
import run_uv355_focal_design_R945_20261102 as original

ROOT=original.ROOT;FD=original.OUT;OUT=ROOT/'results/uv355_C628_phase_bounded_R950_20261102'
GROUPS=[]


def proposal(base,jac,radius,color0=None,jcolor=None):
    text=Path(runtime.__file__).read_text(encoding='utf-8-sig');tree=ast.parse(text)
    code=ast.get_source_segment(text,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='proposal'))
    edits={"w=base['dense_WFE']/.055-1.; a=base['dense_Airy']-1.":"w=base['dense_WFE']/.0545-1.; a=base['dense_Airy']/.995-1.",
           "jw=jac['dense_WFE']/.055; ja=jac['dense_Airy']":"jw=jac['dense_WFE']/.0545; ja=jac['dense_Airy']/.995",
           'rhs=[np.full(n,radius),np.full(n,radius),g,o[passed]]':
           'rhs=[np.full(n,radius),np.full(n,radius),g-np.minimum(.001,np.maximum(g,0.)*.2),o[passed]-np.minimum(.00001,np.maximum(o[passed],0.)*.2)]',
           "    sol=clarabel.DefaultSolver(sparse.triu(P).tocsc(),q,A,b,[clarabel.NonnegativeConeT(len(b))],settings).solve()":
           """    cones=[clarabel.NonnegativeConeT(len(b))]
    phase_bounds=[]
    for indices,factor in GROUPS:
        c=jac['phase_curvature_residual'][indices]*factor
        bottom=sparse.hstack((-c,sparse.csc_matrix((len(c),k))),format='csc')
        block=sparse.vstack([sparse.csc_matrix((1,n+k)),bottom],format='csc')
        A=sparse.vstack((A,block),format='csc');b=np.r_[b,.005*radius,np.zeros(len(c))]
        cones.append(clarabel.SecondOrderConeT(len(c)+1));phase_bounds.append(c)
    sol=clarabel.DefaultSolver(sparse.triu(P).tocsc(),q,A,b,cones,settings).solve()"""}
    for old,new in edits.items():assert code.count(old)==1,old;code=code.replace(old,new)
    # SOC residuals are checked by cone membership, not elementwise positivity.
    old="    x=np.asarray(sol.x); assert np.isfinite(x).all() and min(b-A@x)>=-1e-7, (sol.status,float(min(b-A@x)))"
    assert code.count(old)==1
    code=code.replace(old,"""    x=np.asarray(sol.x);assert np.isfinite(x).all() and str(sol.status) in ('Solved','AlmostSolved'),sol.status
    original_rows=len(np.concatenate(rhs));linear_slack=b[:original_rows]-A[:original_rows]@x
    assert min(linear_slack)>=-1e-7,float(min(linear_slack))
    assert all(np.linalg.norm(c@x[:85])<=.005*radius+1e-8 for c in phase_bounds)""")
    namespace=dict(vars(runtime),GROUPS=GROUPS);exec(compile(code,str(Path(__file__)),'exec'),namespace)
    step,proof=namespace['proposal'](base,jac,radius,color0,jcolor)
    proof.update(measured_phase_trust_groups=len(GROUPS),phase_RMS_increment_bound_waves=.005*radius,
                 phase_bounds_are_auxiliary_not_native_WFE_substitutes=True,
                 WFE_search_goal=.0545,Airy_search_goal=.995,formal_WFE_limit=.055,formal_Airy_limit=1.)
    return step,proof


def main():
    assert not OUT.exists();OUT.mkdir();p=original.pins()
    assert read(FD/'progress.json')['all85_current_source_columns_complete']
    data=FD/'FRESH_CURRENT_POLICY_J85.npz';assert data.exists()
    p.update(status='same_C628_frozen_origin_phase_trust_variant',fresh_model=str(data),fresh_model_sha256=sha(data),
             previous_native_variant=str(FD),derivatives_not_relabelled_as_another_source=True,
             measured_phase_trust_is_search_guidance_only=True)
    p['pinned_files'] += [dict(path=str(data),sha256=sha(data)),dict(path=str(Path(__file__).resolve()),sha256=sha(Path(__file__)))]
    write(OUT/'preparation.json',p)
    rows=[r for r in mf_signature(Path(p['source_model']).with_suffix('.MF')) if r[0]=='OPDX'];assert len(rows)==840
    groups={}
    for i,row in enumerate(rows):
        if int(row[2]) in (1,2,3):groups.setdefault((int(row[2]),float(row[4])),[]).append(i)
    for (wave,radius),indices in groups.items():
        mass=sum(rows[i][-1] for i in indices)
        GROUPS.append((indices,.02/((2. if radius==0. else 1.)*np.sqrt(mass))))
    state=dict(status='phase_bounded_frozen_C628_native_design',active=True,read_only=False,pid=os.getpid(),
               process_creation_identity=process_identity(os.getpid()),source_sha256=p['source_sha256'],evaluations=0,
               qualified=False,full_4mm_design_accepted=False,MTF_gate=False,actual_measured_phase_groups=len(GROUPS))
    def save():state['utc']=datetime.now(timezone.utc).isoformat();write(OUT/'progress.json',state)
    def active():
        original.active();assert not(OUT/'STOP_REQUEST').exists()
    def pins():
        assert all(sha(q['path'])==q['sha256'] for q in p['pinned_files']);return p
    session=read(original.CHAT/'progress.json');session['routes'].append(dict(state,root=str(OUT),progress=str(OUT/'progress.json'),
             role='phase_bounded_R943_optimizer',kind='same_source_phase_bounded_native_minimax'))
    write(original.CHAT/'progress.json',session);save()
    text=Path(original.__file__).read_text(encoding='utf-8-sig');tree=ast.parse(text)
    code=ast.get_source_segment(text,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='optimize'))
    code=code.replace("out=OUT/'OPTIMIZER'","out=NEWOUT/'OPTIMIZER'")
    code=code.replace('for radius in (.5,1.,.25,2.):','for radius in (.5,.25,1.,2.):')
    code=code.replace('                check={}\n','                check={};observed_by_key={}\n')
    needle="                    check[key]=float(np.linalg.norm(observed-pred)/max(np.linalg.norm(observed),1e-12))"
    assert code.count(needle)==1;code=code.replace(needle,needle+"\n                    observed_by_key[key]=observed")
    needle='                assert max(check.values())<.03,check';assert code.count(needle)==1
    code=code.replace(needle,"""                if max(check.values())>=.03:
                    for key,observed in observed_by_key.items():
                        jac[key]+=(observed-jac[key]@step)[:,None]*step[None,:]/float(step@step)
                    state.setdefault('same_source_native_direction_calibrations',[]).append(dict(radius=radius,relative_errors=check,source_sha256=p['source_sha256']))
                    save();continue""")
    namespace=dict(vars(original),NEWOUT=OUT,proposal=proposal,active=active,pins=pins)
    exec(compile(code,str(Path(__file__)),'exec'),namespace)
    try:namespace['optimize'](state,save)
    except BaseException:state.update(status='phase_bounded_native_failure_preserved',error=traceback.format_exc());raise
    finally:
        state['active']=False;save();pins()
        session=read(original.CHAT/'progress.json')
        for r in session['routes']:
            if r.get('pid')==os.getpid() and r.get('process_creation_identity')==state['process_creation_identity']:r.update(active=False,status=state['status'])
        write(original.CHAT/'progress.json',session)


if __name__=='__main__':main()
