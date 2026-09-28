#!/usr/bin/env python3
"""项目绘图样式体检：找出色板/主题/尺寸的重复与冲突，产出**偏好候选**。

定位（重要）：这是**只读诊断**，不生成代码、不改脚本、不要求任何共享依赖。
每个绘图脚本/条目模板都应当**自包含**（单独拿出来就能跑）；项目内的风格一致靠
`library/PREFERENCES.md` 的偏好约束 + agent 写作时遵守，**不靠脚本互相引用**。
把脚本耦合到一个共享 theme 文件会破坏这种独立性——所以本工具不提供 emit/migrate。

它回答三个问题：
  1. 同一套色板在多少个脚本里各写了一遍（重复 → 值得写成一条项目偏好）
  2. 有没有**同名不同色**（同一个变量名指向不同色号集合 → 最危险的隐性不一致）
  3. 基础主题/画布尺寸/导出规格有多散（散 → 值得统一成偏好）

用法:
    style_tokens.py CODE_DIR            # 诊断报告 + 可直接粘贴的偏好候选
    style_tokens.py CODE_DIR --suggest  # 只输出偏好候选
    style_tokens.py CODE_DIR --json
    style_tokens.py CODE_DIR --glob "*.py"
"""
import argparse
import collections
import datetime
import json
import os
import re
import sys

HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
# R 里色值普遍带引号：Normal = "#8B9DAF"。不认引号就会把色板的名字全丢掉。
NAMED_COLOR = re.compile(r"""([A-Za-z_][\w.]*|'[^']+'|"[^"]+")\s*=\s*["']?(#[0-9A-Fa-f]{6})["']?""")
BASE_THEME = re.compile(r"\btheme_(classic|bw|void|minimal|light|dark|linedraw|gray)\s*\(")
EXPORT = re.compile(r"\b(ggsave|cairo_pdf|pdf|jpeg|png|tiff|svglite)\s*\(([^)]{0,300})")
NUM = re.compile(r"\b(width|height|dpi|res|quality|units|base_size|pointsize)\s*=\s*([0-9.]+|\"[a-z]+\")")
# 捕获组：anon=匿名的 values = c(...)；name+op=具名定义（<- 或 =，两者语义不同）
PALETTE_START = re.compile(r"(?:(?P<anon>values\s*=\s*)|(?P<name>[A-Za-z_][\w.]*)\s*(?P<op><-|=)\s*)c\(")


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def code_mask(text: str) -> list:
    """标记哪些字符在 R 代码区（True），注释或字符串里为 False。

    脚本里常有被注释掉的旧定义（`# pal <- c(...)`），匹配时必须跳过，否则会改到注释。
    """
    mask = [True] * len(text)
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "#":
            j = text.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                mask[k] = False
            i = j
        elif ch in "\"'":
            quote, j = ch, i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    break
                j += 1
            for k in range(i, min(j + 1, n)):
                mask[k] = False
            i = min(j + 1, n)
        else:
            i += 1
    return mask


def _balanced_body(text: str, open_idx: int, mask: list = None):
    """从 '(' 取到配对的 ')'，支持跨行与嵌套；只在代码区数括号。"""
    depth = 0
    for i in range(open_idx, len(text)):
        if mask is not None and not mask[i]:
            continue
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:i]
    return ""


def collect_files(code_dir: str, globs: list) -> list:
    out = []
    for root, _dirs, files in os.walk(code_dir):
        for fn in sorted(files):
            if fn.startswith(".") or fn.endswith((".bak", "~")):
                continue
            if any(re.fullmatch(g.replace("*", ".*"), fn) for g in globs):
                out.append(os.path.join(root, fn))
    return sorted(out)


