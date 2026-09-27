#!/usr/bin/env python3
"""项目绘图样式体检 + 生成共享 theme 文件（把 house style 从"靠记"变成"跑不掉"）。

真实项目里同一套配色/主题/尺寸会在几十个脚本里各写一遍：本项目 26 个绘图脚本里有
652 处十六进制色值、144 个唯一色号、基础主题混用 theme_classic/theme_bw/theme_void。
偏好写在 PREFERENCES.md 里还要靠 agent 每次记得用，写进共享 theme 文件则强制生效。

用法:
    style_tokens.py CODE_DIR                      # 体检报告：色板清单、重复定义、主题/尺寸分布
    style_tokens.py CODE_DIR --emit 00.figure_theme.R   # 生成共享 theme 文件
    style_tokens.py CODE_DIR --json
    style_tokens.py CODE_DIR --glob "*.R" --glob "*.py"

只读 + 生成一个新文件；不改任何既有脚本。
"""
import argparse
import collections
import datetime
import json
import os
import re
import sys

HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
NAMED_COLOR = re.compile(r"([A-Za-z_][\w.]*|'[^']+'|\"[^\"]+\")\s*=\s*(#[0-9A-Fa-f]{6})")
BASE_THEME = re.compile(r"\btheme_(classic|bw|void|minimal|light|dark|linedraw|gray)\s*\(")
EXPORT = re.compile(r"\b(ggsave|cairo_pdf|pdf|jpeg|png|tiff|svglite)\s*\(([^)]{0,300})")
NUM = re.compile(r"\b(width|height|dpi|res|quality|units|base_size|pointsize)\s*=\s*([0-9.]+|\"[a-z]+\")")


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def collect_files(code_dir: str, globs: list) -> list:
    out = []
    for root, _dirs, files in os.walk(code_dir):
        for fn in sorted(files):
            if any(re.fullmatch(g.replace("*", ".*"), fn) for g in globs):
                out.append(os.path.join(root, fn))
    return sorted(out)


def _balanced_body(text: str, open_idx: int):
    """从 '(' 的位置取到配对的 ')'，支持跨行与嵌套。"""
    depth = 0
    for i in range(open_idx, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:i]
    return ""


PALETTE_START = re.compile(r"(?:values\s*=\s*|([A-Za-z_][\w.]*)\s*(?:<-|=)\s*)c\(")


def extract_palettes(text: str, rel: str) -> list:
    """抓 `name <- c(...)` 与 `scale_*_manual(values = c(...))` 两类色板定义。

    用括号配对而不是正则贪婪匹配：色板定义经常跨行、还会嵌套 c()。
    """
    out = []
    for m in PALETTE_START.finditer(text):
        name = m.group(1)
        body = _balanced_body(text, m.end() - 1)
        colors = HEX.findall(body)
        if len(colors) < 2:
            continue
        lineno = text[:m.start()].count("\n") + 1
        named = {k.strip("'\""): v for k, v in NAMED_COLOR.findall(body)}
        out.append({"name": name or f"palette_{rel}:{lineno}", "file": rel, "line": lineno,
                    "n": len(colors), "colors": colors, "named": named,
                    "anonymous": name is None})
    return out


def scan_file(path: str, code_dir: str) -> dict:
    text = read(path)
    rel = os.path.relpath(path, code_dir)
    return {
        "file": rel,
        "palettes": extract_palettes(text, rel),
        "colors": collections.Counter(HEX.findall(text)),
        "themes": collections.Counter(BASE_THEME.findall(text)),
        "exports": [{"fn": m.group(1), "spec": dict(NUM.findall(m.group(2)))} for m in EXPORT.finditer(text)],
        "lines": text.count("\n") + 1,
    }


def canonical_palettes(scans: list) -> list:
    """按"色号集合"归并同一套色板（不同脚本里名字不同也算同一套）。"""
    groups = {}
    for s in scans:
        for p in s["palettes"]:
            key = tuple(sorted(set(p["colors"])))
            g = groups.setdefault(key, {"colors": p["colors"], "named": {}, "names": collections.Counter(),
                                        "files": [], "n": p["n"]})
            g["names"][p["name"]] += 1
            g["files"].append(p["file"])
            for k, v in p["named"].items():
                g["named"].setdefault(v, k)
    out = []
    for key, g in groups.items():
        # 名字取出现次数最多的；同一色号若在别处有语义名，沿用语义名
        name = g["names"].most_common(1)[0][0]
        ordered = list(dict.fromkeys(g["colors"]))
        out.append({"name": name, "colors": ordered, "files": sorted(set(g["files"])),
                    "named": g["named"], "aliases": sorted(g["names"]),
                    "anonymous": all(a.startswith("palette_") for a in g["names"])})
    out.sort(key=lambda x: (-len(x["files"]), -x["colors"].__len__(), x["name"]))
    return out


