"""Search objective only; original acceptance inequalities remain unchanged."""
import numpy as np


def family(label):
    if label.startswith('research_coordinate_trust_'): return 'research_coordinate_trust'
    if label.startswith('research_front_envelope_'): return 'research_front_envelope'
    if label.startswith('native_MTF_model_guard_'): return 'mtf'
    if label.startswith('axis_best'): return 'axis_balance'
    if 'WFE' in label: return 'wavefront'
    if 'RMS_Airy' in label: return 'spot'
    if label.startswith('field_depth'): return 'depth'
    if label in ('front', 'object_chief', 'image_chief') or label.startswith('front_ray_envelope_'): return 'angles'
    if label in ('EFL', 'half_image_height', 'edge_image_height', 'sine', 'mapping_maximum_nonregression'): return 'mapping'
    return 'entities'


def repair_cost(slacks, labels, wavefronts, penalty=2., axis_indices=None, axis_soft_weight=0.,family_weights=None):
    """Worst WFE plus mean WFE; per-family mean/max excess avoids row-count bias."""
    slacks = np.asarray(slacks, dtype=float)
    wavefronts = np.asarray(wavefronts, dtype=float)
    if not np.all(np.isfinite(slacks)) or not np.all(np.isfinite(wavefronts)):
        return 1e12
    value = float(np.max(wavefronts)**2 + .1*np.mean(wavefronts**2))
    if axis_soft_weight:
        if axis_indices is None:raise ValueError('Explicit axis rows required for axis soft objective')
        axial=np.maximum(wavefronts[np.asarray(axis_indices,dtype=int)]-1.,0.)
        value+=axis_soft_weight*float(np.mean(axial**2))
    groups = {}
    for label, slack in zip(labels, slacks):
        groups.setdefault(family(label), []).append(max(0., -float(slack)))
    for name,residuals in groups.items():
        residuals = np.asarray(residuals)
        weight=1. if family_weights is None else family_weights.get(name,1.)
        if not np.isfinite(weight) or weight<=0:raise ValueError('Invalid repair family weight')
        value += penalty*weight*float(np.mean(residuals**2) + np.max(residuals)**2)
    return value


def protected_indices(slacks):
    """Do not deliberately sacrifice already satisfied sampled inequalities."""
    return np.flatnonzero(np.asarray(slacks) >= 0.)
