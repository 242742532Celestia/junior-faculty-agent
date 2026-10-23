#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lint_defensive.py -- 防御性表达枚举器（机器层）。

分工原则：本脚本只做“枚举”，不做“判断”。
它把句子里可能属于防御性表达的片段挑出来，连同行号、规则 ID、级别、
“为什么可能是问题”和改写方向一起交给作者；是否真的构成问题、是否该改，
由作者逐条做语义判断后决定。脚本不自动替换任何词。

用法：
    python lint_defensive.py --file paper.md [--file notes.md ...]
    python lint_defensive.py --stdin < paper.md
    python lint_defensive.py --file paper.md --json
    python lint_defensive.py --selftest

退出码：
    0  未发现候选
    1  发现候选
    2  用法错误或运行故障（selftest 不通过同样用 2）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

VERSION = "1.0.0"

# 仓库根与技能目录（由 __file__ 推导，不硬编码任何机器绝对路径）
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(SKILL_DIR))

LEVEL_RANK = {"low": 0, "medium": 1, "high": 2}

# ---------------------------------------------------------------------------
# 规则表：按“功能”分类，而不是一张弱化词清单
# ---------------------------------------------------------------------------
RULES = [
    {
        "id": "HEDGE",
        "name": "过度对冲",
        "level": "medium",
        "why": (
            "连续的弱化语气让读者无法判断结论到底有多强。证据既然支持一个结论，"
            "就应把结论写出来，强度应当由证据和数据决定，而不是由语气词决定。"
        ),
        "fix": (
            "先确认这批证据支持到什么强度，再把弱化词换成对应的确定性表述；"
            "如果证据确实不足，改写成明确的“尚未检验 / 不适用于该场景”，"
            "而不是保留模糊语气。"
        ),
        "patterns": [
            ("可能", r"可能"),
            ("也许", r"也许"),
            ("或许", r"或许"),
            ("或可", r"或可"),
            ("似乎", r"似乎"),
            ("某种程度上", r"某种程度上"),
            ("一定程度上", r"一定程度上"),
        ],
    },
    {
        "id": "SELFDEP",
        "name": "自我贬低",
        "level": "high",
        "why": (
            "把自己的工作说成“只是尝试 / 简单方法”，等于替读者预设了一个负面结论；"
            "读者形成的第一印象很难靠后文的证据挽回。"
        ),
        "fix": (
            "按实际贡献陈述工作：做了什么、相对已有工作多了哪一点、边界在哪里。"
            "不要在引言或讨论部分替读者做价值判断。"
        ),
        "patterns": [
            ("我们只是尝试", r"我们(?:只是|仅仅只是|只不过)?(?:尝试|试图|试着)"),
            ("仅仅是简单的方法", r"(?:仅仅|只是)(?:是)?(?:一个|一种)?简单(?:的)?(?:方法|做法|模型|框架|工作|尝试)"),
            ("不足为道", r"不足为道"),
            ("这很粗糙", r"(?:当然[,，]?)?(?:这|该)(?:很|有点|稍显)?(?:粗糙|粗略|简陋|不完善)"),
            ("微不足道的贡献", r"(?:仅仅|只是)(?:是)?(?:一个|点|些)?(?:微小|微不足道|有限)?的?贡献"),
            ("不值得一提", r"不值一提"),
        ],
    },
    {
        "id": "RESP",
        "name": "责任外推",
        "level": "high",
        "why": (
            "把结论的限制说成外部条件造成（篇幅、数据、算力），读者会读到一种推诿感；"
            "真正的限制应当写清楚是本研究自身的设计选择，并给出具体边界。"
        ),
        "fix": (
            "把“为什么没做”写成可核查的边界说明：缺哪一项数据、哪一组对照、"
            "哪一个分析，以及它对结论适用范围的影响；不要用泛化的外部条件带过。"
        ),
        "patterns": [
            ("受限于", r"受限于[^，。；！？\n]{0,16}"),
            ("篇幅所限", r"(?:由于|因|因为)?[^，。；！？\n]{0,6}篇幅(?:限制|所限|关系)"),
            ("无法进一步讨论", r"(?:无法|不能|尚无法)[^，。；！？\n]{0,6}(?:进一步|更深入地|更深入)?(?:讨论|分析|探讨|验证|检验|解释)"),
            ("不再展开", r"(?:不再|未再)[^，。；！？\n]{0,4}(?:展开|进一步讨论)"),
        ],
    },
    {
        "id": "DISCLAIM",
        "name": "先行免责",
        "level": "medium",
        "why": (
            "在正文开头先替读者免责，会让读者带着“这份工作不算数”的预设往下读；"
            "限定条件应当与具体结论绑定，而不是作为一段开场白。"
        ),
        "fix": (
            "把免责语气改写成与结论绑定的限定：说明该结论适用于什么范围、"
            "在哪一步还需要验证，并把它放到出现该结论的段落里。"
        ),
        "patterns": [
            ("当然，这只是初步结果", r"当然[,，][^。！？\n]{0,8}(?:这|它|本文|本研究)?(?:只是|仅是|不过是)[^。！？\n]{0,8}(?:初步|一个初步|尝试性|探索性)"),
            ("我们无意", r"我们无意[^。！？\n]{0,10}"),
            ("无意暗示", r"无意[^。！？\n]{0,8}(?:暗示|冒犯|贬低|夸大)"),
            ("勿过度解读", r"(?:勿|不要|不应|不能)[^。！？\n]{0,8}过度(?:解读|解读|理解|诠释)"),
            ("本文只是一项初步研究", r"本文(?:只是|仅是)[^。！？\n]{0,10}(?:初步|探索性|尝试性|一项)"),
            ("需要强调的是……只是", r"需要强调的是[,，][^。！？\n]{0,20}(?:这(?:只是|仅是)|仅是)"),
            ("本文无意主张", r"(?:本文|本研究)(?:无意|并不意图|不寻求)[^。！？\n]{0,10}"),
        ],
    },
    {
        "id": "AGENT",
        "name": "模糊化施动者",
        "level": "high",
        "why": (
            "用“研究显示 / 有结果表明”代替具体来源，读者无法追溯是哪一项工作、"
            "用的是什么方法做出的判断，可核查性因此下降。"
        ),
        "fix": (
            "把施动者写实：谁、用什么材料、做了什么分析、得到什么结果。"
            "引用他人时给出可定位的引文；陈述自己工作时点明方法与分析对象。"
        ),
        "patterns": [
            ("研究显示", r"(?<!本文)(?<!本研究)(?<!我们的)(?<!该)(?<!本)(?:研究|文献|实验|结果|数据|证据|学者|专家)(?:显示|表明|证明|说明|指出|支持|证实)"),
            ("有研究显示", r"有(?:研究|文献|实验|结果|学者|研究工作)(?:显示|表明|证明|说明|指出)"),
            ("先前研究表明", r"(?:先前|已有|以往|此前)(?:研究|工作|文献)(?:显示|表明|证明|说明)"),
            ("学者们认为", r"(?:学者们|研究者们|科学家们|专家们)(?:认为|指出|表明)"),
            ("大量研究表明", r"大量(?:研究|文献|证据)(?:显示|表明|证明|说明)"),
        ],
    },
    {
        "id": "SUBJ",
        "name": "主观化归因",
        "level": "low",
        "why": (
            "用“众所周知 / 不难发现 / 显然”代替论证，等于把举证责任转移给读者；"
            "这些词本身不提供任何信息。"
        ),
        "fix": (
            "删掉这类空转的评价语，把它们背后的判断补成一句可核查的陈述，"
            "或者直接引用支持该判断的证据。"
        ),
        "patterns": [
            ("众所周知", r"众所周知"),
            ("不难发现", r"不难(?:发现|看出|理解)"),
            ("显然", r"显然"),
            ("显而易见", r"显而易见"),
            ("不言而喻", r"不言而喻"),
            ("毫无疑问", r"毫无疑问"),
        ],
    },
]

