#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""outline.py —— **大纲先行层**：一份大纲 → 教案 / 课件（纯标准库）

为什么要有这一层
----------------
在本层之前，教案与课件是**两份各自写出来的规格**。它们要对齐，只能靠人（或
事后核对）把它们拉到一起 —— 于是"对齐"成了一个**守卫问题**：
今天教案改了第 3 环节，课件第 5 页还是旧文案，机器只能在事后发现。

本层把这件事**倒过来**：

    outline.json（唯一事实源）
            │
            ├──▶ 教案规格   （环节顺序、时间、目标绑定、意图）
            └──▶ 课件规格   （页面顺序、页面与环节的绑定、讲稿）

教案与课件**不再各自被写出来**，而是从同一份大纲**派生**出来的。
⇒ "教案与课件对不上"这个失败模式，在结构上**不可能发生**；
   真要改，改的是大纲一处，两边一起动。

对齐仍然是**可被检查的**（本仓库的纪律：判据必须能证伪），但它的形态变了：
守卫检查的是「派生结果 == 重新派生的结果」，而不是「两份文件碰巧一样」。

大纲的形状
----------
    meta        课程抬头（与教案抬头同一份）
    objectives  教学目标（3–5 条，每条绑定课程目标编号）
    modules[]   教学模块
      steps[]   教学环节（分钟 / 教师活动 / 学生活动 / 设计意图 / 对应目标）
        slides[] 这一环节配套的页面（内容 + 讲稿）
    deck        封面与目录页（不属于任何环节）

两条硬约束
----------
1. **每一页正文幻灯片必须挂在某个环节下**（可溯源）——
   课件页因此永远说得清"它在讲哪一步"。
2. **每个环节要么有配套页面，要么写明为什么没有**
   （`no_slide_reason`）—— 区分"这一环节本来就是学生活动"与"漏做课件"。

命令
----
    python demo/outline.py --spec demo/spec/outline.example.json
    python demo/outline.py --spec demo/spec/outline.example.json --check
    python demo/outline.py --spec demo/spec/outline.example.json --out demo/out

退出码：0 成功 / 1 参数或派生不一致 / 2 大纲本身不合法
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC_DIR = os.path.join(HERE, "spec")

# 派生目标：键 = 任务名，值 = 已提交的参考产物文件名
DERIVED = (
    ("lesson_plan", "lesson_plan.example.json"),
    ("slides", "slides.example.json"),
    ("handout", "handout.example.json"),
)

# 课件布局里"正文页"的集合 —— 这些页必须有讲稿（与 slide_spec_lint 的口径一致）
CONTENT_LAYOUTS = ("bullets", "two-column", "image-focus")


class OutlineError(Exception):
    """大纲不合法（用户输入问题）——退出码 2。"""


# ─────────────────────────────────────────────────────────────────
# 读 / 写
# ─────────────────────────────────────────────────────────────────
def load(path):
    """读大纲。"""
    if not os.path.isfile(path):
        raise OutlineError("找不到大纲文件：%s" % path)
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except ValueError as e:
        raise OutlineError("大纲文件不是合法 JSON：%s（%s）" % (path, e))


