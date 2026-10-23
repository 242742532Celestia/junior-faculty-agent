#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""slide_spec_lint.py —— 幻灯片规格的**教学规范**审查（纯标准库）

为什么要有这个
--------------
`build_pptx.py` 负责「能生成、能打开」；这个脚本负责「**生成的是不是一份能用的
教学幻灯片**」。两者是不同的失败模式：

* PPTX 能打开，但一页塞了 9 条要点、标题写"如上所述"、讲稿一个字没有 ——
  文件技术上没毛病，作为教学材料是废的。
* 幻灯片写的是"本节课我们学习……"，看着像课件，其实只是把大纲抄成了列表。

所以这个 lint 判的是**教学规范**，不是格式。

检查项
------
编号即检查项 id，`--json` 输出会带上，便于脚本化消费。

| 级别 | 含义 |
|---|---|
| ERROR | 必须改。不改这份幻灯片不成立。 |
| WARN  | 建议改。多数情况下应改。 |
| INFO  | 提示。人工判断。 |

判据来源
--------
* **认知负荷**：一页同时呈现的要点越多，讲座式幻灯片上的工作记忆负担越重
  （Mayer 多媒体学习原则 + 中国高校课堂常见问题）。
* **媒介功能错配**：幻灯片是**并置**媒介，"如上图所示"这类线性指代在并置版面里失效。
* **讲稿分离**：幻灯片给观众看，讲稿给讲授者用。把讲稿写进正文 = 观众在读你念的话。
* **不编造**：本仓库的硬纪律之一 —— 交付物里不许留占位符（待补/XXX/TBD），
  涉及外部事实的页必须能追溯到来源。

    python slide_spec_lint.py spec.json
    python slide_spec_lint.py spec.json --json
    python slide_spec_lint.py spec.json --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# 版式几何与文字度量在 slide_layouts.py 里（**唯一一份**）——
# 渲染器（build_pptx.py）按它画，本判据按它量，两边不会漂移。
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import slide_layouts as L  # noqa: E402

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"

# 判据阈值（全部是**教学经验值**，不是普适定律；可在 --thresholds 里覆盖）
THRESHOLDS = {
    "max_bullets": 6,          # 一页最多几条要点
    "max_bullet_chars": 30,    # 单条要点最多几个字符
    "max_title_chars": 20,     # 页面标题最多几个字符
    "max_body_chars": 120,     # 一页正文最多几个字符
    "max_image_bullets": 4,    # 图 + 要点时，���点最多几条
    "min_notes_chars": 10,     # 讲稿最少几个字符
    "max_notes_chars": 800,    # 讲稿最多几个字符
}

# 占位符残留 —— 交付物里出现即为 ERROR
PLACEHOLDER = re.compile(
    r"(待补|待定|待填|待核|待确认|TBD|TODO|FIXME|XXX+|xxxx|Lorem ipsum|占位|示例文字)")

# 线性指代 —— 在并置媒介里失效
LINEAR_REF = re.compile(r"(如上图|如下图|见下图|如上表|见上表|如前图|如前所述|如下图所示)")

# 空泛的页面标题 —— 只是分类，不是断言
VAGUE_TITLE = re.compile(
    r"^(其他|其它|更多|概况|简介|介绍|总结|小结|要点|内容|问题|思考|练习|作业|案例|流程|方法|背景|意义)[\s　]*$")

# 需要来源标注的信号词：出现即认为该页含外部事实或数据
FACT_SIGNAL = re.compile(
    r"(\d+(\.\d+)?\s*%|研究|数据|统计|调查|文献|实验|结果|表明|证明|显示|来自|数据来源)")

TEXT_LAYOUTS = ("bullets", "two-column", "image-focus", "blank")


class Finding(object):
    __slots__ = ("code", "level", "slide", "msg")

    def __init__(self, code, level, slide, msg):
        self.code = code
        self.level = level
        self.slide = slide
        self.msg = msg

    def as_dict(self):
        return {"code": self.code, "level": self.level,
                "slide": self.slide, "message": self.msg}

    def __str__(self):
        loc = ("第 %d 页" % self.slide) if self.slide else "整体"
        return "[%s] %s %s：%s" % (self.level, self.code, loc, self.msg)


def _bullets_of(sld):
    bl = sld.get("bullets") or []
    out = []
    for b in bl:
        if isinstance(b, str):
            out.append((b, 0))
        elif isinstance(b, dict):
            out.append((str(b.get("text", "")), int(b.get("level", 0))))
    return out


def _chars(s):
    """字符数：中文按 1 个字算，忽略空白。"""
    return len(re.sub(r"\s", "", s or ""))


