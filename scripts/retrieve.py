#!/usr/bin/env python3
"""按需求检索图库，输出 top-K 候选 + 偏好摘要 —— 模式 B 的默认入口。

为什么单独有这个脚本：INDEX.json 随图库增长会到几十 KB，模型为了一次检索读整个
索引既贵又容易只读一半就动手。本脚本直接扫 figure.md（永远比索引新），只把最相关
的 3 条压缩成几百字，并把 PREFERENCES.md 的稳定偏好一并带上——一次调用即可完成
B1 检索，不需要再单独读两个大文件。

用法:
    retrieve.py "两组差异火山图，要标通路"          # 语义检索，默认 top 3
    retrieve.py "umap 分面" --top 5 --json         # 机器可读，便于塞进子代理的委派提示
    retrieve.py --all                              # 无明确需求时按 chart_types 分组浏览
    retrieve.py --preferences-only                 # 只输出偏好摘要（写 harness 记忆用）
    retrieve.py "热图" --chart heatmap --lang R    # 先按受控词/语言过滤再排序

退出码: 0 正常（含"未命中"）；1 图库不可用或参数错误。
"""
import argparse
import datetime
import json
import os
import re
import sys

from build_index import _as_list, collect_records, resolve_library

USAGE_FILE = "USAGE.jsonl"

# 字段权重：aliases/chart_types 是用户口语与受控词的对齐点，权重最高；
# not_when 取负值——命中"不适用"说明这条不是用户要的，但只做温和惩罚，避免误杀。
FIELDS = [
    ("aliases", 3.0),
    ("chart_types", 3.0),
    ("title", 2.0),
    ("use_when", 2.0),
    ("data_shape", 1.5),
    ("layout", 0.8),
    ("not_when", -0.8),
]
VERIFIED_BONUS = {"both": 0.5, "partial": 0.2, "unverified": 0.0}

STOP = set("""的 了 和 与 或 在 是 有 用 把 被 对 为 我 你 要 需要 一个 一张 这 那 怎么 如何
图 图表 图形 figure plot chart 画 绘制 做 出 让 请 帮 一下 可以 想要 分析 数据 结果 展示 呈现
the a an of for and or to with in on is are plot figure chart""".split())


def tokenize(text: str) -> dict:
    """返回 {token: 权重}：ASCII 词 1.0，中文双字 1.0，中文单字 0.4（保召回）。"""
    text = (text or "").lower()
    toks = {}
    for w in re.findall(r"[a-z0-9][a-z0-9_.+-]{1,}", text):
        if w not in STOP:
            toks[w] = 1.0
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        for ch in run:
            if ch not in STOP:
                toks[ch] = max(toks.get(ch, 0), 0.4)
        for i in range(len(run) - 1):
            bg = run[i:i + 2]
            if bg not in STOP:
                toks[bg] = 1.0
    return toks


def score_record(query_tokens: dict, rec: dict):
    """加权命中得分；同时返回命中的 not_when 词，便于在输出里提示风险。

    not_when 只认高信息量 token（ASCII 词与中文双字，权重 1.0）：单字（如"两""组"）
    在中文里到处都是，拿它判"不适用"只会制造噪声。
    """
    score = 0.0
    hits, warns = [], []
    for field, weight in FIELDS:
        raw = rec.get(field)
        if isinstance(raw, list):
            raw = " ".join(str(x) for x in raw)
        ftoks = tokenize(str(raw or ""))
        if weight < 0:
            matched = [t for t in query_tokens if query_tokens[t] >= 1.0 and t in ftoks]
        else:
            matched = [t for t in query_tokens if t in ftoks]
        if not matched:
            continue
        score += weight * sum(query_tokens[t] for t in matched)
        if weight < 0:
            warns.extend(matched)
        else:
            hits.extend(matched)
    score += VERIFIED_BONUS.get(str(rec.get("verified", "")), 0.0)
    norm = max(1.0, len(query_tokens) ** 0.5)
    warns = sorted({w for w in warns if w not in set(hits)})
    return score / norm, hits, warns


