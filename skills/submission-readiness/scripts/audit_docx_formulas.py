#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_docx_formulas.py — DOCX 公式完整性审计。

核心技术点：DOCX 里的公式是 OMML（Office Math Markup Language，`m:oMath` 标签），
在 `paragraph.text` / 纯文本里**完全不可见**。本脚本用 zipfile 解压 .docx，读取
`word/document.xml`，用命名空间感知的 XML 解析统计公式节点。

用法::

    python audit_docx_formulas.py --docx paper/main.docx
    python audit_docx_formulas.py --docx paper/main.docx --strict
    python audit_docx_formulas.py --docx paper/main.docx --json
    python audit_docx_formulas.py --selftest

退出码::

    0 = 未发现错误（且未使用 --strict，或严格模式下无警告）
    1 = 发现错误；或 --strict 模式下存在警告
    2 = 用法错误或运行故障（含 selftest 未通过）

设计约束::

    * 仅使用标准库（zipfile / xml.etree），不依赖 python-docx / lxml
    * Python 3.9 兼容（f-string 表达式内不出现反斜杠）
"""

import argparse
import io
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_P = "{%s}p" % W_NS
W_T = "{%s}t" % W_NS
M_OMATH = "{%s}oMath" % M_NS
M_OMATHPARA = "{%s}oMathPara" % M_NS
M_T = "{%s}t" % M_NS

# 正文里对公式编号的引用：式(1) / 式（2）/ 公式(3) / Eq. (4)
REF_RE = re.compile(
    r"(?<![方公字系等同模定实方公])式\s*[（(]?\s*(\d{1,3})\s*[）)]?"
    r"|公式\s*[（(]?\s*(\d{1,3})\s*[）)]?"
    r"|(?:Eq\.?|equation)\s*[（(]?\s*(\d{1,3})\s*[）)]?",
    re.IGNORECASE)
# 已定义公式编号的候选：带公式的段落中出现的括号数字
PAREN_NUM_RE = re.compile(r"[（(]\s*(\d{1,3})\s*[）)]")

# 占位符公式标记
PLACEHOLDER_EXACT = {
    "xxx", "xx", "xxx...", "todo", "tbd", "fixme", "待补", "待填", "待定",
    "公式", "占位", "占位符", "?", "??", "???", "-", "--", "…", "……",
}
PLACEHOLDER_SUBSTR = ["todo", "tbd", "fixme", "待补", "待填", "占位", "公式"]


def normalize(text):
    return re.sub(r"\s+", "", text or "").lower()


def is_placeholder(formula_text):
    norm = normalize(formula_text)
    if not norm:
        return False
    if norm in PLACEHOLDER_EXACT:
        return True
    if re.fullmatch(r"x{3,}", norm):
        return True
    if re.fullmatch(r"[a-z]?\?", norm):
        return True
    if re.fullmatch(r"公式\d*", norm):
        return True
    for marker in PLACEHOLDER_SUBSTR:
        if marker in norm:
            return True
    return False


def count_plain_text_formulas(text):
    """统计纯文本（不含 OMML）里可识别的公式痕迹。"""
    if not text:
        return 0
    count = 0
    count += len(re.findall(r"\$[^$\n]{1,200}\$", text))
    count += len(re.findall(r"\\\[[^\]\n]{1,400}\\\]", text))
    count += len(re.findall(r"\\\([^\)\n]{1,400}\\\)", text))
    count += len(re.findall(
        r"(?m)(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_^{}\\]{0,20}\s*=\s*[^=\n]{1,80}",
        text))
    return count


def parse_docx(docx_path):
    """返回 (paragraphs, formulas)。"""
    with zipfile.ZipFile(docx_path) as zf:
        try:
            xml_bytes = zf.read("word/document.xml")
        except KeyError:
            raise ValueError("docx 内缺少 word/document.xml，无法审计公式")
    root = ET.fromstring(xml_bytes)
    paragraphs = []
    formulas = []

    def walk(node, para_index):
        for child in list(node):
            if child.tag == W_P:
                text = "".join(t.text or "" for t in child.iter(W_T))
                paragraphs.append({"index": len(paragraphs) + 1,
                                  "text": text,
                                  "formula_count": 0})
                walk(child, len(paragraphs))
            elif child.tag == M_OMATH:
                ftext = "".join(t.text or "" for t in child.iter(M_T))
                formulas.append({"index": len(formulas) + 1,
                                 "paragraph": para_index,
                                 "text": ftext,
                                 "empty": ftext.strip() == ""})
                paragraphs[para_index - 1]["formula_count"] += 1 if para_index else 0
            elif child.tag == M_OMATHPARA:
                walk(child, para_index)
            else:
                walk(child, para_index)

    walk(root, 0)
    return paragraphs, formulas


def audit(docx_path, strict=False):
    paragraphs, formulas = parse_docx(docx_path)
    errors = []
    warnings = []
    full_text = "\n".join(p["text"] for p in paragraphs)

    empty_formulas = []
    placeholder_formulas = []
    for f in formulas:
        if f["empty"]:
            empty_formulas.append(f)
        elif is_placeholder(f["text"]):
            placeholder_formulas.append(f)

    # 1) 公式总数
    formula_count = len(formulas)

    # 2) 空公式
    for f in empty_formulas:
        item = {
            "kind": "空公式",
            "severity": "error" if strict else "warning",
            "formula_index": f["index"],
            "locator": "第{0}段".format(f["paragraph"]) if f["paragraph"] else "（不在段落内）",
            "quote": "<m:oMath> 内无任何有效数学内容",
            "criterion": "公式节点存在，但 m:t 文本为空（无可渲染内容）",
            "human_check": "该公式是漏写、粘贴丢失，还是本就不该存在？"
                           "如需删除请连同正文引用一起处理。",
        }
        (errors if strict else warnings).append(item)

    # 3) 疑似占位符公式
    for f in placeholder_formulas:
        item = {
            "kind": "疑似占位符公式",
            "severity": "error",
            "formula_index": f["index"],
            "locator": "第{0}段".format(f["paragraph"]) if f["paragraph"] else "（不在段落内）",
            "quote": f["text"],
            "criterion": "公式内容命中占位标记（xxx / TODO / 公式 / 待补 / 单字母+问号 等）",
            "human_check": "该占位是否已被正文引用？替换前需确认替换后的公式语义。",
        }
        errors.append(item)

    # 4) 公式编号缺失：正文引用了式(N)，但数不到对应编号
    defined_numbers = set()
    for p in paragraphs:
        if p["formula_count"] > 0:
            for m in PAREN_NUM_RE.finditer(p["text"]):
                defined_numbers.add(int(m.group(1)))
    referenced = []
    for p in paragraphs:
        for m in REF_RE.finditer(p["text"]):
            num = None
            for g in m.groups():
                if g:
                    num = int(g)
                    break
            if num is not None:
                referenced.append((num, p["index"], m.group(0)))
    missing_refs = []
    for num, pidx, matched in referenced:
        if num not in defined_numbers:
            item = {
                "kind": "公式编号引用缺失",
                "severity": "warning",
                "formula_index": None,
                "locator": "第{0}段".format(pidx),
                "quote": matched,
                "criterion": "正文引用了编号 {0}，但未在含公式的段落中检出该编号".format(num),
                "human_check": "该编号对应的公式是否存在于表格、图片或另一文件？"
                               "确认后再决定补公式还是改引用。",
            }
            warnings.append(item)
            missing_refs.append(item)

    # 5) 硬护栏：正文纯文本里数不到公式，但 XML 里有公式
    plain_count = count_plain_text_formulas(full_text)
    guardrail = None
    if formula_count > 0 and plain_count == 0:
        guardrail = {
            "kind": "纯文本改稿丢公式风险",
            "severity": "warning",
            "formula_index": None,
            "locator": "全文",
            "quote": "XML 公式数={0}，纯文本公式数=0".format(formula_count),
            "criterion": "公式全部以 OMML 形式存在，纯文本（如 paragraph.text、"
                         "逐段读取、复制粘贴到纯文本编辑器）中不可见",
            "human_check": "后续任何“按纯文本改稿 / 逐段重写”的操作都会丢掉这 {0} 个公式；"
                           "请在 Word 中改，或先做 OMML 保真转换。".format(formula_count),
        }
        warnings.append(guardrail)

    if strict:
        # 严格模式下，警告也计入失败
        for w in warnings:
            if w["severity"] == "warning":
                w["severity"] = "error"

    return {
        "file": docx_path,
        "formula_count": formula_count,
        "empty_formula_count": len(empty_formulas),
        "placeholder_formula_count": len(placeholder_formulas),
        "plain_text_formula_count": plain_count,
        "defined_equation_numbers": sorted(defined_numbers),
        "referenced_equation_numbers": sorted(set(n for n, _p, _m in referenced)),
        "missing_number_refs": missing_refs,
        "guardrail_triggered": guardrail is not None,
        "strict": strict,
        "errors": errors,
        "warnings": warnings,
        "paragraph_count": len(paragraphs),
    }


def format_report(result):
    lines = []
    lines.append("=== DOCX 公式完整性审计 ===")
    lines.append("文件：{0}".format(result["file"]))
    lines.append("段落数：{0}".format(result["paragraph_count"]))
    lines.append("公式总数（XML 中 m:oMath 节点）：{0}".format(result["formula_count"]))
    lines.append("空公式：{0}    疑似占位符公式：{1}".format(
        result["empty_formula_count"], result["placeholder_formula_count"]))
    lines.append("纯文本可识别的公式数：{0}".format(result["plain_text_formula_count"]))
    lines.append("已定义的公式编号：{0}".format(
        result["defined_equation_numbers"] or "无"))
    lines.append("正文引用的公式编号：{0}".format(
        result["referenced_equation_numbers"] or "无"))
    lines.append("严格模式（--strict）：{0}".format("开" if result["strict"] else "关"))

    lines.append("")
    lines.append("--- 错误（{0} 条）---".format(len(result["errors"])))
    if not result["errors"]:
        lines.append("  （无）")
    for i, item in enumerate(result["errors"], 1):
        lines.append("  [{0}] {1} · {2}".format(i, item["kind"], item["severity"]))
        lines.append("      位置：{0}".format(item["locator"]))
        if item.get("formula_index"):
            lines.append("      公式序号：{0}".format(item["formula_index"]))
        lines.append("      候选：{0}".format(item["quote"]))
        lines.append("      判据：{0}".format(item["criterion"]))
        lines.append("      需要人工判断：{0}".format(item["human_check"]))

    lines.append("")
    lines.append("--- 警告（{0} 条）---".format(len(result["warnings"])))
    if not result["warnings"]:
        lines.append("  （无）")
    for i, item in enumerate(result["warnings"], 1):
        lines.append("  [{0}] {1} · {2}".format(i, item["kind"], item["severity"]))
        lines.append("      位置：{0}".format(item["locator"]))
        if item.get("formula_index"):
            lines.append("      公式序号：{0}".format(item["formula_index"]))
        lines.append("      候选：{0}".format(item["quote"]))
        lines.append("      判据：{0}".format(item["criterion"]))
        lines.append("      需要人工判断：{0}".format(item["human_check"]))

    lines.append("")
    if result["guardrail_triggered"]:
        lines.append("⚠ 硬护栏：本文档公式只存在于 OMML，纯文本不可见。"
                     "任何按纯文本改稿的操作都会丢失公式。")
    else:
        lines.append("护栏：未触发（未发现“纯文本无公式但 XML 有公式”的情况）。")
    return "\n".join(lines)


def build_minimal_docx(formula_variants):
    """在内存中构造最小 docx。formula_variants: [(kind, text)]"""
    parts = []
    parts.append(
        '<w:p><w:r><w:t>如式(1)所示，模型给出预测结果。</w:t></w:r></w:p>')
    parts.append(
        '<w:p><m:oMath><m:r><m:t>E=mc^2</m:t></m:r></m:oMath>'
        '<w:r><w:t>(1)</w:t></w:r></w:p>')
    for kind, text in formula_variants:
        if kind == "empty":
            parts.append('<w:p><m:oMath><m:r><m:t> </m:t></m:r></m:oMath></w:p>')
        elif kind == "placeholder":
            parts.append(
                '<w:p><m:oMath><m:r><m:t>{0}</m:t></m:r></m:oMath></w:p>'.format(text))
        else:
            parts.append(
                '<w:p><m:oMath><m:r><m:t>{0}</m:t></m:r></m:oMath></w:p>'.format(text))
    parts.append('<w:p><w:r><w:t>进一步地，由式(2)可得结论。</w:t></w:r></w:p>')
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        '<w:body>' + "".join(parts) + '</w:body></w:document>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("word/document.xml", doc_xml)
    return buf.getvalue()


def selftest():
    checks = []

    def ck(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    tmp_dir = os.path.dirname(os.path.abspath(__file__))
    tmp_a = os.path.join(tmp_dir, "_selftest_formulas_a.docx")
    tmp_b = os.path.join(tmp_dir, "_selftest_formulas_b.docx")
    try:
        with open(tmp_a, "wb") as fh:
            fh.write(build_minimal_docx([("empty", ""), ("placeholder", "TODO")]))
        result = audit(tmp_a, strict=False)
        ck("公式总数正确", result["formula_count"] == 3,
           str(result["formula_count"]))
        ck("空公式被检出", result["empty_formula_count"] == 1,
           str(result["empty_formula_count"]))
        ck("占位符公式被检出", result["placeholder_formula_count"] == 1,
           str(result["placeholder_formula_count"]))
        ck("编号引用缺失被检出",
           any("式(2)" in it["quote"] for it in result["missing_number_refs"]),
           str([it["quote"] for it in result["missing_number_refs"]]))
        ck("已定义编号含 1", 1 in result["defined_equation_numbers"],
           str(result["defined_equation_numbers"]))
        ck("纯文本护栏被触发", result["guardrail_triggered"] is True)
        ck("纯文本公式数为 0", result["plain_text_formula_count"] == 0,
           str(result["plain_text_formula_count"]))
        ck("默认模式空公式为警告",
           any(it["kind"] == "空公式" and it["severity"] == "warning"
               for it in result["warnings"]))

        strict_result = audit(tmp_a, strict=True)
        ck("严格模式空公式为错误",
           any(it["kind"] == "空公式" and it["severity"] == "error"
               for it in strict_result["errors"]))

        # 第二份：纯文本里存在公式痕迹 → 护栏不应触发
        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            '<w:body><w:p><w:r><w:t>R2 = 0.87</w:t></w:r>'
            '<m:oMath><m:r><m:t>x=1</m:t></m:r></m:oMath></w:p>'
            '</w:body></w:document>'
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '</Types>'
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types)
            zf.writestr("word/document.xml", doc_xml)
        with open(tmp_b, "wb") as fh:
            fh.write(buf.getvalue())
        result_b = audit(tmp_b, strict=False)
        ck("有纯文本公式时护栏不触发",
           result_b["guardrail_triggered"] is False)
        ck("纯文本公式被计数", result_b["plain_text_formula_count"] >= 1,
           str(result_b["plain_text_formula_count"]))
    finally:
        for p in (tmp_a, tmp_b):
            if os.path.exists(p):
                os.remove(p)

    # CLI 端到端（捕捉只在命令行路径出现的错误）
    try:
        with open(tmp_a, "wb") as fh:
            fh.write(build_minimal_docx([("empty", ""), ("placeholder", "TODO")]))
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            code = main(["--docx", tmp_a])
        finally:
            sys.stdout = old
        ck("CLI 端到端可运行", code in (0, 1), str(code))
        ck("CLI 输出含公式总数", "公式总数" in buf.getvalue())
        ck("CLI 输出含硬护栏提示", "护栏" in buf.getvalue())
    finally:
        for p in (tmp_a, tmp_b):
            if os.path.exists(p):
                os.remove(p)

    failed = [c for c in checks if not c[1]]
    print("audit_docx_formulas selftest: {0}/{1} 通过".format(
        len(checks) - len(failed), len(checks)))
    for name, ok, detail in checks:
        print("  [{0}] {1}{2}".format("PASS" if ok else "FAIL", name,
                                     "" if ok else "  <- " + detail))
    if failed:
        print("selftest 失败：{0} 项未通过".format(len(failed)))
        return 2
    print("selftest 通过")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="audit_docx_formulas.py",
        description="DOCX 公式完整性审计：统计 OMML 公式、检出空公式/占位符/编号缺失，"
                    "并给出“纯文本改稿会丢公式”硬护栏。")
    p.add_argument("--docx", help="待审计的 .docx 文件")
    p.add_argument("--strict", action="store_true",
                   help="严格模式：空公式计为错误，且警告也导致失败退出码")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    p.add_argument("--selftest", action="store_true", help="运行离线自检（内存构造 docx）")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.docx:
        parser.print_usage(sys.stderr)
        print("错误：需要 --docx <path>，或使用 --selftest。", file=sys.stderr)
        return 2
    path = args.docx
    if not os.path.isfile(path):
        print("错误：文件不存在：{0}".format(path), file=sys.stderr)
        return 2
    try:
        result = audit(path, strict=args.strict)
    except ValueError as exc:
        print("错误：{0}".format(exc), file=sys.stderr)
        return 2
    except (zipfile.BadZipFile, ET.ParseError) as exc:
        print("错误：无法解析 docx：{0}".format(exc), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_report(result))
    if result["errors"]:
        return 1
    if args.strict and result["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
