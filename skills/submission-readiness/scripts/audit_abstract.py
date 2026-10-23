#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_abstract.py — 摘要体检（只枚举候选，不做语义判定）。

用法::

    python audit_abstract.py --file paper/abstract.md
    python audit_abstract.py --file abstract.docx --target-words 250
    python audit_abstract.py --file abstract.md --json
    python audit_abstract.py --selftest

退出码::

    0 = 未枚举出任何候选条目
    1 = 枚举出候选条目（需人工判断；不代表语义上“不通过”）
    2 = 用法错误或运行故障

设计约束::

    * 仅使用标准库；.docx 用 zipfile + xml.etree 解析 word/document.xml，不依赖 python-docx
    * Python 3.9 兼容（f-string 表达式内不出现反斜杠）
    * 每条输出都是「候选 + 位置 + 判据 + 需要人工判断什么」，不输出通过/不通过
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

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
EN_WORD_RE = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)*")
SENT_SPLIT_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")

# 结构五要素的检出信号词（仅用于「是否检出」的粗筛，不构成要素缺失的判定）
ELEMENTS = [
    ("背景", ["研究背景", "背景", "近年来", "随着", "目前", "领域", "广泛", "普遍"]),
    ("目标", ["目标", "目的", "旨在", "为了", "本文提出", "本研究", "我们提出", "致力于", "面向"]),
    ("方法", ["方法", "模型", "框架", "算法", "架构", "数据集", "实验设置", "实验设计", "实现", "训练"]),
    ("结果", ["结果", "实验表明", "结果显示", "实验显示", "准确率", "性能", "提升了", "取得了"]),
    ("结论", ["结论", "总结", "综上所述", "表明", "说明了", "未来工作", "展望"]),
]

# 模糊指代短语 -> 可选回指名词
VAGUE_PHRASES = [
    "该方法", "该研究", "该结果", "该工作", "该模型", "该系统", "该实验", "该文",
    "该框架", "该算法", "该文章", "该文", "该表", "该图",
    "上述方法", "上述结果", "上述工作", "上述研究", "上述实验", "上述模型", "上述算法",
    "上述系统", "上述框架", "上述表", "上述图",
    "前述方法", "前述结果", "前述工作", "前述研究", "前述实验", "前述模型",
    "这一方法", "这一结果", "这一工作", "这一研究", "这一实验",
    "这种方法", "这种结果", "这种工作", "这种研究",
    "这些方法", "这些结果", "这些工作", "这些研究", "这些实验",
    "这个方法", "这个结果", "这个工作", "这个研究", "这篇文章", "这篇文章",
]
REFERENT_NOUNS = ["方法", "研究", "结果", "工作", "实验", "模型", "系统", "框架",
                  "算法", "文章", "表", "图"]

# 过强断言用词
CLAIM_WORDS = ["证明了", "证实了", "充分证明", "证明", "必然", "必定", "一定会",
               "完全消除", "彻底", "毫无", "从未", "毫无例外", "远远超过",
               "国际领先", "填补了", "首创", "完美", "无可比拟", "无疑", "必然地"]
# 统计量支撑信号
STAT_MARKERS = ["p<", "p <", "p=", "p =", "p值", "p 值", "P<", "P <", "95%", "99%",
                "置信区间", "CI", "显著性", "标准差", "std", "s.e.", "t=", "F=",
                "卡方", "±", "样本量", "n =", "n=", "个样本", "重复", "次实验",
                "误差", "均值", "mean", "MDE", "效应量", "effect size", "p 值"]

# 被动 / 受事结构标记
PASSIVE_MARKERS = ["被", "受到", "遭到", "予以", "加以", "得以", "经由", "受制",
                   "受限于", "所"]

# 句首介词 / 状语（用于「疑似缺主语」粗筛）
PREPOSITIONAL_STARTS = ["通过", "基于", "由于", "对于", "随着", "从而", "进而",
                        "使得", "把", "将", "被", "从", "针对", "围绕", "依据",
                        "借助", "为了", "按照", "在", "经", "其中", "同时"]
# 显性施事 / 主题标记（命中即认为句中存在主语）
ACTOR_MARKERS = ["本文", "本研究", "我们", "作者", "该研究", "实验", "方法", "模型",
                 "系统", "算法", "框架", "结果", "分析", "数据", "工作", "团队",
                 "研究", "领域", "本文工作", "本文提出"]