def render_report(scans: list, canon: list, code_dir: str) -> str:
    all_colors = collections.Counter()
    for s in scans:
        all_colors.update(s["colors"])
    themes = collections.Counter()
    for s in scans:
        themes.update(s["themes"])
    exports = collections.Counter()
    sizes = collections.defaultdict(collections.Counter)
    for s in scans:
        for e in s["exports"]:
            exports[e["fn"]] += 1
            for k, v in e["spec"].items():
                sizes[k][v] += 1
    L = [f"# 绘图样式体检（{datetime.date.today().isoformat()}）", "",
         f"扫描目录: {code_dir}　脚本 {len(scans)} 个，共 {sum(s['lines'] for s in scans)} 行",
         f"十六进制色值出现 {sum(all_colors.values())} 次，唯一色号 {len(all_colors)} 个", ""]
    L += ["## 1. 色板定义（按色号集合归并）"]
    for i, p in enumerate(canon[:20], 1):
        L.append(f"- `{p['name']}`（{len(p['colors'])} 色，{len(p['files'])} 个脚本"
                 + (f"，别名 {', '.join(p['aliases'][:4])}" if len(p["aliases"]) > 1 else "") + "）")
        L.append(f"    {' '.join(p['colors'][:10])}" + (" …" if len(p["colors"]) > 10 else ""))
    if not canon:
        L.append("- （没找到成组色板定义；色值是散落的，更需要统一）")
    L.append("")
    dup = [p for p in canon if len(p["files"]) > 1]
    L += ["## 2. 重复定义（同一套色板在多个脚本里各写一遍）",
          f"- {len(dup)} 套色板被重复定义，共涉及 {sum(len(p['files']) for p in dup)} 处"]
    for p in dup[:10]:
        L.append(f"  - `{p['name']}`：{', '.join(p['files'][:6])}"
                 + (" …" if len(p["files"]) > 6 else ""))
    L.append("")
    L += ["## 3. 基础主题分布",
          "- " + "、".join(f"{k} {v}" for k, v in themes.most_common()) if themes else "- （未检出）"]
    L.append("")
    L += ["## 4. 导出规格"]
    L.append("- 函数: " + "、".join(f"{k} {v}" for k, v in exports.most_common()))
    for k in ("width", "height", "dpi", "res", "quality"):
        if sizes[k]:
            top = "、".join(f"{v}×{c}" for v, c in sizes[k].most_common(5))
            L.append(f"- {k}: {top}")
    L += ["", "## 5. 建议",
          "1. `--emit 00.figure_theme.R` 生成共享 theme 文件：把上面的色板去重成命名色板 + 统一主题 + 统一导出函数",
          "2. 新脚本 `source()` 它；旧脚本逐步迁移（迁移一个跑一个，别一次全改）",
          "3. 把跨图约定按 `references/preference-profile.md` 写进 `PREFERENCES.md`（标适用范围），并把 theme 文件路径写进条目「复用要点」",
          "4. 迁移完成后重跑本脚本：唯一色号数应明显下降（本项目当前 144 个）"]
    return "\n".join(L)


