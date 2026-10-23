#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lint_redflags.py -- 写作雷区扫描器。

A 段（可机检）：空话套话、连接词滥用、标点错误、数字与单位不规范、
符号不成对、段落过长。这些有可判定的形式特征，脚本负责指出位置。

B 段（需人眼）：逻辑跳跃、因果倒置、过度概括、结论超出数据、
伦理 / 利益冲突缺声明。这些没有可靠的形式特征，脚本只输出人工复核清单，
不判定对错，也不计入问题计数。

用法：
    python lint_redflags.py --file paper.md [--file notes.md ...]
    python lint_redflags.py --file paper.md --json
    python lint_redflags.py --file paper.md --max-para-chars 240
    python lint_redflags.py --selftest

退出码：
    0  未发现 A 段问题
    1  发现 A 段问题
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

DEFAULT_MAX_PARA_CHARS = 300

CJK = "\u4e00-\u9fff\u3000-\u303f\uff00-\uffef"

# ---------------------------------------------------------------------------
# A1 空话套话
# ---------------------------------------------------------------------------
A1_CLICHES = [
    ("在当今快速发展的时代", r"在当今(?:快速发展的|信息化|科技飞速发展|经济高速发展|日新月异的)?(?:时代|社会|世界)"),
    ("随着科技的不断进步", r"随着(?:科技的不断进步|科技的飞速发展|技术的不断进步|社会的发展|时代的发展|经济的快速发展|信息技术的飞速发展)"),
    ("日新月异", r"日新月异"),
    ("蓬勃发展", r"(?:蓬勃|蓬勃地|快速)发展"),
    ("举世瞩目", r"举世(?:瞩目|闻名)"),
    ("具有重要意义", r"具有(?:十分|重大|重要|里程碑式)?意义"),
    ("提供了有力支持", r"提供了?有力(?:的)?(?:支持|保证|支撑)"),
]

# ---------------------------------------------------------------------------
# A2 无信息量连接词
# ---------------------------------------------------------------------------
A2_CONNECTIVES = [
    ("值得注意的是", r"值得注意的是"),
    ("不难看出", r"不难看出"),
    ("不难发现", r"不难发现"),
    ("综上所述", r"综上所述"),
    ("总而言之", r"总而言之"),
    ("总的来说", r"总的来说"),
    ("众所周知", r"众所周知"),
    ("显而易见", r"显而易见"),
    ("不言而喻", r"不言而喻"),
    ("毫无疑问", r"毫无疑问"),
    ("毋庸置疑", r"毋庸置疑"),
]

# ---------------------------------------------------------------------------
# A4 数字与单位
# ---------------------------------------------------------------------------
A4_UNITS = (
    r"cm|mm|km|kg|mg|\u03bcg|ug|ng|ml|dl|\u03bcl|ul|nl|L|g|m|s|min|h|"
    r"Hz|kHz|MHz|GHz|MPa|kPa|Pa|ms|us|\u03bcs|\u03bcs|ns|V|mV|kV|A|mA|"
    r"\u03bcA|W|mW|kW|kJ|MJ|J|kN|N|nm|\u03bcm|um|nmol|mmol|mol|ppm|ppb"
)

# ---------------------------------------------------------------------------
# B 段：人工复核清单（不判定对错，不计入问题计数）
# ---------------------------------------------------------------------------
MANUAL_CHECKLIST = [
    {
        "id": "B1",
        "name": "逻辑跳跃",
        "how": "逐段检查“前提 -> 结论”的推理链：中间是否跳过了必要前提、是否存在把相关性直接写成机制的情况。",
    },
    {
        "id": "B2",
        "name": "因果倒置",
        "how": "检查因果表述方向：是否有可能是共同原因、选择偏倚或反向因果；因果词是否与研究设计匹配。",
    },
    {
        "id": "B3",
        "name": "过度概括",
        "how": "检查由单一样本 / 单一场景推出的普遍化表述；结论的适用范围是否与证据的覆盖面一致。",
    },
    {
        "id": "B4",
        "name": "结论超出数据",
        "how": "核对每条结论与对应结果：效应量、区间、样本量、p 值是否支持该表述的强度；未显著不等于无差异。",
    },
    {
        "id": "B5",
        "name": "伦理 / 利益冲突缺声明",
        "how": "检查是否具备伦理审批、知情同意、数据可得性、资助来源、利益冲突与作者贡献声明。",
    },
]

LEVEL_RANK = {"low": 0, "medium": 1, "high": 2}


def _line_index(text):
    lines = text.split("\n")
    starts = []
    pos = 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1
    return lines, starts


