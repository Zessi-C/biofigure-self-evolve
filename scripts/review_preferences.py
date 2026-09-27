#!/usr/bin/env python3
"""偏好整理审计：把"整体偏好"（PREFERENCES.md）与"部分偏好"（各条目的复用要点/演化记录）
放在一起做机械体检，产出可执行的整理报告。

设计原则：脚本只做**可判定**的事（容量、格式、重复、晋升/降级候选、跨条目复现、
过期未复现、条目内堆积），语义合并仍由 agent 按 references/preference-profile.md
的五步流程完成——脚本不写 PREFERENCES.md，也不改任何 figure.md。

用法:
    review_preferences.py                    # 出整理报告（人读）
    review_preferences.py --check            # 只判定"该不该现在整理"（到期或有必做项 → 退出码 1）
    review_preferences.py --json             # 机器可读，便于 agent 逐项执行
    review_preferences.py --digest           # 输出可粘贴进 harness 记忆/托管技能的偏好摘要
    review_preferences.py --due-days 30 --stale-days 60 --top 20
"""
import argparse
import datetime
import json
import os
import re
import sys

from build_index import resolve_library

PREF_FILE = "PREFERENCES.md"
SECTIONS = {"稳定偏好": "stable", "单次观察": "single", "整理记录": "reviews"}
NEGATION = re.compile(r"(不|不要|无需|禁止|不再|避免|别用|不应)")
# "用户显式声明为通用"与"≥2 次一致"是两条并列的晋升通道：显式声明不需要重复次数，
# 否则用户明确锁定的规则会被机械规则反复判为"该降级"。
DECLARATION = re.compile(r"(显式声明|明确锁定|明确声明|明确要求为通用|通用规则|通用要求)")

# 节律阈值：任一命中即认为"该整理了"（软阈值贴着硬上限放，避免刚整理完就又被判到期）
CAP_STABLE_SOFT, CAP_STABLE_HARD = 13, 15
CAP_SINGLE_SOFT, CAP_SINGLE_HARD = 18, 20
EVOLUTIONS_SINCE_REVIEW = 8
DUP_SIM = 0.55        # 偏好行之间判定"近似"的相似度
CROSS_SIM = 0.55      # 条目内规则之间判定"同一条规则"的相似度
GLOBAL_SIM = 0.42     # 与已有整体偏好判定"已被覆盖"的相似度
ENTRY_BLOAT = 5       # 单条目演化记录条数超过它 → 建议折叠


# ---------------------------------------------------------------- 解析

def _norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    text = re.sub(r"[\s，。、；：,.;:!?！？`*_\[\]【】「」“”\"'’—\-–/\\|]+", "", text)
    return text


def _bigrams(text: str):
    t = _norm(text)
    if len(t) < 2:
        return {t} if t else set()
    return {t[i:i + 2] for i in range(len(t) - 1)}


def similarity(a: str, b: str) -> float:
    """字符二元组 Jaccard：中英混排下比词切分稳，够用来找近似行。"""
    x, y = _bigrams(a), _bigrams(b)
    if not x or not y:
        return 0.0
    return len(x & y) / len(x | y)


# 这些 token 太通用，重合了也不能说明是"同一条规则"
GENERIC_TOKENS = {
    "ggplot", "ggplot2", "python", "matplotlib", "rscript", "pdf", "png", "jpg", "jpeg",
    "dpi", "seaborn", "patchwork", "cowplot", "complexheatmap", "figure", "plot", "panel",
    "width", "height", "size", "color", "colour", "label", "labels", "axis", "axes", "scale",
}


def distinctive_tokens(text: str) -> set:
    """长度 ≥5 且非通用的 ASCII token（函数名、参数名、包名），是"同一条规则"的硬指纹。

    门槛设这么高是有意的：`marker`、`list`、`panel` 这类词在偏好库里遍地都是，
    拿它们判重复会造出一堆假阳性，而假阳性会诱导 agent 合并两条本来不同的规则。
    """
    t = (text or "").lower()
    return {w for w in re.findall(r"[a-z][a-z0-9_.+-]{4,}", t) if w not in GENERIC_TOKENS}


def covered_by_global(text: str, prefs: list, sim_threshold: float) -> bool:
    """这条规则是不是已经以另一种写法存在于整体偏好里（防重复晋升）。"""
    mine = distinctive_tokens(text)
    for p in prefs:
        if similarity(text, p["body"]) >= sim_threshold:
            return True
        # 中英文各写一遍的同一条规则：字符相似度低，但共享 ≥2 个硬指纹 token
        if len(mine & distinctive_tokens(p["body"])) >= 2:
            return True
    return False


