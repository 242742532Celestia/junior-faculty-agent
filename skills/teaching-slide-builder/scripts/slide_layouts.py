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

* `CANVAS` / `PROTOTYPES` —— 画布与各版式的槽位表
* `TEXT_HEIGHT` —— 文字高度表（字号 × 行数 → 所需框高）

渲染器（`build_pptx.py`）与判据（`slide_spec_lint.py`）**共用这一份**：
判据不会与渲染器漂移，几何改一处两边同时变。

🔴 **单位约定**：本模块内部一律用**磅(pt)**，只在写 XML 时换算成 EMU
（1 pt = 12700 EMU）。混用 EMU 与 pt 是算错坐标的头号原因。

🔴 **字号约定**：本模块的 `sz` 是**磅**；OOXML 的 `sz` 是**百分之一磅**，
换算在 `build_pptx.py` 里做（×100）。两处各写各的 ⇒ 必出 0.44 磅的错。

视觉设计（v2 —— 对齐参考课件）
------------------------------
本表的画布、色板、字号、卡片几何**实测自**参考课件
（`结构化研讨：理论与实践.pptx`，PptxGenJS 生成），不是凭印象配的。
参考课件的视觉身份：

* 画布 720 × 405 pt（10 × 5.625 in，16:9），左边距 42.5 pt，内容宽 635 pt
* 页标题 24 pt 粗体深色（左 50 pt）；标题下方 1.5 pt 强调色细横线；
  眉题 11 pt 灰色（**在标题与细线之间**）
* **卡片 = 顶部 5 pt 粗色条 + 极浅底 + 彩色粗体标题 + 灰色正文**
* **圆形编号徽章**（实心强调色圆 + 白字数字），两栏页用
* **表格**：深蓝表头 + 白字 + 斑马纹行 + 首列粗体居中
* **左色条块**：左侧 5 pt 色条 + 浅底 + 粗体彩色标题 + 灰正文
* 封面/分节页右上角**深色课时块**（白字两行）
* 页脚是**标签串**：粗体前缀 + ｜ 分隔