# 幅度词与数值的可能冲突
BIG_WORDS = ["大幅", "大幅度", "极大", "成倍", "翻番", "翻倍", "倍增", "巨大",
             "显著提升", "显著改善", "显著降低"]
SMALL_WORDS = ["轻微", "略微", "微乎其微", "稍有", "小幅", "微幅", "稍稍"]
UP_WORDS = ["提高", "提升", "增加", "增长", "上升", "改善"]


def _strip_punct(text):
    return text.lstrip(" \t\r\n。．，,、；;：:（(【[")


def split_sentences(text):
    """按中文/英文句末标点切句，返回 [(起始下标, 句子)]。"""
    normalized = re.sub(r"(?<=[.!?])\s+(?=[A-Z\"'(])", "\n", text)
    out = []
    for m in SENT_SPLIT_RE.finditer(normalized):
        s = m.group(0).strip()
        if s:
            out.append((m.start(), s))
    return out


def count_cjk(text):
    return len(CJK_RE.findall(text))


def count_en_words(text):
    return len(EN_WORD_RE.findall(text))


def has_definition(noun, prefix):
    """判断 prefix 中是否出现过该名词的定义性表述（粗筛）。"""
    n = re.escape(noun)
    patterns = [
        r"本文[^。；\n]{0,30}" + n,
        r"(?:提出|构建|设计|引入|采用|开发)[^。；\n]{0,10}的?" + n,
        n + r"\s*[（(][^）)]{1,40}[）)]",
        n + r"\s*(?:叫做|称为|定义为|指的是)",
    ]
    for p in patterns:
        if re.search(p, prefix):
            return True
    return False


def find_baseline_defined(full_text):
    patterns = [
        r"基线\s*(?:为|是|采用|选择|参见|见|取)",
        r"基线\s*[（(]",
        r"baseline\s*[:：=（(\[]",
        r"对照组\s*(?:为|是|采用|设为|取)",
        r"对照组\s*[（(]",
        r"以[^。；\n]{1,24}作为基线",
        r"参考(?:组|系统|方法)\s*(?:为|是|采用)",
    ]
    for p in patterns:
        if re.search(p, full_text, re.IGNORECASE):
            return True
    return False