def _parse_entry(raw: str, section: str, lineno: int) -> dict:
    markers = re.findall(r"〔([^〕]*)〕", raw)
    marker = markers[-1] if markers else ""
    body = re.sub(r"〔[^〕]*〕", "", raw).strip()
    body = body.rstrip("。；;，,")
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", marker)
    counts = re.findall(r"(\d+)\s*次", marker)
    count = int(counts[-1]) if counts else None
    declared = bool(DECLARATION.search(marker))
    issues = []
    if not marker:
        issues.append("缺 〔日期 场景，次数〕 标注")
    elif not dates:
        issues.append("标注里没有日期")
    if section == "stable" and not declared:
        if count is None:
            issues.append("稳定偏好没有次数（≥2 次或用户显式声明才够格）")
        elif count < 2:
            issues.append(f"稳定偏好但只出现 {count} 次 → 应降回单次观察")
    if section == "single" and declared:
        issues.append("用户已显式声明为通用规则 → 应晋升稳定偏好（不依赖重复次数）")
    elif section == "single" and count is not None and count >= 2:
        issues.append(f"单次观察已累计 {count} 次 → 应晋升稳定偏好")
    return {"section": section, "raw": raw.strip(), "body": body, "marker": marker,
            "dates": dates, "count": count, "declared": declared,
            "lineno": lineno, "issues": issues}


def parse_preferences(path: str) -> dict:
    """解析 PREFERENCES.md。任何 agent 都可用它读偏好，故保持纯标准库、不抛异常。"""
    parsed = {"stable": [], "single": [], "reviews": [], "other": [], "exists": False}
    if not os.path.exists(path):
        parsed["due"] = True
        parsed["due_reasons"] = ["没有 PREFERENCES.md（先跑 init_library.py 建骨架）"]
        return parsed
    parsed["exists"] = True
    section = None
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            s = line.strip()
            m = re.match(r"^##+\s*(.+?)\s*$", s)
            if m:
                section = SECTIONS.get(m.group(1), "other")
                continue
            if not s.startswith(("-", "*")):
                continue
            raw = s.lstrip("-* ").strip()
            if not raw:
                continue
            if section in ("stable", "single"):
                parsed[section].append(_parse_entry(raw, section, lineno))
            elif section == "reviews":
                dates = re.findall(r"\d{4}-\d{2}-\d{2}", raw)
                parsed["reviews"].append({"raw": raw, "dates": dates, "lineno": lineno})
            else:
                parsed["other"].append({"raw": raw, "lineno": lineno})
    parsed["last_review"] = max((d for r in parsed["reviews"] for d in r["dates"]), default=None)
    return parsed


def collect_entry_rules(root: str) -> list:
    """扫各条目 figure.md 的「复用要点 / 演化记录 / 与相近条目的对比」，作为"部分偏好"。"""
    rules = []
    fig_dir = os.path.join(root, "figures")
    if not os.path.isdir(fig_dir):
        return rules
    for name in sorted(os.listdir(fig_dir)):
        record = os.path.join(fig_dir, name, "figure.md")
        if not os.path.isfile(record):
            continue
        section = None
        with open(record, encoding="utf-8") as fh:
            for line in fh:
                s = line.strip()
                m = re.match(r"^##+\s*(.+?)\s*$", s)
                if m:
                    head = m.group(1)
                    if head.startswith("复用要点"):
                        section = "复用要点"
                    elif head.startswith("演化记录"):
                        section = "演化记录"
                    elif head.startswith("与相近条目"):
                        section = "对比"
                    else:
                        section = None
                    continue
                if section and s.startswith("-"):
                    text = s.lstrip("-* ").strip()
                    if text:
                        rules.append({"entry": name, "section": section, "text": text})
    return rules


def collect_evolutions(root: str) -> list:
    """各条目演化记录的日期，用于判断"自上次整理以来新增了多少演化"。"""
    return [r for r in collect_entry_rules(root) if r["section"] == "演化记录"]


# ---------------------------------------------------------------- 聚类