def rank(query: str, records: list, top: int, min_score: float):
    qt = tokenize(query)
    scored = []
    for rec in records:
        s, hits, warns = score_record(qt, rec)
        if s >= min_score:
            scored.append((s, hits, warns, rec))
    scored.sort(key=lambda x: (-x[0], x[3]["id"]))
    return scored[:top], len(scored)


def fmt_candidate(idx: int, s: float, hits: list, warns: list, rec: dict, root: str) -> str:
    lines = [
        f"[{idx}] {rec['id']}  (score {s:.1f}, verified={rec['verified']})",
        f"    标题: {rec['title']}",
        f"    类型: {', '.join(rec['chart_types'])} | 数据形状: {rec['data_shape']}",
        f"    何时用: {rec['use_when']}",
        f"    不适用: {rec['not_when']}",
    ]
    if rec.get("related"):
        lines.append(f"    相近条目(多候选时先看这些的对比句): {', '.join(rec['related'])}")
    if warns:
        lines.append(f"    ⚠ 你的描述还命中了本条的「不适用」: {', '.join(sorted(set(warns)))} —— 确认后再用")
    lines.append(f"    记录: {rec['dir']}/figure.md（读「配方 / 复用要点 / 与相近条目的对比」）")
    return "\n".join(lines)


def log_usage(root: str, query: str, top: list, n_records: int) -> None:
    """把这次检索追加进 library/USAGE.jsonl —— 定期总结的定量基础。

    "agent 到底有没有查图库""哪些需求一直没命中"这类问题只能靠台账回答；写失败
    （只读库、磁盘满）绝不影响检索本身，因此吞掉 OSError。
    """
    try:
        rec = {
            "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "query": query,
            "hit": bool(top),
            "top": top[0][3]["id"] if top else None,
            "score": round(top[0][0], 2) if top else 0.0,
            "candidates": [t[3]["id"] for t in top],
            "n_records": n_records,
        }
        with open(os.path.join(root, USAGE_FILE), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", nargs="*", help="需求描述（自然语言，中英文均可）")
    parser.add_argument("--library", help="图库根目录")
    parser.add_argument("--top", type=int, default=3, help="返回候选数（默认 3）")
    parser.add_argument("--min-score", type=float, default=3.0,
                        help="低于此分视为未命中（默认 3.0）")
    parser.add_argument("--chart", help="只保留含该 chart_type 的条目（受控词表见 references/chart-taxonomy.md）")
    parser.add_argument("--lang", choices=["R", "Python"], help="只保留有该语言模板的条目")
    parser.add_argument("--all", action="store_true", help="浏览模式：按 chart_types 分组列出全部条目")
    parser.add_argument("--preferences-only", action="store_true", help="只输出偏好摘要")
    parser.add_argument("--no-preferences", action="store_true",
                        help="不附偏好摘要（只想要候选时用，输出更短，适合塞进子代理的委派提示）")
    parser.add_argument("--json", action="store_true", help="输出 JSON（便于传给子代理）")
    parser.add_argument("--no-log", action="store_true",
                        help="不把本次检索写进 library/USAGE.jsonl（默认写，作为定期总结的定量台账）")
    args = parser.parse_args()

    root = resolve_library(args.library)
    fig_dir = os.path.join(root, "figures")
    if not os.path.isdir(fig_dir):
        print(f"错误: 未找到图库 {root}（缺 figures/）。先运行 init_library.py。", file=sys.stderr)
        return 1

    records, warnings = collect_records(fig_dir)
    if args.chart:
        records = [r for r in records if args.chart in _as_list(r["chart_types"])]
    if args.lang:
        records = [r for r in records if args.lang in _as_list(r["languages"])]

    prefs = {} if (args.no_preferences and not args.preferences_only) else preference_digest(root)

    if args.preferences_only:
        print(prefs["text"])
        return 0

    query = " ".join(args.query).strip()
    browse = args.all or not query
    top, total = ([], 0)
    if not browse:
        top, total = rank(query, records, args.top, args.min_score)
        if not args.no_log:
            log_usage(root, query, top, len(records))

    if args.json:
        payload = {"library": root, "query": query, "count": len(records),
                   "index_warnings": warnings}
        if not args.no_preferences:
            payload["preferences"] = prefs
        if browse:
            payload["figures"] = [
                {"id": r["id"], "title": r["title"], "chart_types": r["chart_types"],
                 "data_shape": r["data_shape"], "use_when": r["use_when"],
                 "verified": r["verified"], "dir": r["dir"]} for r in records]
        else:
            payload["candidates"] = [
                {"score": round(s, 2), "hit": sorted(set(h)), "not_when_hit": sorted(set(w)),
                 **{k: r[k] for k in ("id", "title", "chart_types", "data_shape",
                                      "use_when", "not_when", "verified", "related", "dir")}}
                for s, h, w, r in top]
            payload["total_above_min"] = total
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"图库: {root}（{len(records)} 条）")
    if warnings:
        print(f"⚠ 图库告警 {len(warnings)} 条（先跑 scripts/build_index.py 看详情）")

    if browse:
        print("\n# 图库条目（按 chart_types 分组）\n")
        groups = {}
        for r in records:
            for ct in _as_list(r["chart_types"]) or ["(未标注)"]:
                groups.setdefault(ct, []).append(r)
        for ct in sorted(groups):
            print(f"## {ct}")
            for r in sorted(groups[ct], key=lambda x: x["id"]):
                print(f"- {r['id']} — {r['title']} | {r['data_shape']} | {r['verified']}")
            print()
    else:
        print(f"\n# 检索: {query}\n")
        if not top:
            print("未命中：库里没有足够相近的条目 → 按普通流程从头设计，交付满意后再提议入库（模式 A）。")
        else:
            for i, (s, h, w, r) in enumerate(top, 1):
                print(fmt_candidate(i, s, h, w, r, root))
                print()
            if total > len(top):
                print(f"（另有 {total - len(top)} 条低分命中，需要时用 --top N 或加限定词再看）")
            print("下一步：打开第 1 名的 figure.md 读「配方 / 复用要点 / 与相近条目的对比」，"
                  "按用户数据临摹式适配（B3），不要直接套模板。")

    if not args.no_preferences:
        print("\n# 偏好摘要（B3 实例化时用于填充用户未指定的细节）\n")
        print(prefs["text"])
    return 0


