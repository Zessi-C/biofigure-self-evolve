# chart_types 受控词表与数据形状词表

`chart_types` 必须从下表选词（可多值），保证学习与检索两端用同一套语言。新图类型确实不在表内时可自造 kebab-case 新词，并考虑把词补进本文件。

## 图类型词表

| 词 | 图 |
|---|---|
| `heatmap` | 热图（含聚类热图、注释条版式） |
| `volcano` | 火山图 |
| `ma-plot` | MA 图 |
| `boxplot` | 箱线图 |
| `violin` | 小提琴图 |
| `barplot` | 柱状图/条形图（含堆叠、分组） |
| `line` | 折线/时间序列 |
| `scatter` | 散点/相关图 |
| `enrichment-dotplot` | 富集分析点图/气泡图（GO/KEGG/Reactome） |
| `gsea-runplot` | GSEA running-score 曲线 |
| `kegg-map` | KEGG 通路图上色 |
| `survival-km` | KM 生存曲线 |
| `risk-plot` | 生存风险评分图（散点+状态+热图组合） |
| `forest` | 森林图（Cox/回归/meta） |
| `roc` | ROC 曲线 |
| `nomogram` | 列线图 |
| `oncoprint` | 突变全景图（oncoPrint） |
| `circos` | 圈图 |
| `manhattan` | 曼哈顿图 |
| `qq-plot` | Q-Q 图 |
| `venn` | 韦恩图 |
| `upset` | UpSet 图 |
| `network` | 网络/通路互作图 |
| `sankey` | 桑基/冲积图 |
| `chord` | 弦图 |
| `umap-tsne` | UMAP/t-SNE 降维散点 |
| `pca` | PCA 图 |
| `dendrogram` | 聚类树状图（含 WGCNA） |
| `genome-track` | 基因组轨道/IGV 风格 |
| `seq-logo` | 序列 logo/motif |
| `alluvial-cohort` | 队列流动/分组流转图 |
| `composition-bar` | 物种/细胞构成比堆叠条 |
| `composition-area` | 构成比堆叠面积/连线（有序条件下的比例趋势） |
| `raincloud` | 云雨图（小提琴+散点+箱线） |
| `paired-line` | 配线图（配对样本前后对比） |
| `waterfall` | 瀑布图（响应深度等） |
| `table-figure` | 表格型图（排版的表格面板） |

## data_shape 书写建议

自由文本，但用这套词开头，后面跟具体列说明：

- **宽矩阵**：行=特征（基因/代谢物），列=样本 → 如「wide matrix: rows=genes, cols=samples + 分组注释表」
- **长表**：一行一个观测 → 如「long: value, group（两列起）」
- **汇总表**：已算好的统计量 → 如「summary: group, mean, sd, n」
- **成对数据**：同一观测两次测量 → 「paired: subject, pre, post」
- **两列差异结果**：FC + 显著性 → 「DE result: gene, log2FC, padj」
- **富集结果**：通路 × 统计量 → 「enrichment: term, category, gene_ratio, padj, count」
- **邻接/网络**：边表 → 「edges: from, to, weight」
- **基因组区间/位点**：「loci: chrom, pos, pvalue」

写 data_shape 的标准是：别人不看原图、只读这一行，就知道自己的数据能不能直接套。
