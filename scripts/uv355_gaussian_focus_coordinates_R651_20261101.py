"""Invertible finite Gaussian-focus compensation in the original85 variables.

Use reduced ray vector (height,n*angle). If internal optics is L=(A,B;C,D),
the full object-to-image B is A*do+B+(C*do+D)*di. The last search coordinate
changes that B; every other variable retains its original physical meaning.
"""
import numpy as np
from physical_prescription_audit import parse_model

class GaussianFocusCoordinates:
    def __init__(self,system,ZOSAPI,source,initial,scales,variables):
        self.initial=np.asarray(initial).copy();self.scales=np.asarray(scales).copy()
        self.variables=[tuple(v)for v in variables];self.surfaces=parse_model(source)[2]
        self.focus=self.variables.index((35,3));self.object=self.variables.index((0,3))
        assert max(self.surfaces)==36
        assert all(self.surfaces[i]['type']in('STANDARD','EVENASPH')for i in range(1,36))
        op=ZOSAPI.Editors.MFE.MeritOperandType.INDX
        self.indices=np.array([float(system.MFE.GetOperandValue(op,i,1,0.,0.,0.,0.,0.,0.))for i in range(36)])
        assert abs(self.indices[0]-1.)<1e-12 and abs(self.indices[-1]-1.)<1e-12
        assert np.all((self.indices>=1.)&(self.indices<1.7))
        zero=np.zeros(85);l=self.internal_matrix(zero);do=self.initial[self.object];di=self.initial[self.focus]
        self.den0=l[1,0]*do+l[1,1];assert abs(self.den0)>.01
        self.B0=l[0,0]*do+l[0,1]+self.den0*di
        self.Bscale=self.den0*self.scales[self.focus]
        self.baseline_full_matrix=np.array([[1.,di],[0.,1.]])@l@np.array([[1.,do],[0.,1.]])
        assert abs(np.linalg.det(self.baseline_full_matrix)-1.)<1e-8
        assert abs(self.baseline_full_matrix[0,0]+10.)<.1
        self.T=np.column_stack([np.imag(self.to_native(1j*1e-20*np.eye(85)[k]))/1e-20 for k in range(85)])
        assert np.linalg.matrix_rank(self.T)==85 and abs(self.T[self.focus,self.focus]-1.)<1e-10
        self.zero_error=float(np.max(abs(self.to_native(zero))));assert self.zero_error<1e-8
        rng=np.random.default_rng(651);tests=rng.normal(size=(8,85))*.001
        self.roundtrip_error=max(float(np.max(abs(self.to_design(self.to_native(y))-y)))for y in tests)
        assert self.roundtrip_error<1e-8
        h=1e-4
        fd=np.column_stack([(self.to_native(h*np.eye(85)[k])-self.to_native(-h*np.eye(85)[k]))/(2*h)for k in range(85)])
        self.chain_error=float(np.max(abs(fd-self.T)))
        assert self.chain_error/max(1.,float(np.max(abs(self.T))))<1e-7

    def internal_matrix(self,y):
        y=np.asarray(y);v=self.initial+self.scales*y
        dtype=np.result_type(y,float);curv=np.array([self.surfaces[i]['curvature']for i in range(36)],dtype=dtype)
        d=np.array([self.surfaces[i]['thickness']for i in range(36)],dtype=dtype)
        for k,(sn,c)in enumerate(self.variables):
            if c==2:curv[sn]=v[k]
            elif c==3:d[sn]=v[k]
        for i in range(1,36):
            if self.surfaces[i]['type']=='EVENASPH':curv[i]+=2.*self.surfaces[i]['parameters'].get(1,0.)
        m=np.eye(2,dtype=dtype)
        for i in range(1,36):
            phi=(self.indices[i]-self.indices[i-1])*curv[i]
            m=np.array([[1.,0.],[-phi,1.]],dtype=dtype)@m
            if i<35:m=np.array([[1.,d[i]/self.indices[i]],[0.,1.]],dtype=dtype)@m
        return m

    def to_native(self,y):
        y=np.asarray(y);x=y.copy();l=self.internal_matrix(y);do=self.initial[self.object]+self.scales[self.object]*y[self.object]
        den=l[1,0]*do+l[1,1];assert abs(den)>.01
        target=self.B0+self.Bscale*y[self.focus]
        di=(target-l[0,0]*do-l[0,1])/den
        x[self.focus]=(di-self.initial[self.focus])/self.scales[self.focus]
        assert np.isfinite(x).all();return x

    def to_design(self,x):
        x=np.asarray(x);y=x.copy();l=self.internal_matrix(x)
        do=self.initial[self.object]+self.scales[self.object]*x[self.object]
        di=self.initial[self.focus]+self.scales[self.focus]*x[self.focus]
        b=l[0,0]*do+l[0,1]+(l[1,0]*do+l[1,1])*di
        y[self.focus]=(b-self.B0)/self.Bscale
        return y

    def proof(self):
        return dict(status='invertible_same_source_finite_gaussian_focus_chart_checked',
            full85_rank=85,source_full_matrix=self.baseline_full_matrix.tolist(),
            Gaussian_B0_mm=float(self.B0),Gaussian_B_scale_mm=float(self.Bscale),
            zero_normalized_error=self.zero_error,roundtrip_normalized_error=self.roundtrip_error,
            complex_step_chain_vs_centered_max_error=self.chain_error,
            matrix_determinant=float(np.linalg.det(self.baseline_full_matrix)),
            central_wavelength_only_defines_search_chart=True,
            every_other_original_physical_variable_unchanged=True,
            all_original_wavelengths_flags_and_actual_acceptance_unchanged=True,
            native_direction_QC_and_full_review_still_required=True,qualified=False)

    def chain(self,data):
        return {k:(v@self.T if k.startswith('J')and v.ndim>=2 and v.shape[-1]==85 else v.copy())for k,v in data.items()}
