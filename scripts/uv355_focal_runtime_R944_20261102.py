"""Versioned R943 native runtime: no MTF constraints; explicit focal-surface limits."""
import ast
from pathlib import Path
import numpy as np
from atomic_progress import read_json_retry as read
from run_uv355_multistart_campaign import sha
from uv355_orthogonal_asphere_coordinates_R679_20261101 import OrthogonalGaussianFocusCoordinates
from uv355_extended_thickness_audit_R351_20261031 import install as install_thickness
from uv355_batched_boundary_and_ordering_R741_20261101 import configure, measure
import run_uv355_direct_native_hard_geometry_R406_20261101 as method

ROOT = method.ROOT
POLICY = ROOT/'results/uv355_user_MTF_visual_focal_policy_R943_20261102/formal_policy.json'


def policy():
    pointer=read(ROOT/'CONTINUATION.json')['current_formal_policy']
    assert Path(pointer['file'])==POLICY and sha(POLICY)==pointer['sha256']
    p=read(POLICY)
    assert p['full_field_rms_wfe_limit_waves']==.055 and not p['MTF_hard_acceptance_requirement']
    assert p['field_curvature_object_limit_um']==p['astigmatism_object_limit_um']==.493
    return p


class FocusOutput(ast.NodeTransformer):
    def visit_Assign(self,node):
        if any(isinstance(t,ast.Name) and t.id=='result' for t in node.targets) and isinstance(node.value,ast.Call):
            node.value.keywords.extend([
                ast.keyword(arg='focus_object_signed',value=ast.parse('np.asarray(depth).reshape(3,33,2)',mode='eval').body),
                ast.keyword(arg='focal_magnifications',value=ast.parse('para[:,1]/.00002',mode='eval').body)])
        return self.generic_visit(node)


def context(system,api,bridge,source,out,state,save,active):
    """Keep established ray/solid tracing; explicitly replace old policy-derived rows."""
    p=policy(); install_thickness()
    # Unchanged interface/solid limits in this legacy helper are checked against
    # the explicit new policy; its WFE/MTF decisions are not used by this runtime.
    import os
    os.environ['UV355_FORMAL_POLICY_FILE']=str(ROOT/'results/uv355_height_lt15_policy_20261018/formal_policy.json')
    legacy=read(Path(os.environ['UV355_FORMAL_POLICY_FILE']))
    for key in ('object_chief_angle_limit_deg','front_divergence_limit_mrad','image_chief_angle_limit_deg','S33_air_gap_upper_mm','image_height_error_limit_mm'):
        assert p[key]==legacy[key]
    text=Path(method.__file__).read_text(encoding='utf-8-sig')
    tree=ast.parse(text); node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='context')
    code=ast.get_source_segment(text,node)
    assert code.count('mesh=geom.pupil(8,16)')==1
    code=code.replace('mesh=geom.pupil(8,16)','mesh=geom.pupil(32,64)')
    needle="    exec(compile(ast.Module(body=[node],type_ignores=[]),geom.__file__,'exec'),ns)"
    assert code.count(needle)==1
    code=code.replace(needle,"    node=FocusOutput().visit(node);ast.fix_missing_locations(node)\n"+needle)
    ns=dict(vars(method),FocusOutput=FocusOutput);exec(compile(code,str(Path(__file__)),'exec'),ns)
    raw,apply,initial,scales,variables,template,signature=ns['context'](system,api,bridge,source,out,state,save,active)
    chart=OrthogonalGaussianFocusCoordinates(system,api,source,initial,scales,variables)
    from measure_uv355_real_chromatic_source_R714_20261101 import make_measure
    color=make_measure(system,api,bridge,lambda y:apply(chart.to_native(y)),active)
    configure(source,out,template)
    desc=read(ROOT/'results/uv355_c628_pending_dense_R936_20261102/BOUNDARY_POINTS.json')
    points=desc['points']; assert len(points)==945
    axes={(q['method'],q['wave']):i for i,q in enumerate(points) if q['radius_normalized']==0}
    def evaluate(y):
        value=raw(chart.to_native(y)); labels=list(value['optical_labels']); g=value['optical'].copy()
        for i,label in enumerate(labels):
            if label=='sine': g[i]=.5+.5*g[i]
            elif label.startswith('native_WFE_') and not label.endswith('_0.00000000_0.0'):
                g[i]=1.-(.05/p['full_field_rms_wfe_limit_waves'])*(1.-g[i])
        def add(label,margin):labels.append(label);extra.append(float(margin))
        extra=[]
        focus=value['focus_object_signed']; curvature=focus.mean(axis=2); astig=focus[:,:,1]-focus[:,:,0]
        image_shift=focus*value['focal_magnifications'][:,None,None]**2
        for w in range(3):
            depth={1:.355,2:.35499,3:.35501}[w+1]/(2*value['native_image_NA'][w]**2)
            for j in range(33):
                for sign,suffix in ((1.,'P'),(-1.,'N')):
                    add(f'curvature{suffix}_{w+1}_{j}',1.-sign*curvature[w,j]/.493)
                    add(f'astigmatism{suffix}_{w+1}_{j}',1.-sign*astig[w,j]/.493)
                for k in range(2): add(f'image_depth_{w+1}_{j}_{k}',1.-abs(image_shift[w,j,k])/depth)
        wf,airy=measure(system,api,bridge,points,value['native_image_NA'])
        for i,q in enumerate(points):
            r=q['radius_normalized']; axis=axes[q['method'],q['wave']]
            add(f'current_WFE_{i}',1.-wf[i]/(.04 if r==0 else .055))
            add(f'current_Airy_{i}',1.-airy[i])
            if r:
                add(f'current_axisWFE_{i}',(wf[i]-wf[axis])/.055)
                add(f'current_axisAiry_{i}',airy[i]-airy[axis])
        value.update(optical=np.r_[g,extra],optical_labels=labels,dense_WFE=wf,dense_Airy=airy,
                     current_worst_WFE=float(max(wf)),current_worst_Airy=float(max(airy)),
                     current_curvature_object_um=float(np.max(abs(curvature))),
                     current_astigmatism_object_um=float(np.max(abs(astig))),
                     MTF_used_for_optimization_or_acceptance=False)
        assert not any('MTF' in label for label in labels)
        state['latest_current_metrics']={k:value[k] for k in ('current_worst_WFE','current_worst_Airy','current_curvature_object_um','current_astigmatism_object_um')}
        save();return value
    return evaluate,lambda y:apply(chart.to_native(y)),initial,scales,variables,template,signature,chart,points,color


