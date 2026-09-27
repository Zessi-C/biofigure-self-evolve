#!/usr/bin/env python3
"""生成"图件 QA 子代理"的委派提示：出图的和验收的分开，避免自己检查自己的盲区。

真实使用记录里，跑过绘图命令的会话只有三分之一打开过渲染结果；用户反馈的缺陷又几乎
全是"看一眼就能发现"的（重叠、出界、字太小、留白、面板不齐）。把验收交给一个只拿
成图 + 清单、不许改代码的子代理，是最省事也最有效的补救。

用法:
    qa_prompt.py FIGDIR                       # 打印可直接粘进 subagent/task 的提示
    qa_prompt.py FIGDIR --task "四队列组成图定稿" --entry 013-milo-da-dualtrack-profile
    qa_prompt.py FIGDIR --max 8 --out /tmp/qa.md
    qa_prompt.py FIGDIR --list-only           # 只列待检文件

提示里内联了 references/delivery-checklist.md 的全文，子代理不需要再读技能目录。
"""
import argparse
import os
import re
import sys

SKILL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHECKLIST = os.path.join(SKILL_DIR, "references", "delivery-checklist.md")
EXTS = (".png", ".jpg", ".jpeg", ".pdf", ".tif", ".tiff", ".svg")


def list_figures(figdir: str, exts: tuple, max_n: int) -> list:
    out = []
    for root, _dirs, files in os.walk(figdir):
        for fn in sorted(files):
            if fn.lower().endswith(exts):
                path = os.path.join(root, fn)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                out.append((os.path.relpath(path, figdir), path, size))
    out.sort(key=lambda x: (-x[2], x[0]))
    return out[:max_n] if max_n else out


def load_checklist() -> str:
    if not os.path.exists(CHECKLIST):
        return "（未找到 references/delivery-checklist.md，按常规发表级标准检查）"
    with open(CHECKLIST, encoding="utf-8") as fh:
        text = fh.read()
    # 去掉"为什么有这份清单"的论证段，只留可执行部分
    text = re.sub(r"^# .*?\n", "", text, count=1)
    text = re.sub(r"这份清单来自.*?\n\n", "", text, count=1, flags=re.S)
    return text.strip()


def build_prompt(figdir: str, figures: list, task: str, entry: str) -> str:
    lines = [
        "# 图件验收（QA）任务",
        "",
        f"任务背景：{task or '（未提供，按图件本身判断）'}",
        f"图件目录：{figdir}",
    ]
    if entry:
        lines.append(f"本次复用的配方条目：`{entry}`（检查是否真的体现了该条目的画法）")
    lines += [
        "",
        "## 你的角色（严格限定）",
        "- 你**只做视觉验收**：打开图、对照清单、报告缺陷。",
        "- **不要修改任何文件**，不要重画，不要运行绘图脚本，不要只根据文件大小/页数下结论。",
        "- 每张图都必须真的打开看（有图像读取能力就用它）。",
        "",
        "## 待检文件",
    ]
    for rel, path, size in figures:
        lines.append(f"- `{path}`（{size / 1024:.0f} KB）")
    if not figures:
        lines.append("- （目录下没找到图件文件）")
    lines += [
        "",
        "## 检查清单（逐项过，不要跳项）",
        "",
        load_checklist(),
        "",
        "## 输出格式（严格遵守）",
        "对每张图输出一段：",
        "```",
        "### <文件名>",
        "- 结论：通过 / 不通过",
        "- 缺陷：[严重度 高/中/低] 位置（哪个面板/哪条轴/哪个图例） + 现象 + 建议怎么改",
        "- 未确认项：无法判断的项要写出来，不要默认通过",
        "```",
        "最后给一个汇总：不通过的图清单 + 最该先改的 3 件事（按影响排序）。",
        "**不要重写图、不要输出绘图代码**——你的输出是给负责改图的人看的缺陷报告。",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("figdir", help="图件目录（要验收的那一批）")
    parser.add_argument("--task", help="这批图是干什么的（写进提示，帮子代理判断内容正确性）")
    parser.add_argument("--entry", help="本次复用的配方条目 id")
    parser.add_argument("--max", type=int, default=12, help="最多列几张（按体积降序，默认 12；0=全部）")
    parser.add_argument("--ext", default=".png,.jpg,.jpeg,.pdf",
                        help="只检这些扩展名（逗号分隔）")
    parser.add_argument("--list-only", action="store_true", help="只列待检文件")
    parser.add_argument("--out", help="写入文件而不是打印")
    args = parser.parse_args()

    figdir = os.path.abspath(os.path.expanduser(args.figdir))
    if not os.path.isdir(figdir):
        print(f"错误: 不是目录 {figdir}", file=sys.stderr)
        return 1
    exts = tuple(e.strip().lower() for e in args.ext.split(",") if e.strip())
    figures = list_figures(figdir, exts, args.max)

    if args.list_only:
        for rel, path, size in figures:
            print(f"{size / 1024:8.0f} KB  {path}")
        print(f"共 {len(figures)} 个（--max 限制前）")
        return 0

    text = build_prompt(figdir, figures, args.task, args.entry)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"已写入 {args.out}（{len(figures)} 张图）")
        print("用法：把该文件内容作为 task/subagent 的 prompt 传下去（子代理不需要再读技能目录）。")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
