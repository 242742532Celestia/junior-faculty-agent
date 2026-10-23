#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引用指代一致性审计：正文引用标记与文末文献表的对账。

三类检查：
  1. 编号对账：悬空引用 / 幽灵条目 / 编号错位
  2. 作者指代一致性：正文作者-年份 vs 文献表第一作者姓氏
  3. 编号风格混用：数字编号制与作者-年份制混用

只报矛盾，不报缺失。文献表缺条 -> 报「文献表缺失」；数据库查不到不归咎作者。

仅使用 Python 标准库。Python 3.9 兼容。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

# 正文中的数字引用标记：[1] [1,2] [1-3] [1,2-4] [1-3,5]
NUM_CITE_RE = re.compile(r"\[\s*(\d+(?:\s*(?:,|-|–|—)\s*\d+)*)\s*\]")
# 正文中的作者-年份引用：(Smith, 2020) （Wang 2021） [Zhang et al. (2021)]
AUTH_YEAR_RE = re.compile(
    r"[\(（]([A-Z][A-Za-z\u4e00-\u9fff'\-]+"
    r"(?:\s+(?:et\s+al\.?|等))?)"
    r"\s*[,，]?\s*(\d{4})[a-z]?\s*[\)）]"
)
# 无括号形式：Zhang et al. (2021)
AUTH_YEAR_BRACKET_RE = re.compile(
    r"([A-Z][A-Za-z\u4e00-\u9fff'\-]+(?:\s+(?:et\s+al\.?|等))?)\s*\(\s*(\d{4})[a-z]?\s*\)"
)
# 全角括号
NUM_CITE_FULL_RE = re.compile(r"[\uFF08]\s*(\d+(?:\s*(?:,|-|–|—)\s*\d+)*)\s*[\uFF09]")

# 文献表条目：行首编号，或 "- " 列表
BIB_NUMBERED_RE = re.compile(r"^\s*(?:\[(\d{1,3})\]|(\d{1,3})[\.\)])\s+(.*)$")
BIB_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*)$")
# 文献表里的年份与第一作者
BIB_SURNAME_RE = re.compile(r"^\s*([A-Z][A-Za-z\u4e00-\u9fff'\-]+)")
BIB_YEAR_RE = re.compile(r"(?<!\d)((?:1[89]|20)\d{2})(?!\d)")

SEV_HIGH = "高"
SEV_MID = "中"
SEV_LOW = "低"

KIND_DANGLING = "悬空引用"
KIND_GHOST = "幽灵条目"
KIND_MISALIGN = "编号错位"
KIND_AUTHOR = "作者指代不一致"
KIND_STYLE = "编号风格混用"
KIND_BIB_MISSING = "文献表缺失"


def read_text_file(path):
    if path.lower().endswith(".docx"):
        return read_docx_text(path)
    with open(path, "r", encoding="utf-8-sig") as fh:
        return fh.read()


def read_docx_text(path):
    """用标准库 zipfile + xml.etree 提取 docx 纯文本，保留段落边界。"""
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for para in root.iter(ns + "p"):
        buf = []
        for node in para.iter(ns + "t"):
            buf.append(node.text or "")
        text = "".join(buf).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def split_bibliography(lines):
    """切分正文与文末文献表。

    返回 (body_lines, bib_lines, bib_start_index)。
    """
    marker = None
    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s:
            continue
        if re.match(r"^#{1,6}\s*(参考文献|参考资料|文献|References|Bibliography)", s, re.IGNORECASE):
            marker = i
            break
        if re.match(r"^#{1,6}\s*(致谢|附录|Acknowledg)", s, re.IGNORECASE):
            marker = i
            break
    if marker is None:
        return list(lines), [], None

    body = list(lines[:marker])
    bib = []
    for raw in lines[marker + 1:]:
        s = raw.strip()
        if not s:
            continue
        if re.match(r"^#{1,6}\s+", s):
            # 文献表后面又出现新章节 -> 截断
            break
        bib.append(raw)
    return body, bib, marker


