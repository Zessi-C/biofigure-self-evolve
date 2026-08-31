#!/usr/bin/env python3
"""把图库条目打包成可迁移的 bundle（zip），供目标机器用 import_figure.py 导入。

用法:
    export_figure.py 003                       # 数字前缀
    export_figure.py 003-umap-small-multiple-highlight
    export_figure.py all                       # 全部条目
    export_figure.py 001 002 -o bundle.zip --with-related --with-preferences

包结构:
    manifest.json                      # kind/bundle_version/entries(sha256)
    figures/<id>/<原文件名>             # 保留条目目录内相对位置
    PREFERENCES.md                     # 仅 --with-preferences 时
"""
import argparse
import datetime
import hashlib
import json
import os
import socket
import sys
import zipfile

from build_index import _as_list, parse_frontmatter, resolve_library

BUNDLE_KIND = "biofigure-bundle"
BUNDLE_VERSION = 1
OUTPUT_PREFIX = "template_output"  # 可再生的验证产物（含大 PDF），默认不入包


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def match_ids(requested: list, available: list):
    """把完整 id / 数字前缀解析为唯一条目。返回 (选中列表, 无法唯一匹配的输入)。"""
    selected, errors = [], []
    for req in requested:
        exact = [a for a in available if a == req]
        cands = exact or [a for a in available if a.startswith(req)]
        if len(cands) == 1:
            if cands[0] not in selected:
                selected.append(cands[0])
        else:
            errors.append(req)
    return sorted(selected), errors


def read_entry_meta(entry_dir: str):
    """读条目 figure.md 的 frontmatter；返回 (dict|None, 错误消息|None)。"""
    record_path = os.path.join(entry_dir, "figure.md")
    if not os.path.isfile(record_path):
        return None, "缺少 figure.md"
    with open(record_path, encoding="utf-8") as fh:
        return parse_frontmatter(fh.read())


def collect_files(entry_dir: str, with_outputs: bool) -> dict:
    """收集条目目录内所有文件；返回 {相对路径: 绝对路径}。

    默认排除文件名以 template_output 开头的验证产物（可再生，且含大 PDF）。
    """
    files = {}
    for dirpath, _dirnames, filenames in os.walk(entry_dir):
        for fn in filenames:
            if not with_outputs and fn.startswith(OUTPUT_PREFIX):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, entry_dir).replace(os.sep, "/")
            files[rel] = full
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="+", metavar="ID",
                        help="条目 id、数字前缀（如 003）或字面量 all")
    parser.add_argument("-o", "--output", help="输出 zip 路径（默认当前目录自动生成）")
    parser.add_argument("--with-related", action="store_true",
                        help="把 related 指向的库内条目也纳入（递归一层）")
    parser.add_argument("--with-preferences", action="store_true",
                        help="把图库根的 PREFERENCES.md 放进包")
    parser.add_argument("--with-outputs", action="store_true",
                        help="不排除 template_output* 验证产物")
    parser.add_argument("--library", help="图库根目录")
    args = parser.parse_args()

    root = resolve_library(args.library)
    fig_dir = os.path.join(root, "figures")
    if not os.path.isdir(fig_dir):
        print(f"错误: 未找到图库 {root}（缺 figures/）。先运行 init_library.py。", file=sys.stderr)
        return 1
    available = sorted(
        n for n in os.listdir(fig_dir) if os.path.isdir(os.path.join(fig_dir, n))
    )
    if not available:
        print(f"错误: 图库 {root} 没有任何条目可导出。", file=sys.stderr)
        return 1

    if "all" in args.ids:
        selected = list(available)
    else:
        selected, errors = match_ids(args.ids, available)
        if errors:
            for req in errors:
                print(f"错误: {req!r} 无法唯一匹配条目（不存在或有多个前缀匹配）。", file=sys.stderr)
            return 1

    # 读 frontmatter；缺 figure.md 的条目报错跳过
    metas, skipped = {}, []
    for eid in selected:
        meta, err = read_entry_meta(os.path.join(fig_dir, eid))
        if meta is None:
            print(f"错误: {eid}: {err}，该条目跳过。", file=sys.stderr)
            skipped.append(eid)
            continue
        metas[eid] = meta

    # related 处理（只追一层，不再追 related 的 related）
    selected_set = set(metas)
    related_missing = set()
    for eid in sorted(metas):
        for rid in _as_list(metas[eid].get("related")):
            if rid in available and rid not in selected_set:
                related_missing.add(rid)
    if args.with_related:
        for rid in sorted(related_missing):
            meta, err = read_entry_meta(os.path.join(fig_dir, rid))
            if meta is None:
                print(f"错误: {rid}（related 引入）: {err}，该条目跳过。", file=sys.stderr)
                skipped.append(rid)
                continue
            metas[rid] = meta
    elif related_missing:
        print(f"提示: 选中条目的 related 还指向库内条目 {', '.join(sorted(related_missing))}，"
              f"本次未包含；如需一并导出请加 --with-related。", file=sys.stderr)

    if not metas:
        print("错误: 没有任何可导出的条目。", file=sys.stderr)
        return 1

    # 偏好档案
    pref_path = os.path.join(root, "PREFERENCES.md")
    include_pref = False
    if args.with_preferences:
        if os.path.isfile(pref_path):
            include_pref = True
        else:
            print("警告: 已指定 --with-preferences，但图库根没有 PREFERENCES.md，未包含。",
                  file=sys.stderr)

    # 组装条目清单与文件哈希
    entries, entry_files = [], {}
    for eid in sorted(metas):
        files = collect_files(os.path.join(fig_dir, eid), args.with_outputs)
        entry_files[eid] = files
        entries.append({
            "id": eid,
            "title": str(metas[eid].get("title", "")),
            "files": {rel: sha256_file(full) for rel, full in files.items()},
        })

    # 输出路径
    if args.output:
        out_path = os.path.abspath(os.path.expanduser(args.output))
    else:
        id_part = "all" if "all" in args.ids else "_".join(sorted(metas))
        if len(id_part) > 40:
            id_part = id_part[:40]
        out_path = os.path.abspath(
            f"biofigure-bundle-{datetime.date.today():%Y%m%d}-{id_part}.zip"
        )
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    manifest = {
        "kind": BUNDLE_KIND,
        "bundle_version": BUNDLE_VERSION,
        "exported_at": datetime.datetime.now().astimezone().isoformat(),
        "exported_from": socket.gethostname(),
        "preferences_included": include_pref,
        "entries": entries,
    }
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        for eid in sorted(metas):
            for rel, full in entry_files[eid].items():
                zf.write(full, f"figures/{eid}/{rel}")
        if include_pref:
            zf.write(pref_path, "PREFERENCES.md")

    print(f"已导出 {len(entries)} 个条目: {out_path}")
    for e in entries:
        print(f"  - {e['id']}  {e['title']}（{len(e['files'])} 个文件）")
    if include_pref:
        print("  - PREFERENCES.md（偏好档案）")
    print("下一步: 把 zip 传到目标机器（如 scp / rsync），"
          f"然后运行 scripts/import_figure.py {os.path.basename(out_path)} --library <图库>。")
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
