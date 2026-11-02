"""Preserve qualified 3 mm files and prepare a 4 mm field copy; never optimize."""
import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from optimize_until_stable import mf_signature
from physical_prescription_audit import parse_model
from zos_probe import INSTALL, ROOT
from formal_optical_policy import limits as formal_optical_limits

OUT = ROOT / 'results/uv355_4mm_preoptimization_20261005'
EXPORT = ROOT / 'exports/UV355_4MM_PREOPTIMIZATION_20261005'
PRESERVED = ROOT / 'exports/UV355_3MM_PRESERVED_20261005'
SEED = ROOT / 'exports/UV355_USER_STOP_20261004_1946/UV355_FIELD_ASTIG_BEST_USER_STOP_20261004.zmx'
DRAFT = EXPORT / 'UV355_4MM_UNOPTIMIZED.zmx'
CHANGES = {861: (-751., -1001.), 862: (-749., -999.),
           865: (-1501., -2001.), 866: (-1499., -1999.)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')


def prepare():
    assert sha(SEED) == '6efd3fee418ee94207a3cbb5ee9f134ff9f9a057589f5662872a950655ca86c8'
    for directory in (OUT, EXPORT, PRESERVED):
        directory.mkdir(parents=True, exist_ok=True)
    sources = [SEED.parent, ROOT / 'exports/uv355_field_astig_priority_1815/UV355_3MM_QUALIFIED_20261004_183615_001']
    preserved_files = []
    for index, source in enumerate(sources):
        destination = PRESERVED / ('SELECTED_BEST_3MM' if index == 0 else 'BALANCED_ALTERNATIVE_3MM')
        shutil.copytree(source, destination, dirs_exist_ok=True)
        for original in source.rglob('*'):
            if original.is_file():
                copied = destination / original.relative_to(source)
                assert sha(original) == sha(copied)
                preserved_files.append({'source': str(original), 'copy': str(copied), 'sha256': sha(original)})
    write_json(PRESERVED / 'preservation_receipt.json', {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'files': preserved_files, 'all_copies_byte_identical': True,
        'scope': 'Qualified 3 mm field results and their original independent evidence; no 4 mm acceptance claim.'})
    shutil.make_archive(str(PRESERVED), 'zip', PRESERVED)

    requirements = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'requirements_listed_before_optimization',
        'optimization_started': False, 'full_4mm_design_accepted': False,
        'field': {'object_circle_diameter_mm': 4., 'object_radius_mm': 2.,
                  'nominal_magnification': -10., 'nominal_image_circle_diameter_mm': 40.,
                  'object_radial_fields_mm': [0., .5, 1., 1.5, 2.],
                  'flat_object_and_common_fixed_image_plane': True},
        'spectrum': {'wavelengths_nm': [355., 354.99, 355.01, 354.99, 355.01],
                     'weights': [1., .5, .5, .0625, .0625], 'object_NA_air': .6},
        'hard_image_quality': {
            'worst_RMS_wavefront_waves_max': .05, 'axis_RMS_wavefront_waves_max': .04,
            'axis_not_worse_than_each_off_axis_sample_same_wave_and_pupil': True,
            'axis_balance_metrics': ['RMS_wavefront', 'RMS_spot_over_Airy_radius'],
            'RMS_spot_over_Airy_radius_max': 1.,
            'object_one_sided_depth_um': .493,
            'depth_scope': 'Each sagittal and tangential focus relative to same-wavelength axis mean focus; check both, not only their mean.',
            'image_depth': 'Use wavelength/(2*actual_image_NA**2); current 3 mm value about +/-49.1 um. Object/image conversion uses the actual longitudinal magnification; nominal air approximation |m|**2.'},
        'soft_goals_not_new_acceptance_limits': {
            'worst_RMS_wavefront_waves': .02,
            'object_max_abs_field_curvature_um': .10,
            'object_max_abs_T_minus_S_full_separation_um': .20,
            'nominal_image_equivalents_um': {'field_curvature': 10., 'astigmatism_full_separation': 20.},
            'field_curvature_definition': '(T+S)/2 minus same-wavelength axis mean focus',
            'astigmatism_definition': 'T-S full focal separation, not its half',
            'focus_definition': 'Finite-pupil centroid geometric RMS minimum focus; distinguish from paraxial Petzval curves.',
            'aggregation': 'Maximum absolute value across field and wavelengths; never replace the maximum by the average.'},
        'other_optical_hard_limits': {
            'front_divergence_mrad_max': .5, 'object_chief_angle_deg_max': formal_optical_limits()['object_chief_angle_limit_deg'],
            'image_chief_angle_deg_max': .05, 'sine_error_um_max': 100.,
            'sine_fixed_reference_a': 30.71792153, 'EFL_mm_range': [49.9, 50.1],
            'half_field_image_height_mm_range': [-10.01, -9.99],
            'edge_field_image_height_mm_range': [-20.01, -19.99]},
        'chromatic_policy': {'active_optimization_priority': False, 'direct_weight': 0.,
                             'native_MF_tie_break_weight': 0., 'existing_control_rows_retained': 44,
                             'new_chromatic_hard_tolerance': None, 'monitor_existing_band': True},
        'prescription_policy': {'original_85_variables_preserved': True,
                                'original_optical_and_radial_entity_constraints_retained': True,
                                'mechanical_constraints_remain_simplified': True,
                                'original_3mm_acceptance_authority_unchanged': True},
        'verification_plan': {'radial_positions': 17, 'azimuths_degrees': list(range(0,360,45)),
                              'unique_object_points': 129, 'wavefront_pupil_checks': ['original GQ', 'rectangular 32', 'rectangular 64'],
                              'real_focus_pupil': {'rings': 32, 'arms': 64},
                              'physical_radial_samples': 2049, 'ray_errors_or_unaccounted_clipping_allowed': False,
                              'FFT_checks': False,
                              'scope': 'Finite sampling is evidence for the sampled disk; add adaptive field/pupil checks near extrema before any complete-design acceptance claim.'},
        'execution_policy': 'Verify the unoptimized 4 mm baseline first. If hard requirements and stage field/astigmatism goals pass, preserve and stop without optimizing. A 0.02-wave soft goal alone does not compel optimization. Adapt 3 mm field-specific guards before using legacy controllers or reviewers.',
        'source_qualified_3mm_model': str(SEED), 'draft_4mm_model': str(DRAFT)}
    write_json(OUT / 'requirements.json', requirements)
    text = '''UV355：4 mm圆形物方视野——优化前像质要求（2026-10-05）

视野定义：直径4 mm、半径2 mm。名义倍率-10×，像方圆直径约40 mm。
物方NA=0.60，空气；355 nm±10 pm，保留原五通道及权重1、0.5、0.5、0.0625、0.0625。

硬性像质要求：
1. 在同一固定像面上，全视野最差RMS波前≤0.05λ，轴上≤0.04λ。
2. 同一波长、同一瞳采样下，轴上RMS波前和RMS/Airy均不得劣于任一轴外样点。
3. 全视野RMS几何斑半径/Airy半径≤1。
4. 物方单侧景深按±0.493 μm。分别检查子午、弧矢焦面相对同波长轴上平均焦面的位移，不能仅检查两者平均值。
   换到像方须用实际纵向倍率，并核对λ/(2NA像²)；当前像方单侧焦深约49.1 μm。

场曲、像散优化参考目标（不是新增硬性验收门槛）：
5. 最大绝对平均场曲≤0.10 μm（物方）；名义10×下像方约10 μm。
   场曲C=(T+S)/2－同波长轴上平均焦面。
6. 最大绝对子午－弧矢焦距差≤0.20 μm（物方）；名义10×下像方约20 μm。
   像散A=T－S，是完整焦面间距，不是半间距。
7. 以上均取全视野、全波段最大绝对值，采用有限瞳实光线质心RMS最佳焦面定义。
8. 0.02λ保留为波前优化目标，不能用它要求已经合格的结果继续优化。

其他原光学硬约束：
9. 前组发散角≤0.5 mrad；物方主光线角≤0.01°；像方主光线角≤0.05°。
10. 最差正弦误差≤100 μm；EFL=50±0.1 mm；保留原固定正弦参考。
11. 半视野物高1 mm对应像高-10±0.01 mm；边缘物高2 mm对应像高-20±0.01 mm。
12. 保留85个原变量、简化后的机械限制及完整径向实体硬约束。

色差：保留原±10 pm波段及44项控制行，当前只监测；色差主动目标权重和原生MF平局权重均为0，不添加新的色差硬阈值。
验证：17个径向位置×8个方位角，轴上合并后129个点；GQ及矩形32/64；实焦面32环64臂；实体径向2049点。
禁止FFT检查。有限采样通过不能直接声称连续4 mm圆域已经完整验收，应检查极值附近。

执行顺序：先验证4 mm未优化基线；硬要求与本阶段场曲/像散目标已满足则保存，不再优化。
本次只备份3 mm结果并准备4 mm初始文件；未启动优化，未宣称4 mm通过。
原3 mm复核脚本含1.5 mm边界及旧像高，使用前必须按4 mm阶段适配，不能直接复用为4 mm验收。
'''
    (OUT / '像质要求.txt').write_text(text, encoding='utf-8-sig')
    shutil.copy2(OUT / '像质要求.txt', EXPORT / '像质要求.txt')
    shutil.copy2(OUT / 'requirements.json', EXPORT / 'requirements.json')

    raw = SEED.read_bytes()
    encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    source_text = raw.decode(encoding)
    draft_text = source_text.replace('YFLN 0 0.375 0.75 1.125 1.5\r\n', 'YFLN 0 0.5 1 1.5 2\r\n')
    assert draft_text != source_text
    source_mf = SEED.with_suffix('.MF')
    mf_raw = source_mf.read_bytes()
    mf_encoding = 'utf-16' if mf_raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    mf_lines = mf_raw.decode(mf_encoding).splitlines(keepends=True)
    sig = mf_signature(source_mf)
    row_line_indices = [i for i, line in enumerate(mf_lines) if i > 0 and line.strip()]
    for row, (old_target, new_target) in CHANGES.items():
        operand = sig[row-1]
        assert operand[9] == old_target
        old_embedded = f'{operand[0]} {int(operand[1])} 0 0 0 0 0 {int(old_target)} 0.5 0 0'
        new_embedded = old_embedded.replace(f' {int(old_target)} ', f' {int(new_target)} ')
        assert draft_text.splitlines().count(old_embedded) == 1
        draft_text = draft_text.replace(old_embedded+'\r\n', new_embedded+'\r\n')
        index = row_line_indices[row-1]
        line = mf_lines[index]
        tokens = list(re.finditer(r'\S+', line))
        assert float(tokens[9].group()) == old_target
        mf_lines[index] = line[:tokens[9].start()] + f'{new_target:.12E}' + line[tokens[9].end():]
    DRAFT.write_bytes(draft_text.encode(encoding))
    DRAFT.with_suffix('.MF').write_bytes(''.join(mf_lines).encode(mf_encoding))
    # Reverse the authorized changes to prove every other model byte/text record is unchanged.
    reversed_text = draft_text.replace('YFLN 0 0.5 1 1.5 2\r\n', 'YFLN 0 0.375 0.75 1.125 1.5\r\n')
    for row, (old_target,new_target) in CHANGES.items():
        operand=sig[row-1]
        old=f'{operand[0]} {int(operand[1])} 0 0 0 0 0 {int(old_target)} 0.5 0 0'
        new=old.replace(f' {int(old_target)} ',f' {int(new_target)} ')
        reversed_text=reversed_text.replace(new+'\r\n',old+'\r\n')
    assert reversed_text == source_text
    new_sig = mf_signature(DRAFT.with_suffix('.MF'))
    assert len(new_sig) == len(sig) == 8794
    assert [i+1 for i,(a,b) in enumerate(zip(sig,new_sig)) if a != b] == list(CHANGES)
    for i,(a,b) in enumerate(zip(sig,new_sig),1):
        assert a[:9] == b[:9] and a[10:] == b[10:]
        if i not in CHANGES: assert a == b
    assert parse_model(SEED)[2] == parse_model(DRAFT)[2]
    receipt = {'created_utc': datetime.now(timezone.utc).isoformat(),
        'source': str(SEED), 'source_sha256': sha(SEED), 'source_MF_sha256': sha(source_mf),
        'draft': str(DRAFT), 'draft_sha256': sha(DRAFT), 'draft_MF_sha256': sha(DRAFT.with_suffix('.MF')),
        'only_authorized_ZMX_changes': ['YFLN radial object fields', 'four embedded half/edge magnification targets'],
        'MF_target_changes': CHANGES, 'MF_operand_count': len(sig),
        'all_other_ZMX_records_unchanged': True, 'all_other_MF_operands_unchanged': True,
        'physical_prescription_unchanged': True, 'source_unchanged': True,
        'cached_MF_values_are_3mm_and_not_4mm_evidence': True,
        'optimization_started': False, 'FFT_checks_run': False, 'full_4mm_design_accepted': False,
        'status': 'prepared_unoptimized_pending_SDK_load_and_4mm_optical_verification'}
    write_json(OUT / 'preparation_receipt.json', receipt)
    write_json(EXPORT / 'preparation_receipt.json', receipt)
    print(json.dumps({'draft':str(DRAFT),'requirements':str(OUT/'像质要求.txt'),
        'preservation_zip':str(PRESERVED.with_suffix('.zip')), 'optimization_started':False},ensure_ascii=False),flush=True)


