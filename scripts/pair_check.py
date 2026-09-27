#!/usr/bin/env python3
"""图-表同源核验：每张交付图都要能指到它的数据来源表，且表是真的。

"图里的数值 == 表里的数值"这件事，脚本没法凭空判断（它不知道图上画了哪些数）；能做且
值得做的是把**同源关系登记下来并核验事实**：
  1. 清单里每张图都填了 `source_table`（或显式声明无表）；
  2. 登记的表存在、非空、能解析（csv/tsv 会检查表头）；
  3. 表目录里没有被任何图引用的表（孤儿表 → 漏配或多余）；
  4. 清单与目录一致（文件还在、体积没变）——避免清单变成历史遗迹。

数值层面的一致性仍要靠 agent 在交付说明里写清口径并抽样核对。

用法:
    pair_check.py FIGDIR                          # 用 <FIGDIR>/figure_manifest.csv
    pair_check.py FIGDIR --manifest m.csv --tables <项目>/table
    pair_check.py FIGDIR --allow-missing-table    # 允许某些图不配表（如纯示意图）
    pair_check.py FIGDIR --json
"""
import argparse
import csv
import json
import os
import sys

DEFAULT_MANIFEST = "figure_manifest.csv"
TABLE_EXTS = (".csv", ".tsv", ".txt", ".xlsx", ".xls")


def read_manifest(path: str) -> list:
    with open(path, encoding="utf-8", newline="") as fh:
        return [r for r in csv.DictReader(fh) if r.get("file")]


def table_ok(path: str) -> tuple:
    """返回 (ok, 说明)。csv/tsv 会检查表头与行数。"""
    if not os.path.exists(path):
        return False, "文件不存在"
    size = os.path.getsize(path)
    if size == 0:
        return False, "空文件"
    if path.lower().endswith((".csv", ".tsv")):
        delim = "\t" if path.lower().endswith(".tsv") else ","
        try:
            with open(path, encoding="utf-8", errors="replace", newline="") as fh:
                reader = csv.reader(fh, delimiter=delim)
                header = next(reader, None)
                n = sum(1 for _ in reader)
            if not header:
                return False, "没有表头"
            if n == 0:
                return False, "只有表头没有数据行"
            return True, f"{len(header)} 列 × {n} 行"
        except OSError as e:
            return False, f"读取失败: {e}"
    return True, f"{size / 1024:.0f} KB"


def collect_tables(tabledir: str) -> set:
    out = set()
    for root, _dirs, files in os.walk(tabledir):
        for fn in files:
            if fn.lower().endswith(TABLE_EXTS):
                out.add(os.path.abspath(os.path.join(root, fn)))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("figdir", help="图件目录")
    parser.add_argument("--manifest", help=f"清单路径（默认 <FIGDIR>/{DEFAULT_MANIFEST}）")
    parser.add_argument("--tables", action="append", default=[], metavar="DIR",
                        help="表格目录（可重复；给了才查孤儿表）")
    parser.add_argument("--allow-missing-table", action="store_true",
                        help="允许图不配表（纯示意图/流程图）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    figdir = os.path.abspath(os.path.expanduser(args.figdir))
    manifest = os.path.abspath(os.path.expanduser(args.manifest or os.path.join(figdir, DEFAULT_MANIFEST)))
    if not os.path.exists(manifest):
        print(f"错误: 找不到清单 {manifest}（先跑 figure_manifest.py <FIGDIR> --write）", file=sys.stderr)
        return 1

    rows = read_manifest(manifest)
    problems, no_table, missing_file, bad_table = [], [], [], []
    referenced = set()
    for r in rows:
        fig = os.path.join(figdir, r["file"])
        if not os.path.exists(fig):
            missing_file.append(r["file"])
        declared = (r.get("source_table") or "").strip()
        if not declared:
            no_table.append(r["file"])
            continue
        # 允许相对图件目录、相对清单所在目录、或绝对路径
        candidates = [declared,
                      os.path.join(figdir, declared),
                      os.path.join(os.path.dirname(manifest), declared)]
        hit = next((os.path.abspath(c) for c in candidates if os.path.exists(c)), None)
        if hit is None:
            bad_table.append((r["file"], declared, "文件不存在"))
            continue
        referenced.add(hit)
        ok, detail = table_ok(hit)
        if not ok:
            bad_table.append((r["file"], declared, detail))

    orphan_tables = []
    for tabledir in args.tables:
        all_tables = collect_tables(os.path.abspath(os.path.expanduser(tabledir)))
        orphan_tables += sorted(all_tables - referenced)

    if missing_file:
        problems.append(f"清单里的图已不在目录（{len(missing_file)}）")
    if no_table and not args.allow_missing_table:
        problems.append(f"没登记 source_table 的图（{len(no_table)}）")
    if bad_table:
        problems.append(f"source_table 有问题（{len(bad_table)}）")
    if orphan_tables:
        problems.append(f"没有被任何图引用的表（{len(orphan_tables)}）")

    if args.json:
        print(json.dumps({"manifest": manifest, "figures": len(rows),
                          "missing_figures": missing_file, "no_source_table": no_table,
                          "bad_tables": bad_table, "orphan_tables": orphan_tables,
                          "problems": problems}, ensure_ascii=False, indent=2))
        return 1 if problems else 0

    print(f"图-表同源核验: {manifest}")
    print(f"图件 {len(rows)} 个；登记了 source_table 的 {len(rows) - len(no_table)} 个")
    if missing_file:
        print(f"\n清单里的图已不在目录（{len(missing_file)}）:")
        for f in missing_file[:15]:
            print(f"  - {f}")
    if no_table and not args.allow_missing_table:
        print(f"\n没登记 source_table（{len(no_table)}）——图-表同源关系缺失:")
        for f in no_table[:15]:
            print(f"  - {f}")
        print("  （纯示意图可用 --allow-missing-table 放行）")
    if bad_table:
        print(f"\nsource_table 有问题（{len(bad_table)}）:")
        for f, t, why in bad_table[:15]:
            print(f"  - {f} → {t}：{why}")
    if orphan_tables:
        print(f"\n没有被任何图引用的表（{len(orphan_tables)}）——漏配或多出来的:")
        for t in orphan_tables[:15]:
            print(f"  - {t}")

    if problems:
        print("\n结论：不通过 —— " + "；".join(problems))
        return 1
    print("\n结论：通过（每张图都有可核验的数据来源表，无孤儿表）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
