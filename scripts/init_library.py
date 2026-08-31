#!/usr/bin/env python3
"""初始化 biofigure-self-evolve 图库骨架（幂等，可重复运行）。

图库默认内嵌在技能目录下（<技能目录>/library/），与技能一起同步。
用法:
    init_library.py                 # 在默认位置 <技能目录>/library 创建
    init_library.py --path DIR     # 在指定位置创建，并写入 config 指针
    init_library.py --path DIR --no-config   # 指定位置但不写 config

已存在的文件不会被覆盖；只补齐缺失的部分。
"""
import argparse
import datetime
import json
import os
import sys

SKILL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_LIBRARY = os.path.join(SKILL_DIR, "library")
CONFIG_PATH = os.path.expanduser("~/.config/biofigure-self-evolve/config.json")

README = """# Biofigure Library

个人生物信息学 figure 学习库。每个 `figures/NNN-slug/` 目录是一条学习记录：
语言无关的绘制配方（figure.md）+ 原图参考（reference.png）+ R/Python 可运行模板。

- `INDEX.json` — 机器可读索引，agent 复用画图时先读它
- `INDEX.md`   — 人类可读索引，由 scripts/build_index.py 生成

本目录是纯文件，可用 git 或任意云盘同步；配合 biofigure-self-evolve 技能使用。
"""

INDEX_JSON_SKELETON = {"version": 1, "updated": None, "figures": []}

INDEX_MD_PLACEHOLDER = """# Biofigure Library 索引

（还没有条目。学习第一个 figure 后运行 scripts/build_index.py 重建本文件。）
"""

PREFERENCES_TEMPLATE = """# 用户偏好档案

（跨条目的个人审美与习惯，实现"图库越长越像你"。由 agent 在复用交付后自动追加——
只记录可观察到的偏好信号，禁止脑补。优先级：用户当前指令 > 稳定偏好 > 条目缺省。
规范见技能 references/preference-profile.md）

## 稳定偏好
（同一偏好累计 ≥2 次一致才从下方晋升到这里；每行格式：偏好 〔日期 场景，次数〕）

## 单次观察
（格式：- 日期 〔场景〕 偏好内容——待复现确认）
"""


def write_if_missing(path: str, content: str) -> bool:
    if os.path.exists(path):
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", help="图库根目录（默认 <技能目录>/library，或环境变量 BIOFIGURE_LIBRARY）")
    parser.add_argument("--no-config", action="store_true", help="不写 config.json 指针")
    args = parser.parse_args()

    root = os.path.abspath(os.path.expanduser(args.path or os.environ.get("BIOFIGURE_LIBRARY") or DEFAULT_LIBRARY))

    # 默认位置初始化但 config 指向别处 → 提醒错位，避免"建了库却检索不到"的困惑
    if not args.path and os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f).get("library_path")
            if cfg and os.path.abspath(os.path.expanduser(cfg)) != root:
                print(f"注意: {CONFIG_PATH} 当前指向 {cfg}，与本次初始化位置不同；"
                      f"build_index 将按 config 优先解析。", file=sys.stderr)
        except (json.JSONDecodeError, OSError):
            pass

    # --path 与默认位置不同时写 config，保证后续按解析顺序能找到这里
    if args.path and not args.no_config:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        existing = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"警告: 读取 {CONFIG_PATH} 失败（{e}），将覆盖", file=sys.stderr)
        if existing.get("library_path") != root:
            existing["library_path"] = root
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            print(f"已写入配置指针: {CONFIG_PATH} -> {root}")

    os.makedirs(os.path.join(root, "figures"), exist_ok=True)
    INDEX_JSON_SKELETON["updated"] = datetime.date.today().isoformat()
    created = []
    if write_if_missing(os.path.join(root, "README.md"), README):
        created.append("README.md")
    if write_if_missing(
        os.path.join(root, "INDEX.json"),
        json.dumps(INDEX_JSON_SKELETON, ensure_ascii=False, indent=2) + "\n",
    ):
        created.append("INDEX.json")
    if write_if_missing(os.path.join(root, "INDEX.md"), INDEX_MD_PLACEHOLDER):
        created.append("INDEX.md")
    if write_if_missing(os.path.join(root, "PREFERENCES.md"), PREFERENCES_TEMPLATE):
        created.append("PREFERENCES.md")

    print(f"图库根目录: {root}")
    if created:
        print("新建: " + ", ".join(created))
    else:
        print("已存在，未做修改（幂等）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