def parse_bib_entries(bib_lines):
    """解析文献表条目，返回 [{number, text, surname, year, line_no}]。

    number 为条目自身的标号（若有）；若无标号则按出现顺序隐式编号。
    """
    entries = []
    for offset, raw in enumerate(bib_lines):
        s = raw.rstrip()
        stripped = s.strip()
        if not stripped:
            continue
        num = None
        body = stripped
        m = BIB_NUMBERED_RE.match(stripped)
        if m:
            num = int(m.group(1) or m.group(2))
            body = m.group(3).strip()
        else:
            m = BIB_BULLET_RE.match(stripped)
            if m:
                body = m.group(1).strip()
            else:
                # Markdown 表格行
                if stripped.startswith("|") and stripped.endswith("|"):
                    cells = [c.strip() for c in stripped.strip("|").split("|")]
                    if len(cells) >= 2:
                        num = None
                        body = cells[-1] if cells else stripped
                    else:
                        continue
                else:
                    if not re.search(r"[A-Za-z\u4e00-\u9fff]{4}", stripped):
                        continue
                    body = stripped
        surname = None
        sm = BIB_SURNAME_RE.match(body)
        if sm:
            surname = sm.group(1)
        else:
            sm2 = re.search(r"([A-Z][A-Za-z\u4e00-\u9fff'\-]+)\s*(?:,|，)", body)
            if sm2:
                surname = sm2.group(1)
        year = None
        ym = BIB_YEAR_RE.search(body)
        if ym:
            year = int(ym.group(1))
        entries.append({
            "number": num,
            "index": len(entries) + 1,
            "text": body,
            "surname": surname,
            "year": year,
            "line_no": offset,
        })
    return entries


def expand_citation_group(spec):
    """把 '1-3,5' 展开成 [1,2,3,5]。"""
    out = []
    for chunk in re.split(r"[,，]", spec):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.match(r"^(\d+)\s*[-–—]\s*(\d+)$", chunk)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b:
                out.extend(range(a, b + 1))
            else:
                out.extend(range(a, b - 1, -1))
            continue
        m = re.match(r"^(\d+)$", chunk)
        if m:
            out.append(int(m.group(1)))
    return out


def collect_body_citations(body_lines):
    """扫描正文引用标记。返回 (citations, author_cites)。

    citations: [{numbers:[...], raw, line_no}]
    author_cites: [{surname, year, raw, line_no}]
    """
    citations = []
    author_cites = []
    for i, raw in enumerate(body_lines):
        line = raw
        for m in NUM_CITE_RE.finditer(line):
            nums = expand_citation_group(m.group(1))
            if nums:
                citations.append({"numbers": nums, "raw": m.group(0), "line_no": i + 1})
        for m in NUM_CITE_FULL_RE.finditer(line):
            nums = expand_citation_group(m.group(1))
            if nums:
                citations.append({"numbers": nums, "raw": m.group(0), "line_no": i + 1})
        for rx in (AUTH_YEAR_RE, AUTH_YEAR_BRACKET_RE):
            for m in rx.finditer(line):
                surname = m.group(1).strip()
                surname = re.sub(r"\s+(?:et\s+al\.?|等)$", "", surname)
                year = int(m.group(2))
                author_cites.append({
                    "surname": surname,
                    "year": year,
                    "raw": m.group(0),
                    "line_no": i + 1,
                })
    return citations, author_cites


def normalize_surname(name):
    if not name:
        return ""
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", name.lower())


