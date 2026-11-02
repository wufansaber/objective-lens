"""Fresh native real-ray chromatic audit; independent focus calculation."""
import math
import numpy as np


def measure(system,ZOSAPI,trace,rings=32,arms=64):
    from chromatic_control import ZONES,FIELDS
    axial=[];direct_errors=[]
    for zone in ZONES:
        for w in (2,3):
            value=float(system.MFE.GetOperandValue(ZOSAPI.Editors.MFE.MeritOperandType.AXCL,1,w,zone,0.,0.,0.,0.,0.))
            axial.append(value*1000.)
            if zone>0.:
                p,d=trace(36,1,0.,0.,zone);q,e=trace(36,w,0.,0.,zone)
                if p is None or q is None:raise RuntimeError('Chromatic audit ray failure')
                direct_errors.append(abs(value-(-q[1]*e[2]/e[1]+p[1]*d[2]/d[1])))
    nodes,weights=np.polynomial.legendre.leggauss(rings)
    focus={};orthogonality={}
    for w in (1,2,3):
        rows=[]
        for node,weight in zip(nodes,weights):
            radius=math.sqrt((node+1.)/2.)
            for arm in range(arms):
                angle=2*math.pi*arm/arms
                p,d=trace(36,w,0.,radius*math.cos(angle),radius*math.sin(angle))
                if p is None:raise RuntimeError('Chromatic audit ray failure')
                rows.append((p[0],p[1],d[0]/d[2],d[1]/d[2],weight/(2*arms)))
        a=np.array(rows);x,y,u,v,weight=a.T
        xu=float(np.dot(weight,x*u)-np.dot(weight,x)*np.dot(weight,u))
        yv=float(np.dot(weight,y*v)-np.dot(weight,y)*np.dot(weight,v))
        variance=float(np.dot(weight,u*u+v*v)-np.dot(weight,u)**2-np.dot(weight,v)**2)
        focus[w]=-(xu+yv)/variance
        orthogonality[w]=abs(xu+yv+focus[w]*variance)
    lateral=[]
    for hy in FIELDS:
        center,_=trace(36,1,hy,0.,0.)
        for w in (2,3):
            end,_=trace(36,w,hy,0.,0.)
            if center is None or end is None:raise RuntimeError('Chromatic chief ray failure')
            lateral.append(float(np.linalg.norm(end[:2]-center[:2]))*1000.)
    offsets=[(focus[w]-focus[1])*1000. for w in (2,3)]
    score=float(np.mean([np.mean((np.asarray(axial)/20.)**2),
        np.mean((np.asarray(offsets)/20.)**2),np.mean((np.asarray(lateral)/.02)**2)]))
    return {'scope':'Soft chromatic targets, no chromatic acceptance tolerance introduced',
            'chromatic_score':score,
            'focus_definition':'Centroid RMS geometric best focus; independently computed covariance formula',
            'pupil_rings':rings,'pupil_arms':arms,'chromatic_axial_max_um':max(map(abs,axial)),
            'chromatic_best_focus_max_um':max(map(abs,offsets)),
            'chromatic_best_focus_endpoint_span_um':abs(offsets[1]-offsets[0]),
            'chromatic_lateral_max_um':max(lateral),'focus_offsets_mm':focus,
            'native_AXCL_vs_real_focus_max_error_mm':max(direct_errors),
            'focus_stationarity_residual':max(orthogonality.values()),
            'calculation_verified':max(direct_errors)<1e-8 and max(orthogonality.values())<1e-12}