def analyze(units, target_words=None, max_sent_chars=60, max_sent_words=45):
    """units: [(unit_text, unit_index)]，返回 findings 列表。"""
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

    # ---- 2. 结构完整性（缺哪个报哪个，不猜作者本意）----
    structure = {}
    total_units = len(units) if units else 0
    for name, keywords in ELEMENTS:
        hits = [k for k in keywords if k in full_text]
        structure[name] = {"detected": bool(hits), "keywords": hits}
        if not hits:
            add("结构要素疑似缺失", "high",
                "全文（1-{0}）".format(total_units),
                "未检出「{0}」要素信号词".format(name),
                "「{0}」的常见信号词为：{1}".format(name, "、".join(keywords)),
                "请人工确认摘要是否真的缺少「{0}」这一要素；"
                "关键词未命中不等于缺失（可能用了同义表述）。".format(name))

    # ---- 1. 逐句可疑片段枚举 ----
    prefix = ""
    for text, idx in units:
        locator = "第{0}行".format(idx) if idx is not None else "第{0}段".format(idx)
        for offset, sent in split_sentences(text):
            head = _strip_punct(sent)
            cjk = count_cjk(sent)
            words = count_en_words(sent)

            # 句子过长
            if cjk >= max_sent_chars or words >= max_sent_words:
                add("句子过长", "low", locator, sent[:80],
                    "单句中文字符数 >= {0} 或英文词数 >= {1}".format(
                        max_sent_chars, max_sent_words),
                    "该句是否承载了多个逻辑层次，是否需要拆句；"
                    "长句不等于错句，需按语义判断。")

            # 被动 / 受事结构堆叠
            found_passive = sorted(set(p for p in PASSIVE_MARKERS if p in sent))
            if len(found_passive) >= 2:
                add("被动结构堆叠", "low", locator, sent[:80],
                    "同一句中出现 >= 2 个被动/受事标记：{0}".format(
                        "、".join(found_passive)),
                    "是否因层层转述导致责任主体（谁做了什么）不明确。")

            # 疑似缺主语
            starts_prep = any(head.startswith(p) for p in PREPOSITIONAL_STARTS)
            has_actor = any(a in sent for a in ACTOR_MARKERS)
            if starts_prep and not has_actor:
                add("疑似缺主语", "low", locator, sent[:80],
                    "句子以介词/状语开头（{0}），句内未检出显性施事标记".format(
                        head[:4]),
                    "该句的动作承担者是谁；是否需要补出主体。")

            # 模糊指代
            for phrase in VAGUE_PHRASES:
                if phrase not in sent:
                    continue
                noun = None
                for n in REFERENT_NOUNS:
                    if n in phrase:
                        noun = n
                        break
                local_prefix = prefix + text[:text.find(phrase)]
                if noun is None:
                    add("模糊指代", "medium", locator, sent[:80],
                        "出现不可回指的短语「{0}」".format(phrase),
                        "该指代具体指向哪一对象；若文中未定义，需补全。")
                elif not has_definition(noun, local_prefix):
                    add("模糊指代", "medium", locator, sent[:80],
                        "出现「{0}」，但前文未检出「{1}」的定义性表述".format(
                            phrase, noun),
                        "「{0}」首次出现处是否已有定义（或是否为公认术语可直接使用）。".format(
                            noun))

            # 过强断言
            claims = [c for c in CLAIM_WORDS if c in sent]
            if claims:
                has_stat = any(s in sent for s in STAT_MARKERS)
                if not has_stat:
                    add("过强断言", "medium", locator, sent[:80],
                        "出现断言词「{0}」，同句未检出统计量支撑".format(
                            claims[0]),
                        "该断言是否有可核验的统计证据；"
                        "若无，需降级为「提示/表明/与…相关」等表述。")

            # 数字与结论不匹配
            pcts = [float(x) for x in PCT_RE.findall(sent)]
            if pcts:
                big = [w for w in BIG_WORDS if w in sent]
                small = [w for w in SMALL_WORDS if w in sent]
                if big and min(pcts) < 3:
                    add("数值与幅度词可能不匹配", "medium", locator, sent[:80],
                        "幅度词「{0}」与数值 {1}% 量级偏小".format(
                            big[0], PCT_RE.search(sent).group(1)),
                        "该数值是否被正确表述（绝对量 / 相对量 / 百分点）。")
                if small and max(pcts) >= 20:
                    add("数值与幅度词可能不匹配", "medium", locator, sent[:80],
                        "幅度词「{0}」与数值 {1}% 量级偏大".format(
                            small[0], PCT_RE.search(sent).group(1)),
                        "该数值是否被正确表述（绝对量 / 相对量 / 百分点）。")
                if any(w in sent for w in ["翻番", "翻倍", "成倍", "倍增"]) and max(pcts) < 100:
                    add("数值与幅度词可能不匹配", "medium", locator, sent[:80],
                        "倍数表述与百分比数值不自洽",
                        "倍数与百分比是否指同一口径；是否漏写「增长到 N 倍」。")
                if any(w in sent for w in UP_WORDS) and max(pcts) > 100:
                    add("数值超出常见区间", "medium", locator, sent[:80],
                        "提升类表述搭配的百分比 > 100%",
                        "该数值是「增长到 N%」还是「提高了 N%」；"
                        "是否为倍数或百分点口径。")

            # 与基线比较但基线未定义
            if ("基线" in sent or "baseline" in sent.lower()
                    or "对照组" in sent) and not find_baseline_defined(full_text):
                add("比较对象疑似未定义", "medium", locator, sent[:80],
                    "句中出现比较对象（基线 / 对照组），全文未检出其定义表述",
                    "文中何处定义了比较对象；"
                    "该比较对象是否与正文实验设置一致。")
        prefix += text + "\n"

    # ---- 3. 词数统计 ----
    cjk_total = count_cjk(full_text)
    en_total = count_en_words(full_text)
    total_units_count = cjk_total + en_total
    counts = {
        "cjk_chars": cjk_total,
        "en_words": en_total,
        "total": total_units_count,
        "target_words": target_words,
    }
    if target_words is not None:
        if total_units_count > target_words:
            add("篇幅超出目标", "high", "全文",
                "实际 {0}（中文 {1} 字符 + 英文 {2} 词）".format(
                    total_units_count, cjk_total, en_total),
                "目标上限 {0}".format(target_words),
                "超出的部分是否可删减；字数上限以目标期刊官网为准。")
        else:
            add("篇幅未超目标", "low", "全文",
                "实际 {0}（中文 {1} 字符 + 英文 {2} 词）".format(
                    total_units_count, cjk_total, en_total),
                "目标上限 {0}".format(target_words),
                "是否过短导致要素不全；是否需要补充关键信息。")
    return findings, structure, counts


