# UV355物镜：4 mm视场数值设计结果

本次发布处方通过 **129、513、1025点原生数值复核**，并通过最小物方半径至1 µm的近轴排序补充检查。物方视场直径4 mm、NA 0.60、名义倍率−10×。

| 指标 | 复核最坏值 | 现行要求 |
|---|---:|---:|
| RMS波前 | 0.054949822 λ | ≤0.055 λ |
| 轴上RMS波前 | 0.033733907 λ | ≤0.04 λ |
| RMS/Airy | 0.998516989 | ≤1 |
| 物方场曲 | 0.283411 µm | ≤0.493 µm |
| 物方像散 | 0.346289 µm | ≤0.493 µm |
| 像高误差 | 14.962812 µm | <15 µm |

前组发散、物像方远心、正弦误差、焦深、厚度与间隙检查也通过；85个原始变量及8794行评价函数保持一致。大口径厚度按已授权的工程估算规则检查。

- [Zemax处方](key_results/FOV_4p0mm/R943_REVIEWED_8052c41f148e/prescription.zmx) · [原始评价函数](key_results/FOV_4p0mm/R943_REVIEWED_8052c41f148e/prescription.MF) · [处方参数](key_results/FOV_4p0mm/R943_REVIEWED_8052c41f148e/PRESCRIPTION_PARAMETERS.json)
- [完整结果说明](key_results/FOV_4p0mm/R943_REVIEWED_8052c41f148e/DESIGN_RESULT.md) · [验收数据汇总](key_results/FOV_4p0mm/R943_REVIEWED_8052c41f148e/ACCEPTANCE_SUMMARY.json)
- [MTF原始数据](key_results/FOV_4p0mm/R943_REVIEWED_8052c41f148e/NATIVE_POLYCHROMATIC_MTF_CURVES.json) · [近轴排序检查](key_results/FOV_4p0mm/R943_REVIEWED_8052c41f148e/FINE_AXIS_ORDERING.json)
- [代码、导数及数据增量封存](exports/UV355_4MM_NUMERICAL_CHECKPOINT_8052c41f148e_20261102/DESIGN_CHECKPOINT.zip) · [逐文件清单](exports/UV355_4MM_NUMERICAL_CHECKPOINT_8052c41f148e_20261102/MANIFEST.json) · [封存校验](exports/UV355_4MM_NUMERICAL_CHECKPOINT_8052c41f148e_20261102/ARCHIVE_VERIFICATION.json)

![原生多色MTF曲线](key_results/FOV_4p0mm/R943_REVIEWED_8052c41f148e/POLYCHROMATIC_MTF.png)

MTF使用原五波长多色计算，像方频率0–200 lp/mm；两档采样各90个数据点，采样7收敛，最大差为0.0000217801。**MTF由用户根据曲线判断，不作为自动验收或优化门槛。**

![1025点数值复核](key_results/FOV_4p0mm/R943_REVIEWED_8052c41f148e/FIELD_DIAGNOSTICS_1025.png)

当前结论是采样数值要求通过。原始优化停止验证、扩大搜索域与色差稳定性证据，以及制造公差、装调和最终放行尚未完成；采样通过不等于连续视场数学证明。

处方SHA256：`8052c41f148e285af8521eb922b8bde728ec758d09006b8c9f5721f8dd708366`。ZIP的SHA256：`30456bec4f01e842f8fc7daed45adb5ec4fddca3db39063979cf0ccfc7ab077c`，已核验CRC和全部文件哈希，含158个条目、11份NPZ数据。

代码与数据保留其原始目录、来源处方和校验值。ZIP是**增量检查点**，优化脚本仍依赖原本地工作区的历史输入、OpticStudio/ZOS-API与许可，不能作为独立的一键运行环境；原始Windows路径仅用于追溯。直接查看处方、复核数据和曲线无需运行优化器。历史原始审计保留0.05 λ判断，现行0.055 λ及场曲、像散判断另存于验收汇总。
