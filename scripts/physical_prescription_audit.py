"""Independent axisymmetric sag/solid checks using saved ZMX data.

Reuses the diameter-dependent thickness bands documented in the prior audit.
These sampled checks do not constitute manufacturing or assembly acceptance.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import numpy as np
from zos_probe import ROOT, SOURCE
from formal_optical_policy import limits as formal_limits,air_cap

def parse_model(path):
    raw = Path(path).read_bytes()
    text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    surfaces = {}
    for chunk in re.split(r"(?m)^SURF ", text)[1:]:
        sn = int(chunk.splitlines()[0])
        s = {"surface":sn,"curvature":0.,"conic":0.,"thickness":0.,"clear_radius":0.,"mechanical_radius":0.,"parameters":{}}
        for line in chunk.splitlines()[1:]:
            parts = line.split()
            if not parts:
                continue
            name = parts[0]
            if name in ("CURV","CONI","DISZ","DIAM","MEMA"):
                key = {"CURV":"curvature","CONI":"conic","DISZ":"thickness","DIAM":"clear_radius","MEMA":"mechanical_radius"}[name]
                s[key] = float(parts[1])
            elif name == "PARM":
                s["parameters"][int(parts[1])] = float(parts[2])
            elif name in ("TYPE","GLAS","COMM"):
                s[name.lower()] = " ".join(parts[1:])
        surfaces[sn] = s
    return raw,text,surfaces

def sag(s, radius):
    radius = np.asarray(radius)
    if s["surface"] in (1,2,3):
        radius = np.minimum(radius,s["clear_radius"]+0.25)
    c,k = s["curvature"],s["conic"]
    domain = 1.-(1.+k)*c*c*radius*radius
    if np.any(domain < -1e-12):
        raise ValueError(f"Invalid sag domain at surface {s['surface']}")
    value = c*radius*radius/(1.+np.sqrt(np.maximum(domain,0.)))
    if s.get("type") == "EVENASPH":
        for order, coefficient in s["parameters"].items():
            value = value+coefficient*radius**(2*order)
    return value

def audit(path, samples=2049, acceptance=None):
    acceptance=formal_limits() if acceptance is None else acceptance
    raw,text,surfaces = parse_model(path)
    previous = json.loads((ROOT / "results/uv355_new_design_20260911/447_same_mf_magnification_independent_audit/independent_audit.json").read_text(encoding="utf-8"))
    bands = sorted({x["source_band"]["maximum_diameter_mm"]:x["source_band"] for g in previous["physical"]["groups"] for x in g["lenses"]}.values(),key=lambda b:b["maximum_diameter_mm"])
    lenses = [s for s in surfaces.values() if s.get("glas")]
    z = {}; vertex = 0.
    for sn,s in surfaces.items():
        z[sn] = vertex
        vertex += s["thickness"]
    report = {"sha256":hashlib.sha256(raw).hexdigest(),"radial_samples":samples,"passed":True,"lenses":[],"gaps":[],"issues":[],"work_clearance_mm":float("inf"),"track_mm":z[max(surfaces)],"manufacturing_accepted":False,"formal_limits_at_audit":acceptance}
    radii = {}
    try:
        for front in lenses:
            rear = surfaces[front["surface"]+1]
            radius = max(front["clear_radius"],rear["clear_radius"],front["mechanical_radius"],rear["mechanical_radius"])
            radii[front["surface"]] = radius
            rr = np.linspace(0.,radius,samples)
            sf,sr = sag(front,rr),sag(rear,rr)
            thickness = front["thickness"]+sr-sf
            band = next((b for b in bands if 2*radius<=b["maximum_diameter_mm"]+1e-8),None)
            if band is None:
                report["issues"].append(f"Thickness band unavailable for S{front['surface']} diameter {2*radius}")
                emin = cmin = None
                okay = False
            else:
                severity = min(1.,float(max(np.max(np.abs(sf)),np.max(np.abs(sr)))/(0.2*radius)))
                emin = float(np.interp(severity,[0.,1.],band["edge_minimum_mm"]))
                cmin = float(np.interp(severity,[0.,1.],band["center_minimum_mm"]))
                okay = front["thickness"]>=cmin-1e-7 and float(thickness.min())>=emin-1e-7 and front["thickness"]<=30.+1e-7
            report["lenses"].append({"front":front["surface"],"radius_mm":radius,"center_mm":front["thickness"],"minimum_mm":float(thickness.min()),"edge_mm":float(thickness[-1]),"required_center_mm":cmin,"required_radial_min_mm":emin,"passed":bool(okay)})
            report["passed"] &= bool(okay)
            report["work_clearance_mm"] = min(report["work_clearance_mm"],float(z[front["surface"]]+sf.min()),float(z[rear["surface"]]+sr.min()))
        for left,right in zip(lenses,lenses[1:]):
            rear = surfaces[left["surface"]+1]
            left_radius,right_radius = radii[left["surface"]],radii[right["surface"]]
            rr = np.linspace(0.,min(left_radius,right_radius),samples)
            # Sum the local vertex separation directly. Subtracting two long
            # accumulated coordinates turned the exact fixed 0.2 mm S16 gap
            # into 0.19999999999998863 mm and a negative zero-gradient slack.
            gap = math.fsum(surfaces[sn]['thickness'] for sn in range(rear['surface'],right['surface']))
            net = gap+sag(right,rr)-sag(rear,rr)
            rim = float(gap+sag(right,right_radius)-sag(rear,left_radius))
            required = 0.2 if rear["surface"]==16 else 0.3
            okay = float(net.min())>=required-1e-7 and rim>=required-1e-7
            report["gaps"].append({"left_rear":rear["surface"],"right_front":right["surface"],"minimum_mm":float(net.min()),"rim_mm":rim,"required_mm":required,"passed":bool(okay)})
            report["passed"] &= bool(okay)
        if 1 in radii and 3 in radii:
            ring_start=max(surfaces[2]['clear_radius'],surfaces[3]['clear_radius'])+.25
            ring_end=min(radii[1],radii[3])
            width=ring_end-ring_start
            report['first_two_lens_common_contact_ring']={'inner_radius_mm':ring_start,'outer_radius_mm':ring_end,'width_mm':width,'required_width_mm':1.,'passed':bool(width>=1.-1e-7),'assembly_accepted':False}
            report['passed'] &= bool(width>=1.-1e-7)
        for sn,s in surfaces.items():
            if sn in (0,11,25,35,36) or s.get("glas"):
                continue
            cap = air_cap(sn,acceptance)
            if s["thickness"]>cap+1e-7 or s["thickness"]<0.:
                report["issues"].append(f"Air thickness cap violation S{sn}")
        for sn in (10,12):
            if surfaces[sn]["thickness"]<20.-1e-7:
                report["issues"].append(f"Fourier space short at S{sn}")
        if abs(surfaces[11]["thickness"]-4.)>1e-9 or abs(surfaces[16]["thickness"]-0.2)>1e-9:
            report["issues"].append("Fixed deck or near-contact gap changed")
        aspheres = [s for s in surfaces.values() if s.get("type")=="EVENASPH"]
        if len(lenses)>16 or len(aspheres)!=4 or any(s["surface"]>=26 for s in aspheres):
            report["issues"].append("Lens count/asphere distribution violation")
        for s in aspheres:
            if any(value!=0. for key,value in s["parameters"].items() if key>5):
                report["issues"].append(f"Order above A10 at S{s['surface']}")
        report["passed"] &= not report["issues"] and report["work_clearance_mm"]>4. and report["track_mm"]<=900.
    except Exception as exc:
        report["passed"] = False
        report["issues"].append(str(exc))
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",default=str(SOURCE))
    parser.add_argument("--output",required=True)
    args = parser.parse_args()
    result = audit(args.model)
    Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("lenses","gaps")},indent=2))