def extract_palettes(text: str, rel: str) -> list:
    """抓 `name <- c(...)`、`name = c(...)` 与 `values = c(...)` 三类色板定义。"""
    out, mask = [], code_mask(text)
    for m in PALETTE_START.finditer(text):
        if not mask[m.start()]:
            continue  # 注释里的旧定义不算
        name = m.group("name")
        body = _balanced_body(text, m.end() - 1, mask)
        colors = HEX.findall(body)
        if len(colors) < 2:
            continue
        lineno = text[:m.start()].count("\n") + 1
        named = {k.strip("'\""): v for k, v in NAMED_COLOR.findall(body)}
        out.append({"name": name or f"inline@{rel}:{lineno}", "file": rel, "line": lineno,
                    "op": m.group("op") or "=", "n": len(colors), "colors": colors,
                    "named": named, "anonymous": name is None})
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
    """按「色号序列」归并同一套色板（顺序不同视为不同色板）。"""
    groups = {}
    for s in scans:
        for p in s["palettes"]:
            key = tuple(p["colors"])
            g = groups.setdefault(key, {"colors": p["colors"], "names": collections.Counter(),
                                        "files": [], "named": {}})
            g["names"][p["name"]] += 1
            g["files"].append(p["file"])
            for k, v in p["named"].items():
                g["named"].setdefault(v, k)
    out = []
    for g in groups.values():
        name = g["names"].most_common(1)[0][0]
        out.append({"name": name, "colors": list(dict.fromkeys(g["colors"])),
                    "files": sorted(set(g["files"])), "named": g["named"],
                    "aliases": sorted(g["names"]),
                    "anonymous": all(a.startswith("inline@") for a in g["names"])})
    out.sort(key=lambda x: (-len(x["files"]), -len(x["colors"]), x["name"]))
    return out


CODE_DIR_NAMES = {"code", "codes", "scripts", "script", "src", "r", "analysis", "figures"}


def project_name(code_dir: str) -> str:
    """偏好里要标"适用范围：哪个项目"，传进来的通常是 <项目>/code，取上一级做项目名。"""
    path = os.path.normpath(code_dir)
    base = os.path.basename(path)
    if base.lower() in CODE_DIR_NAMES:
        parent = os.path.basename(os.path.dirname(path))
        if parent:
            return parent
    return base


def preference_candidates(canon: list, themes, sizes, code_dir: str, today: str,
                          min_files: int = 2) -> list:
    """把体检结论翻译成「可写进 PREFERENCES.md 的偏好候选」。

    措辞里明确写「脚本内保持自包含定义」——风格一致靠偏好约束，不靠共享依赖。
    """
    proj = project_name(code_dir)
    out = []
    name_map = collections.defaultdict(list)
    for p in canon:
        name_map[p["name"]].append(p)

    for p in canon:
        if p["anonymous"] or len(p["files"]) < min_files:
            continue
        colors = " / ".join(p["colors"][:8]) + (" …" if len(p["colors"]) > 8 else "")
        out.append(f"- {proj} 统一色板 `{p['name']}`（{len(p['colors'])} 色）：{colors}"
                   f"〔{today} style_tokens 体检，{len(p['files'])} 个脚本重复定义，"
                   f"适用范围：{proj}；脚本内保持自包含定义，不要引入共享 theme 依赖〕")

    for name, ps in sorted(name_map.items()):
        if len(ps) < 2:
            continue
        detail = "；".join(f"{len(q['colors'])} 色（{', '.join(q['files'][:3])}）" for q in ps)
        out.append(f"- ⚠ 待裁决：`{name}` 同名不同色——{detail}"
                   f"〔{today} style_tokens 体检，适用范围：{proj}；先定哪一版为准，再写入偏好〕")

    if len(themes) > 1:
        top = "、".join(f"{k}×{v}" for k, v in themes.most_common())
        out.append(f"- {proj} 基础主题统一为 `theme_{themes.most_common(1)[0][0]}`"
                   f"（当前混用：{top}）〔{today} style_tokens 体检，适用范围：{proj}〕")
    for key in ("width", "height", "dpi", "res", "quality"):
        vals = sizes.get(key)
        if vals and len(vals) > 2:
            top = "、".join(f"{v}×{c}" for v, c in vals.most_common(4))
            out.append(f"- {proj} 导出规格 `{key}` 统一（当前分布：{top}）"
                       f"〔{today} style_tokens 体检，适用范围：{proj}〕")
    return out