坐标系
------
* 画布 720 × 405 pt（10 × 5.625 in，16:9），原点左上角
* 左边距 42.5 pt，内容宽 635 pt
* 正文区上边 112 pt，下边 58 pt ⇒ 正文可用高 235 pt
"""
from __future__ import annotations

import math
import os
import re
import sys

# ─────────────────────────────────────────────────────────────────
# 画布与调色板
# ─────────────────────────────────────────────────────────────────
CANVAS = {
    "w": 720.0,          # 10 in（16:9）
    "h": 405.0,          # 5.625 in
    "margin": 42.5,      # 参考稿实测：内容左边缘 85px ÷ 2 = 42.5pt
    "body_top": 112.0,   # 正文区上边（细横线之下）
    "body_bottom": 58.0, # 正文区下边（页脚之上）
}
CONTENT_W = CANVAS["w"] - 2 * CANVAS["margin"]            # 635
BODY_H = CANVAS["h"] - CANVAS["body_top"] - CANVAS["body_bottom"]   # 235

COL_GAP = 13.0           # 卡片/列间距（参考稿实测 ≈13pt）
COL_W = (CONTENT_W - COL_GAP) / 2                         # 311
IMG_INSET = 43.2
IMG_W = CONTENT_W - 2 * IMG_INSET                         # 548.4
CAPTION_H = 24.0
CAPTION_BAND = 40.0                                      # 有图注时图片让出的高度

# 卡片几何
CARD_BAR_H = 5.0         # 顶部粗色条高度
CARD_PAD_X = 13.0        # 卡片左右内边距
CARD_PAD_X_NARROW = 10.0 # 多列（≥4 列）时收紧
CARD_PAD_Y = 12.0        # 卡片上下内边距
CARD_MIN_H = 76.0        # 卡片的最小高度（内容少也要像个"块"）
TITLE_GAP = 4.0          # 卡片标题与正文之间的间距
BADGE_D = 30.0           # 圆形编号徽章直径（参考稿实测 60px ÷ 2）

# 表格几何
TABLE_HEAD_H = 29.0      # 表头行高
# 🔴 数据行高是**下限**，不是固定值 —— 见 `_table_geometry` 的说明。
#    只有当单元格里是**真公式**（分式 / 根式）时，行高才会被撑高；
#    纯文字表格的行高与从前**逐字节相同**（30pt）。
TABLE_ROW_H = 30.0
TABLE_CELL_PAD = 5.0
TABLE_HEAD_PAD = 6.0     # 表头单元格的内边距（横向也是 6）

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
    "badge_block": "1F3864",  # 封面右上角的深色课时块
    "table_head": "1E3A8A",  # 表格首列表头（深靛）
    "table_head2": "1D4ED8",  # 表格其余表头（蓝）
    "table_zebra": "DBEAFE",  # 表格斑马纹（深）
    "table_zebra_soft": "EFF6FF",  # 表格斑马纹（浅）
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
    "title": 24,         # 正文页标题
    "title_center": 30,  # 封面标题（比正文页大一号）
    "subtitle": 13,      # 封面副标题
    "eyebrow": 11,       # 页眉下的灰色眉题
    "body": 12,          # 正文
    "body_l2": 11,       # 次级正文
    "quote": 20,         # 引用
    "card_title": 14,    # 卡片标题
    "callout": 13,       # 提示条
    "badge": 12,         # 圆形徽章数字
    "caption": 9,
    "footer": 10,
    "block": 13,         # 封面课时块第一行
    "block2": 11,        # 封面课时块第二行
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
    24: {1: 33, 2: 65, 3: 98, 4: 130, 5: 162},
    30: {1: 41, 2: 81, 3: 122, 4: 162, 5: 203},
}

# 项目符号的段前距（磅），与 build_pptx 的 spcBef 一致
SPC_BEFORE = 6.0

# 层级缩进：文本左边界相对框左边界的偏移
TEXT_INDENT = {0: 0.0, 1: 14.0, 2: 42.0}

# 「标签：说明」用的分隔符（全角冒号）
LABEL_SEP = "："


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
#   rect    实心色块（卡片底 / 强调条 / 角标底 / 表格单元）
#   ellipse 圆形徽章
#   picture 图片
# ─────────────────────────────────────────────────────────────────
PROTOTYPES = {
    # 封面（标题块垂直居中 —— 封面不该是"上面一坨、下面全空"）
    "title": {
        "Title": {"x": 50.0, "y": 170.0, "w": 520.0, "h": 42.0, "sz": 30,
                  "bold": True, "color": "ink_deep", "align": "l"},
        "Subtitle": {"x": 50.0, "y": 224.0, "w": 520.0, "h": 22.0, "sz": 13,
                     "color": "muted", "align": "l"},
        "Rule": {"x": 42.5, "y": 262.0, "w": 635.0, "h": 1.5, "kind": "rule",
                 "color": "rule_soft"},
        # 右上角深色课时块（白字两行）
        "Badge": {"x": 610.5, "y": 34.0, "w": 67.0, "h": 46.0, "kind": "rect",
                  "color": "badge_block"},
        "BadgeText": {"x": 620.0, "y": 40.0, "w": 50.0, "h": 36.0, "sz": 13,
                      "bold": True, "color": "on_accent", "align": "l"},
        "AccentStrip": {"x": 0.0, "y": 396.0, "w": 720.0, "h": 9.0,
                        "kind": "rect", "color": "accent"},
    },
    # 分节页（与封面同骨架，标题色与细线色不同）
    "section": {
        "Title": {"x": 50.0, "y": 38.0, "w": 520.0, "h": 34.0, "sz": 24,
                  "bold": True, "color": "ink_deep", "align": "l"},
        "Subtitle": {"x": 50.0, "y": 76.0, "w": 520.0, "h": 20.0, "sz": 12,
                     "color": "muted", "align": "l"},
        "Rule": {"x": 42.5, "y": 100.0, "w": 635.0, "h": 1.5, "kind": "rule",
                 "color": "accent"},
        "Badge": {"x": 610.5, "y": 34.0, "w": 67.0, "h": 46.0, "kind": "rect",
                  "color": "badge_block"},
        "BadgeText": {"x": 620.0, "y": 40.0, "w": 50.0, "h": 36.0, "sz": 13,
                      "bold": True, "color": "on_accent", "align": "l"},
        "AccentStrip": {"x": 0.0, "y": 396.0, "w": 720.0, "h": 9.0,
                        "kind": "rect", "color": "accent"},
    },
    # 引用
    "quote": {
        "Title": {"x": 50.0, "y": 38.0, "w": 600.0, "h": 34.0, "sz": 24,
                  "bold": True, "color": "ink", "align": "l"},
        "Rule": {"x": 42.5, "y": 100.0, "w": 635.0, "h": 1.5, "kind": "rule",
                 "color": "accent"},
        "Bar": {"x": 42.5, "y": 132.0, "w": 5.0, "h": 110.0, "kind": "rect",
                "color": "accent"},
        "Quote": {"x": 64.0, "y": 132.0, "w": 560.0, "h": 110.0, "sz": 20,
                  "color": "ink", "align": "l", "anchor": "ctr"},
    },
    # 正文页页眉区
    "content": {
        "Title": {"x": 50.0, "y": 38.0, "w": 600.0, "h": 34.0, "sz": 24,
                  "bold": True, "color": "ink", "align": "l"},
        "Eyebrow": {"x": 50.0, "y": 74.0, "w": 600.0, "h": 18.0, "sz": 11,
                    "color": "muted", "align": "l"},
        "Rule": {"x": 42.5, "y": 100.0, "w": 635.0, "h": 1.5, "kind": "rule",
                 "color": "accent"},
        "Picture": {"x": 42.5, "y": 112.0, "w": 635.0, "h": 235.0, "kind": "picture"},
        "Caption": {"x": 42.5, "y": 356.0, "w": 635.0, "h": 20.0, "sz": 9,
                    "color": "muted", "align": "ctr"},
    },
    # 所有版式共用的页脚（标签串：粗体前缀 + 灰正文）
    "footer": {
        "Footer": {"x": 50.0, "y": 368.0, "w": 635.0, "h": 16.0, "sz": 10,
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
# ── 公式（LaTeX）感知 ─────────────────────────────────────────
#
# 🔴 为什么判据必须认公式：公式的**源码长度**与它**印出来的宽度**
#    完全不成比例。
#    `$\zeta = \frac{\gamma}{\omega_{0}}$` 源码 30 个字符（按 ASCII 算 15 em），
#    印出来却只有 4~5 em。
#    按源码量 ⇒ 凭空多折一行 ⇒ **误报溢出** ——
#    而误报一多，真溢出就被淹没在里面，判据红了也没人看。
#
#    所以：宽度与字数都按**渲染后**算，公式按「等效字形数」折算。
#
_MATH_SPAN = re.compile(r"\$\$(.+?)\$\$|\$(?!\$)([^$\n]+?)(?<!\$)\$", re.S)
_MATH_CMD = re.compile(r"\\[A-Za-z]+")
# 带参数的结构（分数/根号/组合数）比单个字形宽一点
_MATH_WIDE = ("\\frac", "\\dfrac", "\\tfrac", "\\sqrt", "\\binom")


def split_math(s):
    """把文本切成 [(是否公式, 载荷)]。

    公式载荷是**里面的 LaTeX**（不含 `$` 定界符）。
    """
    out = []
    pos = 0
    for m in _MATH_SPAN.finditer(str(s or "")):
        if m.start() > pos:
            out.append((False, str(s)[pos:m.start()]))
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        out.append((True, inner or ""))
        pos = m.end()
    if pos < len(str(s or "")):
        out.append((False, str(s)[pos:]))
    return out


def math_width_em(latex):
    """估一个 LaTeX 公式**渲染后**的宽度（em）。

    模型刻意简单、刻意保守：
      · 每个 `\\命令` 记 1 个字形（希腊字母、运算符都约 1 em 宽）；
        带参数的结构（分数/根号）记 1.3；
      · 字母、数字各记 0.5 em；
      · 花括号、空白、上下标标记不计。
    ⇒ `$\\zeta = \\frac{\\gamma}{\\omega_{0}}$` ≈ 5 em，
      与它实际印出来的宽度同量级。
    """
    s = str(latex or "")
    w = 0.0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\":
            m = _MATH_CMD.match(s, i)
            if m:
                w += 1.3 if m.group(0) in _MATH_WIDE else 1.0
                i = m.end()
                continue
            i += 1
            continue
        if ch in "{} \t\r\n":
            i += 1
            continue
        w += 0.5 if ord(ch) < 0x2E80 else 1.0
        i += 1
    return w


def visible_chars(s):
    """字符数（**公式按渲染后的等效字形数算**，不是源码长度）。

    与 `text_width_em` 同一套模型 ⇒ 两处度量不会打架。
    """
    n = 0
    for is_math, payload in split_math(s):
        if is_math:
            n += max(1, int(round(math_width_em(payload) * 2)))
        else:
            n += len(re.sub(r"\s", "", payload))
    return n


def text_width_em(s):
    """文本宽度，以 **em** 计：全角 1.0，半角（ASCII/拉丁/西里尔）0.5。

    🔴 为什么不用"一个字符算一个字"：那会把 `3×3 均值滤波` 算成 9 em
    （实际约 6 em），从而**凭空多折一行**，误报溢出。
    混排的中文课件里英文缩写很多，按 em 算才准。

    🔴 **公式按渲染后的宽度算**（见 `math_width_em`）：
    公式源码长度与它印出来的宽度不成比例，按源码算必然误报溢出。
    """
    w = 0.0
    for is_math, payload in split_math(s):
        if is_math:
            w += math_width_em(payload)
            continue
        for ch in payload:
            w += 0.5 if ord(ch) < 0x2E80 else 1.0
    return w


def text_width_pt(s, font_size):
    """文本的大致宽度（磅）：em 数 × 字号。用于估算容器宽度。"""
    return text_width_em(s) * float(font_size)


# ── 公式高度（实测校准，不是猜的）────────────────────────────────
#
# 🔴 为什么**宽度**认公式还不够：公式还有**高度**。
#    `$\sqrt{\frac{k}{m}}$` 在 12pt 下墨迹高 39.5pt，
#    而表格单元格的文字槽只有 20pt。
#
# 🔴 **失效机理**（实测出来的，跟直觉不一样）：
#    文本框**不会**裁切溢出的公式 —— 墨迹照画。
#    真正把公式弄坏的是**下一行的色块**：表格行高固定 30pt 时，
#    公式从本行溢出到下一行，而下一行的填充矩形**画在后面**，
#    于是把溢出部分盖掉 ⇒ 表现为「分母不见了」「ω₀ 被削掉下半截」
#    「= 号变成一根横杠」。
#    ⇒ 判据必须是：**行高 ≥ 公式的墨迹底**，让公式不越界到下一行。
#
# 本机实测（PowerPoint 真渲染 + 墨迹包围盒，12pt）：
#   「需要的高度」= 文字框上沿 → 墨迹底的净高
#
#     结构                            实测净高      模型取值
#     普通文字 12pt                    12.5 pt      1.35 em（= LINE_FACTOR）
#     下标 `$\omega_{0}$`               13.5 pt      1.35 em
#     根号 `$\sqrt{k}$`                 15.5 pt      1.35 em
#     分式 `$\frac{c}{2m}$`             24.0 pt      2.10 em
#     分式（带上下标）                   26.5/28.5 pt 2.45 em
#     根号套分式                        42.5 pt      3.65 em
#     大算子带上下限 `$\sum_{i}^{n}$`    39.0 pt      3.35 em
#
#    模型取值都比实测**留了余量**（判宁可偏松，不要让真溢出被淹没）。
#
_MATH_FRAC = re.compile(r"\\(?:dfrac|tfrac|frac)\b")
_MATH_SQRT = re.compile(r"\\sqrt\b")
_MATH_BIGOP = re.compile(r"\\(?:sum|prod|int|lim)\b")


def _brace_args(s, start):
    """从 s[start] 处的 `{` 开始，取出配对花括号里的内容。"""
    if start >= len(s) or s[start] != "{":
        return None, start
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1:i], i + 1
    return None, len(s)


def _sqrt_args(latex):
    r"""`\sqrt{...}` 的参数列表（可能有多个根号）。"""
    out = []
    s = str(latex or "")
    for m in _MATH_SQRT.finditer(s):
        i = m.end()
        while i < len(s) and s[i] in " \t":
            i += 1
        # 跳过可选的 [n] 指数
        if i < len(s) and s[i] == "[":
            j = s.find("]", i)
            if j > 0:
                i = j + 1
        arg, _end = _brace_args(s, i)
        if arg is not None:
            out.append(arg)
    return out


def _frac_args(s):
    """`\frac{..}{..}` 的分子、分母参数列表。"""
    out = []
    for m in _MATH_FRAC.finditer(s):
        i = m.end()
        for _ in range(2):            # 分子、分母两个参数
            arg, nxt = _brace_args(s, i)
            if arg is None:
                break
            out.append(arg)
            i = nxt
    return out


def math_height_em(latex):
    r"""一个公式渲染后的**高度**（以 em 计，即字号的倍数）。

    🔴 为什么要单独量高度：公式的源码长度与它的**墨迹高**完全不成比例 ——
       `$\sqrt{\frac{k}{m}}$` 源码 20 个字符，印出来却高 39.5pt（12pt 时）。
       按源码量高度 ⇒ 公式越界到下一行 ⇒ 被下一行的色块盖掉。

    结构 → 高度（em）：
      · 基准（无高结构）      1.35（= LINE_FACTOR，与普通文字行同高）
      · 分式 `\frac`          2.10（带上下标 2.45）
      · 根号套分式            3.65
      · 大算子带上下限        3.35
    """
    s = str(latex or "")
    if not s.strip():
        return LINE_FACTOR
    em = LINE_FACTOR
    sqrt_args = _sqrt_args(s)
    frac_in_sqrt = any(_MATH_FRAC.search(a) for a in sqrt_args)
    if _MATH_FRAC.search(s):
        if frac_in_sqrt:
            em = max(em, 3.65)
        else:
            # 分子/分母带上下标 ⇒ 那一栏还要再高一点（实测 26.5 / 28.5 pt）
            has_script = any("_" in a or "^" in a for a in _frac_args(s))
            em = max(em, 2.45 if has_script else 2.10)
    if _MATH_BIGOP.search(s) and ("_" in s or "^" in s):
        em = max(em, 3.35)
    return em


def math_height_pt(latex, font_size):
    """公式渲染高度（磅）。"""
    return math_height_em(latex) * float(font_size)


def paragraph_height(text, box_w, font_size, level=0):
    """一段文字占多高（磅）—— **公式感知**。

    🔴 文字行数按**宽度**算；行高按**内容**算：
       段落里只要有一个高结构（分式 / 根式），**含它的那一行**就会变高。
       算式：`总高 = 文字总高 − 单行高 + max(单行高, 公式高)`。
    """
    base = text_height(font_size, 1)
    lines = lines_for(text, box_w, font_size, level)
    need = text_height(font_size, lines)
    mh = 0.0
    for is_math, payload in split_math(text):
        if is_math:
            mh = max(mh, math_height_pt(payload, font_size))
    return float(need - base + max(base, mh))


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


def _free_slot(name, kind, x, y, w, h, **over):
    """凭空造一个槽位（几何不在原型表里的：卡片网格、表格单元……）。"""
    g = {"kind": kind, "name": name, "x": x, "y": y, "w": w, "h": h}
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

    🔴 高度按**公式感知**的口径算（`paragraph_height`）：
       分式、根式比普通文字高得多，只按「行数 × 行高」算 ⇒ 表格单元格里
       的公式会被 PowerPoint 裁掉（实测：`√(k/m)` 的分母被切没了），
       而判据还说「装得下」。
    """
    need = 0.0
    for p in paras or []:
        sz = int(p.get("sz") or SIZES["body"])
        text = p.get("text", "")
        if p.get("runs"):
            text = "".join(str(r.get("text", "")) for r in p["runs"])
        need += paragraph_height(text, box_w, sz, int(p.get("level", 0)))
        need += float(p.get("spc_before") or 0.0)
    return need


