"""Native unchanged-MF multistage optical research, run until measured plateau."""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path
import numpy as np
from zos_probe import ROOT, INSTALL, SOURCE
from physical_prescription_audit import audit

def mf_signature(path):
    raw = Path(path).read_bytes()
    txt = raw.decode("utf-16" if raw.startswith((b"\xff\xfe",b"\xfe\xff")) else "utf-8-sig")
    return [(r.split()[0],*[float(t) for t in r.split()[1:11]]) for r in txt.splitlines()[1:] if r.strip()]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out",default=str(ROOT / "results/uv355_quality_until_stable_20261001"))
    parser.add_argument("--stable-batches",type=int,default=5)
    parser.add_argument("--restart-patience",type=int,default=4)
    parser.add_argument("--resume",action="store_true")
    parser.add_argument("--window",type=int,default=20)
    parser.add_argument("--resume-stage",default="all_dls")
    parser.add_argument("--seed-model")
    parser.add_argument("--project-image-guard",action="store_true")
    args = parser.parse_args()
    out = Path(args.out).resolve(); out.mkdir(parents=True,exist_ok=True)
    from pythonnet import load
    load("netfx")
    import clr
    clr.AddReference(str(INSTALL / "ZOSAPI_NetHelper.dll"))
    import ZOSAPI_NetHelper
    if not ZOSAPI_NetHelper.ZOSAPI_Initializer.Initialize(str(INSTALL)):
        raise RuntimeError("Initializer failed")
    clr.AddReference(str(INSTALL / "ZOSAPI_Interfaces.dll"))
    clr.AddReference(str(INSTALL / "ZOSAPI.dll"))
    import ZOSAPI
    app = ZOSAPI.ZOSAPI_Connection().CreateNewApplication()
    if app is None or not app.IsValidLicenseForAPI:
        raise RuntimeError("Valid API license required")
    system = app.PrimarySystem
    started = time.monotonic()
    report = {"status":"running","source_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),"final_design_accepted":False,
              "method":"unchanged native MF; native 10-cycle batches; alternate algorithms, variable groups and deterministic small restarts",
              "stability_thresholds":{"relative_merit":1e-7,"wavefront_absolute_waves":1e-7,"rms_over_airy_absolute":1e-5,"max_normalized_variable_change":1e-5,"consecutive_batches":args.stable_batches},
              "research_selection_policy":"physical and first-order guards; native-MF best and nonworsening-interface worst-wavefront best saved separately; neither is automatically accepted",
              "stages":[],"batches":[],"failures":[],"best_native":None,"best_wavefront":None}
    resumed = None
    if args.resume:
        report = json.loads((out / "progress.json").read_text(encoding="utf-8"))
        resumed = report["batches"][-1]["model"]
        report.setdefault("stop_policy_history",[]).append({"old":report["stability_thresholds"],"last_batch":len(report["batches"]),"reason":"Use an optical quality window rather than individual compensating coefficient drift"})
        report["status"] = "running"
        if report["stages"][-1]["status"] == "running":
            report["stages"][-1]["status"] = "continued_from_saved_checkpoint"
        report.setdefault("search_policy_history",[]).append({"batch":len(report["batches"]),"resume_stage":args.resume_stage,"OD_cycles_per_batch":1,"DLS_cycles_per_batch":10,"seed_model":args.seed_model,"project_image_guard":args.project_image_guard})
    report["stability_thresholds"] = {"window_batches":args.window,"merit_relative_range":1e-4,"wavefront_range_waves":1e-4,"rms_over_airy_range":.005,"coefficient_drift":"recorded, not a quality stop criterion"}
    prior_elapsed = report.get("elapsed_seconds",0.) if args.resume else 0.
    def write_status():
        report["elapsed_seconds"] = prior_elapsed+time.monotonic()-started
        (out / "progress.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    variable_desc = []
    signature = mf_signature(SOURCE.with_suffix(".MF"))
    best_native_path = out / "BEST_NATIVE_MF_RESEARCH.zmx"
    best_wave_path = out / "BEST_WAVEFRONT_RESEARCH.zmx"
    baseline = None
    batch_number = len(report["batches"]) if args.resume else 0
    rng = np.random.default_rng(20261001)
    def set_group(group):
        for sn,col in variable_desc:
            enabled = group == "all" or (group == "spherical" and col<9) or (group == "objective" and sn<26)
            cell = system.LDE.GetSurfaceAt(sn).GetCellAt(col)
            cell.MakeSolveVariable() if enabled else cell.MakeSolveFixed()
    def coordinates():
        values = []
        for sn,col in variable_desc:
            value = float(system.LDE.GetSurfaceAt(sn).GetCellAt(col).DoubleValue)
            if col == 2:
                value = 1./value if abs(value)>1e-15 and abs(value)<1e17 else 0.
            values.append(value)
        return np.array(values)
    def save(path):
        set_group("all")
        system.SaveAs(str(path))
        system.MFE.SaveMeritFunction(str(path.with_suffix(".MF")))
        if mf_signature(path.with_suffix(".MF")) != signature:
            raise RuntimeError("MF operands/parameters/targets/weights changed")
    def metrics():
        merit = float(system.MFE.CalculateMeritFunction())
        wfe,rms = [],[]
        waves = system.SystemData.Wavelengths
        if int(waves.NumberOfWavelengths)!=5 or int(system.SystemData.Fields.NumberOfFields)!=5:
            raise RuntimeError("Field or spectral channel count changed")
        spectrum = [(float(waves.GetWavelength(w).Wavelength),float(waves.GetWavelength(w).Weight)) for w in range(1,6)]
        expected = [(.355,1.),(.35499,.5),(.35501,.5),(.35499,.0625),(.35501,.0625)]
        if not np.allclose(np.array(spectrum),np.array(expected),rtol=0.,atol=1e-14):
            raise RuntimeError("Spectrum changed")
        for wave in range(1,6):
            for hy in np.linspace(0.,1.,9):
                wfe.append((wave,float(hy),float(system.MFE.GetOperandValue(ZOSAPI.Editors.MFE.MeritOperandType.RWCE,20,wave,0.,float(hy),0.,0.,0.,0.))))
                rms.append((wave,float(hy),float(system.MFE.GetOperandValue(ZOSAPI.Editors.MFE.MeritOperandType.RSCE,20,wave,0.,float(hy),0.,0.,0.,0.))))
        ray = system.Tools.OpenBatchRayTrace()
        failures=[]; sine=[]; divergence=[]; obj_angles=[]; img_angles=[]; nas={}; image_y={}
        def trace(sn,wave,hy,px,py):
            r = ray.SingleRayNormUnpol(ZOSAPI.Tools.RayTrace.RaysType.Real,sn,wave,0.,float(hy),float(px),float(py),False,0,0,*([0.]*11))
            if not r[0] or r[1] or r[2]:
                failures.append({"surface":sn,"wave":wave,"hy":float(hy),"px":float(px),"py":float(py),"error":int(r[1]),"vignette":int(r[2])})
                return None,None
            return np.array(r[3:6]),np.array(r[6:9])
        try:
            for wave in (1,2,3):
                for hy in (0.,0.5,1.):
                    _,chief = trace(10,wave,hy,0.,0.)
                    _,obj = trace(0,wave,hy,0.,0.)
                    pos,img = trace(36,wave,hy,0.,0.)
                    if pos is not None:
                        image_y[(wave,hy)] = float(pos[1])
                    for d,arr in ((obj,obj_angles),(img,img_angles)):
                        if d is not None:
                            arr.append(math.degrees(math.atan2(np.linalg.norm(d[:2]),d[2])))
                    for radius in (0.25,0.5,0.75,1.):
                        for arm in range(8):
                            px,py = radius*np.cos(arm*np.pi/4),radius*np.sin(arm*np.pi/4)
                            _,direction = trace(10,wave,hy,px,py)
                            _,last = trace(36,wave,hy,px,py)
                            if direction is not None and chief is not None:
                                divergence.append(math.atan2(np.linalg.norm(np.cross(direction,chief)),float(np.dot(direction,chief)))*1000.)
                            if hy==0.:
                                p,_ = trace(11,wave,hy,px,py)
                                _,incoming = trace(0,wave,hy,px,py)
                                if p is not None and incoming is not None:
                                    sine.append(float(np.linalg.norm(p[:2]-30.71792153*incoming[:2]))*1000.)
                                if last is not None:
                                    nas[wave] = max(nas.get(wave,0.),float(np.linalg.norm(last[:2])))
        finally:
            ray.Close()
        ratios = [spot/(.61*float(waves.GetWavelength(wave).Wavelength)*.001/nas.get({4:2,5:3}.get(wave,wave),1e-20)) for wave,hy,spot in rms]
        result = {"merit":merit,"worst_wfe":max(x[2] for x in wfe),"center_worst_wfe":max(x[2] for x in wfe if x[0]==1),
                  "axis_worst_wfe":max(x[2] for x in wfe if x[1]==0.),"worst_airy":max(ratios),
                  "objective_efl_mm":float(system.MFE.GetOperandAt(11).Value),
                  "sine_max_um":max(sine,default=1e6),"front_max_mrad":max(divergence,default=1e6),
                  "object_chief_max_deg":max(obj_angles,default=1e6),"image_chief_max_deg":max(img_angles,default=1e6),
                  "image_y_half":image_y.get((1,.5),1e6),"image_y_edge":image_y.get((1,1.),1e6),
                  "ray_failures":failures}
        return result
    def inspect(model, current):
        physical = audit(model)
        (model.with_suffix(".physical.json")).write_text(json.dumps(physical,indent=2),encoding="utf-8")
        current["physical_pass"] = bool(physical["passed"])
        current["work_clearance_mm"] = physical["work_clearance_mm"]
        current["track_mm"] = physical["track_mm"]
        current["first_order_guard"] = (abs(current["objective_efl_mm"]-50.)<=.1 and abs(current["image_y_half"]+7.5)<=.01 and abs(current["image_y_edge"]+15.)<=.01)
        eligible = current["physical_pass"] and current["first_order_guard"] and not current["ray_failures"] and current["worst_wfe"]<=.07 and current["axis_worst_wfe"]<=.04
        current["research_eligible"] = eligible
        improved = False
        if eligible and (report["best_native"] is None or current["merit"]<report["best_native"]["merit"]-1e-10):
            save(best_native_path)
            report["best_native"] = {**current,"model":str(best_native_path),"origin_model":str(model),"batch":batch_number}
            improved = True
        nonworsening = all(current[k]<=baseline[k]+eps for k,eps in (("sine_max_um",1e-6),("front_max_mrad",1e-8),("object_chief_max_deg",1e-9),("image_chief_max_deg",1e-9)))
        if eligible and nonworsening and current["merit"]<=baseline["merit"]*1.05 and (report["best_wavefront"] is None or current["worst_wfe"]<report["best_wavefront"]["worst_wfe"]-1e-8):
            save(best_wave_path)
            report["best_wavefront"] = {**current,"model":str(best_wave_path),"origin_model":str(model),"batch":batch_number}
            improved = True
        return improved
    def run_stage(label, algorithm="DLS", group="all", start_from=None, perturb=0.):
        nonlocal batch_number
        if start_from is not None:
            system.LoadFile(str(start_from),False)
        if perturb:
            set_group("all")
            for sn,col in variable_desc:
                cell = system.LDE.GetSurfaceAt(sn).GetCellAt(col)
                value = float(cell.DoubleValue)
                if col==3:
                    cell.DoubleValue = value+rng.normal(0.,perturb*10.)
                else:
                    cell.DoubleValue = value*(1.+rng.normal(0.,perturb))
        set_group(group)
        previous = metrics()
        last_coords = coordinates()
        stable = 0; stage_batches=0; window=[]
        stage = {"label":label,"algorithm":algorithm,"group":group,"perturb":perturb,"status":"running","start_batch":batch_number+1}
        report["stages"].append(stage); write_status()
        while True:
            set_group(group)
            opt = system.Tools.OpenLocalOptimization()
            try:
                opt.Algorithm = ZOSAPI.Tools.Optimization.OptimizationAlgorithm.DampedLeastSquares if algorithm=="DLS" else ZOSAPI.Tools.Optimization.OptimizationAlgorithm.OrthogonalDescent
                opt.Cycles = ZOSAPI.Tools.Optimization.OptimizationCycles.Fixed_10_Cycles if algorithm=="DLS" else ZOSAPI.Tools.Optimization.OptimizationCycles.Fixed_1_Cycle
                opt.RunAndWaitForCompletion()
            finally:
                opt.Close()
            projection = None
            if args.project_image_guard and group=="all" and algorithm=="DLS":
                system.MFE.CalculateMeritFunction()
                errors=[abs(float(system.MFE.GetOperandValue(ZOSAPI.Editors.MFE.MeritOperandType.REAY,36,1,0.,hy,0.,0.,0.,0.))+nominal) for hy,nominal in ((.5,7.5),(1.,15.))]
                # Correct only the observed small soft-boundary escape. Large
                # violations and all other constraints remain independently rejected.
                if .01<max(errors)<.0105 and abs(float(system.MFE.GetOperandAt(11).Value)-50.)<=.1:
                    from repair_image_guard import repair
                    projection=repair(system,ZOSAPI,out/'projected_image_guards',f'BATCH{batch_number+1:04d}',refocus=True,surfaces=[34])
                    (out/'projected_image_guards'/f'BATCH{batch_number+1:04d}_projection.json').write_text(json.dumps(projection,indent=2),encoding='utf-8')
            batch_number += 1; stage_batches += 1
            current = metrics()
            coords = coordinates()
            change = {"merit_relative":abs(current["merit"]-previous["merit"])/max(abs(previous["merit"]),1e-12),
                      "wfe_absolute":abs(current["worst_wfe"]-previous["worst_wfe"]),"airy_absolute":abs(current["worst_airy"]-previous["worst_airy"]),
                      "max_normalized_variable_change":float(np.max(np.abs(coords-last_coords)/np.maximum(np.abs(last_coords),1e-25)))}
            window.append(current)
            window = window[-args.window:]
            ranges = {"merit_relative_range":(max(v["merit"] for v in window)-min(v["merit"] for v in window))/max(abs(current["merit"]),1e-12),
                      "wavefront_range_waves":max(v["worst_wfe"] for v in window)-min(v["worst_wfe"] for v in window),
                      "rms_over_airy_range":max(v["worst_airy"] for v in window)-min(v["worst_airy"] for v in window)}
            settled = len(window)==args.window and ranges["merit_relative_range"]<1e-4 and ranges["wavefront_range_waves"]<1e-4 and ranges["rms_over_airy_range"]<.005
            stable = len(window) if settled else 0
            model = out / f"BATCH_{batch_number:04d}_{label}.zmx"
            save(model)
            improved = inspect(model,current)
            record = {"batch":batch_number,"stage":label,"cycles":10 if algorithm=="DLS" else 1,"stable_streak":stable,"change":change,"window_ranges":ranges,"model":str(model),**current,"best_improved":improved,"image_guard_projection":projection,"elapsed_seconds":prior_elapsed+time.monotonic()-started}
            report["batches"].append(record); write_status()
            print(json.dumps({k:record[k] for k in ("batch","stage","merit","worst_wfe","worst_airy","physical_pass","first_order_guard","stable_streak","best_improved")}),flush=True)
            previous,last_coords = current,coords
            if settled:
                stage["status"] = "stable"
                stage["final_window_ranges"] = ranges
                break
            if not math.isfinite(current["merit"]) or current["merit"]>baseline["merit"]*10000:
                stage["status"] = "invalid_branch_rejected"
                break
        stage["batches"] = stage_batches; stage["end_batch"] = batch_number
        stage["final_change"] = change
        set_group("all"); write_status()
    try:
        system.LoadFile(str(resumed or SOURCE),False)
        for sn in range(system.LDE.NumberOfSurfaces-1):
            for col in range(2,20):
                cell = system.LDE.GetSurfaceAt(sn).GetCellAt(col)
                if cell.Solve==ZOSAPI.Editors.SolveType.Variable:
                    variable_desc.append((sn,col))
        report["variable_count"] = len(variable_desc)
        if args.resume:
            baseline = report["baseline"]
        else:
            baseline = metrics(); report["baseline"] = baseline.copy()
            model = out / "BASELINE.zmx"; save(model); inspect(model,baseline)
        print("BASELINE "+json.dumps(baseline),flush=True)
        if args.seed_model:
            system.LoadFile(str(Path(args.seed_model).resolve()),False)
            seeded = metrics()
            inspect(Path(args.seed_model).resolve(),seeded)
            report["seed_candidate"] = seeded
            write_status()
        plan = [("all_dls","DLS","all"), ("orthogonal","OD","all"), ("release_after_od","DLS","all"), ("spherical","DLS","spherical"), ("release_after_spherical","DLS","all"), ("objective","DLS","objective"), ("release_after_objective","DLS","all")]
        labels = [p[0] for p in plan]+["restarts","final_polish"]
        if args.resume_stage not in labels:
            raise ValueError("Unknown resume stage")
        for label,algorithm,group in plan:
            if labels.index(label)<labels.index(args.resume_stage):
                continue
            start = resumed if args.resume and label==args.resume_stage and label=="orthogonal" else (best_native_path if label in ("orthogonal","release_after_od","spherical","objective") else None)
            run_stage(label,algorithm=algorithm,group=group,start_from=start)
        stale_restarts = 0; restart = 0
        report["restart_no_meaningful_improvement_streak"] = 0
        while stale_restarts<args.restart_patience:
            restart += 1
            before = (report["best_native"]["merit"],report["best_wavefront"]["worst_wfe"])
            run_stage(f"restart_{restart:02d}",start_from=best_native_path,perturb=0.00005*(1+(restart%3)))
            after = (report["best_native"]["merit"],report["best_wavefront"]["worst_wfe"])
            meaningful = before[0]-after[0]>max(1e-8,abs(before[0])*1e-6) or before[1]-after[1]>1e-7
            stale_restarts = 0 if meaningful else stale_restarts+1
            report["restart_no_meaningful_improvement_streak"] = stale_restarts
            write_status()
        run_stage("final_polish",start_from=best_native_path)
        report["status"] = "stable_in_tested_search"
        report["global_optimum_proven"] = False
    except BaseException as exc:
        report["status"] = "interrupted" if isinstance(exc,KeyboardInterrupt) else "error"
        report["failures"].append(str(exc))
        raise
    finally:
        app.CloseApplication(); write_status()
    print("COMPLETE "+json.dumps({"status":report["status"],"batches":batch_number,"best_native":report["best_native"],"best_wavefront":report["best_wavefront"]}),flush=True)

if __name__ == "__main__":
    main()