def dump(obj):
    """规范化的 JSON 文本（键排序）——用于**比较**，不用于写盘。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2)


def write_json(path, obj):
    """写 JSON（UTF-8 无 BOM、LF 换行、结尾带换行 —— 与仓库其它 spec 一致）。"""
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2))
        f.write("\n")


# ─────────────────────────────────────────────────────────────────
# 派生
# ─────────────────────────────────────────────────────────────────
def to_lesson_plan(outline):
    """大纲 → 教案规格。

    环节顺序 = 模块顺序 × 环节顺序；每个环节带上它的模块归属与环节号，
    让教案里的每一行都能回溯到大纲。
    """
    meta = dict(outline.get("meta") or {})
    objectives = [dict(o) for o in (outline.get("objectives") or [])]

    process = []
    for m in outline.get("modules") or []:
        for s in m.get("steps") or []:
            process.append({
                "minutes": s.get("minutes", 0),
                "teacher": s.get("teacher", ""),
                "student": s.get("student", ""),
                "intent": s.get("intent", ""),
                "objective": s.get("objective", ""),
                "module": m.get("id", ""),
                "module_title": m.get("title", ""),
                "step": s.get("id", ""),
            })

    return {
        "meta": meta,
        "ubd": dict(outline.get("ubd") or {}),
        "objectives": objectives,
        "key_points": list(outline.get("key_points") or []),
        "difficulties": list(outline.get("difficulties") or []),
        "prior_knowledge": list(outline.get("prior_knowledge") or []),
        "barriers": list(outline.get("barriers") or []),
        "methods": list(outline.get("methods") or []),
        "process": process,
        "board_design": dict(outline.get("board_design") or {}),
        "questions": [dict(q) for q in (outline.get("questions") or [])],
        "ideology_points": [dict(p) for p in (outline.get("ideology_points") or [])],
        "homework": [dict(h) for h in (outline.get("homework") or [])],
        "reflection": list(outline.get("reflection") or []),
        "needs_manual_check": [dict(e) for e in (outline.get("needs_manual_check") or [])],
    }


def to_slides(outline):
    """大纲 → 课件规格。

    页面顺序 = 封面 → 目录 → （模块顺序 × 环节顺序 × 该环节的页面顺序）。
    每页带上溯源字段：`role`（封面/目录）或 `module` / `step` / `objective`。
    """
    deck = outline.get("deck") or {}
    slides = []

    cover = deck.get("cover")
    if cover:
        s = dict(cover)
        s["role"] = "cover"
        slides.append(s)

    agenda = deck.get("agenda")
    if agenda:
        s = dict(agenda)
        s["role"] = "agenda"
        slides.append(s)

    for m in outline.get("modules") or []:
        for st in m.get("steps") or []:
            for sl in st.get("slides") or []:
                s = dict(sl)
                s["module"] = m.get("id", "")
                s["step"] = st.get("id", "")
                s["objective"] = st.get("objective", "")
                slides.append(s)

    return {
        "meta": dict(deck.get("meta") or {}),
        "slides": slides,
    }


def to_handout(outline):
    """大纲 → 讲义规格（**纯派生，0 次模型调用**）。

    🔴 讲义**不再另写一遍讲稿**。
       讲稿只有一份 —— 写在大纲的 `slides[].notes` 里；
       讲义里的讲稿是从**同一份课件规格**里搬过来的（`to_slides` 的输出），
       所以「讲义讲稿」与「课件讲稿」**逐字同源**，不可能对不上。

       这消灭的是本仓库历史上最常见的一处双写：
       「课件改了一句讲稿，讲义里还是旧的」。

    讲义页与课件页一一对应，靠 `id` 对齐。
    """
    slides = to_slides(outline)["slides"]
    pages = []
    for s in slides:
        role = s.get("role", "content")
        p = {
            "id": s.get("id", ""),
            "kind": role,
            "title": s.get("title", ""),
            "layout": s.get("layout", ""),
            "notes": s.get("notes", ""),
        }
        if s.get("subtitle"):
            p["subtitle"] = s.get("subtitle", "")
        if role == "content":
            p["module"] = s.get("module", "")
            p["step"] = s.get("step", "")
            p["objective"] = s.get("objective", "")
            p["bullets"] = [dict(b) for b in (s.get("bullets") or [])]
        pages.append(p)
    # 抬头取**大纲的 meta**（课程/课题/时长），再补上课件 deck 的 meta
    # （title/author/subject）—— 讲义抬头要能说清"哪门课哪次课"。
    meta = dict(outline.get("meta") or {})
    for k, v in ((outline.get("deck") or {}).get("meta") or {}).items():
        meta.setdefault(k, v)
    return {
        "meta": meta,
        "pages": pages,
    }


def derive(outline):
    """一次派生全部下游规格。"""
    return {
        "lesson_plan": to_lesson_plan(outline),
        "slides": to_slides(outline),
        "handout": to_handout(outline),
    }


# ─────────────────────────────────────────────────────────────────
# 增量重生成：只重跑一页
# ─────────────────────────────────────────────────────────────────
def page_index(outline):
    """页面 id → 定位信息。

    `("deck", "cover")` / `("deck", "agenda")` / `("step", (mi, si, pi))`
    """
    idx = {}
    deck = outline.get("deck") or {}
    for key in ("cover", "agenda"):
        pg = deck.get(key)
        if isinstance(pg, dict) and pg.get("id"):
            idx[pg["id"]] = ("deck", key)
    for mi, m in enumerate(outline.get("modules") or []):
        for si, s in enumerate(m.get("steps") or []):
            for pi, sl in enumerate(s.get("slides") or []):
                if isinstance(sl, dict) and sl.get("id"):
                    idx[sl["id"]] = ("step", (mi, si, pi))
    return idx


def page_fingerprints(outline):
    """每页的 sha256（内容指纹）——用来证明「只重跑一页 ⇒ 其余页一字未动」。"""
    import hashlib
    out = {}
    for m in outline.get("modules") or []:
        for s in m.get("steps") or []:
            for sl in s.get("slides") or []:
                pid = sl.get("id")
                if pid:
                    out[pid] = hashlib.sha256(
                        dump(sl).encode("utf-8")).hexdigest()
    deck = outline.get("deck") or {}
    for key in ("cover", "agenda"):
        pg = deck.get(key)
        if isinstance(pg, dict) and pg.get("id"):
            out[pg["id"]] = hashlib.sha256(
                dump(pg).encode("utf-8")).hexdigest()
    return out


def page_context(outline, page_id):
    """取某一页的**重生成上下文**：所在环节 + 当前页 + 同环节的其他页。

    给「只重跑一页」用：模型要看到**这一页在整节课里的位置**，
    否则它会把这一页重写成一段脱离上下文的孤立内容。
    """
    idx = page_index(outline)
    if page_id not in idx:
        return None
    kind, where = idx[page_id]
    if kind == "deck":
        return {"page_id": page_id, "kind": "deck", "where": where,
                "current": (outline.get("deck") or {}).get(where) or {},
                "siblings": []}
    mi, si, pi = where
    m = outline["modules"][mi]
    s = m["steps"][si]
    pages = s.get("slides") or []
    return {
        "page_id": page_id,
        "kind": "content",
        "module": {"id": m.get("id", ""), "title": m.get("title", "")},
        "step": {"id": s.get("id", ""), "minutes": s.get("minutes", 0),
                 "teacher": s.get("teacher", ""), "student": s.get("student", ""),
                 "intent": s.get("intent", ""), "objective": s.get("objective", "")},
        "current": pages[pi] if pi < len(pages) else {},
        "siblings": [p for j, p in enumerate(pages) if j != pi],
    }


def replace_page(outline, page_id, new_page):
    """把大纲里 `page_id` 那一页换成 `new_page`，**其余部分逐字不动**。

    返回 (新大纲, 是否换过)。找不到该页 ⇒ 原样返回 + False（不猜、不报错退出）。

    🔴 「只重跑一页」的价值不在省 CPU，而在**可证伪**：
       重跑之后，其余页的指纹必须一模一样 ——
       变了，说明这一页的改动**漏到了别处**，那才是真问题。
    """
    import copy
    idx = page_index(outline)
    if page_id not in idx:
        return outline, False
    new_out = copy.deepcopy(outline)
    kind, where = idx[page_id]
    if kind == "deck":
        new_out.setdefault("deck", {})[where] = copy.deepcopy(new_page)
    else:
        mi, si, pi = where
        new_out["modules"][mi]["steps"][si]["slides"][pi] = copy.deepcopy(new_page)
    # 页 id 是**定位键**，替换后必须还是同一个 —— 否则后续增量就找不到它了
    if kind == "deck":
        new_out["deck"][where]["id"] = page_id
    else:
        mi, si, pi = where
        new_out["modules"][mi]["steps"][si]["slides"][pi]["id"] = page_id
    return new_out, True


# ─────────────────────────────────────────────────────────────────
# 一致性：派生结果 vs 已提交的参考产物
# ─────────────────────────────────────────────────────────────────
def diff_problems(outline, spec_dir=SPEC_DIR):
    """比对派生结果与已提交的参考产物，返回不一致的说明列表。

    这条比对是本层守卫的核心：**参考产物是"某次派生的结果"的快照**，
    任何一方被手改（改了教案、也改了派生器）都会在这里露出来。
    """
    problems = []
    derived = derive(outline)
    for task, fname in DERIVED:
        path = os.path.join(spec_dir, fname)
        if not os.path.isfile(path):
            problems.append("缺参考产物：%s" % fname)
            continue
        with io.open(path, encoding="utf-8") as f:
            try:
                committed = json.load(f)
            except ValueError as e:
                problems.append("参考产物 %s 不是合法 JSON：%s" % (fname, e))
                continue
        if dump(committed) != dump(derived[task]):
            problems.append(_first_diff(committed, derived[task], fname))
    return problems


def _first_diff(a, b, label):
    """给出**第一处**不一致的位置 —— 报错要说人话，不要只说"不相等"。"""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return "%s 与大纲派生结果不一致" % label
    for k in sorted(set(a) | set(b)):
        if k not in a:
            return "%s 多了字段 %r（大纲派生结果里没有）" % (label, k)
        if k not in b:
            return "%s 缺字段 %r（大纲派生结果里有）" % (label, k)
        if dump(a[k]) != dump(b[k]):
            return "%s 的 %r 与大纲派生结果不一致" % (label, k)
    return "%s 与大纲派生结果不一致" % label


# ─────────────────────────────────────────────────────────────────
# 命令行
# ─────────────────────────────────────────────────────────────────
def _summary(outline):
    modules = outline.get("modules") or []
    steps = [s for m in modules for s in (m.get("steps") or [])]
    pages = [sl for s in steps for sl in (s.get("slides") or [])]
    minutes = sum(int(s.get("minutes") or 0) for s in steps)
    return ("模块 %d ｜ 环节 %d ｜ 环节页 %d ｜ 环节合计 %d 分钟"
            % (len(modules), len(steps), len(pages), minutes))


def main(argv=None):
    ap = argparse.ArgumentParser(description="大纲先行层：派生教案与课件")
    ap.add_argument("--spec", default=os.path.join(SPEC_DIR, "outline.example.json"),
                    help="大纲文件（默认仓库示例）")
    ap.add_argument("--check", action="store_true",
                    help="核对派生结果与已提交的参考产物是否一致")
    ap.add_argument("--regen", action="store_true",
                    help="用大纲重新生成已提交的参考产物（demo/spec/*.example.json）")
    ap.add_argument("--out", help="把派生出的规格写到该目录")
    ap.add_argument("--regen-page", help="只重跑这一页（页面 id，如 P5）；需配 --page-file")
    ap.add_argument("--page-file", help="新页面内容的 JSON 文件（--regen-page 的输入）")
    ap.add_argument("--write-outline", action="store_true",
                    help="把增量重生成的结果写回大纲文件（默认只改副本，不动事实源）")
    args = ap.parse_args(argv)

    try:
        outline = load(args.spec)
    except OutlineError as e:
        sys.stderr.write("%s\n" % e)
        return 2

    # ── 增量重生成：只重跑一页 ──────────────────────────────────
    changed_pages = []
    if args.regen_page:
        if not args.page_file:
            sys.stderr.write("--regen-page 需要 --page-file（新页面内容）\n")
            return 2
        if not os.path.isfile(args.page_file):
            sys.stderr.write("找不到新页面文件：%s\n" % args.page_file)
            return 2
        try:
            with io.open(args.page_file, encoding="utf-8") as f:
                new_page = json.load(f)
        except ValueError as e:
            sys.stderr.write("新页面文件不是合法 JSON：%s\n" % e)
            return 2
        before = page_fingerprints(outline)
        outline, changed = replace_page(outline, args.regen_page, new_page)
        if not changed:
            sys.stderr.write("大纲里找不到页面 %s（页面 id 必须是 P1/P2/…）\n"
                             % args.regen_page)
            return 2
        after = page_fingerprints(outline)
        changed_pages = sorted(k for k in before if before[k] != after.get(k))
        untouched = len(before) - len(changed_pages)
        print("增量重生成：%s 已替换；其余 %d 页指纹不变" % (args.regen_page, untouched))
        if changed_pages != [args.regen_page]:
            sys.stderr.write("!! 换了一页却动了 %s —— 增量替换漏到了别处\n"
                             % ", ".join(changed_pages))
            return 1
        if args.write_outline:
            write_json(args.spec, outline)
            print("已写回大纲：%s" % os.path.abspath(args.spec))

    if args.regen:
        derived = derive(outline)
        for task, fname in DERIVED:
            p = os.path.join(SPEC_DIR, fname)
            write_json(p, derived[task])
            print("已重生成参考产物：%s" % p)

    if args.out:
        if not os.path.isdir(args.out):
            os.makedirs(args.out)
        for task, _f in DERIVED:
            write_json(os.path.join(args.out, task + ".spec.json"),
                       derive(outline)[task])
        print("已写出派生规格到 %s" % os.path.abspath(args.out))

    print("大纲：%s" % os.path.abspath(args.spec))
    print("  %s" % _summary(outline))

    if args.check:
        problems = diff_problems(outline)
        if problems:
            sys.stderr.write("大纲派生的产物与已提交示例不一致：\n")
            for p in problems:
                sys.stderr.write("   - %s\n" % p)
            return 1
        print("  派生结果与已提交参考产物一致（唯一事实源成立）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
