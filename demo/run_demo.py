#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_demo.py —— 「输入课程信息 → 教案 / 试卷 / PPTX + 自检报告」的最小本地 Demo

    # 离线：不需要任何 API key，用仓库自带的大纲示例跑通全链路
    python demo\\run_demo.py --out demo\\out

    # 在线：让模型把课程信息写成大纲（需设 JFA_LLM_BASE_URL / API_KEY / MODEL）
    python demo\\run_demo.py --input demo\\course_input.example.json --mode live --out demo\\out

流程
----
    课程信息 ──▶ **大纲**（唯一事实源）
                    │
                    ├─▶ 教案 Markdown      ┐ 派生（0 次模型调用）
                    ├─▶ PPTX（仓库自研）  ┘
                    │
                    └─▶ 试卷 Markdown（单独一次模型调用）

🔴 **为什么中间多了一层「大纲」**：
   教案与课件若各自写出来，对齐就只能靠事后核对（改了教案忘了改课件）。
   从同一份大纲**派生**，对齐就是**结构问题**而不是检查问题。

🔴 **Demo 的重点不是"能生成"，是"生成完自己检查过"**：
   自检里的 ERROR 全部对应本仓库写进 agent.md 的硬纪律
   （各环节时间相加 = 总学时、评价权重合计 = 100%、事实项不得编造）。

退出码：0 全部通过（可能带 WARN/INFO）/ 1 有 ERROR / 2 参数或依赖问题
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "skills", "teaching-slide-builder", "scripts"))

import llm  # noqa: E402
import outline as outline_mod  # noqa: E402
import selfcheck  # noqa: E402

SPEC_DIR = os.path.join(HERE, "spec")
TASKS = ("lesson_plan", "exam_paper", "slides", "handout")
# 从大纲派生的三件（试卷另有来源，不派生）
DERIVED_TASKS = ("lesson_plan", "slides", "handout")


# ─────────────────────────────────────────────────────────────────
# 渲染：Markdown
# ─────────────────────────────────────────────────────────────────
def _md_table(header, rows):
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x).replace("|", "\\|").replace("\n", "<br>")
                                     for x in r) + " |")
    return "\n".join(out)


