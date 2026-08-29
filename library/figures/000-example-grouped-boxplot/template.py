# 000-example-grouped-boxplot — 分组箱线 + 抖动散点 + 显著性括线（Python / matplotlib 模板）
# 本条目是发布示例：演示 figure.md 配方 ↔ 模板代码的对应关系。复用时替换示例数据块。

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

outdir = Path(__file__).resolve().parent

# ---------- 构造示例数据（复用时替换为你的长表：group, value） ----------
rng = np.random.default_rng(1)
groups = ["Control", "Low dose", "High dose"]
df = pd.DataFrame({
    "group": np.repeat(groups, 30),
    "value": np.concatenate([rng.normal(5, 1.2, 30), rng.normal(6.2, 1.4, 30), rng.normal(7.1, 1.1, 30)]),
})
df["group"] = pd.Categorical(df["group"], categories=groups, ordered=True)  # 组序=展示序
# -----------------------------------------------------------

try:
    from scipy import stats as _st
    pv = _st.mannwhitneyu(df.loc[df.group == groups[0], "value"],
                          df.loc[df.group == groups[1], "value"]).pvalue
except ImportError:                                   # 无 scipy 时给个占位 p
    pv = 0.03

def star(p):
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"

PAL = ["#4C72B0", "#DD8452", "#55A868"]
fig, ax = plt.subplots(figsize=(4.2, 4.2))
for i, g in enumerate(groups):
    v = df.loc[df.group == g, "value"]
    ax.scatter(rng.uniform(i - 0.12, i + 0.12, len(v)), v, s=14, c="#595959", alpha=0.45, linewidths=0)
    ax.boxplot(v, positions=[i], widths=0.5, showfliers=False, patch_artist=True,
               boxprops=dict(facecolor=PAL[i], alpha=0.55, edgecolor="black", lw=0.8),
               medianprops=dict(color="black", lw=1.4),
               whiskerprops=dict(lw=0.8), capprops=dict(lw=0.8))

top = df.value.max()
ax.plot([0, 1], [top * 1.06] * 2, lw=0.8, c="black")        # 括线
ax.plot([0, 0], [top * 1.035, top * 1.06], lw=0.8, c="black")
ax.plot([1, 1], [top * 1.035, top * 1.06], lw=0.8, c="black")
ax.text(0.5, top * 1.075, star(pv), ha="center", fontsize=11)
ax.set_ylim(df.value.min() * 0.9, top * 1.15)
ax.set_xticks(range(len(groups))); ax.set_xticklabels(groups)
ax.set_ylabel("Value")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(outdir / "template_output_p.png", dpi=300)
fig.savefig(outdir / "template_output_p.pdf")
print("OK: template_output_p.png / template_output_p.pdf")
