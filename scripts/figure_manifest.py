#!/usr/bin/env python3
"""图件清单：扫描一个图件目录，产出/核对 `figure_manifest.csv`。

为什么需要：图件目录会很快长到几百个文件（本项目 676 个 PDF），`ls` 看不出
"哪些是最终交付、哪些是被取代的旧版、哪些根本没登记"。本项目已有的 manifest
（umap_manifest.csv / figure_object_manifest.csv）记的是**数据来源**，本脚本补的是
**文件层事实**（体积、页数/像素、时间、校验和），两者拼起来才完整。

列分两类：脚本能确定的事实列（file/ext/bytes/modified/pages/width_px/height_px/sha256_8），
以及留给 agent 填的语义列（figure_set/entry_reused/note）——`--write` 更新时会
**保留已填的语义列**，只刷新事实列。

用法:
    figure_manifest.py FIGDIR                     # 只报告（不改盘）
    figure_manifest.py FIGDIR --write             # 写/更新 <FIGDIR>/figure_manifest.csv
    figure_manifest.py FIGDIR --check             # 与已有清单比对，有漂移 → 退出码 1
    figure_manifest.py FIGDIR --diff OLD.csv      # 增量重导：哪些新增/消失/内容变了/内容没变
    figure_manifest.py FIGDIR --diff OLD.csv --only unchanged   # 可跳过重导的文件（hash 未变）
    figure_manifest.py FIGDIR --check --fail-on-unregistered   # 未登记文件也算漂移
    figure_manifest.py FIGDIR --json
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys

EXTS = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".svg", ".eps")
FACT_COLS = ["file", "ext", "bytes", "modified", "pages", "width_px", "height_px", "sha256_8"]
SEM_COLS = ["figure_set", "entry_reused", "source_table", "note"]
COLUMNS = FACT_COLS + SEM_COLS
DEFAULT_CSV = "figure_manifest.csv"


def pdf_pages(path: str):
    """PDF 页数：优先 pdfinfo（poppler），否则退回正则数 /Type /Page。

    正则对 cairo_pdf 这类用对象流的 PDF 数不出来（页对象被压缩），所以 pdfinfo 存在时
    优先用它；两者都拿不到就留空——宁可空着，也不要给个错的页数。
    """
    exe = shutil.which("pdfinfo")
    if exe:
        try:
            proc = subprocess.run([exe, path], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  timeout=10)
            m = re.search(rb"^Pages:\s+(\d+)", proc.stdout, re.M)
            if m:
                return int(m.group(1))
        except (OSError, subprocess.TimeoutExpired):
            pass
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return ""
    n = len(re.findall(rb"/Type\s*/Page[^s]", data))
    return n or ""


def png_size(path: str):
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            return "", ""
        w, h = struct.unpack(">II", head[16:24])
        return w, h
    except OSError:
        return "", ""


def jpeg_size(path: str):
    """遍历 JPEG 段找 SOF，取宽高。"""
    try:
        with open(path, "rb") as fh:
            fh.read(2)
            while True:
                b = fh.read(1)
                if not b:
                    return "", ""
                if b != b"\xff":
                    continue
                marker = fh.read(1)
                while marker == b"\xff":
                    marker = fh.read(1)
                if marker in (b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5", b"\xc6",
                              b"\xc7", b"\xc9", b"\xca", b"\xcb", b"\xcd", b"\xce", b"\xcf"):
                    fh.read(3)
                    h, w = struct.unpack(">HH", fh.read(4))
                    return w, h
                seg = fh.read(2)
                if len(seg) < 2:
                    return "", ""
                fh.read(struct.unpack(">H", seg)[0] - 2)
    except OSError:
        return "", ""


def sha8(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()[:8]


def scan(figdir: str, recursive: bool) -> list:
    rows = []
    for root, _dirs, files in os.walk(figdir):
        for fn in sorted(files):
            if not fn.lower().endswith(EXTS) or fn == DEFAULT_CSV:
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, figdir)
            ext = os.path.splitext(fn)[1].lower()
            try:
                st = os.stat(path)
            except OSError:
                continue
            pages = w = h = ""
            if ext == ".pdf":
                pages = pdf_pages(path)
            elif ext == ".png":
                w, h = png_size(path)
            elif ext in (".jpg", ".jpeg"):
                w, h = jpeg_size(path)
            rows.append({
                "file": rel, "ext": ext, "bytes": st.st_size,
                "modified": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                "pages": pages, "width_px": w, "height_px": h, "sha256_8": sha8(path),
            })
        if not recursive:
            break
    rows.sort(key=lambda r: r["file"])
    return rows


def load_csv(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("file"):
                out[row["file"]] = row
    return out


def merge(rows: list, old: dict) -> list:
    """事实列用新扫描结果，语义列沿用旧清单里已填的内容。"""
    for r in rows:
        prev = old.get(r["file"], {})
        for c in SEM_COLS:
            r[c] = (prev.get(c) or "").strip()
    return rows


def write_csv(path: str, rows: list) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})


def diff_manifests(rows: list, old: dict) -> dict:
    """当前扫描结果 vs 旧清单：按 sha256_8 判定内容有没有变（mtime 变了但 hash 没变 = 白重导）。"""
    cur = {r["file"]: r for r in rows}
    added = sorted(set(cur) - set(old))
    removed = sorted(set(old) - set(cur))
    changed, unchanged = [], []
    for f in sorted(set(cur) & set(old)):
        same = cur[f]["sha256_8"] and cur[f]["sha256_8"] == (old[f].get("sha256_8") or "")
        (unchanged if same else changed).append(f)
    return {"added": added, "removed": removed, "changed": changed, "unchanged": unchanged}


def report_diff(d: dict, only: str) -> None:
    kinds = [(k, v) for k, v in (("added", d["added"]), ("removed", d["removed"]),
                                 ("changed", d["changed"]), ("unchanged", d["unchanged"]))
             if v and (not only or k == only)]
    if not kinds:
        print("与旧清单比较：无变化。" if not only else f"与旧清单比较：没有 {only} 的文件。")
        return
    labels = {"added": "新增（旧清单没有）", "removed": "消失（文件已不在）",
              "changed": "内容变化（需要重导）", "unchanged": "内容未变（可跳过重导）"}
    for kind, items in kinds:
        print(f"\n{labels[kind]}：{len(items)} 个")
        for f in items[:20]:
            print(f"  - {f}")
        if len(items) > 20:
            print(f"  …另有 {len(items) - 20} 个")



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("figdir", help="图件目录（figure/8.xxx 这类）")
    parser.add_argument("--out", help=f"清单路径（默认 <FIGDIR>/{DEFAULT_CSV}）")
    parser.add_argument("--write", action="store_true", help="写/更新清单")
    parser.add_argument("--check", action="store_true", help="与已有清单比对（漂移 → 退出码 1）")
    parser.add_argument("--fail-on-unregistered", action="store_true",
                        help="--check 时把「目录里有、清单没登记」也算漂移")
    parser.add_argument("--flat", action="store_true", help="只看顶层，不递归子目录")
    parser.add_argument("--diff", metavar="OLD.csv",
                        help="与旧清单比较，报增量重导需要的信息（新增/消失/内容变化/内容未变）")
    parser.add_argument("--only", choices=["added", "removed", "changed", "unchanged"],
                        help="配合 --diff，只输出某一类")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    figdir = os.path.abspath(os.path.expanduser(args.figdir))
    if not os.path.isdir(figdir):
        print(f"错误: 不是目录 {figdir}", file=sys.stderr)
        return 1
    csv_path = args.out or os.path.join(figdir, DEFAULT_CSV)

    rows = scan(figdir, recursive=not args.flat)
    old = load_csv(csv_path)
    if args.diff:
        diff_path = os.path.abspath(os.path.expanduser(args.diff))
        if not os.path.exists(diff_path):
            print(f"错误: 旧清单不存在 {diff_path}", file=sys.stderr)
            return 1
        old_diff = load_csv(diff_path)
        d = diff_manifests(rows, old_diff)
        if args.json:
            print(json.dumps(d, ensure_ascii=False, indent=2))
        else:
            print(f"图件目录: {figdir}")
            print(f"当前 {len(rows)} 个文件；旧清单 {len(old_diff)} 行")
            report_diff(d, args.only)
        return 0
    rows = merge(rows, old)
    on_disk = {r["file"] for r in rows}
    registered = set(old)
    unregistered = sorted(on_disk - registered)
    orphans = sorted(registered - on_disk)
    missing_sem = [r["file"] for r in rows if not r.get("entry_reused")]

    if args.json:
        print(json.dumps({"dir": figdir, "manifest": csv_path, "files": rows,
                          "unregistered": unregistered, "orphans": orphans}, ensure_ascii=False, indent=2))
        return 1 if (args.check and (orphans or (args.fail_on_unregistered and unregistered))) else 0

    total = sum(r["bytes"] for r in rows)
    print(f"图件目录: {figdir}")
    print(f"文件 {len(rows)} 个，合计 {total / 1048576:.1f} MB；清单: {csv_path}"
          + ("" if os.path.exists(csv_path) else "（尚未生成）"))
    print(f"已登记 {len(registered & on_disk)}；未登记 {len(unregistered)}；"
          f"登记了但文件已不在（旧版/残留）{len(orphans)}")

    if args.check:
        drift = bool(orphans) or (args.fail_on_unregistered and bool(unregistered))
        if orphans:
            print("\n登记了但文件已不在（被取代的旧图或残留，确认后可删行）:")
            for f in orphans[:20]:
                print(f"  - {f}")
        if unregistered and args.fail_on_unregistered:
            print("\n目录里有但清单未登记:")
            for f in unregistered[:20]:
                print(f"  - {f}")
        if not drift:
            print("\n清单与目录一致。")
        return 1 if drift else 0

    if not args.write:
        print("\n（只报告模式；加 --write 生成/更新清单）")
        for r in rows[:10]:
            size = f"{r['bytes'] / 1024:.0f}KB"
            dim = f"{r['width_px']}x{r['height_px']}" if r["width_px"] else (f"{r['pages']}页" if r["pages"] else "")
            print(f"  {r['file']}  {size}  {dim}")
        if len(rows) > 10:
            print(f"  …另有 {len(rows) - 10} 个")
        return 0

    try:
        write_csv(csv_path, rows)
    except OSError as e:
        print(f"错误: 写不了 {csv_path}（{e}）——目录只读或磁盘满？", file=sys.stderr)
        return 1
    print(f"\n已写入 {csv_path}（{len(rows)} 行）。")
    print("语义列 figure_set / entry_reused / source_table / note 需 agent 填：entry_reused 写复用了哪条配方"
          "（如 `013-milo-da-dualtrack-profile`），source_table 写这张图的数据来源表路径（图-表同源，用 pair_check.py 核验）。")
    if missing_sem:
        print(f"其中 {len(missing_sem)} 个文件还没填 entry_reused。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