def render_lesson_plan(spec):
    m = spec.get("meta") or {}
    L = []
    L.append("# 教案 · %s · %s" % (m.get("course", ""), m.get("topic", "")))
    L.append("")
    L.append("> 结构依据 `skills/teaching-file-builder`（文件类型 2：教案）。")
    L.append("> ⚠️ 抬头中标「需人工核验」的字段尚未确认，**请勿直接提交**。")
    L.append("")
    L.append("## 一、本次授课信息")
    L.append("")
    L.append(_md_table(["课程", "第几次课", "课题", "学时", "授课方式", "授课日期"], [[
        m.get("course", ""), m.get("session_no", ""), m.get("topic", ""),
        "%s 学时 / %s 分钟" % (m.get("hours", ""), m.get("minutes", "")),
        "讲授 + 练习", m.get("date") or "需人工核验"]]))
    L.append("")
    L.append("> 课程代码：%s ｜ 授课教师：%s ｜ 学院：%s ｜ 学期：%s ｜ "
             "适用专业：%s ｜ 课程性质：%s ｜ 先修课程：%s"
             % (m.get("course_code") or "需人工核验", m.get("teacher") or "需人工核验",
                m.get("college") or "需人工核验", m.get("semester") or "需人工核验",
                m.get("major", ""), m.get("nature", ""), m.get("prerequisites", "")))
    L.append("")

    L.append("## 二、教学目标")
    L.append("")
    L.append(_md_table(["编号", "目标（可检验）", "检验证据", "对应课程目标"],
                       [[o.get("id", ""), o.get("text", ""), o.get("evidence", ""),
                         o.get("course_objective", "")] for o in spec.get("objectives") or []]))
    L.append("")
    _render_ubd_section(spec, L)

    L.append("## 三、教学重点与难点")
    L.append("")
    for x in spec.get("key_points") or []:
        L.append("- 重点：%s" % x)
    for x in spec.get("difficulties") or []:
        L.append("- 难点：%s" % x)
    L.append("")

    L.append("## 四、学情分析")
    L.append("")
    L.append("**先备知识**：" + "；".join(spec.get("prior_knowledge") or []))
    L.append("")
    L.append("**可能障碍**：" + "；".join(spec.get("barriers") or []))
    L.append("")

    L.append("## 五、教学方法与教具")
    L.append("")
    L.append("、".join(spec.get("methods") or []) + "；教具：板书 + 练习纸 + 统计工具。")
    L.append("")

    L.append("## 六、教学过程")
    L.append("")
    L.append(_md_table(["模块", "时间", "教师活动", "学生活动", "设计意图", "对应目标"],
                       [["%s %s" % (s.get("module", ""), s.get("module_title", "")),
                         "⏱ %s 分钟" % s.get("minutes", ""), s.get("teacher", ""),
                         s.get("student", ""), s.get("intent", ""), s.get("objective", "")]
                        for s in spec.get("process") or []]))
    total = sum(int(s.get("minutes") or 0) for s in spec.get("process") or [])
    L.append("")
    L.append("⏱ **各段合计 %d 分钟 ／ 本次课 %s 分钟**" % (total, m.get("minutes", "")))
    L.append("")

    bd = spec.get("board_design") or {}
    L.append("## 七、板书设计")
    L.append("")
    L.append("- 主板书：%s" % bd.get("main", ""))
    L.append("- 副板书：%s" % bd.get("aux", ""))
    L.append("")

    L.append("## 八、课堂提问与互动设计")
    L.append("")
    L.append(_md_table(["预设问题", "预期回答", "追问路径"],
                       [[q.get("q", ""), q.get("expected", ""), q.get("followup", "")]
                        for q in spec.get("questions") or []]))
    L.append("")

    L.append("## 九、课程思政融入点")
    L.append("")
    pts = spec.get("ideology_points") or []
    if not pts:
        L.append("（本次课未设课程思政融入点）")
    for p in pts:
        L.append("- **%s** ｜ 载体：%s ｜ 融入方式：%s"
                 % (p.get("point", ""), p.get("carrier", ""), p.get("how", "")))
    L.append("")

    L.append("## 十、课后作业与延伸阅读")
    L.append("")
    for h in spec.get("homework") or []:
        L.append("- %s（检验：%s）" % (h.get("task", ""), h.get("purpose", "")))
    L.append("")

    L.append("## 十一、教学反思要点（课后填写）")
    L.append("")
    for r in spec.get("reflection") or []:
        L.append("- [ ] %s" % r)
    L.append("")

    L.append("## 十二、需人工核验清单")
    L.append("")
    for e in spec.get("needs_manual_check") or []:
        if isinstance(e, dict):
            L.append("- [ ] %s（字段：%s）" % (e.get("desc", ""), e.get("field", "")))
        else:
            L.append("- [ ] %s" % e)
    L.append("")
    return "\n".join(L)


def _render_ubd_section(spec, L):
    """教案里的 UbD 设计骨架一节（从大纲的 `ubd` 块派生）。

    🔴 为什么教案要带这一节：UbD 回答的是「这次课凭什么这样设计」，
       它和「怎么讲」是同一份大纲的两个面 ——
       教案只写过程不写骨架，教师就无从判断某个环节是**有意为之**还是**随手安排的**。
    """
    u = spec.get("ubd") or {}
    if not u:
        return
    L.append("### 2.1 设计骨架（UbD）")
    L.append("")
    big = u.get("big_idea") or []
    if big:
        L.append("**持久理解（学生能带走、能迁移的理解）**")
        L.append("")
        for b in big:
            L.append("- %s" % b)
        L.append("")
    eqs = u.get("essential_questions") or []
    if eqs:
        L.append("**基本问题**")
        L.append("")
        for q in eqs:
            L.append("- **%s** %s" % (q.get("id", ""), q.get("text", "")))
        L.append("")
    g = u.get("grasps") or {}
    if g:
        L.append("**表现性任务（GRASPS）**")
        L.append("")
        L.append(_md_table(["要素", "内容"], [
            ["G · 目标", g.get("goal", "")],
            ["R · 角色", g.get("role", "")],
            ["A · 受众", g.get("audience", "")],
            ["S · 情境", g.get("situation", "")],
            ["P · 产物", g.get("product", "")],
            ["S · 标准", g.get("standards", "")],
        ]))
        L.append("")
    w = u.get("whereto") or {}
    if w:
        L.append("**学习循环覆盖（WHERETO）**")
        L.append("")
        L.append(_md_table(["要素", "落在哪个环节", "说明"], [
            [label, "%s（%s）" % ((w.get(key) or {}).get("step", ""),
                                  (w.get(key) or {}).get("note", "")),
             (w.get(key) or {}).get("step", "")]
            for key, label in (
                ("where", "W · Where & Why"),
                ("hook", "H · Hook"),
                ("equip", "E · Equip"),
                ("experience", "E · Experience"),
                ("rethink", "R · Rethink & Revise"),
                ("tailor", "T · Tailor"),
                ("organize", "O · Organize"))
        ]))
        L.append("")


