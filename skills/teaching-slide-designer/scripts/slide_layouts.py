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

坐标系
------
* 画布 960 × 540 pt（13.333 × 7.5 in，16:9），原点左上角
* 左边距 54 pt（0.75 in），内容宽 852 pt
* 内容区上边 135 pt，下边 45 pt ⇒ 正文可用高 360 pt
"""
from __future__ import annotations

import math
import os
import sys

# ─────────────────────────────────────────────────────────────────
# 画布与调色板
# ─────────────────────────────────────────────────────────────────
CANVAS = {
    "w": 960.0,          # 13.333 in（16:9）
    "h": 540.0,          # 7.5 in
    "margin": 54.0,      # 0.75 in
    "body_top": 135.0,   # 正文区上边
    "body_bottom": 45.0, # 正文区下边
}
CONTENT_W = CANVAS["w"] - 2 * CANVAS["margin"]            # 852
BODY_H = CANVAS["h"] - CANVAS["body_top"] - CANVAS["body_bottom"]   # 360

COL_GAP = 30.0
COL_W = (CONTENT_W - COL_GAP) // 2                        # 411
IMG_INSET = 60.0
IMG_W = CONTENT_W - 2 * IMG_INSET                         # 732
CAPTION_H = 30.0
CAPTION_BAND = 50.0                                      # 有图注时图片让出的高度

# 颜色（设计 token；渲染器与判据共用）
COLORS = {
    "ink": "1F2933",      # 主文字
    "muted": "5A6570",    # 次要文字
    "accent": "1B4965",   # 强调色
    "rule": "D5DBE1",     # 分隔线
    "paper": "FFFFFF",    # 背景
}

# 字号（磅）
SIZES = {
    "title": 40,        # 正文页标题
    "title_center": 44, # 封面 / 章节页标题
    "subtitle": 24,
    "body": 24,
    "body_l2": 20,
    "quote": 28,
    "caption": 14,
    "footer": 12,
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
    12: {1: 17, 2: 33, 3: 49, 4: 65, 5: 81},
    14: {1: 19, 2: 38, 3: 57, 4: 76, 5: 95},
    20: {1: 27, 2: 54, 3: 81, 4: 108, 5: 135},
    24: {1: 33, 2: 65, 3: 98, 4: 130, 5: 162},
    28: {1: 38, 2: 76, 3: 114, 4: 152, 5: 189},
    40: {1: 54, 2: 108, 3: 162, 4: 216, 5: 270},
    44: {1: 60, 2: 119, 3: 179, 4: 238, 5: 297},
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
# ─────────────────────────────────────────────────────────────────
PROTOTYPES = {
    "title": {
        "Title": {"x": 54.0, "y": 210.0, "w": 852.0, "h": 90.0, "sz": 44,
                  "bold": True, "color": "accent", "align": "ctr"},
        "Subtitle": {"x": 54.0, "y": 310.0, "w": 852.0, "h": 60.0, "sz": 24,
                     "color": "muted", "align": "ctr"},
        "Rule": {"x": 338.0, "y": 290.0, "w": 284.0, "h": 2.0, "kind": "rule"},
    },
    "section": {
        "Title": {"x": 54.0, "y": 250.0, "w": 852.0, "h": 100.0, "sz": 44,
                  "bold": True, "color": "accent", "align": "ctr"},
        "Subtitle": {"x": 54.0, "y": 355.0, "w": 852.0, "h": 50.0, "sz": 24,
                     "color": "muted", "align": "ctr"},
    },
    "quote": {
        "Quote": {"x": 114.0, "y": 200.0, "w": 732.0, "h": 200.0, "sz": 28,
                  "color": "ink", "align": "ctr", "anchor": "ctr"},
        "Attribution": {"x": 114.0, "y": 410.0, "w": 732.0, "h": 40.0, "sz": 24,
                        "color": "muted", "align": "ctr"},
    },
    # bullets / two-column / image-focus / blank 共用的页眉区
    "content": {
        "Title": {"x": 54.0, "y": 40.0, "w": 852.0, "h": 60.0, "sz": 40,
                  "bold": True, "color": "ink", "align": "l"},
        "Rule": {"x": 54.0, "y": 112.0, "w": 852.0, "h": 2.0, "kind": "rule"},
        "Body": {"x": 54.0, "y": 135.0, "w": 852.0, "h": 360.0, "sz": 24},
        "BodyLeft": {"x": 54.0, "y": 135.0, "w": 411.0, "h": 360.0, "sz": 24},
        "BodyRight": {"x": 495.0, "y": 135.0, "w": 411.0, "h": 360.0, "sz": 24},
        "Picture": {"x": 114.0, "y": 135.0, "w": 732.0, "h": 360.0, "kind": "picture"},
        "Caption": {"x": 54.0, "y": 507.0, "w": 852.0, "h": 30.0, "sz": 14,
                    "color": "muted", "align": "ctr"},
    },
    # 所有版式共用的页脚
    "footer": {
        "Footer": {"x": 54.0, "y": 512.0, "w": 852.0, "h": 20.0, "sz": 12,
                   "color": "muted", "align": "l"},
    },
}

LAYOUTS = ("title", "bullets", "two-column", "image-focus", "quote", "section", "blank")


def geom(group, name):
    """取一个槽位的几何。group ∈ {title, section, quote, content, footer}。"""
    return PROTOTYPES[group][name]


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


def _bullet_pars(bullets, sz, sz_l2):
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
                    "color": "ink", "align": "l", "bold": False})
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

    if layout == "title":
        if title:
            out.append(_text_slot("title", "Title", title))
        if subtitle:
            out.append(_text_slot("title", "Subtitle", subtitle))
        out.append(dict(geom("title", "Rule"), kind="rule", name="Rule"))
    elif layout == "section":
        if title:
            out.append(_text_slot("section", "Title", title))
        if subtitle:
            out.append(_text_slot("section", "Subtitle", subtitle))
    elif layout == "quote":
        if title:
            out.append(_text_slot("quote", "Quote", title))
        if subtitle:
            out.append(_text_slot("quote", "Attribution", subtitle))
    else:
        if title:
            out.append(_text_slot("content", "Title", title))
            out.append(dict(geom("content", "Rule"), kind="rule", name="Rule"))
        if layout == "two-column":
            left, right = _split_columns(bullets)
            gl = dict(geom("content", "BodyLeft"))
            gl.update({"kind": "text", "name": "BodyLeft",
                       "paras": _bullet_pars(left, SIZES["body"], SIZES["body_l2"])})
            gr = dict(geom("content", "BodyRight"))
            gr.update({"kind": "text", "name": "BodyRight",
                       "paras": _bullet_pars(right, SIZES["body"], SIZES["body_l2"])})
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
                          "y": CANVAS["body_top"] + img_h + 10.0, "h": 40.0,
                          "paras": _bullet_pars(bullets, SIZES["body"], SIZES["body_l2"])})
                out.append(b)
            if caption:
                c = dict(geom("content", "Caption"))
                c.update({"kind": "text", "name": "Caption",
                          "y": CANVAS["body_top"] + img_h + 12.0,
                          "paras": [{"text": caption, "sz": SIZES["caption"],
                                     "bold": False, "color": "muted",
                                     "align": "ctr", "bullet": False}]})
                out.append(c)
        else:
            if bullets:
                b = dict(geom("content", "Body"))
                b.update({"kind": "text", "name": "Body",
                          "paras": _bullet_pars(bullets, SIZES["body"], SIZES["body_l2"])})
                out.append(b)

    if footer:
        out.append(_text_slot("footer", "Footer", footer))
    return out


# ─────────────────────────────────────────────────────────────────
# 溢出判定
# ─────────────────────────────────────────────────────────────────
def measure_slot(slot):
    """量一个文本槽位：需要多高、框有多高。"""
    need = 0.0
    for p in slot.get("paras") or []:
        sz = int(p.get("sz") or SIZES["body"])
        lines = lines_for(p.get("text", ""), slot.get("w", 0), sz,
                          int(p.get("level", 0)))
        need += text_height(sz, lines)
        need += float(p.get("spc_before") or 0.0)
    return need, float(slot.get("h") or 0.0)


def overflow(slide):
    """一页里所有**装不下**的文本槽位。

    返回 [{slot, need, have, over, text}]。
    🔴 装不下 ≠ 看不见：PowerPoint 的文本框带 `normAutofit`，
       文字放不下时会**自动缩小字号** —— 于是"设计的 24pt"实际变成 18pt，
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
    # ② 装不下：超长封面标题（44pt，20 字 = 880pt > 852pt → 两行 → 120pt > 90pt）
    bad = {"layout": "title", "title": "数字图像处理课程第四章图像增强方法与工程实践",
           "subtitle": "2 学时 · 从看不清到看得清"}
    if not overflow(bad):
        print("selftest: 超长封面标题没有被报出来")
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
            if n > 1 and tbl[n] <= tbl[n - 1]:
                print("selftest: 文字高度表不自洽：%dpt %d 行" % (sz, n))
                return 2
    # ④ 表必须覆盖原型表里用到的每一个字号（漏一档 = 某处退回现算，口径不一）
    used = set()
    for group in PROTOTYPES.values():
        for slot in group.values():
            if slot.get("sz"):
                used.add(int(slot["sz"]))
    missing = sorted(sz for sz in used if sz not in TEXT_HEIGHT)
    if missing:
        print("selftest: 文字高度表缺这些字号：%s" % missing)
        return 2
    print("selftest: 全部通过（已知溢出被报出 / 良好样例零误报 / 高度表与公式逐格相符）")
    return 0


if __name__ == "__main__":
    sys.exit(selftest())
