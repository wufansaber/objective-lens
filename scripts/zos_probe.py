"""Probe installed ZOS-API and load a research copy without altering the source."""
import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_pythonnet_spec = importlib.util.find_spec("pythonnet")
if (_pythonnet_spec is None or _pythonnet_spec.origin is None) and (ROOT / ".zos-dependencies").is_dir():
    sys.path.insert(0, str(ROOT / ".zos-dependencies"))
INSTALL = Path(r"C:\Program Files\Ansys Zemax OpticStudio 2022 R2.02")
SOURCE = ROOT / "results/uv355_new_design_20260911/443_same_mf_magnification_homotopy/UV355_BEST_UNCHANGED_MF_MAGNIFICATION_GUARD.zmx"
OUT = ROOT / "results/uv355_continue_20261001"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--load-model", action="store_true")
    parser.add_argument("--ray-check", action="store_true")
    parser.add_argument("--dls-batches", type=int, default=0)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"python": sys.executable, "version": sys.version,
              "installation": str(INSTALL), "final_design_accepted": False,
              "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
    app = None
    try:
        from pythonnet import load
        load("netfx")
        import clr
        clr.AddReference(str(INSTALL / "ZOSAPI_NetHelper.dll"))
        import ZOSAPI_NetHelper
        report["initialized"] = bool(ZOSAPI_NetHelper.ZOSAPI_Initializer.Initialize(str(INSTALL)))
        if not report["initialized"]:
            raise RuntimeError("ZOSAPI initializer failed")
        clr.AddReference(str(INSTALL / "ZOSAPI_Interfaces.dll"))
        clr.AddReference(str(INSTALL / "ZOSAPI.dll"))
        import ZOSAPI
        connection = ZOSAPI.ZOSAPI_Connection()
        connection.ConnectionTimeoutSeconds = 45
        print("Launching headless OpticStudio for license verification", flush=True)
        app = connection.CreateNewApplication()
        if app is None:
            report["initialization_progress"] = str(connection.IntializationProgress)
            raise RuntimeError("CreateNewApplication returned no application")
        report["license_status"] = str(app.LicenseStatus)
        report["api_license_valid"] = bool(app.IsValidLicenseForAPI)
        if not app.IsValidLicenseForAPI:
            report["initialization_error"] = str(app.InitializationErrorCode)
            raise RuntimeError("OpticStudio license does not permit ZOS-API")
        if args.load_model:
            copy = OUT / "BASELINE_RESEARCH.zmx"
            shutil.copy2(SOURCE, copy)
            shutil.copy2(SOURCE.with_suffix(".MF"), copy.with_suffix(".MF"))
            system = app.PrimarySystem
            system.LoadFile(str(copy), False)
            report["surfaces"] = int(system.LDE.NumberOfSurfaces)
            report["fields"] = int(system.SystemData.Fields.NumberOfFields)
            report["wavelengths"] = int(system.SystemData.Wavelengths.NumberOfWavelengths)
            report["merit"] = float(system.MFE.CalculateMeritFunction())
            report["model_loaded"] = True
            if args.dls_batches:
                report["dls_batches"] = []
                for batch in range(args.dls_batches):
                    opt = system.Tools.OpenLocalOptimization()
                    try:
                        opt.Algorithm = ZOSAPI.Tools.Optimization.OptimizationAlgorithm.DampedLeastSquares
                        opt.Cycles = ZOSAPI.Tools.Optimization.OptimizationCycles.Fixed_10_Cycles
                        opt.RunAndWaitForCompletion()
                    finally:
                        opt.Close()
                    value = float(system.MFE.CalculateMeritFunction())
                    model = OUT / f"NATIVE_DLS10_BATCH{batch+1}_RESEARCH.zmx"
                    system.SaveAs(str(model))
                    system.MFE.SaveMeritFunction(str(model.with_suffix(".MF")))
                    record = {"batch":batch+1,"cycles":10,"merit":value,"model":str(model),"final_design_accepted":False}
                    report["dls_batches"].append(record)
                    print(json.dumps(record),flush=True)
            if args.ray_check:
                ray = system.Tools.OpenBatchRayTrace()
                try:
                    report["ray_probe"] = {}
                    for surf in (0, 10, 11, 25, 36):
                        result = ray.SingleRayNormUnpol(ZOSAPI.Tools.RayTrace.RaysType.Real, surf, 1,
                                                       0., 0., 0., 1., False, 0, 0, *([0.] * 11))
                        report["ray_probe"][str(surf)] = list(result)
                    report["optimization_enums"] = {}
                    import System
                    for name in ("OptimizationCycles", "OptimizationAlgorithm"):
                        enum = getattr(ZOSAPI.Tools.Optimization, name)
                        report["optimization_enums"][name] = list(System.Enum.GetNames(enum))
                finally:
                    ray.Close()
        report["success"] = True
    except Exception as exc:
        report["success"] = False
        report["error"] = str(exc)
        report["traceback"] = traceback.format_exc()
    finally:
        if app is not None:
            try:
                app.CloseApplication()
            except Exception as exc:
                report["close_error"] = str(exc)
        (OUT / "zos_connection.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return 0 if report["success"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
