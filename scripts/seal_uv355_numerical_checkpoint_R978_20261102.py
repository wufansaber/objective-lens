"""Seal a fully reviewed numerical design and exact-source visual MTF curves.

This is an incremental checkpoint for the existing workspace. It does not
declare original optimizer stopping evidence or manufacturing release.
"""
from datetime import datetime, timezone
from pathlib import Path
import io
import json
import shutil
import zipfile
import numpy as np
from atomic_progress import read_json_retry as read, write_json_atomic as write
from run_uv355_multistart_campaign import sha
from physical_prescription_audit import parse_model

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT/'results/uv355_near_axis_margin_R988_20261102'
REVIEW = ROOT/'results/uv355_near_axis_margin_review_R989_20261102'
EXTRA = ROOT/'results/uv355_final_margin_radial65_R990_20261102'
MTF = ROOT/'results/uv355_final_visual_MTF_R991_20261102'


def main():
    candidate = read(UP/'progress.json')['best_candidate']
    record = read(REVIEW/'CANDIDATE_01/FULL_R943_REVIEW.json')
    extra = read(EXTRA/'R943_ACCEPTANCE.json')
    extra.update(original_review=str(EXTRA/'CIRCLE1025/circle_audit.json'),
                 original_review_sha256=sha(EXTRA/'CIRCLE1025/circle_audit.json'))
    curves = read(MTF/'NATIVE_POLYCHROMATIC_MTF_CURVES.json')
    digest = record['sha256']
    model = Path(record['model'])
    assert sha(model) == digest == candidate['sha256'] == extra['source_sha256'] == curves['sha256']
    assessments = record['native_reviews'] + [extra]
    assert [r['field_count'] for r in assessments] == [129, 513, 1025]
    assert all(r['all_listed_numerical_checks_pass'] and not r['failed_numerical_checks'] for r in assessments)
    assert all(not r['MTF_used_for_acceptance'] for r in assessments)
    assert curves['status'] == 'complete' and curves['sampling_stable'] and curves['validated_sampling'] >= 7
    fine_axis_path=ROOT/'results/uv355_final_fine_axis_R992_20261102/NEAR_AXIS_ORDERING.json'
    fine_axis=read(fine_axis_path)
    assert fine_axis['sha256']==digest and fine_axis['strict_ordering_pass']
    assert record['coordinate_proof']['all8794_MF_rows_preserved']
    assert record['coordinate_proof']['saved_original85_normalized_error'] < 1e-7
    assert sha(record['policy']) == record['policy_sha256']
    native_paths = [Path(r['original_review']) for r in record['native_reviews']]
    native_paths.append(EXTRA/'CIRCLE1025/circle_audit.json')
    natives = [read(p) for p in native_paths]
    assert all(n['status'] == 'complete' and n['sha256'] == digest for n in natives)
    for assessment, path in zip(assessments, native_paths):
        if 'original_review_sha256' in assessment:
            assert sha(path) == assessment['original_review_sha256']
    interfaces = [row for n in natives for row in n['interfaces']]
    height = max(abs(r['radial_image_height_mm'] + 20*r['radius_normalized'])*1000 for r in interfaces)
    assert height < 15.
    physical = read(model.with_suffix('.physical.json'))
    assert physical['passed'] and not physical['manufacturing_accepted']
    summary = dict(
        status='sampled_numerical_design_checks_pass_MTF_user_judgment_pending',
        utc=datetime.now(timezone.utc).isoformat(), model=str(model), source_sha256=digest,
        policy=record['policy'], policy_sha256=record['policy_sha256'],
        field_grids=[129, 513, 1025], all_listed_numerical_checks_pass=True,
        summary=dict(wfe_worst_waves=max(r['wfe_worst_waves'] for r in assessments),
                     axis_wfe_worst_waves=max(r['axis_wfe_worst_waves'] for r in assessments),
                     rms_over_airy_worst=max(r['rms_over_airy_worst'] for r in assessments),
                     field_curvature_object_um=max(r['field_curvature_object_um'] for r in assessments),
                     astigmatism_object_um=max(r['astigmatism_object_um'] for r in assessments),
                     maximum_height_error_um=height,
                     front_divergence_mrad=max(r['front_max_mrad'] for r in interfaces),
                     object_chief_angle_deg=max(r['object_chief_deg'] for r in interfaces),
                     image_chief_angle_deg=max(r['image_chief_deg'] for r in interfaces),
                     sine_error_um=max(n['summary']['sine_error_um'] for n in natives),
                     efl_mm=natives[-1]['efl_mm'],
                     work_clearance_mm=physical['work_clearance_mm'], track_mm=physical['track_mm']),
        native_assessments=assessments, coordinate_proof=record['coordinate_proof'],
        MTF_curves=str(MTF/'NATIVE_POLYCHROMATIC_MTF_CURVES.json'),
        MTF_png=str(MTF/'POLYCHROMATIC_MTF.png'), MTF_used_for_acceptance=False,
        MTF_visual_judgment_pending=True, original_stopping_evidence_established=False,
        expanded_domain_and_color_stability_evidence_established=False,
        manufacturing_accepted=False, qualified=False, full_4mm_design_accepted=False,
        numerical_sampling_is_not_a_continuous_domain_proof=True,
        finite_corrections_not_counted_as_original_successful_interior_rounds=True,
        original_workspace_required_for_dependencies=True)
    folder = ROOT/'key_results/FOV_4p0mm'/f'R943_REVIEWED_{digest[:12]}'
    folder.mkdir(exist_ok=True)
    for source in [model, model.with_suffix('.MF'), model.with_suffix('.npz'), model.with_suffix('.physical.json')]:
        dest = folder/('prescription' + ''.join(source.suffixes))
        if dest.exists():
            assert sha(dest) == sha(source)
        else:
            shutil.copy2(source, dest)
    surfaces = parse_model(model)[2]
    prescription = []
    for number, surface in surfaces.items():
        row = dict(surface=number, type=surface.get('type'),
                   radius_mm=None if abs(surface['curvature']) < 1e-18 else 1./surface['curvature'],
                   thickness_mm=surface['thickness'], clear_diameter_mm=2*surface['clear_radius'],
                   mechanical_diameter_mm=2*surface['mechanical_radius'], conic=surface['conic'],
                   glass_record=surface.get('glas'), even_asphere_parameters=surface['parameters'])
        prescription.append(row)
    write(folder/'PRESCRIPTION_PARAMETERS.json', dict(model=str(model), source_sha256=digest,
          units='mm; even-asphere PARM i multiplies r^(2*i)', plane_radius_is_null=True, surfaces=prescription))
    for name in ['NATIVE_POLYCHROMATIC_MTF_CURVES.json', 'POLYCHROMATIC_MTF.png', 'POLYCHROMATIC_MTF.svg']:
        shutil.copy2(MTF/name, folder/name)
    write(folder/'RADIAL65_R943_ACCEPTANCE.json', extra)
    write(folder/'ACCEPTANCE_SUMMARY.json', summary)
    handoff = dict(status=summary['status'], model=str(model), source_sha256=digest,
                   policy=record['policy'], policy_sha256=record['policy_sha256'],
                   numerical_summary=str(folder/'ACCEPTANCE_SUMMARY.json'),
                   latest_verified_local_repair_profile=str(UP),
                   original85_squared_RMS_derivative_profile=str(ROOT/'results/uv355_refreshed_squared_model_R960_20261102'),
                   added_near_axis_derivative_profile=str(ROOT/'results/uv355_near_axis_design_R981_20261102'),
                   native_review_profiles=[str(REVIEW), str(EXTRA)], fine_axis_report=str(fine_axis_path),
                   exact_source_MTF_profile=str(MTF), user_task_paused=False,
                   next_action='User judges the delivered native MTF curves. Further automatic design needs an improvement objective from this verified prescription; do not rerun exhausted fixed-output repair scripts.',
                   continuation_constraints='Keep every geometric/interface/focal/ordering row unconditional; preserve original85/MF8794; no MTF objective or rejection gate; max3 optimizer SDK/max4 total.',
                   original_stopping_evidence_established=False, manufacturing_accepted=False,
                   qualified=False, full_4mm_design_accepted=False)
    write(folder/'VERIFIED_DESIGN_HANDOFF.json', handoff)
    s = summary['summary']
    report = (
        '# 4 mm设计数值检查结果\n\n'
        f'处方 SHA256：`{digest}`。物方视场直径4 mm，NA 0.60，名义倍率−10×。\n\n'
        '129、513、1025点原生复核均通过现行数值要求。MTF只提供曲线，由用户判断。\n\n'
        '[Zemax处方](prescription.zmx) · [原始评价函数](prescription.MF) · [处方参数](PRESCRIPTION_PARAMETERS.json)\n\n'
        '| 项目 | 复核最坏值 | 要求 |\n|---|---:|---:|\n'
        f"| RMS波前 | {s['wfe_worst_waves']:.9f} λ | ≤0.055 λ |\n"
        f"| 轴上RMS波前 | {s['axis_wfe_worst_waves']:.9f} λ | ≤0.04 λ |\n"
        f"| RMS/Airy | {s['rms_over_airy_worst']:.9f} | ≤1 |\n"
        f"| 物方场曲 | {s['field_curvature_object_um']:.6f} µm | ≤0.493 µm |\n"
        f"| 物方像散 | {s['astigmatism_object_um']:.6f} µm | ≤0.493 µm |\n"
        f"| 像高误差 | {s['maximum_height_error_um']:.6f} µm | <15 µm |\n"
        f"| 前组发散 | {s['front_divergence_mrad']:.9f} mrad | ≤1 mrad |\n"
        f"| 物方主光线角 | {s['object_chief_angle_deg']:.9f}° | ≤0.02° |\n"
        f"| 像方主光线角 | {s['image_chief_angle_deg']:.9f}° | ≤0.08° |\n"
        f"| 工作距离 | {s['work_clearance_mm']:.6f} mm | >4 mm |\n"
        f"| 总长 | {s['track_mm']:.9f} mm | ≤900 mm |\n\n"
        '85个原始变量及8794行评价函数保持一致，实体厚度和间隙检查通过。'
        '大口径厚度按用户授权推算规则检查。场曲按同波长轴上平均焦面为参考，'
        '像散为T/S焦面全间距，均使用实际波长倍率平方换算到物方。\n\n'
        '原始审计文件保留其历史0.05 λ检查结果；现行0.055 λ及场曲、像散要求的判定单独存放于'
        '[当前验收汇总](ACCEPTANCE_SUMMARY.json)，未覆盖历史原始数据。\n\n'
        f"MTF采用原五波长多色计算，采样{curves['validated_sampling']}稳定，频率为像方lp/mm。\n\n"
        '![MTF曲线](POLYCHROMATIC_MTF.png)\n\n'
        '![1025点场曲、像散及波前检查](FIELD_DIAGNOSTICS_1025.png)\n\n'
        '原始20轮成功内部迭代、4次无改善重启、扩大搜索域及色差稳定性证据尚未建立；'
        '本次有限修复不计作这些停止条件。制造公差、装调和最终放行尚未完成。'
        '采样通过不等于连续视场数学证明。\n\n'
        '继续设计应从本处方启动；保留全量几何约束，先验证基线，再进行有余量的优化。'
        '不得恢复MTF自动门槛或使用按正负号动态筛选几何约束的旧路线。\n')
    (folder/'DESIGN_RESULT.md').write_text(report, encoding='utf-8')
    record.update(additional_native_assessment=extra, all_listed_numerical_checks_pass=True,
                  numerical_checkpoint=str(folder/'ACCEPTANCE_SUMMARY.json'),
                  MTF_curves_for_user_judgment_still_to_be_delivered=False,
                  MTF_visual_judgment_pending=True, key_result_directory=str(folder))
    write(ROOT/'key_results/LATEST_R943_REVIEWED.json', record)
    write(ROOT/'key_results/LATEST_R943_NUMERICAL_CHECKPOINT.json', summary)
    write(ROOT/'key_results/LATEST_R943_VISUAL_MTF.json', dict(model=str(model), sha256=digest,
          curves=str(folder/'NATIVE_POLYCHROMATIC_MTF_CURVES.json'), plot=str(folder/'POLYCHROMATIC_MTF.png'),
          sampling_stable=True, validated_sampling=curves['validated_sampling'], MTF_used_for_acceptance=False))
    prep = read(UP/'preparation.json')
    selected = {Path(row['path']) for row in prep['pinned_files']}
    for profile in [UP, REVIEW, EXTRA, MTF, folder]:
        selected.update(p for p in profile.rglob('*') if p.is_file() and p.suffix.lower() in ('.json', '.npz', '.zmx', '.mf', '.png', '.svg', '.md'))
    fd = ROOT/'results/uv355_refreshed_squared_model_R960_20261102'
    selected.add(fd/'preparation.json')
    selected.add(fine_axis_path)
    for part in range(3):
        selected.update([fd/f'PART_{part}/BASELINE.npz', fd/f'PART_{part}/LABELS.json'])
    selected.update(ROOT/'scripts'/name for name in [
        'continue_uv355_unconditional_repair_R970_20261102.py', 'review_uv355_unconditional_repair_R971_20261102.py',
        'continue_uv355_height_margin_R974_20261102.py', 'review_uv355_height_margin_R975_20261102.py',
        'review_uv355_final_radial65_R977_20261102.py', 'seal_uv355_numerical_checkpoint_R978_20261102.py',
        'uv355_near_axis_runtime_R980_20261102.py', 'continue_uv355_near_axis_R981_20261102.py',
        'review_uv355_near_axis_R982_20261102.py', 'review_uv355_final_near_axis_radial65_R983_20261102.py',
        'probe_uv355_near_axis_R979_20261102.py', 'probe_uv355_fine_axis_R992_20261102.py',
        'continue_uv355_near_axis_margin_R988_20261102.py', 'review_uv355_near_axis_margin_R989_20261102.py',
        'review_uv355_final_margin_radial65_R990_20261102.py', 'sync_uv355_numerical_entry_pages_R987_20261102.py',
        'review_uv355_focal_design_R946_20261102.py', 'uv355_acceptance_revision_R943_20261102.py',
        'measure_uv355_visual_MTF_curves_R947_20261102.py', 'measure_uv355_key_visual_MTF_curves_R948_20261102.py',
        'plot_uv355_field_diagnostics_R949_20261102.py', 'plot_uv355_radial65_diagnostics_R994_20261102.py',
        'audit_uv355_extended_thickness_R352_20261031.py',
        'audit_uv355_field_continuation_20261012.py', 'CircularBatchTraceBridge.dll'])
    near_origin = ROOT/'results/uv355_near_axis_design_R981_20261102'
    selected.update([near_origin/'preparation.json', near_origin/'FRESH_ADDED_NEAR_AXIS_J85.npz'])
    near_seed = Path(read(near_origin/'preparation.json')['seed_model'])
    selected.update([near_seed, near_seed.with_suffix('.MF'), near_seed.with_suffix('.npz')])
    # Preserve the failed denser validation explaining the final height reserve.
    selected.add(ROOT/'results/uv355_radial65_confirmation_R973_20261102/R943_ACCEPTANCE.json')
    selected.update([ROOT/'key_results/LATEST_R943_REVIEWED.json', ROOT/'key_results/LATEST_R943_NUMERICAL_CHECKPOINT.json', ROOT/'key_results/LATEST_R943_VISUAL_MTF.json'])
    assert all(p.is_file() and p.is_relative_to(ROOT) for p in selected)
    export = ROOT/'exports'/f'UV355_4MM_NUMERICAL_CHECKPOINT_{digest[:12]}_20261102'
    assert not export.exists()
    export.mkdir()
    entries = [dict(path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(selected)]
    manifest = dict(status='incremental_numerical_design_checkpoint', source_sha256=digest, entries=entries,
                    standalone=False, required_base_checkpoint='exports/UV355_USER_PAUSE_20261102_084518/WORKSPACE_CHECKPOINT.zip',
                    original_base_sha256='fcfe76e15002c2d88b5a151fcbb5f02024eec8f9b4a54c790a801340bbb91bd3',
                    qualified=False, manufacturing_accepted=False)
    write(export/'MANIFEST.json', manifest)
    archive = export/'DESIGN_CHECKPOINT.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for row in entries:
            package.write(ROOT/row['path'], row['path'])
        package.write(export/'MANIFEST.json', 'MANIFEST.json')
    npz_count = 0
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None
        import hashlib
        for row in entries:
            blob = package.read(row['path'])
            assert len(blob) == row['bytes'] and hashlib.sha256(blob).hexdigest() == row['sha256']
            if row['path'].endswith('.npz'):
                with np.load(io.BytesIO(blob), allow_pickle=False) as arrays:
                    assert arrays.files
                    for name in arrays.files:
                        np.asarray(arrays[name])
                npz_count += 1
    receipt = dict(archive=str(archive), sha256=sha(archive), bytes=archive.stat().st_size,
                   entries=len(entries)+1, NPZ_files=npz_count, CRC_and_all_entry_hashes_verified=True,
                   source_sha256=digest, standalone=False)
    write(export/'ARCHIVE_VERIFICATION.json', receipt)
    write(folder/'ARCHIVE_VERIFICATION.json', receipt)
    summary['archive'] = receipt
    write(ROOT/'key_results/LATEST_R943_NUMERICAL_CHECKPOINT.json', summary)
    continuation = read(ROOT/'CONTINUATION.json')
    continuation.update(status=summary['status'], active=False, user_task_paused=False,
                        paused_by_user=False, current_native_batch_active=False,
                        authoritative_resume_handoff=dict(file=str(folder/'VERIFIED_DESIGN_HANDOFF.json'), sha256=sha(folder/'VERIFIED_DESIGN_HANDOFF.json')),
                        latest_compact_acceptance_record=str(folder/'ACCEPTANCE_SUMMARY.json'),
                        current_verified_fourmm_R943=summary, qualified=False,
                        full_4mm_design_accepted=False, updated_utc=summary['utc'])
    write(ROOT/'CONTINUATION.json', continuation)
    chat = ROOT/'results/uv355_chat_continuation_R4_20261025/progress.json'
    session = read(chat)
    session.update(status=summary['status'], active=False, user_task_paused=False,
                   current_native_batch_active=False, MTF_visual_judgment_pending=True,
                   qualified=False, full_4mm_design_accepted=False)
    write(chat, session)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
