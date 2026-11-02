"""Direct native WFE/spot SQP; signed phase supplies step curvature only."""
import math,time
import numpy as np
from scipy import sparse
from compiled_batch_bridge import trace_bridge

def sample_points():
    points=[(m,z,w,float(r),0.)for m,z in [('GQ20',20)]for w in (1,2,3)for r in np.linspace(0.,1.,33)]
    points +=[(m,z,w,float(r),a)for m,z in [('RECT32',32),('RECT64',64)]for w in (1,2,3)for r in (0.,.03125,.25,.5,.75,1.)for a in ((0.,)if r==0. else(0.,45.))]
    return points

def augment_native(result,system,op,bridge,uniform):
    start=time.monotonic();points=sample_points();values=[]
    for method,size,w,r,angle in points:
        hx=r*math.sin(math.radians(angle));hy=r*math.cos(math.radians(angle))
        wf=float(system.MFE.GetOperandValue(op.RWCE if method=='GQ20'else op.RWRE,size,w,hx,hy,0.,0.,0.,0.))
        spot=float(system.MFE.GetOperandValue(op.RSCE if method=='GQ20'else op.RSRE,size,w,hx,hy,0.,0.,0.,0.))
        values.append((wf,spot))
    ray=system.Tools.OpenBatchRayTrace()
    try:axis=trace_bridge(bridge,ray,36,[(w,0.,0.,px,py)for w in (1,2,3)for px,py in uniform]).reshape(3,len(uniform),6)
    finally:ray.Close()
    na=np.max(np.linalg.norm(axis[...,3:5],axis=-1),axis=1)
    values=np.asarray(values);wf=values[:,0];airy=np.asarray([v[1]*na[p[2]-1]/(.61*{1:.355,2:.35499,3:.35501}[p[2]]*.001)for p,v in zip(points,values)])
    assert np.isfinite(values).all() and np.min(values)>=0. and np.isfinite(airy).all()
    axes={(p[0],p[2]):i for i,p in enumerate(points)if p[3]==0.}
    ia=np.asarray(list(axes.values()),dtype=int)
    spectral=np.asarray([{1:1.,2:.5625,3:.5625}[p[2]]for p in points]);mass=spectral/spectral.sum();amass=spectral[ia]/spectral[ia].sum()
    # All original five wavelength weights are represented. Channels 2/4 and
    # 3/5 are identical wavelengths and their weights are summed, never dropped.
    residual=np.r_[np.sqrt(mass)*wf/.05,np.sqrt(.25*mass)*airy,np.sqrt(amass)*wf[ia]/.025]
    guards=list(result['optical']);labels=list(result['optical_labels'])
    def add(label,value):labels.append(label);guards.append(float(value))
    for i,p in enumerate(points):
        method,size,w,r,angle=p;tag=f'{method}_{w}_{r:.8f}_{angle:.1f}'
        add(f'native_WFE_{tag}',1.-wf[i]/(.04 if r==0. else .05))
        add(f'native_spot_{tag}',1.-airy[i])
        if r:
            a=axes[method,w]
            add(f'native_axisWFE_{tag}',(wf[i]-wf[a])/.02)
            add(f'native_axisSpot_{tag}',(airy[i]-airy[a])/.2)
    result.update(phase_curvature_residual=result['residual'],residual=residual,optical=np.asarray(guards),optical_labels=labels,
        native_WFE=wf,native_Airy=airy,native_points=points,native_image_NA=na,
        direct_native_WFE_peak=float(wf.max()),direct_native_axis_WFE=float(wf[ia].max()),direct_native_Airy_peak=float(airy.max()),
        direct_native_seconds=time.monotonic()-start)
    assert len(residual)==339 and len(points)==165
    return result

def guard_weights(labels):
    def family(label):
        if label.startswith('native_'):return '_'.join(label.split('_')[:2])
        return label.split('_')[0].rstrip('PN')
    families=[family(s)for s in labels];counts={s:families.count(s)for s in set(families)}
    weights=np.asarray([(1. if s in ('EFL','sine')else 20.)/counts[s]for s in families])
    assert np.isfinite(weights).all()and min(weights)>0.
    return weights