def render_handout(spec):
    """讲义（Markdown）：逐页课件 + 该页讲稿。

    🔴 讲稿**不是这里写的** —— 它是从课件规格搬过来的（`to_handout` 派生），
       所以讲义与课件的讲稿**逐字同源**。这一节只负责排版。
    """
    m = spec.get("meta") or {}
    L = []
    L.append("# 讲义 · %s · %s" % (m.get("course", "") or m.get("title", ""),
                                   m.get("topic", "") or m.get("subject", "")))
    L.append("")
    L.append("> 讲稿与课件**逐字同源**：本讲义的讲稿由课件规格自动导出，"
             "不是另写一遍。")
    L.append("")
    pages = spec.get("pages") or []
    L.append("共 %d 页。" % len(pages))
    L.append("")
    for p in pages:
        pid = p.get("id", "")
        kind = p.get("kind", "content")
        L.append("## %s %s" % (pid, p.get("title", "")))
        L.append("")
        if p.get("subtitle"):
            L.append("> %s" % p.get("subtitle", ""))
            L.append("")
        if kind == "content":
            L.append("- 所属：%s ｜ %s ｜ 目标 %s"
                     % (p.get("module", ""), p.get("step", ""), p.get("objective", "")))
            L.append("")
        bullets = p.get("bullets") or []
        if bullets:
            L.append("**页面要点**")
            L.append("")
            for b in bullets:
                lvl = int(b.get("level", 0) or 0)
                L.append("%s- %s" % ("  " * lvl, b.get("text", "")))
            L.append("")
        if str(p.get("notes", "")).strip():
            L.append("**讲稿**")
            L.append("")
            L.append(p.get("notes", ""))
            L.append("")
    return "\n".join(L) + "\n"


def render_handout_extra(spec):
    """学生阅读版讲义（自学者可独立使用）。

    🔴 与 `render_handout`（逐页讲稿讲义）是**两件不同的东西**：
       前者是**从课件派生**的讲稿本（讲稿与课件逐字同源，给讲授者）；
       这一份是**模型写的**自学材料（给「每个概念给出直觉→形式化的桥梁」）。
       两者不混 —— 混了就等于把讲稿又写了一遍。
    """
    L = []
    L.append("# 学生阅读版讲义 · %s" % spec.get("title", ""))
    L.append("")
    L.append("> 自学者可独立使用的材料：每个概念都给出「直觉 → 形式化」的桥梁。")
    L.append("")
    for i, sec in enumerate(spec.get("sections") or []):
        L.append("## %s %s" % (i + 1, sec.get("heading", "")))
        L.append("")
        if sec.get("intuition"):
            L.append("**直觉**")
            L.append("")
            L.append(sec.get("intuition", ""))
            L.append("")
        L.append(sec.get("body", ""))
        L.append("")
        terms = sec.get("terms") or []
        if terms:
            L.append(_md_table(["术语", "解释"],
                               [[t.get("term", ""), t.get("meaning", "")] for t in terms]))
            L.append("")
        if sec.get("check"):
            L.append("**读完能回答**")
            L.append("")
            L.append("- %s" % sec.get("check", ""))
            L.append("")
    mc = spec.get("needs_manual_check") or []
    if mc:
        L.append("## 需人工核验清单")
        L.append("")
        for e in mc:
            L.append("- %s" % (e if isinstance(e, str)
                               else "%s：%s" % (e.get("field", ""), e.get("desc", ""))))
        L.append("")
    return "\n".join(L) + "\n"


