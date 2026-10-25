#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_pptx.py —— 纯标准库 PPTX 生成器（零第三方依赖）

为什么自己写
------------
本仓库此前把「幻灯片生成」外包给运行时内置的 `pptx` 技能。该技能**不随本仓库
分发** ⇒ 克隆本仓库后，这项能力就断了。这与本项目「能力必须随交付物走」的
部署原则冲突（同 ADW 论文线那次教训）。

所以这里自研一个**纯标准库**的 PPTX 生成器：输入一份幻灯片规格 JSON，
输出一个 PowerPoint 能直接打开、可继续编辑的 `.pptx` 文件。
只依赖 `json` / `zipfile` / `xml` 相关的标准库，不装任何第三方包。

    python build_pptx.py spec.json -o slides.pptx
    python build_pptx.py spec.json -o slides.pptx --check   # 生成后做结构自检

输入规格（spec）结构
--------------------
    {
      "meta": {"title": "课程标题", "author": "作者", "subject": "副标题"},
      "slides": [
        {
          "layout": "title",              # title|bullets|two-column|image-focus|quote|section|blank
          "title": "页标题",
          "subtitle": "副标题（title/section 布局用）",
          "bullets": [{"text": "要点", "level": 0}],
          "notes": "讲授者备注 / 讲稿",
          "footer": "数据来源标注",
          "image": "assets/fig1.png",     # 相对 spec 文件所在目录
          "caption": "图注"
        }
      ]
    }

坐标系
------
OOXML 用 EMU（English Metric Unit）。1 英寸 = 914400 EMU，1 磅 = 12700 EMU。
本脚本固定 16:9 版面：12192000 × 6858000 EMU（13.333in × 7.5in）。

技术约束
--------
* Python 3.9 兼容（用 `from __future__ import annotations`，不使用 3.10+ 语法）
* 纯标准库，不写死任何机器绝对路径
* UTF-8 无 BOM，LF 换行
* 退出码：0 成功 / 1 参数或规格错误 / 2 输出校验失败
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile

# 版式几何与文字度量在 slide_layouts.py 里（**唯一一份**）——
# 渲染器按它画，判据（slide_spec_lint.py）按它量，两边不会漂移。
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import slide_layouts as L  # noqa: E402

# ---------------------------------------------------------------- 版面常量

EMU_PER_PT = 12700
EMU_PER_IN = 914400

SLIDE_W = int(L.CANVAS["w"] * EMU_PER_PT)       # 16:9 宽
SLIDE_H = int(L.CANVAS["h"] * EMU_PER_PT)       # 16:9 高

MARGIN = int(L.CANVAS["margin"] * EMU_PER_PT)   # 外边距
CONTENT_W = SLIDE_W - 2 * MARGIN

# 字号（磅）
SZ_TITLE = L.SIZES["title"]
SZ_TITLE_CENTER = L.SIZES["title_center"]
SZ_SUBTITLE = L.SIZES["subtitle"]
SZ_BODY = L.SIZES["body"]
SZ_BODY_L2 = L.SIZES["body_l2"]
SZ_QUOTE = L.SIZES["quote"]
SZ_FOOTER = L.SIZES["footer"]

# 颜色
C_INK = L.COLORS["ink"]
C_MUTED = L.COLORS["muted"]
C_ACCENT = L.COLORS["accent"]
C_RULE = L.COLORS["rule"]
C_PAPER = L.COLORS["paper"]

COLOR_MAP = {"ink": C_INK, "muted": C_MUTED, "accent": C_ACCENT}


def resolve_color(c, default=None):
    """颜色可以是**令牌名**（"ink" / "body" / "muted"）也可以是**字面色值**（"1E3A8A"）。

    🔴 两种写法都必须支持：版式表用令牌名（语义），多色强调体系用字面色值（轮转）。
       早先只有令牌名，于是每页都是同一个强调色 —— 参考课件那种「每张卡一个颜色」
       的做法就做不出来。
    """
    if c is None:
        return default if default is not None else C_INK
    s = str(c).strip()
    if not s:
        return default if default is not None else C_INK
    if s in L.COLORS:
        return L.COLORS[s]
    if s in COLOR_MAP:
        return COLOR_MAP[s]
    if len(s) == 6 and all(ch in "0123456789ABCDEFabcdef" for ch in s):
        return s.upper()
    return default if default is not None else C_INK

LAYOUTS = L.LAYOUTS

# 关系的固定类型串
RT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
# 🔴 **包级**关系（core-properties）用的是 package 命名空间，不是 officeDocument。
#    曾经把它也拼成 officeDocument ⇒ 核心属性部件在关系图里"类型不对"，
#    严格校验器会判非法（PowerPoint 恰好容忍，但不该依赖它的宽容）。
RT_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "application/vnd.openxmlformats-officedocument.presentationml"
# 🔴 主题部件的 content type 是 `application/vnd.openxmlformats-officedocument.theme+xml`
#    —— **没有 `.drawingml` 这一段**。
#    曾经写成 `...officedocument.drawingml.theme+xml` ⇒ PowerPoint 按 content type
#    装载主题时认不出来 ⇒ 母版的主题断链 ⇒ **打开时直接拒绝（HRESULT E_FAIL）**。
#    注意：content type 写错时，**只换主题部件的内容是修不好的**，
#    必须连 [Content_Types].xml 里的声明一起对。
CT_THEME = "application/vnd.openxmlformats-officedocument.theme+xml"


class SpecError(Exception):
    """规格错误（可预期的用户输入问题）——退出码 1。"""


class CheckFailed(Exception):
    """产物结构自检失败——退出码 2。"""


# ---------------------------------------------------------------- 基础工具

def esc(s):
    """XML 文本转义。"""
    if s is None:
        s = ""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def pt(v):
    """磅 → EMU。"""
    return int(round(v * EMU_PER_PT))


