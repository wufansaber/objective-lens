"""Record the user-approved diagnostic MTF / hard focal-surface policy while paused.

Reassesses immutable native arrays without loading ZOS-API or changing prescriptions.
Legacy optimizer integration remains an explicit prerequisite for a later resume.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from atomic_progress import read_json_retry as read, write_json_atomic as write
from inspect_uv355_host_processes_20261020 import inventory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/uv355_user_MTF_visual_focal_policy_R943_20261102'
PARENT = ROOT / 'results/uv355_user_wfe055_policy_R942_20261102'
INSTRUCTION = 'MTF不做验收标准。我根据MTF曲线来判断。增加场曲和像散的要求'
FOCAL_REPLY = '采用现有焦深尺度：物方场曲≤0.493 µm、像散≤0.493 µm'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reassess(review, policy):
    """Use native finite-field data; MTF comparisons never enter this decision."""
    assert review['status'] == 'complete'
    optical, focal = review['optical'], review['focus_samples']
    assert len(focal) == review['field_count'] * 3
    assert {r['wave'] for r in focal} == {1, 2, 3}
    axes = {r['wave']: r for r in focal if r['radius_normalized'] == 0}
    assert len(axes) == 3
    curves, astig = [], []
    for row in focal:
        wave = row['wave']
        reference = (axes[wave]['sagittal_offset_um'] + axes[wave]['tangential_offset_um']) / 2
        m2 = float(review['paraxial_magnifications'][str(wave)]) ** 2
        assert m2 > 0
        curvature = ((row['sagittal_offset_um'] + row['tangential_offset_um']) / 2 - reference) / m2
        separation = (row['tangential_offset_um'] - row['sagittal_offset_um']) / m2
        assert all(math.isfinite(x) for x in (curvature, separation))
        assert abs(curvature - row['field_curvature_object_um']) < 1e-10
        assert abs(separation - row['astigmatism_object_um']) < 1e-10
        curves.append(abs(curvature)); astig.append(abs(separation))
    worst = max(r['wfe_waves'] for r in optical)
    axis = max(r['wfe_waves'] for r in optical if r['radius_normalized'] == 0)
    assert abs(worst - review['summary']['wfe_worst_waves']) < 1e-12
    checks = dict(review['checks'])
    checks.update(
        worst_wavefront=worst <= policy['full_field_rms_wfe_limit_waves'],
        axis_wavefront=axis <= policy['on_axis_rms_wfe_limit_waves'],
        field_curvature=max(curves) <= policy['field_curvature_object_limit_um'],
        astigmatism=max(astig) <= policy['astigmatism_object_limit_um'])
    return dict(source_sha256=review['sha256'], field_count=review['field_count'],
                focal_samples=len(focal), wfe_worst_waves=worst, axis_wfe_worst_waves=axis,
                rms_over_airy_worst=max(r['rms_over_airy'] for r in optical),
                field_curvature_object_um=max(curves), astigmatism_object_um=max(astig),
                field_curvature_limit_um=policy['field_curvature_object_limit_um'],
                astigmatism_limit_um=policy['astigmatism_object_limit_um'],
                checks=checks, failed_numerical_checks=[k for k, v in checks.items() if not v],
                all_listed_numerical_checks_pass=all(checks.values()),
                MTF_used_for_acceptance=False, qualified=False, full_4mm_design_accepted=False)


def main():
    continuation = read(ROOT / 'CONTINUATION.json')
    assert continuation['user_task_paused'] and not continuation['active']
    assert not OUT.exists(), 'New revision directory required; do not overwrite a saved revision'
    host = inventory()
    assert not any(p['name'].lower() == 'opticstudio.exe' for p in host['processes'])
    utc = datetime.now(timezone.utc).isoformat()
    parent = PARENT / 'formal_policy.json'
    policy = read(parent)
    policy.update(
        policy_id='USER_MTF_VISUAL_FOCAL_0493_20261102',
        policy_revision_id='USER_MTF_VISUAL_FOCAL_0493_20261102',
        source='User: ' + INSTRUCTION, revision_user_authorization=INSTRUCTION,
        focal_limit_user_authorization=FOCAL_REPLY, effective_date='2026-11-02', revision_utc=utc,
        parent_policy_file=str(parent), parent_policy_sha256=digest(parent),
        revised_fields=['MTF_acceptance_mode', 'field_curvature_object_limit_um', 'astigmatism_object_limit_um'],
        MTF_hard_acceptance_requirement=False, MTF_historical_anchor_comparison_required=False,
        MTF_source_nonregression_required=False, MTF_automatic_rejection_enabled=False,
        MTF_optimization_target_required=False, MTF_automatic_ranking_enabled=False,
        MTF_acceptance_mode='native_curves_for_user_visual_judgment',
        MTF_historical_measurements_preserved=True,
        field_curvature_object_limit_um=.493, astigmatism_object_limit_um=.493,
        field_curvature_hard_acceptance_requirement=True, astigmatism_hard_acceptance_requirement=True,
        focal_requirement_space='object', focal_inequality='maximum_absolute_value <= limit',
        field_curvature_definition='C_obj(h,w)=((zT(h,w)+zS(h,w))/2-(zT(0,w)+zS(0,w))/2)/m(w)^2',
        astigmatism_definition='A_obj(h,w)=(zT(h,w)-zS(h,w))/m(w)^2',
        focal_scope='All independently sampled physical 4mm fields, azimuths and three distinct wavelengths; 129/513 grids retained.',
        focal_method='Existing independently verified geometrical weighted-RMS T/S focus; not relabelled as paraxial Zemax field curvature.',
        existing_individual_ST_object_depth_limit_um=.493,
        existing_individual_ST_image_depth_requirement_unchanged=True,
        old_focal_soft_goals_not_hard_acceptance={'field_curvature_object_um': .1, 'astigmatism_object_um': .2},
        all_other_limits_unchanged=True)
    assert policy['full_field_rms_wfe_limit_waves'] == .055 and policy['on_axis_rms_wfe_limit_waves'] == .04

    selected = read(ROOT / 'key_results/ACTIVE_BEST.json')
    pending = read(ROOT / 'results/uv355_fa620_smaller_snapshot_review_R934_20261102/trial_progress.json')['reviews'][0]
    source_paths = [parent, PARENT / 'PAUSED_CONTINUATION.json']
    candidates = []
    for label, record in [('selected_canonical_Fa620', selected), ('complete_reviewed_pending_C628', pending)]:
        model = Path(record['model']); expected = record.get('source_sha256', record.get('sha256'))
        assert digest(model) == expected
        source_paths.extend([model, model.with_suffix('.MF'), Path(record['review'])])
        reviews = []
        for tag in ('CIRCLE129', 'EXTENDED513'):
            path = Path(record['review']).parents[1] / tag / 'circle_audit.json'
            native = read(path); assert native['sha256'] == expected
            result = reassess(native, policy)
            result.update(original_review=str(path), original_review_sha256=digest(path))
            source_paths.append(path); reviews.append(result)
        candidates.append(dict(label=label, model=str(model), sha256=expected, native_reviews=reviews))
    preserved = {str(p): digest(p) for p in source_paths}
    OUT.mkdir()
    write(OUT / 'formal_policy.json', policy)
    pointer = dict(file=str(OUT / 'formal_policy.json'), sha256=digest(OUT / 'formal_policy.json'),
                   effective_date='2026-11-02', full_field_rms_wfe_limit_waves=.055,
                   on_axis_rms_wfe_limit_waves=.04, MTF_hard_acceptance_requirement=False,
                   field_curvature_object_limit_um=.493, astigmatism_object_limit_um=.493,
                   all_other_limits_unchanged=True)
    reassessment = dict(status='offline_reassessment_of_immutable_native_arrays_under_user_revision', utc=utc,
                        policy=pointer, candidates=candidates, native_calculation_run=False,
                        optimization_started=False, user_task_paused=True,
                        MTF_manual_curve_judgment='reserved_for_user; no automatic numeric gate',
                        qualified=False, full_4mm_design_accepted=False)
    write(OUT / 'ACCEPTANCE_REASSESSMENT.json', reassessment)
    handoff = deepcopy(read(PARENT / 'PAUSED_CONTINUATION.json'))
    old_resume = handoff.pop('resume_plan')
    handoff.update(utc=utc, current_formal_policy=pointer, policy_revision_utc=utc,
                   policy_user_instruction=INSTRUCTION, focal_limit_user_reply=FOCAL_REPLY,
                   policy_reassessment=str(OUT / 'ACCEPTANCE_REASSESSMENT.json'),
                   previous_pause_handoff=str(PARENT / 'PAUSED_CONTINUATION.json'),
                   prior_policy_resume_plan_historical_only=old_resume,
                   MTF_historical_comparisons_are_diagnostic_only=True,
                   MTF_curve_delivery_for_user_judgment_pending=True,
                   latest_policy_overrides_legacy_thresholds_and_MTF_gates=True)
    handoff['acceptance'].update(all35_MTF_required=False, MTF_source_nonregression_required=False,
                                  MTF_automatic_rejection_enabled=False,
                                  field_curvature_object_limit_um=.493, astigmatism_object_limit_um=.493)
    handoff['failed_optical_checks'] = candidates[1]['native_reviews'][1]['failed_numerical_checks']
    handoff['resume_plan'] = [
        'Remain paused until explicit user resume. Do not run the active R552 writer or restart old output directories.',
        'Bind the R943 policy before any new runtime launch. Legacy controllers still enforce .05 WFE and MTF hard floors; they are NOT directly resumable. Runtime integration has not been completed by this offline policy save.',
        'Remove all35 historical MTF success, current-source MTF nonregression, native7 protected-floor feasibility repairs, MTF rank/count stopping gates, and mandatory MTF target penalties from new optimizer/selection/qualification paths. Preserve old data; deliver native MTF curves for user judgment, with numeric sampling convergence as measurement quality only.',
        'Use full WFE .055, axis .04, Airy1, hard object-space curvature .493 and astigmatism .493, plus every unchanged optical, geometry and individual T/S depth rule. Old curvature .1 / astigmatism .2 were only soft goals and must not become rejection gates.',
        'For each raw native focus sample calculate C=((zT+zS)/2-axis_mean)/m(w)^2 and A=(zT-zS)/m(w)^2. Add both signs of C/A guard rows and derivatives at .493; require full129/513 independent numerical reassessment. Image-to-object conversion uses the actual wavelength magnification squared, not a fixed 100.',
        'Rebuild cached off-axis WFE margins: g055=1-(.05/.055)*(1-g05), J055=(.05/.055)*J05. Keep axis .04 and ordering/research rows unchanged; rebuild newly feasible guards from raw native data.',
        'Canonical Fa620 and pending C628 stay distinct while paused. On resume reassess all candidates using R943; do not reject, rank or promote them using historical MTF pass counts.',
        'Preserve R936 four genuine C628 columns and queued zero-column R939. Reuse only after exact source/MF/T/variables/scales/sampling/step checks; rebuild policy-derived guards and new derivatives. Fa620 caches must never be relabelled as C628.',
        'Original stopping, expanded-domain, colour stability and manufacturing/assembly evidence remain required. Current C628 still fails WFE and Airy; no acceptance or convergence claim.'
    ]
    write(OUT / 'PAUSED_CONTINUATION.json', handoff)
    for relative in ('CONTINUATION.json', 'results/uv355_chat_continuation_R4_20261025/progress.json',
                     'results/uv355_chat_continuation_R4_20261025/CONTINUOUS_ACTIVE_HANDOFF_20261022.json',
                     'results/uv355_current_continuation_R552_20261101.json'):
        path = ROOT / relative; data = read(path)
        assert data['user_task_paused'] and not data['active']
        data.update(current_formal_policy=pointer, latest_policy_reassessment=str(OUT / 'ACCEPTANCE_REASSESSMENT.json'),
                    latest_compact_acceptance_record=str(OUT / 'PAUSED_CONTINUATION.json'),
                    authoritative_pause_handoff=str(OUT / 'PAUSED_CONTINUATION.json'),
                    latest_user_requirement=INSTRUCTION, focal_limit_user_reply=FOCAL_REPLY,
                    policy_updated_while_paused=True, active=False, user_task_paused=True, paused_by_user=True,
                    resume_requires_explicit_user_instruction=True, updated_utc=utc,
                    all_original_final_limits_and_original35_MTF_anchors_unchanged=False,
                    historical_MTF_arrays_unchanged_but_no_longer_acceptance=True,
                    acceptance_override_requires_new_runtime_integration=True)
        if 'next_actions' in data:
            data['previous_next_actions_historical_only'] = data['next_actions']
            data['next_actions'] = handoff['resume_plan']
        if 'next_work' in data:
            data['previous_next_work_historical_only'] = data['next_work']
            data['next_work'] = 'PAUSED. Follow R943 authoritative_pause_handoff; do not run historical controllers before policy integration.'
        if 'corrected_method' in data:
            data['corrected_method'].update(original_physical_and_optical_limits_unchanged=False,
                original_35_MTF_anchors_unchanged=True, MTF_hard_acceptance_requirement=False,
                formal_full_field_WFE_limit_waves=.055, formal_field_curvature_object_limit_um=.493,
                formal_astigmatism_object_limit_um=.493)
        write(path, data)
    for path, expected in preserved.items():
        assert digest(path) == expected
    write(OUT / 'POLICY_CHANGE_RECEIPT.json', dict(utc=utc, policy=pointer, user_instruction=INSTRUCTION,
          focal_limit_user_reply=FOCAL_REPLY, immutable_source_hashes=preserved,
          all_preserved_hashes_verified=True, native_calculation_run=False, optimization_started=False,
          native_count_observed=0, user_task_paused=True, legacy_runtime_integration_complete=False))
    print(json.dumps(dict(status='user_revision_saved_while_paused', policy=pointer,
                         pending_C628=candidates[1]['native_reviews'][1]), ensure_ascii=False))


if __name__ == '__main__':
    main()
