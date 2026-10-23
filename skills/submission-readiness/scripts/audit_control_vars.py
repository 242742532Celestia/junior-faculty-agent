#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_control_vars.py — 控制变量（control variable）/ 参考状态体检。

用法::

    python audit_control_vars.py --file paper/methods.md
    python audit_control_vars.py --file methods.docx --json
    python audit_control_vars.py --selftest

退出码::

    0 = 未发现事实缺口
    1 = 发现事实缺口（需人工补全，不推断作者本意）
    2 = 用法错误或运行故障

设计约束::

    * 仅使用标准库；.docx 用 zipfile + xml.etree 解析 word/document.xml，不依赖 python-docx
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
W_P = "{%s}p" % W_NS
W_T = "{%s}t" % W_NS

# 1. “其余条件保持不变”类模糊表述（长匹配优先，避免重复报告）
FUZZY_HOLD = [
    "其余参数保持不变", "其他参数保持不变", "其余变量保持不变", "其他变量保持不变",
    "其余设置保持不变", "其余条件保持不变", "其他条件保持不变",
    "其余几何条件未变", "其他几何条件未变", "其余边界条件未变", "其余工况未变",
    "其余同前", "其它同前", "其余保持不变", "其他保持不变", "保持不变",
    "未作其他改变", "不作其他改变", "其余条件不变", "其他条件不变",
]
FUZZY_RE = re.compile("|".join(re.escape(k) for k in FUZZY_HOLD))

# 2. 参数区间（连字符 / 连接号 / ～ / 至 / 到）
RANGE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:--|—|―|–|~|-|～|至|到)\s*(\d+(?:\.\d+)?)")
RANGE_WORD_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:到|至)\s*(\d+(?:\.\d+)?)")
BETWEEN_RE = re.compile(r"介于\s*(\d+(?:\.\d+)?)\s*和\s*(\d+(?:\.\d+)?)\s*之间")

# 参数表线索
TABLE_HINT = ["参数", "取值", "取值范围", "超参", "超参数", "设置", "配置",
              "学习率", "批次", "窗口", "步长", "迭代", "阈值", "取值区间"]
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")

# 3. 例外项
EXCEPT_RE = re.compile(r"除[^。；;\n]{0,24}?外")
EXCEPT_RE2 = re.compile(r"除了[^。；;\n]{0,24}?以外")

# 4. 比较对象 / 基线
BASELINE_MENTION = ["基线", "baseline", "对照组", "参考系统", "参照组", "对照方法"]
BASELINE_DEF = [
    r"基线\s*(?:为|是|采用|选择|参见|见|取|设为)",
    r"基线\s*[（(]",
    r"baseline\s*[:：=（(\[]",
    r"对照组\s*(?:为|是|采用|设为|取)",
    r"对照组\s*[（(]",
    r"以[^。；\n]{1,24}作为基线",
    r"参考(?:组|系统|方法)\s*(?:为|是|采用)",
    r"参照(?:组|系统|方法)\s*(?:为|是|采用)",
]
COMPARE_RE = re.compile(
    r"与[^。；\n]{0,12}基线[^。；\n]{0,12}比较|相比[^。；\n]{0,12}基线|"
    r"较[^。；\n]{0,12}基线|优于[^。；\n]{0,12}基线|"
    r"baseline|对照组|对照方法|参照组|参考系统")