def vector(value):
    return {k:np.asarray(value[k]) for k in ('residual','physical','optical','phase_curvature_residual','dense_WFE','dense_Airy')}


def proposal(base,jac,radius,color0=None,jcolor=None):
    """Native WFE/Airy minimax, hard passed optical/solid guards, no MTF rows."""
    import clarabel
    from scipy import sparse
    n=85; k=2; g=base['physical']; o=base['optical']; passed=np.flatnonzero(o>=0.)
    # Preserve all currently passing requirements. Violating WFE/Airy are driven
    # by explicit epigraphs; every finite candidate still needs a native check.
    w=base['dense_WFE']/.055-1.; a=base['dense_Airy']-1.
    jw=jac['dense_WFE']/.055; ja=jac['dense_Airy']
    jr=jac['residual']; jc=jac['phase_curvature_residual']
    h=2*(.05*np.eye(n)+.05*jr.T@jr+.01*jc.T@jc/max(1,len(jc)))
    color_gradient=np.zeros(n)
    if jcolor is not None:
        h+=.1*jcolor.T@jcolor
        color_gradient=.1*jcolor.T@color0
    P=sparse.block_diag((h,sparse.diags([2000.,1000.])),format='csc')
    q=np.r_[.1*jr.T@base['residual']+color_gradient,0.,0.]
    zero=lambda rows:sparse.csc_matrix((rows,k))
    blocks=[sparse.hstack((sparse.eye(n),zero(n))),sparse.hstack((-sparse.eye(n),zero(n))),
            sparse.hstack((-jac['physical'],zero(len(g)))),sparse.hstack((-jac['optical'][passed],zero(len(passed))))]
    rhs=[np.full(n,radius),np.full(n,radius),g,o[passed]]
    for values,J,column in ((w,jw,0),(a,ja,1)):
        slack=np.zeros((len(values),2));slack[:,column]=-1
        blocks.append(sparse.hstack((J,sparse.csc_matrix(slack))));rhs.append(-values)
    blocks.append(sparse.hstack((sparse.csc_matrix((2,n)),-sparse.eye(2))));rhs.append(np.zeros(2))
    A=sparse.vstack(blocks,format='csc');b=np.concatenate(rhs)
    settings=clarabel.DefaultSettings();settings.verbose=False;settings.max_threads=1;settings.max_iter=300;settings.time_limit=90.
    settings.tol_gap_abs=settings.tol_gap_rel=settings.tol_feas=1e-9
    sol=clarabel.DefaultSolver(sparse.triu(P).tocsc(),q,A,b,[clarabel.NonnegativeConeT(len(b))],settings).solve()
    x=np.asarray(sol.x); assert np.isfinite(x).all() and min(b-A@x)>=-1e-7, (sol.status,float(min(b-A@x)))
    return x[:85],dict(status=str(sol.status),radius=radius,predicted_WFE_excess=float(x[-2]),predicted_Airy_excess=float(x[-1]),
                       passed_optical_guards=len(passed),physical_guards=len(g),MTF_constraints=0,MTF_objective_terms=0)