# ---------------------------------------------------------------------------
# 受保护判据：识别到就不得报为问题
# suppress 列出该判据可以压制的规则 ID
# ---------------------------------------------------------------------------
PROTECTED = [
    {
        "id": "P1",
        "name": "范围限定",
        "desc": "结论已被明确限定在某个数据集 / 样本 / 语料范围内。",
        "pattern": r"在(?:本|该|此|本文|本研究|我们|我们的)[^，。；！？\n]{0,8}(?:数据集|数据|样本|语料|子集)(?:上|中|内)?",
        "suppress": ["HEDGE", "AGENT", "SUBJ"],
    },
    {
        "id": "P2",
        "name": "效应量小但差异稳定",
        "desc": "已区分统计显著与效应量，并给出效应量数值，属于必要的精确表述。",
        "pattern": r"(?:效应量|effect size)[^，。；！？\n]{0,14}(?:较小|偏小|不大|很小|偏低)|(?:效应量|effect size|Cohen'?s\s*d|\bd)\s*[=＝]\s*0?\.\d+",
        "suppress": ["HEDGE", "SUBJ", "DISCLAIM"],
    },
    {
        "id": "P3",
        "name": "统计不显著",
        "desc": "如实报告“未检出显著差异”，属于必须保留的结论，不得当作对冲。",
        "pattern": r"(?:未检出|未发现|未观察到)[^，。；！？\n]{0,14}(?:显著|统计显著|差异|效应|相关|影响)|(?:差异|效应|相关性)[^，。；！？\n]{0,8}(?:不显著|未达显著|无统计显著性)|p\s*[>≥＝=]\s*0?\.\d+|不具(?:备)?统计显著性",
        "suppress": ["HEDGE", "SUBJ", "DISCLAIM"],
    },
    {
        "id": "P4",
        "name": "样本受限",
        "desc": "已写明样本量或预实验性质，属于必要的设计说明。",
        "pattern": r"(?:预实验|初步(?:研究|实验|探索)|小样本(?:研究)?|试点|探索性研究|样本量有限)|n\s*=\s*\d+[^，。；！？\n]{0,12}(?:预实验|初步|探索)",
        "suppress": ["HEDGE", "SELFDEP", "RESP", "DISCLAIM", "SUBJ"],
    },
    {
        "id": "P5",
        "name": "条件性结论",
        "desc": "结论已绑定具体条件，属于限定性陈述。",
        "pattern": r"在[^，。；！？\n]{1,20}(?:条件下|情况下|情形下|设定下|场景下)|当[^，。；！？\n]{1,20}时[，,]",
        "suppress": ["HEDGE", "AGENT", "SUBJ"],
    },
    {
        "id": "P6",
        "name": "明确的未来工作声明",
        "desc": "明确声明后续工作方向，属于必要的前瞻性陈述。",
        "pattern": r"(?:未来|后续|下一步|尚待|有待)[^，。；！？\n]{0,20}(?:研究|工作|验证|检验|评估|分析|探索)|(?:需要|应|将在)[^，。；！？\n]{0,16}(?:在后续|在未来的)[^，。；！？\n]{0,12}(?:研究|工作|验证|检验)|留待(?:未来|后续)",
        "suppress": ["HEDGE", "DISCLAIM", "RESP", "SUBJ"],
    },
    {
        "id": "P7",
        "name": "涉及他人的错误归因",
        "desc": "在指出他人工作的问题，属于必要的学术讨论。",
        "pattern": r"(?:错误|疏漏|失误|误解)[^，。；！？\n]{0,10}(?:在于|来自|源于|出在)|(?:前人|先前研究|先前工作|文献|原文|该文|他人|作者)[^，。；！？\n]{0,20}(?:错误|疏漏|失误|误解)",
        "suppress": ["HEDGE", "SUBJ", "RESP", "AGENT"],
    },
    {
        "id": "P8",
        "name": "引用他人观点",
        "desc": "句子在转述他人成果或观点，弱化词属于转述语气的一部分。",
        "pattern": r"(?:文献|前人|先前研究|已有研究|原文|作者|该文|他人)[^，。；！？\n]{0,14}(?:指出|认为|主张|强调|声称|提议)|如[^，。；！？\n]{0,8}所述|(?:引述|转述)[^，。；！？\n]{0,10}(?:观点|结论)|\[\d+\]",
        "suppress": ["HEDGE", "AGENT", "SUBJ", "DISCLAIM"],
    },
]

