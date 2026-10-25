#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""slide_layouts.py —— **版式原型表 + 文字高度表**（纯标准库）

为什么要有这一层
----------------
排版几何原先散在 `build_pptx.py` 的 `render_slide()` 里：每种版式各写各的坐标。
那有两个具体问题：

1. **判据读不到几何** —— "这页字放得下吗"只能靠人眼在 PowerPoint 里看。
2. **几何不是数据** —— 改一个版式的坐标要翻代码，而不是改一行表。

本模块把几何**抽成数据**：

* `CANVAS` / `PROTOTYPES` —— 画布与 7 种版式的槽位表
* `TEXT_HEIGHT` —— 文字高度表（字号 × 行数 → 所需框高）

渲染器（`build_pptx.py`）与判据（`slide_spec_lint.py`）**共用这一份**：
判据不会与渲染器漂移，几何改一处两边同时变。

🔴 **单位约定**：本模块内部一律用**磅(pt)**，只在写 XML 时换算成 EMU
（1 pt = 12700 EMU）。混用 EMU 与 pt 是算错坐标的头号原因。

🔴 **字号约定**：本模块的 `sz` 是**磅**；OOXML 的 `sz` 是**百分之一磅**，
换算在 `build_pptx.py` 里做（×100）。两处各写各的 ⇒ 必出 0.44 磅的错。

视觉设计
--------
本表的画布、色板、字号、卡片几何**实测自**参考课件
（`结构化研讨：理论与实践.pptx`，PptxGenJS 生成），不是凭印象配的。
参考课件的视觉身份：

* 画布 720 × 405 pt（10 × 5.625 in，16:9）
* 左边距 43.2 pt（0.6 in），内容宽 633.6 pt（8.8 in）
* 页标题 23 pt 粗体；卡片标题 14 pt；眉题/正文 12 pt；角标/页脚 10 pt
* 多色强调体系：每个卡片一套（强调色 / 极浅底 / 深色标题字），
  强调色在蓝-青-紫-青绿-绿-橙-粉-琥珀之间轮转

