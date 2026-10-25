#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""selftest.py —— Demo 自检判据的变异测试

    python demo\\selftest.py

🔴 **「检查全绿」有两种可能**：真的没问题，或者**检查在空转**。
   只跑绿不算数 —— 必须证明每一类故障都能让对应的判据变红。

每个用例：注入一处典型错误 → 跑自检 → 要求**指定的那条判据**出现在结果里。
判据没报 = 漏检 = 这个检查没有存在价值。
"""
from __future__ import annotations

import copy
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import selfcheck  # noqa: E402
import llm  # noqa: E402
import outline as outline_mod  # noqa: E402

SPEC_DIR = os.path.join(HERE, "spec")


def load(name):
    with io.open(os.path.join(SPEC_DIR, name + ".example.json"),
                 encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────
# 变异：每个函数改坏 spec 的一处，返回 (spec, 期望命中的判据)
# ─────────────────────────────────────────────────────────────────
def m_lesson_time_mismatch(spec):
    spec["process"][0]["minutes"] = 5          # 合计变成 85 ≠ 90
    return spec, "LP-P04"


def m_lesson_objective_unbound(spec):
    del spec["objectives"][1]["course_objective"]
    return spec, "LP-P09"


def m_lesson_missing_manual_entry(spec):
    spec["needs_manual_check"] = [
        e for e in spec["needs_manual_check"] if e.get("field") != "course_code"]
    return spec, "LP-P02"


def m_lesson_placeholder(spec):
    spec["objectives"][0]["text"] = "能理解待补充的知识点"
    return spec, "LP-P01"


def m_lesson_no_intent(spec):
    spec["process"][3]["intent"] = ""
    return spec, "LP-P10"


def m_exam_score_sum(spec):
    spec["questions"][0]["score"] = 6          # 合计 101 ≠ 100
    return spec, "EX-P08"


def m_exam_cog_sum(spec):
    spec["design"]["cognitive_distribution"][0]["score"] = 15
    return spec, "EX-P10"


def m_exam_no_scoring(spec):
    del spec["questions"][2]["scoring"]
    return spec, "EX-P05"


def m_exam_placeholder(spec):
    spec["questions"][1]["stem"] = "见教材第 XXX 页"
    return spec, "EX-P01"


def m_slides_too_many_bullets(spec):
    spec["slides"][2]["bullets"] = [
        {"text": "要点%d" % i, "level": 0} for i in range(9)]
    return spec, "L01"


def m_slides_no_notes(spec):
    del spec["slides"][2]["notes"]
    return spec, "L04"


def m_slides_vague_title(spec):
    spec["slides"][2]["title"] = "小结"
    return spec, "L11"


def m_slides_two_covers(spec):
    spec["slides"][1]["layout"] = "title"
    return spec, "L07"


def m_slides_title_overflow(spec):
    """封面副标题过长：几何上放不下（L15），而 L03 根本不查副标题。

    🔴 这条用例证明 L15 不是 L03 的重复 —— 它抓的是 L03 抓不到的。

    🔴 **样例必须按当前几何重算，不能沿用旧画布的数字**：
       旧版 960×540 / 标题 44pt 时，20 字封面标题会折成 2 行而溢出；
       改版后画布 720×405、封面标题 30pt、标题框宽 520pt ⇒
       一行放得下 520÷30 ≈ 17.3 个全角字，20 字**不再溢出** ⇒ 旧样例失效。
       现在封面副标题是 13pt、框宽 520pt（40 字/行）、框高 22pt（只容 1 行，
       2 行 = 36pt 就超）⇒ 超过 40 字即溢出。
       而 L03 只查 `title`，副标题再长也不报 ⇒ L15 是唯一一道能抓住它的判据。
    """
    spec["slides"][0]["subtitle"] = (
        "两学时 · 需要带上自己拍的偏暗照片 · 上课前请先复习灰度级与直方图的基本概念"
        "并带笔记本电脑现场做一次对比实验")
    return spec, "L15"


# ── 大纲先行层 ───────────────────────────────────────────────────
def m_outline_step_no_minutes(spec):
    del spec["modules"][0]["steps"][0]["minutes"]
    return spec, "OL-P03"


def m_outline_module_time(spec):
    spec["modules"][0]["minutes"] = 99
    return spec, "OL-P04"


def m_outline_total_time(spec):
    spec["meta"]["minutes"] = 100
    return spec, "OL-P05"


def m_outline_step_objective_unknown(spec):
    spec["modules"][0]["steps"][0]["objective"] = "O9"
    return spec, "OL-P06"


def m_outline_module_objective_unknown(spec):
    spec["modules"][0]["objectives"] = ["O1", "O9"]
    return spec, "OL-P07"


def m_outline_no_intent(spec):
    spec["modules"][0]["steps"][0]["intent"] = ""
    return spec, "OL-P08"


def m_outline_step_no_slides_no_reason(spec):
    """环节既没页面也没写 no_slide_reason —— 分不清是设计使然还是漏做课件。"""
    st = spec["modules"][1]["steps"][1]          # S4：本来靠 no_slide_reason 过关
    st.pop("slides", None)
    st.pop("no_slide_reason", None)
    return spec, "OL-P09"


def m_outline_slide_no_notes(spec):
    del spec["modules"][0]["steps"][0]["slides"][0]["notes"]
    return spec, "OL-P10"


def m_outline_no_cover(spec):
    # 封面用了要点页布局 —— 既不是 title（正式封面）也不是 section（续讲课分节页）
    spec["deck"]["cover"]["layout"] = "bullets"
    return spec, "OL-P11"


def m_outline_two_title_pages(spec):
    # 环节里又出现一个 title 版式 ⇒ 全稿两个封面
    spec["modules"][0]["steps"][0]["slides"][0]["layout"] = "title"
    return spec, "OL-P11"


def m_outline_too_few_objectives(spec):
    spec["objectives"] = spec["objectives"][:2]
    return spec, "OL-P12"


def m_outline_objective_unbound(spec):
    del spec["objectives"][1]["course_objective"]
    return spec, "OL-P13"


def m_outline_too_few_questions(spec):
    spec["questions"] = spec["questions"][:2]
    return spec, "OL-P14"


def m_outline_placeholder(spec):
    spec["modules"][0]["title"] = "待补模块"
    return spec, "OL-P01"


# ── UbD 骨架（OL-P15 – OL-P18）─────────────────────────────────
def m_ubd_missing(spec):
    del spec["ubd"]
    return spec, "OL-P15"


def m_ubd_big_idea_no_situation(spec):
    # 写成知识点而不是持久理解（技能文档明写 ❌「理解 XX 原理」）
    spec["ubd"]["big_idea"] = ["理解直方图均衡化的基本原理"]
    return spec, "OL-P15"


def m_ubd_question_backable(spec):
    spec["ubd"]["essential_questions"][0]["text"] = "什么是频域？"
    return spec, "OL-P16"


def m_ubd_grasps_no_product(spec):
    del spec["ubd"]["grasps"]["product"]
    return spec, "OL-P17"


def m_ubd_whereto_unknown_step(spec):
    spec["ubd"]["whereto"]["rethink"]["step"] = "S99"
    return spec, "OL-P18"


def m_ubd_whereto_no_experience(spec):
    del spec["ubd"]["whereto"]["experience"]
    return spec, "OL-P18"


def m_slide_id_missing(spec):
    del spec["modules"][0]["steps"][0]["slides"][0]["id"]
    return spec, "OL-P19"


# ── 讲义（HD-P01 – HD-P04）────────────────────────────────────
def m_handout_notes_tampered(spec):
    # 有人绕过派生层手改了讲义的讲稿 —— 讲义与课件就不再同源
    for p in spec["pages"]:
        if p.get("kind") == "content":
            p["notes"] = p["notes"] + "（手改过的讲稿）"
            break
    return spec, "HD-P04"


def m_handout_page_missing(spec):
    spec["pages"] = spec["pages"][:-1]
    return spec, "HD-P03"


CASES = [
    ("大纲：环节缺 minutes", m_outline_step_no_minutes, "outline"),
    ("大纲：模块分钟与环节合计不符", m_outline_module_time, "outline"),
    ("大纲：本次课分钟与环节合计不符", m_outline_total_time, "outline"),
    ("大纲：环节绑定了不存在的目标", m_outline_step_objective_unknown, "outline"),
    ("大纲：模块绑定了不存在的目标", m_outline_module_objective_unknown, "outline"),
    ("大纲：环节缺设计意图", m_outline_no_intent, "outline"),
    ("大纲：环节既无页面也无 no_slide_reason", m_outline_step_no_slides_no_reason,
     "outline"),
    ("大纲：正文页没有讲稿", m_outline_slide_no_notes, "outline"),
    ("大纲：封面布局不对", m_outline_no_cover, "outline"),
    ("大纲：全稿出现第二个 title 版式页", m_outline_two_title_pages, "outline"),
    ("大纲：教学目标不足 3 条", m_outline_too_few_objectives, "outline"),
    ("大纲：目标没绑定课程目标编号", m_outline_objective_unbound, "outline"),
    ("大纲：预设提问不足 3 个", m_outline_too_few_questions, "outline"),
    ("大纲：残留占位符", m_outline_placeholder, "outline"),
    ("大纲：缺 UbD 骨架", m_ubd_missing, "outline"),
    ("大纲：持久理解写成了知识点", m_ubd_big_idea_no_situation, "outline"),
    ("大纲：基本问题写成能背定义的题", m_ubd_question_backable, "outline"),
    ("大纲：GRASPS 缺产物", m_ubd_grasps_no_product, "outline"),
    ("大纲：WHERETO 落在不存在的环节", m_ubd_whereto_unknown_step, "outline"),
    ("大纲：WHERETO 缺体验环节", m_ubd_whereto_no_experience, "outline"),
    ("大纲：页面没有 id", m_slide_id_missing, "outline"),
    ("教案：环节时间合计 ≠ 总学时", m_lesson_time_mismatch, "lesson_plan"),
    ("教案：目标没绑定课程目标编号", m_lesson_objective_unbound, "lesson_plan"),
    ("教案：留空字段没进需人工核验清单", m_lesson_missing_manual_entry, "lesson_plan"),
    ("教案：正文残留占位符", m_lesson_placeholder, "lesson_plan"),
    ("教案：教学过程缺设计意图", m_lesson_no_intent, "lesson_plan"),
    ("试卷：各题分值合计 ≠ 总分", m_exam_score_sum, "exam_paper"),
    ("试卷：认知层次分布合计 ≠ 总分", m_exam_cog_sum, "exam_paper"),
    ("试卷：题目缺评分细则", m_exam_no_scoring, "exam_paper"),
    ("试卷：题干残留占位符", m_exam_placeholder, "exam_paper"),
    ("幻灯片：一页 9 条要点", m_slides_too_many_bullets, "slides"),
    ("幻灯片：正文页没有讲稿", m_slides_no_notes, "slides"),
    ("幻灯片：标题是分类词不是断言", m_slides_vague_title, "slides"),
    ("幻灯片：出现第二个封面", m_slides_two_covers, "slides"),
    ("幻灯片：标题几何上放不下（字数合规但溢出）", m_slides_title_overflow, "slides"),
    ("讲义：讲稿被绕过派生层手改", m_handout_notes_tampered, "handout"),
    ("讲义：少了一页（与课件对不齐）", m_handout_page_missing, "handout"),
]

CHECKERS = {
    "outline": selfcheck.check_outline,
    "lesson_plan": selfcheck.check_lesson_plan,
    "exam_paper": selfcheck.check_exam_paper,
    "slides": selfcheck.check_slides,
    "handout": selfcheck.check_handout,
}


def _run_checker(task, spec, base):
    """跑判据。

    🔴 讲义的判据要**同时看课件**（"讲稿是否同源"必须两边比），
       所以它不是单参数 —— 这里统一收口，别处就不会漏传。
    """
    if task == "handout":
        return selfcheck.check_handout(spec, base["slides"])
    return CHECKERS[task](spec)


def main():
    base = {t: load(t) for t in ("outline", "lesson_plan", "exam_paper", "slides",
                                  "handout")}
    passed = 0
    failed = []

    # ① 基线：原始 spec 必须零 ERROR（否则说明判据本身写错了）
    for task, fn in CHECKERS.items():
        fs = _run_checker(task, copy.deepcopy(base[task]), base)
        errs = [f for f in fs if f.level == "ERROR"]
        if errs:
            failed.append("基线 %s 就有 %d 个 ERROR：%s"
                          % (task, len(errs), errs[0].message))
        else:
            passed += 1

    # ② 每个变异必须命中它指定的那条判据
    for label, mutator, task in CASES:
        spec = copy.deepcopy(base[task])
        spec, expect = mutator(spec)
        fs = _run_checker(task, spec, base)
        codes = set(f.rule for f in fs)
        if expect in codes:
            passed += 1
            print("  抓到 OK  %s" % label)
        else:
            failed.append("%s：期望命中 %s，实际命中 %s"
                          % (label, expect, sorted(codes)))
            print("  !! 漏检  %s（期望 %s，实际 %s）"
                  % (label, expect, sorted(codes)))

    # ③ 在线路径的**接线**（不发网络请求）：
    #    提示词必须能从技能文档里摘到规则 —— 技能文档改了小节标题，
    #    excerpt() 会抛错，这正是我们要的"响亮失败"而不是静默变弱。
    #
    # 🔴 两个坑都在这里踩过：
    #    ① `g` 只在 try 里赋值 ⇒ skill_grounding 抛错时，下面用 `g` 的
    #       那一轮会变成 UnboundLocalError，**把真正的错误盖掉**。
    #    ② 分档包（research）**不含教学技能** —— 那是分档的正常结果，
    #       不该算失败，但也**不能假装检查过**：跳过的任务要如实报出来。
    g = None
    present = []
    try:
        g = llm.skill_grounding()
        for task, rel, why in getattr(g, "missing", []):
            print("  跳过  %s（%s）" % (task, why))
        present = [t for t in ("outline", "lesson_plan", "exam_paper", "slides",
                               "page", "handout", "lint")
                   if t in g]
        ok = all(len(g[k].strip()) > 200 for k in present)
        if ok:
            passed += 1
            print("  抓到 OK  提示词能从技能文档摘到规则")
        else:
            failed.append("技能文档摘录为空：%s"
                          % {k: len(g[k]) for k in present})
            print("  !! 漏检  技能文档摘录为空")
    except Exception as e:
        failed.append("skill_grounding 失败（技能文档的小节标题变了？）：%s" % e)
        print("  !! 漏检  skill_grounding 失败：%s" % e)

    for task in present:
        try:
            msgs = llm.build_messages(task, {"course": "示例课程"}, g)
            user = msgs[1]["content"]
            if len(user) > 1500 and "课程信息" in user:
                passed += 1
            else:
                failed.append("%s 的提示词内容异常（长度 %d）" % (task, len(user)))
        except Exception as e:
            failed.append("%s 的提示词组装失败：%s" % (task, e))

    # ④ JSON 提取：模型常加代码块围栏或前后废话
    for label, raw, ok in (
            ("裸 JSON", '{"a": 1}', True),
            ("带围栏", '```json\n{"a": 1}\n```', True),
            ("带废话", '好的，这是结果：\n{"a": 1}\n希望有用', True),
            ("没有 JSON", '完全不是 JSON', False)):
        try:
            got = llm.extract_json(raw)
            good = (got.get("a") == 1) if ok else False
        except llm.LLMError:
            good = not ok
        if good:
            passed += 1
            print("  抓到 OK  JSON 提取：%s" % label)
        else:
            failed.append("JSON 提取用例失败：%s" % label)
            print("  !! 漏检  JSON 提取用例失败：%s" % label)

    # ⑤ 增量重生成：**只重跑一页 ⇒ 其余页逐字不动**
    #    这不是变异测试（不是注入错误），而是**不变量**：
    #    增量替换一旦漏到别处，其余页的指纹就会变 —— 那正是它要防的失败模式。
    outline = copy.deepcopy(base["outline"])
    before = outline_mod.page_fingerprints(outline)
    target = "P5"
    new_page = copy.deepcopy(outline_mod.page_context(outline, target)["current"])
    new_page["title"] = "改过的标题"
    outline2, changed = outline_mod.replace_page(outline, target, new_page)
    after = outline_mod.page_fingerprints(outline2)
    touched = sorted(k for k in before if before[k] != after.get(k))
    if changed and touched == [target] and len(before) == len(after):
        passed += 1
        print("  抓到 OK  增量重生成只动了 %s（其余 %d 页不变）"
              % (target, len(before) - 1))
    else:
        failed.append("增量重生成漏到了别处：动了 %s" % touched)
        print("  !! 漏检  增量重生成动了 %s" % touched)

    # ⑤b 找不到的页面 id ⇒ 明确失败，不静默通过
    _, ok2 = outline_mod.replace_page(outline, "P999", {"title": "x"})
    if not ok2:
        passed += 1
        print("  抓到 OK  增量重生成对不存在的页面 id 明确失败")
    else:
        failed.append("增量重生成对不存在的页面 id 竟然成功了")
        print("  !! 漏检  增量重生成对不存在的页面 id 竟然成功了")

    # ⑥ 模型路由：按用途取到各自的模型
    saved = {k: os.environ.get(k) for k in
             ("JFA_LLM_MODEL", "JFA_LLM_MODEL_PLAN", "JFA_LLM_MODEL_SLIDES",
              "JFA_LLM_MODEL_HANDOUT", "JFA_LLM_MODEL_LINT")}
    try:
        for k in saved:
            os.environ.pop(k, None)
        os.environ["JFA_LLM_MODEL"] = "默认模型"
        os.environ["JFA_LLM_MODEL_SLIDES"] = "课件模型"
        os.environ["JFA_LLM_MODEL_LINT"] = "审校模型"
        got = {
            "outline": llm.resolve_model("outline"),
            "lesson_plan": llm.resolve_model("lesson_plan"),
            "slides": llm.resolve_model("slides"),
            "page": llm.resolve_model("page"),
            "handout": llm.resolve_model("handout"),
            "lint": llm.resolve_model("lint"),
        }
        want = {"outline": "默认模型", "lesson_plan": "默认模型",
                "slides": "课件模型", "page": "课件模型",
                "handout": "默认模型", "lint": "审校模型"}
        if got == want:
            passed += 1
            print("  抓到 OK  模型按用途路由（plan/slides/handout/lint）")
        else:
            failed.append("模型路由不对：%s" % got)
            print("  !! 漏检  模型路由不对：%s" % got)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    print("")
    if failed:
        print("selftest 未通过：%d 项失败" % len(failed))
        for f in failed:
            print("   - " + f)
        return 1
    print("selftest: %d/%d checks passed" % (passed, passed + len(failed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