# ---------------------------------------------------------------------------
# 切分与保护
# ---------------------------------------------------------------------------
_SENT_END = "\u3002\uff01\uff1f\uff1b\u2026!?;"
_CLOSERS = "\u201d\u2019\u300d\u300f\"'\uff09\uff09\u300b\u3011"


def _emit_segment(text, start, end, out):
    raw = text[start:end]
    stripped = raw.strip()
    if not stripped:
        return
    offset = start + (len(raw) - len(raw.lstrip()))
    out.append((stripped, offset))


def _split_sentences(text):
    """切句：中文与英文标点都处理，保留每句在原串中的起始偏移。"""
    out = []
    start = 0
    i = 0
    n = len(text)
    abbrevs = (
        "et", "al", "fig", "eq", "eqs", "ref", "refs", "no", "vs", "cf",
        "e.g", "i.e", "dr", "prof", "inc", "ltd", "vol", "pp", "ch",
    )
    while i < n:
        ch = text[i]
        if ch in _SENT_END:
            j = i + 1
            while j < n and text[j] in _CLOSERS:
                j += 1
            _emit_segment(text, start, j, out)
            start = j
            i = j
            continue
        if ch == ".":
            k = i + 1
            while k < n and text[k] in " \t":
                k += 1
            if k >= n or text[k].isupper() or text[k] in "\"'(":
                window = text[max(0, i - 10):i + 1]
                ab = re.search(r"([A-Za-z]+)\.$", window)
                if ab and (len(ab.group(1)) == 1 or ab.group(1).lower() in abbrevs):
                    i += 1
                    continue
                if i > 0 and text[i - 1].isdigit() and k < n and text[k].isdigit():
                    i += 1
                    continue
                j = i + 1
                while j < n and text[j] in _CLOSERS:
                    j += 1
                _emit_segment(text, start, j, out)
                start = j
                i = j
                continue
        i += 1
    _emit_segment(text, start, n, out)
    return out


