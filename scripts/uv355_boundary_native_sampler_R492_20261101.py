"""Native WFE/Airy at additional physical-field samples, with the same dense NA."""
import math
import numpy as np
from compiled_batch_bridge import trace_bridge
def image_na(system,bridge):
    uniform=[(0.,0.)]+[(r*math.cos(k*2*math.pi/64),r*math.sin(k*2*math.pi/64))for r in np.linspace(1/32,1.,32)for k in range(64)]
    ray=system.Tools.OpenBatchRayTrace()
    try:axis=trace_bridge(bridge,ray,36,[(w,0.,0.,px,py)for w in(1,2,3)for px,py in uniform]).reshape(3,len(uniform),6)
    finally:ray.Close()
    return np.max(np.linalg.norm(axis[...,3:5],axis=-1),axis=1)
def measure(system,ZOSAPI,bridge,points,na=None):
    if na is None:na=image_na(system,bridge)
    op=ZOSAPI.Editors.MFE.MeritOperandType;wf=[];airy=[]
    for p in points:
        angle=math.radians(p['azimuth_deg']);hx=p['radius_normalized']*math.sin(angle);hy=p['radius_normalized']*math.cos(angle);size=20 if p['method']=='GQ20'else int(p['method'][4:]);w=p['wave']
        wf.append(float(system.MFE.GetOperandValue(op.RWCE if p['method']=='GQ20'else op.RWRE,size,w,hx,hy,0.,0.,0.,0.)));spot=float(system.MFE.GetOperandValue(op.RSCE if p['method']=='GQ20'else op.RSRE,size,w,hx,hy,0.,0.,0.,0.));airy.append(spot*na[w-1]/(.61*{1:.355,2:.35499,3:.35501}[w]*.001))
    return np.asarray(wf),np.asarray(airy)