def preference_digest(root: str) -> dict:
    """偏好摘要：稳定偏好全文 + 单次观察计数，供 B1/B3 与 harness 记忆同步使用。"""
    path = os.path.join(root, "PREFERENCES.md")
    if not os.path.exists(path):
        return {"text": "（无 PREFERENCES.md，先跑 scripts/init_library.py 建骨架）",
                "stable": [], "single": []}
    try:
        from review_preferences import parse_preferences
        parsed = parse_preferences(path)
    except Exception as e:  # 解析失败不能挡住检索主流程
        return {"text": f"（PREFERENCES.md 解析失败: {e}）", "stable": [], "single": []}
    lines = ["## 稳定偏好（用户当前指令 > 稳定偏好 > 条目缺省）"]
    if parsed["stable"]:
        lines += [f"- {e['body']}" for e in parsed["stable"]]
    else:
        lines.append("- （暂无；跨图习惯累计 ≥2 次一致才晋升）")
    lines.append("")
    lines.append(f"## 单次观察（{len(parsed['single'])} 条，仅备查，不要当规则用）")
    for e in parsed["single"][:10]:
        lines.append(f"- {e['body']}")
    if len(parsed["single"]) > 10:
        lines.append(f"- …另有 {len(parsed['single']) - 10} 条，见 library/PREFERENCES.md")
    if parsed.get("due"):
        lines.append("")
        lines.append("⚠ 偏好档案已到整理节律（跑 scripts/review_preferences.py 出整理报告）")
    return {"text": "\n".join(lines),
            "stable": [e["body"] for e in parsed["stable"]],
            "single": [e["body"] for e in parsed["single"]],
            "due": bool(parsed.get("due"))}


if __name__ == "__main__":
    sys.exit(main())