def render_lint(spec):
    """审校意见（Markdown）。"""
    fs = spec.get("findings") or []
    L = []
    L.append("# 审校意见 · %s" % (spec.get("summary") or ""))
    L.append("")
    if not fs:
        L.append("未发现问题。")
        L.append("")
        return "\n".join(L) + "\n"
    L.append(_md_table(["级别", "代号", "位置", "问题"],
                       [[f.get("level", ""), f.get("rule", ""), f.get("where", ""),
                         f.get("message", "")] for f in fs]))
    L.append("")
    return "\n".join(L) + "\n"


def render_exam_paper(spec):
    m = spec.get("meta") or {}
    d = spec.get("design") or {}
    L = []
    L.append("# %s · 单元测验（%s 卷）" % (m.get("course", ""), m.get("paper", "A")))
    L.append("")
    L.append("> 结构依据 `skills/exam-question-bank`（输出格式）。")
    L.append("> 总分 %s 分 ｜ 考试时长 %s 分钟 ｜ 日期：%s"
             % (m.get("total_score", ""), m.get("duration_minutes", ""),
                m.get("date") or "需人工核验"))
    L.append("")

    L.append("## 一、命题设计说明")
    L.append("")
    L.append("**目标—题型—认知层次映射**")
    L.append("")
    L.append(_md_table(["目标", "题型", "题量", "分值"],
                       [[r.get("objective", ""), r.get("type", ""),
                         r.get("count", ""), r.get("score", "")]
                        for r in d.get("objective_type_matrix") or []]))
    L.append("")
    L.append("**认知层次分布**：" + " ｜ ".join(
        "%s %s 分" % (r.get("level", ""), r.get("score", ""))
        for r in d.get("cognitive_distribution") or []))
    L.append("")
    L.append("**难度分布**：" + " ｜ ".join(
        "%s %s 分" % (r.get("level", ""), r.get("score", ""))
        for r in d.get("difficulty_distribution") or []))
    L.append("")
    L.append("**命题思路**：%s" % d.get("design_note", ""))
    L.append("")

    L.append("## 二、试题（%s 卷）" % m.get("paper", "A"))
    L.append("")
    by_type = {}
    for q in spec.get("questions") or []:
        by_type.setdefault(q.get("type", "题目"), []).append(q)
    for t, qs in by_type.items():
        L.append("### %s（共 %d 分）" % (t, sum(int(q.get("score") or 0) for q in qs)))
        L.append("")
        for q in qs:
            L.append("**%s.（%s 分，建议用时 %s 分钟）**" % (q.get("no", ""),
                                                         q.get("score", ""),
                                                         q.get("minutes", "")))
            L.append("")
            L.append(str(q.get("stem", "")))
            L.append("")
            for opt in q.get("options") or []:
                L.append("- %s" % opt)
            if q.get("options"):
                L.append("")
        L.append("")

    L.append("## 三、答案与评分细则（逐题）")
    L.append("")
    L.append(_md_table(["题号", "目标", "层次", "难度", "答案", "评分细则"],
                       [[q.get("no", ""), q.get("objective", ""), q.get("cognitive", ""),
                         q.get("difficulty", ""), q.get("answer", ""), q.get("scoring", "")]
                        for q in spec.get("questions") or []]))
    L.append("")

    bk = spec.get("backup") or {}
    L.append("## 四、备用卷 %s" % bk.get("paper", "B"))
    L.append("")
    L.append(bk.get("note", ""))
    L.append("")
    for q in bk.get("questions") or []:
        L.append("**%s.（%s 分，%s）** %s" % (q.get("no", ""), q.get("score", ""),
                                            q.get("type", ""),
                                            str(q.get("stem", "")).splitlines()[0]))
        L.append("")
    L.append("> 备用卷完整题干与评分细则见 `exam_paper.spec.json`。")
    L.append("")

    L.append("## 五、题库覆盖矩阵（目标 × 题型）")
    L.append("")
    L.append(_md_table(["目标", "题型", "题量", "分值", "覆盖"],
                       [[r.get("objective", ""), r.get("type", ""), r.get("count", ""),
                         r.get("score", ""),
                         sum(1 for q in spec.get("questions") or []
                             if q.get("objective") == r.get("objective")
                             and q.get("type") == r.get("type"))]
                        for r in d.get("objective_type_matrix") or []]))
    L.append("")

    L.append("## 六、需人工核验清单")
    L.append("")
    for e in spec.get("needs_manual_check") or []:
        if isinstance(e, dict):
            L.append("- [ ] %s（字段：%s）" % (e.get("desc", ""), e.get("field", "")))
        else:
            L.append("- [ ] %s" % e)
    L.append("")
    return "\n".join(L)


