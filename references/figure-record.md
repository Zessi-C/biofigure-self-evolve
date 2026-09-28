# 学习记录格式规范（figure.md 与 INDEX.json）

每个图库条目对应一个独立目录，其核心文件为 `figure.md`，由机器解析所需的 YAML frontmatter 与供模型理解的 Markdown 正文两部分组成。本文件为条目格式的唯一权威规范，撰写记录前须完整通读。

## figure.md 结构

```text
figures/NNN-slug/
├── figure.md         # 唯一事实源：配方 + 解剖 + 复用要点（必填）
├── reference.png     # 参考图（必填）
├── template.R        # 可选：参考实现
└── template.py       # 可选：参考实现
```

- **条目是独立插件**：各条目不得引用其他条目或共享文件；独立复制或删除条目均不影响技能本体与其他条目（`related` 仅作推荐参考，不构成运行依赖）
- `NNN`：三位补零递增序号（001、002…）；条目删除后编号不再复用
- `slug`：语义明确的小写英文连字符命名（如 `grouped-heatmap`、`km-survival`、`enrichment-dotplot`）
- 目录名必须与 frontmatter 的 `id` 完全一致

## Frontmatter 字段定义

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串 | 是 | 与目录名保持一致，如 `001-volcano-ranked` |
| `title` | 字符串 | 是 | 中文标题，须具体至变体（「带排名标签的火山图」优于「火山图」） |
| `aliases` | 字符串列表 | 是 | 中英文别名与常用俗称，作为检索匹配的核心依据之一 |
| `chart_types` | 字符串列表 | 是 | 受控词表，详见 `chart-taxonomy.md`；可多值指定（如 `[survival-km, risk-table]`） |
| `data_shape` | 字符串 | 是 | 图表所需的输入数据结构，以具体字段列名描述（「data.frame: gene, log2FC, padj, sig」） |
| `use_when` | 字符串 | 是 | 适用场景；须详明判定依据，切忌空泛表述 |
| `not_when` | 字符串 | 是 | 不适用场景或常见误用情形 |
| `layout` | 字符串 | 是 | 单句排版描述（涵盖主图、注释条及图例位置等） |
| `languages` | 字符串列表 | 是 | 配方涉及的参考实现语言，`[R]` / `[Python]` / `[R, Python]` |
| `packages` | 字符串列表 | 是 | 模板所依赖的程序包，扁平列出（如 `[ggplot2, ggrepel, matplotlib]`） |
| `verified` | 字符串 | 否 | 仅在提供参考实现时填写：`both` / `partial` / `unverified`；以实际运行结果为准。纯配方条目省略该字段 |
| `related` | 字符串列表 | 否 | 功能相近条目的 id 列表（表征变体关联，**双方互指**）；作为复用时多候选排序与查重归位的依据 |
| `source` | 一层嵌套 map | 是 | 详见下表 |

`source` 子字段（以两格缩进书写于 `source:` 下方）：

| 子字段 | 说明 |
|---|---|
| `type` | `paper` / `wechat` / `screenshot` / `project` / `manual`（`project` = 从项目历史脚本与成图沉淀的自有风格；`manual` = 复用流程中提炼的原创作图方法） |
| `title` | 素材标题（论文题名、文章标题或任务描述） |
| `ref` | DOI、URL 或出处标识；`project` 类型填写「绘图脚本路径 + 成图路径」；若无外部出处则填写 `original` |
| `panel` | 面板编号（如 `Fig.2a`）；整图填写 `full` |
| `learned_date` | 学习日期，格式为 `YYYY-MM-DD` |

### Frontmatter 语法限制（重要）

语法仅允许：`key: value` 标量、`key: [a, b, c]` 单行字符串列表，以及 `source:` 下缩进两格的单层 map。**严禁**使用多行块（`|`、`>`）、锚点、嵌套列表或注释之外的特殊字符；若键值本身包含逗号或冒号，必须加引号包裹。上述限制旨在确保未集成 YAML 类库的环境（如脚本内置的受限解析器）亦能稳定解析，以规范格式灵活性为代价，换取跨平台解析的可靠性。

### 完整示例

```yaml
---
id: 001-volcano-ranked
title: 带排名标签的火山图
aliases: [volcano plot, 火山图, 差异表达散点图]
chart_types: [volcano]
data_shape: "data.frame: gene, log2FC, padj（或 pval）, 可选 sig 分组列"
use_when: 展示差异分析的倍数变化与显著性总体分布，并标注重点基因
not_when: 非两组比较的数据；想看样本聚类时应改用 PCA 或热图
layout: 散点主图，横轴 log2FC 纵轴 -log10(padj)，阈值虚线 + 右侧基因标签
languages: [R, Python]
packages: [ggplot2, ggrepel, matplotlib, adjustText]
verified: both
source:
  type: paper
  title: "FigureYa59volcanoV2 示例（测试种子条目）"
  ref: "https://github.com/ying-ge/FigureYa (CC BY-NC-SA 4.0)"
  panel: full
  learned_date: 2026-08-29
---
```

## 正文结构（固定四节 + 可选两节）

**各节的演化契约**：依反馈推进的条目演化（模式 B，参见 SKILL.md B5）仅可修改「配方」、「复用要点」与模板文件；**「视觉解剖」始终记录来源原图的客观事实，不随条目演化而改写**。「配方」与模板反映当前最佳实践，允许与原始解剖记录存在出入，其差异成因须如实记入「演化记录」。

