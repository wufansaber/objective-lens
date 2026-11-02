"""Explicit soft chromatic controls authorized 2026-10-04; spectrum unchanged.

Scales are numerical normalization, never acceptance tolerances. AXCL is
checked against real-ray axial intercepts in the installed SDK before use.
"""
import numpy as np

AXIAL_SCALE_UM = 20.
LATERAL_SCALE_UM = .02
OBJECTIVE_WEIGHT = .05
# Canonicalize to the installed native MF writer's 13 significant digits.
ZONES = tuple(float(format(v,'.12e')) for v in (0., .25, .5, 2**-.5, 3**.5/2., 1.))
FIELDS = tuple(i/16. for i in range(1,17))


def merit_block(start):
    rows=[]
    def add(kind, params, weight=0.):
        rows.append((kind,*params,*([0.]*(8-len(params))),0.,weight))
        return start+len(rows)
    for zone in ZONES:
        for wave in (2,3):
            leaf=add('AXCL',[1.,float(wave),zone])
            add('PROB',[float(leaf),1.,1000./AXIAL_SCALE_UM],.2)
    for hy in FIELDS:
        center=add('REAY',[36.,1.,0.,hy,0.,0.])
        for wave in (2,3):
            end=add('REAY',[36.,float(wave),0.,hy,0.,0.])
            diff=add('DIFF',[float(end),float(center)])
            add('PROB',[float(diff),1.,1000./LATERAL_SCALE_UM],.2)
    return rows


def pupil(rings=8,arms=16):
    q,w=np.polynomial.legendre.leggauss(rings)
    return [(float(np.sqrt((a+1.)/2.)*np.cos(2*np.pi*j/arms)),
             float(np.sqrt((a+1.)/2.)*np.sin(2*np.pi*j/arms)),float(b/(2*arms)))
            for a,b in zip(q,w) for j in range(arms)]


def best_focus(rows):
    positions=np.array([p[:2] for p,d,w in rows]);directions=np.array([d for p,d,w in rows])
    weights=np.array([w for p,d,w in rows]);weights/=weights.sum()
    slopes=directions[:,:2]/directions[:,2,None]
    p=positions-np.sum(weights[:,None]*positions,axis=0)
    u=slopes-np.sum(weights[:,None]*slopes,axis=0)
    denominator=float(np.sum(weights[:,None]*u*u))
    if denominator<=1e-20:raise RuntimeError('Degenerate chromatic focus rays')
    return -float(np.sum(weights[:,None]*p*u))/denominator


def metrics(axial_mm, chief_positions, focus_mm):
    axial=np.array(axial_mm,dtype=float)*1000.
    lateral=np.array([np.asarray(chief_positions[(w,h)])[:2]-np.asarray(chief_positions[(1,h)])[:2]
                      for h in FIELDS for w in (2,3)])*1000.
    focus=np.array([focus_mm[w]-focus_mm[1] for w in (2,3)])*1000.
    components={'zonal_axial':float(np.mean((axial/AXIAL_SCALE_UM)**2)),
                'best_geometric_focus':float(np.mean((focus/AXIAL_SCALE_UM)**2)),
                'real_chief_lateral':float(np.mean(np.sum((lateral/LATERAL_SCALE_UM)**2,axis=1)))}
    score=float(np.mean(list(components.values())))
    return {'chromatic_score':score,'chromatic_objective_penalty':OBJECTIVE_WEIGHT*score,
            'chromatic_axial_max_um':float(np.max(np.abs(axial))),
            'chromatic_lateral_max_um':float(np.max(np.linalg.norm(lateral,axis=1))),
            'chromatic_best_focus_max_um':float(np.max(np.abs(focus))),
            'chromatic_best_focus_endpoint_span_um':abs(float(focus[1]-focus[0])),
            'chromatic_score_components':components,
            'chromatic_zonal_axial_um':axial.tolist(),'chromatic_lateral_xy_um':lateral.tolist(),
            'chromatic_best_focus_offsets_mm':{str(w):float(v) for w,v in focus_mm.items()}}


def policy():
    return {'enabled':True,'spectrum':'355.000 nm +/-10 pm; all original 5 channels and weights retained',
            'target':'Zero chromatic focus differences and real-chief image-height differences',
            'axial_zones':ZONES,'lateral_fields':FIELDS,'focus_pupil':{'rings':8,'arms':16,'radial_rule':'Gauss-Legendre in pupil radius squared'},
            'axial_scale_um':AXIAL_SCALE_UM,'lateral_scale_um':LATERAL_SCALE_UM,
            'objective_weight':OBJECTIVE_WEIGHT,'new_acceptance_limits':None,
            'scope':'Soft objective only. Full-field 0.05 waves, on-axis 0.04 waves and all existing inequalities remain hard. Focus means centroid RMS geometric best focus.'}
