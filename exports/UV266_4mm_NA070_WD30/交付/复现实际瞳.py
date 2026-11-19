"""Reproduce the three clipped object pupils using the frozen OptiWork document.

python retrace_channels.py --optiwork C:/path/to/optiwork --field 2 --channel CH0
Outputs one field's boundary in local direction cosines and its native ray throughput.
"""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np

def boundary(phi,field,ch,cfg):
    half=np.arcsin(cfg['object_na']);width=cfg['straight_cut_x_over_z']
    radius=cfg['front_sphere_radius_mm'];wd=cfg['working_vertex_distance_mm']
    wall=cfg['barrel_to_barrel_clearance_mm']/2+cfg['tip_wall_normal_mm']+cfg['optical_edge_reserve_normal_mm']
    cc,ss=np.cos(np.pi/8),np.sin(np.pi/8)
    lo=np.zeros_like(phi);hi=np.full_like(phi,half)
    a=np.radians({'CH0':0,'CH1':-45,'CH2':45}[ch])
    for _ in range(45):
        theta=(lo+hi)/2
        ux=np.sin(theta)*np.cos(phi);uy=np.sin(theta)*np.sin(phi);uz=np.cos(theta)
        B=(wd+radius)*uz-field*uy;C=wd*(wd+2*radius)+field**2
        distance=-C/(np.sqrt(B*B-C)-B)
        x=distance*ux;z=distance*uz
        into_seam=abs(x) if ch=='CH0' else x if ch=='CH1' else -x
        keep=(ss*z-cc*into_seam>=wall)&(into_seam<=width*z)
        keep&=np.cos(a)*uz-np.sin(a)*ux>=np.sqrt(1-cfg['common_global_na']**2)
        lo=np.where(keep,theta,lo);hi=np.where(keep,hi,theta)
    return np.c_[np.sin(lo)*np.cos(phi),np.sin(lo)*np.sin(phi),np.cos(lo)]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--optiwork',required=True,type=Path,help='OptiWork source directory that contains backend/ and desktop/')
    parser.add_argument('--field',type=float,default=0.,help='local line-field height in mm, 0 to 2')
    parser.add_argument('--channel',choices=['CH0','CH1','CH2'],default='CH0')
    parser.add_argument('--csv',type=Path,help='optional output of 360 real boundary rays')
    args=parser.parse_args()
    if not 0<=args.field<=2:parser.error('use 0 to 2 mm for the nonnegative half field')
    folder=Path(__file__).resolve().parent
    sys.path.insert(0,str(args.optiwork.resolve()))
    from desktop.project_io import read_project
    from backend.engine import make_system
    from backend.vendor.ai_zemax.standalone import trace
    pr=read_project(folder/'266nm_30mm_母处方.owx')
    pr['importSource']['externalCatalogPaths']=[str(folder/'CH0DUV.agf')]
    sy=make_system(pr);phi=np.deg2rad(np.arange(360))
    dirs=boundary(phi,args.field,args.channel,pr['channelAssembly']['first_cell'])
    org=np.zeros_like(dirs);org[:,1]=args.field
    rr=trace(sy.surfaces[sy.primary],org,dirs)
    if args.csv:
        with args.csv.open('w',encoding='utf-8-sig',newline='') as file:
            writer=csv.writer(file);writer.writerow(['azimuth_deg','kx_local','ky_local','kz_local','ray_passes'])
            writer.writerows([[k,*d,bool(v)] for k,(d,v) in enumerate(zip(dirs,rr.valid))])
    print(json.dumps({'channel':args.channel,'field_mm':args.field,'retained_boundary':len(dirs),
                      'reached_sensor':int(rr.valid.sum())},ensure_ascii=False))
    return int(not rr.valid.all())
if __name__=='__main__':raise SystemExit(main())