def audit(text):
    """执行三类检查，返回 findings 列表 + 统计。"""
    lines = text.splitlines()
    body_lines, bib_lines, bib_start = split_bibliography(lines)
    body_text = "\n".join(body_lines)

    findings = []
    citations, author_cites = collect_body_citations(body_lines)
    entries = parse_bib_entries(bib_lines)

    # ---- 检查 3：编号风格混用（先做，因为影响后续解读）----
    has_numeric_style = bool(citations)
    has_author_style = bool(author_cites)
    if has_numeric_style and has_author_style:
        # 排除：作者-年份引用其实出现在方括号里当数字引用的一部分
        findings.append({
            "kind": KIND_STYLE,
            "severity": SEV_MID,
            "location": "全文",
            "detail": "同时存在数字编号制引用（%d 处）与作者-年份制引用（%d 处），请统一为一种风格"
                      % (len(citations), len(author_cites)),
            "fix": "全稿统一为数字编号制或作者-年份制之一",
        })

    if not entries:
        # 只报矛盾不报缺失：正文有引用但文献表整体缺失 -> 报「文献表缺失」
        if citations or author_cites:
            findings.append({
                "kind": KIND_BIB_MISSING,
                "severity": SEV_HIGH,
                "location": "全文",
                "detail": "正文存在 %d 处引用标记，但未找到可解析的文献表条目"
                          % (len(citations) + len(author_cites)),
                "fix": "补充文献表，或确认文献表标题是否可被本脚本识别",
            })
        return findings, {
            "citations": len(citations),
            "author_cites": len(author_cites),
            "bib_entries": 0,
            "bib_start_line": bib_start,
        }

    # 建立编号 -> 条目 的索引；无显式标号时按位置隐式编号
    has_labels = any(e["number"] is not None for e in entries)
    by_number = {}
    for e in entries:
        key = e["number"] if e["number"] is not None else e["index"]
        by_number.setdefault(key, e)
    # 标号是否构成 1..N 的连续序列。只有连续时「位置」与「标号」才可互相校验，
    # 否则（如章节续编 [15][16][17]）无法据此判断错位。
    labels = sorted(e["number"] for e in entries if e["number"] is not None)
    contiguous_from_one = labels == list(range(1, len(labels) + 1))

    # 建立姓氏+年份 -> 条目 索引
    by_author_year = {}
    for e in entries:
        if e["surname"] and e["year"]:
            by_author_year.setdefault(
                (normalize_surname(e["surname"]), e["year"]), e
            )

    # ---- 检查 1：编号对账 ----
    # 1a) 文献表层面的标号-顺序错位
    if has_labels and contiguous_from_one:
        displaced = [e for e in entries if e["number"] is not None and e["number"] != e["index"]]
        if displaced:
            desc = "；".join(
                "第 %d 个条目的标号为 [%d]" % (e["index"], e["number"]) for e in displaced
            )
            findings.append({
                "kind": KIND_MISALIGN,
                "severity": SEV_HIGH,
                "location": "文献表",
                "detail": "文献表标号与条目顺序不符：%s" % desc,
                "fix": "按正文首次引用顺序重排文献表，或修正条目标号",
            })

    cited_numbers = set()
    for c in citations:
        for n in c["numbers"]:
            cited_numbers.add(n)
            if n in by_number:
                e = by_number[n]
                if contiguous_from_one and e["index"] != n:
                    findings.append({
                        "kind": KIND_MISALIGN,
                        "severity": SEV_HIGH,
                        "location": "正文第 %d 行" % c["line_no"],
                        "detail": "正文标注 [%d]，该标号在文献表中位于第 %d 个条目；"
                                  "按顺序应为第 %d 条（%s）"
                                  % (n, e["index"], n, e["text"][:50]),
                        "fix": "核对编号来源：正文 [N] 解析到的条目与顺序位置不一致",
                    })
                continue
            findings.append({
                "kind": KIND_DANGLING,
                "severity": SEV_HIGH,
                "location": "正文第 %d 行" % c["line_no"],
                "detail": "正文标注 [%d]，但文献表中没有可对应的编号条目" % n,
                "fix": "补入该条参考文献，或删除正文引用标记",
            })

    # 幽灵条目：文献表有、正文从未引
    author_keys = set(
        (normalize_surname(a["surname"]), a["year"]) for a in author_cites
    )
    for e in entries:
        key = e["number"] if e["number"] is not None else e["index"]
        if key in cited_numbers:
            continue
        if e["surname"] and e["year"]:
            ek = (normalize_surname(e["surname"]), e["year"])
            if ek in author_keys:
                continue
        if has_numeric_style:
            detail = "文献表条目「%s」在正文中从未被引用" % e["text"][:60]
            severity = SEV_MID
            fix = "在正文相应位置补引，或从文献表删除该条"
        else:
            detail = ("文献表条目「%s」按作者姓氏+年份未匹配到正文引用"
                      % e["text"][:60])
            severity = SEV_LOW
            fix = "确认该条是否确实被引用；作者-年份匹配可能因写法差异漏配"
        findings.append({
            "kind": KIND_GHOST,
            "severity": severity,
            "location": "文献表第 %d 条" % e["index"],
            "detail": detail,
            "fix": fix,
        })

    # ---- 检查 2：作者指代一致性 ----
    for a in author_cites:
        key = (normalize_surname(a["surname"]), a["year"])
        if key in by_author_year:
            continue
        # 同姓氏不同年份 -> 找同年其他作者
        same_year = [e for e in entries if e["year"] == a["year"]]
        same_surname_other_year = [
            e for e in entries
            if e["surname"] and normalize_surname(e["surname"]) == normalize_surname(a["surname"])
            and e["year"] and e["year"] != a["year"]
        ]
        if same_surname_other_year:
            e = same_surname_other_year[0]
            findings.append({
                "kind": KIND_AUTHOR,
                "severity": SEV_HIGH,
                "location": "正文第 %d 行" % a["line_no"],
                "detail": "正文写作 %s (%d)，但文献表中 %s 的条目年份为 %s"
                          % (a["surname"], a["year"], e["surname"], e["year"]),
                "fix": "核对年份，或修正文献表条目年份",
            })
        elif same_year:
            surnames = ", ".join(
                (e["surname"] or "?") for e in same_year if e["surname"]
            )
            findings.append({
                "kind": KIND_AUTHOR,
                "severity": SEV_MID,
                "location": "正文第 %d 行" % a["line_no"],
                "detail": "正文写作 %s (%d)，文献表 %d 年条目第一作者为：%s"
                          % (a["surname"], a["year"], a["year"], surnames),
                "fix": "确认正文作者-年份与文献表条目是否对应",
            })
        else:
            findings.append({
                "kind": KIND_BIB_MISSING,
                "severity": SEV_LOW,
                "location": "正文第 %d 行" % a["line_no"],
                "detail": "正文写作 %s (%d)，文献表中未找到同年条目（不代表该文献不存在）"
                          % (a["surname"], a["year"]),
                "fix": "人工确认文献表是否应补入该条",
            })

    return findings, {
        "citations": len(citations),
        "author_cites": len(author_cites),
        "bib_entries": len(entries),
        "bib_start_line": bib_start,
        "cited_numbers": sorted(cited_numbers),
    }