# ─────────────────────────────────────────────────────────────────
# 「标签：说明」拆分
#
# 🔴 这条规则**不新增任何事实**：只是把已有的要点文字按第一个全角冒号
#    拆成"标签"与"说明"两段，分别用不同字号/颜色呈现。
#    拆分点找不到就原样返回 —— **绝不猜、绝不补**。
# ─────────────────────────────────────────────────────────────────
def split_label(text):
    """拆成 (标签, 说明)。没有全角冒号 ⇒ (原文, "")。"""
    s = str(text or "")
    i = s.find(LABEL_SEP)
    if i <= 0:
        return (s, "")
    return (s[:i], s[i + 1:])


def cards_from_bullets(bullets):
    """要点 → [(卡片标题, 卡片正文行)]；不适合做卡片时返回 None。

    规则（**版式规则，写在这里，不散在调用方**）：
    * 每条一级要点 = 一张卡片；
    * 要点里有「：」⇒ 冒号前是**标签**（做卡片标题），冒号后是**说明**（做正文）；
    * 没有「：」⇒ 整条要点做卡片标题（**一个字不改**，只是加粗上色）；
    * 二级要点挂到上一张卡片的正文里。

    🔴 这条规则**不新增任何事实**：只把已有的字按原样重新分组。
       渲染器与判据看到的必须是同一个判定。
    """
    if not bullets:
        return None
    cards = []
    for b in bullets:
        if isinstance(b, str):
            text, level = b, 0
        else:
            text, level = str(b.get("text", "")), int(b.get("level", 0))
        if level == 0:
            t, d = split_label(text)
            cards.append([t, [d] if d else []])
        else:
            if not cards:
                return None
            cards[-1][1].append(text)
    return [(t, b) for t, b in cards]


