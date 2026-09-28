# chart_types 受控词表与数据形状词表

`chart_types` 须自下表受控词中选取（支持多值标注），以确保图表学习与检索两端遵循统一术语。若目标图表类型确未收录，可依规范自拟 kebab-case 格式新词，并酌情增补至本文档。

## 图类型词表

| 词 | 图 |
|---|---|
| `heatmap` | 热图（含聚类热图与注释条版式） |
| `volcano` | 火山图 |
| `ma-plot` | MA 图 |
| `boxplot` | 箱线图 |
| `violin` | 小提琴图 |
| `barplot` | 柱状图/条形图（含堆叠与分组模式） |
| `line` | 折线图/时间序列图 |
| `scatter` | 散点图/相关性分析图 |
| `enrichment-dotplot` | 富集分析点图/气泡图（GO/KEGG/Reactome） |
| `gsea-runplot` | GSEA 运行得分曲线（running-score 曲线） |
| `kegg-map` | KEGG 通路富集着色图 |
| `survival-km` | KM 生存分析曲线 |
| `risk-plot` | 生存风险评分联合图（散点分布、生存状态与热图组合） |
| `forest` | 森林图（涵盖 Cox 回归、常规回归与 Meta 分析） |
| `roc` | ROC 曲线 |
| `nomogram` | 列线图 |
| `oncoprint` | 突变全景图（OncoPrint） |
| `circos` | 基因组圈图（Circos 图） |
| `manhattan` | 曼哈顿图 |
| `qq-plot` | Q-Q 图 |
| `venn` | 韦恩图 |
| `upset` | UpSet 集合交集图 |
| `network` | 分子网络与通路互作图 |
| `sankey` | 桑基图/冲积图 |
| `chord` | 弦图 |
| `umap-tsne` | UMAP/t-SNE 降维散点图 |
| `pca` | PCA 主成分分析图 |
| `dendrogram` | 层次聚类树状图（含 WGCNA 分析） |
| `genome-track` | 基因组轨道图（IGV 视图风格） |
| `seq-logo` | 序列特征图谱（Logo/Motif） |
| `alluvial-cohort` | 队列演变/亚群流转图 |
| `composition-bar` | 物种或细胞构成比堆叠柱状图 |
| `composition-area` | 构成比堆叠面积图（有序条件下的组分比例动态） |
| `raincloud` | 云雨图（整合小提琴图、散点抖动与箱线图） |
| `paired-line` | 配对连线图（成对样本处理前后对比） |
| `waterfall` | 瀑布图（展示治疗响应深度等指标） |
| `table-figure` | 图版化表格（整合排版的数据面板） |

## data_shape 书写建议

本字段虽采用自由文本格式，但须遵循统一的前缀规范，后接具体的列名与结构说明：

- **宽矩阵**：行对应特征（如基因或代谢物），列对应样本 → 如「wide matrix: rows=genes, cols=samples + 分组注释表」
- **长表**：单行记录单次观测 → 如「long: value, group（两列起）」
- **汇总表**：已预先计算的聚合统计量 → 如「summary: group, mean, sd, n」
- **成对数据**：针对同一观测对象的配对测量数据 → 「paired: subject, pre, post」
- **两列差异结果**：包含表达倍数变化与统计显著性 → 「DE result: gene, log2FC, padj」
- **富集结果**：功能通路与对应的关联统计量 → 「enrichment: term, category, gene_ratio, padj, count」
- **邻接/网络**：网络拓扑与节点互作边表 → 「edges: from, to, weight」
- **基因组区间/位点**：「loci: chrom, pos, pvalue」

data_shape 的书写基准在于：读者在脱离原图的情况下，仅凭此行说明即可判定自有数据能否直接适配套用。
