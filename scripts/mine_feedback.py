#!/usr/bin/env python3
"""从 agent 会话历史里挖"用户纠偏"，生成偏好候选——偏好的真实来源是多轮改图。

用户对成图的每一次"再改/还是不对/不要/改成"都是偏好信号，但现在全靠 agent 当场自觉
写回。本脚本把会话历史里的这类原话挖出来、聚类、排频，产出候选清单交给
`review_preferences.py` 的整理流程判断——**只产出候选，绝不自动写 PREFERENCES.md**。

支持两种输入：
- 默认扫本机已知 harness 的会话目录（omp 的 ~/.omp/agent/sessions、dsh 的 ~/.dsh/sessions）
- `--input FILE.jsonl` 直接喂已抽取的消息（每行 {"text": "...", "ts": "..."}）

用法:
    mine_feedback.py                                  # 扫默认目录，最近 90 天
    mine_feedback.py --since 2026-08-01 --min-count 2
    mine_feedback.py --sessions /path/to/sessions     # 可重复
    mine_feedback.py --out library/FEEDBACK-CANDIDATES.md
    mine_feedback.py --json
"""
import argparse
import collections
import datetime
import glob
import json
import os
import re
import sys

from build_index import resolve_library
from review_preferences import cluster, similarity

DEFAULT_SESSION_ROOTS = [
    "~/.omp/agent/sessions",
    "~/.dsh/sessions",
    "~/.claude/projects",
]

# 纠偏/缺陷词：只留"用户在说图哪里不对/要怎么改"的话
SIGNAL = re.compile(
    r"(重叠|遮挡|盖住|出界|超出|裁切|太小|太大|字小|留白|空白|不齐|不一致|不搭|丑|难看|"
    r"再改|改一下|调整一下|重新画|重画|重做|还是不对|不要|去掉|删掉|换成|改成|建议|最好)")
FIGURE = re.compile(r"(图|figure|fig\.|plot|umap|heatmap|热图|火山|富集|点图|柱|箱线|色|轴|图例|面板|排版|画布)", re.I)
# agent/子代理注入的合成"用户消息"，不是人说的话
INJECTED = re.compile(r"^(###\s*Session update|Complete assignment thoroughly|Workspace\b|# Target|ROLE:|You are\b|<)")
NOISE = re.compile(r"^(ok|好的|可以|行|嗯|谢谢|继续|yes|no)[。！!]?$", re.I)


def session_files(roots: list) -> list:
    out = []
    for root in roots:
        root = os.path.expanduser(root)
        if os.path.isdir(root):
            out += glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
    return sorted(set(out))


def iter_messages(files: list):
    for path in files:
        try:
            with open(path, errors="replace") as fh:
                for line in fh:
                    if '"role":"user"' not in line and '"role": "user"' not in line:
                        continue
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    m = d.get("message")
                    if not isinstance(m, dict) or m.get("role") != "user":
                        continue
                    content = m.get("content")
                    if isinstance(content, str):
                        text = content
                    else:
                        text = " ".join(c.get("text", "") for c in (content or [])
                                        if isinstance(c, dict) and c.get("type") == "text")
                    text = text.strip()
                    if text:
                        yield {"text": text, "ts": (d.get("timestamp") or "")[:10], "src": os.path.basename(path)}
        except OSError:
            continue


