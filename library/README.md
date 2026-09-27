# Biofigure Library

个人生物信息学 figure 学习库。每个 `figures/NNN-slug/` 目录是一条学习记录：
语言无关的绘制配方（figure.md）+ 原图参考（reference.png）+ R/Python 可运行模板。

- `INDEX.json` — 机器可读索引，由 scripts/build_index.py 从各 figure.md 投影生成
- `INDEX.md`   — 人类可读索引，同上
- `PREFERENCES.md` — 跨图偏好档案（个人数据，不入公开仓库）

检索与整理走技能里的脚本，不要手工翻这两个索引：

```bash
python3 ../scripts/retrieve.py "两组差异火山图，要标通路"     # 复用前检索：top-K 候选 + 偏好摘要
python3 ../scripts/review_preferences.py --check              # 偏好是否到该整理的节律（退出码 1 = 该整理）
python3 ../scripts/build_index.py                             # 改过任何 figure.md 后重建索引
```

本目录是纯文件，可用 git 或任意云盘同步；配合 biofigure-self-evolve 技能使用。