def read_units(path):
    """返回 (units, unit_kind)。units = [(text, index)]。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return [(t, i + 1) for i, t in enumerate(docx_paragraphs(path))], "paragraph"
    if ext in (".md", ".markdown", ".txt", ".text", ""):
        with io.open(path, "r", encoding="utf-8-sig") as fh:
            content = fh.read()
        return [(t, i + 1) for i, t in enumerate(content.splitlines())], "line"
    raise ValueError("不支持的文件类型：{0}（支持 .md / .txt / .docx）".format(ext))


def docx_paragraphs(docx_path):
    with zipfile.ZipFile(docx_path) as zf:
        try:
            xml_bytes = zf.read("word/document.xml")
        except KeyError:
            raise ValueError("docx 内缺少 word/document.xml")
    root = ET.fromstring(xml_bytes)
    paras = []

    def walk(node):
        for child in list(node):
            if child.tag == W_P:
                txt = "".join(t.text or "" for t in child.iter(W_T))
                paras.append(txt)
                walk(child)
            else:
                walk(child)

    walk(root)
    return paras


def is_param_table_unit(text, unit_kind):
    """该单元是否像“参数表/参数说明”。"""
    if TABLE_ROW_RE.match(text):
        return True
    if re.search(r"表\s*\d+\s*[：:．.]?\s*\S*参数", text):
        return True
    return any(h in text for h in TABLE_HINT)


def analyze(units, unit_kind):
    findings = []
    full_text = "\n".join(t for t, _ in units)

    def add(kind, severity, locator, quote, criterion, human):
        findings.append({
            "kind": kind,
            "severity": severity,
            "locator": locator,
            "quote": quote,
            "criterion": criterion,
            "human_check": human,
        })

    for text, idx in units:
        locator = ("第{0}行".format(idx) if unit_kind == "line"
                   else "第{0}段".format(idx))

        # 1. 模糊的“保持不变”表述
        for m in FUZZY_RE.finditer(text):
            add("模糊的“保持不变”表述", "medium", locator, m.group(0),
                "出现「{0}」类未具名的固定条件表述".format(m.group(0)),
                "需要显式列出被固定的量：变量名、取值、单位、来源；"
                "“其余”具体指哪些量？")

        # 2. 参数区间
        ranges = []
        for rx in (RANGE_RE, RANGE_WORD_RE, BETWEEN_RE):
            for m in rx.finditer(text):
                ranges.append((m.start(), m.group(0), m.group(1), m.group(2)))
        if ranges:
            in_table = is_param_table_unit(text, unit_kind)
            for _start, matched, lo, hi in ranges:
                try:
                    lo_f = float(lo)
                    hi_f = float(hi)
                except ValueError:
                    lo_f = hi_f = 0.0
                single = lo_f == hi_f
                severity = "medium" if in_table else "low"
                add("参数区间取值", severity, locator, matched,
                    "出现区间「{0}」{1}".format(
                        matched, "（位于参数表/参数说明中）" if in_table else ""),
                    "若实际固定为单值，应说明用的是哪个值；"
                    "若确为区间，需说明取值依据与是否逐点扫描。")

        # 3. 例外项
        for rx in (EXCEPT_RE, EXCEPT_RE2):
            for m in rx.finditer(text):
                add("例外项未交代", "medium", locator, m.group(0),
                    "出现排除式表述「{0}」".format(m.group(0)),
                    "需说明例外项的处理方式：是否单独报告、是否剔除、依据是什么；"
                    "排除后样本量如何变化。")

    # 4. 比较对象 / 基线缺失定义
    baseline_defined = any(re.search(p, full_text, re.IGNORECASE)
                           for p in BASELINE_DEF)
    if not baseline_defined:
        for text, idx in units:
            locator = ("第{0}行".format(idx) if unit_kind == "line"
                       else "第{0}段".format(idx))
            for m in COMPARE_RE.finditer(text):
                add("比较对象疑似未定义", "high", locator, m.group(0),
                    "文中出现比较对象（基线 / 对照组 / 参考系统），"
                    "但全文未检出其定义性表述",
                    "基线/对照组的定义出现在哪里（哪一节、哪个引用）；"
                    "比较对象是否与正文实验设置一致。")
    return findings


def format_report(path, unit_kind, findings):
    lines = []
    lines.append("=== 控制变量 / 参考状态体检报告 ===")
    lines.append("文件：{0}".format(path))
    kind_label = "行" if unit_kind == "line" else "段"
    lines.append("定位单位：{0}".format(kind_label))
    lines.append("")
    lines.append("--- 事实缺口（共 {0} 条）---".format(len(findings)))
    if not findings:
        lines.append("  （未检出事实缺口。注意：这不等于实验设计无问题。）")
    for i, f in enumerate(findings, 1):
        lines.append("  [{0}] {1} · {2}".format(i, f["kind"], f["severity"]))
        lines.append("      位置：{0}".format(f["locator"]))
        lines.append("      原文片段：{0}".format(f["quote"]))
        lines.append("      判据：{0}".format(f["criterion"]))
        lines.append("      需要人工判断：{0}".format(f["human_check"]))
    return "\n".join(lines)


def build_minimal_docx():
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'
        '<w:p><w:r><w:t>表 1 参数设置</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>学习率取值 10-50，其余参数保持不变。</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>除 B 组外均采用相同设置。</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>本文结果与基线比较。</w:t></w:r></w:p>'
        '</w:body></w:document>'
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

    units = [
        ("表 1 参数设置", 1),
        ("| 参数 | 取值 |", 2),
        ("| 学习率 | 10-50 |", 3),
        ("除 B 组外，其余设置一致。", 4),
        ("其余参数保持不变。", 5),
        ("本文结果与基线比较。", 6),
    ]
    f = analyze(units, "line")
    kinds = [x["kind"] for x in f]
    ck("模糊保持不变被报出", "模糊的“保持不变”表述" in kinds)
    ck("参数区间被报出", "参数区间取值" in kinds)
    ck("例外项被报出", "例外项未交代" in kinds)
    ck("基线缺失被报出", "比较对象疑似未定义" in kinds)
    ck("每条含定位与判据",
       all(("locator" in x and "criterion" in x and "human_check" in x) for x in f))
    ck("参数表内区间级别为 medium",
       any(x["kind"] == "参数区间取值" and x["severity"] == "medium" for x in f))

    # 有基线定义时不应报基线缺失
    units2 = [("基线采用 XX 方法。", 1), ("本文结果与基线比较。", 2)]
    f2 = analyze(units2, "line")
    ck("有基线定义时不报缺失",
       not any(x["kind"] == "比较对象疑似未定义" for x in f2),
       str([x["quote"] for x in f2]))

    # docx 读取路径
    data = build_minimal_docx()
    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_selftest_tmp2.docx")
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        got, kind = read_units(tmp)
        ck("docx 段落读取正常", kind == "paragraph" and len(got) == 4, str(got))
        f3 = analyze(got, kind)
        ck("docx 内容被检出",
           any(x["kind"] == "模糊的“保持不变”表述" for x in f3))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    # CLI 端到端（捕捉只在命令行路径出现的错误）
    tmp_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "_selftest_cli.md")
    try:
        with io.open(tmp_cli, "w", encoding="utf-8") as fh:
            fh.write("表 1 参数设置\n\n| 学习率 | 10-50 |\n\n其余参数保持不变。\n")
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            code = main(["--file", tmp_cli])
        finally:
            sys.stdout = old
        ck("CLI 端到端可运行", code in (0, 1), str(code))
        ck("CLI 输出含报告标题", "控制变量" in buf.getvalue())
    finally:
        if os.path.exists(tmp_cli):
            os.remove(tmp_cli)

    failed = [c for c in checks if not c[1]]
    print("audit_control_vars selftest: {0}/{1} 通过".format(
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
        prog="audit_control_vars.py",
        description="控制变量/参考状态体检：模糊“保持不变”、参数区间、例外项、基线缺失。")
    p.add_argument("--file", help="待体检文件（.md / .txt / .docx）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    p.add_argument("--selftest", action="store_true", help="运行离线自检")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.file:
        parser.print_usage(sys.stderr)
        print("错误：需要 --file <path>，或使用 --selftest。", file=sys.stderr)
        return 2
    path = args.file
    if not os.path.isfile(path):
        print("错误：文件不存在：{0}".format(path), file=sys.stderr)
        return 2
    try:
        units, unit_kind = read_units(path)
    except ValueError as exc:
        print("错误：{0}".format(exc), file=sys.stderr)
        return 2
    except (zipfile.BadZipFile, ET.ParseError) as exc:
        print("错误：无法解析 docx：{0}".format(exc), file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print("错误：文件不是 UTF-8 文本，请先转码后重试。", file=sys.stderr)
        return 2

    findings = analyze(units, unit_kind)
    if args.json:
        payload = {
            "file": path,
            "unit_kind": unit_kind,
            "findings": findings,
            "note": "只报可确定的事实缺口，不推断作者本意。",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_report(path, unit_kind, findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
