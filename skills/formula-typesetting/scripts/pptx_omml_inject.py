#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
pptx_omml_inject.py —— 把 LaTeX 公式注入 PPTX，生成 **PowerPoint 原生可编辑公式**（OMML）。

为什么需要它
------------
PPTX 里的公式要变成「双击能进公式编辑器」的真公式，必须注入 OMML（`<a14:m>`），
而不是贴图片或塞 Unicode 伪公式。LaTeX→OMML 用本机已装的 pandoc（内含 texmath），
零新增第三方依赖。

三种排布都支持
--------------
  整条是公式        → 整条替换成 `<a14:m>`
  文字 + 公式       → 文字留 run，紧跟 `<a14:m>`
  文字 + 公式 + 文字 → 拆成 `文字 run` + `<a14:m>` + `文字 run`（真正的行内公式）

🔴 三条铁律（踩过就废，详见 references/omml-injection.md）
  1. `a:p` 的子元素顺序必须是 pPr, (r|br|fld|a14:m)*, endParaRPr
     ⇒ 只能**就地替换** `<a:r>`；顺序错 ⇒ PowerPoint「修复」并**无声删掉整个形状**。
  2. `m:r` 内部顺序是 m:rPr, a:rPr, m:t —— a:rPr 必须整段拼好再闭合，
     否则游离的 `/>` 会被当字面量渲染出来（满屏 "/>"）。
  3. 一行一个公式用 inline 的 `m:oMath`；用 `m:oMathPara` 时 PowerPoint 会合并相邻的。

用法
----
  # ① 先看看 deck 里有什么文本（用来写 spec）
  python pptx_omml_inject.py --scan deck.pptx

  # ② 按 spec 注入，产出新文件
  python pptx_omml_inject.py deck.pptx out.pptx --spec spec.json

  # ③ 只看会改成什么，不写文件
  python pptx_omml_inject.py deck.pptx out.pptx --spec spec.json --dry-run

spec.json 格式
--------------
{
  "parts": [
    {"part": "ppt/slides/slide3.xml",
     "target": "x = A₀e^(−γt)cos(ω_d t + φ)",
     "latex": "x = A_0 e^{-\\gamma t} \\cos(\\omega_d t + \\varphi)"},

    {"part": "ppt/slides/slide2.xml",
     "target": "阻尼比 ζ = γ/ω₀",
     "prefix": "阻尼比 ",
     "latex": "\\zeta = \\frac{\\gamma}{\\omega_0}"},

    {"part": "ppt/notesSlides/notesSlide2.xml",
     "auto": true}
  ]
}

`auto: true` = 自动检测该 part 里的公式片段并**行内**注入（片段位置由
formula_norm.find_spans 给出）。`prefix`/`suffix` 可选，分别对应公式前后的文字。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formula_norm  # noqa: E402

NS_A14 = "http://schemas.microsoft.com/office/drawing/2010/main"
NS_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"