def _card_pars(body_lines, sz, color="body", bullet=False, bullet_color=None):
    """卡片正文 → 段落规格。

    🔴 卡片正文默认**不带圆点**（卡片标题已经在承担"分层"这件事）；
       两栏版式是陈述列表，要圆点 —— 由调用方显式打开。
    """
    out = []
    for i, t in enumerate(body_lines or []):
        out.append({"text": t, "sz": sz, "level": 0,
                    "spc_before": 0.0 if i == 0 else 4.0,
                    "bullet": bullet,
                    "bullet_color": bullet_color or color,
                    "color": color, "align": "l", "bold": False})
    return out


# ─────────────────────────────────────────────────────────────────
# 卡片
# ─────────────────────────────────────────────────────────────────
def _card_pad_x(cols):
    return CARD_PAD_X_NARROW if cols >= 4 else CARD_PAD_X


def _card_inner_w(w, cols):
    return max(w - 2 * _card_pad_x(cols), 1.0)


def _card_content_h(title, body_paras, inner_w):
    """一张卡片的内容高度（不含上下内边距与顶部色条）。"""
    need = 0.0
    if title:
        # 🔴 用 `paragraph_height`（**公式感知**），不是 `text_height` ——
        #    卡片标题里放分式时，它比一行文字高得多（实测 2.10 em）。
        need += paragraph_height(title, inner_w, SIZES["card_title"]) + TITLE_GAP
    if body_paras:
        need += _paras_need(body_paras, inner_w)
    return need