def read_text(p):
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write_text(p, text):
    if not isinstance(text, str):
        raise TypeError("write_text 只接受 str，收到 %r" % type(text).__name__)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def rel(rid, rtype, target, mode=None):
    """一条关系。

    `rtype` 不含命名空间时按 **officeDocument** 命名空间拼；
    以 `pkg:` 开头的是**包级**关系（core-properties），用 package 命名空间。
    """
    extra = ' TargetMode="External"' if mode == "External" else ""
    if rtype.startswith("pkg:"):
        base = RT_PKG
        rtype = rtype[4:]
    else:
        base = RT
    return '<Relationship Id="%s" Type="%s/%s" Target="%s"%s/>' % (rid, base, rtype, target, extra)


# ---------------------------------------------------------------- 规格读取

def load_spec(path):
    """读并校验幻灯片规格。规格里的**事实性内容**（标题、要点、来源）由调用方负责，
    本脚本只做结构校验与排版，不生成、不改写、不杜撰任何内容。"""
    if not os.path.isfile(path):
        raise SpecError("找不到规格文件：%s" % path)
    try:
        raw = json.loads(read_text(path))
    except ValueError as e:
        raise SpecError("规格文件不是合法 JSON：%s（%s）" % (path, e))
    if not isinstance(raw, dict):
        raise SpecError("规格根节点必须是对象")
    slides = raw.get("slides")
    if not isinstance(slides, list) or not slides:
        raise SpecError("规格缺少非空的 slides 数组")
    meta = raw.get("meta") or {}
    if not isinstance(meta, dict):
        raise SpecError("meta 必须是对象")
    for i, s in enumerate(slides):
        if not isinstance(s, dict):
            raise SpecError("slides[%d] 必须是对象" % i)
        lay = s.get("layout", "bullets")
        if lay not in LAYOUTS:
            raise SpecError("slides[%d].layout = %r 不在允许值 %s 内"
                            % (i, lay, "/".join(LAYOUTS)))
        bl = s.get("bullets")
        if bl is not None and not isinstance(bl, list):
            raise SpecError("slides[%d].bullets 必须是数组" % i)
        for j, b in enumerate(bl or []):
            if isinstance(b, str):
                continue
            if not isinstance(b, dict) or "text" not in b:
                raise SpecError("slides[%d].bullets[%d] 必须是字符串或含 text 的对象" % (i, j))
    return raw


# ---------------------------------------------------------------- 形状构造

def run_props(sz, bold=False, color=C_INK):
    """一段文字的 <a:rPr> 属性串。

    🔴 `sz` 的单位是**百分之一磅**（OOXML `ST_TextFontSize`，schema 下限 100）。
       本模块内部一律用**磅**（与 `slide_layouts.SIZES` 一致），写进 XML 时 ×100。
       曾经直接写磅值（44 ⇒ sz="44"）⇒ 违反 schema 下限 ⇒
       **PowerPoint 打开时直接拒绝（HRESULT E_FAIL），不是提示修复**。
       见 docs 参考：本仓库的 PPTX 产物曾长期打不开，根因就是这一处单位。
    """
    return ('<a:rPr lang="zh-CN" altLang="en-US" sz="%d" b="%d" dirty="0">'
            '<a:solidFill><a:srgbClr val="%s"/></a:solidFill>'
            '<a:latin typeface="Arial"/><a:ea typeface="Microsoft YaHei"/>'
            '<a:cs typeface="Arial"/></a:rPr>'
            % (int(round(sz * 100)), 1 if bold else 0, color))


def _ppr(algn="l", level=0, bullet=True, spc_before=0, bullet_color=None,
         color=C_INK):
    """构造 `<a:pPr>`。

    `spc_before` 的单位是**百分之一磅**（OOXML `a:spcPts` 的单位）。
    🔴 它是 `<a:pPr>` 的**子元素**，且按 schema 顺序必须排在
       `buClr` / `buFont` / `buChar` **之前**。
       曾经把它当成 `<a:rPr>` 的**属性**拼进去（` spcBef><a:spcPts .../>`），
       那个位置既不是合法属性也不是合法子元素 ⇒ 一旦命中就是 schema 违规。
    """
    ppr = '<a:pPr algn="%s"' % algn
    if level:
        ppr += ' marL="%d" indent="%d"' % (pt(28 * level), -pt(14))
    else:
        ppr += ' marL="%d" indent="%d"' % (pt(24), -pt(24))
    ppr += ">"
    if spc_before:
        ppr += '<a:spcBef><a:spcPts val="%d"/></a:spcBef>' % int(round(spc_before))
    if bullet:
        ch = "•" if level == 0 else "–"
        ppr += ('<a:buClr><a:srgbClr val="%s"/></a:buClr><a:buFont typeface="Arial"/>'
                '<a:buChar char="%s"/>'
                % (resolve_color(bullet_color, color), esc(ch)))
    else:
        ppr += "<a:buNone/>"
    ppr += "</a:pPr>"
    return ppr


def paragraph(text, sz=SZ_BODY, bold=False, color=C_INK, algn="l",
              level=0, bullet=True, spc_before=0, indent=0, bullet_color=None):
    """构造一个 <a:p>。level > 0 时用缩进+短横线项目符号。"""
    ppr = _ppr(algn, level, bullet, spc_before, bullet_color, color)

    # 支持行内换行：文本里的 \n 拆成多个 <a:br/>
    chunks = str(text).split("\n")
    runs = []
    for k, c in enumerate(chunks):
        if k:
            runs.append("<a:br>%s</a:br>" % run_props(sz, bold, color))
        runs.append("<a:r>%s<a:t>%s</a:t></a:r>" % (run_props(sz, bold, color), esc(c)))
    return "<a:p>%s%s</a:p>" % (ppr, "".join(runs))


