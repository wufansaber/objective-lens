"""Batched equivalent native WFE/Airy, including explicit per-method axis order."""
import hashlib,math
from pathlib import Path
import numpy as np
from uv355_boundary_native_sampler_R492_20261101 import image_na
CONFIG=None


def configure(source,out,template):
    global CONFIG
    CONFIG=dict(source=Path(source),out=Path(out),template=Path(template),verified=set())


def guard_values(w,a,rows):
    return np.array([(w[r['point']]-w[r['axis_point']])/.05 if r['metric']=='axisWFE'
        else a[r['point']]-a[r['axis_point']]if r['metric']=='axisAiry'
        else 1.-w[r['point']]/r['limit']if r['metric']=='WFE'
        else 1.-a[r['point']]for r in rows])


def guard_jacobian(jw,ja,rows):
    return np.array([(jw[r['point']]-jw[r['axis_point']])/.05 if r['metric']=='axisWFE'
        else ja[r['point']]-ja[r['axis_point']]if r['metric']=='axisAiry'
        else -jw[r['point']]/r['limit']if r['metric']=='WFE'
        else -ja[r['point']]for r in rows])


def measure(system,ZOSAPI,bridge,points,na=None):
    assert CONFIG is not None
    c=CONFIG;key=hashlib.sha256(repr(points).encode()).hexdigest()[:20]
    path=c['out']/f'NATIVE_BATCH_BOUNDARY_{key}.MF'
    if not path.exists():
        lines=[c['source'].with_suffix('.MF').read_text(encoding='utf-16').splitlines()[0]]
        for p in points:
            angle=math.radians(p['azimuth_deg']);hx=p['radius_normalized']*math.sin(angle);hy=p['radius_normalized']*math.cos(angle)
            size=20 if p['method']=='GQ20'else int(p['method'][4:])
            for kind in(('RWCE','RSCE')if p['method']=='GQ20'else('RWRE','RSRE')):
                lines.append(f"{kind} {size} {p['wave']} {hx:.17g} {hy:.17g} 0 0 0 0 0 1 0")
        path.write_text('\n'.join(lines)+'\n',encoding='utf-16')
    try:
        system.MFE.LoadMeritFunction(str(path));system.MFE.CalculateMeritFunction()
        values=np.array([float(system.MFE.GetOperandAt(i+1).Value)for i in range(2*len(points))])
        assert np.isfinite(values).all()and min(values)>0.
        if key not in c['verified']:
            op=ZOSAPI.Editors.MFE.MeritOperandType
            for i in sorted({0,len(points)//2,len(points)-1}):
                p=points[i];angle=math.radians(p['azimuth_deg']);hx=p['radius_normalized']*math.sin(angle);hy=p['radius_normalized']*math.cos(angle)
                size=20 if p['method']=='GQ20'else int(p['method'][4:])
                operands=(op.RWCE,op.RSCE)if p['method']=='GQ20'else(op.RWRE,op.RSRE)
                direct=[float(system.MFE.GetOperandValue(kind,size,p['wave'],hx,hy,0.,0.,0.,0.))for kind in operands]
                assert np.max(abs(values[2*i:2*i+2]-direct))<1e-8
            c['verified'].add(key)
        if na is None:na=image_na(system,bridge)
        airy=np.array([v*na[p['wave']-1]/(.61*{1:.355,2:.35499,3:.35501}[p['wave']]*.001)for p,v in zip(points,values[1::2])])
        return values[::2],airy
    finally:
        system.MFE.LoadMeritFunction(str(c['template']));system.MFE.CalculateMeritFunction()
