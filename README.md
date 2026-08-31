[English](README.en.md)

# biofigure-self-evolve

自进化的生信 figure 学习库与复用引擎。agent 把文献里看到的图画法存成本地图库条目，你要画图时先查库复用，条目与偏好随使用不断更新。条目组织参考 [FigureYa](https://github.com/ying-ge/FigureYa)（iMetaMed 2025），差异在于维护交给 agent 而非人工。

## 工作方式

- **学习**：把文献、PDF、文章、截图发给 agent，它判断按单图、成组还是组合版式记录，并优先追溯原始绘图代码（正文内嵌代码 > GitHub 仓库 > 论文 DOI → PMC code availability），都找不到才看图反推且如实标注；
- **复用**：画图时按 `use_when` / `data_shape` 检索相近条目，借鉴其技术骨架，轴、阈值、配色按当前数据重新决定；多候选时按数据形状 > 意图 > 验证状态排序取前三；
- **回流**：满意的结果回收为新条目；对已有条目的意见写入其模板缺省值并记入演化记录；跨图反复出现的习惯沉淀到 `library/PREFERENCES.md`。
- **迁移**：条目可打包成 bundle（zip，带清单与逐文件校验和）导入其他设备的图库，冲突可跳过/覆盖/换编号；新环境导入后跑 `verify_library.py` 体检。

学习是否完成由完工清单判定。记录格式见 [references/figure-record.md](references/figure-record.md)，触发行为见 SKILL.md。

## 安装

```bash
git clone https://github.com/Zessi-C/biofigure-self-evolve.git ~/.agents/skills/biofigure-self-evolve
```

适用于任何遵循 agents/skills 约定的 agent（目录含带 name/description frontmatter 的 SKILL.md 即为技能）。其他 harness 只要能读文件、抓网页、跑脚本即可驱动，有自有插件格式的加一层薄适配。依赖：

- 脚本只需 Python 3 标准库（PyYAML 可选，缺省走内置受限解析器）；
- 模板验证需要 R（ggplot2）和/或 Python（matplotlib），缺哪边哪边的条目标 `unverified`；
- 不依赖任何厂商 API、MCP 或联网服务。

## 仓库结构

```text
SKILL.md                    # 技能入口：触发、学习/复用/回流的行为规范
library/
├── INDEX.json / INDEX.md   # 索引，脚本从所有 figure.md 全量重建，不入公开仓库
├── PREFERENCES.md          # 跨图偏好档案（个人数据，不入公开仓库）
└── figures/NNN-slug/
    ├── figure.md           # 唯一事实源：frontmatter + 视觉解剖 + 配方 + 复用要点 + 演化记录
    ├── reference.png       # 原图参考（仅个人学习用）
    ├── template.R / template.py   # 自包含双模板，无参数运行即出图
    └── template_output_*   # 模板运行产物，作为已知良好输出
references/                 # 记录 schema、各来源取图方法、chart_types 受控词表（近 40 种）、偏好档案格式
scripts/                    # init_library / build_index / export_figure / import_figure / verify_library
```

frontmatter 是刻意收窄的 YAML 子集（标量、单行列表、一层嵌套），没有 YAML 库的环境也能可靠解析。关键字段：`chart_types`（受控词表选词）、`data_shape`（一行写清输入格式）、`use_when` / `not_when`（复用时的语义匹配依据）、`related`（同功能条目互指）、`verified`（只认实际运行结果）。

`library/figures/*`、`INDEX.*`、`PREFERENCES.md` 被 .gitignore 忽略，学到的条目不进公开仓库；随仓库发布的 `000-example-grouped-boxplot` 是格式示例，也是新建条目的骨架。公开分享学到的条目请注意原文献版权。

## 脚本

```bash
python3 scripts/init_library.py    # 初始化图库骨架（幂等；--path 可放别处并自动写配置）
python3 scripts/build_index.py     # 全量重建索引并做一致性校验；改过任何 figure.md 后必须重跑
python3 scripts/build_index.py --check      # 只比对索引与记录是否一致（不一致退出码 1），不写文件

# 跨设备迁移条目（典型：本机读文献学图 → 服务器跑分析复用）
python3 scripts/export_figure.py 003 --with-related   # 打包条目为 bundle（id/数字前缀/all 均可）
python3 scripts/import_figure.py bundle.zip           # 校验完整性后导入，自动重建索引；冲突默认拒绝（--force 覆盖 / --rename 换编号）
python3 scripts/verify_library.py                     # 体检：模板复制到临时目录试运行，只报告不改库
```

## 许可

MIT，见 [LICENSE](LICENSE)。