def paragraph_runs(runs, sz=SZ_BODY, algn="l", level=0, bullet=False,
                   spc_before=0):
    """构造一个**一段内混排粗细/颜色**的 <a:p>。

    用在哪：页脚是「**依据**：《…》「…」」这种**标签串** ——
    粗体前缀 + 灰色正文必须**在同一行**里，靠两个文本框排不出来。
    """
    ppr = _ppr(algn, level, bullet, spc_before, None, C_INK)
    body = []
    for r in runs or []:
        t = str(r.get("text", ""))
        if not t:
            continue
        body.append("<a:r>%s<a:t>%s</a:t></a:r>"
                    % (run_props(int(r.get("sz") or sz), bool(r.get("bold")),
                                 resolve_color(r.get("color"), C_INK)),
                       esc(t)))
    if not body:
        body.append('<a:endParaRPr lang="zh-CN"/>')
    return "<a:p>%s%s</a:p>" % (ppr, "".join(body))


def textbox(shape_id, name, x, y, cx, cy, paras, anchor="t", wrap=True):
    """一个带文字的矩形形状。"""
    if not paras:
        paras = [paragraph("", bullet=False)]
    body = ('<p:sp><p:nvSpPr><p:cNvPr id="%d" name="%s"/>'
            '<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            '<a:noFill/></p:spPr>'
            '<p:txBody><a:bodyPr wrap="%s" lIns="0" tIns="0" rIns="0" bIns="0" anchor="%s">'
            '<a:normAutofit/></a:bodyPr><a:lstStyle/>%s</p:txBody></p:sp>'
            % (shape_id, esc(name), x, y, cx, cy,
               "square" if wrap else "none", anchor, "".join(paras)))
    return body


def picture(shape_id, name, rid, x, y, cx, cy):
    return ('<p:pic><p:nvPicPr><p:cNvPr id="%d" name="%s"/>'
            '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            '<p:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            '<p:spPr><a:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
            % (shape_id, esc(name), rid, x, y, cx, cy))


def rule(shape_id, x, y, cx, color=C_RULE, h=12700):
    """一条水平分隔线。"""
    return ('<p:sp><p:nvSpPr><p:cNvPr id="%d" name="Rule %d"/>'
            '<p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            '<a:solidFill><a:srgbClr val="%s"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>'
            '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="zh-CN"/></a:p></p:txBody></p:sp>'
            % (shape_id, shape_id, x, y, cx, h, resolve_color(color, C_RULE)))


def rect(shape_id, name, x, y, cx, cy, color):
    """一个实心色块（卡片底 / 强调条 / 角标底）。

    🔴 几何用**点**（pt），写 XML 时换算成 EMU；与本模块其它图元同一坐标系。
       参考课件的卡片与角标都是**直角矩形**（不是圆角），
       这里保持一致 —— 学界课件的视觉语言偏方正。
    """
    return ('<p:sp><p:nvSpPr><p:cNvPr id="%d" name="%s"/>'
            '<p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            '<a:solidFill><a:srgbClr val="%s"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>'
            '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="zh-CN"/></a:p></p:txBody></p:sp>'
            % (shape_id, esc(name), x, y, cx, cy, resolve_color(color)))


def ellipse(shape_id, name, x, y, cx, cy, color):
    """一个实心椭圆（圆形编号徽章）。

    🔴 用 `prst="ellipse"` 而不是圆角矩形 —— 参考课件的编号徽章是**正圆**，
       方角徽章一眼就能看出不是同一套视觉语言。
    """
    return ('<p:sp><p:nvSpPr><p:cNvPr id="%d" name="%s"/>'
            '<p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom>'
            '<a:solidFill><a:srgbClr val="%s"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>'
            '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="zh-CN"/></a:p></p:txBody></p:sp>'
            % (shape_id, esc(name), x, y, cx, cy, resolve_color(color)))


# ---------------------------------------------------------------- 幻灯片排版

def _para(p):
    """槽位里的段落规格 → 段落 XML。

    `spc_before` 在版式表里是**磅**（度量用），这里换算成 OOXML 用的
    百分之一磅（`spcPts`）。
    """
    if p.get("runs"):
        # 一段内混排粗细/颜色（页脚标签串）
        return paragraph_runs(p["runs"], sz=p.get("sz", SZ_BODY),
                              algn=p.get("align", "l"),
                              level=int(p.get("level", 0)),
                              bullet=p.get("bullet", False),
                              spc_before=int(round(float(p.get("spc_before") or 0) * 100)))
    return paragraph(p.get("text", ""), sz=p.get("sz", SZ_BODY),
                     bold=p.get("bold", False),
                     color=resolve_color(p.get("color"), C_INK),
                     algn=p.get("align", "l"),
                     level=int(p.get("level", 0)),
                     bullet=p.get("bullet", True),
                     spc_before=int(round(float(p.get("spc_before") or 0) * 100)),
                     bullet_color=resolve_color(p.get("bullet_color"),
                                                p.get("color")))


def render_slide(sld, idx, media, image_rels, base_dir):
    """把一页规格渲染成 slide XML。media/image_rels 用于登记图片关系。

    🔴 **几何与文字内容都来自 `slide_layouts.slots_for()`**：
       渲染器按它画，判据（`slide_spec_lint.py`）按它量文字会不会溢出。
       两边共用同一份槽位表 ⇒ 判据说的和画出来的一定是同一件事。
       （两份几何各算一套 ⇒ 判据会与渲染器漂移，那种判据没有价值。）
    """
    sid = 2
    shapes = []

    for slot in L.slots_for(sld):
        kind = slot.get("kind")
        if kind == "text":
            paras = [_para(p) for p in slot.get("paras") or []]
            shapes.append(textbox(sid, slot["name"], pt(slot["x"]), pt(slot["y"]),
                                  pt(slot["w"]), pt(slot["h"]), paras,
                                  anchor=slot.get("anchor", "t"),
                                  wrap=slot.get("wrap", True)))
            sid += 1
        elif kind == "rule":
            shapes.append(rule(sid, pt(slot["x"]), pt(slot["y"]), pt(slot["w"]),
                               color=slot.get("color", C_RULE),
                               h=pt(slot.get("h", 1.0))))
            sid += 1
        elif kind == "rect":
            shapes.append(rect(sid, slot["name"], pt(slot["x"]), pt(slot["y"]),
                               pt(slot["w"]), pt(slot["h"]),
                               slot.get("color", C_PAPER)))
            sid += 1
        elif kind == "ellipse":
            shapes.append(ellipse(sid, slot["name"], pt(slot["x"]), pt(slot["y"]),
                                  pt(slot["w"]), pt(slot["h"]),
                                  slot.get("color", C_ACCENT)))
            sid += 1
        elif kind == "picture":
            rid = _register_image(image_rels, slot.get("src", ""), media, base_dir)
            shapes.append(picture(sid, "Picture", rid, pt(slot["x"]), pt(slot["y"]),
                                  pt(slot["w"]), pt(slot["h"])))
            sid += 1

    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
           'xmlns:r="%s" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
           '<p:cSld><p:spTree>'
           '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
           '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
           '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
           '%s</p:spTree></p:cSld>'
           '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
           % (RT, "".join(shapes)))
    return xml


