"""Native polychromatic MTF curves for user judgment; never a design acceptance gate."""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import traceback
import numpy as np
from atomic_progress import read_json_retry as read,write_json_atomic as write
from run_uv355_multistart_campaign import sha
from uv355_verification_priority import process_identity
from verification_capacity import verification_slot
import run_uv355_direct_native_hard_geometry_R406_20261101 as method


def main(model,out):
    assert not out.exists();out.mkdir();digest=sha(model);mf_digest=sha(model.with_suffix('.MF'))
    state=dict(status='waiting_native_curve_measurement_seat',active=True,read_only=True,pid=os.getpid(),
               process_creation_identity=process_identity(os.getpid()),model=str(model),sha256=digest,
               MTF_hard_acceptance_requirement=False,FFT_checks_run=False,completed_points=0)
    def save():state['utc']=datetime.now(timezone.utc).isoformat();write(out/'progress.json',state)
    def active():assert not read(method.CHAT/'progress.json')['user_task_paused'] and not(out/'STOP_REQUEST').exists()
    session=read(method.CHAT/'progress.json');session['routes'].append(dict(state,root=str(out),progress=str(out/'progress.json'),role='native_MTF_curves_for_user',kind='readonly_MTF_curve_delivery'))
    write(method.CHAT/'progress.json',session);save();app=None
    try:
        with verification_slot():
            active();app,api,bridge=method.make_application();system=app.PrimarySystem
            system.LoadFile(str(model),False);op=api.Editors.MFE.MeritOperandType
            fields=[[float(system.SystemData.Fields.GetField(i).X),float(system.SystemData.Fields.GetField(i).Y)] for i in range(1,6)]
            assert fields==[[0.,0.],[0.,.5],[0.,1.],[0.,1.5],[0.,2.]]
            frequencies=np.arange(0.,351.,10.).tolist()
            points=[[f,freq,kind] for f in range(1,6) for freq in frequencies for kind in ('MTFT','MTFS')]
            report=dict(status='measuring',model=str(model),sha256=digest,fields=fields,frequencies_lp_mm=frequencies,
                        frequency_space='native_image_space',wave=0,polychromatic_original_five_channels=True,
                        points=points,sampling_rows=[],FFT_checks_run=False,MTF_used_for_acceptance=False,
                        user_visual_judgment_required=True)
            previous=None
            for sampling in (6,7,8):
                values=[];state.update(status='measuring_native_MTF_curves',sampling=sampling,completed_points=0);save()
                for i,(field,freq,kind) in enumerate(points):
                    active();v=float(system.MFE.GetOperandValue(getattr(op,kind),sampling,0,field,freq,0.,0.,0.,0.))
                    assert np.isfinite(v) and -1e-10<=v<=1.+1e-10
                    values.append(v)
                    if (i+1)%12==0:
                        state['completed_points']=i+1;save()
                        write(out/'PARTIAL_NATIVE_CURVES.json',dict(report,current_sampling=sampling,current_values=values))
                error=None if previous is None else float(np.max(abs(np.array(values)-previous)))
                report['sampling_rows'].append(dict(sampling=sampling,values=values,maximum_change_from_previous=error))
                if sampling>=7 and error<1e-4:
                    report.update(status='complete',validated_sampling=sampling,sampling_stable=True,values=values);break
                previous=np.array(values)
            if report['status']!='complete':
                report.update(status='sampling_requires_further_convergence_check',validated_sampling=8,sampling_stable=False,values=values)
            assert sha(model)==digest and sha(model.with_suffix('.MF'))==mf_digest
            write(out/'NATIVE_POLYCHROMATIC_MTF_CURVES.json',report)
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            fig,ax=plt.subplots(figsize=(10,6),layout='constrained')
            colors=plt.cm.viridis(np.linspace(.05,.9,5))
            for i,field in enumerate(fields,1):
                for kind,style in [('MTFT','-'),('MTFS','--')]:
                    selected=[v for pt,v in zip(points,report['values']) if pt[0]==i and pt[2]==kind]
                    ax.plot(frequencies,selected,style,color=colors[i-1],lw=1.6,label=f'Y={field[1]:g} mm {"T" if kind=="MTFT" else "S"}')
            ax.set(xlabel='Image-space spatial frequency (lp/mm)',ylabel='MTF',xlim=(0,350),ylim=(0,1.02),
                   title=f'UV355, 4 mm object field: native polychromatic MTF\n{digest[:12]} | sampling {report["validated_sampling"]} | for user judgment')
            ax.grid(alpha=.22);ax.legend(ncol=2,fontsize=8)
            fig.savefig(out/'POLYCHROMATIC_MTF.png',dpi=180);fig.savefig(out/'POLYCHROMATIC_MTF.svg');plt.close(fig)
            state.update(status=report['status'],sampling_stable=report['sampling_stable'],curve_json=str(out/'NATIVE_POLYCHROMATIC_MTF_CURVES.json'),
                         curve_png=str(out/'POLYCHROMATIC_MTF.png'),MTF_used_for_acceptance=False)
    except BaseException:state.update(status='native_curve_measurement_failure_preserved',error=traceback.format_exc());raise
    finally:
        if app is not None:app.CloseApplication()
        state['active']=False;save()
        session=read(method.CHAT/'progress.json')
        for r in session['routes']:
            if r.get('pid')==os.getpid() and r.get('process_creation_identity')==state['process_creation_identity']:r.update(active=False,status=state['status'])
        write(method.CHAT/'progress.json',session)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    main(a.model.resolve(),a.out.resolve())