# ─────────────────────────────────────────────────────────────────
# 产出
# ─────────────────────────────────────────────────────────────────
def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def build_slides(spec, spec_path, out_path):
    """用仓库自研的纯标准库生成器产出 PPTX，并做结构自检。"""
    import build_pptx
    n_slides, n_notes, warns = build_pptx.build(
        spec, out_path, os.path.dirname(os.path.abspath(spec_path)))
    problems = build_pptx.check_pptx(out_path)
    return {"slides": n_slides, "notes": n_notes,
            "warnings": warns, "structure_problems": problems}


def render_report(results):
    """自检报告（Markdown）。results: {任务: {"findings": [...], "summary": {...}}}"""
    L = []
    L.append("# 交付物自检报告")
    L.append("")
    L.append("> 本报告由 `demo/selfcheck.py` 与仓库自带的 `slide_spec_lint.py` 机械生成。")
    L.append("> ERROR = 必须改（不改这份交付物不成立）；WARN = 多数情况应改；INFO = 人工判断。")
    L.append("")
    L.append("| 交付物 | ERROR | WARN | INFO | 结论 |")
    L.append("|---|---|---|---|---|")
    total_err = 0
    for task, r in results.items():
        s = r["summary"]
        total_err += s["error"]
        verdict = "✅ 通过" if s["error"] == 0 else "❌ 不通过"
        L.append("| %s | %d | %d | %d | %s |"
                 % (TASK_LABEL.get(task, task), s["error"], s["warn"], s["info"], verdict))
    L.append("")
    for task, r in results.items():
        L.append("## %s" % TASK_LABEL.get(task, task))
        L.append("")
        fs = r["findings"]
        if not fs:
            L.append("✅ 无问题。")
            L.append("")
            continue
        L.append(_md_table(["级别", "检查项", "位置", "说明"],
                           [[f.level, f.rule, f.where, f.message] for f in fs]))
        L.append("")
    L.append("---")
    L.append("")
    L.append("**合计 ERROR %d 项。** ERROR 必须清零后再提交。" % total_err)
    L.append("")
    return "\n".join(L)


TASK_LABEL = {
    "outline": "大纲（唯一事实源）",
    "lesson_plan": "教案",
    "exam_paper": "试卷",
    "slides": "幻灯片（PPTX）",
    "handout": "讲义",
    "handout_extra": "讲义（学生版）",
    "lint": "模型审校",
}