坐标系
------
* 画布 720 × 405 pt（10 × 5.625 in，16:9），原点左上角
* 左边距 43.2 pt（0.6 in），内容宽 633.6 pt
* 内容区上边 112 pt，下边 36 pt ⇒ 正文可用高 257 pt
"""
from __future__ import annotations

import math
import os
import sys

# ─────────────────────────────────────────────────────────────────
# 画布与调色板
# ─────────────────────────────────────────────────────────────────
CANVAS = {
    "w": 720.0,          # 10 in（16:9）
    "h": 405.0,          # 5.625 in
    "margin": 43.2,      # 0.6 in
    "body_top": 120.0,   # 正文区上边
    "body_bottom": 36.0, # 正文区下边
}
CONTENT_W = CANVAS["w"] - 2 * CANVAS["margin"]            # 633.6
BODY_H = CANVAS["h"] - CANVAS["body_top"] - CANVAS["body_bottom"]   # 257

COL_GAP = 14.4
COL_W = (CONTENT_W - COL_GAP) / 2                         # 309.6
IMG_INSET = 43.2
IMG_W = CONTENT_W - 2 * IMG_INSET                         # 547.2
CAPTION_H = 24.0
CAPTION_BAND = 40.0                                      # 有图注时图片让出的高度
CARD_PAD = 14.4                                          # 卡片边缘到内文的留白
BADGE_ZONE = 38.0                                        # 角标占的高度（角标 + 间距）

# 颜色（设计 token；渲染器与判据共用）
COLORS = {
    "ink": "1E293B",      # 主文字（正文页标题）
    "ink_deep": "172554", # 封面 / 分节页标题（深靛）
    "body": "334155",     # 正文
    "muted": "64748B",    # 次要文字（眉题、页脚）
    "accent": "2563EB",   # 主强调色（蓝）
    "accent_deep": "1E3A8A",
    "rule": "D1D5DB",     # 分隔线
    "rule_soft": "93C5FD",  # 封面分隔线（浅蓝）
    "card": "F8FAFC",     # 卡片底
    "paper": "FFFFFF",    # 背景
    "on_accent": "FFFFFF",  # 强调色之上的反白字
}

# 多色强调体系：每一套 = (强调色, 极浅底, 深色标题字)
# 取自参考课件实测用色（蓝/青/紫/青绿/绿/橙/粉/琥珀）。
ACCENTS = [
    {"accent": "2563EB", "tint": "EFF6FF", "deep": "1E3A8A"},
    {"accent": "0891B2", "tint": "ECFEFF", "deep": "155E75"},
    {"accent": "7C3AED", "tint": "F5F3FF", "deep": "6D28D9"},
    {"accent": "0F766E", "tint": "F0FDFA", "deep": "115E59"},
    {"accent": "16A34A", "tint": "F0FDF4", "deep": "15803D"},
    {"accent": "EA580C", "tint": "FFF7ED", "deep": "9A3412"},
    {"accent": "DB2777", "tint": "FCE7F3", "deep": "BE185D"},
    {"accent": "D97706", "tint": "FFFBEB", "deep": "92400E"},
]

# 字号（磅）
SIZES = {
    "title": 23,         # 正文页标题
    "title_center": 23,  # 封面 / 分节页标题
    "subtitle": 12,      # 眉题
    "body": 12,          # 正文
    "body_l2": 11,       # 次级正文
    "quote": 20,         # 引用
    "card_title": 14,    # 卡片标题
    "callout": 13,       # 提示条
    "badge": 10,         # 角标数字
    "caption": 9,
    "footer": 10,
}

# ─────────────────────────────────────────────────────────────────
# 文字高度表
#
# 行高 = 字号 × LINE_FACTOR（微软雅黑在 PowerPoint 里的常见行距），
# 框高 = 行高 × 行数。本仓库的文本框内边距为 0（见 build_pptx 的 bodyPr），
# 所以**不需要**再加 padding。
#
# 这张表是**显式写出来的**，不是运行时算的 ——
# 判据要给教师看"需要多高的框"，教师要能拿这张表自己核对。
#
# 🔴 表里的每个数都必须等于 `ceil(字号 × LINE_FACTOR × 行数)`，
#    自检会逐格核对（不是只查单调性）——
#    手写这种表最容易出的错就是"某一档凭感觉多写了 1–5 pt"，
#    那样会让溢出判据**偏松**，该报的报不出来。
# ─────────────────────────────────────────────────────────────────
LINE_FACTOR = 1.35

TEXT_HEIGHT = {
    9: {1: 13, 2: 25, 3: 37, 4: 49, 5: 61},
    10: {1: 14, 2: 27, 3: 41, 4: 54, 5: 68},
    11: {1: 15, 2: 30, 3: 45, 4: 60, 5: 75},
    12: {1: 17, 2: 33, 3: 49, 4: 65, 5: 81},
    13: {1: 18, 2: 36, 3: 53, 4: 71, 5: 88},
    14: {1: 19, 2: 38, 3: 57, 4: 76, 5: 95},
    20: {1: 27, 2: 54, 3: 81, 4: 108, 5: 135},
    23: {1: 32, 2: 63, 3: 94, 4: 125, 5: 156},
}

# 项目符号的段前距（磅），与 build_pptx 的 spcBef 一致
SPC_BEFORE = 6.0

# 层级缩进：文本左边界相对框左边界的偏移
TEXT_INDENT = {0: 0.0, 1: 14.0, 2: 42.0}


def _indent(level):
    if level <= 0:
        return 0.0
    return 28.0 * level - 14.0


# ─────────────────────────────────────────────────────────────────
# 版式原型表
#
# 每种版式 = 一组具名槽位。槽位是几何（数据），渲染时按名字取。
# 「哪些槽位出现」由 `slots_for()` 决定（那是组装逻辑，不是几何）。
#
# 槽位 kind：
#   text    文本框
#   rule    分隔线（细横条）
#   rect    实心色块（卡片底 / 强调条 / 角标底）
#   picture 图片
# ─────────────────────────────────────────────────────────────────
PROTOTYPES = {
    # 封面
    "title": {
        "Panel": {"x": 43.2, "y": 108.0, "w": 633.6, "h": 186.0, "kind": "rect",
                  "color": "card"},
        "PanelBar": {"x": 43.2, "y": 108.0, "w": 4.32, "h": 186.0, "kind": "rect",
                     "color": "accent"},
        "Title": {"x": 64.8, "y": 144.0, "w": 540.0, "h": 76.0, "sz": 23,
                  "bold": True, "color": "ink_deep", "align": "l"},
        "Subtitle": {"x": 64.8, "y": 228.0, "w": 540.0, "h": 32.0, "sz": 12,
                     "color": "muted", "align": "l"},
        "AccentStrip": {"x": 0.0, "y": 396.0, "w": 720.0, "h": 9.0,
                        "kind": "rect", "color": "accent"},
    },
    # 分节页
    "section": {
        "Panel": {"x": 43.2, "y": 126.0, "w": 633.6, "h": 150.0, "kind": "rect",
                  "color": "card"},
        "PanelBar": {"x": 43.2, "y": 126.0, "w": 4.32, "h": 150.0, "kind": "rect",
                     "color": "accent"},
        "Title": {"x": 64.8, "y": 156.0, "w": 540.0, "h": 60.0, "sz": 23,
                  "bold": True, "color": "ink_deep", "align": "l"},
        "Subtitle": {"x": 64.8, "y": 224.0, "w": 540.0, "h": 32.0, "sz": 12,
                     "color": "muted", "align": "l"},
        "AccentStrip": {"x": 0.0, "y": 396.0, "w": 720.0, "h": 9.0,
                        "kind": "rect", "color": "accent"},
    },
    # 引用
    "quote": {
        "Bar": {"x": 43.2, "y": 140.0, "w": 4.32, "h": 96.0, "kind": "rect",
                "color": "accent"},
        "Quote": {"x": 60.0, "y": 140.0, "w": 560.0, "h": 96.0, "sz": 20,
                  "color": "ink", "align": "l", "anchor": "ctr"},
        "Attribution": {"x": 60.0, "y": 248.0, "w": 560.0, "h": 28.0, "sz": 12,
                        "color": "muted", "align": "l"},
    },
    # bullets / two-column / image-focus / blank 共用的页眉区
    "content": {
        "Title": {"x": 43.2, "y": 28.8, "w": 633.6, "h": 43.2, "sz": 23,
                  "bold": True, "color": "ink", "align": "l"},
        "Eyebrow": {"x": 43.2, "y": 72.0, "w": 633.6, "h": 25.2, "sz": 12,
                    "color": "muted", "align": "l"},
        "Rule": {"x": 43.2, "y": 104.4, "w": 633.6, "h": 2.16, "kind": "rule",
                 "color": "accent"},
        # 正文卡：浅底 + 左侧强调条
        "Card": {"x": 43.2, "y": 120.0, "w": 633.6, "h": 249.0, "kind": "rect",
                 "color": "card"},
        "CardBar": {"x": 43.2, "y": 120.0, "w": 4.32, "h": 249.0, "kind": "rect",
                    "color": "accent"},
        "Body": {"x": 60.0, "y": 134.4, "w": 604.8, "h": 220.2, "sz": 12},
        # 两栏：两张白卡，各带一条强调条
        "ColLeft": {"x": 43.2, "y": 120.0, "w": 309.6, "h": 249.0, "kind": "rect",
                    "color": "paper"},
        "ColLeftBar": {"x": 43.2, "y": 120.0, "w": 4.32, "h": 249.0, "kind": "rect",
                       "color": "accent"},
        "ColRight": {"x": 367.2, "y": 120.0, "w": 309.6, "h": 249.0, "kind": "rect",
                     "color": "paper"},
        "ColRightBar": {"x": 367.2, "y": 120.0, "w": 4.32, "h": 249.0, "kind": "rect",
                        "color": "accent2"},
        "BadgeLeft": {"x": 57.6, "y": 132.0, "w": 28.8, "h": 28.8, "kind": "rect",
                      "color": "accent"},
        "BadgeRight": {"x": 381.6, "y": 132.0, "w": 28.8, "h": 28.8, "kind": "rect",
                       "color": "accent2"},
        "BodyLeft": {"x": 57.6, "y": 170.0, "w": 281.0, "h": 187.0, "sz": 12},
        "BodyRight": {"x": 381.6, "y": 170.0, "w": 281.0, "h": 187.0, "sz": 12},
        # 角标文字与角标色块**同框**（不是叠在上面）⇒ 数字必然在色块正中，
        # 不会因为字体度量差几 pt 而露到块外面去。
        "BadgeLeftText": {"x": 57.6, "y": 132.0, "w": 28.8, "h": 28.8, "sz": 10,
                          "bold": True, "color": "on_accent", "align": "ctr",
                          "anchor": "ctr"},
        "BadgeRightText": {"x": 381.6, "y": 132.0, "w": 28.8, "h": 28.8, "sz": 10,
                           "bold": True, "color": "on_accent", "align": "ctr",
                           "anchor": "ctr"},
        "Picture": {"x": 43.2, "y": 120.0, "w": 633.6, "h": 249.0, "kind": "picture"},
        "Caption": {"x": 43.2, "y": 371.0, "w": 633.6, "h": 22.0, "sz": 9,
                    "color": "muted", "align": "ctr"},
    },
    # 所有版式共用的页脚
    "footer": {
        "Footer": {"x": 43.2, "y": 376.0, "w": 633.6, "h": 16.0, "sz": 10,
                   "color": "muted", "align": "l"},
    },
}

LAYOUTS = ("title", "bullets", "two-column", "image-focus", "quote", "section", "blank")


def geom(group, name):
    """取一个槽位的几何。group ∈ {title, section, quote, content, footer}。"""
    return PROTOTYPES[group][name]


# ─────────────────────────────────────────────────────────────────
# 强调色选取
# ─────────────────────────────────────────────────────────────────
def accent_pair(slide):
    """这一页用哪一套强调色（单栏用 accent，两栏用 accent / accent2）。

    🔴 必须**只由 spec 自身决定**（渲染器与判据看到的输入完全一样），
       否则「画出来的颜色」和「判据以为的颜色」会不一致。
    规则：spec 的 `id`（形如 "P3"）优先按序号轮转；没有 id 就按标题的字符和轮转。
    """
    sid = str(slide.get("id") or "")
    if sid.startswith("P") and sid[1:].isdigit():
        idx = (int(sid[1:]) - 1) % len(ACCENTS)
    else:
        t = str(slide.get("title") or "")
        idx = sum(ord(c) for c in t) % len(ACCENTS)
    a = ACCENTS[idx]
    b = ACCENTS[(idx + 1) % len(ACCENTS)]
    out = dict(a)
    out["accent2"] = b["accent"]
    out["tint2"] = b["tint"]
    out["deep2"] = b["deep"]
    return out, idx


# ─────────────────────────────────────────────────────────────────
# 文字度量
# ─────────────────────────────────────────────────────────────────
def text_width_em(s):
    """文本宽度，以 **em** 计：全角 1.0，半角（ASCII/拉丁/西里尔）0.5。

    🔴 为什么不用"一个字符算一个字"：那会把 `3×3 均值滤波` 算成 9 em
    （实际约 6 em），从而**凭空多折一行**，误报溢出。
    混排的中文课件里英文缩写很多，按 em 算才准。
    """
    w = 0.0
    for ch in str(s or ""):
        w += 0.5 if ord(ch) < 0x2E80 else 1.0
    return w


def chars_per_line(box_w, font_size, level=0):
    """一行能放多少 em。

    🔴 **保守估计**：不按字距、不按标点压缩、不给西文做 kerning。
    宁可让教师多看一眼，不要让字悄悄被缩掉。
    """
    usable = box_w - _indent(level)
    if usable <= 0:
        return 0.0
    return float(usable) / float(font_size)


def lines_for(text, box_w, font_size, level=0):
    """一段文字占几行。"""
    if not str(text or ""):
        return 1
    cap = chars_per_line(box_w, font_size, level)
    if cap <= 0:
        return 1
    return max(1, int(math.ceil(text_width_em(text) / cap)))


def row_height(font_size, lines):
    """所需框高 = ceil(字号 × 行高系数 × 行数)。

    🔴 减 1e-9 的容差不是装饰：`12 × 1.35 × 5` 在浮点里是
    `81.00000000000001`，不吸收掉就会 ceil 成 82 —— 高度表凭空多 1 pt。
    这类误差会让"表 ↔ 公式"的逐格核对**永远差 1**，守卫就会变成噪音。
    """
    return int(math.ceil(float(font_size) * LINE_FACTOR * int(lines) - 1e-9))


def text_height(font_size, lines):
    """按文字高度表查所需框高；表里没有的字号/行数按行高现算。"""
    tbl = TEXT_HEIGHT.get(int(font_size))
    if tbl and lines in tbl:
        return tbl[lines]
    return row_height(font_size, lines)


# ─────────────────────────────────────────────────────────────────
# 槽位组装：一份 spec → 实际会渲染的槽位列表
#
# 🔴 这是**几何与内容的唯一真相**：
#    渲染器按它画，判据按它量文字会不会溢出。
#    两边各算一套 ⇒ 判据说的和画出来的不一样（那种判据没有价值）。
# ─────────────────────────────────────────────────────────────────
def _text_slot(group, name, text, **over):
    g = dict(geom(group, name))
    g["kind"] = "text"
    g["name"] = name
    g["paras"] = [{"text": text, "sz": g.get("sz", SIZES["body"]),
                   "bold": g.get("bold", False), "color": g.get("color", "ink"),
                   "align": g.get("align", "l"), "bullet": False}]
    g.update(over)
    return g


def _rect_slot(group, name, **over):
    g = dict(geom(group, name))
    g["kind"] = "rect"
    g["name"] = name
    g.update(over)
    return g


def _bullet_pars(bullets, sz, sz_l2, color="body", bullet_color=None):
    out = []
    for b in bullets:
        if isinstance(b, str):
            text, level = b, 0
        else:
            text, level = b.get("text", ""), int(b.get("level", 0))
        out.append({"text": text,
                    "sz": sz if level == 0 else sz_l2,
                    "level": level,
                    "spc_before": SPC_BEFORE if level == 0 else 0.0,
                    "bullet": True,
                    "bullet_color": bullet_color or color,
                    "color": color, "align": "l", "bold": False})
    return out


def _split_columns(bullets):
    """两栏版式的分栏规则：先按层级，层级不够就按数量对半。"""
    left = [b for b in bullets if int(b.get("level", 0) if isinstance(b, dict) else 0) == 0]
    right = [b for b in bullets
             if int(b.get("level", 0) if isinstance(b, dict) else 0) > 0]
    if not right:
        half = (len(left) + 1) // 2
        right, left = left[half:], left[:half]
    return left, right


def _paras_need(paras, box_w):
    """一组段落占多高（磅）。

    🔴 渲染器与判据**必须用同一个函数**算高度 —— 两处各算一套，
       就会出现「判据说没溢出、画出来溢出了」那种没有价值的判据。
    """
    need = 0.0
    for p in paras or []:
        sz = int(p.get("sz") or SIZES["body"])
        lines = lines_for(p.get("text", ""), box_w, sz, int(p.get("level", 0)))
        need += text_height(sz, lines)
        need += float(p.get("spc_before") or 0.0)
    return need


def _fit_card(paras, box_w, cap_h, pad, min_h=64.0):
    """卡片（浅底 + 强调条）的高度与内文框高度。

    卡片**随内容自适应**（3 条要点不该在下面留 200pt 空白），
    但**上限是正文区高** —— 超出的部分由溢出判据报出来（`overflow()`），
    而不是让 PowerPoint 悄悄缩字号。
    返回 (card_h, inner_h)。
    """
    need = _paras_need(paras, box_w)
    inner = min(need, max(cap_h - 2 * pad, 0.0))
    card_h = max(min_h, inner + 2 * pad)
    if card_h > cap_h:
        card_h = cap_h
        inner = max(cap_h - 2 * pad, 0.0)
    return card_h, inner


def slots_for(slide):
    """一页 spec → 实际渲染的槽位列表（含几何与文字内容）。"""
    layout = slide.get("layout", "bullets")
    title = slide.get("title", "")
    subtitle = slide.get("subtitle", "")
    bullets = slide.get("bullets") or []
    footer = slide.get("footer", "")
    image = slide.get("image", "")
    caption = slide.get("caption", "")
    out = []
    pair, _idx = accent_pair(slide)

    if layout == "title":
        out.append(_rect_slot("title", "Panel", color=COLORS["card"]))
        out.append(_rect_slot("title", "PanelBar", color=pair["accent"]))
        if title:
            out.append(_text_slot("title", "Title", title))
        if subtitle:
            out.append(_text_slot("title", "Subtitle", subtitle))
        out.append(_rect_slot("title", "AccentStrip", color=pair["accent"]))
    elif layout == "section":
        out.append(_rect_slot("section", "Panel", color=COLORS["card"]))
        out.append(_rect_slot("section", "PanelBar", color=pair["accent"]))
        if title:
            out.append(_text_slot("section", "Title", title))
        if subtitle:
            out.append(_text_slot("section", "Subtitle", subtitle))
        out.append(_rect_slot("section", "AccentStrip", color=pair["accent"]))
    elif layout == "quote":
        out.append(_rect_slot("quote", "Bar", color=pair["accent"]))
        if title:
            out.append(_text_slot("quote", "Quote", title))
        if subtitle:
            out.append(_text_slot("quote", "Attribution", subtitle))
    else:
        if title:
            out.append(_text_slot("content", "Title", title))
            if subtitle:
                out.append(_text_slot("content", "Eyebrow", subtitle))
            out.append(dict(geom("content", "Rule"), kind="rule", name="Rule",
                            color=pair["accent"]))
        if layout == "two-column":
            left, right = _split_columns(bullets)
            bl = _bullet_pars(left, SIZES["body"], SIZES["body_l2"],
                              color=COLORS["body"], bullet_color=pair["accent"])
            br = _bullet_pars(right, SIZES["body"], SIZES["body_l2"],
                              color=COLORS["body"], bullet_color=pair["accent2"])
            lg = geom("content", "BodyLeft")
            rg = geom("content", "BodyRight")
            need = max(_paras_need(bl, lg["w"]), _paras_need(br, rg["w"]))
            card_h = max(96.0, min(need + 2 * CARD_PAD + BADGE_ZONE, BODY_H))
            inner = max(card_h - 2 * CARD_PAD - BADGE_ZONE, 0.0)
            out.append(_rect_slot("content", "ColLeft", color=COLORS["paper"],
                                  h=card_h))
            out.append(_rect_slot("content", "ColLeftBar", color=pair["accent"],
                                  h=card_h))
            out.append(_rect_slot("content", "ColRight", color=COLORS["paper"],
                                  h=card_h))
            out.append(_rect_slot("content", "ColRightBar", color=pair["accent2"],
                                  h=card_h))
            out.append(_rect_slot("content", "BadgeLeft", color=pair["accent"]))
            out.append(_text_slot("content", "BadgeLeftText", "01"))
            out.append(_rect_slot("content", "BadgeRight", color=pair["accent2"]))
            out.append(_text_slot("content", "BadgeRightText", "02"))
            gl = dict(lg)
            gl.update({"kind": "text", "name": "BodyLeft", "h": inner, "paras": bl})
            gr = dict(rg)
            gr.update({"kind": "text", "name": "BodyRight", "h": inner, "paras": br})
            out.append(gl)
            out.append(gr)
        elif layout == "image-focus":
            img_h = BODY_H - (CAPTION_BAND if caption else 0.0)
            if image:
                pic = dict(geom("content", "Picture"))
                pic.update({"kind": "picture", "name": "Picture", "h": img_h,
                            "src": image})
                out.append(pic)
            if bullets:
                b = dict(geom("content", "Body"))
                b.update({"kind": "text", "name": "Body",
                          "y": CANVAS["body_top"] + img_h + 8.0, "h": 30.0,
                          "paras": _bullet_pars(bullets, SIZES["body"], SIZES["body_l2"],
                                                color=COLORS["body"],
                                                bullet_color=pair["accent"])})
                out.append(b)
            if caption:
                c = dict(geom("content", "Caption"))
                c.update({"kind": "text", "name": "Caption",
                          "y": CANVAS["body_top"] + img_h + 10.0,
                          "paras": [{"text": caption, "sz": SIZES["caption"],
                                     "bold": False, "color": "muted",
                                     "align": "ctr", "bullet": False}]})
                out.append(c)
        else:
            # 正文卡：高度随内容自适应（但封顶在正文区高）
            bp = _bullet_pars(bullets, SIZES["body"], SIZES["body_l2"],
                              color=COLORS["body"], bullet_color=pair["accent"])
            body_geom = geom("content", "Body")
            card_h, inner_h = _fit_card(bp, body_geom["w"], BODY_H, CARD_PAD)
            card = dict(geom("content", "Card"))
            card.update({"kind": "rect", "name": "Card", "h": card_h,
                         "color": COLORS["card"]})
            out.append(card)
            bar = dict(geom("content", "CardBar"))
            bar.update({"kind": "rect", "name": "CardBar", "h": card_h,
                        "color": pair["accent"]})
            out.append(bar)
            if bullets:
                b = dict(body_geom)
                b.update({"kind": "text", "name": "Body",
                          "y": body_geom["y"], "h": inner_h, "paras": bp})
                out.append(b)

    if footer:
        out.append(_text_slot("footer", "Footer", footer))
    return out


# ─────────────────────────────────────────────────────────────────
# 溢出判定
# ─────────────────────────────────────────────────────────────────
def measure_slot(slot):
    """量一个文本槽位：需要多高、框有多高。"""
    return _paras_need(slot.get("paras") or [], slot.get("w", 0)), \
        float(slot.get("h") or 0.0)


def overflow(slide):
    """一页里所有**装不下**的文本槽位。

    返回 [{slot, need, have, over, text}]。
    🔴 装不下 ≠ 看不见：PowerPoint 的文本框带 `normAutofit`，
       文字放不下时会**自动缩小字号** —— 于是"设计的 12pt"实际变成 9pt，
       而版面看起来还是"正常的"。这是**静默失效**，必须报出来。
    """
    bad = []
    for slot in slots_for(slide):
        if slot.get("kind") != "text":
            continue
        need, have = measure_slot(slot)
        if need > have + 0.5:
            preview = ""
            for p in slot.get("paras") or []:
                if p.get("text"):
                    preview = str(p["text"])[:24]
                    break
            bad.append({"slot": slot.get("name", ""), "need": need, "have": have,
                        "over": need - have, "text": preview})
    return bad


def selftest():
    """内置自检：已知样例必须给出已知结论。"""
    # ① 装得下：一行短标题
    ok = {"layout": "bullets", "title": "看清问题的起点",
          "bullets": [{"text": "同一场景，两张成像清晰度不同", "level": 0}],
          "notes": "讲稿"}
    if overflow(ok):
        print("selftest: 良好样例被误报为溢出")
        return 2
    # ② 装不下：超长封面标题（23pt，20 字 = 460pt < 633.6 ⇒ 一行 ⇒ 32pt < 96pt 装得下）
    #    ⇒ 改用真正会溢出的：正文页 40 条要点
    bad = {"layout": "bullets", "title": "标题",
           "bullets": [{"text": "第 %d 条要点，占满一行宽度需要折行才能放进卡片里" % i,
                        "level": 0} for i in range(12)]}
    if not overflow(bad):
        print("selftest: 装不下的样例没有被报出来")
        return 2
    # ③ 文字高度表自洽：每一格都必须等于 ceil(字号 × 行高系数 × 行数)
    #    🔴 只查单调性**不够**：手写这种表最容易出的错是
    #       「某一档凭感觉多写了 1–5 pt」—— 单调性照样成立，
    #       但溢出判据会**偏松**，该报的报不出来。
    for sz, tbl in sorted(TEXT_HEIGHT.items()):
        for n in sorted(tbl):
            want = row_height(sz, n)
            if tbl[n] != want:
                print("selftest: 文字高度表与行高公式不符：%dpt %d 行，表里 %d，应为 %d"
                      % (sz, n, tbl[n], want))
                return 2
    # ④ 强调色选取只由 spec 自身决定（渲染器与判据看到的输入一样）
    s1 = {"id": "P3", "title": "甲"}
    s2 = {"id": "P3", "title": "乙"}
    if accent_pair(s1)[0] != accent_pair(s2)[0]:
        print("selftest: 强调色选取依赖了标题文字（应当只依赖 id）")
        return 2
    print("selftest: 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(selftest())
