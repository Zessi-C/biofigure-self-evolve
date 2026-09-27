#!/usr/bin/env python3
"""图库定量总结：按固定节律把"图库长成什么样了、有没有在被用、缺什么"讲成数字。

与 review_preferences.py 的分工：
- review_preferences.py 管**偏好**的语义整理（合并/晋升/降级/下沉）；
- 本脚本管**整体定量总结**：图库规模与增长、复用台账（命中率、热度、未命中需求）、
  偏好计数、自动可判定的待办，以及"该不该现在总结"的节律判定。

复用台账来自 `library/USAGE.jsonl`（retrieve.py 每次检索自动追加一行）。台账同时回答
"agent 到底有没有在查图库"——只靠感觉判断这件事是不可靠的。

用法:
    summary.py                 # 出人读报告（默认窗口 30 天）
    summary.py --write         # 同时落盘 library/SUMMARY.md，并记录本次总结时间
    summary.py --check         # 只判定是否到总结节律（到期 → 退出码 1）
    summary.py --json          # 机器可读
    summary.py --days 7 --top 5
"""
import argparse
import collections
import datetime
import json
import os
import re
import sys

from build_index import collect_records, parse_frontmatter, resolve_library

USAGE_FILE = "USAGE.jsonl"
STATE_FILE = "SUMMARY.json"
REPORT_FILE = "SUMMARY.md"
DUE_DAYS = 30
DUE_NEW_USAGE = 20
SIZE_LIMIT = 2 * 1024 * 1024


def load_learned_dates(fig_dir: str) -> dict:
    """从各 figure.md 的 source.learned_date 取学习日期（索引里没有这个字段）。"""
    out = {}
    for name in sorted(os.listdir(fig_dir)):
        path = os.path.join(fig_dir, name, "figure.md")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data, _err = parse_frontmatter(fh.read())
        if isinstance(data, dict):
            date = (data.get("source") or {}).get("learned_date")
            if date:
                out[name] = str(date)
    return out


def load_usage(root: str) -> list:
    path = os.path.join(root, USAGE_FILE)
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict) and rec.get("ts"):
                rows.append(rec)
    return rows


def load_state(root: str) -> dict:
    path = os.path.join(root, STATE_FILE)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _month(date_str: str) -> str:
    return date_str[:7] if date_str and len(date_str) >= 7 else "未知"


