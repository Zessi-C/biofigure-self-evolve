#!/usr/bin/env python3
"""体检：把每个条目的模板复制到临时目录试运行，验证当前环境能否复现。

只读检查——绝不写图库任何文件（包括 figure.md 的 verified 字段，
那是 agent 看了本报告之后自行维护的）。

判定：运行时不存在 → skip；否则在临时目录运行模板（--timeout 限时），
退出码 0 且产出至少一个 .png/.jpg/.pdf → pass，其余 → fail（附 stderr 末尾 5 行）。

用法:
    verify_library.py [--library DIR] [--id ID ...] [--timeout 300]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from build_index import resolve_library

OUTPUT_EXTS = (".png", ".jpg", ".pdf")
TEMPLATES = [("template.R", "R"), ("template.py", "Python")]


def runtime_cmd(fname: str):
    """返回运行模板的命令；运行时不存在返回 None。"""
    if fname == "template.R":
        exe = shutil.which("Rscript")
        return [exe, fname] if exe else None
    return [sys.executable, fname]  # Python 用当前解释器，总是存在


def produced_output(workdir: str) -> bool:
    for dirpath, _dirnames, filenames in os.walk(workdir):
        for fn in filenames:
            if fn.lower().endswith(OUTPUT_EXTS):
                return True
    return False


def run_template(src: str, fname: str, timeout: int):
    """在临时目录运行单个模板；返回 (状态, 详情)。"""
    cmd = runtime_cmd(fname)
    if cmd is None:
        return "skip", "无运行时"
    workdir = tempfile.mkdtemp(prefix="biofigure-verify-")
    try:
        shutil.copy(src, os.path.join(workdir, fname))
        try:
            proc = subprocess.run(cmd, cwd=workdir, timeout=timeout,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.TimeoutExpired:
            return "fail", f"超时（>{timeout}s）"
        except OSError as e:
            return "fail", f"无法启动运行时: {e}"
        if proc.returncode == 0 and produced_output(workdir):
            return "pass", ""
        if proc.returncode == 0:
            detail = "退出码 0 但未产出 .png/.jpg/.pdf"
        else:
            detail = f"退出码 {proc.returncode}"
        tail = proc.stderr.decode("utf-8", errors="replace").strip().splitlines()[-5:]
        if tail:
            detail += "；stderr 末尾 5 行:\n" + "\n".join("    " + line for line in tail)
        return "fail", detail
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", help="图库根目录")
    parser.add_argument("--id", nargs="+", metavar="ID",
                        help="只检查指定条目（完整 id 或数字前缀，可多个）；缺省全部")
    parser.add_argument("--timeout", type=int, default=300, help="单个模板的秒级超时（默认 300）")
    args = parser.parse_args()

    root = resolve_library(args.library)
    fig_dir = os.path.join(root, "figures")
    if not os.path.isdir(fig_dir):
        print(f"错误: 未找到图库 {root}（缺 figures/）。先运行 init_library.py。", file=sys.stderr)
        return 1
    names = sorted(n for n in os.listdir(fig_dir) if os.path.isdir(os.path.join(fig_dir, n)))

    if args.id:
        selected, errors = set(), []
        for req in args.id:
            hits = [n for n in names if n == req or n.startswith(req)]
            if not hits:
                errors.append(req)
            selected.update(hits)
        if errors:
            for req in errors:
                print(f"错误: {req!r} 未匹配任何条目。", file=sys.stderr)
            return 1
        names = sorted(selected)

    counts = {"pass": 0, "fail": 0, "skip": 0}
    for name in names:
        entry_dir = os.path.join(fig_dir, name)
        for fname, lang in TEMPLATES:
            src = os.path.join(entry_dir, fname)
            if not os.path.isfile(src):
                continue
            status, detail = run_template(src, fname, args.timeout)
            counts[status] += 1
            line = f"{name} {lang} {status}"
            if status == "skip":
                line += f"（{detail}）"
            print(line)
            if status == "fail" and detail:
                print(f"    {name} fail 详情: {detail}")

    total = sum(counts.values())
    print(f"\n汇总: 共运行 {total} 个模板 — pass {counts['pass']}，"
          f"fail {counts['fail']}，skip {counts['skip']}。")
    if counts["fail"]:
        print("存在失败模板；体检不修改图库，请人工/agent 依据上方详情处理。")
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