def _build_units(text):
    """按段落 / 列表项 / 表格行 / 引用块切分；标题与代码块不进入分析。"""
    units = []
    lines = text.split("\n")
    in_code = False
    para = []

    def flush_para():
        if para:
            units.append({"kind": "para", "parts": list(para)})
            del para[:]

    for idx, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith("```") or s.startswith("~~~"):
            flush_para()
            in_code = not in_code
            continue
        if in_code:
            continue
        if not s:
            flush_para()
            continue
        if s.startswith("#"):
            flush_para()
            continue
        if re.match(r"^([-*_]\s*){3,}$", s):
            flush_para()
            continue
        if s.startswith(">"):
            flush_para()
            units.append({"kind": "quote", "parts": [(idx, re.sub(r"^>\s?", "", s))]})
            continue
        if s.startswith("|"):
            flush_para()
            units.append({"kind": "table", "parts": [(idx, s.strip("| \t"))]})
            continue
        item = re.match(r"^(?:[-*+\u2022]|\d+[.)])\s+(.*)$", s)
        if item:
            flush_para()
            units.append({"kind": "list", "parts": [(idx, item.group(1))]})
            continue
        para.append((idx, s))
    flush_para()
    return units


def _unit_sentences(unit):
    parts = unit["parts"]
    pieces = []
    mapping = []
    pos = 0
    for lineno, txt in parts:
        if pieces:
            pieces.append("\n")
            pos += 1
        mapping.append((pos, pos + len(txt), lineno))
        pieces.append(txt)
        pos += len(txt)
    joined = "".join(pieces)
    result = []
    for seg, off in _split_sentences(joined):
        line = mapping[-1][2]
        for s, e, ln in mapping:
            if s <= off <= e:
                line = ln
                break
        result.append((seg, off, line))
    return result