def analyze(root: str, days: int, top: int) -> dict:
    fig_dir = os.path.join(root, "figures")
    records, warnings = collect_records(fig_dir)
    learned = load_learned_dates(fig_dir)
    usage = load_usage(root)
    state = load_state(root)
    today = datetime.date.today()
    cutoff = (today - datetime.timedelta(days=days)).isoformat()

    def _ts(rec):
        return str(rec.get("ts", ""))[:10]

    recent = [u for u in usage if _ts(u) >= cutoff]
    hits = [u for u in recent if u.get("hit")]
    misses = [u for u in recent if not u.get("hit")]

    # 未命中需求 → 待学候选（按归一化文本归并；互相包含的算同一条，如"KM 生存曲线"⊂"KM 生存曲线带风险表"）
    miss_groups = {}
    for u in misses:
        key = re.sub(r"\s+", " ", str(u.get("query", "")).strip().lower())[:80]
        g = miss_groups.setdefault(key, {"query": u.get("query", ""), "count": 0, "last": "",
                                         "samples": []})
        g["count"] += 1
        g["last"] = max(g["last"], _ts(u))
        if u.get("query") not in g["samples"]:
            g["samples"].append(u.get("query", ""))
    merged_misses = {}
    for key in sorted(miss_groups, key=len):
        host = next((mk for mk in merged_misses if key in mk or mk in key), None)
        if host is None:
            merged_misses[key] = dict(miss_groups[key])
        else:
            m = merged_misses[host]
            m["count"] += miss_groups[key]["count"]
            m["last"] = max(m["last"], miss_groups[key]["last"])
            m["samples"] += [s for s in miss_groups[key]["samples"] if s not in m["samples"]]
    miss_list = sorted(merged_misses.values(), key=lambda g: (-g["count"], g["last"]))

    # 命中热度
    hot = collections.Counter(u["top"] for u in hits if u.get("top"))

    # 图库构成
    charts = collections.Counter()
    for r in records:
        for ct in (r["chart_types"] or ["(未标注)"]):
            charts[ct] += 1
    langs = collections.Counter(l for r in records for l in r["languages"])
    verified = collections.Counter(r["verified"] for r in records)
    sources = collections.Counter(r["source_type"] for r in records)
    months = collections.Counter(_month(d) for d in learned.values())
    ref_bytes = 0
    biggest = []
    for name in sorted(os.listdir(fig_dir)):
        p = os.path.join(fig_dir, name, "reference.png")
        if os.path.isfile(p):
            size = os.path.getsize(p)
            ref_bytes += size
            biggest.append((size, name))
    biggest.sort(reverse=True)

    prefs_path = os.path.join(root, "PREFERENCES.md")
    pref_counts = {"stable": 0, "single": 0, "reviews": []}
    if os.path.exists(prefs_path):
        try:
            from review_preferences import parse_preferences
            parsed = parse_preferences(prefs_path)
            pref_counts = {"stable": len(parsed["stable"]), "single": len(parsed["single"]),
                           "last_review": parsed.get("last_review"),
                           "reviews": [r["raw"] for r in parsed["reviews"]]}
        except Exception as e:  # 偏好解析失败不该让总结整体失败
            pref_counts["error"] = str(e)

    # 节律判定
    last_summary = state.get("last_summary")
    usage_since = len(usage) - int(state.get("usage_total", 0))
    due_reasons = []
    if not last_summary:
        due_reasons.append("没有总结记录——建议现在出第一份")
    else:
        try:
            age = (today - datetime.date.fromisoformat(last_summary)).days
            if age > DUE_DAYS:
                due_reasons.append(f"距上次总结（{last_summary}）已 {age} 天 > {DUE_DAYS} 天")
        except ValueError:
            due_reasons.append(f"总结记录日期无法解析: {last_summary}")
        if usage_since >= DUE_NEW_USAGE:
            due_reasons.append(f"自上次总结以来新增 {usage_since} 条检索记录（阈值 {DUE_NEW_USAGE}）")

    return {
        "library": root, "today": today.isoformat(), "window_days": days,
        "figures": len(records),
        "chart_types": charts.most_common(),
        "languages": dict(langs), "verified": dict(verified), "sources": dict(sources),
        "months": sorted(months.items()),
        "learned_last_days": sum(1 for d in learned.values() if d >= cutoff),
        "reference_bytes": ref_bytes,
        "largest_reference": [{"name": n, "bytes": s} for s, n in biggest[:3]],
        "usage_total": len(usage), "usage_recent": len(recent),
        "hits_recent": len(hits), "misses_recent": len(misses),
        "hit_rate_recent": round(len(hits) / len(recent), 3) if recent else None,
        "hot_entries": hot.most_common(top),
        "miss_candidates": miss_list[:top],
        "preferences": pref_counts,
        "warnings": warnings,
        "last_summary": last_summary, "usage_since_summary": usage_since,
        "due": bool(due_reasons), "due_reasons": due_reasons,
    }