def _bullets_paras(bullets):
    """项目符号数组 → 段落 XML 列表。

    ⚠️ 已由 `slide_layouts` 的槽位规格取代，保留仅为兼容外部调用。
    """
    paras = []
    for b in bullets:
        if isinstance(b, str):
            text, level = b, 0
        else:
            text, level = b.get("text", ""), int(b.get("level", 0))
        sz = SZ_BODY if level == 0 else SZ_BODY_L2
        paras.append(paragraph(text, sz=sz, level=level, spc_before=600 if level == 0 else 0))
    return paras or [paragraph("", bullet=False)]


def _register_image(image_rels, image, media, base_dir):
    """登记一张图片，返回 r:embed 的关系 Id。图片被登记进 media/ 并复制到包内。

    🔴 相对路径必须**相对 spec 文件所在目录**解析，不是相对当前工作目录 ——
       否则换一个目录跑脚本，同一份 spec 就会报「找不到图片」。
    """
    src = image
    if not os.path.isabs(src):
        src = os.path.join(base_dir, src)
    src = os.path.normpath(src)
    if not os.path.isfile(src):
        raise SpecError("找不到图片：%s（按 spec 所在目录解析为 %s）" % (image, src))
    ext = os.path.splitext(src)[1].lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
        raise SpecError("不支持的图片格式：%s（支持 png/jpg/jpeg/gif/bmp）" % ext)
    key = os.path.normcase(os.path.abspath(src))
    if key in image_rels:
        return image_rels[key][0]
    n = len(image_rels) + 1
    rid = "rIdImg%d" % n
    name = "image%d%s" % (n, ext)
    media[name] = src
    image_rels[key] = (rid, name)
    return rid


# ---------------------------------------------------------------- 静态部件

def content_types(n_slides, n_notes, images):
    ov = [
        '<Override PartName="/ppt/presentation.xml" ContentType="%s.presentation.main+xml"/>' % CT,
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="%s.slideMaster+xml"/>' % CT,
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="%s.slideLayout+xml"/>' % CT,
        '<Override PartName="/ppt/notesMasters/notesMaster1.xml" ContentType="%s.notesMaster+xml"/>' % CT,
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="%s"/>' % CT_THEME,
        '<Override PartName="/ppt/theme/theme2.xml" ContentType="%s"/>' % CT_THEME,
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for i in range(1, n_slides + 1):
        ov.append('<Override PartName="/ppt/slides/slide%d.xml" ContentType="%s.slide+xml"/>' % (i, CT))
    for i in range(1, n_notes + 1):
        ov.append('<Override PartName="/ppt/notesSlides/notesSlide%d.xml" ContentType="%s.notesSlide+xml"/>' % (i, CT))
    defaults = [
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
    ]
    exts = set(os.path.splitext(p)[1].lower().lstrip(".") for p in images)
    for e in sorted(exts):
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "gif": "image/gif", "bmp": "image/bmp"}.get(e, "application/octet-stream")
        defaults.append('<Default Extension="%s" ContentType="%s"/>' % (e, mime))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '%s%s</Types>' % ("".join(defaults), "".join(ov)))


ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    + rel("rId1", "officeDocument", "ppt/presentation.xml") +
    rel("rId2", "pkg:metadata/core-properties", "docProps/core.xml",
        ) +
    rel("rId3", "extended-properties", "docProps/app.xml") +
    '</Relationships>')

THEME = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="JFA">
<a:themeElements>
<a:clrScheme name="JFA"><a:dk1><a:srgbClr val="1F2933"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
<a:dk2><a:srgbClr val="1B4965"/></a:dk2><a:lt2><a:srgbClr val="F4F6F8"/></a:lt2>
<a:accent1><a:srgbClr val="1B4965"/></a:accent1><a:accent2><a:srgbClr val="5A6570"/></a:accent2>
<a:accent3><a:srgbClr val="2F6F8F"/></a:accent3><a:accent4><a:srgbClr val="6B8E9E"/></a:accent4>
<a:accent5><a:srgbClr val="8FA9B5"/></a:accent5><a:accent6><a:srgbClr val="A8BDC6"/></a:accent6>
<a:hlink><a:srgbClr val="1B4965"/></a:hlink><a:folHlink><a:srgbClr val="5A6570"/></a:folHlink></a:clrScheme>
<a:fontScheme name="JFA">
<a:majorFont><a:latin typeface="Arial"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface=""/></a:majorFont>
<a:minorFont><a:latin typeface="Arial"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface=""/></a:minorFont></a:fontScheme>
<a:fmtScheme name="JFA">
<a:fillStyleLst>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
<a:lnStyleLst>
<a:ln w="6350" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>
<a:ln w="12700" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>
<a:ln w="19050" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln></a:lnStyleLst>
<a:effectStyleLst>
<a:effectStyle><a:effectLst/></a:effectStyle>
<a:effectStyle><a:effectLst/></a:effectStyle>
<a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
<a:bgFillStyleLst>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
</a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>'''

SLIDE_MASTER = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="%s" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="%s"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree></p:cSld>
<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>''' % (RT, C_PAPER)

