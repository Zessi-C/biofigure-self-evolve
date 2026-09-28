[English](README.en.md)

# biofigure-self-evolve

**范围**：本技能界定于两项核心任务：图型选择（选型与配方复用）以及视觉呈现规范（美学与排版规范、风格统一、交付前目视验收）。统计口径、数据管道及表格/Excel 交付均不属于本技能范畴。

本项目包含一套**绘图引导**机制与自进化的 figure 图库：未指定图型时引导选型；指定图型时指导画法与美学；图库无匹配条目时依据美学规范从零设计（若提供参考图，则自参考图提炼美学特征）。全局偏好档案用于记录跨项目通用的绘图方式。图库中每条记录均为**独立插件**：抽离任意单条记录，本技能与其余条目仍照常运行。agent 将文献中提炼的图表画法沉淀为本地图库条目；制图前须先检索图库复用，条目与偏好在实际调用中持续迭代更新。条目组织结构参考 [FigureYa](https://github.com/ying-ge/FigureYa)（iMetaMed 2025），主要差异在于图库维护交由 agent 自动执行而非依赖人工。

## 工作方式

- **触发**：凡涉及生信与统计图的生成、修改、复刻或学习，执行操作前须运行 `scripts/retrieve.py` 检索图库；交付成果时须注明"复用了哪条/未命中"；向子代理委派绘图任务时，应将技能入口或检索结果写入委派提示。若配置描述受字段长度限制无法载入完整触发条件，可将 `references/trigger-hook.md` 中的轻量钩子写入项目级或全局 agent 指令。
- **学习**：向 agent 提交文献、PDF、文章或截图后，由其研判并按单图、成组或组合版式建立条目，同时优先追溯原始绘图代码（优先级：正文内嵌代码 > GitHub 仓库 > 论文 DOI → PMC code availability）；仅在无法获取代码时依据图件反推画法，并如实标注来源；
- **从项目历史学**：当接收到「参考我之前的风格 / 把这套画法入库」等指令时，agent 依次读取作为事实源的项目绘图脚本与渲染成图，将既有规范 house style（配色语义、尺寸字号、拼合版式、目录与文件命名）抽象为独立条目（`source.type=project`）：文献条目提供前沿画法，项目条目则沉淀团队既有风格；
- **复用**：绘图时依据 `use_when` 与 `data_shape` 检索相近条目并参考其技术骨架，坐标轴、阈值与配色依据当前数据重新设定；**须按配方临摹改写，而非直接调用或拷贝条目中的参考实现**；命中多个候选时，依 数据形状 > 意图 > 验证状态 降序排序并选取前三项；
- **交付**：成套图件须先输出清单（B0）方可开始绘制；交付前**强制目视自检**（依据 B6 与 `references/delivery-checklist.md` 进行交付自检）；关键图件须增设独立验收环节：环境支持子代理时交由子代理验收，不支持时则运行 `qa_prompt.py --self` 自主核查；交付完成后须记录回执（`retrieve.py --record-used`）。
- **可选辅助**（仅在项目已有清单管理习惯时选用）：包含用于图件清单管理与 `--diff` 增量重导的 `figure_manifest.py`，以及用于图-表同源核验的 `pair_check.py`；此类工具属于图件层面的组织工作，并非本技能核心。
- **美学与偏好**：当图库无匹配条目、或用户仅需要参考特定视觉风格时，可自参考图中提炼**美学**要素（配色逻辑、字号层级、留白与排版策略）并写入 `PREFERENCES.md`，避免强行创建冗余条目；跨项目通用的绘图方式亦沉淀于此，在绘图时作为默认配置生效。脚本与条目模板始终保持**自包含**（独立抽取即可直接运行）；项目内的一致性依赖偏好档案约束，而非引入共享依赖。`scripts/mine_feedback.py`（可选功能，取决于 harness 是否保留会话日志）可定期自交互历史中挖掘用户纠偏，产出偏好候选供后续整理流程研判。
- **回流**：质量达标的成图结果可沉淀为新条目；针对已有条目的修改建议写入对应模板的缺省配置，并记入演化记录；跨图表反复出现的绘图习惯，则汇总至 `library/PREFERENCES.md`。
- **整理**：全局偏好档案（`PREFERENCES.md`）与局部偏好（各条目中的「复用要点」与「演化记录」）须定期收敛整理：执行晋升、合并、降级、下沉及清退，且每次整理均须保留单行记录；`scripts/review_preferences.py` 用于判定维护周期是否届满并列出规则明确的待办事项，语义层面的合并操作则由 agent 负责研判。
- **总结**：`scripts/summary.py` 周期性输出定量报告，涵盖图库规模与月度增量、复用台账（检索次数/命中率/命中热度/**未命中需求 → 待学候选**）、偏好统计与目录结构告警。台账由 `retrieve.py` 在每次检索时自动生成，系核验「agent 是否实际检索图库」的唯一客观证据。
- **迁移**：条目可打包为 bundle（zip 格式，内含清单与逐文件校验和）并导入其他设备的图库，遇到冲突时支持跳过、覆盖或重新编号；导入新环境后，可运行 `verify_library.py` 进行健康体检。

学习流程是否完成由完工清单判定。条目记录格式参见 [references/figure-record.md](references/figure-record.md)，触发机制与行为规范参见 SKILL.md。

## 安装

```bash
git clone https://github.com/Zessi-C/biofigure-self-evolve.git ~/.agents/skills/biofigure-self-evolve

# 装完就跑：把常驻触发钩子写进 agent 指令层（这一步和克隆同等重要）
python3 ~/.agents/skills/biofigure-self-evolve/scripts/install_hook.py
python3 ~/.agents/skills/biofigure-self-evolve/scripts/install_hook.py --check
# omp 等按项目读 AGENTS.md 的 harness，逐个项目装：
python3 ~/.agents/skills/biofigure-self-evolve/scripts/install_hook.py --project /path/to/项目
```

本技能适用于遵循 agents/skills 规范的各类 agent（目录中包含具备 name 与 description frontmatter 的 SKILL.md 即视为技能）。其他 harness 只要具备文件读写、网页抓取与脚本执行能力即可驱动；若有专有插件格式，仅需添加一层轻量适配。环境依赖：

- 脚本仅依赖 Python 3 标准库（PyYAML 为可选项，缺省使用内置受限解析器；`figure_manifest.py` 在存在 `pdfinfo` 时能更准确统计 PDF 页数，缺失时退回内置解析，若仍无法获取则置空）；
- 条目以**配方**为核心，参考实现（`template.R` / `template.py`）为可选项；仅在验证参考实现时需要 R（ggplot2）与/或 Python（matplotlib），环境缺失对应运行时则标注 `unverified` 或缺省该字段；
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
    ├── template.R / template.py   # 可选：参考实现，无参数运行即出图（"怎么写"的示范，不是可调用接口）
    └── template_output_*   # 模板运行产物，作为已知良好输出
references/                 # 记录 schema、各来源取图方法、chart_types 受控词表（近 40 种）、偏好档案格式、触发钩子、交付清单
scripts/                    # install_hook / init_library / build_index / retrieve / review_preferences / summary / figure_manifest / pair_check / qa_prompt / mine_feedback / export_figure / import_figure / verify_library
```

frontmatter 采用严格受限的 YAML 子集（仅支持标量、单行列表与单层嵌套），在未安装 YAML 库的环境下亦能可靠解析。核心字段包含：`chart_types`（受控词表选词）、`data_shape`（单行写明输入格式）、`use_when` / `not_when`（复用检索时的语义匹配依据）、`related`（同功能条目互相引用）以及 `verified`（仅认可实际运行检验结果）。

`library/figures/*`、`INDEX.*`、`PREFERENCES.md`、`USAGE.jsonl`、`SUMMARY.*` 与 `FEEDBACK-CANDIDATES.md` 均已被 .gitignore 忽略：积累的条目与个人使用数据不进入公开仓库；随仓库发布的 `000-example-grouped-boxplot` 既是格式示例，也是创建新条目的初始骨架。公开分享自文献习得的条目时，请注意遵守原文献版权。

## 脚本

```bash
python3 scripts/init_library.py    # 初始化图库骨架（幂等；--path 可放别处并自动写配置）
python3 scripts/build_index.py     # 全量重建索引并做一致性校验；改过任何 figure.md 后必须重跑
python3 scripts/build_index.py --check      # 只比对索引与记录是否一致（不一致退出码 1），不写文件

# 安装钩子（装技能后跑一次）
python3 scripts/install_hook.py                              # 写进检测到的 harness 全局指令层（幂等；--check/--uninstall/--dry-run）
python3 scripts/install_hook.py --project /path/to/项目       # omp 等项目级 AGENTS.md

# 复用前检索、偏好整理、定期总结
python3 scripts/retrieve.py "两组差异火山图，要标通路"      # top-K 候选 + 偏好摘要（--all 浏览 / --json 给子代理；自动记台账）
python3 scripts/review_preferences.py --check                # 偏好是否到该整理的节律（退出码 1 = 该整理）
python3 scripts/review_preferences.py                        # 出整理报告：合并/晋升/降级/跨条目复现/过期未复现
python3 scripts/review_preferences.py --digest               # 输出可粘贴进 harness 记忆的偏好摘要
python3 scripts/summary.py --check                           # 定量总结是否到期（退出码 1 = 该总结）
python3 scripts/summary.py --write                           # 出报告并落盘 library/SUMMARY.md

# 图件清单（交付图族时用）
python3 scripts/figure_manifest.py figure/8.xxx --write      # 生成/更新 figure_manifest.csv（语义列保留）
python3 scripts/figure_manifest.py figure/8.xxx --check      # 未登记文件 / 被取代的旧图 → 退出码 1
python3 scripts/figure_manifest.py figure/8.xxx --diff old.csv --only unchanged   # 增量重导：hash 未变可跳过
python3 scripts/pair_check.py figure/8.xxx --tables table/8.xxx   # 图-表同源核验
python3 scripts/qa_prompt.py figure/8.xxx --task "定稿图" --out /tmp/qa.md   # 生成 QA 子代理提示

# 偏好候选
python3 scripts/mine_feedback.py --since 2026-08-01           # 从会话历史挖纠偏 → 偏好候选

# 跨设备迁移条目（典型：本机读文献学图 → 服务器跑分析复用）
python3 scripts/export_figure.py 003 --with-related   # 打包条目为 bundle（id/数字前缀/all 均可）
python3 scripts/import_figure.py bundle.zip           # 校验完整性后导入，自动重建索引；冲突默认拒绝（--force 覆盖 / --rename 换编号）
python3 scripts/verify_library.py                     # 体检（可选）：有参考实现的条目复制到临时目录试运行，只报告不改库
```

## 许可

遵循 MIT 许可证，详见 [LICENSE](LICENSE)。
