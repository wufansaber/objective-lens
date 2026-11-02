"""Measured phase Gauss-Newton proposals with hard physical inequalities."""
import numpy as np
from scipy import sparse


def projection(signature):
    rows=[r for r in signature if r[0]=='OPDX'];assert len(rows)==840
    transform=np.zeros((840,840));groups={}
    for i,r in enumerate(rows):groups.setdefault((int(r[2]),float(r[4])),[]).append(i)
    for (wave,radius),indices in groups.items():
        ix=np.asarray(indices);weights=np.asarray([rows[i][-1] for i in ix]);norm=weights/weights.sum()
        y=np.asarray([rows[i][6] for i in ix])
        basis=np.ones((len(ix),1)) if radius==0. else np.column_stack((np.ones(len(ix)),y))
        remove=np.eye(len(ix))-basis@np.linalg.solve(basis.T@(norm[:,None]*basis),basis.T*norm)
        # Preserve the original five channel weights.  Axis emphasis is only
        # a temporary optimization weight, never a revised acceptance limit.
        transform[np.ix_(ix,ix)]=np.sqrt(weights)[:,None]*remove*(2. if radius==0. else 1.)/.02
    return transform


def propose(residual,jphase,physical,jphysical,optical,joptical,radius,penalty=10.,damping=.05):
    import clarabel
    residual=np.asarray(residual);jr=np.asarray(jphase);g=np.asarray(physical);jg=np.asarray(jphysical)
    go=np.asarray(optical);jo=np.asarray(joptical);n=jr.shape[1];m=len(go);size=n+m
    assert n==85 and jg.shape==(len(g),n) and jo.shape==(m,n)
    assert np.min(g)>=-1e-8
    floors=np.minimum(.001,np.maximum(0.,g*.5))
    passed=np.flatnonzero(go>=0.);ofloors=np.minimum(.001,np.maximum(0.,go[passed]*.5))
    h=2.*(jr.T@jr/len(residual)+damping*np.eye(n))
    q=np.r_[2.*jr.T@residual/len(residual),np.zeros(m)]
    fullp=sparse.block_diag((h,sparse.eye(m)*2.*penalty/max(m,1)),format='csc')
    eye=sparse.eye(n,format='csc');zero=sparse.csc_matrix((n,m))
    blocks=[sparse.hstack((eye,zero)),sparse.hstack((-eye,zero)),sparse.hstack((-jg,sparse.csc_matrix((len(g),m))))]
    rhs=[np.full(n,radius),np.full(n,radius),g-floors]
    if len(passed):blocks.append(sparse.hstack((-jo[passed],sparse.csc_matrix((len(passed),m)))));rhs.append(go[passed]-ofloors)
    blocks.extend([sparse.hstack((-jo,-sparse.eye(m))),sparse.hstack((sparse.csc_matrix((m,n)),-sparse.eye(m)))])
    rhs.extend([go,np.zeros(m)]);a=sparse.vstack(blocks,format='csc');b=np.concatenate(rhs)
    gram=h+(a[:,:n].T@a[:,:n]).toarray();values,vectors=np.linalg.eigh((gram+gram.T)/2.)
    floor=max(float(values[-1])/1e8,float(np.median(values)),1.)
    factor=np.sqrt(floor/np.maximum(values,floor));optical_transform=vectors*factor[None,:]
    transform=sparse.block_diag((optical_transform,sparse.eye(m)),format='csc')
    p=(transform.T@fullp@transform).tocsc();at=(a@transform).tocsc();qt=np.asarray(transform.T@q).ravel()
    settings=clarabel.DefaultSettings();settings.verbose=False;settings.max_threads=1;settings.max_iter=400;settings.time_limit=120.
    settings.tol_gap_abs=1e-9;settings.tol_gap_rel=1e-9;settings.tol_feas=1e-9
    solution=clarabel.DefaultSolver(sparse.triu(p).tocsc(),qt,at,b,[clarabel.NonnegativeConeT(len(b))],settings).solve()
    encoded=np.asarray(transform@np.asarray(solution.x)).ravel();step=encoded[:n]
    pred=go+jo@step;lifted=np.r_[step,np.maximum(-pred,0.)]
    slack=b-a@lifted
    before=float(np.mean(residual**2)+penalty*np.mean(np.minimum(go,0.)**2))
    after=float(np.mean((residual+jr@step)**2)+penalty*np.mean(np.minimum(pred,0.)**2)+damping*(step@step))
    feasible=np.isfinite(step).all() and float(slack.min())>=-1e-8
    assert feasible and after<before-1e-8,dict(status=str(solution.status),minimum_slack=float(slack.min()),before=before,after=after)
    return step,dict(status=str(solution.status),predicted_cost_before=before,predicted_cost_after=after,
        original_coordinate_primal_minimum_slack=float(slack.min()),original_physical_minimum_slack=float(np.min(g+jg@step-floors)),
        physical_guard_count=len(g),passed_optical_guards_protected=len(passed),optical_repair_count=m,
        coordinate_whitening_condition_limit=1e8,maximum_step=float(np.max(abs(step))),
        feasible_descent_reconstructed_in_original_coordinates=True,
        native_finite_step_physical_audit_required=True,solver_optimality_not_claimed=True,qualified=False)
