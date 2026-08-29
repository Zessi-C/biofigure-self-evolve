#!/usr/bin/env python3
"""扫描 figures/*/figure.md 的 frontmatter，重建 INDEX.json 与 INDEX.md。

优先使用 PyYAML；不可用时退回内置的受限解析器（只支持本技能 schema 约定的
子集：标量、单行 [列表]、source: 下一层 map），因此 figure.md 必须遵守
references/figure-record.md 的 frontmatter 语法限制。

用法:
    build_index.py                # 解析图库位置：--library > $BIOFIGURE_LIBRARY > config > ~/biofigure-library
    build_index.py --library DIR  # 显式指定图库
"""
import argparse
import datetime
import json
import os
import re
import sys

SKILL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_LIBRARY = os.path.join(SKILL_DIR, "library")
CONFIG_PATH = os.path.expanduser("~/.config/biofigure-self-evolve/config.json")

REQUIRED_FIELDS = [
    "id", "title", "aliases", "chart_types", "data_shape",
    "use_when", "not_when", "layout", "languages", "packages", "verified",
]
SOURCE_FIELDS = ["type", "title", "ref", "panel", "learned_date"]


def resolve_library(explicit: str) -> str:
    if explicit:
        return os.path.abspath(os.path.expanduser(explicit))
    if os.environ.get("BIOFIGURE_LIBRARY"):
        return os.path.abspath(os.path.expanduser(os.environ["BIOFIGURE_LIBRARY"]))
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                p = json.load(f).get("library_path")
            if p:
                return os.path.abspath(os.path.expanduser(p))
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_LIBRARY


def _parse_scalar(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_unquote(x.strip()) for x in inner.split(",") if x.strip()]
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return _unquote(raw)


def _unquote(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def _as_list(v):
    """列表字段容错：手写成标量时包成单元素列表，避免后续按字符迭代。"""
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return v
    return [v]


def parse_frontmatter(text: str):
    """返回 (dict|None, 错误消息|None)。无 PyYAML 时用受限解析器。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "缺少 frontmatter 起始 ---"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, "frontmatter 未闭合"

    body = "\n".join(lines[1:end])
    try:
        import yaml  # type: ignore
        return yaml.safe_load(body), None
    except ImportError:
        pass

    data, current_map = {}, None
    for lineno, line in enumerate(lines[1:end], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            return None, f"第 {lineno} 行无法解析: {stripped!r}"
        key, raw = stripped.split(":", 1)
        key, raw = key.strip(), raw.strip()
        if line.startswith((" ", "\t")):  # source: 的下一层
            if current_map is None:
                return None, f"第 {lineno} 行缩进层级超出 schema（只允许 source: 下一层）"
            current_map[key] = _parse_scalar(raw) if raw else ""
            continue
        current_map = None
        if raw == "":
            data[key] = {}
            current_map = data[key]
        else:
            data[key] = _parse_scalar(raw)
    return data, None


def build_index_md(figures: list) -> str:
    lines = [
        "# Biofigure Library 索引",
        "",
        f"共 {len(figures)} 条记录。生成于 {datetime.date.today().isoformat()}（由 scripts/build_index.py 维护，勿手改）。",
        "",
        "| id | 标题 | chart_types | languages | verified |",
        "|---|---|---|---|---|",
    ]
    for f in figures:
        lines.append(
            f"| `{f['id']}` | {f['title']} | {', '.join(f['chart_types'])} "
            f"| {', '.join(f['languages'])} | {f['verified']} |"
        )
    lines += ["", "## 各条目详情", ""]
    for f in figures:
        lines += [
            f"### `{f['id']}` — {f['title']}",
            "",
            f"- **别名**: {', '.join(f['aliases'])}",
            f"- **数据形状**: {f['data_shape']}",
            f"- **适用**: {f['use_when']}",
            f"- **不适用**: {f['not_when']}",
            f"- **排版**: {f['layout']}",
        ]
        if f.get("related"):
            lines.append(f"- **相近条目**: {', '.join('`%s`' % r for r in f['related'])}")
        lines += [
            f"- **来源**: {f['source_type']} — {f['source_title']}",
            f"- **目录**: `{f['dir']}`",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", help="图库根目录")
    args = parser.parse_args()

    root = resolve_library(args.library)
    fig_dir = os.path.join(root, "figures")
    if not os.path.isdir(fig_dir):
        print(f"错误: 未找到图库 {root}（缺 figures/）。先运行 init_library.py。", file=sys.stderr)
        return 1

    records, warnings = [], []
    for name in sorted(os.listdir(fig_dir)):
        record_path = os.path.join(fig_dir, name, "figure.md")
        if not os.path.isdir(os.path.join(fig_dir, name)):
            continue
        if not os.path.exists(record_path):
            warnings.append(f"{name}: 目录缺少 figure.md，已跳过（不是完整条目）")
            continue
        with open(record_path, encoding="utf-8") as fh:
            data, err = parse_frontmatter(fh.read())
        if data is None:
            warnings.append(f"{name}: 解析失败 — {err}")
            continue
        missing = [k for k in REQUIRED_FIELDS if k not in data or data[k] in ("", [])]
        if missing:
            warnings.append(f"{name}: 缺少必填字段 {', '.join(missing)}")
        if data.get("id") != name:
            warnings.append(f"{name}: frontmatter id ({data.get('id')!r}) 与目录名不一致")
        source = data.get("source") or {}
        missing_src = [k for k in SOURCE_FIELDS if k not in source]
        if missing_src:
            warnings.append(f"{name}: source 缺少 {', '.join(missing_src)}")
        records.append({
            "id": data.get("id", name),
            "title": data.get("title", ""),
            "aliases": _as_list(data.get("aliases")),
            "chart_types": _as_list(data.get("chart_types")),
            "data_shape": data.get("data_shape", ""),
            "use_when": data.get("use_when", ""),
            "not_when": data.get("not_when", ""),
            "layout": data.get("layout", ""),
            "languages": _as_list(data.get("languages")),
            "verified": data.get("verified", "unverified"),
            "related": _as_list(data.get("related")),
            "packages": _as_list(data.get("packages")),
            "source_type": source.get("type", ""),
            "source_title": source.get("title", ""),
            "dir": f"figures/{name}",
        })

    records.sort(key=lambda r: r["id"])

    all_ids = {r["id"] for r in records}
    for r in records:
        dangling = [rid for rid in r["related"] if rid not in all_ids]
        if dangling:
            warnings.append(f"{r['id']}: related 指向不存在的条目 {', '.join(dangling)}")

    today = datetime.date.today().isoformat()
    index = {"version": 1, "updated": today, "figures": records}

    with open(os.path.join(root, "INDEX.json"), "w", encoding="utf-8") as fh:
        # default=str 兜底：PyYAML 会把日期解析成 date 对象，直写 JSON 会崩
        json.dump(index, fh, ensure_ascii=False, indent=2, default=str)
        fh.write("\n")
    with open(os.path.join(root, "INDEX.md"), "w", encoding="utf-8") as fh:
        fh.write(build_index_md(records) + "\n")

    print(f"图库: {root}")
    print(f"已重建 INDEX.json / INDEX.md，共 {len(records)} 条记录。")
    if warnings:
        print(f"\n{len(warnings)} 条警告:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