SLIDE_LAYOUT = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="%s" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
<p:cSld name="空白"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree></p:cSld>
<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>''' % RT

NOTES_MASTER = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:notesMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="%s" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image Placeholder 1"/>
<p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr>
<p:nvPr><p:ph type="sldImg"/></p:nvPr></p:nvSpPr>
<p:spPr/></p:sp>
<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/>
<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr>
<p:spPr/></p:sp>
</p:spTree></p:cSld>
<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
<p:notesStyle/>
</p:notesMaster>''' % RT

APP_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Template></Template><Company></Company><Slides>%d</Slides><PresentationFormat>On-screen Show (16:9)</PresentationFormat><Application>junior-faculty-agent build_pptx.py</Application><AppVersion>16.0000</AppVersion>
</Properties>'''


# ---------------------------------------------------------------- 主流程

def build(spec, out_path, base_dir):
    """生成 pptx。返回 (n_slides, n_notes, warnings)。"""
    slides = spec["slides"]
    media = {}
    image_rels = {}
    slide_xmls = []
    notes_specs = []

    for sld in slides:
        slide_xmls.append(render_slide(sld, len(slide_xmls) + 1, media, image_rels, base_dir))
        if str(sld.get("notes", "")).strip():
            notes_specs.append((len(slide_xmls), sld.get("notes", "")))

    n_slides = len(slide_xmls)
    n_notes = len(notes_specs)

    # presentation.xml + 它的关系表
    # 🔴 `sldIdLst` 的 r:id 必须与 `presentation.xml.rels` 里的 slide 关系**一一对应且同序**。
    #    曾经这里错位一格（列表用 rId2..、rels 用 rId1..），结果是 PowerPoint 能打开、
    #    但页序整体错位且首屏空白 —— 结构自检当时没报，因为"关系都声明了"。
    sld_ids = "".join('<p:sldId id="%d" r:id="rId%d"/>' % (255 + i, i)
                       for i in range(1, n_slides + 1))
    pres = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="%s" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
            'saveSubsetFonts="1">'
            '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId%d"/></p:sldMasterIdLst>'
            '<p:notesMasterIdLst><p:notesMasterId r:id="rId%d"/></p:notesMasterIdLst>'
            '<p:sldIdLst>%s</p:sldIdLst>'
            '<p:sldSz cx="%d" cy="%d"/><p:notesSz cx="6858000" cy="9144000"/>'
            '</p:presentation>'
            % (RT, n_slides + 1, n_slides + 2, sld_ids, SLIDE_W, SLIDE_H))

    pres_rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for i in range(1, n_slides + 1):
        pres_rels.append(rel("rId%d" % i, "slide", "slides/slide%d.xml" % i))
    pres_rels.append(rel("rId%d" % (n_slides + 1), "slideMaster", "slideMasters/slideMaster1.xml"))
    pres_rels.append(rel("rId%d" % (n_slides + 2), "notesMaster", "notesMasters/notesMaster1.xml"))
    pres_rels.append(rel("rId%d" % (n_slides + 3), "theme", "theme/theme1.xml"))
    pres_rels.append("</Relationships>")

    # notesSlide 指向它对应的那一页（rId2）以及 notesMaster（rId1）
    notes_for = {}
    for slide_no, text in notes_specs:
        notes_for[slide_no] = text
    note_rels = {}
    if notes_for:
        for i, slide_no in enumerate(sorted(notes_for), start=1):
            note_rels[slide_no] = i

    parts = {}

    parts["[Content_Types].xml"] = content_types(n_slides, n_notes, list(media.values()))
    parts["_rels/.rels"] = ROOT_RELS
    parts["docProps/app.xml"] = APP_XML % n_slides
    parts["docProps/core.xml"] = core_xml(spec.get("meta") or {})
    parts["ppt/presentation.xml"] = pres
    parts["ppt/_rels/presentation.xml.rels"] = "".join(pres_rels)
    parts["ppt/theme/theme1.xml"] = THEME
    parts["ppt/theme/theme2.xml"] = THEME
    parts["ppt/slideMasters/slideMaster1.xml"] = SLIDE_MASTER
    parts["ppt/slideMasters/_rels/slideMaster1.xml.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + rel("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml")
        + rel("rId2", "theme", "../theme/theme1.xml")
        + '</Relationships>')
    parts["ppt/slideLayouts/slideLayout1.xml"] = SLIDE_LAYOUT
    parts["ppt/slideLayouts/_rels/slideLayout1.xml.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + rel("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")
        + '</Relationships>')
    parts["ppt/notesMasters/notesMaster1.xml"] = NOTES_MASTER
    parts["ppt/notesMasters/_rels/notesMaster1.xml.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + rel("rId1", "theme", "../theme/theme2.xml")
        + '</Relationships>')

    for i, xml in enumerate(slide_xmls, start=1):
        parts["ppt/slides/slide%d.xml" % i] = xml
        # 该页用到的图片关系
        used = _slide_image_rids(xml, image_rels)
        rr = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
              '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
              rel("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml")]
        for rid, name in used:
            rr.append(rel(rid, "image", "../media/%s" % name))
        # 🔴 讲稿备注是靠 **页面 → notesSlide** 这条关系挂上去的。
        #    只写 notesSlide 部件而漏了这条关系，文件照样能打开、备注却静默不显示。
        if i in note_rels:
            rr.append(rel("rIdNotes", "notesSlide",
                          "../notesSlides/notesSlide%d.xml" % note_rels[i]))
        rr.append("</Relationships>")
        parts["ppt/slides/_rels/slide%d.xml.rels" % i] = "".join(rr)

    for slide_no, text in sorted(notes_for.items()):
        ni = note_rels[slide_no]
        paras = [paragraph(p, sz=12, bullet=False) for p in str(text).split("\n")]
        notes_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                     '<p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                     'xmlns:r="%s" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
                     '<p:cSld><p:spTree>'
                     '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
                     '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
                     '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
                     '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image Placeholder 1"/>'
                     '<p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr>'
                     '<p:nvPr><p:ph type="sldImg"/></p:nvPr></p:nvSpPr><p:spPr/></p:sp>'
                     '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/>'
                     '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
                     '<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr>'
                     '<p:spPr/>'
                     '<p:txBody><a:bodyPr/><a:lstStyle/>%s</p:txBody></p:sp>'
                     '</p:spTree></p:cSld>'
                     '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>'
                     % (RT, "".join(paras)))
        parts["ppt/notesSlides/notesSlide%d.xml" % ni] = notes_xml
        parts["ppt/notesSlides/_rels/notesSlide%d.xml.rels" % ni] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + rel("rId1", "notesMaster", "../notesMasters/notesMaster1.xml")
            + rel("rId2", "slide", "../slides/slide%d.xml" % slide_no)
            + '</Relationships>')

    # 写 zip
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        # [Content_Types].xml 必须是包里的第一个条目
        z.writestr("[Content_Types].xml", parts.pop("[Content_Types].xml"))
        for name in sorted(parts):
            z.writestr(name, parts[name])
        for name, src in sorted(media.items()):
            with open(src, "rb") as f:
                z.writestr("ppt/media/%s" % name, f.read())

    warnings = []
    for i, sld in enumerate(slides, start=1):
        if sld.get("layout") == "image-focus" and not sld.get("image"):
            warnings.append("第 %d 页用了 image-focus 布局但没有 image 字段" % i)
        # 文字装不下 ⇒ PowerPoint 自动缩字（静默失效，产物上看不出来）
        for ov in L.overflow(sld):
            warnings.append("第 %d 页 %s 槽位文字装不下：需要约 %d pt，框高 %d pt"
                            "（PowerPoint 会自动缩小字号）"
                            % (i, ov["slot"], int(ov["need"] + 0.5),
                               int(ov["have"])))
    return n_slides, n_notes, warnings


def core_xml(meta):
    title = esc(meta.get("title", ""))
    creator = esc(meta.get("author", ""))
    subject = esc(meta.get("subject", ""))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>%s</dc:title><dc:subject>%s</dc:subject><dc:creator>%s</dc:creator>'
            '<cp:lastModifiedBy>%s</cp:lastModifiedBy>'
            '</cp:coreProperties>' % (title, subject, creator, creator))


def _slide_image_rids(slide_xml, image_rels):
    """这页用到的图片关系 [(rid, name)]，按出现顺序。"""
    out = []
    for key, (rid, name) in image_rels.items():
        if ('r:embed="%s"' % rid) in slide_xml:
            out.append((rid, name))
    return out


# ---------------------------------------------------------------- 结构自检

def check_pptx(path):
    """产物结构自检：部件齐全、XML 可解析、关系引用闭合、幻灯片数一致。

    这一步不是形式主义：OOXML 包里**任何一个 rels 引用悬空**或**缺一个部件**，
    PowerPoint 打开时都会报「需要修复」。宁可在这里红掉。
    """
    problems = []
    if not os.path.isfile(path):
        return ["产物不存在：%s" % path]
    import re
    import xml.etree.ElementTree as ET
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        return ["不是合法的 zip：%s" % e]
    with z:
        names = set(z.namelist())
        if "[Content_Types].xml" not in names:
            problems.append("缺少 [Content_Types].xml")
        if z.namelist()[0] != "[Content_Types].xml":
            problems.append("[Content_Types].xml 不是包内第一个条目")

        # XML 全部可解析
        import xml.etree.ElementTree as ET
        for n in sorted(names):
            if n.endswith(".xml") or n.endswith(".rels"):
                try:
                    ET.fromstring(z.read(n))
                except Exception as e:
                    problems.append("XML 解析失败 %s：%s" % (n, e))

        # 幻灯片/备注数与 presentation 一致
        n_slides = len([n for n in names if n.startswith("ppt/slides/slide")
                        and n.endswith(".xml")])
        n_notes = len([n for n in names if n.startswith("ppt/notesSlides/notesSlide")
                       and n.endswith(".xml")])
        if "ppt/presentation.xml" in names:
            pres = z.read("ppt/presentation.xml").decode("utf-8")
            ids = pres.count("<p:sldId ")
            if ids != n_slides:
                problems.append("presentation.xml 列出 %d 页，实际 %d 页" % (ids, n_slides))
            # 🔴 页序必须与部件编号一一对应。PowerPoint 会照着 sldIdLst 的顺序取页，
            #    这里错位一格的话：文件照样能打开，但页序整体错乱 —— 比打不开更难发现。
            if "ppt/_rels/presentation.xml.rels" in names:
                rmap = {}
                try:
                    rroot = ET.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
                    for r in rroot:
                        rmap[r.get("Id")] = r.get("Target")
                except Exception:
                    rmap = {}
                order = re.findall(r'<p:sldId[^>]*r:id="([^"]+)"', pres)
                for k, rid in enumerate(order, start=1):
                    tgt = rmap.get(rid)
                    if tgt is None:
                        problems.append("sldIdLst 第 %d 项的 %s 未在 rels 中声明" % (k, rid))
                    elif tgt != "slides/slide%d.xml" % k:
                        problems.append("页序错位：第 %d 项 %s 指向 %s（应为 slides/slide%d.xml）"
                                        % (k, rid, tgt, k))

        # 关系引用闭合：每个 r:id 都要有对应 Relationship
        for part in sorted(n for n in names if n.endswith(".rels")):
            base = os.path.dirname(os.path.dirname(part))
            try:
                root = ET.fromstring(z.read(part))
            except Exception:
                continue
            declared = set()
            for r in root:
                declared.add(r.get("Id"))
            src = part.replace("_rels/", "").replace(".rels", "")
            if src in names:
                blob = z.read(src).decode("utf-8", "replace")
                import re as _re
                for rid in set(_re.findall(r'r:(?:id|embed)="([^"]+)"', blob)):
                    if rid not in declared:
                        problems.append("%s 引用了未声明的关系 %s" % (src, rid))
            # 每个非 External 的 Target 必须存在
            for r in root:
                if r.get("TargetMode") == "External":
                    continue
                tgt = r.get("Target")
                resolved = os.path.normpath(os.path.join(base, tgt)).replace("\\", "/")
                if resolved not in names:
                    problems.append("%s 指向不存在的部件 %s" % (part, resolved))

        # 每页 slide 都要有 rels
        for i in range(1, n_slides + 1):
            if "ppt/slides/_rels/slide%d.xml.rels" % i not in names:
                problems.append("缺 ppt/slides/_rels/slide%d.xml.rels" % i)

        # 🔴 每个 notesSlide 部件都必须被某页的 rels 引用，且该页 rels 必须指回它。
        #    漏挂关系 = 备注静默不显示（文件能开、页数对，PowerPoint 里却是空的）。
        for i in range(1, n_notes + 1):
            part = "ppt/notesSlides/notesSlide%d.xml" % i
            if part not in names:
                continue
            owner = None
            for k in range(1, n_slides + 1):
                rp = "ppt/slides/_rels/slide%d.xml.rels" % k
                if rp in names and ("notesSlide%d.xml" % i) in z.read(rp).decode("utf-8", "replace"):
                    owner = k
                    break
            if owner is None:
                problems.append("notesSlide%d.xml 没有被任何页面的 rels 引用（备注不会显示）" % i)
        # 🔴 字号单位检查：**OOXML 的 `sz` 是百分之一磅，schema 下限 100**。
        #    曾经把磅值直接写进去（sz="44"），PowerPoint 打开时直接 E_FAIL ——
        #    而当时的关系闭合自检全绿 ⇒ 靠"关系闭合"抓不到这类错。
        #    这条检查把"单位"变成机械判据：所有 sz 必须是 100 的整数倍且 ≥ 100。
        import re as _re2
        for part in sorted(n for n in names
                           if n.startswith("ppt/slides/slide") or n.startswith("ppt/notesSlides/notesSlide")):
            if not part.endswith(".xml"):
                continue
            blob = z.read(part).decode("utf-8", "replace")
            for m in _re2.finditer(r'sz="(\d+)"', blob):
                v = int(m.group(1))
                if v < 100:
                    problems.append("%s 的字号 sz=%d 小于 schema 下限 100"
                                    "（OOXML 用百分之一磅，本模块内部用磅，×100 才对）"
                                    % (part, v))
                elif v % 100 != 0:
                    problems.append("%s 的字号 sz=%d 不是 100 的整数倍（应为整磅）"
                                    % (part, v))
            # spcBef 只能是 a:pPr 的子元素，不能出现在 a:rPr 的属性位置
            for m in _re2.finditer(r'<a:rPr[^>]*\sspcBef', blob):
                problems.append("%s 把 spcBef 写进了 a:rPr 的属性位置"
                                "（它只能是 a:pPr 的子元素）" % part)

        # 🔴 content type 检查：按部件路径**机械推导**应有的 content type，
        #    再与 [Content_Types].xml 的实际声明比对。
        #    写错的代价是致命的：PowerPoint 按 content type 装载部件，认不出来就
        #    **直接拒开**（实测主题写成 `...officedocument.drawingml.theme+xml`
        #    ⇒ HRESULT E_FAIL）。而这类错**只换部件内容是修不好的**，
        #    必须连声明一起对 —— 所以判据必须落在"声明"上。
        def expected_ct(part):
            p = part.lstrip("/")
            if p == "ppt/presentation.xml":
                return CT + ".presentation.main+xml"
            if p.startswith("ppt/slideMasters/"):
                return CT + ".slideMaster+xml"
            if p.startswith("ppt/slideLayouts/"):
                return CT + ".slideLayout+xml"
            if p.startswith("ppt/notesMasters/"):
                return CT + ".notesMaster+xml"
            if p.startswith("ppt/slides/"):
                return CT + ".slide+xml"
            if p.startswith("ppt/notesSlides/"):
                return CT + ".notesSlide+xml"
            if p.startswith("ppt/theme/"):
                return CT_THEME
            if p.startswith("ppt/presProps"):
                return CT + ".presProps+xml"
            if p.startswith("ppt/viewProps"):
                return CT + ".viewProps+xml"
            if p.startswith("ppt/tableStyles"):
                return CT + ".tableStyles+xml"
            if p == "docProps/core.xml":
                return "application/vnd.openxmlformats-package.core-properties+xml"
            if p == "docProps/app.xml":
                return "application/vnd.openxmlformats-officedocument.extended-properties+xml"
            return None

        if "[Content_Types].xml" in names:
            ct_root = ET.fromstring(z.read("[Content_Types].xml"))
            declared_ct = {}
            for e in ct_root:
                pn = e.get("PartName")
                if pn:
                    declared_ct[pn] = e.get("ContentType")
            for pn, actual in sorted(declared_ct.items()):
                exp = expected_ct(pn)
                if exp is None:
                    continue
                if actual != exp:
                    problems.append("content type 声明不对：%s 声明为 %s，应为 %s"
                                    % (pn, actual, exp))
            for pn in sorted(declared_ct):
                if pn.lstrip("/") not in names:
                    problems.append("content type 声明了不存在的部件 %s" % pn)

    return problems


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description="纯标准库 PPTX 生成器")
    ap.add_argument("spec", nargs="?", help="幻灯片规格 JSON 文件")
    ap.add_argument("-o", "--out", help="输出 .pptx 路径")
    ap.add_argument("--check", action="store_true", help="生成后做结构自检")
    ap.add_argument("--selftest", action="store_true", help="跑内置自检")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    if not args.spec:
        print("错误：必须给出规格文件，或用 --selftest", file=sys.stderr)
        return 1
    if not args.out:
        print("错误：必须用 -o 指定输出路径", file=sys.stderr)
        return 1
    try:
        spec = load_spec(args.spec)
    except SpecError as e:
        print("规格错误：%s" % e, file=sys.stderr)
        return 1
    base = os.path.dirname(os.path.abspath(args.spec))
    try:
        n_slides, n_notes, warnings = build(spec, args.out, base)
    except SpecError as e:
        print("规格错误：%s" % e, file=sys.stderr)
        return 1
    for w in warnings:
        print("警告：%s" % w, file=sys.stderr)
    if args.check:
        problems = check_pptx(args.out)
        if problems:
            print("结构自检未通过：", file=sys.stderr)
            for p in problems:
                print("  - %s" % p, file=sys.stderr)
            return 2
    print("已生成 %s：%d 页，%d 页带讲稿备注。" % (args.out, n_slides, n_notes))
    return 0


def selftest():
    """内置自检：生成一份最小规格 → 检查结构 → 确认关键部件存在。

    🔴 自检用的临时目录**必须清理**。本脚本的 --selftest 被仓库守卫
    每次运行都调一遍、变异测试每轮要调几十遍；不清理 ⇒ 系统 TEMP 里
    堆出上百个 `jfa_pptx_*` 空目录（实测一轮变异测试就漏几十个）。
    「跑得越多越脏」的自检是负资产，所以清理放在 finally 里，
    成功/失败/异常都清。
    """
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="jfa_pptx_")
    # 报告用了哪个临时目录 —— 守卫据此**独立**核对它有没有被清掉。
    # 只报事实（路径），不下结论（清没清），否则就变成"自己给自己打分"。
    print("selftest: tmpdir=%s" % tmp)
    try:
        return _selftest_in(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _selftest_in(tmp):
    """自检主体。tmp 由调用方负责清理。"""
    spec = {
        "meta": {"title": "自检", "author": "jfa"},
        "slides": [
            {"layout": "title", "title": "封面", "subtitle": "副标题"},
            {"layout": "bullets", "title": "第二页", "bullets": [
                {"text": "要点一", "level": 0}, {"text": "要点二", "level": 1}],
             "notes": "这是讲稿。\n第二行。", "footer": "来源：自检"},
            {"layout": "two-column", "title": "第三页", "bullets": [
                {"text": "左一", "level": 0}, {"text": "左二", "level": 0},
                {"text": "右一", "level": 1}]},
        ],
    }
    sp = os.path.join(tmp, "spec.json")
    op = os.path.join(tmp, "out.pptx")
    write_text(sp, json.dumps(spec, ensure_ascii=False, indent=2))
    try:
        n, nn, _w = build(spec, op, tmp)
    except Exception as e:
        print("selftest: 生成失败 %s" % e, file=sys.stderr)
        return 2
    problems = check_pptx(op)
    if problems:
        print("selftest: 结构自检未通过", file=sys.stderr)
        for p in problems:
            print("  - %s" % p, file=sys.stderr)
        return 2
    if n != 3 or nn != 1:
        print("selftest: 页数/备注数不对：%d / %d" % (n, nn), file=sys.stderr)
        return 2
    # 非法规格必须被拒
    bad = os.path.join(tmp, "bad.json")
    write_text(bad, json.dumps({"slides": [{"layout": "不存在的版式"}]}))
    try:
        load_spec(bad)
    except SpecError:
        pass
    else:
        print("selftest: 非法版式未被拒绝", file=sys.stderr)
        return 2

    # 🔴 变异测试：content type 写坏 ⇒ 守卫必须报红。
    #    （只跑绿不算数——必须证明它会红。历史上主题的 content type 写成
    #     `...officedocument.drawingml.theme+xml` 就是这样静默溜过去的。）
    import zipfile as _zf
    mutant = os.path.join(tmp, "mutant.pptx")
    with _zf.ZipFile(op) as zin, _zf.ZipFile(mutant, "w", _zf.ZIP_DEFLATED) as zout:
        for n in zin.namelist():
            data = zin.read(n)
            if n == "[Content_Types].xml":
                data = data.replace(
                    b"application/vnd.openxmlformats-officedocument.theme+xml",
                    b"application/vnd.openxmlformats-officedocument.drawingml.theme+xml")
            zout.writestr(n, data)
    m_problems = check_pptx(mutant)
    if not any("content type" in p for p in m_problems):
        print("selftest: 主题 content type 被改坏后守卫没有报红", file=sys.stderr)
        for p in m_problems:
            print("  - %s" % p, file=sys.stderr)
        return 2

    # 变异测试 2：字号单位写坏（sz 少乘 100）⇒ 守卫必须报红。
    #    🔴 变异**不能写死某个字号**（版式一改字号，变异就命不中 ⇒ 守卫"没红"，
    #       看起来像守卫失灵，其实是变异失效）。这里按正则抓**任意** sz 属性，
    #       把它砍掉两位数字（1200 → 12）⇒ 必然违反 schema 下限 100。
    import re as _re3
    mutant2 = os.path.join(tmp, "mutant2.pptx")
    hit2 = False
    with _zf.ZipFile(op) as zin, _zf.ZipFile(mutant2, "w", _zf.ZIP_DEFLATED) as zout:
        for n in zin.namelist():
            data = zin.read(n)
            if not hit2 and n.startswith("ppt/slides/slide") and n.endswith(".xml"):
                def _shrink(m):
                    return b'sz="' + m.group(1)[:-2] + b'"'
                new, cnt = _re3.subn(rb'sz="(\d{4})"', _shrink, data)
                if cnt:
                    hit2 = True
                    data = new
            zout.writestr(n, data)
    if not hit2:
        print("selftest: 变异没命中任何 sz 属性（守卫无从验证）", file=sys.stderr)
        return 2
    m2_problems = check_pptx(mutant2)
    if not any("字号" in p for p in m2_problems):
        print("selftest: 字号单位被改坏后守卫没有报红", file=sys.stderr)
        return 2

    print("selftest: 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
