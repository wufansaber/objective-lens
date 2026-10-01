# UV355 / NA 0.60 / 10× objective — research snapshot

This repository contains the current 3 mm-field research prescription and the development requirements. **It is not an accepted final optical design.** The next planned stage is a 4 mm full object field, but the 3 mm design has not yet passed all criteria.

## Files

- [Current development requirements](UV355_10x物镜_开发输入要求_2026-09-18.md) — the opening 2026-09-29 amendment supersedes older ±15/±30 pm spectrum text in the same document. The 30 pm laser linewidth is a separate stated engineering input, not a claim that it was measured as 20 pm.
- [Selected Zemax ZMX prescription](results/uv355_new_design_20260911/443_same_mf_magnification_homotopy/UV355_BEST_UNCHANGED_MF_MAGNIFICATION_GUARD.zmx) and [matching merit function](results/uv355_new_design_20260911/443_same_mf_magnification_homotopy/UV355_BEST_UNCHANGED_MF_MAGNIFICATION_GUARD.MF).
- [Optimization comparison and limitations](results/uv355_new_design_20260911/449_不改权重的结构搜索_2026-09-29.md).
- [Independent full-pupil audit](results/uv355_new_design_20260911/447_same_mf_magnification_independent_audit/independent_audit.json) and [same-prescription diffraction diagnostics](results/uv355_new_design_20260911/448_same_mf_magnification_psf_mtf/diffraction_diagnostic.json), with the 36 native PSF/MTF text exports in that directory.

The ZMX SHA-256 is `F68AB0B1D09BA1BA636484805183CCD20953F5F9EED1839828EF2E8A10D40425`. The five saved channels use 355.000/354.990/355.010/354.990/355.010 nm. The independently audited worst full-field RMS wavefront is 0.063188931 λ and the worst RMS/Airy ratio is 1.701906. NA 0.60, EFL 50.011463 mm, 4.444308 mm minimum working clearance, and the 3 mm-field image-height guard pass the sampled audit. The 0.02 λ optimization target, Airy-size requirement, original sine condition, front-group collimation, and double telecentricity **do not pass**. The 0.07 λ wavefront acceptance line alone must not be interpreted as overall acceptance.

Only the selected research snapshot and its verification data are included; historical unsuccessful branches and local license/configuration files are intentionally excluded.