def cost(result):
    return float(result['residual']@result['residual']+np.dot(guard_weights(result['optical_labels']),np.minimum(result['optical'],0.)**2))

def propose(residual,jr,physical,jg,optical,jo,labels,jcurvature,radius,damping=.05,phase_curvature_weight=.01):
    import clarabel
    g=np.asarray(physical);go=np.asarray(optical);n=jr.shape[1];m=len(go);assert n==85 and min(g)>=-1e-8
    weights=guard_weights(labels);floors=np.minimum(.001,np.maximum(0.,g*.5));passed=np.flatnonzero(go>=0.);ofloors=np.minimum(.001,np.maximum(0.,go[passed]*.5))
    # There is no signed-phase target or phase-gradient term in this objective.
    # Its Jacobian only regularizes finite changes to the native wavefront.
    h=2.*(jr.T@jr+damping*np.eye(n)+phase_curvature_weight*jcurvature.T@jcurvature/len(jcurvature))
    q=np.r_[2.*jr.T@residual,np.zeros(m)]
    fullp=sparse.block_diag((h,sparse.diags(2.*weights)),format='csc')
    eye=sparse.eye(n,format='csc');zero=sparse.csc_matrix((n,m))
    blocks=[sparse.hstack((eye,zero)),sparse.hstack((-eye,zero)),sparse.hstack((-jg,sparse.csc_matrix((len(g),m))))]
    rhs=[np.full(n,radius),np.full(n,radius),g-floors]
    if len(passed):blocks.append(sparse.hstack((-jo[passed],sparse.csc_matrix((len(passed),m)))));rhs.append(go[passed]-ofloors)
    blocks.extend([sparse.hstack((-jo,-sparse.eye(m))),sparse.hstack((sparse.csc_matrix((m,n)),-sparse.eye(m)))])
    rhs.extend([go,np.zeros(m)]);a=sparse.vstack(blocks,format='csc');b=np.concatenate(rhs)
    gram=h+(a[:,:n].T@a[:,:n]).toarray();vals,vec=np.linalg.eigh((gram+gram.T)/2.)
    floor=max(float(vals[-1])/1e8,float(np.median(vals)),1.);factor=np.sqrt(floor/np.maximum(vals,floor))
    transform=sparse.block_diag((vec*factor[None,:],sparse.eye(m)),format='csc')
    settings=clarabel.DefaultSettings();settings.verbose=False;settings.max_threads=1;settings.max_iter=400;settings.time_limit=120.
    settings.tol_gap_abs=1e-9;settings.tol_gap_rel=1e-9;settings.tol_feas=1e-9
    solution=clarabel.DefaultSolver(sparse.triu(transform.T@fullp@transform).tocsc(),np.asarray(transform.T@q).ravel(),(a@transform).tocsc(),b,[clarabel.NonnegativeConeT(len(b))],settings).solve()
    encoded=np.asarray(transform@np.asarray(solution.x)).ravel();step=encoded[:n];pred=go+jo@step;lifted=np.r_[step,np.maximum(-pred,0.)];slack=b-a@lifted
    before=float(residual@residual+np.dot(weights,np.minimum(go,0.)**2))
    after=float(np.sum((residual+jr@step)**2)+np.dot(weights,np.minimum(pred,0.)**2)+damping*(step@step)+phase_curvature_weight*np.mean((jcurvature@step)**2))
    assert np.isfinite(step).all()and min(slack)>=-1e-8 and after<before-1e-8,dict(status=str(solution.status),minimum_slack=float(min(slack)),before=before,after=after)
    return step,dict(status=str(solution.status),predicted_cost_before=before,predicted_cost_after=after,original_coordinate_primal_minimum_slack=float(min(slack)),maximum_step=float(max(abs(step))),
        direct_native_objective=True,signed_phase_target_used=False,signed_phase_step_curvature_only=True,all_passed_optical_samples_protected=True,physical_guard_count=len(g),optical_guard_count=m,
        all85_current_pose_centered_native_derivatives_required=True,nonlinear_native_acceptance_required=True,solver_optimality_not_claimed=True,qualified=False)