def lint(spec, th=None):
    """对一份规格做教学规范审查，返回 Finding 列表。"""
    t = dict(THRESHOLDS)
    if th:
        t.update(th)
    out = []
    slides = spec.get("slides") or []
    meta = spec.get("meta") or {}

    def add(code, level, slide, msg):
        out.append(Finding(code, level, slide, msg))

    # 整份：占位符残留
    for i, sld in enumerate(slides, start=1):
        for field in ("title", "subtitle", "footer", "caption"):
            v = sld.get(field)
            if v and PLACEHOLDER.search(str(v)):
                add("L14", ERROR, i, "%s 字段留有占位符：%r" % (field, str(v)[:40]))
        for j, (text, _lv) in enumerate(_bullets_of(sld)):
            if PLACEHOLDER.search(text):
                add("L14", ERROR, i, "第 %d 条要点留有占位符：%r" % (j + 1, text[:40]))
        notes = sld.get("notes")
        if notes and PLACEHOLDER.search(str(notes)):
            add("L14", ERROR, i, "讲稿留有占位符")
    if PLACEHOLDER.search(str(meta.get("title", ""))):
        add("L14", ERROR, None, "meta.title 留有占位符")

    # 整份：封面布局唯一
    title_pages = [i for i, s in enumerate(slides, start=1)
                   if s.get("layout") == "title"]
    if len(title_pages) > 1:
        add("L07", ERROR, None,
            "封面（title 布局）出现 %d 次（第 %s 页）；封面只能有一个，"
            "章节过渡请用 section 布局" % (len(title_pages), "、".join(map(str, title_pages))))
    elif title_pages and title_pages[0] != 1:
        add("L07", ERROR, title_pages[0], "封面不在第 1 页，实际在第 %d 页" % title_pages[0])

    for i, sld in enumerate(slides, start=1):
        layout = sld.get("layout", "bullets")
        title = str(sld.get("title", "") or "")
        notes = str(sld.get("notes", "") or "")
        footer = str(sld.get("footer", "") or "")
        bullets = _bullets_of(sld)
        body_chars = sum(_chars(t_) for t_, _lv in bullets)

        # L05 正文页必须有标题
        if layout in TEXT_LAYOUTS and not title.strip():
            add("L05", ERROR, i, "正文页没有标题；标题要承担「这一页在讲什么」的断言")
        # L03 标题长度
        if title and _chars(title) > t["max_title_chars"]:
            add("L03", WARN, i, "标题 %d 字，超过 %d 字上限"
                % (_chars(title), t["max_title_chars"]))
        # L11 空泛标题
        if title and VAGUE_TITLE.match(title.strip()):
            add("L11", INFO, i, "标题「%s」是分类词不是断言；"
                "改成「这一页要让学生知道什么」更好" % title.strip())
        # L01 要点数
        if len(bullets) > t["max_bullets"]:
            add("L01", ERROR, i, "有 %d 条要点，超过 %d 条上限；"
                "请拆页或转成讲稿" % (len(bullets), t["max_bullets"]))
        # L02 单条长度
        for j, (text, _lv) in enumerate(bullets):
            if _chars(text) > t["max_bullet_chars"]:
                add("L02", WARN, i, "第 %d 条要点 %d 字，超过 %d 字；"
                    "长句应进讲稿" % (j + 1, _chars(text), t["max_bullet_chars"]))
        # L04 讲稿
        if layout in ("bullets", "two-column", "image-focus"):
            if not notes.strip():
                add("L04", ERROR, i, "正文页没有讲稿备注；"
                    "幻灯片给观众看，讲稿给讲授者用，两者要分开")
            else:
                nc = _chars(notes)
                if nc < t["min_notes_chars"]:
                    add("L12", WARN, i, "讲稿仅 %d 字，可能不足以支撑 %d 条要点的口述"
                        % (nc, len(bullets)))
                elif nc > t["max_notes_chars"]:
                    add("L12", INFO, i, "讲稿 %d 字，建议拆成多页" % nc)
        # L04 正文总字数
        if body_chars > t["max_body_chars"]:
            add("L04", WARN, i, "正文合计 %d 字，超过 %d 字上限"
                % (body_chars, t["max_body_chars"]))
        # L06 线性指代
        blob = title + " " + " ".join(t_ for t_, _ in bullets)
        m = LINEAR_REF.search(blob)
        if m:
            add("L06", WARN, i, "出现「%s」；幻灯片是并置版面，"
                "线性指代在观众眼里不成立" % m.group(0))
        # L08 来源标注
        if FACT_SIGNAL.search(blob) and not footer.strip():
            add("L08", WARN, i, "本页出现事实/数据类表述但没有来源标注（footer）")
        # L09 空白页
        if layout in ("bullets", "two-column", "image-focus") \
                and not bullets and not sld.get("image"):
            add("L09", WARN, i, "既没有要点也没有图片，等于空白页")
        # L10 图 + 要点
        if sld.get("image") and len(bullets) > t["max_image_bullets"]:
            add("L10", WARN, i, "图 + %d 条要点，超过 %d 条；"
                "图会分走注意力" % (len(bullets), t["max_image_bullets"]))
        # 讲稿里出现与本页要点无关的占位
        if sld.get("image") and not sld.get("caption"):
            add("L10", INFO, i, "有图但没有图注；图注是讲稿的一部分")

        # L15 文字装不装得下 —— **几何判据**，不是字数估计
        # 🔴 为什么必须是几何：PowerPoint 的文本框带 `normAutofit`，
        #    文字超出框高时不会"露出来"，而是**自动缩小字号** ——
        #    于是"设计的 24pt"实际变成 18pt，而版面看起来还是正常的。
        #    这是静默失效，光看字数（L02/L04）看不出来。
        for ov in L.overflow(sld):
            add("L15", ERROR, i,
                "%s 槽位装不下：文字需要约 %d pt，框高只有 %d pt"
                "（超出 %d pt）。PowerPoint 会自动缩小这行字，"
                "实际字号会小于设计值 —— 请缩短文字或降低字号：%r"
                % (ov["slot"], int(ov["need"] + 0.5), int(ov["have"]),
                   int(ov["over"] + 0.5), ov["text"]))

    return out


