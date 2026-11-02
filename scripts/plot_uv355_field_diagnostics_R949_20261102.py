"""Plot independently measured full-field WFE, Airy ratio and focal-surface metrics."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(review,out):
    data=json.loads(review.read_text(encoding='utf-8-sig'))
    assert data['status']=='complete' and data['field_count']==513
    fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True,layout='constrained')
    colors=['#2477b4','#d47a12','#2b9462'];waves=[2,1,3]
    names={1:'355.000 nm',2:'354.990 nm',3:'355.010 nm'};curves=[]
    for ax,key,rows,limit,title in [
        (axes[0,0],'wfe_waves',data['optical'],.055,'Worst RMS wavefront over pupils and azimuths'),
        (axes[0,1],'rms_over_airy',data['optical'],1.,'Worst RMS spot / Airy radius'),
        (axes[1,0],'field_curvature_object_um',data['focus_samples'],.493,'Object-space field curvature (absolute)'),
        (axes[1,1],'astigmatism_object_um',data['focus_samples'],.493,'Object-space T/S focal separation (absolute)')]:
        for wave,color in zip(waves,colors):
            samples=[r for r in rows if r['wave']==wave];radii=sorted({r['radius_normalized'] for r in samples})
            values=[max(abs(r[key]) for r in samples if r['radius_normalized']==radius) for radius in radii]
            ax.plot(np.array(radii)*2,values,label=names[wave],color=color,lw=1.6)
            curves.append(dict(metric=key,wave=wave,object_radius_mm=(np.array(radii)*2).tolist(),values=values))
        ax.axhline(limit,color='#be3344',ls='--',lw=1.3,label=f'Limit {limit:g}')
        ax.set_title(title,fontsize=10);ax.grid(alpha=.2);ax.legend(fontsize=7,loc='best')
    axes[0,0].set_ylabel('RMS wavefront (waves)');axes[0,1].set_ylabel('RMS / Airy')
    for ax in axes[1]:ax.set(xlabel='Object field radius (mm)',ylabel='Micrometres, object space')
    fig.suptitle(f'4 mm native field diagnostics | {data["sha256"][:12]} | R943 limits',fontsize=13)
    out.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(out.with_suffix('.png'),dpi=170);fig.savefig(out.with_suffix('.svg'));plt.close(fig)
    out.with_suffix('.json').write_text(json.dumps(dict(original_review=str(review),source_sha256=data['sha256'],curves=curves),indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--review',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.review.resolve(),a.out.resolve())
