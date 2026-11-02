"""Restore the existing image-height guard with a tiny single tube-curvature correction.

The native merit function is never edited. This creates research copies only.
"""
import argparse
import json
import math
from pathlib import Path
from scipy.optimize import brentq, minimize_scalar
from zos_probe import ROOT, INSTALL
from physical_prescription_audit import audit
from optimize_until_stable import mf_signature

def optical(system,ZOSAPI):
    result = {"merit":float(system.MFE.CalculateMeritFunction()),"efl_mm":float(system.MFE.GetOperandAt(11).Value)}
    values=[]
    for wave in range(1,6):
        for hy in (0.,.125,.25,.375,.5,.625,.75,.875,1.):
            w = float(system.MFE.GetOperandValue(ZOSAPI.Editors.MFE.MeritOperandType.RWCE,20,wave,0.,hy,0.,0.,0.,0.))
            values.append((wave,hy,w))
    result["worst_wfe"] = max(x[2] for x in values)
    result["axis_worst_wfe"] = max(x[2] for x in values if x[1]==0.)
    for hy,label in ((.5,"image_y_half"),(1.,"image_y_edge")):
        result[label] = float(system.MFE.GetOperandValue(ZOSAPI.Editors.MFE.MeritOperandType.REAY,36,1,0.,hy,0.,0.,0.,0.))
    return result

def repair(system,ZOSAPI,out,prefix,refocus=False,surfaces=None):
    out.mkdir(parents=True,exist_ok=True)
    initial = optical(system,ZOSAPI)
    baseline_path = out / (prefix+"_PRE_REPAIR.zmx")
    system.SaveAs(str(baseline_path))
    system.MFE.SaveMeritFunction(str(baseline_path.with_suffix(".MF")))
    signature = mf_signature(baseline_path.with_suffix(".MF"))
    log = {"initial":initial,"trials":[],"selection":None,"final_design_accepted":False}
    if abs(initial["image_y_half"]+7.5)<=.01 and abs(initial["image_y_edge"]+15.)<=.01:
        log["selection"] = {"model":str(baseline_path),**initial,"repair_needed":False}
        return log
    # Restore whichever original +/- 0.01 mm guard is violated. 0.00005 mm is
    # an internal numerical reserve, not a new user tolerance.
    hy,target_height = (.5,-7.5) if abs(initial["image_y_half"]+7.5)>.01 else (1.,-15.)
    label = "image_y_half" if hy==.5 else "image_y_edge"
    correction_target = target_height+math.copysign(.00995,initial[label]-target_height)
    for sn in (surfaces or range(35,25,-1)):
        system.LoadFile(str(baseline_path),False)
        cell = system.LDE.GetSurfaceAt(sn).RadiusCell
        if cell.Solve != ZOSAPI.Editors.SolveType.Variable:
            continue
        radius = float(cell.DoubleValue)
        c = 1./radius if abs(radius)<1e17 and abs(radius)>1e-16 else 0.
        focus_cell = system.LDE.GetSurfaceAt(35).ThicknessCell
        focus_initial = float(focus_cell.DoubleValue)
        if refocus and focus_cell.Solve != ZOSAPI.Editors.SolveType.Variable:
            raise RuntimeError("Refocus requires an existing image-distance variable")
        def residual(delta):
            cv = c+delta
            cell.DoubleValue = 1./cv if abs(cv)>1e-16 else 1e18
            if refocus:
                def focus_merit(offset):
                    focus_cell.DoubleValue = focus_initial+offset
                    return float(system.MFE.CalculateMeritFunction())
                optimum = minimize_scalar(focus_merit,bounds=(-.2,.2),method="bounded",options={"xatol":1e-8})
                focus_merit(float(optimum.x))
            return float(system.MFE.GetOperandValue(ZOSAPI.Editors.MFE.MeritOperandType.REAY,36,1,0.,hy,0.,0.,0.,0.))-correction_target
        step = 1e-9
        try:
            fa,fb = residual(-step),residual(step)
            while fa*fb>0. and step<1e-5:
                step *= 4.
                fa,fb = residual(-step),residual(step)
            if fa*fb>0.:
                log["trials"].append({"surface":sn,"error":"No local root bracket"})
                continue
            delta = brentq(residual,-step,step,xtol=1e-15,rtol=1e-12)
            residual(delta)
            current = optical(system,ZOSAPI)
            model = out / (prefix+f"_S{sn}_REPAIRED_RESEARCH.zmx")
            system.SaveAs(str(model)); system.MFE.SaveMeritFunction(str(model.with_suffix(".MF")))
            if mf_signature(model.with_suffix(".MF"))!=signature:
                raise RuntimeError("Native MF changed")
            physical = audit(model)
            (model.with_suffix(".physical.json")).write_text(json.dumps(physical,indent=2),encoding="utf-8")
            guarded = abs(current["image_y_half"]+7.5)<=.01 and abs(current["image_y_edge"]+15.)<=.01 and abs(current["efl_mm"]-50.)<=.1 and current["axis_worst_wfe"]<=.04 and physical["passed"]
            record = {"surface":sn,"curvature_delta_per_mm":delta,"refocus_offset_mm":float(focus_cell.DoubleValue)-focus_initial,"model":str(model),"guards_pass":bool(guarded),**current}
            log["trials"].append(record)
            if guarded and (log["selection"] is None or current["merit"]<log["selection"]["merit"]):
                log["selection"] = record
        except Exception as exc:
            log["trials"].append({"surface":sn,"error":str(exc)})
    if log["selection"] is not None:
        system.LoadFile(log["selection"]["model"],False)
    else:
        system.LoadFile(str(baseline_path),False)
    return log

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",required=True)
    parser.add_argument("--out-dir",required=True)
    parser.add_argument("--prefix",default="GUARD")
    parser.add_argument("--refocus",action="store_true")
    parser.add_argument("--surfaces",default=None)
    args = parser.parse_args()
    from pythonnet import load
    load("netfx")
    import clr
    clr.AddReference(str(INSTALL / "ZOSAPI_NetHelper.dll"))
    import ZOSAPI_NetHelper
    assert ZOSAPI_NetHelper.ZOSAPI_Initializer.Initialize(str(INSTALL))
    clr.AddReference(str(INSTALL / "ZOSAPI_Interfaces.dll")); clr.AddReference(str(INSTALL / "ZOSAPI.dll"))
    import ZOSAPI
    app = ZOSAPI.ZOSAPI_Connection().CreateNewApplication()
    try:
        if app is None or not app.IsValidLicenseForAPI:
            raise RuntimeError("Valid API license required")
        system = app.PrimarySystem
        system.LoadFile(str(Path(args.model).resolve()),False)
        surfaces = [int(s) for s in args.surfaces.split(",")] if args.surfaces else None
        if surfaces and any(s<26 or s>35 for s in surfaces):
            raise ValueError("Only existing spherical tube surfaces 26..35 are allowed")
        log = repair(system,ZOSAPI,Path(args.out_dir).resolve(),args.prefix,args.refocus,surfaces)
        (Path(args.out_dir) / (args.prefix+"_repair.json")).write_text(json.dumps(log,indent=2),encoding="utf-8")
        print(json.dumps(log,indent=2),flush=True)
    finally:
        if app is not None:
            app.CloseApplication()

if __name__ == "__main__":
    main()
