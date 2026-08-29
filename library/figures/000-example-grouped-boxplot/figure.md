---
id: 000-example-grouped-boxplot
title: 示例条目——分组箱线图 + 抖动散点 + 显著性括线
aliases: [boxplot example, 箱线图示例, format demo]
chart_types: [boxplot]
data_shape: "长表：group（2~5 组因子）, value（数值列）；每组 ≥10 个观测为宜"
use_when: 比较少组（2~5 组）连续变量的分布与组间差异，需同时呈现个体数据点与统计显著性
not_when: 组数多且只关心中位数排序（改条形图）；数据成对（改配线图 paired-line）
layout: 纵向箱线（无缺省外点）+ 半透明抖动散点 + 顶部显著性括线与星号，无背景网格，y 从 0 或数据下界起
languages: [R, Python]
packages: [ggplot2, matplotlib, pandas, numpy]
verified: both
source:
  type: manual
  title: "格式演示条目：本条目为发布示例而作，可作学习新图时的照抄模板"
  ref: original
  panel: full
  learned_date: 2026-08-29
---

## 视觉解剖

- 图层（自底向上）：抖动散点（灰、半透明、size 小）→ 箱线（填充组色、无边框外点、中位线加粗）→ 显著性括线（黑色细线 + 星号文本）
- 映射：x=group，y=value，fill=group（半透明让散点可读）；散点 x 抖动 ±0.12 避免重叠
- 坐标与变换：y 范围留出顶部括线空间（上限扩 ~15%）；x 离散
- 阈值与注释：括线连接两组的 y=max(两组上限)+偏移，星号按 p 值映射（*<0.05, **<0.01, ***<0.001, ns 不画）
- 配色：3 组用中等饱和分类色（#4C72B0 #DD8452 #55A868），箱线填充 alpha≈0.55
- 排版：无主标题；轴标题常规字号；去背景网格保留轴线；导出 300dpi PNG + 矢量 PDF

## 配方（语言无关）

1. 输入整形：长表按组因子化，组序=展示序（不要默认字母序）
2. 底层散点：jitter（x 方向 ±0.12，y 原值），灰色半透明压底
3. 箱线层：默认统计（中位/四分位/须 1.5×IQR），隐藏外点（散点已承担），填充组色半透明
4. 显著性括线：选定组对 → 括线 y 从最高箱须向上逐对抬高（每对 +6% 高度），线端下垂 2%，中点放星号；p 值由外部检验（t 检验/Wilcoxon）算好传入
5. 主题：去网格、保留轴线、y 上限扩 15% 给括线让位
6. 导出：300dpi PNG + 矢量 PDF

## 模板自检记录

- R：通过（2026-08-29，ggplot2；括线用 annotate 手绘，无 ggsignif 依赖）
- Python：通过（2026-08-29，matplotlib；括线用 plot+text 手绘）

## 复用要点

- 接用户数据前检查：分组列与数值列名；组数（>5 组建议横置或分面）；是否已有算好的 p 值矩阵，没有则现场跑 Wilcoxon 并注明方法
- 常见变体：小提琴+内嵌箱线；按第二因子分面；换显著性标注为字母标记（cbkstyle）；箱线换均值±SEM 误差棒
- 已知坑：括线 y 逐对抬高时别忘了重置基准，否则最后一对飞出画布；抖动只抖 x 不抖 y（抖 y 会歪曲数值）；组序因子化前先确认语义顺序
- 本条目 source.type=manual、ref=original：复用流程中「满意后回流」的条目长这样

## 与相近条目的对比

（示例条目，无相近条目；私有库中如有同类型条目，按 references/figure-record.md 的 related 规则互指）