def _find_quote_spans(text):
    """引号与行内代码区间：命中其中的片段视为引文原文。"""
    spans = []
    pairs = (("\u201c", "\u201d"), ("\u300c", "\u300d"), ("\u2018", "\u2019"))
    for opener, closer in pairs:
        idx = 0
        while True:
            i = text.find(opener, idx)
            if i < 0:
                break
            j = text.find(closer, i + 1)
            if j < 0:
                break
            spans.append((i, j + 1))
            idx = j + 1
    idx = 0
    while True:
        i = text.find('"', idx)
        if i < 0:
            break
        j = text.find('"', i + 1)
        if j < 0:
            break
        spans.append((i, j + 1))
        idx = j + 1
    for m in re.finditer(r"`[^`\n]+`", text):
        spans.append((m.start(), m.end()))
    return spans


def _in_spans(start, end, spans):
    for s, e in spans:
        if s <= start and end <= e:
            return True
    return False


def _protection_for(sentence, rule_id):
    """返回压制该规则的受保护判据；没有则返回 None。"""
    for item in PROTECTED:
        if rule_id in item["suppress"] and re.search(item["pattern"], sentence):
            return item
    return None


def _dedupe_spans(spans):
    spans = sorted(spans, key=lambda t: (t[0], -t[1]))
    out = []
    for s, e in spans:
        overlap = False
        for os_, oe in out:
            if s < oe and os_ < e:
                overlap = True
                break
        if not overlap:
            out.append((s, e))
    return out


def analyze_text(text):
    """返回 (candidates, suppressed)。candidates 为需要人工判断的候选。"""
    candidates = []
    suppressed = []
    for unit in _build_units(text):
        is_quote_unit = unit["kind"] == "quote"
        for seg, off, lineno in _unit_sentences(unit):
            quote_spans = _find_quote_spans(seg)
            hits = {}
            for rule in RULES:
                for label, pattern in rule["patterns"]:
                    for m in re.finditer(pattern, seg):
                        s, e = m.start(), m.end()
                        token = m.group(0)
                        if is_quote_unit:
                            suppressed.append({"line": lineno, "rule": rule["id"], "match": token, "protected_by": "P9"})
                            continue
                        if _in_spans(s, e, quote_spans):
                            suppressed.append({"line": lineno, "rule": rule["id"], "match": token, "protected_by": "P9"})
                            continue
                        prot = _protection_for(seg, rule["id"])
                        if prot is not None:
                            suppressed.append({
                                "line": lineno,
                                "rule": rule["id"],
                                "match": token,
                                "protected_by": prot["id"],
                            })
                            continue
                        hits.setdefault(rule["id"], []).append((s, e, token, label))
            if not hits:
                continue
            level = "low"
            rule_ids = []
            rule_names = []
            matched = []
            why_parts = []
            fix_parts = []
            for rule in RULES:
                if rule["id"] not in hits:
                    continue
                spans = _dedupe_spans([(s, e) for s, e, _, _ in hits[rule["id"]]])
                kept = []
                for s, e, token, label in hits[rule["id"]]:
                    if (s, e) in spans:
                        kept.append(token)
                rule_level = rule["level"]
                if len(spans) >= 3 and LEVEL_RANK[rule_level] < LEVEL_RANK["high"]:
                    rule_level = "high"
                if LEVEL_RANK[rule_level] > LEVEL_RANK[level]:
                    level = rule_level
                rule_ids.append(rule["id"])
                rule_names.append(rule["name"])
                matched.extend(kept)
                why_parts.append("[{0}] {1}".format(rule["name"], rule["why"]))
                fix_parts.append("[{0}] {1}".format(rule["name"], rule["fix"]))
            candidates.append({
                "line": lineno,
                "sentence": seg,
                "rule_ids": rule_ids,
                "rule_names": rule_names,
                "level": level,
                "matched": matched,
                "why": " ".join(why_parts),
                "suggest": " ".join(fix_parts),
            })
    return candidates, suppressed


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
def _short(text, limit=180):
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _print_human(results):
    total = 0
    for res in results:
        cands = res["candidates"]
        print("=" * 68)
        print("文件: {0}".format(res["path"]))
        counts = {"high": 0, "medium": 0, "low": 0}
        for c in cands:
            counts[c["level"]] += 1
        total += len(cands)
        print("候选 {0} 处（high {1} / medium {2} / low {3}）；受保护而静默 {4} 处".format(
            len(cands), counts["high"], counts["medium"], counts["low"], len(res["suppressed"])))
        if not cands:
            print("  未发现防御性表达候选。")
        for c in cands:
            print("")
            print("  行 {0}  [{1}]  {2}".format(c["line"], c["level"], ", ".join(c["rule_ids"])))
            print("    规则: {0}".format(" / ".join(c["rule_names"])))
            print("    句子: {0}".format(_short(c["sentence"])))
            print("    命中: {0}".format("、".join(c["matched"])))
            print("    为什么可能是问题: {0}".format(c["why"]))
            print("    改写方向: {0}".format(c["suggest"]))
    print("")
    print("=" * 68)
    print("合计候选 {0} 处。机器只枚举、不下结论：每一条都请自行判断是否构成问题。".format(total))
    return total


