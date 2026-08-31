#!/usr/bin/env python3
"""把 export_figure.py 产出的 bundle（zip）导入图库，导入后自动重建索引。

用法:
    import_figure.py bundle.zip --list            # 只读 manifest 打印清单
    import_figure.py bundle.zip --library DIR     # 导入（冲突默认拒绝）
    import_figure.py bundle.zip --force           # 冲突时覆盖目标条目
    import_figure.py bundle.zip --rename          # 冲突时分配新编号
    import_figure.py bundle.zip --dry-run         # 走全校验与判定，但不写入

校验（任一失败即退出 1，不写任何文件）：
    zip 可读、含 manifest.json、kind/bundle_version 正确、路径白名单
    （防 zip-slip）、无 manifest 之外的多余文件、逐文件 sha256 一致。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

from build_index import resolve_library

BUNDLE_KIND = "biofigure-bundle"
BUNDLE_VERSION = 1
NUM_PREFIX_RE = re.compile(r"^(\d+)-")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_member(zf: zipfile.ZipFile, name: str) -> str:
    h = hashlib.sha256()
    with zf.open(name) as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(zf: zipfile.ZipFile):
    """读 manifest 并做基础校验；返回 (manifest|None, 错误列表)。"""
    if "manifest.json" not in zf.namelist():
        return None, ["zip 缺少 manifest.json"]
    try:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, [f"manifest.json 解析失败: {e}"]
    errors = []
    if manifest.get("kind") != BUNDLE_KIND:
        errors.append(f"kind 不是 {BUNDLE_KIND!r}（得到 {manifest.get('kind')!r}）")
    if manifest.get("bundle_version") != BUNDLE_VERSION:
        errors.append(f"bundle_version 不是 {BUNDLE_VERSION}（得到 {manifest.get('bundle_version')!r}）")
    if errors or not isinstance(manifest.get("entries"), list):
        errors = errors or ["manifest 缺少 entries 列表"]
        return None, errors
    by_id = {}
    for e in manifest["entries"]:
        eid = e.get("id")
        if not eid:
            return None, ["manifest 存在缺少 id 的条目"]
        if eid in by_id:
            return None, [f"manifest 条目 id 重复: {eid}"]
        by_id[eid] = e
    return manifest, []


def validate_members(zf: zipfile.ZipFile, manifest: dict):
    """路径白名单 + 完整性 + sha256 校验；返回错误列表（空 = 通过）。"""
    errors = []
    entries = {e["id"]: e for e in manifest["entries"]}
    expected_sha = {}
    for eid, e in entries.items():
        for rel, sha in (e.get("files") or {}).items():
            expected_sha[f"figures/{eid}/{rel}"] = sha

    name_set = set(zf.namelist())
    for name in zf.namelist():
        parts = name.split("/")
        if name.startswith("/") or ".." in parts or name.startswith("\\"):
            errors.append(f"非法路径成员（绝对路径或目录穿越）: {name}")
            continue
        if name == "manifest.json" or name == "PREFERENCES.md":
            continue
        if (len(parts) >= 3 and parts[0] == "figures" and parts[1] in entries
                and "/".join(parts[2:]) in (entries[parts[1]].get("files") or {})):
            continue
        errors.append(f"manifest 之外的多余成员: {name}")

    for member in expected_sha:
        if member not in name_set:
            errors.append(f"manifest 声明的文件在 zip 中缺失: {member}")
    if manifest.get("preferences_included") and "PREFERENCES.md" not in name_set:
        errors.append("manifest 声明 preferences_included 但 zip 缺少 PREFERENCES.md")
    if errors:
        return errors

    for member, sha in expected_sha.items():
        if sha256_member(zf, member) != sha:
            errors.append(f"sha256 不一致: {member}")
    return errors


def target_identical(dest: str, files: dict) -> bool:
    """目标目录与包内逐文件 sha256 一致（目标多出的文件不算冲突）。"""
    for rel, sha in files.items():
        p = os.path.join(dest, *rel.split("/"))
        if not os.path.isfile(p) or sha256_file(p) != sha:
            return False
    return True


def extract_entry(zf: zipfile.ZipFile, eid: str, files: dict, dest: str) -> None:
    os.makedirs(dest, exist_ok=True)
    for rel in files:
        data = zf.read(f"figures/{eid}/{rel}")
        out = os.path.join(dest, *rel.split("/"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as fh:
            fh.write(data)


def rewrite_figure_md(path: str, new_id: str, rename_map: dict) -> None:
    """改写 frontmatter：id 行换成新 id；related 行中被本次重命名的旧 id 换成新 id。"""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    if not lines or lines[0].strip() != "---":
        return
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            break
        stripped = lines[i].lstrip()
        if stripped.startswith("id:"):
            lines[i] = f"id: {new_id}"
        elif stripped.startswith("related:"):
            for old, new in rename_map.items():
                lines[i] = re.sub(
                    rf"(?<![\w-]){re.escape(old)}(?![\w-])", new, lines[i]
                )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def print_list(manifest: dict, bundle_path: str) -> None:
    print(f"Bundle: {bundle_path}（共 {len(manifest['entries'])} 个条目）")
    for e in manifest["entries"]:
        print(f"  {e['id']}  {e.get('title', '')}（{len(e.get('files') or {})} 个文件）")
    print(f"包含 PREFERENCES.md: {'是' if manifest.get('preferences_included') else '否'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", help="export_figure.py 产出的 zip 包")
    parser.add_argument("--library", help="图库根目录")
    strategy = parser.add_mutually_exclusive_group()
    strategy.add_argument("--force", action="store_true", help="内容冲突时覆盖目标条目")
    strategy.add_argument("--rename", action="store_true", help="内容冲突时分配新编号导入")
    parser.add_argument("--dry-run", action="store_true", help="只做校验与判定，不写入")
    parser.add_argument("--list", action="store_true", help="只打印包内条目清单后退出")
    args = parser.parse_args()

    try:
        zf = zipfile.ZipFile(args.bundle)
    except (OSError, zipfile.BadZipFile) as e:
        print(f"错误: 无法打开 {args.bundle}: {e}", file=sys.stderr)
        return 1

    with zf:
        manifest, errors = read_manifest(zf)
        if errors:
            for err in errors:
                print(f"错误: {err}", file=sys.stderr)
            return 1
        if args.list:
            print_list(manifest, os.path.abspath(args.bundle))
            return 0
        errors = validate_members(zf, manifest)
        if errors:
            for err in errors:
                print(f"错误: {err}", file=sys.stderr)
            return 1

        root = resolve_library(args.library)
        fig_root = os.path.join(root, "figures")
        existing = set()
        if os.path.isdir(fig_root):
            existing = {n for n in os.listdir(fig_root)
                        if os.path.isdir(os.path.join(fig_root, n))}

        def entry_num(name: str):
            m = NUM_PREFIX_RE.match(name)
            return int(m.group(1)) if m else None

        # 编号水位：图库现有条目 + 本次按原编号导入的包内条目都计入，
        # 保证 --rename 分配的新编号不与任何一方冲突
        nums = [entry_num(n) for n in existing]
        nums += [entry_num(e["id"]) for e in manifest["entries"]]
        next_num = max((n for n in nums if n is not None), default=0) + 1
        entries_by_id = {e["id"]: e for e in manifest["entries"]}

        # 判定阶段：逐条目决定动作（此时不写任何文件）
        plan, rename_map = [], {}
        for e in manifest["entries"]:
            eid, files = e["id"], e.get("files") or {}
            dest = os.path.join(fig_root, eid)
            if not os.path.exists(dest):
                action = "install"
            elif target_identical(dest, files):
                action = "skip"
            elif args.force:
                action = "overwrite"
            elif args.rename:
                slug = NUM_PREFIX_RE.sub("", eid)
                new_id = f"{next_num:03d}-{slug}"
                rename_map[eid] = new_id
                next_num += 1
                action = "rename"
            else:
                action = "reject"
            plan.append((eid, action))

        pref_member = "PREFERENCES.md" in zf.namelist()
        pref_target = os.path.join(root, "PREFERENCES.md")
        pref_exists = os.path.exists(pref_target)

        if args.dry_run:
            print(f"[dry-run] 图库: {root}")
            for eid, action in plan:
                if action == "install":
                    print(f"[dry-run] 将导入 {eid}")
                elif action == "skip":
                    print(f"[dry-run] {eid}: 已存在相同内容，将跳过")
                elif action == "overwrite":
                    print(f"[dry-run] 将覆盖 {eid}（--force）")
                elif action == "rename":
                    print(f"[dry-run] {eid} 内容冲突，将以 {rename_map[eid]} 导入（--rename）")
                else:
                    print(f"[dry-run] {eid}: 内容冲突，需 --force 或 --rename")
            if pref_member:
                if pref_exists:
                    print("[dry-run] 目标已有 PREFERENCES.md，将保持不动")
                else:
                    print("[dry-run] 将写入 PREFERENCES.md")
            print("[dry-run] 未写入任何文件。")
            rejected = [eid for eid, a in plan if a == "reject"]
            if rename_map:
                print("重命名映射（预计）:")
                for old, new in rename_map.items():
                    print(f"  {old} -> {new}")
            return 1 if rejected else 0

        # 执行阶段
        os.makedirs(fig_root, exist_ok=True)
        imported, skipped, rejected = [], [], []
        for eid, action in plan:
            files = entries_by_id[eid].get("files") or {}
            if action == "skip":
                skipped.append(eid)
                print(f"{eid}: 已存在相同内容，跳过。")
                continue
            if action == "reject":
                rejected.append(eid)
                print(f"{eid}: 内容冲突，需 --force 或 --rename。", file=sys.stderr)
                continue
            dest_name = rename_map.get(eid, eid)
            dest = os.path.join(fig_root, dest_name)
            if action == "overwrite":
                if os.path.isdir(dest):
                    shutil.rmtree(dest)
                else:
                    os.remove(dest)
            extract_entry(zf, eid, files, dest)
            if action == "rename":
                record = os.path.join(dest, "figure.md")
                if os.path.isfile(record):
                    rewrite_figure_md(record, dest_name, rename_map)
                print(f"{eid} -> {dest_name}: 已按新编号导入。")
            else:
                print(f"{eid}: 已导入。")
            imported.append(eid)

        pref_written = False
        if pref_member:
            if pref_exists:
                print("目标已有偏好档案（PREFERENCES.md），保持不动；如需合并请人工/agent 对比处理。")
            else:
                with open(pref_target, "wb") as fh:
                    fh.write(zf.read("PREFERENCES.md"))
                pref_written = True
                print("已写入 PREFERENCES.md。")

    if imported or pref_written:
        print("重建索引...")
        sys.stdout.flush()
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_index.py")
        r = subprocess.run([sys.executable, script, "--library", root])
        if r.returncode != 0:
            print("警告: build_index.py 重建索引未成功，请手动检查。", file=sys.stderr)

    print(f"\n汇总: 导入 {len(imported)} 条，跳过 {len(skipped)} 条，被拒 {len(rejected)} 条。")
    if rename_map:
        print("重命名映射:")
        for old, new in rename_map.items():
            print(f"  {old} -> {new}")
    print("提示: 服务器环境与本机可能不同，建议运行 verify_library.py 体检。")
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