def read_units(path):
    """返回 (units, unit_kind)。units = [(text, index)]。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".docx",):
        paras = docx_paragraphs(path)
        return [(t, i + 1) for i, t in enumerate(paras)], "paragraph"
    if ext in (".md", ".markdown", ".txt", ".text", ""):
        with io.open(path, "r", encoding="utf-8-sig") as fh:
            content = fh.read()
        lines = content.splitlines()
        return [(t, i + 1) for i, t in enumerate(lines)], "line"
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


def format_report(path, unit_kind, findings, structure, counts):
    lines = []
    lines.append("=== 摘要体检报告 ===")
    lines.append("文件：{0}".format(path))
    kind_label = "行" if unit_kind == "line" else "段"
    lines.append("定位单位：{0}（{1}）".format(kind_label, unit_kind))
    lines.append("字数：中文 {0} 字符 + 英文 {1} 词 = 合计 {2}".format(
        counts["cjk_chars"], counts["en_words"], counts["total"]))
    if counts["target_words"] is not None:
        target = counts["target_words"]
        actual = counts["total"]
        state = "超出目标" if actual > target else "未超目标"
        lines.append("目标上限：{0} → 实际 {1}，{2}（差 {3:+d}）".format(
            target, actual, state, actual - target))
    else:
        lines.append("目标上限：未指定（未做超限判定）")

    lines.append("")
    lines.append("--- 结构要素检出情况 ---")
    for name, info in structure.items():
        if info["detected"]:
            lines.append("  [{0}] 命中信号词：{1}".format(
                name, "、".join(info["keywords"][:6])))
        else:
            lines.append("  [{0}] 未检出信号词 → 已记为候选条目（需人工确认）".format(name))

    lines.append("")
    lines.append("--- 候选条目（共 {0} 条；机器只枚举候选，不作通过/不通过判定）---".format(
        len(findings)))
    if not findings:
        lines.append("  （未枚举出候选条目。注意：这不等于语义上没有问题。）")
    for i, f in enumerate(findings, 1):
        lines.append("  [{0}] {1} · {2}".format(i, f["kind"], f["severity"]))
        lines.append("      位置：{0}".format(f["locator"]))
        lines.append("      候选：{0}".format(f["quote"]))
        lines.append("      判据：{0}".format(f["criterion"]))
        lines.append("      需要人工判断：{0}".format(f["human_check"]))
    return "\n".join(lines)


def build_minimal_docx():
    """在内存中构造一个最小 docx（含一个带正文的段落），用于自检。"""
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>Abstract sentence one.</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>Second sentence.</w:t></w:r></w:p></w:body></w:document>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
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

    # 1) 长句
    long_sent = "本文构建了一个" + "非常复杂的" * 40 + "模型。"
    units = [(long_sent, 1)]
    f, _, _ = analyze(units)
    ck("长句被枚举", any(x["kind"] == "句子过长" for x in f))

    # 2) 模糊指代（无定义）
    units = [("该方法显著提升了性能。", 1)]
    f, _, _ = analyze(units)
    ck("模糊指代被枚举", any(x["kind"] == "模糊指代" for x in f))

    # 3) 模糊指代（有定义则不报）
    units = [("本文提出的方法在该领域广泛使用。", 1),
             ("该方法显著提升了性能。", 2)]
    f, _, _ = analyze(units)
    vague = [x for x in f if x["kind"] == "模糊指代"]
    ck("有定义时不报模糊指代", not vague, str([x["quote"] for x in vague]))

    # 4) 过强断言
    units = [("实验结果证明了该框架的有效性。", 1)]
    f, _, _ = analyze(units)
    ck("过强断言被枚举", any(x["kind"] == "过强断言" for x in f))

    # 5) 数值与幅度词冲突
    units = [("性能大幅提升了 1%。", 1)]
    f, _, _ = analyze(units)
    ck("幅度词冲突被枚举",
       any(x["kind"] in ("数值与幅度词可能不匹配", "数值超出常见区间") for x in f))

    # 6) 结构缺项
    units = [("我们提出一个方法用于识别问题。", 1)]
    f, structure, counts = analyze(units)
    ck("结构缺失被报出",
       any(x["kind"] == "结构要素疑似缺失" for x in f))
    ck("结构检测结果可序列化", isinstance(structure, dict) and len(structure) == 5)

    # 7) 字数统计
    units = [("中文 12 个字符 abc def。", 1)]
    f, structure, counts = analyze(units, target_words=2)
    # "中文 12 个字符 abc def。" → 中文 5 字（句号不在 CJK 汉字区）、英文 2 词
    ck("字数统计正确", counts["cjk_chars"] == 5 and counts["en_words"] == 2,
       str(counts))
    ck("超限被报出", any(x["kind"] == "篇幅超出目标" for x in f))

    # 8) docx 读取（内存构造）
    data = build_minimal_docx()
    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_selftest_tmp.docx")
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        paras, kind = read_units(tmp)
        ck("docx 段落读取正常",
           kind == "paragraph" and len(paras) == 2
           and "Abstract" in paras[0][0], str(paras))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    # 9) 严重度字段完整
    f, _, _ = analyze([("该方法。", 1)])
    ck("finding 字段完整",
       all(set(("kind", "severity", "locator", "quote", "criterion",
                "human_check")).issubset(set(x)) for x in f))

    # 10) CLI 端到端（捕捉只在命令行路径出现的属性名漂移）
    parser = build_parser()
    ns = parser.parse_args(["--file", "x.md", "--target-words", "100",
                            "--max-sentence-chars", "50",
                            "--max-sentence-words", "30"])
    try:
        analysis_kwargs(ns)
        ck("CLI 参数名一致", True)
    except AttributeError as exc:
        ck("CLI 参数名一致", False, str(exc))

    tmp_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "_selftest_cli.md")
    try:
        with io.open(tmp_cli, "w", encoding="utf-8") as fh:
            fh.write("本文提出了一种方法用于识别问题。该方法证明有效。\n")
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            code = main(["--file", tmp_cli, "--target-words", "50"])
        finally:
            sys.stdout = old
        ck("CLI 端到端可运行", code in (0, 1), str(code))
        ck("CLI 输出含报告标题", "摘要体检报告" in buf.getvalue())
    finally:
        if os.path.exists(tmp_cli):
            os.remove(tmp_cli)

    failed = [c for c in checks if not c[1]]
    print("audit_abstract selftest: {0}/{1} 通过".format(
        len(checks) - len(failed), len(checks)))
    for name, ok, detail in checks:
        print("  [{0}] {1}{2}".format("PASS" if ok else "FAIL", name,
                                     "" if ok else "  <- " + detail))
    if failed:
        print("selftest 失败：{0} 项未通过".format(len(failed)))
        return 2
    print("selftest 通过")
    return 0


def analysis_kwargs(args):
    """把 argparse 命名空间转成 analyze() 的关键字参数（主流程与自检共用，避免属性名漂移）。"""
    return {
        "target_words": args.target_words,
        "max_sent_chars": args.max_sentence_chars,
        "max_sent_words": args.max_sentence_words,
    }


def build_parser():
    p = argparse.ArgumentParser(
        prog="audit_abstract.py",
        description="摘要体检：逐句枚举可疑片段、检出结构要素、统计字数（只枚举，不下语义判定）。")
    p.add_argument("--file", help="待体检文件（.md / .txt / .docx）")
    p.add_argument("--target-words", type=int, default=None,
                   help="摘要字数上限（可选）；上限以目标期刊官网要求为准")
    p.add_argument("--max-sentence-chars", type=int, default=60,
                   help="单句中文字符数阈值（默认 60）")
    p.add_argument("--max-sentence-words", type=int, default=45,
                   help="单句英文词数阈值（默认 45）")
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

    findings, structure, counts = analyze(units, **analysis_kwargs(args))

    if args.json:
        payload = {
            "file": path,
            "unit_kind": unit_kind,
            "counts": counts,
            "structure": structure,
            "findings": findings,
            "note": "机器只枚举候选条目，不做通过/不通过的语义判定。",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_report(path, unit_kind, findings, structure, counts))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
