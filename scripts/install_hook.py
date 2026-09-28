#!/usr/bin/env python3
"""把常驻触发钩子写进 agent 的指令层——技能装完就跑它，不要指望模型自己记得查图库。

为什么需要：技能自带的 description 只在"技能列表被注入上下文"时起作用，而
①技能列表常常几十上百条、②子代理往往根本拿不到技能列表、③描述可能被截断。
钩子写在每一轮都会读的指令文件里，才能真正解决"agent 老是不查图库"。

写入方式：用成对 HTML 注释包住一个块，重复运行只会替换这个块（幂等），
卸载只需 `--uninstall`。文件不存在则创建，已有内容原样保留。

用法:
    install_hook.py                        # 自动装到检测到的 harness 全局层（dsh/claude/omp）
    install_hook.py --check                # 只报告各层是否已装（全部就绪 → 退出码 0）
    install_hook.py --dsh                  # ~/.dsh/AGENTS.md（DeepSeek Harness 全局）
    install_hook.py --claude               # ~/.claude/CLAUDE.md
    install_hook.py --omp-home             # ~/.omp/AGENTS.md（omp 是否读 home 层取决于版本）
    install_hook.py --project DIR [...]    # <DIR>/AGENTS.md（omp 等按项目读 AGENTS.md）
    install_hook.py --uninstall --project DIR
    install_hook.py --dry-run              # 只打印将要写入的内容
"""
import argparse
import os
import sys

BEGIN = "<!-- biofigure-self-evolve:trigger-hook:begin -->"
END = "<!-- biofigure-self-evolve:trigger-hook:end -->"

SKILL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

HOOK_TEMPLATE = """{begin}
## 生信绘图（biofigure-self-evolve）
任何生信/统计图的产出、修改、复刻、学习，以及把这类任务委派给子代理之前，先读
`skill://biofigure-self-evolve`（omp；其他 harness 用 `{skill}/SKILL.md`），并跑
`python3 {skill}/scripts/retrieve.py "<需求>"` 检索图库；交付说明必须写明
"复用了 NNN-slug 的 XX"或"图库未命中"。委派时把技能入口或检索结果写进委派提示。
{end}"""


def hook_block() -> str:
    return HOOK_TEMPLATE.format(begin=BEGIN, end=END, skill=SKILL_DIR)


def strip_block(text: str) -> str:
    """移除已有钩子块（连同它前面的空行），返回新文本与是否找到。"""
    start = text.find(BEGIN)
    if start == -1:
        return text, False
    end = text.find(END, start)
    if end == -1:
        return text[:start], True
    end += len(END)
    while end < len(text) and text[end] == "\n":
        end += 1
    head = text[:start].rstrip("\n")
    tail = text[end:]
    if head and tail:
        return head + "\n\n" + tail.lstrip("\n"), True
    return (head + ("\n" if head else "") + tail.lstrip("\n")), True


def install(path: str, dry_run: bool = False) -> str:
    block = hook_block()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        cleaned, found = strip_block(text)
        if found and cleaned.strip() == "":
            new = block + "\n"
        elif cleaned.strip():
            new = cleaned.rstrip("\n") + "\n\n" + block + "\n"
        else:
            new = block + "\n"
        state = "已存在，已刷新" if found else "已追加"
    else:
        new = block + "\n"
        state = "已新建文件"
    if not dry_run:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new)
    return state


def uninstall(path: str, dry_run: bool = False) -> str:
    if not os.path.exists(path):
        return "文件不存在"
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    cleaned, found = strip_block(text)
    if not found:
        return "未装钩子"
    if not dry_run:
        if cleaned.strip():
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(cleaned)
        else:
            os.remove(path)  # 文件里只剩我们写的钩子 → 一起清掉，不留空文件
    return "已移除钩子" + ("（文件已空，已删除）" if not cleaned.strip() else "")


def hook_state(path: str) -> str:
    """已装 / 已装但技能路径过期 / 未装 / 无此文件。

    "有钩子但指向旧路径"和"根本没装"要分开报：前者只需重跑一次刷新，
    报成"未装"会让人以为钩子没生效过。
    """
    if not os.path.exists(path):
        return "无此文件"
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if BEGIN not in text:
        return "未装"
    return "已装" if SKILL_DIR in text else "已装但路径过期"


def default_targets() -> list:
    home = os.path.expanduser("~")
    dsh_home = os.environ.get("DSH_HOME") or os.path.join(home, ".dsh")
    out = []
    if os.path.isdir(dsh_home):
        out.append(os.path.join(dsh_home, "AGENTS.md"))
    if os.path.isdir(os.path.join(home, ".claude")):
        out.append(os.path.join(home, ".claude", "CLAUDE.md"))
    if os.path.isdir(os.path.join(home, ".omp")):
        out.append(os.path.join(home, ".omp", "AGENTS.md"))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dsh", action="store_true", help="装到 $DSH_HOME/AGENTS.md（默认 ~/.dsh/AGENTS.md）")
    parser.add_argument("--claude", action="store_true", help="装到 ~/.claude/CLAUDE.md")
    parser.add_argument("--omp-home", action="store_true", help="装到 ~/.omp/AGENTS.md")
    parser.add_argument("--project", action="append", default=[], metavar="DIR",
                        help="装到 <DIR>/AGENTS.md（可重复；omp 等按项目读 AGENTS.md）")
    parser.add_argument("--check", action="store_true", help="只报告状态（全部就绪 → 退出码 0）")
    parser.add_argument("--uninstall", action="store_true", help="移除钩子块")
    parser.add_argument("--dry-run", action="store_true", help="只打印将写入的内容")
    args = parser.parse_args()

    home = os.path.expanduser("~")
    targets = []
    if args.dsh:
        targets.append(os.path.join(os.environ.get("DSH_HOME") or os.path.join(home, ".dsh"), "AGENTS.md"))
    if args.claude:
        targets.append(os.path.join(home, ".claude", "CLAUDE.md"))
    if args.omp_home:
        targets.append(os.path.join(home, ".omp", "AGENTS.md"))
    targets += [os.path.join(os.path.abspath(os.path.expanduser(p)), "AGENTS.md") for p in args.project]
    if not targets:
        targets = default_targets()
        if not targets:
            print("没有检测到已知 harness 的全局指令层；用 --project <项目目录> 指定，"
                  "或 --dsh/--claude/--omp-home 显式指定。", file=sys.stderr)
            return 1
        print("未指定目标，自动检测到：")

    if args.dry_run:
        print(f"技能目录: {SKILL_DIR}\n")
        print(hook_block())
        print("\n将写入：")
        for t in targets:
            print(f"  - {t}")
        return 0

    if args.check:
        states = {}
        for t in targets:
            states[t] = hook_state(t)
            print(f"{states[t]:>10}  {t}")
        bad = {s for s in states.values() if s != "已装"}
        if not bad:
            print("\n全部就绪。")
            return 0
        if bad == {"已装但路径过期"}:
            print("\n钩子都在，但指向的技能路径已过期（技能搬过家）：跑 install_hook.py 刷新即可。")
        else:
            print("\n有目标未装钩子：跑 install_hook.py（不带 --check）安装。")
        return 1

    for t in targets:
        state = uninstall(t) if args.uninstall else install(t)
        print(f"{state:>12}  {t}")
    if not args.uninstall:
        print(f"\n钩子里的技能路径: {SKILL_DIR}")
        print("验证：新开一个会话，直接说\"帮我画个 UMAP\"（不提图库），看它有没有先跑 retrieve.py。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