def render_report(scans, canon, cands, code_dir, today) -> str:
    all_colors = collections.Counter()
    for s in scans:
        all_colors.update(s["colors"])
    themes = collections.Counter()
    for s in scans:
        themes.update(s["themes"])
    exports, sizes = collections.Counter(), collections.defaultdict(collections.Counter)
    for s in scans:
        for e in s["exports"]:
            exports[e["fn"]] += 1
            for k, v in e["spec"].items():
                sizes[k][v] += 1

    L = [f"# 绘图样式体检（{today}）", "",
         f"扫描目录: {code_dir}　脚本 {len(scans)} 个，共 {sum(s['lines'] for s in scans)} 行",
         f"十六进制色值出现 {sum(all_colors.values())} 次，唯一色号 {len(all_colors)} 个", "",
         "> 本报告是**只读诊断**：产出偏好候选，不改代码、不生成共享依赖。",
         "> 每个脚本/模板保持自包含；项目内风格一致靠 `library/PREFERENCES.md` 的偏好约束。", ""]

    L += ["## 1. 色板清单（按色号序列归并）"]
    for p in canon[:20]:
        tag = "（匿名内联）" if p["anonymous"] else ""
        L.append(f"- `{p['name']}`{tag}：{len(p['colors'])} 色，{len(p['files'])} 个脚本"
                 + (f"，别名 {', '.join(p['aliases'][:4])}" if len(p["aliases"]) > 1 else ""))
        L.append(f"    {' '.join(p['colors'][:10])}" + (" …" if len(p["colors"]) > 10 else ""))
    if not canon:
        L.append("- （没找到成组色板定义）")
    L.append("")

    dup = [p for p in canon if len(p["files"]) > 1 and not p["anonymous"]]
    L += ["## 2. 重复定义（同一套色在多个脚本里各写一遍）",
          f"- {len(dup)} 套，共 {sum(len(p['files']) for p in dup)} 处"]
    for p in dup[:10]:
        L.append(f"  - `{p['name']}`：{', '.join(p['files'][:6])}" + (" …" if len(p["files"]) > 6 else ""))
    L.append("")

    name_map = collections.defaultdict(list)
    for p in canon:
        name_map[p["name"]].append(p)
    clashes = {n: ps for n, ps in name_map.items() if len(ps) > 1}
    L += ["## 3. 同名不同色（最危险的一类隐性不一致）"]
    if clashes:
        for n, ps in sorted(clashes.items()):
            L.append(f"- `{n}`：{len(ps)} 个版本")
            for q in ps:
                L.append(f"    - {len(q['colors'])} 色，用于 {', '.join(q['files'][:4])}"
                         + (" …" if len(q["files"]) > 4 else ""))
    else:
        L.append("- （无）")
    L.append("")

    L += ["## 4. 主题与导出规格分布",
          "- 基础主题: " + ("、".join(f"{k} {v}" for k, v in themes.most_common()) if themes else "（未检出）"),
          "- 导出函数: " + ("、".join(f"{k} {v}" for k, v in exports.most_common()) if exports else "（未检出）")]
    for key in ("width", "height", "dpi", "res", "quality"):
        if sizes[key]:
            L.append(f"- {key}: " + "、".join(f"{v}×{c}" for v, c in sizes[key].most_common(5)))
    L.append("")

    L += ["## 5. 建议写进偏好档案的条目（可直接粘贴，确认后再写入）"]
    L += cands or ["- （暂无可提炼的候选：色板没有跨脚本重复，也没有同名不同色）"]
    L += ["", "## 收尾",
          "1. 逐条判断：跨图型通用 → 写进 `PREFERENCES.md` 稳定偏好；只服务本项目 → 同样写进档案但**标适用范围**",
          "2. `⚠ 待裁决` 的同名不同色先定哪一版为准（这是真会画错的地方）",
          "3. **不要**为了让脚本一致而引入共享 theme 文件——脚本/模板保持自包含，一致性由偏好约束",
          "4. 整理动作与记录格式见 `references/preference-profile.md`"]
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("code_dir", help="脚本目录（如 <项目>/code）")
    parser.add_argument("--glob", action="append", default=[], metavar="PATTERN",
                        help="文件匹配（可重复，默认 *.R；Python 项目用 --glob '*.py'）")
    parser.add_argument("--suggest", action="store_true", help="只输出偏好候选")
    parser.add_argument("--min-files", type=int, default=2, metavar="N",
                        help="色板至少在 N 个脚本里重复出现才算候选（默认 2；想只看重点就调大）")
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
    themes, sizes = collections.Counter(), collections.defaultdict(collections.Counter)
    for s in scans:
        themes.update(s["themes"])
        for e in s["exports"]:
            for k, v in e["spec"].items():
                sizes[k][v] += 1
    today = datetime.date.today().isoformat()
    cands = preference_candidates(canon, themes, sizes, code_dir, today, args.min_files)

    if args.json:
        print(json.dumps({"dir": code_dir, "files": [s["file"] for s in scans],
                          "palettes": canon, "themes": dict(themes),
                          "preference_candidates": cands,
                          "unique_colors": sorted({c for s in scans for c in s["colors"]})},
                         ensure_ascii=False, indent=2))
        return 0
    if args.suggest:
        print("\n".join(cands) if cands else "（暂无可提炼的候选）")
        return 0

    print(render_report(scans, canon, cands, code_dir, today))
    return 0


if __name__ == "__main__":
    sys.exit(main())