def _print_json(results):
    payload = {
        "tool": "lint_defensive",
        "version": VERSION,
        "skill_dir": SKILL_DIR,
        "note": "机器只枚举候选，不做语义判断；受保护句已被排除，请逐条人工复核后再改写。",
        "files": [],
        "total_candidates": 0,
    }
    for res in results:
        payload["files"].append({
            "path": res["path"],
            "candidates": res["candidates"],
            "suppressed": res["suppressed"],
            "counts": {
                "high": len([c for c in res["candidates"] if c["level"] == "high"]),
                "medium": len([c for c in res["candidates"] if c["level"] == "medium"]),
                "low": len([c for c in res["candidates"] if c["level"] == "low"]),
                "suppressed": len(res["suppressed"]),
            },
        })
        payload["total_candidates"] += len(res["candidates"])
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload["total_candidates"]


# ---------------------------------------------------------------------------
# 自检（离线）
# ---------------------------------------------------------------------------
SELFTEST_CASES = [
    # (期望被报出, 必须出现的规则 ID, 句子)
    (True, {"HEDGE", "SELFDEP"}, "我们只是尝试性地使用了一种简单的方法，结果可能说明了一些问题。"),
    (True, {"RESP"}, "受限于篇幅，我们无法进一步讨论这一设定的影响。"),
    (True, {"DISCLAIM"}, "当然，这只是初步结果，请勿过度解读。"),
    (True, {"AGENT"}, "研究显示，该方法显著提升了准确率。"),
    (True, {"SUBJ"}, "众所周知，该现象在多个领域均有观察。"),
    # 以下为受保护句，必须不被报出
    (False, set(), "在本数据集上，结果可能略有提升。"),
    (False, set(), "在 n=23 的预实验中，可能未检出显著差异。"),
    (False, set(), "在高温条件下，该方法可能优于基线。"),
    (False, set(), "未来研究可能进一步检验该效应是否稳定。"),
    (False, set(), "众所周知，这一错误来自先前工作的误用。"),
    (False, set(), "正如文献[3]所指出的，该方法可能存在偏差。"),
]