def sdk_verify():
    from pythonnet import load
    load('netfx')
    import clr
    clr.AddReference(str(INSTALL/'ZOSAPI_NetHelper.dll'))
    import ZOSAPI_NetHelper
    assert ZOSAPI_NetHelper.ZOSAPI_Initializer.Initialize(str(INSTALL))
    clr.AddReference(str(INSTALL/'ZOSAPI_Interfaces.dll'))
    clr.AddReference(str(INSTALL/'ZOSAPI.dll'))
    import ZOSAPI
    app = None
    receipt = {'optimization_started':False,'FFT_checks_run':False,'full_4mm_design_accepted':False}
    before_hashes={str(p):sha(p) for p in (SEED,SEED.with_suffix('.MF'),DRAFT,DRAFT.with_suffix('.MF'))}
    try:
        connection=ZOSAPI.ZOSAPI_Connection()
        connection.ConnectionTimeoutSeconds=45
        print('Loading preserved source and 4 mm draft for read-only SDK verification',flush=True)
        app=connection.CreateNewApplication()
        assert app is not None and app.IsValidLicenseForAPI
        system=app.PrimarySystem
        def snapshot(model):
            system.LoadFile(str(model),False)
            variables=[(sn,col) for sn in range(system.LDE.NumberOfSurfaces-1)
                       for col in range(2,20)
                       if system.LDE.GetSurfaceAt(sn).GetCellAt(col).Solve == ZOSAPI.Editors.SolveType.Variable]
            fields=system.SystemData.Fields
            waves=system.SystemData.Wavelengths
            return {'surfaces':int(system.LDE.NumberOfSurfaces),'variables':variables,
                    'fields':[[float(fields.GetField(i).X),float(fields.GetField(i).Y),float(fields.GetField(i).Weight)]
                              for i in range(1,fields.NumberOfFields+1)],
                    'waves':[[float(waves.GetWavelength(i).Wavelength),float(waves.GetWavelength(i).Weight)]
                             for i in range(1,waves.NumberOfWavelengths+1)],
                    'MF_count':int(system.MFE.NumberOfOperands),
                    'MF_targets':{str(row):float(system.MFE.GetOperandAt(row).Target) for row in CHANGES}}
        source=snapshot(SEED)
        draft=snapshot(DRAFT)
        assert draft['fields'] == [[0.,y,1.] for y in (0.,.5,1.,1.5,2.)]
        assert source['variables'] == draft['variables'] and len(draft['variables']) == 85
        assert source['waves'] == draft['waves'] and len(draft['waves']) == 5
        assert source['surfaces'] == draft['surfaces']
        assert draft['MF_count'] == 8794
        assert draft['MF_targets'] == {str(r):b for r,(a,b) in CHANGES.items()}
        receipt.update({'success':True,'source':source,'draft':draft,
                        'scope':'Read-only load and field/variables/spectrum/MF consistency; no optical acceptance or optimization.'})
    finally:
        if app is not None: app.CloseApplication()
        receipt['files_unchanged_by_SDK']=all(sha(p)==h for p,h in before_hashes.items())
        write_json(OUT/'SDK_load_verification.json',receipt)
        write_json(EXPORT/'SDK_load_verification.json',receipt)
    assert receipt['files_unchanged_by_SDK']
    preparation=json.loads((OUT/'preparation_receipt.json').read_text(encoding='utf-8'))
    preparation['status']='prepared_unoptimized_SDK_load_verified_optical_acceptance_pending'
    preparation['SDK_load_verification']=str(OUT/'SDK_load_verification.json')
    write_json(OUT/'preparation_receipt.json',preparation)
    write_json(EXPORT/'preparation_receipt.json',preparation)
    write_json(OUT/'stage_status.json',{
        'status':preparation['status'], 'requirements':str(OUT/'requirements.json'),
        'draft_model':str(DRAFT), 'preserved_3mm_results':str(PRESERVED),
        'original_acceptance_authority':str(ROOT/'results/uv355_user_stop_20261004_1946/selected_acceptance_authority.json'),
        'optimization_enabled':False, 'optimization_started':False,
        'automation_remains_paused':True, 'full_4mm_design_accepted':False,
        'next_action':'Verify 4 mm baseline using field-adapted guards; if hard requirements and stage goals pass, freeze without optimization.'})
    shutil.make_archive(str(EXPORT),'zip',EXPORT)
    print(json.dumps({'SDK_load_verified':True,'variables':85,'wavelength_channels':5,
                      'MF_rows':8794,'optimization_started':False},ensure_ascii=False),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--sdk-verify',action='store_true')
    args=parser.parse_args()
    if args.sdk_verify: sdk_verify()
    else: prepare()