def emit_theme(canon: list, code_dir: str, out_path: str) -> str:
    named = [p for p in canon if not p.get("anonymous")]
    if named:
        canon = named
    today = datetime.date.today().isoformat()
    L = [f"# 项目绘图样式单一事实源 —— 由 biofigure style_tokens.py 生成（{today}）",
         f"# 来源: {code_dir}",
         "# 用法：绘图脚本里 source(\"code/00.figure_theme.R\")，然后只用这里定义的色板/主题/尺寸。",
         "# 手工改动请同步回本文件（它是唯一事实源，别在脚本里再写一套）。",
         "",
         "## 色板（去重后；名字取原脚本里最常见的那个）",
         "biofigure_palettes <- list("]
    for i, p in enumerate(canon):
        name = re.sub(r"[^A-Za-z0-9_.]", "_", p["name"])
        entries = []
        for c in p["colors"]:
            label = p["named"].get(c, "")
            entries.append(f'{label} = "{c}"' if label else f'"{c}"')
        sep = "," if i < len(canon) - 1 else ""
        L.append(f"  {name} = c({', '.join(entries)}){sep}")
    L += ["  )", "",
          "# 取色板：biofigure_pal(\"group_4group\")；缺名时报错而不是静默给错色",
          "biofigure_pal <- function(name) {",
          "  if (!name %in% names(biofigure_palettes)) {",
          "    stop(sprintf(\"Unknown palette '%s'. Known: %s\", name, paste(names(biofigure_palettes), collapse = \", \")))",
          "  }",
          "  biofigure_palettes[[name]]",
          "}", "",
          "## 主题：统一基础主题 + 常用微调（各脚本不再各写一套 theme()）",
          "biofigure_theme <- function(base_size = 11, base_family = \"\", legend_position = \"right\") {",
          "  ggplot2::theme_classic(base_size = base_size, base_family = base_family) +",
          "    ggplot2::theme(",
          "      axis.text = ggplot2::element_text(colour = \"grey20\"),",
          "      axis.title = ggplot2::element_text(colour = \"grey10\"),",
          "      axis.line = ggplot2::element_line(linewidth = 0.4, colour = \"grey30\"),",
          "      axis.ticks = ggplot2::element_line(linewidth = 0.4, colour = \"grey30\"),",
          "      strip.background = ggplot2::element_blank(),",
          "      strip.text = ggplot2::element_text(face = \"bold\"),",
          "      panel.grid = ggplot2::element_blank(),",
          "      legend.position = legend_position,",
          "      legend.key.size = grid::unit(0.35, \"cm\"),",
          "      plot.title = ggplot2::element_text(face = \"bold\", hjust = 0.5),",
          "      plot.margin = ggplot2::margin(6, 8, 6, 8)",
          "    )",
          "}", "",
          "## 尺寸：常用画布（英寸）。显式指定，别靠默认值。",
          "biofigure_size <- list(single = c(6, 5), wide = c(10, 5), tall = c(6, 9), square = c(6, 6))",
          "",
          "## 导出：默认 PDF 矢量；需要高清预览时额外出 JPG（600dpi, quality 100）",
          "biofigure_save <- function(plot, stem, width, height, jpg = FALSE, dpi = 600) {",
          "  grDevices::cairo_pdf(paste0(stem, \".pdf\"), width = width, height = height)",
          "  print(plot)",
          "  grDevices::dev.off()",
          "  if (isTRUE(jpg)) {",
          "    grDevices::jpeg(paste0(stem, \".jpg\"), width = width, height = height,",
          "                    units = \"in\", res = dpi, quality = 100)",
          "    print(plot)",
          "    grDevices::dev.off()",
          "  }",
          "  invisible(c(paste0(stem, \".pdf\"), if (isTRUE(jpg)) paste0(stem, \".jpg\")))",
          "}", ""]
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("code_dir", help="脚本目录（如 <项目>/code）")
    parser.add_argument("--glob", action="append", default=[], metavar="PATTERN",
                        help="文件匹配（可重复，默认 *.R；Python 项目用 --glob '*.py'）")
    parser.add_argument("--emit", metavar="PATH", help="生成共享 theme 文件到该路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    code_dir = os.path.abspath(os.path.expanduser(args.code_dir))
    if not os.path.isdir(code_dir):
        print(f"错误: 不是目录 {code_dir}", file=sys.stderr)
        return 1
    globs = args.glob or ["*.R"]
    files = collect_files(code_dir, globs)
    if not files:
        print(f"错误: {code_dir} 下没有匹配 {globs} 的文件", file=sys.stderr)
        return 1

    scans = [scan_file(p, code_dir) for p in files]
    canon = canonical_palettes(scans)

    if args.emit:
        out = os.path.abspath(os.path.expanduser(args.emit))
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        if os.path.exists(out):
            print(f"错误: {out} 已存在，先备份或改名（本脚本不覆盖已有文件）", file=sys.stderr)
            return 1
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(emit_theme(canon, code_dir, out))
        print(f"已生成 {out}（{len(canon)} 套去重色板）")
        print("下一步：挑一个绘图脚本改成 source() 它并重跑对比成图；确认一致后再逐个迁移。")
        return 0

    if args.json:
        print(json.dumps({"dir": code_dir, "files": [s["file"] for s in scans],
                          "canonical_palettes": canon,
                          "unique_colors": sorted({c for s in scans for c in s["colors"]}),
                          "themes": dict(collections.Counter(
                              {k: v for s in scans for k, v in s["themes"].items()}))},
                         ensure_ascii=False, indent=2))
        return 0

    print(render_report(scans, canon, code_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