def render_text(findings, stats, path):
    lines = []
    lines.append("=" * 68)
    lines.append("引用指代一致性审计报告")
    lines.append("文件：%s" % path)
    lines.append("=" * 68)
    lines.append(
        "统计：正文数字引用 %d 处，作者-年份引用 %d 处，文献表条目 %d 条"
        % (stats.get("citations", 0), stats.get("author_cites", 0), stats.get("bib_entries", 0))
    )
    lines.append("")
    if not findings:
        lines.append("未发现指代矛盾。")
    else:
        order = {SEV_HIGH: 0, SEV_MID: 1, SEV_LOW: 2}
        findings = sorted(findings, key=lambda f: (order.get(f["severity"], 3), f["kind"]))
        for i, f in enumerate(findings, 1):
            lines.append("[%d] [%s] %s（严重度：%s）" % (i, f["kind"], f["location"], f["severity"]))
            lines.append("    %s" % f["detail"])
            lines.append("    建议：%s" % f["fix"])
            lines.append("")
    lines.append("-" * 68)
    lines.append("说明：本脚本只报告文档内部的矛盾，不判定文献真伪，不判定数据库是否收录。")
    lines.append("=" * 68)
    return "\n".join(lines)


def has_problem(findings):
    return bool(findings)


# --------------------------------------------------------------------------
# 自检（完全离线）
# --------------------------------------------------------------------------
def selftest():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print("  [PASS] %s" % name)
        else:
            print("  [FAIL] %s %s" % (name, detail))
            failures.append(name)

    print("audit_citation_index.py 自检（离线）")

    # 展开编号组
    check("展开 [1]", expand_citation_group("1") == [1])
    check("展开 [1,2]", expand_citation_group("1,2") == [1, 2])
    check("展开 [1-3]", expand_citation_group("1-3") == [1, 2, 3])
    check("展开 [1-3,5]", expand_citation_group("1-3,5") == [1, 2, 3, 5])

    # 正文/文献表切分
    doc = (
        "引言\n"
        "已有研究表明 [1] 该结论成立。\n"
        "另有研究（Smith, 2020）提出相反意见 [1,2]。\n"
        "范围扩展 [1-3]。\n"
        "\n"
        "## 参考文献\n"
        "[1] Zhang, W. (2021). Title A. Journal A.\n"
        "[2] Smith, J. (2020). Title B. Journal B.\n"
        "[3] Li, Y. (2019). Title C. Journal C.\n"
    )
    body, bib, marker = split_bibliography(doc.splitlines())
    check("切出文献表段", marker is not None and len(bib) == 3,
          "marker=%r bib=%d" % (marker, len(bib)))

    findings, stats = audit(doc)
    kinds = set(f["kind"] for f in findings)
    check("编号风格混用被报出", KIND_STYLE in kinds, "kinds=%s" % kinds)
    check("正文引用数统计正确", stats["citations"] == 3, "got=%d" % stats["citations"])
    check("作者-年份引用数统计正确", stats["author_cites"] == 1, "got=%d" % stats["author_cites"])
    check("无悬空引用", KIND_DANGLING not in kinds, "kinds=%s" % kinds)
    check("无幽灵条目", KIND_GHOST not in kinds, "kinds=%s" % kinds)
    check("作者指代一致时不报", KIND_AUTHOR not in kinds, "kinds=%s" % kinds)

    # 悬空引用：正文 [9]，文献表只有 1-3
    doc_dangling = doc.replace("[1-3]", "[9]")
    f2, _s2 = audit(doc_dangling)
    kinds2 = set(f["kind"] for f in f2)
    check("悬空引用被报出", KIND_DANGLING in kinds2 or KIND_MISALIGN in kinds2, "kinds=%s" % kinds2)

    # 幽灵条目：文献表第 3 条正文未引
    doc_ghost = doc.replace("[1-3]", "[1,2]")
    f3, _s3 = audit(doc_ghost)
    ghosts = [f for f in f3 if f["kind"] == KIND_GHOST]
    check("幽灵条目被报出", len(ghosts) == 1, "n=%d" % len(ghosts))

    # 编号错位：文献表标号乱序 [1] [3] [2]，正文标注 [2]
    doc_mis = (
        "正文提到 [2]。\n\n"
        "## 参考文献\n"
        "[1] Zhang, W. (2021). Title A. Journal A.\n"
        "[3] Smith, J. (2020). Title B. Journal B.\n"
        "[2] Li, Y. (2019). Title C. Journal C.\n"
    )
    f4, _s4 = audit(doc_mis)
    kinds4 = set(f["kind"] for f in f4)
    check("编号错位被报出", KIND_MISALIGN in kinds4, "kinds=%s" % kinds4)
    mis = [f for f in f4 if f["kind"] == KIND_MISALIGN]
    check("编号错位定位到正文行号或文献表",
          any("正文第" in f["location"] or f["location"] == "文献表" for f in mis),
          "n=%d" % len(mis))

    # 标号连续且顺序正确时不得误报编号错位
    doc_ok = (
        "正文提到 [2]。\n\n"
        "## 参考文献\n"
        "[1] Zhang, W. (2021). Title A. Journal A.\n"
        "[2] Smith, J. (2020). Title B. Journal B.\n"
    )
    f_ok, _s_ok = audit(doc_ok)
    check("标号连续时无误报编号错位",
          KIND_MISALIGN not in set(f["kind"] for f in f_ok),
          "kinds=%s" % set(f["kind"] for f in f_ok))

    # 章节续编标号（非 1..N 连续）时不得误报编号错位
    doc_cont = (
        "正文提到 [16]。\n\n"
        "## 参考文献\n"
        "[15] Zhang, W. (2021). Title A. Journal A.\n"
        "[16] Smith, J. (2020). Title B. Journal B.\n"
    )
    f_cont, _s_cont = audit(doc_cont)
    check("非 1..N 连续标号时无误报编号错位",
          KIND_MISALIGN not in set(f["kind"] for f in f_cont),
          "kinds=%s" % set(f["kind"] for f in f_cont))

    # 作者不符：正文 (Smith, 2020)，文献表该年第一作者是 Zhang
    doc_auth = (
        "正文写作 (Smith, 2020)。\n\n"
        "## 参考文献\n"
        "[1] Zhang, W. (2020). Title A. Journal A.\n"
    )
    f5, _s5 = audit(doc_auth)
    kinds5 = set(f["kind"] for f in f5)
    check("作者指代不一致被报出", KIND_AUTHOR in kinds5, "kinds=%s" % kinds5)

    # 文献表整体缺失 -> 报「文献表缺失」，不报悬空/幽灵
    doc_nobib = "正文写作 [1] 与 (Smith, 2020)。\n"
    f6, s6 = audit(doc_nobib)
    kinds6 = set(f["kind"] for f in f6)
    check("文献表缺失被报出", KIND_BIB_MISSING in kinds6, "kinds=%s" % kinds6)
    check("文献表缺失时不误报悬空/幽灵",
          KIND_DANGLING not in kinds6 and KIND_GHOST not in kinds6, "kinds=%s" % kinds6)

    # 渲染
    text = render_text(f6, s6, "<selftest>")
    check("报告含说明行", "只报告文档内部的矛盾" in text)

    if failures:
        print("自检失败：%d 项未通过 -> %s" % (len(failures), ", ".join(failures)))
        return 2
    print("自检全部通过。")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(description="引用指代一致性审计（编号对账 / 作者指代 / 风格混用）")
    parser.add_argument("--file", help="待审计文件（.md / .txt / .docx）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--selftest", action="store_true", help="运行离线自检")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if not args.file:
        parser.print_usage()
        sys.stderr.write("用法错误：需要 --file。\n")
        return 2

    try:
        text = read_text_file(args.file)
    except Exception as exc:
        sys.stderr.write("读取失败：%s\n" % (exc,))
        return 2

    findings, stats = audit(text)
    stats = dict(stats)
    stats["file"] = args.file

    if args.json:
        payload = {"file": args.file, "stats": stats, "findings": findings}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(render_text(findings, stats, args.file) + "\n")

    if has_problem(findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