def _offset_to_line(starts, offset):
    lo, hi = 0, len(starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= offset:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


def _code_mask(lines):
    """标记处于代码块内的行号。"""
    mask = set()
    in_code = False
    for idx, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith("```") or s.startswith("~~~"):
            in_code = not in_code
            mask.add(idx)
            continue
        if in_code:
            mask.add(idx)
    return mask


def _short(text, limit=120):
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


# ---------------------------------------------------------------------------
# A 段检测
# ---------------------------------------------------------------------------
def _check_a1(lines, mask, findings):
    for idx, raw in enumerate(lines, 1):
        if idx in mask:
            continue
        hits = []
        for label, pattern in A1_CLICHES:
            for m in re.finditer(pattern, raw):
                hits.append((label, m.group(0)))
        if not hits:
            continue
        distinct = len(set(hits))
        level = "high" if distinct >= 2 else "medium"
        names = "、".join(sorted(set(label for label, _ in hits)))
        if distinct >= 2:
            msg = "同一句堆叠了 {0} 处空话套话，读者得不到任何信息。".format(distinct)
        else:
            msg = "出现空话套话“{0}”，未承载具体信息。".format(hits[0][0])
        findings.append({
            "rule": "A1", "name": "空话套话堆砌", "level": level, "line": idx,
            "message": msg, "excerpt": _short(raw.strip()), "detail": names,
        })


def _check_a2(lines, mask, findings):
    doc_count = {}
    for label, pattern in A2_CONNECTIVES:
        total = 0
        for idx, raw in enumerate(lines, 1):
            if idx in mask:
                continue
            total += len(re.findall(pattern, raw))
        doc_count[label] = total
    for idx, raw in enumerate(lines, 1):
        if idx in mask:
            continue
        for label, pattern in A2_CONNECTIVES:
            for m in re.finditer(pattern, raw):
                freq = doc_count.get(label, 0)
                if freq >= 3:
                    level = "high"
                    msg = "“{0}”在本文出现 {1} 次，属于密集使用且不承载信息。".format(label, freq)
                elif freq == 2:
                    level = "medium"
                    msg = "“{0}”在本文出现 {1} 次，密度偏高。".format(label, freq)
                else:
                    level = "low"
                    msg = "“{0}”未承载信息，可直接删除或替换为具体判断。".format(label)
                findings.append({
                    "rule": "A2", "name": "无信息量连接词滥用", "level": level, "line": idx,
                    "message": msg, "excerpt": _short(raw.strip()), "detail": "全文出现 {0} 次".format(freq),
                })


def _check_a3(lines, mask, findings, text, starts):
    half_re = re.compile("(?<=[" + CJK + r"])[,;:]|[,;:](?=[" + CJK + r"])|(?<=[" + CJK + r"])\.(?!\d)")
    dot_full_re = re.compile("(?<=[" + CJK + r"])\.(?!\d)")
    for idx, raw in enumerate(lines, 1):
        if idx in mask:
            continue
        half_hits = half_re.findall(raw)
        dot_hits = dot_full_re.findall(raw)
        count = len(half_hits) + len(dot_hits)
        if count:
            level = "high" if count >= 6 else "medium"
            findings.append({
                "rule": "A3", "name": "中英混排标点错误", "level": level, "line": idx,
                "message": "中文语境中出现 {0} 处半角逗号 / 句号 / 分号，应改用全角标点。".format(count),
                "excerpt": _short(raw.strip()), "detail": "半角标点 {0} 处".format(count),
            })
        if ("，" in raw and "," in raw) or ("（）" in raw and "()" in raw) or ("《" in raw and "<" in raw):
            findings.append({
                "rule": "A3", "name": "中英混排标点错误", "level": "medium", "line": idx,
                "message": "同一行内全角与半角标点混用，需要统一。",
                "excerpt": _short(raw.strip()), "detail": "全半角混用",
            })
    # 括号配对
    stack = []
    pairs = {"(": ")", "\uff08": "\uff09", "[": "]", "\u3010": "\u3011"}
    closers = {v: k for k, v in pairs.items()}
    for m in re.finditer(r"[()\uff08\uff09\[\]\u3010\u3011]", text):
        ch = m.group(0)
        line = _offset_to_line(starts, m.start())
        if ch in pairs:
            stack.append((ch, line))
        elif ch in closers:
            if stack and stack[-1][0] == closers[ch]:
                stack.pop()
            else:
                findings.append({
                    "rule": "A3", "name": "中英混排标点错误", "level": "high", "line": line,
                    "message": "括号不配对：多出一个“{0}”。".format(ch),
                    "excerpt": _short(lines[line - 1].strip()), "detail": "多余右括号",
                })
    for ch, line in stack:
        findings.append({
            "rule": "A3", "name": "中英混排标点错误", "level": "high", "line": line,
            "message": "括号不配对：“{0}”缺少对应的右括号。".format(ch),
            "excerpt": _short(lines[line - 1].strip()), "detail": "缺少右括号",
        })


def _check_a4(lines, mask, findings):
    percent_half = sum(len(re.findall(r"%", raw)) for idx, raw in enumerate(lines, 1) if idx not in mask)
    percent_full = sum(len(re.findall(r"\uff05", raw)) for idx, raw in enumerate(lines, 1) if idx not in mask)
    minority = None
    if percent_half and percent_full:
        minority = "%" if percent_half <= percent_full else "\uff05"
    unit_re = re.compile(r"(?<![0-9A-Za-z.])[0-9]+(?:\.[0-9]+)?(?:" + A4_UNITS + r")(?![A-Za-z])")
    for idx, raw in enumerate(lines, 1):
        if idx in mask:
            continue
        if minority is not None and minority in raw:
            other = "\uff05" if minority == "%" else "%"
            findings.append({
                "rule": "A4", "name": "数字与单位不规范", "level": "medium", "line": idx,
                "message": "百分号写法不统一：本文同时出现“%”与“\uff05”，请统一为其中一种。",
                "excerpt": _short(raw.strip()), "detail": "混用 {0} 与 {1}".format(other, minority),
            })
        for m in unit_re.finditer(raw):
            findings.append({
                "rule": "A4", "name": "数字与单位不规范", "level": "medium", "line": idx,
                "message": "数字与单位之间缺少空格：“{0}”。建议写作“{1} ”或改用中文单位。".format(m.group(0), m.group(0)),
                "excerpt": _short(raw.strip()), "detail": "数字+单位未分隔",
            })
        for m in re.finditer(r"[0-9]\s+%", raw):
            findings.append({
                "rule": "A4", "name": "数字与单位不规范", "level": "low", "line": idx,
                "message": "百分号前不应留空格：“{0}”。".format(m.group(0)),
                "excerpt": _short(raw.strip()), "detail": "百分号前空格",
            })
        for m in re.finditer(r"[0-9]\uff0e[0-9]", raw):
            findings.append({
                "rule": "A4", "name": "数字与单位不规范", "level": "high", "line": idx,
                "message": "中文里的小数点不应使用全角“．”，应写作半角“.”。",
                "excerpt": _short(raw.strip()), "detail": "全角小数点",
            })
        for m in re.finditer(r"[0-9]\uff0c[0-9]", raw):
            findings.append({
                "rule": "A4", "name": "数字与单位不规范", "level": "high", "line": idx,
                "message": "小数不应使用中文逗号“，”作分隔，应写作半角“.”。",
                "excerpt": _short(raw.strip()), "detail": "中文逗号作小数点",
            })


def _check_a5(lines, mask, findings, text, starts):
    quote_pairs = [("\u201c", "\u201d"), ("\u300c", "\u300d"), ("\u300e", "\u300f"), ("\u2018", "\u2019")]
    for opener, closer in quote_pairs:
        opens = [m.start() for m in re.finditer(re.escape(opener), text)]
        closes = [m.start() for m in re.finditer(re.escape(closer), text)]
        if len(opens) > len(closes):
            for off in opens[len(closes):]:
                line = _offset_to_line(starts, off)
                findings.append({
                    "rule": "A5", "name": "引号 / 书名号 / 破折号不成对", "level": "high", "line": line,
                    "message": "“{0}”缺少配对的“{1}”。".format(opener, closer),
                    "excerpt": _short(lines[line - 1].strip()), "detail": "缺少配对符号",
                })
        elif len(closes) > len(opens):
            for off in closes[len(opens):]:
                line = _offset_to_line(starts, off)
                findings.append({
                    "rule": "A5", "name": "引号 / 书名号 / 破折号不成对", "level": "high", "line": line,
                    "message": "“{0}”缺少配对的“{1}”。".format(closer, opener),
                    "excerpt": _short(lines[line - 1].strip()), "detail": "缺少配对符号",
                })
    straight = [m.start() for m in re.finditer(r'"', text)]
    if len(straight) % 2 == 1:
        line = _offset_to_line(starts, straight[-1])
        findings.append({
            "rule": "A5", "name": "引号 / 书名号 / 破折号不成对", "level": "high", "line": line,
            "message": "直引号成对数量为奇数（共 {0} 个），存在未闭合的引号。".format(len(straight)),
            "excerpt": _short(lines[line - 1].strip()), "detail": "直引号不成对",
        })
    for idx, raw in enumerate(lines, 1):
        if idx in mask:
            continue
        for m in re.finditer(r"\u2014(?![\u2014])", raw):
            findings.append({
                "rule": "A5", "name": "引号 / 书名号 / 破折号不成对", "level": "low", "line": idx,
                "message": "单个破折号“—”应写成中文规范的双破折号“——”。",
                "excerpt": _short(raw.strip()), "detail": "单破折号",
            })


def _check_a6(lines, mask, findings, max_chars):
    block = []
    start_line = 0
    for idx, raw in enumerate(lines, 1):
        s = raw.strip()
        is_block = bool(s) and idx not in mask and not s.startswith("#") and not s.startswith("|")
        if is_block:
            if not block:
                start_line = idx
            block.append(s)
            continue
        if block:
            chars = len("".join(block))
            if chars > max_chars:
                level = "high" if chars > max_chars * 2 else "medium"
                findings.append({
                    "rule": "A6", "name": "段落长度异常", "level": level, "line": start_line,
                    "message": "该段落约 {0} 字，超过阈值 {1} 字，建议按论点拆分。".format(chars, max_chars),
                    "excerpt": _short(" ".join(block)), "detail": "行 {0}-{1}".format(start_line, idx - 1),
                })
            block = []
    if block:
        chars = len("".join(block))
        if chars > max_chars:
            level = "high" if chars > max_chars * 2 else "medium"
            findings.append({
                "rule": "A6", "name": "段落长度异常", "level": level, "line": start_line,
                "message": "该段落约 {0} 字，超过阈值 {1} 字，建议按论点拆分。".format(chars, max_chars),
                "excerpt": _short(" ".join(block)), "detail": "段落末尾",
            })


def analyze_text(text, max_para_chars=DEFAULT_MAX_PARA_CHARS):
    """返回 findings（A 段问题）；B 段不计入。"""
    lines, starts = _line_index(text)
    mask = _code_mask(lines)
    findings = []
    _check_a1(lines, mask, findings)
    _check_a2(lines, mask, findings)
    _check_a3(lines, mask, findings, text, starts)
    _check_a4(lines, mask, findings)
    _check_a5(lines, mask, findings, text, starts)
    _check_a6(lines, mask, findings, max_para_chars)
    findings.sort(key=lambda f: (f["line"], f["rule"]))
    return findings


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
def _print_human(results, max_para_chars):
    total = 0
    for res in results:
        findings = res["findings"]
        print("=" * 68)
        print("文件: {0}".format(res["path"]))
        counts = {"high": 0, "medium": 0, "low": 0}
        for f in findings:
            counts[f["level"]] += 1
        total += len(findings)
        print("A 段问题 {0} 处（high {1} / medium {2} / low {3}）".format(
            len(findings), counts["high"], counts["medium"], counts["low"]))
        if not findings:
            print("  未发现可机检的写作雷区。")
        for f in findings:
            print("")
            print("  行 {0}  [{1}]  {2}  {3}".format(f["line"], f["level"], f["rule"], f["name"]))
            print("    说明: {0}".format(f["message"]))
            if f.get("detail"):
                print("    细节: {0}".format(f["detail"]))
            print("    原文: {0}".format(f["excerpt"]))
    print("")
    print("-" * 68)
    print("B 段人工复核清单（需人眼判断，不判定对错，不计入问题计数）")
    for item in MANUAL_CHECKLIST:
        print("  {0} {1}：{2}".format(item["id"], item["name"], item["how"]))
    print("-" * 68)
    print("合计 A 段问题 {0} 处（段落长度阈值 {1} 字）。".format(total, max_para_chars))
    return total


def _print_json(results, max_para_chars):
    payload = {
        "tool": "lint_redflags",
        "version": VERSION,
        "skill_dir": SKILL_DIR,
        "max_para_chars": max_para_chars,
        "note": "A 段为可机检问题并计入计数；B 段为人工复核清单，不判定对错，不计入计数。",
        "files": [],
        "total_findings": 0,
        "manual_checklist": MANUAL_CHECKLIST,
    }
    for res in results:
        payload["files"].append({
            "path": res["path"],
            "findings": res["findings"],
            "counts": {
                "high": len([f for f in res["findings"] if f["level"] == "high"]),
                "medium": len([f for f in res["findings"] if f["level"] == "medium"]),
                "low": len([f for f in res["findings"] if f["level"] == "low"]),
            },
        })
        payload["total_findings"] += len(res["findings"])
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload["total_findings"]


# ---------------------------------------------------------------------------
# 自检（离线）
# ---------------------------------------------------------------------------
def _selftest_document():
    long_para = "本段用于触发段落长度检查，重复若干次以超过默认阈值。" * 12
    lines = [
        "# 标题",
        "",
        "在当今快速发展的时代，随着科技的不断进步，值得注意的是，该方法取得了进展。",
        "综上所述，我们完成了验证。",
        "",
        "值得注意的是，第一点。",
        "值得注意的是，第二点。",
        "值得注意的是，第三点。",
        "",
        "我们的结果表明,该方法有效, 结论稳定. 后续（未闭合",
        "",
        "提升幅度为 5%，另一处写成 5％，样本量 10cm。",
        "",
        "他提到\u201c这一方法可以提升效果。",
        "",
        long_para,
        "",
        "| 表格 | 一行 |",
        "",
    ]
    return "\n".join(lines)


def _clean_document():
    return (
        "# 标题\n"
        "\n"
        "我们提出了一种基于 X 的方法，在数据集 Y 上取得了 5% 的提升（p < 0.05）。\n"
        "\n"
        "实验在两台服务器上完成，耗时 30 min。\n"
    )


def _run_selftest():
    failures = []
    checked = 0

    doc = _selftest_document()
    findings = analyze_text(doc)
    by_rule = {}
    for f in findings:
        by_rule.setdefault(f["rule"], []).append(f)

    expected = ["A1", "A2", "A3", "A4", "A5", "A6"]
    for rule in expected:
        checked += 1
        if rule not in by_rule:
            failures.append("规则 {0} 未被检出".format(rule))

    checked += 1
    if not any(f["rule"] == "A2" and f["level"] == "high" for f in findings):
        failures.append("A2 高频连接词未升级为 high")

    checked += 1
    if not any(f["rule"] == "A1" and f["level"] == "high" for f in findings):
        failures.append("A1 同句堆砌未升级为 high")

    checked += 1
    for f in findings:
        if f["rule"].startswith("B"):
            failures.append("B 段条目不应出现在 A 段问题里: {0}".format(f))
            break

    checked += 1
    if len(MANUAL_CHECKLIST) != 5:
        failures.append("B 段清单条目数应为 5，实际 {0}".format(len(MANUAL_CHECKLIST)))

    checked += 1
    clean = analyze_text(_clean_document())
    if clean:
        failures.append("干净文档被误报: {0}".format([f["rule"] for f in clean]))

    checked += 1
    long_doc = "一" * (DEFAULT_MAX_PARA_CHARS + 50)
    if not any(f["rule"] == "A6" for f in analyze_text(long_doc)):
        failures.append("A6 超长段落未被检出")

    checked += 1
    if any(f["rule"] == "A6" for f in analyze_text("一" * 10)):
        failures.append("A6 短段落被误报")

    if failures:
        print("selftest 失败：{0} 项断言未通过".format(len(failures)))
        for f in failures:
            print("  - {0}".format(f))
        return 2
    print("selftest 通过：{0} 项断言全部成立（A1-A6 覆盖、B 段不计数、干净文档零误报）。".format(checked))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _load_text(path):
    with open(path, "rb") as fh:
        data = fh.read()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="lint_redflags.py",
        description="写作雷区扫描器：A 段机检并计数，B 段只输出人工复核清单。",
    )
    parser.add_argument("--file", action="append", default=[], help="待检查的 Markdown / 文本文件，可重复")
    parser.add_argument("--json", action="store_true", dest="as_json", help="以 JSON 输出")
    parser.add_argument("--selftest", action="store_true", help="运行内置离线自检")
    parser.add_argument("--max-para-chars", type=int, default=DEFAULT_MAX_PARA_CHARS,
                        help="段落长度阈值（字符），默认 {0}".format(DEFAULT_MAX_PARA_CHARS))
    args = parser.parse_args(argv)

    if args.selftest:
        return _run_selftest()

    if not args.file:
        sys.stderr.write("用法错误：至少需要 --file\n")
        parser.print_usage(sys.stderr)
        return 2
    if args.max_para_chars <= 0:
        sys.stderr.write("用法错误：--max-para-chars 必须为正整数\n")
        return 2

    results = []
    for path in args.file:
        if not os.path.isfile(path):
            sys.stderr.write("用法错误：文件不存在: {0}\n".format(path))
            return 2
        try:
            text = _load_text(path)
        except OSError as exc:
            sys.stderr.write("运行故障：无法读取 {0}: {1}\n".format(path, exc))
            return 2
        results.append({"path": path, "findings": analyze_text(text, args.max_para_chars)})

    if args.as_json:
        total = _print_json(results, args.max_para_chars)
    else:
        total = _print_human(results, args.max_para_chars)
    return 1 if total else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