def cluster(items: list, key, sim: float):
    """单链聚类，判定"同一条规则"用两路**高精度**信号：

    1. 字符二元组 Jaccard ≥ sim —— 措辞几乎一样的重复写入（偏好档案膨胀的主要来源）；
    2. 共享 ≥2 个长度 ≥5 的硬指纹 token —— 同一条规则用中英两种语言各写了一遍。

    故意不做"中文改写"的模糊匹配：领域词重合度不足以区分"生信图默认使用英文"和
    "生信图默认只导出 PDF"这类共享主语前缀的句子，误报会诱导 agent 合并两条不同的
    规则。语义重复交给整理流程里的人工通读（references/preference-profile.md 第 0 步）。
    聚类用全连接（complete linkage），避免 A~B、B~C 但 A!~C 被链成一串。
    """
    sets = [_bigrams(key(it)) for it in items]
    toks = [distinctive_tokens(key(it)) for it in items]

    def similar(i: int, j: int) -> bool:
        x, y = sets[i], sets[j]
        if x and y and len(x & y) / len(x | y) >= sim:
            return True
        return len(toks[i] & toks[j]) >= 2

    groups = []
    for i in range(len(items)):
        for c in groups:
            if all(similar(i, j) for j in c):
                c.append(i)
                break
        else:
            groups.append([i])
    return [[items[i] for i in c] for c in groups]


# ---------------------------------------------------------------- 分析

