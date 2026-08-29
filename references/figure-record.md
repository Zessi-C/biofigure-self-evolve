# 学习记录格式规范（figure.md 与 INDEX.json）

每个图库条目 = 一个目录，核心是 `figure.md`：YAML frontmatter（机器解析用）+ Markdown 正文（模型理解用）。本文件是唯一格式权威，写记录前先读完。

## figure.md 结构

```text
figures/NNN-slug/
├── figure.md
├── reference.png
├── template.R
└── template.py
```

- `NNN`：三位零填充递增序号（001、002…），删除条目后编号不复用
- `slug`：小写英文连字符，能望文生义（如 `grouped-heatmap`、`km-survival`、`enrichment-dotplot`）
- 目录名必须与 frontmatter 的 `id` 完全一致

## Frontmatter 字段定义

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | 字符串 | 是 | 等于目录名，如 `001-volcano-ranked` |
| `title` | 字符串 | 是 | 中文标题，具体到变体（「带排名标签的火山图」优于「火山图」） |
| `aliases` | 字符串列表 | 是 | 中英文别名、俗称，检索匹配的主要依据之一 |
| `chart_types` | 字符串列表 | 是 | 受控词表，见 `chart-taxonomy.md`；可多值（如 `[survival-km, risk-table]`） |
| `data_shape` | 字符串 | 是 | 这张图需要什么输入，用具体列描述（「data.frame: gene, log2FC, padj, sig」） |
| `use_when` | 字符串 | 是 | 什么场景该用；写判断依据，不要写空话 |
| `not_when` | 字符串 | 是 | 什么场景不该用/容易误用 |
| `layout` | 字符串 | 是 | 一句话排版描述（主图 + 注释条 + 图例位置等） |
| `languages` | 字符串列表 | 是 | 实际存在的模板，`[R]` / `[Python]` / `[R, Python]` |
| `packages` | 字符串列表 | 是 | 模板依赖的包，扁平列出（如 `[ggplot2, ggrepel, matplotlib]`） |
| `verified` | 字符串 | 是 | `both` / `partial`（仅部分语言验证通过）/ `unverified`；以实际运行为准 |
| `related` | 字符串列表 | 否 | 功能相近条目的 id（变体关系，**双方互指**）；复用多候选排序与查重归位的依据 |
| `source` | 一层嵌套 map | 是 | 见下表 |

`source` 子字段（缩进两格写在 `source:` 下）：

| 子字段 | 说明 |
|---|---|
| `type` | `paper` / `wechat` / `screenshot` / `manual`（manual = 复用流程中沉淀的原创画法） |
| `title` | 材料标题（论文名/文章标题/任务描述） |
| `ref` | DOI、URL 或出处标识；无出处写 `original` |
| `panel` | 面板号（如 `Fig.2a`）；整图写 `full` |
| `learned_date` | 学习日期 `YYYY-MM-DD` |

### Frontmatter 语法限制（重要）

只允许：`key: value` 标量、`key: [a, b, c]` 单行字符串列表、`source:` 下一层两格缩进的 map。**禁止**：多行块（`|`、`>`）、锚点、嵌套列表、注释外的特殊字符。值本身含逗号或冒号时必须用引号包住。这是为了让没有 YAML 库的环境（脚本内置的受限解析器）也能可靠解析——格式自由度换跨设备可靠性，值得。

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

**各节的演化契约**：模式 B 的按反馈进化（SKILL.md B4）只改「配方」「复用要点」和模板文件——**「视觉解剖」永远是来源原图的客观事实，不随演化改写**；「配方」与模板代表当前最佳实践，允许与解剖出现差异，差异原因写进「演化记录」。

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

## 模板自检记录
- R：通过 / 未通过（原因、缺什么依赖）
- Python：通过 / 未通过（原因）
（运行日期；未验证的写清差在哪一步。条目按反馈演化重跑自检时更新本节）

## 复用要点
- 接用户数据前检查：列名映射、分组列是否存在、阈值习惯（padj 还是 pval、FC 阈值 1 还是 2）、标签列有无
- 常见变体：用户可能要求的合理改动（换色板、按显著性分面、只标 top N…）及改法
- 已知坑：如 padj=0 导致 -log10 无穷、基因名重复需去重等

## 与相近条目的对比（仅 related 非空时写）
- `002-km-with-risk-table`：需要按时间展示个体风险状态时用它；只看组间生存差异时用本条

## 演化记录（条目按用户反馈演化后追加，倒序，一行一条）
- 2026-09-02 〔复用反馈〕图例默认移到底部（原置右侧易遮点），双模板已同步并重检通过
```

「配方」必须具体到能照着写代码的程度；「复用要点」与「与相近条目的对比」是复用提速和多候选排序的关键，宁多勿少。对比句的固定句式是"什么时候用它 / 什么时候用本条"。「演化记录」让条目的收敛过程可追溯——它与「视觉解剖」的差异，就是这张图"被你的使用改造"的部分。

### 组合版式 / 图序模式条目的附加要求

- **面板联动**是这类条目的核心资产，必须写进「视觉解剖」和「配方」：面板间共享什么（行序、列序、群编号、配色、阈值），删掉联动设计版式就不成立的部分要显式点名
- **图序模式**（多图讲一个故事）：`source.panel` 填多图（如 `图1 + 图2（成对学习）`）；`reference.png` 可把成组的图拼接成一张（PIL 并排），并在 figure.md 里注明拼接关系；叙事分工（总览 vs 详情）写进 use_when
- 配方按「先各面板、再拼合」组织：第 1~n 步各面板画法，最后一步写拼合（R patchwork / Python gridspec）与图例收纳方式
- 拼合实战坑（已踩过，直接引用）：patchwork 各面板右侧图例会挤占列宽——用 `guides="collect"` + `legend.position="bottom"` 收底；收底色标要横放；facet/分组变量必须转显式因子，否则面板间顺序脱节

## INDEX.json 格式

图库根目录，`figures` 数组每条对应一个条目，字段全部由 figure.md frontmatter 投影而来：

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

- 复用检索只看 INDEX.json，不逐个打开 figure.md——所以它必须与记录同步
- 同步方式只有一种：`build_index.py` 从各 figure.md 的 frontmatter 全量重建。figure.md 是唯一事实源，INDEX.json / INDEX.md 是投影，永远不要手改它们
- `dir` 始终是相对图库根目录的路径
