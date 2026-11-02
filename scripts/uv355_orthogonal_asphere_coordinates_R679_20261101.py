"""Invertible A4..A10 area-orthogonal sag coordinates on each clear aperture.

Let u=(r/R)^2. The four sag shapes are
u^2 * sqrt(2*j+5) * Jacobi(j,alpha=0,beta=4)(2*u-1), j=0..3.
Their area-weighted Gram matrix on the clear disk is the identity. These
coordinates introduce neither A2 nor powers above A10. Sag RMS is a search
unit, not an optical merit or a replacement for native WFE.
"""
import numpy as np
from numpy.polynomial import Polynomial
from scipy.special import jacobi
from physical_prescription_audit import parse_model
from uv355_gaussian_focus_coordinates_R651_20261101 import GaussianFocusCoordinates


class OrthogonalAsphereCoordinates:
    def __init__(self,source,scales,variables,sag_rms_mm=1e-4):
        self.scales=np.asarray(scales);self.variables=[tuple(v)for v in variables]
        self.sag_rms_mm=float(sag_rms_mm);self.M=np.eye(85);self.blocks=[]
        surfaces=parse_model(source)[2]
        polys=[]
        for degree in range(4):
            p=Polynomial(jacobi(degree,0,4).c[::-1])(Polynomial([-1.,2.]))
            polys.append(Polynomial([0.,0.,1.])*p*np.sqrt(2*degree+5.))
        nodes,weights=np.polynomial.legendre.leggauss(128);u=(nodes+1)/2.;weights=weights/2.
        q=np.column_stack([p(u)for p in polys]);gram=q.T@(weights[:,None]*q)
        self.gram_error=float(np.max(abs(gram-np.eye(4))));assert self.gram_error<1e-10
        for sn in (2,10,20,22):
            radius=float(surfaces[sn]['clear_radius']);assert radius>0 and surfaces[sn]['type']=='EVENASPH'
            cols=[self.variables.index((sn,c))for c in(13,14,15,16)]
            coefficients=np.column_stack([np.pad(p.coef,(0,6-len(p.coef)))[2:6]for p in polys])
            powers=np.array([4,6,8,10]);physical=self.sag_rms_mm*coefficients/radius**powers[:,None]
            block=physical/self.scales[cols,None];self.M[np.ix_(cols,cols)]=block
            self.blocks.append(dict(surface=sn,clear_radius_mm=radius,columns=cols,
                sag_RMS_search_unit_mm=self.sag_rms_mm,
                search_to_original_normalized_block=block.tolist(),
                physical_A4_A6_A8_A10_per_search_coordinate=physical.tolist()))
        self.inverse=np.linalg.inv(self.M);assert np.linalg.matrix_rank(self.M)==85
        self.inverse_error=float(np.max(abs(self.inverse@self.M-np.eye(85))))
        assert self.inverse_error<1e-10
        self.polys=polys

    def to_native(self,y):return self.M@np.asarray(y)
    def to_design(self,x):return self.inverse@np.asarray(x)
    def proof(self):
        return dict(status='exact_invertible_area_orthogonal_A4_A10_search_coordinates',
            basis='u^2 sqrt(2j+5) Jacobi(j,0,4)(2u-1),u=(r/R)^2,j=0..3',
            clear_disk_area_weighted_Gram_max_error=self.gram_error,
            inverse_product_max_error=self.inverse_error,rank=85,
            condition_number=float(np.linalg.cond(self.M)),blocks=self.blocks,
            A2_fixed_and_above_A10_zero_unchanged=True,conics_original_coordinates=True,
            optical_WFE_and_Airy_still_native_only=True,
            full_mechanical_radial_checks_still_required=True,
            sag_RMS_is_search_unit_not_acceptance=True)


class OrthogonalGaussianFocusCoordinates:
    def __init__(self,system,ZOSAPI,source,initial,scales,variables):
        self.gaussian=GaussianFocusCoordinates(system,ZOSAPI,source,initial,scales,variables)
        self.poly=OrthogonalAsphereCoordinates(source,scales,variables)
        self.T=self.gaussian.T@self.poly.M
        assert np.linalg.matrix_rank(self.T)==85
        rng=np.random.default_rng(679);trials=rng.normal(size=(8,85))*.001
        self.roundtrip_error=max(float(np.max(abs(self.to_design(self.to_native(y))-y)))for y in trials)
        assert self.roundtrip_error<1e-8
        h=1e-5
        fd=np.column_stack([(self.to_native(h*np.eye(85)[i])-self.to_native(-h*np.eye(85)[i]))/(2*h)for i in range(85)])
        self.chain_error=float(np.max(abs(fd-self.T)))
        assert self.chain_error/max(1.,float(np.max(abs(self.T))))<1e-7

    def __getattr__(self,name):return getattr(self.gaussian,name)
    def to_native(self,y):return self.gaussian.to_native(self.poly.to_native(y))
    def to_design(self,x):return self.poly.to_design(self.gaussian.to_design(x))
    def chain(self,data):
        return {k:(v@self.T if k.startswith('J')and v.ndim>=2 and v.shape[-1]==85 else v.copy())for k,v in data.items()}
    def proof(self):
        result=self.gaussian.proof()
        result.update(status='invertible_Gaussian_focus_and_orthogonal_asphere_chart_checked',
            every_other_original_physical_variable_unchanged=False,
            asphere_coordinate_proof=self.poly.proof(),full85_rank=85,
            composite_roundtrip_normalized_error=self.roundtrip_error,
            composite_chain_vs_centered_max_error=self.chain_error,
            all_original_physical_variables_and_acceptance_unchanged=True)
        return result