def _card_slots(name, x, y, w, h, accent, tint, deep, cols,
                title="", body_lines=None, badge=None, bullet=False):
    """一张卡片的全部槽位。

    槽位顺序 = 绘制顺序（后者盖在前者之上）：
    极浅底 → 顶部色条 → 徽章 → 徽章文字 → 标题 → 正文。

    🔴 内容在卡片里**垂直居中**：卡片高度由整行统一决定，
       内容少的时候居中比顶对齐好看，也更像参考稿的"概念块"。
    """
    pad = _card_pad_x(cols)
    out = []
    out.append(_free_slot(name + "Fill", "rect", x, y, w, h, color=tint))
    out.append(_free_slot(name + "Bar", "rect", x, y, w, CARD_BAR_H, color=accent))

    inner_x = x + pad
    inner_w = _card_inner_w(w, cols)
    content_x = inner_x
    content_w = inner_w

    if badge:
        content_x = inner_x + BADGE_D + 12.0
        content_w = max(content_w - BADGE_D - 12.0, 1.0)

    title_h = 0.0
    if title:
        # 🔴 公式感知：标题里放了分式，标题框必须按**公式高度**算，
        #    否则框只有一行文字那么高 ⇒ 公式越界 ⇒ 被下一块色块盖掉。
        title_h = paragraph_height(title, content_w, SIZES["card_title"])
    body_pars = []
    body_h = 0.0
    if body_lines:
        body_pars = _card_pars(body_lines, SIZES["body"], COLORS["body"],
                                bullet=bullet, bullet_color=accent)
        body_h = _paras_need(body_pars, content_w)

    content_h = title_h + body_h
    if title and body_pars:
        content_h += TITLE_GAP
    # 🔴 徽章与内容是**左右并排**（徽章在左、正文在右），
    #    所以徽章**不占正文的高度**；整组高度取两者较大值。
    group_h = max(content_h, BADGE_D) if badge else content_h
    # 🔴 内容**顶对齐**（不是垂直居中）：参考课件的卡片内容都贴着卡顶，
    #    这样同一行几张卡的标题落在**同一条基线**上；居中会让每张卡各飘各的。
    cy = y + CARD_BAR_H + CARD_PAD_Y

    if badge:
        badge_y = cy + max(0.0, (content_h - BADGE_D) / 2.0)
        out.append(_free_slot(name + "Badge", "ellipse", inner_x, badge_y,
                              BADGE_D, BADGE_D, color=accent))
        out.append(_free_slot(name + "BadgeText", "text", inner_x, badge_y,
                              BADGE_D, BADGE_D, sz=SIZES["badge"], bold=True,
                              color="on_accent", align="ctr", anchor="ctr",
                              paras=[{"text": badge, "sz": SIZES["badge"],
                                      "bold": True, "color": "on_accent",
                                      "align": "ctr", "bullet": False}]))

    if title:
        out.append(_free_slot(name + "Title", "text", content_x, cy, content_w,
                              title_h, sz=SIZES["card_title"], bold=True,
                              color=deep, align="l",
                              paras=[{"text": title, "sz": SIZES["card_title"],
                                      "bold": True, "color": deep,
                                      "align": "l", "bullet": False}]))
        cy += title_h + TITLE_GAP

    if body_pars:
        avail = max(y + h - CARD_PAD_Y - cy, 0.0)
        out.append(_free_slot(name + "Body", "text", content_x, cy, content_w,
                              avail, sz=SIZES["body"], paras=body_pars))
    return out