def render(rep: dict, top: int) -> str:
    pct = rep["hit_rate_recent"]
    L = [f"# 图库定量总结（{rep['today']}）", "",
         f"图库: {rep['library']}　窗口: 最近 {rep['window_days']} 天",
         f"上次总结: {rep['last_summary'] or '无记录'}　节律: "
         f"{'**该总结了**' if rep['due'] else '未到期'}", ""]
    if rep["due_reasons"]:
        L += ["触发原因:"] + [f"- {r}" for r in rep["due_reasons"]] + [""]

    L += ["## 1. 图库规模",
          f"- 条目 {rep['figures']} 条；语言 " +
          "、".join(f"{k} {v}" for k, v in sorted(rep["languages"].items())) +
          "；verified " + "、".join(f"{k} {v}" for k, v in sorted(rep["verified"].items())),
          f"- chart_types 覆盖 {len(rep['chart_types'])} 类，最多：" +
          "、".join(f"{k}({v})" for k, v in rep["chart_types"][:6]),
          f"- 来源：" + "、".join(f"{k} {v}" for k, v in sorted(rep["sources"].items())),
          f"- reference.png 合计 {rep['reference_bytes'] / 1048576:.1f} MB" +
          ("，最大：" + "、".join(f"{x['name']} {x['bytes'] / 1048576:.1f}MB"
                                for x in rep["largest_reference"]) if rep["largest_reference"] else ""),
          ""]

    L += ["## 2. 增长（按 source.learned_date 月度）"]
    L += [f"- {m}: {n} 条" for m, n in rep["months"]] or ["- （没有条目）"]
    L.append(f"- 最近 {rep['window_days']} 天新增 {rep['learned_last_days']} 条")
    L.append("")

    L += ["## 3. 复用台账（library/USAGE.jsonl）"]
    if rep["usage_total"] == 0:
        L += ["- 台账为空：没有任何检索记录。**这是最重要的信号**——要么还没画过图，",
              "  要么 agent 画图时根本没查图库（装触发钩子：`scripts/install_hook.py`）"]
    else:
        L.append(f"- 累计检索 {rep['usage_total']} 次；最近 {rep['window_days']} 天 {rep['usage_recent']} 次")
        if pct is not None:
            L.append(f"- 命中率（近 {rep['window_days']} 天）：{pct * 100:.0f}%"
                     f"（命中 {rep['hits_recent']} / 未命中 {rep['misses_recent']}）")
        if rep["hot_entries"]:
            L.append("- 命中最多：" + "、".join(f"{k} ×{v}" for k, v in rep["hot_entries"]))
        if rep["miss_candidates"]:
            L.append("- **未命中需求（待学候选）**：")
            for g in rep["miss_candidates"]:
                extra = "、".join(g.get("samples", [])[:3]) if len(g.get("samples", [])) > 1 else ""
                L.append(f"  - ×{g['count']}（最近 {g['last']}）{g['query'][:70]}"
                         + (f"　样本：{extra}" if extra else ""))
        else:
            L.append("- 窗口内没有未命中需求")
    L.append("")

    p = rep["preferences"]
    L += ["## 4. 偏好档案",
          f"- 稳定偏好 {p.get('stable', '?')} 行 / 单次观察 {p.get('single', '?')} 条；"
          f"上次整理 {p.get('last_review') or '无记录'}"]
    if p.get("reviews"):
        L.append("- 整理历史：" + "；".join(r[:80] for r in p["reviews"][-3:]))
    if p.get("error"):
        L.append(f"- ⚠ 偏好解析失败: {p['error']}")
    L.append("")

    L += ["## 5. 自动可判定的待办"]
    if rep["warnings"]:
        L += [f"- 图库告警 {len(rep['warnings'])} 条："] + [f"  - {w}" for w in rep["warnings"][:top]]
    else:
        L.append("- 图库结构告警：无")
    L.append("- 偏好侧的机械项：跑 `scripts/review_preferences.py` 看报告")
    L.append("")
    L += ["## 收尾动作",
          "1. 把上面 3~5 条要点讲给用户（尤其是命中率与待学候选）",
          f"2. `summary.py --write` 落盘 {REPORT_FILE} 并记录本次总结时间（下次据此判到期）",
          "3. 待学候选里反复出现的图型，问用户要不要现在学（模式 A）"]
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--library", help="图库根目录")
    parser.add_argument("--days", type=int, default=30, help="统计窗口天数（默认 30）")
    parser.add_argument("--top", type=int, default=5, help="每节最多列几项（默认 5）")
    parser.add_argument("--check", action="store_true", help="只判到期（到期 → 退出码 1）")
    parser.add_argument("--write", action="store_true", help=f"落盘 {REPORT_FILE} 并更新 {STATE_FILE}")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    root = resolve_library(args.library)
    if not os.path.isdir(os.path.join(root, "figures")):
        print(f"错误: 未找到图库 {root}（缺 figures/）。先运行 init_library.py。", file=sys.stderr)
        return 1

    rep = analyze(root, args.days, args.top)

    if args.check:
        if rep["due"]:
            print("该做定量总结了:")
            for r in rep["due_reasons"]:
                print(f"  - {r}")
            return 1
        print("未到总结节律。")
        return 0
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0

    text = render(rep, args.top)
    print(text)
    if args.write:
        with open(os.path.join(root, REPORT_FILE), "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        state = {"last_summary": rep["today"], "usage_total": rep["usage_total"],
                 "figures": rep["figures"]}
        with open(os.path.join(root, STATE_FILE), "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"\n已写入 {os.path.join(root, REPORT_FILE)}，并记录总结时间 {rep['today']}。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