def load_input(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("text"):
                rows.append({"text": str(d["text"]), "ts": str(d.get("ts", ""))[:10], "src": "input"})
    return rows


def normalize(text: str) -> str:
    t = re.sub(r"^[0-9]+[.、)]\s*", "", text.strip())
    t = re.sub(r"\s+", " ", t)
    return t[:220]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sessions", action="append", default=[], metavar="DIR",
                        help="会话目录（可重复；默认扫 omp/dsh/claude 的常见位置）")
    parser.add_argument("--input", help="直接读已抽取的消息 JSONL（每行含 text/ts）")
    parser.add_argument("--since", help="只看该日期之后（YYYY-MM-DD，默认 90 天前）")
    parser.add_argument("--min-count", type=int, default=2, help="至少出现几次才算候选（默认 2）")
    parser.add_argument("--top", type=int, default=30, help="最多输出多少条候选（默认 30）")
    parser.add_argument("--library", help="图库根目录（决定默认输出路径）")
    parser.add_argument("--out", help="候选清单输出路径（默认 <library>/FEEDBACK-CANDIDATES.md）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    since = args.since or (datetime.date.today() - datetime.timedelta(days=90)).isoformat()

    if args.input:
        rows = load_input(args.input)
        scanned = 0
        # 有时间戳就同样按 --since 过滤（没有时间戳的输入无法按日期筛，如实保留）
        rows = [r for r in rows if not r["ts"] or r["ts"] >= since]
    else:
        roots = args.sessions or DEFAULT_SESSION_ROOTS
        files = session_files(roots)
        scanned = len(files)
        rows = [r for r in iter_messages(files) if r["ts"] >= since]

    kept = []
    for r in rows:
        t = r["text"]
        if INJECTED.match(t) or NOISE.match(t) or len(t) < 8 or len(t) > 800:
            continue
        if not FIGURE.search(t) or not SIGNAL.search(t):
            continue
        kept.append({"text": normalize(t), "ts": r["ts"]})

    # 同一条偏好会被用户说很多遍（措辞略变），按字符二元组相似度聚类
    groups = cluster(kept, lambda x: x["text"], 0.55) if kept else []
    cands = []
    for g in groups:
        texts = [x["text"] for x in g]
        dates = sorted({x["ts"] for x in g if x["ts"]})
        if len(g) < args.min_count and not args.json:
            # 单次出现也留（可能正是新偏好），但排在后面
            pass
        cands.append({
            "count": len(g),
            "first": dates[0] if dates else "",
            "last": dates[-1] if dates else "",
            "samples": texts[:4],
            "representative": max(texts, key=len),
        })
    cands.sort(key=lambda c: (-c["count"], c["last"]))

    if args.json:
        print(json.dumps({"since": since, "scanned_sessions": scanned,
                          "messages_scanned": len(rows), "signals": len(kept),
                          "candidates": cands}, ensure_ascii=False, indent=2))
        return 0

    root = resolve_library(args.library)
    out = args.out or os.path.join(root, "FEEDBACK-CANDIDATES.md")
    today = datetime.date.today().isoformat()
    L = [f"# 偏好候选（由 mine_feedback.py 从会话历史抽取，{today}）", "",
         f"扫描: {scanned} 个会话文件 / {len(rows)} 条用户消息（{since} 之后）；"
         f"命中纠偏信号 {len(kept)} 条，聚类成 {len(cands)} 组。", "",
         "> **这是候选，不是偏好。** 按 `references/preference-profile.md` 判断：哪些是跨图型通用规则"
         "（写进 PREFERENCES.md 稳定偏好）、哪些只服务某个项目/图型（下沉到条目「复用要点」或标适用范围）、"
         "哪些只是一次性要求（丢弃）。判断完在 `## 整理记录` 留一行。", "",
         "## 候选（按出现次数排序）", ""]
    for i, c in enumerate(cands[:args.top], 1):
        L.append(f"### {i}. ×{c['count']}　{c['first']} → {c['last']}")
        L.append(f"- 代表表述：{c['representative']}")
        for s in c["samples"][1:4]:
            if s != c["representative"]:
                L.append(f"- 其他说法：{s}")
        L.append("")
    L += ["## 收尾", "1. 逐条判断归属（通用 / 项目专属 / 一次性），通用项按五步晋升写进 PREFERENCES.md",
          "2. 项目专属项写进对应条目的「复用要点」并标适用范围",
          "3. 判断完删掉本文件（它是工作底稿，不是长期资产）"]
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"扫描 {scanned} 个会话文件 / {len(rows)} 条消息（{since} 之后）")
    print(f"命中纠偏信号 {len(kept)} 条，聚类 {len(cands)} 组；候选已写入 {out}")
    print("下一步：读该文件逐条判断归属，按 review_preferences.py 的整理流程落地。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