def _grid_shape(n):
    """n 张卡片 → (列数, 行数)。"""
    if n <= 2:
        return (max(n, 1), 1)
    if n == 3:
        return (3, 1)
    if n == 4:
        return (2, 2)
    if n == 5:
        return (5, 1)
    if n == 6:
        return (3, 2)
    cols = 3
    return (cols, (n + cols - 1) // cols)


def _card_grid(cards, pair):
    """卡片网格的槽位。

    🔴 卡片高度**按内容算**，再夹在 [最小高, 本行可用高] 之间：
       内容超出可用高 ⇒ 卡片被压到可用高 ⇒ **溢出判据会报出来**，
       而不是让 PowerPoint 悄悄缩字号。
    """
    n = len(cards)
    cols, rows = _grid_shape(n)
    gap = COL_GAP
    card_w = (CONTENT_W - (cols - 1) * gap) / float(cols)
    row_h = (BODY_H - (rows - 1) * gap) / float(rows)
    inner_w = _card_inner_w(card_w, cols)

    need_h = []
    for t, bl in cards:
        body = _card_pars(bl, SIZES["body"], COLORS["body"]) if bl else []
        need_h.append(CARD_BAR_H + 2 * CARD_PAD_Y +
                      _card_content_h(t, body, inner_w))

    # 🔴 卡片高度下限跟着**版心高度**走：内容少的页也不塌成一条细带，
    #    否则整页的空白会全堆在底部（参考稿里卡片是占住版心的）。
    min_h = max(CARD_MIN_H, row_h * 0.55)

    out = []
    for idx, (t, bl) in enumerate(cards):
        r = idx // cols
        c = idx % cols
        x = CANVAS["margin"] + c * (card_w + gap)
        y = CANVAS["body_top"] + r * (row_h + gap)
        row_need = max(need_h[r * cols:(r + 1) * cols] or [0.0])
        h = max(min_h, min(row_h, row_need))
        out.extend(_card_slots("Card%d" % (idx + 1), x, y, card_w, h,
                                pair["accent"], pair["tint"], pair["deep"], cols,
                                title=t, body_lines=bl))
    return out


def _block_slots(bullets, pair):
    """左色条块（**保留的备选版式**：要点带二级层级、无法拆成卡片时用）。

    几何取自参考课件第 2 页：左侧 5pt 色条 + 浅底 + 圆点要点。
    块宽按**文字实际宽度**估（不做满宽），与参考稿一致。
    """
    bp = _bullet_pars(bullets, SIZES["body"], SIZES["body_l2"],
                      color=COLORS["body"], bullet_color=pair["accent"])
    inner_w = CONTENT_W - 5.0 - 22.0 - 16.0
    need = _paras_need(bp, inner_w)
    text_w = 0.0
    for p in bp:
        text_w = max(text_w, text_width_pt(p.get("text", ""), p.get("sz", 12)))
    block_w = min(CONTENT_W, max(320.0, text_w + 5.0 + 22.0 + 16.0))
    block_h = max(CARD_MIN_H, min(BODY_H, need + 2 * CARD_PAD_Y))
    out = [_free_slot("BlockFill", "rect", CANVAS["margin"], CANVAS["body_top"],
                      block_w, block_h, color=pair["tint"]),
           _free_slot("BlockBar", "rect", CANVAS["margin"], CANVAS["body_top"],
                      5.0, block_h, color=pair["accent"]),
           _free_slot("BlockBody", "text", CANVAS["margin"] + 5.0 + 22.0,
                      CANVAS["body_top"] + CARD_PAD_Y,
                      block_w - 5.0 - 22.0 - 16.0,
                      max(block_h - 2 * CARD_PAD_Y, 0.0),
                      sz=SIZES["body"], paras=bp)]
    return out


def _two_column_slots(bullets, pair):
    """两栏：两张卡片，各带**圆形编号徽章**（参考稿第 1 页）。"""
    left, right = _split_columns(bullets)
    bl = [b if isinstance(b, str) else str(b.get("text", "")) for b in left]
    br = [b if isinstance(b, str) else str(b.get("text", "")) for b in right]
    card_w = (CONTENT_W - COL_GAP) / 2.0
    inner_w = _card_inner_w(card_w, 2) - BADGE_D - 12.0
    need = max(_paras_need(_card_pars(bl, SIZES["body"], COLORS["body"]),
                            inner_w),
               _paras_need(_card_pars(br, SIZES["body"], COLORS["body"]),
                            inner_w))
    card_h = max(max(CARD_MIN_H, BODY_H * 0.55),
                 min(BODY_H, need + CARD_BAR_H + 2 * CARD_PAD_Y))
    out = []
    out.extend(_card_slots("ColLeft", CANVAS["margin"], CANVAS["body_top"],
                            card_w, card_h, pair["accent"], pair["tint"],
                            pair["deep"], 2, body_lines=bl, badge="01",
                            bullet=True))
    out.extend(_card_slots("ColRight", CANVAS["margin"] + card_w + COL_GAP,
                            CANVAS["body_top"], card_w, card_h,
                            pair["accent2"], pair["tint2"], pair["deep2"], 2,
                            body_lines=br, badge="02", bullet=True))
    return out


def _table_geometry(tb):
    """表格的几何：列宽、表头高、数据行高。**几何的单一出处**。

    🔴 数据行高为什么**不是固定值**：
       单元格里的**真公式**（分式 / 根式）比文字高得多 ——
       实测 12pt 下 `√(k/m)` 的墨迹高 39.5pt，而单元格的文字槽只有 20pt。
       行高固定 ⇒ 公式被 PowerPoint **裁掉**（分母直接不见了），
       同时 autofit 把同一段里的普通文字**悄悄缩小**。

       所以行高改成：**下限 + 按内容撑高**。
         · 纯文字表格 ⇒ 行高仍是 30pt（与从前**逐字节相同**）；
         · 有公式的表格 ⇒ 行高统一取「所有单元格里最高的那个」，
           表格才不会被切，且仍然是一张**等高行**的表（不是参差的）。

    🔴 溢出判据没有因此作废：判据从「单元格里装不装得下」
       换成「**整张表放不放得进正文区**」（见 `overflow`）。
       表格放不下 ⇒ 报错，而不是让 PowerPoint 悄悄缩字号。
    """
    header = [str(h or "") for h in (tb.get("header") or [])]
    rows = tb.get("rows") or []
    ncols = len(header)
    for r in rows:
        ncols = max(ncols, len(r or []))
    if ncols < 1:
        return None
    if ncols == 1:
        ratios = [1.0]
    elif ncols == 2:
        ratios = [0.34, 0.66]
    else:
        ratios = [0.24] + [(0.76 / (ncols - 1))] * (ncols - 1)

    xs = []
    acc = CANVAS["margin"]
    for r in ratios:
        xs.append((acc, CONTENT_W * r))
        acc += CONTENT_W * r

    def cell_need(text, inner_w, sz):
        return paragraph_height(text, inner_w, sz, 0)

    # 表头行高
    head_need = 0.0
    for i, htxt in enumerate(header):
        cx, cw = xs[i]
        head_need = max(head_need, cell_need(htxt, cw - 2 * TABLE_HEAD_PAD,
                                              SIZES["body"]))
    head_h = max(TABLE_HEAD_H, head_need + 2 * TABLE_HEAD_PAD)

    # 数据行高（**所有行统一**）
    row_need = 0.0
    for r, row in enumerate(rows):
        for i in range(ncols):
            cx, cw = xs[i]
            cell = ""
            if i < len(row or []):
                cell = str(row[i] or "")
            row_need = max(row_need, cell_need(cell, cw - 2 * TABLE_CELL_PAD,
                                                SIZES["body"]))
    row_h = max(TABLE_ROW_H, row_need + 2 * TABLE_CELL_PAD)

    return {"header": header, "rows": rows, "ncols": ncols, "xs": xs,
            "head_h": head_h, "row_h": row_h,
            "total_h": head_h + len(rows) * row_h}


def _table_slots(slide):
    """表格版式：深蓝表头 + 斑马纹行 + 首列粗体。

    🔴 行高来自 `_table_geometry`（**几何的单一出处**）：
       纯文字表格仍是 30pt；装了分式/根式的表格会等高撑开，
       公式不再被裁。表格整体放不下正文区时，由 `overflow` 报出来。
    """
    tb = slide.get("table") or {}
    g = _table_geometry(tb)
    if not g:
        return []
    header = g["header"]
    rows = g["rows"]
    xs = g["xs"]
    head_h = g["head_h"]
    row_h = g["row_h"]

    out = []
    y = CANVAS["body_top"]
    for i, htxt in enumerate(header):
        cx, cw = xs[i]
        color = COLORS["table_head"] if i == 0 else COLORS["table_head2"]
        out.append(_free_slot("Head%d" % i, "rect", cx, y, cw, head_h,
                              color=color))
        out.append(_free_slot("HeadText%d" % i, "text", cx + TABLE_HEAD_PAD,
                              y + TABLE_HEAD_PAD,
                              cw - 2 * TABLE_HEAD_PAD,
                              head_h - 2 * TABLE_HEAD_PAD,
                              sz=SIZES["body"],
                              bold=True, color="on_accent", align="ctr",
                              paras=[{"text": htxt, "sz": SIZES["body"],
                                      "bold": True, "color": "on_accent",
                                      "align": "ctr", "bullet": False}]))
    y += head_h
    for r, row in enumerate(rows):
        for i in range(g["ncols"]):
            cx, cw = xs[i]
            if i == 0:
                fill = COLORS["paper"]
                txt_color = COLORS["ink"]
                bold = True
            else:
                fill = (COLORS["table_zebra"] if r % 2 == 0
                        else COLORS["table_zebra_soft"])
                txt_color = COLORS["body"]
                bold = False
            cell = ""
            if i < len(row or []):
                cell = str(row[i] or "")
            out.append(_free_slot("Cell%d_%d" % (r, i), "rect", cx, y, cw,
                                  row_h, color=fill))
            out.append(_free_slot("CellText%d_%d" % (r, i), "text",
                                  cx + TABLE_CELL_PAD, y + TABLE_CELL_PAD,
                                  cw - 2 * TABLE_CELL_PAD,
                                  row_h - 2 * TABLE_CELL_PAD,
                                  sz=SIZES["body"], bold=bold, color=txt_color,
                                  align="ctr",
                                  paras=[{"text": cell, "sz": SIZES["body"],
                                          "bold": bold, "color": txt_color,
                                          "align": "ctr", "bullet": False}]))
        y += row_h
    return out


def _footer_slot(footer):
    """页脚 = 标签串：粗体前缀 + 灰色正文（参考稿「准备清单：场地｜白板｜…」）。

    🔴 拆点只取**第一个全角冒号**；没有就整条灰色。
       拆出来的两段**一字不改**，只是粗细不同。
    """
    label, rest = split_label(footer)
    if not rest:
        runs = [{"text": str(footer), "bold": False, "color": COLORS["muted"]}]
    else:
        runs = [{"text": label + LABEL_SEP, "bold": True, "color": COLORS["ink"]},
                {"text": rest, "bold": False, "color": COLORS["muted"]}]
    g = dict(geom("footer", "Footer"))
    g["kind"] = "text"
    g["name"] = "Footer"
    g["paras"] = [{"runs": runs, "sz": SIZES["footer"], "bullet": False,
                   "align": "l"}]
    return g


def _badge_block_slots(group, slide):
    """封面/分节页右上角的深色课时块（白字两行）。

    🔴 只有 spec 明确给了 `badge_label` 才画 —— **不猜时长、不猜学时**。
    """
    label = slide.get("badge_label")
    if not label:
        return []
    if isinstance(label, str):
        label = [label]
    lines = [str(x) for x in label if str(x).strip()]
    if not lines:
        return []
    out = [_rect_slot(group, "Badge", color=COLORS["badge_block"])]
    paras = []
    for i, t in enumerate(lines):
        paras.append({"text": t,
                      "sz": SIZES["block"] if i == 0 else SIZES["block2"],
                      "bold": i == 0, "color": "on_accent", "align": "l",
                      "bullet": False, "spc_before": 0.0 if i == 0 else 2.0})
    g = dict(geom(group, "BadgeText"))
    g["kind"] = "text"
    g["name"] = "BadgeText"
    g["paras"] = paras
    out.append(g)
    return out


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
        if title:
            out.append(_text_slot("title", "Title", title))
        if subtitle:
            out.append(_text_slot("title", "Subtitle", subtitle))
        out.append(dict(geom("title", "Rule"), kind="rule", name="Rule",
                        color=COLORS["rule_soft"]))
        out.extend(_badge_block_slots("title", slide))
        out.append(_rect_slot("title", "AccentStrip", color=pair["accent"]))
    elif layout == "section":
        if title:
            out.append(_text_slot("section", "Title", title))
        if subtitle:
            out.append(_text_slot("section", "Subtitle", subtitle))
        out.append(dict(geom("section", "Rule"), kind="rule", name="Rule",
                        color=pair["accent"]))
        out.extend(_badge_block_slots("section", slide))
        # 分节页也可以承载**模块卡**（议程页）：给了要点就排成卡片网格。
        cards = cards_from_bullets(bullets)
        if cards:
            out.extend(_card_grid(cards, pair))
        out.append(_rect_slot("section", "AccentStrip", color=pair["accent"]))
    elif layout == "quote":
        if title:
            out.append(_text_slot("quote", "Title", title))
        out.append(dict(geom("quote", "Rule"), kind="rule", name="Rule",
                        color=pair["accent"]))
        out.append(_rect_slot("quote", "Bar", color=pair["accent"]))
        if subtitle:
            out.append(_text_slot("quote", "Quote", subtitle))
    else:
        if title:
            out.append(_text_slot("content", "Title", title))
            if subtitle:
                out.append(_text_slot("content", "Eyebrow", subtitle))
            out.append(dict(geom("content", "Rule"), kind="rule", name="Rule",
                            color=pair["accent"]))
        if slide.get("table"):
            out.extend(_table_slots(slide))
        elif layout == "two-column":
            out.extend(_two_column_slots(bullets, pair))
        elif layout == "image-focus":
            img_h = BODY_H - (CAPTION_BAND if caption else 0.0)
            if image:
                pic = dict(geom("content", "Picture"))
                pic.update({"kind": "picture", "name": "Picture", "h": img_h,
                            "src": image})
                out.append(pic)
            if bullets:
                b = dict(geom("content", "Body") if "Body" in PROTOTYPES["content"]
                         else {"x": 42.5, "y": CANVAS["body_top"], "w": CONTENT_W,
                               "h": 30.0, "sz": SIZES["body"]})
                b.update({"kind": "text", "name": "Body",
                          "y": CANVAS["body_top"] + img_h + 8.0, "h": 30.0,
                          "paras": _bullet_pars(bullets, SIZES["body"],
                                                SIZES["body_l2"],
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
            cards = cards_from_bullets(bullets)
            if cards:
                out.extend(_card_grid(cards, pair))
            elif bullets:
                out.extend(_block_slots(bullets, pair))

    if footer:
        out.append(_footer_slot(footer))
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
                if p.get("runs"):
                    preview = "".join(str(r.get("text", "")) for r in p["runs"])[:24]
                    break
            bad.append({"slot": slot.get("name", ""), "need": need, "have": have,
                        "over": need - have, "text": preview})
    # 🔴 表格页的判据在**整张表**这一层：
    #    单元格的行高是按内容撑出来的（`_table_geometry`），
    #    所以「单元格装不下」永远不会发生；真正会出问题的是
    #    **整张表比正文区还高** —— 那时必须报出来，
    #    而不是让 PowerPoint 把字悄悄缩掉。
    tb = slide.get("table")
    if isinstance(tb, dict) and (tb.get("rows") or []):
        g = _table_geometry(tb)
        if g and g["total_h"] > BODY_H + 0.5:
            bad.append({"slot": "Table", "need": g["total_h"], "have": BODY_H,
                        "over": g["total_h"] - BODY_H,
                        "text": "表格共 %d 行" % len(g["rows"])})
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
    # ② 装不下：正文页超长标题（40 字 ⇒ 24pt 下折成 2 行 ⇒ 65pt > 标题框 34pt）
    bad = {"layout": "bullets",
           "title": "周期信号可以拆成若干正弦波的叠加而这已经接近单行容量上限了所以标题必须拆",
           "bullets": [{"text": "要点一", "level": 0}],
           "notes": "讲稿"}
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
    # ⑤ 「标签：说明」拆分：只拆第一个全角冒号，且不丢字
    t, d = split_label("小振动：位移远小于场区尺度")
    if t != "小振动" or d != "位移远小于场区尺度":
        print("selftest: 标签拆分不对：%r / %r" % (t, d))
        return 2
    if split_label("没有标签")[1]:
        print("selftest: 没有标签的文本被凭空拆出了说明")
        return 2
    # ⑥ 卡片判定：一级要点 ⇒ 一张卡片；带「：」的拆成标题 + 正文
    c = cards_from_bullets([{"text": "甲"}, {"text": "乙"}])
    if c is None or c[0][0] != "甲" or c[0][1]:
        print("selftest: 无标签的要点没有变成标题式卡片")
        return 2
    c = cards_from_bullets([{"text": "甲：说明"}, {"text": "乙：说明"}])
    if c is None or c[0][0] != "甲" or c[0][1] != ["说明"]:
        print("selftest: 带标签的要点没有拆成标题 + 正文")
        return 2
    # ⑦ 表格几何：**行高按内容自适应**，但判据落在「整张表放不放得下」
    #    ⑦-1 纯文字表格的行高与从前完全一样（30pt）—— 不许被公式改动连累
    plain = {"layout": "bullets", "title": "表",
             "table": {"header": ["维度", "内容"], "rows": [["甲", "乙"]]},
             "notes": "讲稿"}
    g0 = _table_geometry(plain["table"])
    if g0["row_h"] != TABLE_ROW_H or g0["head_h"] != TABLE_HEAD_H:
        print("selftest: 纯文字表格的行高被改动了（%r / %r）"
              % (g0["row_h"], g0["head_h"]))
        return 2
    # ⑦-2 有分式 / 根式的表格：行高被撑高，且**公式必须装得进单元格的槽**
    #     （实测：12pt 的 √(k/m) 墨迹高 39.5pt，槽高 20pt ⇒ 分母被裁掉）
    hard = {"layout": "bullets", "title": "表",
            "table": {"header": ["参数", "含义"],
                      "rows": [[r"$\omega_{0} = \sqrt{\frac{k}{m}}$", "固有角频率"],
                               [r"$\gamma = \frac{c}{2m}$", "衰减速率"]]},
            "notes": "讲稿"}
    g1 = _table_geometry(hard["table"])
    if g1["row_h"] <= TABLE_ROW_H:
        print("selftest: 含公式的表格行高没有被撑开（%r）" % g1["row_h"])
        return 2
    slot_h = g1["row_h"] - 2 * TABLE_CELL_PAD
    for row in hard["table"]["rows"]:
        need = paragraph_height(row[0], g1["xs"][0][1] - 2 * TABLE_CELL_PAD,
                                SIZES["body"], 0)
        if need > slot_h + 0.5:
            print("selftest: 单元格里装不下公式（需要 %r，槽高 %r）"
                  % (need, slot_h))
            return 2
    # ⑦-3 行数多到整张表超过正文区 ⇒ 必须报出来（而不是让 PowerPoint 缩字号）
    tall = {"layout": "bullets", "title": "表",
            "table": {"header": ["参数", "含义"],
                      "rows": [[r"$\omega_{0} = \sqrt{\frac{k}{m}}$", "固有角频率"]] * 9},
            "notes": "讲稿"}
    ovs = overflow(tall)
    if not any(o["slot"] == "Table" for o in ovs):
        print("selftest: 表格比正文区高却没有被报出来")
        return 2
    # ⑦-4 含公式的表格**不该**被误报（表格放得下就是放得下）
    if [o for o in overflow(hard) if o["slot"] == "Table"]:
        print("selftest: 放得下的表格被误报为溢出")
        return 2
    print("selftest: 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(selftest())