def load_spec(path):
    if not os.path.isfile(path):
        raise SystemExit("找不到规格文件：%s" % path)
    with open(path, encoding="utf-8", newline="") as f:
        return json.load(f)


def selftest():
    """内置自检：构造已知问题与已知良好的样例，确认判据会响、且不会误报。"""
    bad = {
        "meta": {"title": "待补"},
        "slides": [
            {"layout": "title", "title": "封面"},
            {"layout": "title", "title": "又一个封面"},
            # 21 字封面标题：字数合规（L03 ≤20 不报），但几何上放不下
            {"layout": "title", "title": "数字图像处理课程第四章图像增强方法与工程"},
            {"layout": "bullets", "title": "要点",
             "bullets": [{"text": "占位文字待补", "level": 0}] * 8,
             "notes": ""},
            {"layout": "bullets", "title": "如上图所示",
             "bullets": [{"text": "数据表明占比 %d" % k, "level": 0} for k in range(3)]},
            {"layout": "bullets",
             "bullets": [{"text": "没有标题的正文页", "level": 0}]},
        ],
    }
    codes = set(f.code for f in lint(bad))
    for expect in ("L01", "L04", "L05", "L06", "L07", "L08", "L14", "L15"):
        if expect not in codes:
            print("selftest: 期望命中 %s，实际命中 %s" % (expect, sorted(codes)))
            return 2
    good = {
        "meta": {"title": "傅里叶变换的物理意义"},
        "slides": [
            {"layout": "title", "title": "傅里叶变换的物理意义", "subtitle": "物理系"},
            {"layout": "bullets", "title": "周期信号可以拆成若干正弦波的叠加",
             "bullets": [{"text": "叠加就是相加", "level": 0},
                         {"text": "每一路有独立的频率与幅值", "level": 1}],
             "notes": "先问学生：一根弦振动时它在做什么？"
                      "再用两个音叉叠加的演示把直觉建立起来，"
                      "最后才给出叠加律的数学表述。",
             "footer": "示意图为作者自绘"},
            {"layout": "section", "title": "应用", "subtitle": "两个例子"},
        ],
    }
    g = lint(good)
    errs = [f for f in g if f.level == ERROR]
    if errs:
        for f in errs:
            print("selftest: 良好样例被误报 -> %s" % f)
        return 2
    print("selftest: 全部通过（坏样例命中 %s，良好样例零 ERROR）" % sorted(codes))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="幻灯片规格的教学规范审查")
    ap.add_argument("spec", nargs="?", help="幻灯片规格 JSON")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    ap.add_argument("--selftest", action="store_true", help="跑内置自检")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.spec:
        print("错误：必须给出规格文件，或用 --selftest", file=sys.stderr)
        return 1
    try:
        spec = load_spec(args.spec)
    except ValueError as e:
        print("规格文件不是合法 JSON：%s" % e, file=sys.stderr)
        return 1

    findings = lint(spec)
    errors = [f for f in findings if f.level == ERROR]
    warns = [f for f in findings if f.level == WARN]
    infos = [f for f in findings if f.level == INFO]

    if args.json:
        print(json.dumps({
            "file": args.spec,
            "counts": {"error": len(errors), "warn": len(warns), "info": len(infos)},
            "findings": [f.as_dict() for f in findings],
        }, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print(f)
        print("\n合计：ERROR %d，WARN %d，INFO %d" % (len(errors), len(warns), len(infos)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
