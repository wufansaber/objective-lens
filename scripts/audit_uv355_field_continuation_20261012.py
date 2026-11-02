"""Fresh circular field, dense focal surfaces and radial-entity audit; no FFT."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from atomic_progress import write_json_atomic
from audit_resource_lock import independent_audit_lock
from uv355_optimizer_capacity import optimizer_slot
from verification_capacity import verification_slot
from compiled_batch_bridge import trace_bridge
from chromatic_control import pupil
from field_continuation_policy_20261012 import invariants, radius as field_radius
from physical_prescription_audit import audit as physical_audit
from prepare_uv355_4mm_20261005 import DRAFT, SEED, sha
from zos_probe import INSTALL
from formal_optical_policy import limits as formal_limits,image_height_pass,image_height_limit


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',default=str(DRAFT));p.add_argument('--out',required=True)
    p.add_argument('--radial-count',type=int,default=17);p.add_argument('--azimuth-count',type=int,default=8)
    p.add_argument('--regular-verification-lane',action='store_true',help='Borrow one of the original three SDK optimizer leases for independent read-only verification')
    args=p.parse_args();model=Path(args.model).resolve();out=Path(args.out).resolve()
    out.mkdir(parents=True,exist_ok=True)
    if (out/'circle_audit.json').exists():raise RuntimeError('Preserve earlier audit; choose new folder')
    OBJECT_RADIUS=field_radius(model)
    acceptance=formal_limits()
    digest=sha(model);static=invariants(model);physical=physical_audit(model,2049)
    write_json_atomic(out/'invariants.json',static);write_json_atomic(out/'physical.json',physical)
    report={'model':str(model),'sha256':digest,'optimization_started':False,'FFT_checks_run':False,
        'object_circle_diameter_mm':2*OBJECT_RADIUS,'intermediate_field_only':OBJECT_RADIUS<2.,'full_4mm_design_accepted':False,'sampled_requirements_pass':False,'status':'initializing',
        'optical':[],'interfaces':[],'focus_samples':[],'ray_failure_count':0,'native_comparison_max_error':0.,
        'formal_optical_limits_at_launch':acceptance}
    def write():
        # Vector checks may produce numpy scalar bools; serialize their native values.
        plain=json.loads(json.dumps(report,default=lambda value:value.item()))
        write_json_atomic(out/'circle_audit.json',plain)
    write()
    from pythonnet import load
    load('netfx')
    import clr
    clr.AddReference(str(INSTALL/'ZOSAPI_NetHelper.dll'))
    import ZOSAPI_NetHelper
    assert ZOSAPI_NetHelper.ZOSAPI_Initializer.Initialize(str(INSTALL))
    clr.AddReference(str(INSTALL/'ZOSAPI_Interfaces.dll'));clr.AddReference(str(INSTALL/'ZOSAPI.dll'))
    import ZOSAPI
    dll=Path(__file__).with_name('CircularBatchTraceBridge.dll')
    clr.AddReference(str(dll))
    from ObjectiveLensCircularBridge import CircularBatchTraceBridge as bridge
    mesh=pupil(32,64)
    uniform=[(0.,0.)]+[(r*math.cos(a*2*math.pi/64),r*math.sin(a*2*math.pi/64))
        for r in np.linspace(1/32,1,32) for a in range(64)]
    image_pupil=sorted({(px,py) for px,py,wt in mesh}|set(uniform))
    indices={q:i for i,q in enumerate(image_pupil)}
    focus_ids=[indices[(px,py)] for px,py,wt in mesh]
    weights=np.array([wt for px,py,wt in mesh]);weights/=weights.sum()
    if args.radial_count<17 or args.azimuth_count<8:
        raise ValueError('Use at least 17 radii and 8 evenly spaced azimuths')
    fields=[(0.,0)]+[(i/(args.radial_count-1),angle) for i in range(1,args.radial_count)
                    for angle in (index*360./args.azimuth_count for index in range(args.azimuth_count))]
    report['field_count']=len(fields)
    app=ray=None
    with (optimizer_slot() if args.regular_verification_lane else verification_slot()):
        try:
            app=ZOSAPI.ZOSAPI_Connection().CreateNewApplication()
            assert app is not None and app.IsValidLicenseForAPI
            system=app.PrimarySystem
            def variables():return [(sn,c) for sn in range(system.LDE.NumberOfSurfaces-1) for c in range(2,20)
                if system.LDE.GetSurfaceAt(sn).GetCellAt(c).Solve==ZOSAPI.Editors.SolveType.Variable]
            system.LoadFile(str(SEED),False);original_variables=variables()
            system.LoadFile(str(model),False)
            assert variables()==original_variables and len(original_variables)==85
            if acceptance['policy_id']=='USER_RELAX_THREE_20261017':
                from optimize_until_stable import mf_signature
                native_mf=out/'SDK_EMBEDDED_MF_VERIFIED.MF'
                system.MFE.SaveMeritFunction(str(native_mf))
                assert mf_signature(native_mf)==mf_signature(model.with_suffix('.MF'))
                report['embedded_external_MF_equivalence_verified']=True
            report['variables_preserved']=True
            assert np.allclose([[float(system.SystemData.Fields.GetField(i).X),float(system.SystemData.Fields.GetField(i).Y)]
                    for i in range(1,6)],[[0.,OBJECT_RADIUS*i/4] for i in range(5)],rtol=0.,atol=1e-12)
            assert static['static_invariants_pass']
            system.MFE.CalculateMeritFunction()
            report['efl_mm']=float(system.MFE.GetOperandAt(11).Value)
            # Automatic apertures expand with the new field. Audit the refreshed envelope,
            # not stale semi-diameters saved in the preserved 3 mm source.
            evaluated=out/'SDK_EVALUATED_AUTO_APERTURES.zmx'
            system.SaveAs(str(evaluated));system.MFE.SaveMeritFunction(str(evaluated.with_suffix('.MF')))
            physical=physical_audit(evaluated,2049)
            physical['optical_source_sha256']=digest
            physical['evaluated_model']=str(evaluated)
            report['physical_evaluated_model']=str(evaluated)
            report['physical_evaluated_sha256']=sha(evaluated)
            write_json_atomic(out/'physical.json',physical)
            ray=system.Tools.OpenBatchRayTrace();report['status']='running';write()
            def native(s,w,hx,hy,px,py):
                r=ray.SingleRayNormUnpol(ZOSAPI.Tools.RayTrace.RaysType.Real,s,w,hx,hy,px,py,False,0,0,*([0.]*11))
                if not r[0] or r[1] or r[2]:
                    report['ray_failure_count']+=1
                    raise RuntimeError(f'Native ray failure: {s,w,hx,hy,px,py,r[1],r[2]}')
                return np.asarray(r[3:9])
            report['paraxial_magnifications']={str(w):float(native(36,w,0.,1e-5,0.,0.)[1]/(OBJECT_RADIUS*1e-5)) for w in (1,2,3)}
            image_na={};reference={};stationarity=[];quadratic_error=[]
            for fi,(radius,angle) in enumerate(fields):
                theta=math.radians(angle);radial=np.array([math.sin(theta),math.cos(theta)])
                sagittal=np.array([math.cos(theta),-math.sin(theta)])
                hx,hy=map(float,radius*radial)
                for w in range(1,6):
                    methods=[('GQ20','RWCE','RSCE',20)]
                    if w<=3:methods += [('RECT32','RWRE','RSRE',32),('RECT64','RWRE','RSRE',64)]
                    for name,wt,st,n in methods:
                        wfe=float(system.MFE.GetOperandValue(getattr(ZOSAPI.Editors.MFE.MeritOperandType,wt),n,w,hx,hy,0.,0.,0.,0.))
                        rms=float(system.MFE.GetOperandValue(getattr(ZOSAPI.Editors.MFE.MeritOperandType,st),n,w,hx,hy,0.,0.,0.,0.))
                        report['optical'].append({'method':name,'wave':w,'radius_normalized':radius,'azimuth_deg':angle,
                            'object_radius_mm':OBJECT_RADIUS*radius,'hx':hx,'hy':hy,'wfe_waves':wfe,'rms_spot_mm':rms})
                for w in (1,2,3):
                    requests=[(w,hx,hy,px,py) for px,py in image_pupil]
                    image=trace_bridge(bridge,ray,36,requests)
                    front=trace_bridge(bridge,ray,10,[(w,hx,hy,px,py) for px,py in uniform])
                    for index in (0,len(requests)//2,len(requests)-1):
                        _,xx,yy,px,py=requests[index]
                        error=float(np.max(np.abs(native(36,w,xx,yy,px,py)-image[index])))
                        report['native_comparison_max_error']=max(error,report['native_comparison_max_error'])
                    chief=image[indices[(0.,0.)]];incoming=native(0,w,hx,hy,0.,0.)
                    d=front[:,3:];chief_front=front[0,3:]
                    divergence=np.arctan2(np.linalg.norm(np.cross(d,chief_front),axis=1),d@chief_front)*1000.
                    if radius==0:
                        image_na[w]=float(np.max(np.linalg.norm(image[[indices[q] for q in uniform],3:5],axis=1)))
                    report['interfaces'].append({'wave':w,'radius_normalized':radius,'azimuth_deg':angle,
                        'front_max_mrad':float(np.max(divergence)),
                        'object_chief_deg':math.degrees(math.atan2(np.linalg.norm(incoming[3:5]),incoming[5])),
                        'image_chief_deg':math.degrees(math.atan2(np.linalg.norm(chief[3:5]),chief[5])),
                        'radial_image_height_mm':float(chief[:2]@radial)})
                    focal=image[focus_ids];positions=focal[:,:2];slopes=focal[:,3:5]/focal[:,5,None]
                    pair=[]
                    for direction in (sagittal,radial):
                        pos=positions@direction;slope=slopes@direction
                        pc=pos-weights@pos;sc=slope-weights@slope
                        covariance=float(weights@(pc*sc));variance=float(weights@(sc*sc))
                        if variance<=1e-20:raise RuntimeError('Degenerate focus variance')
                        z=-covariance/variance;pair.append(z)
                        stationarity.append(abs(covariance+z*variance))
                        step=.02
                        values=[float(weights@((pc+(z+delta)*sc)**2)) for delta in (-step,0.,step)]
                        quadratic_error.append(abs((values[0]-values[2])*step/(2*(values[0]-2*values[1]+values[2]))))
                    if radius==0:reference[w]=sum(pair)/2
                    c=(sum(pair)/2-reference[w])*1000.;a=(pair[1]-pair[0])*1000.
                    m2=report['paraxial_magnifications'][str(w)]**2
                    report['focus_samples'].append({'wave':w,'radius_normalized':radius,'azimuth_deg':angle,
                        'sagittal_offset_um':pair[0]*1000.,'tangential_offset_um':pair[1]*1000.,
                        'field_curvature_image_um':c,'astigmatism_image_um':a,
                        'field_curvature_object_um':c/m2,'astigmatism_object_um':a/m2,
                        'individual_shift_image_um':max(abs(z-reference[w])*1000. for z in pair),
                        'individual_shift_object_um':max(abs(z-reference[w])*1000./m2 for z in pair)})
                if fi%16==0 or fi==len(fields)-1:
                    report['fields_completed']=fi+1;write()
                    print(json.dumps({'fields_completed':fi+1,'total':len(fields),'outer_radius_mm':OBJECT_RADIUS*radius}),flush=True)
            sine=[]
            for w in (1,2,3):
                requests=[(w,0.,0.,px,py) for px,py in uniform]
                stop=trace_bridge(bridge,ray,11,requests);incoming=trace_bridge(bridge,ray,0,requests)
                sine.extend(np.linalg.norm(stop[:,:2]-30.71792153*incoming[:,3:5],axis=1)*1000.)
            report['image_na']=image_na
            for r in report['optical']:
                w={4:2,5:3}.get(r['wave'],r['wave'])
                lam=float(system.SystemData.Wavelengths.GetWavelength(r['wave']).Wavelength)
                r['rms_over_airy']=r['rms_spot_mm']/(.61*lam*.001/image_na[w])
            axis={(r['method'],r['wave']):r for r in report['optical'] if r['radius_normalized']==0.}
            axis_balance=all(r['wfe_waves']>=axis[(r['method'],r['wave'])]['wfe_waves'] and
                r['rms_over_airy']>=axis[(r['method'],r['wave'])]['rms_over_airy'] for r in report['optical'])
            f=report['focus_samples'];interfaces=report['interfaces'];samples=report['optical']
            finite=all(math.isfinite(r[k]) and r[k]>=0 for r in samples for k in ('wfe_waves','rms_over_airy'))
            depth_limits={w:float(system.SystemData.Wavelengths.GetWavelength(w).Wavelength)/(2*image_na[w]**2) for w in (1,2,3)}
            heights=[r for r in interfaces if r['wave']==1 and r['radius_normalized'] in (.5,1.)]
            from uv355_known_physical_gate_20261020 import assess_physical
            known_physical=assess_physical(physical)
            report['known_physical_entity_checks']=known_physical
            checks={'static_invariants':static['static_invariants_pass'],'physical_entities':physical['passed'],
                'quantifiable_physical_entities':known_physical['passed'],
                'variables':report['variables_preserved'],'field_coverage':len(samples)==len(fields)*11 and len(f)==len(fields)*3,
                'transport_verified':report['native_comparison_max_error']<1e-10,
                'focal_calculation_verified':max(stationarity)<1e-12 and max(quadratic_error)<1e-8,
                'finite_optical':finite,'worst_wavefront':all(r['wfe_waves']<=.05 for r in samples),
                'axis_wavefront':all(r['wfe_waves']<=.04 for r in axis.values()),
                'spot_airy':all(r['rms_over_airy']<=1 for r in samples),'axis_balance':axis_balance,
                'front_divergence':all(r['front_max_mrad']<=acceptance['front_divergence_limit_mrad'] for r in interfaces),
                'object_telecentric':all(r['object_chief_deg']<=acceptance['object_chief_angle_limit_deg'] for r in interfaces),
                'image_telecentric':all(r['image_chief_deg']<=acceptance['image_chief_angle_limit_deg'] for r in interfaces),
                'sine_error':max(sine)<=100.,'efl':49.9<=report['efl_mm']<=50.1,
                'image_heights':all(image_height_pass(r['radial_image_height_mm']+10*OBJECT_RADIUS*r['radius_normalized'],acceptance) for r in (interfaces if acceptance.get('policy_revision_id')=='USER_HEIGHT_LT15_20261018' else heights)),
                'object_depth':all(r['individual_shift_object_um']<=.493 for r in f),
                'image_depth':all(r['individual_shift_image_um']<=depth_limits[r['wave']] for r in f),
                'no_ray_failures':report['ray_failure_count']==0,'source_unchanged':sha(model)==digest}
            soft={'field_curvature_goal':all(abs(r['field_curvature_object_um'])<=.1 for r in f),
                  'astigmatism_goal':all(abs(r['astigmatism_object_um'])<=.2 for r in f)}
            report.update(status='complete',checks=checks,stage_goals=soft,
                sampled_requirements_pass=all(checks.values()),stage_goals_pass=all(soft.values()),
                summary={'wfe_worst_waves':max(r['wfe_waves'] for r in samples),
                    'axis_wfe_worst_waves':max(r['wfe_waves'] for r in axis.values()),
                    'rms_over_airy_worst':max(r['rms_over_airy'] for r in samples),
                    'field_curvature_image_um':max(abs(r['field_curvature_image_um']) for r in f),
                    'astigmatism_image_um':max(abs(r['astigmatism_image_um']) for r in f),
                    'field_curvature_object_um':max(abs(r['field_curvature_object_um']) for r in f),
                    'astigmatism_object_um':max(abs(r['astigmatism_object_um']) for r in f),
                    'max_individual_focus_shift_image_um':max(r['individual_shift_image_um'] for r in f),
                    'max_individual_focus_shift_object_um':max(r['individual_shift_object_um'] for r in f),
                    'front_divergence_mrad':max(r['front_max_mrad'] for r in interfaces),
                    'image_chief_angle_deg':max(r['image_chief_deg'] for r in interfaces),
                    'object_chief_angle_deg':max(r['object_chief_deg'] for r in interfaces),'sine_error_um':float(max(sine))},
                image_depth_limits_um=depth_limits,focus_stationarity_max=max(stationarity),
                shifted_ray_quadratic_error_max_mm=max(quadratic_error),
                scope=f'{len(fields)} sampled disk positions and dense pupils; no continuous-domain acceptance or search convergence claim.')
            write();print(json.dumps({'summary':report['summary'],'checks':checks,'stage_goals':soft},default=lambda value:value.item()),flush=True)
        except BaseException as exc:
            report.update(status='failed_requires_inspection',error=str(exc));write();raise
        finally:
            if ray is not None:ray.Close()
            if app is not None:app.CloseApplication()
            write()


if __name__=='__main__':main()
