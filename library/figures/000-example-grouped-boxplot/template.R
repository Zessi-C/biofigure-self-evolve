# 000-example-grouped-boxplot — 分组箱线 + 抖动散点 + 显著性括线（R / ggplot2 模板）
# 本条目是发布示例：演示 figure.md 配方 ↔ 模板代码的对应关系。复用时替换示例数据块。

suppressPackageStartupMessages(library(ggplot2))

outdir <- {
  a <- commandArgs(); f <- grep("^--file=", a, value = TRUE)
  if (length(f)) dirname(normalizePath(sub("^--file=", "", f))) else getwd()
}

## ---------- 构造示例数据（复用时替换为你的长表：group, value） ----------
set.seed(1)
groups <- c("Control", "Low dose", "High dose")
df <- data.frame(
  group = factor(rep(groups, each = 30), levels = groups),
  value = c(rnorm(30, 5, 1.2), rnorm(30, 6.2, 1.4), rnorm(30, 7.1, 1.1)))
## -----------------------------------------------------------

pal <- setNames(c("#4C72B0", "#DD8452", "#55A868"), groups)
pv <- with(df, wilcox.test(value ~ group, subset = group %in% groups[1:2])$p.value)  # 示例只检验前两组
star <- function(p) cut(p, c(-Inf, 0.001, 0.01, 0.05, Inf),
                       labels = c("***", "**", "*", "ns"), right = FALSE)

top <- max(df$value)
p <- ggplot(df, aes(group, value, fill = group)) +
  geom_jitter(width = 0.12, alpha = 0.45, size = 1.4, color = "grey35") +
  geom_boxplot(outlier.shape = NA, alpha = 0.55, linewidth = 0.4,
               fatten = 1.1, show.legend = FALSE) +
  scale_fill_manual(values = pal) +
  annotate("segment", x = 1, xend = 2, y = top * 1.06, yend = top * 1.06, linewidth = 0.4) +
  annotate("segment", x = 1, xend = 1, y = top * 1.06, yend = top * 1.035, linewidth = 0.4) +
  annotate("segment", x = 2, xend = 2, y = top * 1.06, yend = top * 1.035, linewidth = 0.4) +
  annotate("text", x = 1.5, y = top * 1.085, label = star(pv), size = 4) +
  scale_y_continuous(expand = expansion(mult = c(0.05, 0.15))) +
  labs(x = NULL, y = "Value") +
  theme_classic(base_size = 11) + theme(legend.position = "none")

ggsave(file.path(outdir, "template_output_r.png"), p, width = 4.2, height = 4.2, dpi = 300)
ggsave(file.path(outdir, "template_output_r.pdf"), p, width = 4.2, height = 4.2)
cat("OK: template_output_r.png / template_output_r.pdf\n")
