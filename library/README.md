# Biofigure Library

个人生物信息学 figure 学习库。每个 `figures/NNN-slug/` 目录均对应一条学习记录：
包含与语言无关的绘制配方（figure.md）、参考图（reference.png）以及 R/Python 可运行模板。

- `INDEX.json` — 机器可读索引，由 scripts/build_index.py 遍历各 figure.md 投影生成
- `INDEX.md`   — 人类可读索引，生成逻辑同上
- `PREFERENCES.md` — 跨图偏好档案（属个人数据，不纳入公开仓库）
- `USAGE.jsonl`   — 复用台账：每次调用 `retrieve.py` 均追加记录，`summary.py` 据此统计命中率并评估待学候选
- `SUMMARY.md`    — 最近一次定量总结报告（由 `summary.py --write` 生成）

检索与整理均须调用技能内置脚本完成，切勿手动翻阅上述两份索引：

```bash
python3 ../scripts/retrieve.py "两组差异火山图，要标通路"     # 复用前检索：top-K 候选 + 偏好摘要（自动记台账）
python3 ../scripts/review_preferences.py --check              # 偏好是否到该整理的节律（退出码 1 = 该整理）
python3 ../scripts/summary.py --check                         # 定量总结是否到期；--write 落盘 SUMMARY.md
python3 ../scripts/build_index.py                             # 改过任何 figure.md 后重建索引
```

本目录均为纯文本与静态文件，支持通过 git 或任意云盘同步；使用时需配合 biofigure-self-evolve 技能。