# ─────────────────────────────────────────────────────────────────
def main(argv=None):
    # 🔴 Windows 中文控制台默认 GBK —— 本脚本要打印 `✅`（U+2705，GBK 里没有），
    #    不切 UTF-8 就会在**最后一行汇报**时抛 UnicodeEncodeError。
    #    而它正是守卫 `check_demo` 的被测对象：崩了会被记成「Demo 有 ERROR」，
    #    **判据红的原因和真正的原因对不上号**（编码问题被当成内容问题）。
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="教学交付物最小本地 Demo")
    ap.add_argument("--input", help="课程信息 JSON（在线模式用；默认用仓库自带示例）")
    ap.add_argument("--out", default=os.path.join(HERE, "out"), help="输出目录")
    ap.add_argument("--mode", choices=("offline", "live"), default="offline",
                    help="offline=用仓库自带示例 spec；live=调模型生成 spec")
    ap.add_argument("--only", choices=TASKS, help="只跑某一件交付物")
    ap.add_argument("--outline", help="已有的大纲文件（给了就不再向模型要整份大纲）")
    ap.add_argument("--regen-page", help="只重跑这一页（页面 id，如 P5）；需 --mode live")
    ap.add_argument("--handout-extra", action="store_true",
                    help="额外生成「学生阅读版讲义」（模型写；需 --mode live）")
    ap.add_argument("--lint", action="store_true",
                    help="额外做一次模型审校（需 --mode live）")
    args = ap.parse_args(argv)

    out_dir = os.path.abspath(args.out)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    course = {}
    if args.input:
        if not os.path.isfile(args.input):
            sys.stderr.write("找不到课程信息文件：%s\n" % args.input)
            return 2
        with io.open(args.input, encoding="utf-8") as f:
            course = json.load(f)

    tasks = [args.only] if args.only else list(TASKS)
    specs = {}
    grounding = None
    outline = None
    outline_findings = []
    need_outline = any(t in DERIVED_TASKS for t in tasks)

    # ── ① 大纲（唯一事实源）──────────────────────────────────
    if need_outline:
        if args.outline:
            # 已有大纲：不问模型要整份（增量重生成的前提）
            if not os.path.isfile(args.outline):
                sys.stderr.write("找不到大纲文件：%s\n" % args.outline)
                return 2
            with io.open(args.outline, encoding="utf-8") as f:
                outline = json.load(f)
        elif args.mode == "offline":
            p = os.path.join(SPEC_DIR, "outline.example.json")
            if not os.path.isfile(p):
                sys.stderr.write("找不到示例大纲：%s\n" % p)
                return 2
            with io.open(p, encoding="utf-8") as f:
                outline = json.load(f)
        else:
            try:
                if grounding is None:
                    grounding = llm.skill_grounding()
                msgs = llm.build_messages("outline", course, grounding)
                raw = llm.call(msgs, task="outline")
                outline = llm.extract_json(raw)
            except llm.LLMError as e:
                sys.stderr.write("[outline] 生成大纲失败：%s\n" % e)
                return 2

        # ── ①b 增量重生成：只重跑一页 ───────────────────────────
        if args.regen_page:
            if args.mode != "live":
                sys.stderr.write("--regen-page 需要 --mode live（离线没有模型可重跑；"
                                 "离线改页请用 demo/outline.py --regen-page --page-file）\n")
                return 2
            ctx = outline_mod.page_context(outline, args.regen_page)
            if ctx is None:
                sys.stderr.write("大纲里找不到页面 %s\n" % args.regen_page)
                return 2
            before = outline_mod.page_fingerprints(outline)
            try:
                if grounding is None:
                    grounding = llm.skill_grounding()
                msgs = llm.build_messages("page", course, grounding, extra=ctx)
                raw = llm.call(msgs, task="page")
                new_page = llm.extract_json(raw)
            except llm.LLMError as e:
                sys.stderr.write("[page %s] 重生成失败：%s\n" % (args.regen_page, e))
                return 2
            outline, changed = outline_mod.replace_page(outline, args.regen_page, new_page)
            if not changed:
                sys.stderr.write("替换页面 %s 失败\n" % args.regen_page)
                return 2
            after = outline_mod.page_fingerprints(outline)
            touched = sorted(k for k in before if before[k] != after.get(k))
            print("增量重生成：%s（只调了 1 次模型）；其余 %d 页指纹不变"
                  % (args.regen_page, len(before) - len(touched)))
            if touched != [args.regen_page]:
                sys.stderr.write("!! 重跑一页却动了 %s —— 增量替换漏到了别处\n"
                                 % ", ".join(touched))
                return 1

        # 落盘大纲：它既是中间产物，也是"模型写了什么"的审计凭据
        write_text(os.path.join(out_dir, "outline.spec.json"),
                   json.dumps(outline, ensure_ascii=False, indent=2))
        # 大纲自检：**在大纲层能查的，不要留到下游查**。
        # 大纲是下游的唯一事实源，它不成立，下游全都不成立 ⇒ 立刻中止。
        outline_findings = selfcheck.check_outline(outline)
        oerr = sum(1 for f in outline_findings if f.level == "ERROR")
        if oerr:
            for f in outline_findings:
                if f.level == "ERROR":
                    sys.stderr.write("      ✗ %s %s：%s\n"
                                     % (f.rule, f.where, f.message))
            sys.stderr.write("❌ 大纲自检未通过：%d 项 ERROR"
                             "（大纲是下游的唯一事实源，它不成立，下游都不成立）\n" % oerr)
            return 1

    # ── ② 从大纲派生教案与课件（**0 次模型调用**）───────────
    if outline is not None:
        derived = outline_mod.derive(outline)
        for task in DERIVED_TASKS:
            if task in tasks:
                specs[task] = derived[task]

    # ── ③ 试卷：不从大纲派生，单独取 ─────────────────────────
    if "exam_paper" in tasks:
        if args.mode == "offline":
            p = os.path.join(SPEC_DIR, "exam_paper.example.json")
            if not os.path.isfile(p):
                sys.stderr.write("找不到示例 spec：%s\n" % p)
                return 2
            with io.open(p, encoding="utf-8") as f:
                specs["exam_paper"] = json.load(f)
        else:
            try:
                if grounding is None:
                    grounding = llm.skill_grounding()
                msgs = llm.build_messages("exam_paper", course, grounding)
                raw = llm.call(msgs, task="exam_paper")
                specs["exam_paper"] = llm.extract_json(raw)
            except llm.LLMError as e:
                sys.stderr.write("[exam_paper] 生成 spec 失败：%s\n" % e)
                return 2

    # ── ④ 学生阅读版讲义（模型写；与「逐页讲稿讲义」是两件东西）──
    if args.handout_extra:
        if args.mode != "live":
            sys.stderr.write("--handout-extra 需要 --mode live（离线不调模型）\n")
            return 2
        try:
            if grounding is None:
                grounding = llm.skill_grounding()
            msgs = llm.build_messages("handout", course, grounding)
            raw = llm.call(msgs, task="handout")
            specs["handout_extra"] = llm.extract_json(raw)
        except llm.LLMError as e:
            sys.stderr.write("[handout_extra] 生成失败：%s\n" % e)
            return 2

    # ── ⑤ 审校（模型挑毛病）────────────────────────────────────
    if args.lint:
        if args.mode != "live":
            sys.stderr.write("--lint 需要 --mode live（离线不调模型）\n")
            return 2
        review = {"outline": outline, "slides": specs.get("slides")}
        try:
            if grounding is None:
                grounding = llm.skill_grounding()
            msgs = llm.build_messages("lint", course, grounding, extra=review)
            raw = llm.call(msgs, task="lint")
            specs["lint"] = llm.extract_json(raw)
        except llm.LLMError as e:
            sys.stderr.write("[lint] 审校失败：%s\n" % e)
            return 2

    # ── ⑤′ 公式规范化：每一件生成物的公式都必须过一遍 ─────────────
    #    大纲派生的三件已经在 outline.py 里规范过了（规范化是幂等的，
    #    再过一次是空转）；试卷、学生版讲义、审校意见这些**不走派生**的
    #    规格必须在这里补上 —— 否则伪公式会绕过规范化漏到交付物里。
    #    （本轮实测：试卷的答案与评分细则里有 4 处伪公式，正是这条漏掉的。）
    for task in sorted(specs):
        if task == "lint":
            continue
        try:
            specs[task] = outline_mod.normalize_spec(specs[task], task)
        except outline_mod.OutlineError as e:
            sys.stderr.write("[%s] 公式规范化中止：%s\n" % (task, e))
            return 2

    # 落盘 spec：它们既是中间产物，也是"模型写了什么"的审计凭据
    for task in specs:
        write_text(os.path.join(out_dir, task + ".spec.json"),
                   json.dumps(specs[task], ensure_ascii=False, indent=2))

    # ── 渲染 + 自检 ──────────────────────────────────────────────
    results = {}
    outputs = []

    if outline is not None:
        results["outline"] = {"findings": outline_findings,
                              "summary": selfcheck.summarize(outline_findings)}

    if "lesson_plan" in specs:
        p = os.path.join(out_dir, "教案.md")
        write_text(p, render_lesson_plan(specs["lesson_plan"]))
        outputs.append(p)
        fs = selfcheck.check_lesson_plan(specs["lesson_plan"])
        results["lesson_plan"] = {"findings": fs, "summary": selfcheck.summarize(fs)}

    if "exam_paper" in specs:
        p = os.path.join(out_dir, "试卷.md")
        write_text(p, render_exam_paper(specs["exam_paper"]))
        outputs.append(p)
        fs = selfcheck.check_exam_paper(specs["exam_paper"])
        results["exam_paper"] = {"findings": fs, "summary": selfcheck.summarize(fs)}

    if "slides" in specs:
        p = os.path.join(out_dir, "幻灯片.pptx")
        info = build_slides(specs["slides"], os.path.join(out_dir, "slides.spec.json"), p)
        outputs.append(p)
        fs = selfcheck.check_slides(specs["slides"])
        for prob in info["structure_problems"]:
            fs.append(selfcheck.Finding("ERROR", "PPTX-STRUCT", "pptx", str(prob)))
        results["slides"] = {"findings": fs,
                             "summary": selfcheck.summarize(fs),
                             "info": info}

    if "handout" in specs:
        p = os.path.join(out_dir, "讲义.md")
        write_text(p, render_handout(specs["handout"]))
        outputs.append(p)
        # 讲义自检**必须带上课件规格** —— 只查讲义自身的话，
        # 「讲义讲稿被手改过」这类缺陷就查不出来。
        fs = selfcheck.check_handout(specs["handout"], specs.get("slides"))
        results["handout"] = {"findings": fs, "summary": selfcheck.summarize(fs)}

    if "handout_extra" in specs:
        p = os.path.join(out_dir, "讲义-学生版.md")
        write_text(p, render_handout_extra(specs["handout_extra"]))
        outputs.append(p)

    # ── 公式验收闸：所有生成物的公式都必须已经过规范化 ──────────────
    #    规范化在**派生层**做（demo/outline.py 的 normalize_spec），
    #    这里检查它**真的做到了** —— 判据不重写一份，用技能里的 formula_gate。
    formula_findings = []
    for key in ("lesson_plan", "exam_paper", "slides", "handout"):
        if key in specs:
            formula_findings.extend(selfcheck.check_formula(specs[key], key))
    if formula_findings:
        results["formula"] = {"findings": formula_findings,
                              "summary": selfcheck.summarize(formula_findings)}

    if "lint" in specs:
        p = os.path.join(out_dir, "审校意见.md")
        write_text(p, render_lint(specs["lint"]))
        outputs.append(p)
        fs = [selfcheck.Finding(f.get("level", "WARN"), f.get("rule", "LLM-LINT"),
                                 f.get("where", ""), f.get("message", ""))
              for f in (specs["lint"].get("findings") or [])]
        results["lint"] = {"findings": fs, "summary": selfcheck.summarize(fs)}

    # ── 自检报告 ─────────────────────────────────────────────────
    rep = os.path.join(out_dir, "自检报告.md")
    write_text(rep, render_report(results))
    outputs.append(rep)
    with io.open(os.path.join(out_dir, "自检报告.json"), "w", encoding="utf-8") as f:
        json.dump({t: {"summary": r["summary"],
                       "findings": [x.as_dict() for x in r["findings"]]}
                   for t, r in results.items()},
                  f, ensure_ascii=False, indent=2)

    # ── 汇报 ─────────────────────────────────────────────────────
    print("模式：%s%s" % (args.mode, ("（输入：%s）" % args.input) if args.input else ""))
    print("输出目录：%s" % out_dir)
    print("")
    err = 0
    for task, r in results.items():
        s = r["summary"]
        err += s["error"]
        extra = ""
        if task == "slides" and r.get("info"):
            extra = "（%d 页 / %d 页有讲稿）" % (r["info"]["slides"], r["info"]["notes"])
        print("  %-16s ERROR %d ｜ WARN %d ｜ INFO %d%s"
              % (TASK_LABEL.get(task, task), s["error"], s["warn"], s["info"], extra))
        for f in r["findings"]:
            if f.level == "ERROR":
                print("      ✗ %s %s：%s" % (f.rule, f.where, f.message))
    print("")
    for p in outputs:
        print("  → %s" % p)
    print("")
    if err:
        print("❌ 自检未通过：%d 项 ERROR（详见自检报告.md）" % err)
        return 1
    print("✅ 自检通过：全部交付物零 ERROR")
    return 0


if __name__ == "__main__":
    sys.exit(main())