def analyze(root: str, due_days: int, stale_days: int) -> dict:
    path = os.path.join(root, PREF_FILE)
    parsed = parse_preferences(path)
    rules = collect_entry_rules(root)
    today = datetime.date.today()
    rep = {"library": root, "today": today.isoformat(), "preferences_exists": parsed["exists"],
           "stable": parsed["stable"], "single": parsed["single"],
           "last_review": parsed.get("last_review"), "must_do": [], "cross_entry": [],
           "entry_bloat": [], "stale": [], "conflicts": [], "due": False, "due_reasons": []}

    if not parsed["exists"]:
        rep["due"] = True
        rep["due_reasons"] = parsed.get("due_reasons", [])
        return rep

    # 1) 容量
    ns, ng = len(parsed["stable"]), len(parsed["single"])
    if ns > CAP_STABLE_HARD:
        rep["must_do"].append(f"[容量] 稳定偏好 {ns} 行，超过 {CAP_STABLE_HARD} 行硬上限：先合并近似项，"
                              f"再把只服务单一图型的偏好下沉到对应条目的「复用要点」")
    elif ns >= CAP_STABLE_SOFT:
        rep["due_reasons"].append(f"稳定偏好 {ns} 行接近上限（{CAP_STABLE_SOFT}/{CAP_STABLE_HARD}）")
    if ng > CAP_SINGLE_HARD:
        rep["must_do"].append(f"[容量] 单次观察 {ng} 条，超过 {CAP_SINGLE_HARD} 条：清退过期未复现项或晋升")
    elif ng >= CAP_SINGLE_SOFT:
        rep["due_reasons"].append(f"单次观察 {ng} 条接近上限（{CAP_SINGLE_SOFT}/{CAP_SINGLE_HARD}）")

    # 2) 格式与升降级（"显式声明待晋升"的单次观察交给第 4 步，避免重复报同一行）
    for e in parsed["stable"] + parsed["single"]:
        if e["issues"] and not (e["section"] == "single" and e["declared"]):
            rep["must_do"].append(f"[格式/升降级] 第 {e['lineno']} 行：{'; '.join(e['issues'])} — {e['body'][:60]}")

    # 3) 偏好行重复/近似 → 合并候选
    all_prefs = parsed["stable"] + parsed["single"]
    for c in cluster(all_prefs, lambda x: x["body"], DUP_SIM):
        if len(c) > 1:
            desc = " / ".join(f"L{x['lineno']}" for x in c)
            rep["must_do"].append({"kind": "merge", "lines": [x["lineno"] for x in c],
                                   "bodies": [x["body"] for x in c],
                                   "text": f"[合并] {len(c)} 行近似（{desc}）：合并为一条，次数与日期累加 ｜ "
                                           + " ｜ ".join(x["body"][:60] for x in c)})

    # 4) 单次观察晋升：用户显式声明为通用，或组内累计次数 ≥2
    for e in parsed["single"]:
        if e["declared"]:
            rep["must_do"].append({"kind": "promote", "lines": [e["lineno"]], "total": e["count"] or 1,
                                   "text": f"[晋升] 第 {e['lineno']} 行：用户已显式声明为通用规则 → 晋升稳定偏好："
                                           + e["body"][:80]})
    declared_lines = {e["lineno"] for e in parsed["single"] if e["declared"]}
    for c in cluster([e for e in parsed["single"] if e["lineno"] not in declared_lines],
                     lambda x: x["body"], DUP_SIM):
        total = sum(x["count"] or 1 for x in c)
        if len(c) >= 2 or total >= 2:
            rep["must_do"].append({"kind": "promote", "lines": [x["lineno"] for x in c],
                                   "total": total,
                                   "text": f"[晋升] 单次观察 {len(c)} 条一致（合计 {total} 次）→ 晋升稳定偏好："
                                           + " ｜ ".join(x["body"][:60] for x in c)})

    # 5) 跨条目复现：部分偏好 → 整体偏好
    #    只看「复用要点」与「演化记录」：schema 要求 related 双方各写一句「与相近条目的对比」，
    #    那类句子天然会在两条目里重复，拿来当"该晋升的跨条目规则"是噪声。
    promotable = [r for r in rules if r["section"] != "对比"]
    for c in cluster(promotable, lambda x: x["text"], CROSS_SIM):
        entries = sorted({x["entry"] for x in c})
        if len(entries) < 2:
            continue
        body = max((x["text"] for x in c), key=len)
        if covered_by_global(body, all_prefs, GLOBAL_SIM):
            continue
        rep["cross_entry"].append({"entries": entries, "text": body[:220],
                                   "samples": [{"entry": x["entry"], "text": x["text"][:160]} for x in c[:4]],
                                   "kind": "promote_from_entries"})

    # 6) 条目内堆积：演化记录过多 → 折叠
    by_entry = {}
    for r in collect_evolutions(root):
        by_entry.setdefault(r["entry"], []).append(r["text"])
    for entry, items in sorted(by_entry.items()):
        if len(items) >= ENTRY_BLOAT:
            rep["entry_bloat"].append({"entry": entry, "count": len(items),
                                       "hint": f"{entry} 有 {len(items)} 条演化记录：把已被取代的收敛进"
                                               f"「复用要点」，只留仍然生效的缺省"})

    # 7) 过期未复现的单次观察
    for e in parsed["single"]:
        if not e["dates"]:
            continue
        last = max(e["dates"])
        try:
            d = datetime.date.fromisoformat(last)
        except ValueError:
            continue
        age = (today - d).days
        if age > stale_days:
            rep["stale"].append({"line": e["lineno"], "age": age, "date": last,
                                 "text": e["body"][:120]})

    # 8) 疑似冲突：近似但一方带否定
    for c in cluster(parsed["stable"], lambda x: x["body"], 0.5):
        if len(c) < 2:
            continue
        neg = [x for x in c if NEGATION.search(x["body"])]
        pos = [x for x in c if not NEGATION.search(x["body"])]
        if neg and pos:
            rep["conflicts"].append({"lines": [x["lineno"] for x in c],
                                     "hint": "近似表述中既有肯定又有否定，可能是被推翻的旧偏好未清理",
                                     "bodies": [x["body"][:80] for x in c]})

    # 9) 节律判定（空档案不算到期：刚初始化的图库不该被要求"整理"）
    if not parsed["stable"] and not parsed["single"] and not parsed["reviews"]:
        rep["due"] = False
        rep["due_reasons"] = []
        return rep
    evolutions = collect_evolutions(root)
    if rep["last_review"]:
        try:
            last = datetime.date.fromisoformat(rep["last_review"])
            if (today - last).days > due_days:
                rep["due_reasons"].append(f"距上次整理（{rep['last_review']}）已 {(today - last).days} 天 > {due_days} 天")
            new_ev = [r for r in evolutions if max(re.findall(r"\d{4}-\d{2}-\d{2}", r["text"]) or ["0000-00-00"]) > rep["last_review"]]
            if len(new_ev) >= EVOLUTIONS_SINCE_REVIEW:
                rep["due_reasons"].append(f"自上次整理以来新增 {len(new_ev)} 条演化记录（阈值 {EVOLUTIONS_SINCE_REVIEW}）")
        except ValueError:
            pass
    else:
        rep["due_reasons"].append("整理记录为空——建议现在做第一次整理")

    # 跨条目复现只是"考虑晋升"的提示，不参与到期判定：一条只服务同一图族的规则
    # 长期留在条目里是正确状态，不该让 --check 每次都说"该整理了"。
    rep["due"] = bool(rep["due_reasons"]) or bool(rep["must_do"])
    return rep


# ---------------------------------------------------------------- 输出

def _must_do_text(item):
    return item if isinstance(item, str) else item["text"]