def _run_selftest():
    failures = []
    checked = 0

    for expect, need, sentence in SELFTEST_CASES:
        checked += 1
        cands, _ = analyze_text(sentence)
        got_ids = set()
        for c in cands:
            got_ids.update(c["rule_ids"])
        if expect:
            missing = need - got_ids
            if missing:
                failures.append("应被报出但缺少规则 {0}: {1}".format(sorted(missing), sentence))
        else:
            if cands:
                failures.append("受保护句被误报: {0} -> {1}".format(sentence, [c["rule_ids"] for c in cands]))

    # 结构类断言
    checks = [
        ("标题不当作句子", "# 可能与或许：研究显示", 0),
        ("代码块跳过", "```\n我们只是尝试\n```", 0),
        ("引文原文受保护", "\u201c我们只是尝试\u201d这句话引自他人。", 0),
        ("列表项被检查", "- 我们只是尝试了一种简单的方法。", 1),
        ("表格行被检查", "| 备注 | 我们只是尝试 |", 1),
    ]
    for label, text, expect_min in checks:
        checked += 1
        cands, _ = analyze_text(text)
        if len(cands) < expect_min:
            failures.append("{0}: 期望至少 {1} 个候选，实际 {2}".format(label, expect_min, len(cands)))

    # 行号定位
    checked += 1
    doc = "第一段没有问题。\n\n我们只是尝试了一个简单的方法，可能有效。\n"
    cands, _ = analyze_text(doc)
    if not cands or cands[0]["line"] != 3:
        failures.append("行号定位错误: {0}".format([c["line"] for c in cands]))

    # 字节解码（Windows 管道常见编码差异）
    for label, enc in (("UTF-8", "utf-8"), ("GBK", "gbk")):
        checked += 1
        try:
            decoded = _decode_bytes("可能".encode(enc))
        except Exception as exc:  # pragma: no cover - 防御性
            decoded = "异常: {0}".format(exc)
        if decoded != "可能":
            failures.append("{0} 字节解码错误: {1}".format(label, decoded))

    if failures:
        print("selftest 失败：{0} 项断言未通过".format(len(failures)))
        for f in failures:
            print("  - {0}".format(f))
        return 2
    print("selftest 通过：{0} 项断言全部成立（含受保护句反向断言）。".format(checked))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _decode_bytes(data):
    """按 UTF-8 / UTF-8-BOM / GBK 依次尝试解码，避免中文管道输入被读成乱码。"""
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _load_text(path):
    with open(path, "rb") as fh:
        data = fh.read()
    return _decode_bytes(data)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="lint_defensive.py",
        description="防御性表达枚举器：只枚举候选，不做语义判断。",
    )
    parser.add_argument("--file", action="append", default=[], help="待检查的 Markdown / 文本文件，可重复")
    parser.add_argument("--stdin", action="store_true", help="从标准输入读取文本")
    parser.add_argument("--json", action="store_true", dest="as_json", help="以 JSON 输出")
    parser.add_argument("--selftest", action="store_true", help="运行内置离线自检")
    args = parser.parse_args(argv)

    if args.selftest:
        return _run_selftest()

    if not args.file and not args.stdin:
        sys.stderr.write("用法错误：至少需要 --file 或 --stdin\n")
        parser.print_usage(sys.stderr)
        return 2

    results = []
    if args.stdin:
        stream = getattr(sys.stdin, "buffer", None)
        raw = stream.read() if stream is not None else sys.stdin.read()
        if isinstance(raw, bytes):
            text = _decode_bytes(raw)
        else:
            text = raw
        cands, sup = analyze_text(text)
        results.append({"path": "<stdin>", "candidates": cands, "suppressed": sup})

    for path in args.file:
        if not os.path.isfile(path):
            sys.stderr.write("用法错误：文件不存在: {0}\n".format(path))
            return 2
        try:
            text = _load_text(path)
        except OSError as exc:
            sys.stderr.write("运行故障：无法读取 {0}: {1}\n".format(path, exc))
            return 2
        cands, sup = analyze_text(text)
        results.append({"path": path, "candidates": cands, "suppressed": sup})

    if args.as_json:
        total = _print_json(results)
    else:
        total = _print_human(results)
    return 1 if total else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
