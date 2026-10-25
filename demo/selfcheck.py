#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""selfcheck.py —— 交付物的**机器自检**（纯标准库）

为什么 Demo 要自带自检
----------------------
这个仓库的产品主张不是「AI 帮你写教案」，而是「**给你一份能直接交上去、
而且它自己检查过的**文件」。那「检查过」就必须是真的检查 —— 机器跑的，
不是"我看了看觉得没问题"。

所以自检分两层：

1. **本模块**：教案与试卷的**形式合规**（学时/分值合计必须对得上、
   事实项不能编造、必须有需人工核验清单……）。
   这几条对应本仓库写在 agent.md 里的硬纪律。
2. **`slide_spec_lint.py`**：幻灯片的**教学规范**（一页几条要点、
   标题是不是断言、讲稿有没有、来源标注有没有）。

⚠️ 本模块**不判断教学内容对不对** —— 那是教师的事。
它只保证「形式上站得住」+「编造的东西露出来」。
"""
from __future__ import annotations

import importlib.util
import os
import re

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"

# 交付物里出现即不合格的占位符 —— 与 slide_spec_lint 的判据同源
PLACEHOLDER = re.compile(
    r"(待补|待定|待填|待核|待确认|TBD|TODO|FIXME|XXX+|xxxx|Lorem ipsum|占位|示例文字)")

# 不可检验的目标动词 —— 有这些词且没有可观察动词时给出提示
VAGUE_VERB = re.compile(r"(了解|熟悉|掌握|理解|认识|了解并)")

# 可观察的行为动词
OBSERVABLE_VERB = re.compile(
    r"(能|会|能够|可|学会|完成|分析|比较|计算|推导|设计|解释|判断|选择|"
    r"评价|设计并|验证|归纳|重构|迁移)")


class Finding(object):
    __slots__ = ("level", "rule", "where", "message")

    def __init__(self, level, rule, where, message):
        self.level = level
        self.rule = rule
        self.where = where
        self.message = message

    def as_dict(self):
        return {"level": self.level, "rule": self.rule,
                "where": self.where, "message": self.message}

    def __str__(self):
        return "[%s] %s %s：%s" % (self.level, self.rule, self.where, self.message)


def _add(out, level, rule, where, msg):
    out.append(Finding(level, rule, where, msg))


# ─────────────────────────────────────────────────────────────────
# 通用：占位符残留 + 需人工核验清单
# ─────────────────────────────────────────────────────────────────
def _walk_strings(node, path=""):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            for p, s in _walk_strings(v, "%s.%s" % (path, k) if path else str(k)):
                yield p, s
    elif isinstance(node, list):
        for i, v in enumerate(node):
            for p, s in _walk_strings(v, "%s[%d]" % (path, i)):
                yield p, s


def check_no_placeholder(spec, out, tag):
    """交付物里不得残留占位符。

    🔴 缺事实的正确表达是「**字段留空 + 写进需人工核验清单**」，
    不是留一个 `待补` 让人以为填了。
    """
    for path, text in _walk_strings(spec):
        if path.startswith("needs_manual_check"):
            continue  # 清单条目本身就是在描述"还缺什么"
        m = PLACEHOLDER.search(text)
        if m:
            _add(out, ERROR, "%s-P01" % tag, path,
                 "残留占位符 %r —— 缺事实请留空并写进需人工核验清单" % m.group(0))


def _manual_check_covers(spec, fields, out, tag):
    """留空的事实字段，必须在需人工核验清单里有对应条目。

    清单条目推荐写成 `{"field": "course_code", "desc": "…"}` ——
    `field` 让机器能对上号，`desc` 让人读得懂。写纯文本时退回按子串匹配。
    """
    checklist = spec.get("needs_manual_check") or []
    covered = set()
    blob = ""
    for e in checklist:
        if isinstance(e, dict):
            f = e.get("field")
            if f:
                covered.add(str(f))
            blob += " " + str(e.get("desc", ""))
        else:
            blob += " " + str(e)
    for f in fields:
        val = (spec.get("meta") or {}).get(f)
        if val in (None, "", []):
            if f not in covered and f not in blob:
                _add(out, WARN, "%s-P02" % tag, "meta.%s" % f,
                     "该字段留空，但需人工核验清单里没有提到它（清单里应出现 %r）" % f)


# ─────────────────────────────────────────────────────────────────
# 教案
# ─────────────────────────────────────────────────────────────────
def check_lesson_plan(spec):
    out = []
    meta = spec.get("meta") or {}
    tag = "LP"

    check_no_placeholder(spec, out, tag)

    # 时长合计必须等于本次课总时长（仓库硬纪律：不是流水账）
    minutes = meta.get("minutes")
    total = 0
    for i, seg in enumerate(spec.get("process") or []):
        m = seg.get("minutes")
        if not isinstance(m, (int, float)):
            _add(out, ERROR, "%s-P03" % tag, "process[%d]" % i, "缺 minutes")
        else:
            total += int(m)
    if isinstance(minutes, (int, float)):
        if total != int(minutes):
            _add(out, ERROR, "%s-P04" % tag, "process",
                 "各环节时间合计 %d 分钟 ≠ 本次课 %d 分钟（教案不能是流水账）"
                 % (total, int(minutes)))
    else:
        _add(out, ERROR, "%s-P05" % tag, "meta.minutes", "缺本次课总时长")

    # 教学目标：数量 + 可观察 + 绑定课程目标编号
    objs = spec.get("objectives") or []
    if len(objs) < 3:
        _add(out, ERROR, "%s-P06" % tag, "objectives",
             "教学目标只有 %d 条，应 3–5 条" % len(objs))
    for i, o in enumerate(objs):
        text = str(o.get("text", ""))
        if not OBSERVABLE_VERB.search(text):
            _add(out, WARN, "%s-P07" % tag, "objectives[%d]" % i,
                 "目标「%s」没有可观察的行为动词（能/会/能够分析…）" % text[:24])
        elif VAGUE_VERB.match(text.strip()):
            _add(out, WARN, "%s-P08" % tag, "objectives[%d]" % i,
                 "目标以「%s」开头却用了不可检验的说法" % VAGUE_VERB.match(text).group(0))
        if not o.get("course_objective"):
            _add(out, ERROR, "%s-P09" % tag, "objectives[%d]" % i,
                 "目标没有绑定课程目标编号（无法做目标—证据对齐）")

    # 教学过程：每段要有教师活动/学生活动/设计意图/对应目标
    for i, seg in enumerate(spec.get("process") or []):
        for field, label in (("teacher", "教师活动"), ("student", "学生活动"),
                             ("intent", "设计意图")):
            if not str(seg.get(field, "")).strip():
                _add(out, ERROR, "%s-P10" % tag, "process[%d]" % i,
                     "缺%s —— 没有%s的环节只是流水账" % (label, label))
        if not seg.get("objective"):
            _add(out, ERROR, "%s-P11" % tag, "process[%d]" % i,
                 "未标注对应的教学目标")

    # 课堂提问 ≥ 3
    qs = spec.get("questions") or []
    if len(qs) < 3:
        _add(out, ERROR, "%s-P12" % tag, "questions",
             "预设提问只有 %d 个，应至少 3 个" % len(qs))
    for i, q in enumerate(qs):
        if not q.get("expected"):
            _add(out, WARN, "%s-P13" % tag, "questions[%d]" % i,
                 "没有预期回答 —— 教师无法预判课堂走向")

    # 作业
    if not (spec.get("homework") or []):
        _add(out, ERROR, "%s-P14" % tag, "homework", "没有课后作业")

    # 事实性字段留空 → 需人工核验清单要提到
    _manual_check_covers(spec, ["course_code", "teacher", "date", "textbook"],
                          out, tag)
    return out


# ─────────────────────────────────────────────────────────────────
# 试卷
# ─────────────────────────────────────────────────────────────────
def check_exam_paper(spec):
    out = []
    meta = spec.get("meta") or {}
    design = spec.get("design") or {}
    tag = "EX"

    check_no_placeholder(spec, out, tag)

    total = meta.get("total_score")
    if not isinstance(total, (int, float)):
        _add(out, ERROR, "%s-P01" % tag, "meta.total_score", "缺总分")
        total = 0

    # ① 试题分值合计必须等于总分（仓库硬纪律：评价权重合计 = 100%）
    qs = spec.get("questions") or []
    s = 0
    for i, q in enumerate(qs):
        sc = q.get("score")
        if not isinstance(sc, (int, float)):
            _add(out, ERROR, "%s-P02" % tag, "questions[%d]" % i, "缺分值")
        else:
            s += sc
        if not str(q.get("stem", "")).strip():
            _add(out, ERROR, "%s-P03" % tag, "questions[%d]" % i, "缺题干")
        if not q.get("answer"):
            _add(out, ERROR, "%s-P04" % tag, "questions[%d]" % i, "缺答案")
        if not q.get("scoring"):
            _add(out, ERROR, "%s-P05" % tag, "questions[%d]" % i, "缺评分细则")
        if not q.get("objective"):
            _add(out, ERROR, "%s-P06" % tag, "questions[%d]" % i, "未绑定考核目标")
        if not q.get("cognitive"):
            _add(out, ERROR, "%s-P07" % tag, "questions[%d]" % i, "未标注认知层次")
    if qs and s != int(total):
        _add(out, ERROR, "%s-P08" % tag, "questions",
             "试题分值合计 %d ≠ 总分 %d" % (s, int(total)))

    # ② 目标—题型映射表、认知层次分布、难度分布：三者各自合计 = 总分
    for key, rule, label in (
            ("objective_type_matrix", "%s-P09" % tag, "目标—题型映射表"),
            ("cognitive_distribution", "%s-P10" % tag, "认知层次分布"),
            ("difficulty_distribution", "%s-P11" % tag, "难度分布")):
        rows = design.get(key) or []
        if not rows:
            _add(out, ERROR, rule, "design." + key, "缺%s" % label)
            continue
        acc = 0
        for j, r in enumerate(rows):
            v = r.get("score")
            if not isinstance(v, (int, float)):
                _add(out, ERROR, rule, "design.%s[%d]" % (key, j), "缺分值")
            else:
                acc += v
        if acc != int(total):
            _add(out, ERROR, rule, "design." + key,
                 "%s分值合计 %d ≠ 总分 %d" % (label, acc, int(total)))

    # ③ 题号连续
    nos = [q.get("no") for q in qs]
    if nos and nos != list(range(1, len(nos) + 1)):
        _add(out, WARN, "%s-P12" % tag, "questions", "题号不连续：%s" % nos)

    # ④ 备用卷
    if not (spec.get("backup") or {}).get("questions"):
        _add(out, WARN, "%s-P13" % tag, "backup",
             "没有备用卷 B —— 考试泄题后无卷可用")

    # ⑤ 事实项
    _manual_check_covers(spec, ["course_code", "date", "duration_minutes"], out, tag)
    return out


# ─────────────────────────────────────────────────────────────────
# 大纲先行层
# ─────────────────────────────────────────────────────────────────
def check_outline(outline):
    """大纲自检：**在大纲层就能查的，不要留到下游查**。

    大纲是教案与课件的唯一事实源。下游（教案/课件）能查的判据在下游查；
    这里只管**大纲自己**的结构闭合，以及**大纲层特有**的两件事：

    ① 时间三层闭合：本次课分钟 = Σ 模块分钟 = Σ 环节分钟
    ② 页面—环节绑定：每个环节要么有配套页面，要么写明为什么没有

    🔴 ② 里"没有页面"有两种成因，必须分开：
       - **设计使然**（本环节就是学生活动，不投影）⇒ 写了 no_slide_reason 就算过
       - **漏做课件**（该有页面却没做）⇒ 没写原因 ⇒ 报错
       只看"页数为 0"会把前者也当成错误，反过来不写原因又会把漏做放过去。
    """
    out = []
    tag = "OL"
    meta = outline.get("meta") or {}
    objectives = outline.get("objectives") or []
    obj_ids = set(str(o.get("id")) for o in objectives if o.get("id"))
    modules = outline.get("modules") or []
    deck = outline.get("deck") or {}

    # OL-P01 = 占位符、OL-P02 = 需人工核验覆盖（与 LP/EX 同一套约定，不另起编号）
    check_no_placeholder(outline, out, tag)

    # ① 目标：数量 + 绑定课程目标编号
    if len(objectives) < 3:
        _add(out, ERROR, "%s-P12" % tag, "objectives",
             "教学目标只有 %d 条，应 3–5 条" % len(objectives))
    for i, o in enumerate(objectives):
        if not o.get("course_objective"):
            _add(out, ERROR, "%s-P13" % tag, "objectives[%d]" % i,
                 "目标没有绑定课程目标编号（无法做目标—证据对齐）")

    # ② 时间三层闭合
    total_steps = 0
    for mi, m in enumerate(modules):
        m_total = 0
        for si, s in enumerate(m.get("steps") or []):
            where = "modules[%d](%s).steps[%d](%s)" % (mi, m.get("id"), si, s.get("id"))
            mins = s.get("minutes")
            if not isinstance(mins, (int, float)):
                _add(out, ERROR, "%s-P03" % tag, where, "环节缺 minutes")
            else:
                m_total += int(mins)
        total_steps += m_total
        declared = m.get("minutes")
        if isinstance(declared, (int, float)) and int(declared) != m_total:
            _add(out, ERROR, "%s-P04" % tag, "modules[%d](%s)" % (mi, m.get("id")),
                 "模块声明 %s 分钟，与其环节合计 %d 分钟不符" % (declared, m_total))
    minutes = meta.get("minutes")
    if not isinstance(minutes, (int, float)):
        _add(out, ERROR, "%s-P05" % tag, "meta.minutes", "缺本次课总时长")
    elif int(minutes) != total_steps:
        _add(out, ERROR, "%s-P05" % tag, "meta.minutes",
             "本次课 %d 分钟 ≠ 各环节合计 %d 分钟" % (int(minutes), total_steps))

    # ③ 目标闭合 + 环节三要素 + 页面绑定
    for mi, m in enumerate(modules):
        for oid in m.get("objectives") or []:
            if str(oid) not in obj_ids:
                _add(out, ERROR, "%s-P07" % tag, "modules[%d](%s)" % (mi, m.get("id")),
                     "模块声明的目标 %r 不在教学目标里" % oid)
        for si, s in enumerate(m.get("steps") or []):
            where = "modules[%d](%s).steps[%d](%s)" % (mi, m.get("id"), si, s.get("id"))
            oid = s.get("objective")
            if not oid:
                _add(out, ERROR, "%s-P06" % tag, where, "环节未标注对应的教学目标")
            elif str(oid) not in obj_ids:
                _add(out, ERROR, "%s-P06" % tag, where,
                     "环节对应的目标 %r 不在教学目标里" % oid)
            for field, label in (("teacher", "教师活动"), ("student", "学生活动"),
                                 ("intent", "设计意图")):
                if not str(s.get(field, "")).strip():
                    _add(out, ERROR, "%s-P08" % tag, where,
                         "缺%s —— 没有%s的环节只是流水账" % (label, label))
            slides = s.get("slides") or []
            if not slides and not str(s.get("no_slide_reason", "")).strip():
                _add(out, ERROR, "%s-P09" % tag, where,
                     "环节既没有配套页面也没写 no_slide_reason —— "
                     "分不清是「本环节不投影」还是「漏做课件」")

    # ④ 页面：正文页必须有讲稿；封面唯一且在首位
    all_steps = [st for m in modules for st in (m.get("steps") or [])]
    cover = deck.get("cover") or {}
    if cover.get("layout") not in ("title", "section"):
        _add(out, ERROR, "%s-P11" % tag, "deck.cover",
             "封面缺失或 layout 不是 title/section")
    # 🔴 「封面唯一」的真正含义是**全稿只有一个 title 版式** ——
    #    续讲课（第 2 次课、第 3 次课…）的分节页本来就承担「这一讲的开场」角色，
    #    它的 layout 是 section 而不是 title。
    #    所以判据落在「title 版式最多一个」，而不是「cover 必须是 title」——
    #    后者会把合法的续讲课判成错。
    n_title = 0
    for pg in (deck.get("cover"), deck.get("agenda")):
        if isinstance(pg, dict) and pg.get("layout") == "title":
            n_title += 1
    for st in all_steps:
        for sl in (st.get("slides") or []):
            if sl.get("layout") == "title":
                n_title += 1
    if n_title > 1:
        _add(out, ERROR, "%s-P11" % tag, "deck",
             "全稿有 %d 个 title 版式页 —— 封面只能有一个" % n_title)
    agenda = deck.get("agenda") or {}
    if agenda and agenda.get("layout") == "title":
        _add(out, ERROR, "%s-P11" % tag, "deck.agenda",
             "目录页用了 title 布局 —— 封面只能有一个，章节过渡请用 section")
    for s in all_steps:
        for pi, sl in enumerate(s.get("slides") or []):
            where = "step(%s).slides[%d]" % (s.get("id"), pi)
            if sl.get("layout") in ("bullets", "two-column", "image-focus") \
                    and not str(sl.get("notes", "")).strip():
                _add(out, ERROR, "%s-P10" % tag, where,
                     "正文页没有讲稿备注；幻灯片给观众看，讲稿给讲授者用")

    # ⑤ 提问
    if len(outline.get("questions") or []) < 3:
        _add(out, ERROR, "%s-P14" % tag, "questions", "预设提问不足 3 个")

    # ⑥ UbD 骨架：大概念 / 基本问题 / GRASPS / WHERETO
    #    判据来自 skills/teaching-file-builder/SKILL.md「UbD 骨架」一节
    #    （内核适配自 skills/backwards-design-unit-planner 的 UbD 三阶段）。
    _check_ubd(outline, out, tag, obj_ids, [s.get("id") for s in all_steps])

    # ⑦ 页面 id：增量重生成靠它定位，id 必须存在且唯一
    ids = []
    for s in all_steps:
        for pi, sl in enumerate(s.get("slides") or []):
            pid = sl.get("id")
            where = "step(%s).slides[%d]" % (s.get("id"), pi)
            if not pid:
                _add(out, ERROR, "%s-P19" % tag, where,
                     "页面没有 id —— 增量重生成（只重跑一页）靠 id 定位")
            else:
                ids.append(pid)
    for key in ("cover", "agenda"):
        pg = (deck.get(key) or {})
        if pg and not pg.get("id"):
            _add(out, ERROR, "%s-P19" % tag, "deck.%s" % key,
                 "页面没有 id —— 增量重生成（只重跑一页）靠 id 定位")
        elif pg:
            ids.append(pg.get("id"))
    dup = sorted(set(i for i in ids if i and ids.count(i) > 1))
    if dup:
        _add(out, ERROR, "%s-P19" % tag, "slides",
             "页面 id 重复：%s" % ", ".join(dup))

    # ⑧ 事实性字段留空 → 需人工核验清单要提到
    _manual_check_covers(outline, ["course_code", "teacher", "date", "textbook"],
                         out, tag)
    return out


# ─────────────────────────────────────────────────────────────────
# UbD 骨架
# ─────────────────────────────────────────────────────────────────
# GRASPS 六要素：G/R/A/S/P/S —— 缺一两项不致命，但 P 与 S 必须实
GRASPS_FIELDS = (
    ("goal", "G·Goal 目标", WARN),
    ("role", "R·Roles 角色", WARN),
    ("audience", "A·Audience 受众", WARN),
    ("situation", "S·Situation 情境", WARN),
    ("product", "P·Product 产物", ERROR),
    ("standards", "S·Standards 标准", ERROR),
)

# WHERETO 七项：技能文档里 E 出现两次（Equip / Experience），
# 所以用**不缩写**的键名，避免 E 撞车。
WHERETO_FIELDS = (
    ("where", "W·Where&Why 情境与意义"),
    ("hook", "H·Hook 钩子"),
    ("equip", "E·Equip 装备"),
    ("experience", "E·Experience 体验"),
    ("rethink", "R·Rethink&Revise 反思与修订"),
    ("tailor", "T·Tailor 因材施教"),
    ("organize", "O·Organize 组织"),
)

# 基本问题写成能背的题的典型开头（技能文档明写 ❌「什么是频域？」）
BACKABLE_QUESTION_START = re.compile(r"^\s*(什么是|是什么|定义|请解释|简述)")


def _check_ubd(outline, out, tag, obj_ids, step_ids):
    """UbD 骨架自检：大概念 / 基本问题 / GRASPS / WHERETO。

    🔴 判据全部**可机械判定**，且逐条对应技能文档里写死的写法要求 ——
       不做"读起来像不像"的主观判断。
    """
    ubd = outline.get("ubd")
    if not isinstance(ubd, dict) or not ubd:
        _add(out, ERROR, "%s-P15" % tag, "ubd",
             "大纲缺 UbD 骨架（持久理解 / 基本问题 / GRASPS / WHERETO）—— "
             "没有它，「这次课凭什么这样设计」无从查起")
        return

    # ── 持久理解 ──
    big = ubd.get("big_idea") or []
    if not isinstance(big, list) or not (1 <= len(big) <= 3):
        _add(out, ERROR, "%s-P15" % tag, "ubd.big_idea",
             "持久理解应有 1–3 条，实为 %d 条（多了会退化成章节标题的改写）"
             % len(big) if isinstance(big, list) else "持久理解格式不对")
    for i, b in enumerate(big if isinstance(big, list) else []):
        t = str(b)
        where = "ubd.big_idea[%d]" % i
        if not t.strip():
            _add(out, ERROR, "%s-P15" % tag, where, "持久理解为空")
            continue
        # 写法公式：「学生能理解 ___，并在 ___ 情境中用它」
        if "能理解" not in t:
            _add(out, ERROR, "%s-P15" % tag, where,
                 "持久理解没写成「学生能理解 ……」（写成了知识点，无法迁移）")
        if "情境" not in t:
            _add(out, ERROR, "%s-P15" % tag, where,
                 "持久理解没写「在 …… 情境中用它」（缺迁移场景）")

    # ── 基本问题 ──
    eqs = ubd.get("essential_questions") or []
    if not isinstance(eqs, list) or not (3 <= len(eqs) <= 5):
        _add(out, ERROR, "%s-P16" % tag, "ubd.essential_questions",
             "基本问题应有 3–5 个，实为 %d 个" % len(eqs)
             if isinstance(eqs, list) else "基本问题格式不对")
    seen_eq = set()
    for i, q in enumerate(eqs if isinstance(eqs, list) else []):
        where = "ubd.essential_questions[%d]" % i
        text = str((q or {}).get("text", "")) if isinstance(q, dict) else str(q)
        if not text.strip():
            _add(out, ERROR, "%s-P16" % tag, where, "基本问题为空")
            continue
        if BACKABLE_QUESTION_START.match(text):
            _add(out, ERROR, "%s-P16" % tag, where,
                 "基本问题写成能背定义的题（%s）—— 能背定义回答的题不指向持久理解"
                 % text[:20])
        qid = str((q or {}).get("id", "")) if isinstance(q, dict) else ""
        if qid and qid in seen_eq:
            _add(out, ERROR, "%s-P16" % tag, where, "基本问题编号重复：%s" % qid)
        seen_eq.add(qid)

    # ── GRASPS ──
    grasps = ubd.get("grasps")
    if not isinstance(grasps, dict) or not grasps:
        _add(out, ERROR, "%s-P17" % tag, "ubd.grasps",
             "缺表现性任务的 GRASPS 六要素（没有它就没有真实性证据）")
    else:
        for key, label, level in GRASPS_FIELDS:
            if not str(grasps.get(key, "")).strip():
                _add(out, level, "%s-P17" % tag, "ubd.grasps.%s" % key,
                     "GRASPS 缺 %s" % label
                     + ("（P 与 S 必须实 —— 缺了就没有可检验的成品与达标标准）"
                        if level == ERROR else ""))

    # ── WHERETO ──
    wh = ubd.get("whereto")
    if not isinstance(wh, dict) or not wh:
        _add(out, ERROR, "%s-P18" % tag, "ubd.whereto",
             "缺 WHERETO 覆盖表（答不出落在哪的项就是设计漏洞）")
    else:
        known = set(s for s in step_ids if s)
        for key, label in WHERETO_FIELDS:
            item = wh.get(key)
            where = "ubd.whereto.%s" % key
            if not isinstance(item, dict) or not str(item.get("step", "")).strip():
                _add(out, ERROR, "%s-P18" % tag, where,
                     "WHERETO 的 %s 没写「落在哪个环节」" % label)
                continue
            st = str(item.get("step"))
            if st not in known:
                _add(out, ERROR, "%s-P18" % tag, where,
                     "WHERETO 的 %s 落在环节 %r，但大纲里没有这个环节" % (label, st))
            if key in ("experience", "rethink") \
                    and not str(item.get("note", "")).strip():
                _add(out, ERROR, "%s-P18" % tag, where,
                     "%s 的说明为空 —— 这两项最常漏" % label)


# ─────────────────────────────────────────────────────────────────
# 讲义（handout）
# ─────────────────────────────────────────────────────────────────
def check_handout(spec, slides_spec=None):
    """讲义自检：**讲稿必须与课件逐字同源**。

    🔴 这条判据是「讲义层」存在的全部理由。
       讲义是纯派生的（讲稿从课件规格搬过来），所以「讲义讲稿 ≠ 课件讲稿」
       只可能意味着**有人绕过派生层手改了讲义** —— 那是要抓的。
       与其相信"我们只从大纲生成"，不如**每次都比一遍**：判据要能证伪。

    slides_spec 为空时只做讲义自身的检查（不与课件对照）。
    """
    out = []
    tag = "HD"
    pages = spec.get("pages") or []
    if not pages:
        _add(out, ERROR, "%s-P01" % tag, "pages", "讲义没有任何页面")
        return out

    ids = []
    for i, p in enumerate(pages):
        where = "pages[%d]" % i
        pid = p.get("id")
        if not pid:
            _add(out, ERROR, "%s-P01" % tag, where, "讲义页缺 id（与课件页对不齐）")
        else:
            ids.append(pid)
        if p.get("kind") == "content" and not str(p.get("notes", "")).strip():
            _add(out, ERROR, "%s-P02" % tag, where,
                 "正文页没有讲稿 —— 讲义是给讲授者拿着讲的")

    dup = sorted(set(x for x in ids if x and ids.count(x) > 1))
    if dup:
        _add(out, ERROR, "%s-P01" % tag, "pages", "讲义页 id 重复：%s" % ", ".join(dup))

    if slides_spec:
        spages = {s.get("id"): s for s in (slides_spec.get("slides") or []) if s.get("id")}
        if len(spages) != len(pages):
            _add(out, ERROR, "%s-P03" % tag, "pages",
                 "讲义 %d 页 vs 课件 %d 页 —— 页数对不上" % (len(pages), len(spages)))
        for i, p in enumerate(pages):
            pid = p.get("id")
            s = spages.get(pid)
            if s is None:
                _add(out, ERROR, "%s-P03" % tag, "pages[%d]" % i,
                     "讲义页 %s 在课件里找不到" % pid)
                continue
            if str(p.get("notes", "")) != str(s.get("notes", "")):
                _add(out, ERROR, "%s-P04" % tag, "pages[%d](%s)" % (i, pid),
                     "讲义讲稿与课件讲稿不一致 —— 讲稿应当只有一份（从课件导出）")
            if str(p.get("title", "")) != str(s.get("title", "")):
                _add(out, ERROR, "%s-P04" % tag, "pages[%d](%s)" % (i, pid),
                     "讲义标题与课件标题不一致 —— 讲义应当从课件派生")
    return out


# ─────────────────────────────────────────────────────────────────
# 幻灯片：复用仓库自带的教学规范审查器
# ─────────────────────────────────────────────────────────────────
def _load_skill_module(rel_path, name):
    """按路径加载技能里的脚本（不硬编码任何机器绝对路径）。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, rel_path.replace("/", os.sep))
    if not os.path.isfile(path):
        raise IOError("找不到 %s" % rel_path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_slides(spec):
    """幻灯片自检：直接用仓库自带的 slide_spec_lint（判据不重写一份）。"""
    out = []
    try:
        lint = _load_skill_module(
            "skills/teaching-slide-builder/scripts/slide_spec_lint.py",
            "jfa_slide_spec_lint")
    except Exception as e:
        _add(out, ERROR, "SL-P00", "slide_spec_lint", "加载失败：%s" % e)
        return out
    for f in lint.lint(spec):
        out.append(Finding(f.level, f.code,
                            ("第 %d 页" % f.slide) if f.slide else "整体", f.msg))
    return out


# ─────────────────────────────────────────────────────────────────
def summarize(findings):
    err = sum(1 for f in findings if f.level == ERROR)
    warn = sum(1 for f in findings if f.level == WARN)
    info = sum(1 for f in findings if f.level == INFO)
    return {"error": err, "warn": warn, "info": info, "total": len(findings)}