def render(rep: dict, top: int) -> str:
    L = [f"# 偏好整理报告（{rep['today']}）", "",
         f"图库: {rep['library']}",
         f"上次整理: {rep['last_review'] or '无记录'}",
         f"节律判定: {'**该整理了**' if rep['due'] else '未到期'}",
         f"容量: 稳定偏好 {len(rep['stable'])} 行 / 单次观察 {len(rep['single'])} 条", ""]
    if rep["due_reasons"]:
        L += ["触发原因:"] + [f"- {r}" for r in rep["due_reasons"]] + [""]
    L += ["## 1. 必做（机械可判定）"]
    L += [f"- {_must_do_text(x)}" for x in rep["must_do"][:top]] or ["- （无）"]
    if len(rep["must_do"]) > top:
        L.append(f"- …另有 {len(rep['must_do']) - top} 项（--top 调大或看 --json）")
    L += ["", "## 2. 跨条目复现（部分偏好 → 整体偏好）"]
    if rep["cross_entry"]:
        for c in rep["cross_entry"][:top]:
            L.append(f"- 出现在 {', '.join(c['entries'])}：{c['text']}")
            L.append("  → 若这条规则跨图型通用，写进 PREFERENCES.md 并注明适用范围；"
                     "若只服务同一图族（如都属 Milo），保持在各条目里并用 related 互指即可")
    else:
        L.append("- （无）")
    L += ["", "## 3. 条目内堆积（收敛到条目自身的「复用要点」）"]
    L += [f"- {b['hint']}" for b in rep["entry_bloat"][:top]] or ["- （无）"]
    L += ["", f"## 4. 过期单次观察（> {rep.get('stale_days', 60)} 天未复现）"]
    L += [f"- L{s['line']}（{s['date']}，{s['age']} 天）{s['text']}" for s in rep["stale"][:top]] or ["- （无）"]
    L += ["", "## 5. 疑似冲突（人工判断）"]
    L += [f"- L{','.join(map(str, c['lines']))}: {c['hint']}" for c in rep["conflicts"][:top]] or ["- （无）"]
    L += ["", "## 收尾动作（按 references/preference-profile.md 的五步整理流程）",
          "1. 逐项执行上面的合并/晋升/降级/下沉/清退，只改 PREFERENCES.md 与相关条目",
          "2. 在 PREFERENCES.md 的 `## 整理记录` 追加一行：`- YYYY-MM-DD 整理：晋升 N、合并 N、降级 N、清退 N、下沉 N`",
          "3. 跑 `scripts/build_index.py` 重建索引（若动过 figure.md）",
          "4. 若 harness 原生记忆/托管技能里另存了一份同类偏好（如 omp managed-skills），用 `--digest` 刷新，避免漂移",
          "5. 完成后重跑本脚本，必做项应清空"]
    return "\n".join(L)


def digest(rep: dict, with_single: bool) -> str:
    L = [f"# 生信绘图偏好（整理于 {rep['today']}，源: library/PREFERENCES.md）", "", "## 稳定偏好"]
    L += [f"- {e['body']}" for e in rep["stable"]] or ["- （无）"]
    if with_single:
        L += ["", "## 单次观察（备查，不构成规则）"]
        L += [f"- {e['body']}" for e in rep["single"]] or ["- （无）"]
    L += ["", "画任何图之前：先 `retrieve.py \"<需求>\"` 查图库，命中就临摹式复用，未命中才从头设计。"]
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--library", help="图库根目录")
    parser.add_argument("--check", action="store_true", help="只判定该不该整理（到期/有必做项 → 退出码 1）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--digest", action="store_true", help="输出可粘贴进 harness 记忆的偏好摘要")
    parser.add_argument("--with-single", action="store_true", help="digest 里带上单次观察")
    parser.add_argument("--due-days", type=int, default=30, help="距上次整理多少天算到期（默认 30）")
    parser.add_argument("--stale-days", type=int, default=60, help="单次观察多少天未复现算过期（默认 60）")
    parser.add_argument("--top", type=int, default=20, help="每节最多列几项（默认 20）")
    args = parser.parse_args()

    root = resolve_library(args.library)
    rep = analyze(root, args.due_days, args.stale_days)
    rep["stale_days"] = args.stale_days

    if args.digest:
        print(digest(rep, args.with_single))
        return 0
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0
    if args.check:
        if rep["due"]:
            print("该整理了:")
            for r in rep["due_reasons"]:
                print(f"  - {r}")
            for x in rep["must_do"]:
                print(f"  - {_must_do_text(x)}")
            for c in rep["cross_entry"]:
                print(f"  - 跨条目复现（{', '.join(c['entries'])}）: {c['text'][:80]}")
            return 1
        print("偏好档案未到整理节律，无需整理。")
        return 0
    print(render(rep, args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