```markdown
## 视觉解剖
### Panel A（多面板时逐面板写；单图直接写）
- 图层（自底向上）：…
- 映射：x=…, y=…, color=…, size=…, fill=…
- 坐标与变换：log 轴/反转/极坐标/分面…
- 阈值与注释：参考线、显著性标记、标签规则
- 配色：具体到色值或色板名
- 排版：画布尺寸比例、字号层级、图例位置、导出规格（300dpi PNG + 矢量 PDF）

## 配方（语言无关）
1. 输入整形：把用户数据变成 data_shape 描述的形状，具体到操作
2. 衍生列：如 -log10(padj)、显著性分组、排序规则
3. 分层绘制：按图层顺序写清每层画什么、参数要点
4. 主题与导出：主题细节、图例调整、输出规格

## 参考实现（可选）
- 没写参考实现 → 本节写一句"纯配方条目（未附代码）"即可
- 写了 → R / Python 各一行：通过 / 未通过（原因、缺什么依赖），带运行日期
（参考实现是"怎么写"的示范、并用来验证画法可行；复用时按配方临摹改写，不要整段拷贝）

**参考实现必须自包含**：不要 `source()` 项目里的共享文件、不要依赖条目目录之外的路径或 theme——条目要能被单独拷到任何设备、任何项目里跑起来。项目内的风格一致由 `PREFERENCES.md` 的偏好约束，不靠代码耦合。

## 复用要点
- 接用户数据前检查：列名映射、分组列是否存在、阈值习惯（padj 还是 pval、FC 阈值 1 还是 2）、标签列有无
- 常见变体：用户可能要求的合理改动（换色板、按显著性分面、只标 top N…）及改法
- 已知坑：如 padj=0 导致 -log10 无穷、基因名重复需去重等

## 与相近条目的对比（仅 related 非空时写）
- `002-km-with-risk-table`：需要按时间展示个体风险状态时用它；只看组间生存差异时用本条

## 演化记录（条目按用户反馈演化后追加，倒序，一行一条）
- 2026-09-02 〔复用反馈〕图例默认移到底部（原置右侧易遮点），双模板已同步并重检通过
```

**条目的事实源是「配方」，而非代码文件**：参考实现仅用于示范绘图逻辑与自验可行性，实际复用时须遵循配方重新编写。

「配方」的详实程度必须达到可直接指导代码编写的水平；「复用要点」与「与相近条目的对比」是提升复用效率与实施多候选排序的关键依据，内容宜详不宜简。对比描述须遵循固定句式："什么时候用它 / 什么时候用本条"。「演化记录」使条目的收敛演进全程可溯；其与「视觉解剖」的偏离，真实反映了图表在实际应用中所沉淀的定制化改造。

随着条目持续迭代，「演化记录」可能逐步累积（当记录条数 ≥5 时，脚本将提示"条目内堆积"）。此时，持续生效的默认设定应提炼并收敛至「复用要点」，演化记录本身仅保留"改了什么、为什么"。此类收敛属于偏好整理的组成部分，详见 `preference-profile.md` 的「条目侧的整理」。

### 组合版式 / 图序模式条目的附加要求

- **面板联动**是此类条目的核心资产，必须明确写入「视觉解剖」与「配方」：阐明面板间共享的具体要素（如行序、列序、群编号、配色与阈值），并显式指出一旦移除联动设计则整体版式无法成立的关键环节
- **图序模式**（多图协同叙事）：`source.panel` 填写多图标识（如 `图1 + 图2（成对学习）`）；`reference.png` 可将成组图像合并为单张参考图（利用 PIL 并排拼接），并在 figure.md 中注明拼接关系；叙事分工（总览 vs 详情）须写入 use_when 字段
- 配方须按「先各面板、再拼合」的次序组织：第 1~n 步依次阐明各面板的绘制方法，最后一步明确拼合方案（R patchwork / Python gridspec）与图例收纳方式
- 拼合实战要点（已验证经验）：使用 patchwork 时，各面板右侧图例易挤占列宽，须通过 `guides="collect"` + `legend.position="bottom"` 统一步局于底部；底部色标须水平放置；facet/分组变量必须转换为显式因子，否则面板间对应顺序将会脱节

## INDEX.json 格式

位于图库根目录，`figures` 数组中的每个元素对应一个条目，所有字段均由 figure.md frontmatter 投影生成：

```json
{
  "version": 1,
  "updated": "2026-08-29",
  "figures": [
    {
      "id": "001-volcano-ranked",
      "title": "带排名标签的火山图",
      "aliases": ["volcano plot", "火山图", "差异表达散点图"],
      "chart_types": ["volcano"],
      "data_shape": "data.frame: gene, log2FC, padj（或 pval）, 可选 sig 分组列",
      "use_when": "展示差异分析的倍数变化与显著性总体分布，并标注重点基因",
      "languages": ["R", "Python"],
      "verified": "both",
      "related": [],
      "source_type": "paper",
      "dir": "figures/001-volcano-ranked"
    }
  ]
}
```

- 复用检索仅读取 INDEX.json，并不逐一解析 figure.md，因此索引文件必须与条目记录保持严格同步
- 索引同步仅有单一合法途径：运行 `build_index.py` 从各 figure.md 的 frontmatter 执行全量重建。figure.md 是唯一事实源，INDEX.json / INDEX.md 仅为其衍生投影，严禁手动修改
- `dir` 始终为相对于图库根目录的相对路径