# ══════════════════════════════════════════════════════════════════
# 1. LaTeX → OMML（走 pandoc / texmath）
# ══════════════════════════════════════════════════════════════════
def latex_to_omml(latex):
    """LaTeX → <m:oMath>...</m:oMath> 片段（inline 形式）。"""
    tmpdir = tempfile.mkdtemp(prefix="omml_")
    tmp_tex = os.path.join(tmpdir, "m.tex")
    tmp_docx = os.path.join(tmpdir, "m.docx")
    try:
        with open(tmp_tex, "w", encoding="utf-8") as f:
            f.write("$%s$\n" % latex)
        r = subprocess.run(["pandoc", "-f", "latex", "-t", "docx", "-o", tmp_docx, tmp_tex],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("pandoc 失败：%s" % (r.stderr or "").strip()[:300])
        with zipfile.ZipFile(tmp_docx) as z:
            xml = z.read("word/document.xml").decode("utf-8")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    m = re.search(r"<m:oMath>.*?</m:oMath>", xml, re.S)
    if not m:
        raise RuntimeError("pandoc 没产出 oMath：%s" % latex)
    return m.group(0)


def inject_arpr(omml, sz, color):
    """给每个 m:r 注入 a:rPr（字号/颜色），顺序 m:rPr, a:rPr, m:t。

    🔴 带颜色时必须**整段拼好再闭合**。把 `/>` 放模板尾部、再拼 solidFill，
    闭合标签会跑到 </a:rPr> 之后，在 m:r 里留下游离的 `/>` 文本节点 ——
    PowerPoint 不报错，直接把它当字面量渲染出来（满屏 "/>"）。
    """
    if color:
        arpr = ('<a:rPr lang="en-US" sz="%d" dirty="0">'
                '<a:solidFill><a:srgbClr val="%s"/></a:solidFill>'
                '</a:rPr>' % (sz, color))
    else:
        arpr = '<a:rPr lang="en-US" sz="%d" dirty="0"/>' % sz

    def one(mm):
        body = mm.group(1)
        mrpr = re.match(r"\s*(<m:rPr>.*?</m:rPr>)", body, re.S)
        if mrpr:
            body = mrpr.group(1) + arpr + body[mrpr.end():]
        else:
            body = arpr + body
        return "<m:r>" + body + "</m:r>"

    omml = re.sub(r"<m:r>(.*?)</m:r>", one, omml, flags=re.S)
    omml = omml.replace("<m:t>", '<m:t xml:space="preserve">')
    return omml


def build_a14m(latex, sz, color):
    omml = inject_arpr(latex_to_omml(latex), sz or 1800, color)
    return ('<a14:m xmlns:a14="%s" xmlns:m="%s" xmlns:a="%s">%s</a14:m>'
            % (NS_A14, NS_M, NS_A, omml))


# ══════════════════════════════════════════════════════════════════
# 2. XML 小工具
# ══════════════════════════════════════════════════════════════════
def xesc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def unescape(s):
    return (s.replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&apos;", "'")
             .replace("&amp;", "&"))


# ── LaTeX 源码片段（源已规范化时用） ──────────────────────────────
# 🔴 两种源形态对应两条注入路径：
#    · 源**未规范化**（正文页写着 `c = B²L²/R`）→ `auto` 模式：先探测伪公式再转写。
#    · 源**已规范化**（正文页写着 `$c = \frac{B^2L^2}{R}$`）→ `latex` 模式：
#      直接把 `$…$` 里的 LaTeX 注入。
#    两条路径都产出同一种东西：`<a14:m>` 原生公式对象。
_LATEX_SPAN = re.compile(r"\$\$(.+?)\$\$|\$(?!\$)([^$\n]+?)(?<!\$)\$", re.S)
# 「像不像 LaTeX」：**判据不重写一份** —— 用 `formula_norm.looks_like_latex`
# （注入器与验收闸共用同一份，见那里的注释：两边各写一份就会同时漏判）。


def looks_like_latex(s):
    """这段文本像不像 LaTeX 公式（用来排除 `$50` 这种货币写法）。

    🔴 判据在 `formula_norm` 里（注入器与验收闸共用一份）——
       窄判据会漏掉 `F = -BLi` 这种**只有字母和运算符**的简单关系式。
    """
    return formula_norm.looks_like_latex(s)


def find_latex_spans(text):
    """找出文本里**已经是 LaTeX 源码**的公式片段。返回 [(start, end, latex)]。

    与 `formula_norm.find_spans` 的区别：那个找的是**伪公式**（要转写），
    这个找的是**已写好的 LaTeX**（要注入）。
    """
    spans = []
    for m in _LATEX_SPAN.finditer(text):
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        if not looks_like_latex(inner):
            continue
        spans.append((m.start(), m.end(), inner.strip()))
    return spans


def patch_root(xml):
    """给根元素补命名空间 + mc:Ignorable（幻灯片是 <p:sld>，备注页是 <p:notes>）。"""
    m = re.search(r"<p:(?:sld|notes)\b[^>]*>", xml)
    if not m:
        raise RuntimeError("找不到 <p:sld>/<p:notes> 根元素")
    tag = m.group(0)
    if "xmlns:a14" in tag:
        return xml
    add = (' xmlns:a14="%s" xmlns:m="%s" xmlns:mc="%s" mc:Ignorable="a14"'
           % (NS_A14, NS_M, NS_MC))
    return xml[:m.start()] + tag[:-1] + add + ">" + xml[m.end():]


def read_run_style(run):
    """从 run 里读字号与颜色（公式要继承它们）。"""
    szm = re.search(r'sz="(\d+)"', run)
    sz = int(szm.group(1)) if szm else None
    cm = re.search(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', run)
    return sz, (cm.group(1) if cm else None)


def make_run(run_xml, text):
    """复制一个 run，只把 <a:t> 的内容换成 text（属性原样保留）。"""
    def rep(m):
        return "<a:t%s>%s</a:t>" % (m.group(1) or "", xesc(text))
    return re.sub(r"<a:t(\s[^>]*)?>(.*?)</a:t>", rep, run_xml, count=1, flags=re.S)


def inject_spans_into_run(run_xml, plain, spans):
    """把一个 run 按公式片段拆成「文字 / 公式 / 文字 …」的序列。"""
    out = []
    pos = 0
    for (s, e, latex) in spans:
        if s > pos:
            out.append(make_run(run_xml, plain[pos:s]))
        sz, color = read_run_style(run_xml)
        out.append(build_a14m(latex, sz, color))
        pos = e
    if pos < len(plain):
        out.append(make_run(run_xml, plain[pos:]))
    return "".join(out)


# ══════════════════════════════════════════════════════════════════
# 3. 注入
# ══════════════════════════════════════════════════════════════════
def patch_target(xml, target, latex, prefix="", suffix=""):
    """把承载 target 文字的那个 run 换成公式（可带前后文字）。"""
    t_esc = xesc(target)
    pm = re.search(r"<a:p>(?:(?!</a:p>).)*?<a:t>%s</a:t>(?:(?!</a:p>).)*?</a:p>"
                   % re.escape(t_esc), xml, re.S)
    if not pm:
        raise RuntimeError("这一 part 里找不到目标文字：%r" % target)
    para = pm.group(0)
    rm = re.search(r"<a:r>(?:(?!</a:r>).)*?<a:t>%s</a:t>(?:(?!</a:r>).)*?</a:r>"
                   % re.escape(t_esc), para, re.S)
    if not rm:
        raise RuntimeError("找不到承载该文字的 run：%r" % target)
    run = rm.group(0)
    sz, color = read_run_style(run)
    a14m = build_a14m(latex, sz, color)
    if prefix or suffix:
        pieces = []
        if prefix:
            pieces.append(make_run(run, prefix))
        pieces.append(a14m)
        if suffix:
            pieces.append(make_run(run, suffix))
        new_para = para[:rm.start()] + "".join(pieces) + para[rm.end():]
    else:
        new_para = para[:rm.start()] + a14m + para[rm.end():]
    return xml[:pm.start()] + new_para + xml[pm.end():]


def patch_auto(xml):
    """自动检测该 part 里的公式片段并**行内**注入。返回 (xml, 命中数, 明细)。

    🔴 偏移陷阱：所有匹配的偏移量是在**原始** xml 上算的，
       而公式片段比原文字长，替换后 xml 变长 ⇒ 后续偏移全部错位，
       公式会被插进错误位置（实测吃掉一个表格单元格的 <p:sp> 标签）。
       ⇒ 先收集全部编辑，再**从后往前**替换，前面的改动才不会影响后面的偏移。
    """
    hits = 0
    detail = []
    edits = []   # (start, end, replacement) —— 原始 xml 坐标系
    for m in re.finditer(r"<a:r>(?:(?!</a:r>).)*?</a:r>", xml, re.S):
        run = m.group(0)
        tm = re.search(r"<a:t(\s[^>]*)?>(.*?)</a:t>", run, re.S)
        if not tm:
            continue
        plain = unescape(tm.group(2))
        spans = formula_norm.find_spans(plain)
        if not spans:
            continue
        edits.append((m.start(), m.end(), inject_spans_into_run(run, plain, spans)))
        for (s, e, latex) in spans:
            detail.append((plain[s:e], latex))
        hits += len(spans)
    for (s, e, rep) in reversed(edits):
        xml = xml[:s] + rep + xml[e:]
    return xml, hits, detail


def patch_latex(xml):
    """把 run 里**已经是 LaTeX 源码**的 `$…$` 片段注入成 OMML。

    与 `patch_auto` 的区别：源已经规范化过（正文页写着 `$c = \frac{B^2L^2}{R}$`），
    不需要探测伪公式，直接把 `$…$` 里的 LaTeX 注入。

    🔴 偏移陷阱与 `patch_auto` 相同：所有偏移量在**原始** xml 上算，
       公式片段比原文字长 ⇒ 必须**从后往前**替换。
    """
    hits = 0
    detail = []
    edits = []
    for m in re.finditer(r"<a:r>(?:(?!</a:r>).)*?</a:r>", xml, re.S):
        run = m.group(0)
        tm = re.search(r"<a:t(\s[^>]*)?>(.*?)</a:t>", run, re.S)
        if not tm:
            continue
        plain = unescape(tm.group(2))
        spans = find_latex_spans(plain)
        if not spans:
            continue
        edits.append((m.start(), m.end(), inject_spans_into_run(run, plain, spans)))
        for (s, e, latex) in spans:
            detail.append((plain[s:e], latex))
        hits += len(spans)
    for (s, e, rep) in reversed(edits):
        xml = xml[:s] + rep + xml[e:]
    return xml, hits, detail


# ══════════════════════════════════════════════════════════════════
# 1.5 注入后的守卫：形状数与 XML 良构性
# ══════════════════════════════════════════════════════════════════
_SHAPE_TAGS = ("<p:sp>", "<p:pic>", "<p:graphicFrame>", "<p:cxnSp>", "<p:grpSp>")
_CNPR = re.compile(r'<p:cNvPr id="(\d+)" name="([^"]*)"')


def part_census(xml):
    """统计 part 里的形状与形状名，用于「注入前后必须一致」的校验。"""
    shapes = sum(xml.count(t) for t in _SHAPE_TAGS)
    ids = _CNPR.findall(xml)
    return {"shapes": shapes, "ids": [i for i, _ in ids], "names": [n for _, n in ids]}


def check_part_preserved(part, before, after):
    """校验注入没有破坏 part 结构；不通过就抛错，不让损坏文件落盘。

    为什么这道闸必须存在：PowerPoint 遇到不合法的形状结构会「修复」文件并
    **无声删掉整个形状**——不报错、不提示，用户只会发现内容凭空少了。
    """
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(after)
    except ET.ParseError as e:
        raise RuntimeError("注入后 XML 不合法（%s）：%s" % (part, e))
    b, a = part_census(before), part_census(after)
    if b["shapes"] != a["shapes"]:
        raise RuntimeError("注入后形状数变了（%s）：%d → %d"
                           % (part, b["shapes"], a["shapes"]))
    lost = set(b["ids"]) - set(a["ids"])
    if lost:
        raise RuntimeError("注入后丢了形状 id（%s）：%s" % (part, sorted(lost)))


# ══════════════════════════════════════════════════════════════════
# 4. 主流程
# ══════════════════════════════════════════════════════════════════
def scan_pptx(path):
    """列出所有 part 里的文本（用来写 spec）。"""
    out = []
    with zipfile.ZipFile(path) as z:
        for name in sorted(z.namelist()):
            if not (name.startswith("ppt/slides/slide") or name.startswith("ppt/notesSlides/")):
                continue
            if not name.endswith(".xml"):
                continue
            xml = z.read(name).decode("utf-8")
            for tm in re.finditer(r"<a:t(\s[^>]*)?>(.*?)</a:t>", xml, re.S):
                txt = unescape(tm.group(2)).strip()
                if txt:
                    out.append((name, txt))
    return out


def _scope_parts(parts, scope):
    """按 scope 选出要注入的 part 名。

    🔴 默认只处理**正文页**（`ppt/slides/`）：备注页必须与讲义 Markdown
       **逐字同源**，注入 OMML 后备注页抽出来的是 `m:t` 里的内容，
       与讲义里的 LaTeX 源码不是同一串字 ⇒ 同源判据必红。
    """
    out = []
    for name in sorted(parts):
        if not name.endswith(".xml"):
            continue
        is_slide = name.startswith("ppt/slides/slide")
        is_notes = name.startswith("ppt/notesSlides/notesSlide")
        if scope == "slides" and is_slide:
            out.append(name)
        elif scope == "notes" and is_notes:
            out.append(name)
        elif scope == "all" and (is_slide or is_notes):
            out.append(name)
    return out


def main():
    ap = argparse.ArgumentParser(description="把 LaTeX 公式注入 PPTX，生成原生可编辑公式（OMML）")
    ap.add_argument("pptx", nargs="?", help="输入 pptx")
    ap.add_argument("out", nargs="?", help="输出 pptx")
    ap.add_argument("--spec", help="注入规格（JSON）")
    ap.add_argument("--scan", action="store_true", help="只列出 part 里的文本")
    ap.add_argument("--dry-run", action="store_true", help="不写文件")
    ap.add_argument("--latex", action="store_true",
                    help="注入模式：把 run 里 $…$ 已经是 LaTeX 的片段注入成 OMML"
                         "（源已规范化时用这个）")
    ap.add_argument("--auto", action="store_true",
                    help="注入模式：自动探测伪公式并注入（源未规范化时用这个）")
    ap.add_argument("--scope", default="slides", choices=("slides", "notes", "all"),
                    help="处理哪些 part（默认 slides —— 备注页要保逐字同源，不注入）")
    args = ap.parse_args()

    if args.scan:
        if not args.pptx:
            raise SystemExit("需要 pptx 路径")
        for name, txt in scan_pptx(args.pptx):
            print("%-34s %s" % (name, txt[:110]))
        return 0

    bulk_mode = args.latex or args.auto
    if bulk_mode and not (args.pptx and args.out):
        raise SystemExit("用法：pptx_omml_inject.py <in.pptx> <out.pptx> --latex|--auto")

    if not bulk_mode and not (args.pptx and args.out and args.spec):
        raise SystemExit("用法：pptx_omml_inject.py <in.pptx> <out.pptx> --spec <spec.json>")

    spec = {}
    if args.spec:
        with open(args.spec, encoding="utf-8") as f:
            spec = json.load(f)

    with zipfile.ZipFile(args.pptx) as z:
        infos = z.infolist()
        parts = {i.filename: z.read(i.filename) for i in infos}

    total = 0
    failed = []

    if bulk_mode:
        for part in _scope_parts(parts, args.scope):
            original = parts[part].decode("utf-8")
            xml = patch_root(original)
            if args.latex:
                xml, hits, detail = patch_latex(xml)
                for (src, lat) in detail:
                    print("  %-34s latex %r → %s" % (part, src, lat))
            else:
                xml, hits, detail = patch_auto(xml)
                for (src, lat) in detail:
                    print("  %-34s auto  %r → %s" % (part, src, lat))
            if hits:
                check_part_preserved(part, original, xml)
                parts[part] = xml.encode("utf-8")
            total += hits
    else:
        for item in spec.get("parts", []):
            part = item["part"]
            if part not in parts:
                print("  ! part 不存在：%s" % part)
                continue
            original = parts[part].decode("utf-8")
            xml = patch_root(original)
            if item.get("auto"):
                xml, hits, detail = patch_auto(xml)
                for (src, lat) in detail:
                    print("  %-34s auto  %r → %s" % (part, src, lat))
                total += hits
            elif item.get("latex_spans"):
                xml, hits, detail = patch_latex(xml)
                for (src, lat) in detail:
                    print("  %-34s latex %r → %s" % (part, src, lat))
                total += hits
            else:
                target = item["target"]
                xml = patch_target(xml, target, item["latex"],
                                   item.get("prefix", ""), item.get("suffix", ""))
                print("  %-34s 替换  %r → %s" % (part, target, item["latex"]))
                total += 1
            check_part_preserved(part, original, xml)
            parts[part] = xml.encode("utf-8")

    if args.dry_run:
        print("dry-run：共 %d 处，未写文件" % total)
        return 0

    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as zo:
        for info in infos:
            zo.writestr(info, parts[info.filename])
    print("已写出 %s（%d 处公式）" % (args.out, total))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
