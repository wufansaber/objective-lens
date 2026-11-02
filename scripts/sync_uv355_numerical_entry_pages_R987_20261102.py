"""Promote verified current numerical evidence while retaining historical designs."""
from pathlib import Path
import re
from atomic_progress import read_json_retry as read
from run_uv355_multistart_campaign import sha

ROOT = Path(__file__).resolve().parents[1]


def main():
    checkpoint = read(ROOT/'key_results/LATEST_R943_NUMERICAL_CHECKPOINT.json')
    assert checkpoint['all_listed_numerical_checks_pass']
    assert sha(checkpoint['model']) == checkpoint['source_sha256']
    record = read(ROOT/'key_results/LATEST_R943_REVIEWED.json')
    assert record['sha256'] == checkpoint['source_sha256']
    folder = Path(record['key_result_directory'])
    location = folder.relative_to(ROOT).as_posix()
    s = checkpoint['summary']
    current = (f"当前4 mm处方通过原生129、513、1025点数值检查：最坏RMS波前 **{s['wfe_worst_waves']:.9f} λ**，"
               f"RMS/Airy **{s['rms_over_airy_worst']:.9f}**，物方场曲 **{s['field_curvature_object_um']:.6f} µm**，"
               f"物方像散 **{s['astigmatism_object_um']:.6f} µm**，像高误差 **{s['maximum_height_error_um']:.6f} µm**。")
    limits = ('现行数值要求为：全视场RMS波前≤0.055 λ、轴上≤0.04 λ、RMS/Airy≤1、物方场曲和像散各≤0.493 µm、'
              '像高误差<15 µm，并满足其他接口及实体要求。MTF仅提供曲线，等待用户判断。'
              '原始优化停止条件和制造、装配放行证据尚未建立；采样通过不等于连续视场证明。')
    root = ROOT/'README.md'
    text = root.read_text(encoding='utf-8-sig')
    marker = '| 内容 | 位置 |'
    assert text.count(marker) == 1
    tail = text[text.index(marker):]
    tail = re.sub(r'^\| 当前 4\.0 mm 完整复核结果与处方 \|.*$',
                  f'| 当前 4.0 mm 数值通过处方与完整复核 | [设计结果]({location}/DESIGN_RESULT.md) · [最新指针](key_results/LATEST_R943_NUMERICAL_CHECKPOINT.json) |', tail, flags=re.M)
    tail = re.sub(r'^\| 当前状态、最优处方与后续工作 \|.*$',
                  '| 当前状态、处方与后续工作 | [CONTINUATION.json](CONTINUATION.json)及其中的 authoritative_resume_handoff |', tail, flags=re.M)
    intro = ('# UV355物镜：3–4 mm设计结果与代码\n\n'+current+'\n\n'+limits+'\n\n'
             f'[处方、MTF及完整结果]({location}/DESIGN_RESULT.md) · '
             f"[校验过的增量封存]({Path(checkpoint['archive']['archive']).relative_to(ROOT).as_posix()})。\n\n"
             f"当前处方SHA256：`{checkpoint['source_sha256']}`。3–3.8 mm关键结果和历史4 mm研究处方继续保留。\n\n")
    root.write_text(intro+tail, encoding='utf-8')
    key = ROOT/'key_results/README.md'
    kt = key.read_text(encoding='utf-8-sig')
    kt = re.sub(r'<!-- CURRENT_NUMERICAL_START -->.*?<!-- CURRENT_NUMERICAL_END -->\n?', '', kt, flags=re.S)
    kt = re.sub(r'^现行规则复核方案：.*\n?', '', kt, flags=re.M)
    kt = re.sub(r'^\| 4\.0 mm \| 现行数值要求通过.*\n?', '', kt, flags=re.M)
    kt = re.sub(r'^4 mm 当前保留处方的 SHA256 为 .*$',
                '原规则下保留的4 mm研究处方见 [ACTIVE_BEST.json](ACTIVE_BEST.json)。该历史指针保留其原验收结论，现行数值通过处方见上方链接。', kt, flags=re.M)
    kt = re.sub(r'^\| 4\.0 mm \| 当前.*$', '| 4.0 mm | 历史原规则保留研究处方，513点 | 0.062350377 |', kt, flags=re.M)
    kt = kt.replace('|---|---|---:|', f"|---|---|---:|\n| 4.0 mm | 现行数值要求通过，129／513／1025点 | {s['wfe_worst_waves']:.9f} |", 1)
    kt = kt.replace('# 3–4 mm 关键结果\n', '# 3–4 mm 关键结果\n\n<!-- CURRENT_NUMERICAL_START -->\n'+current+'\n\n'
                    f"[当前设计结果与MTF]({folder.relative_to(ROOT/'key_results').as_posix()}/DESIGN_RESULT.md)。"+limits+'\n<!-- CURRENT_NUMERICAL_END -->\n', 1)
    kt = kt.replace('对应文件位于 [当前 4 mm 结果](FOV_4p0mm/ACTIVE_REVIEWED_20261102_065454/)',
                    f"对应现行文件位于 [当前4 mm结果]({folder.relative_to(ROOT/'key_results').as_posix()}/)")
    key.write_text(re.sub(r'\n{3,}', '\n\n', kt), encoding='utf-8')
    print('Numerical result entry pages synchronized with immutable native evidence')


if __name__ == '__main__':
    main()
