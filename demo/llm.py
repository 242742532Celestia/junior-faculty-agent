#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""llm.py —— 可插拔的模型后端（OpenAI 兼容协议，纯标准库）

设计取舍
--------
**Demo 的价值不在"调哪个模型"，而在"规格 → 交付物 → 自检"这条链**。
所以模型后端刻意做成最通用的一种：OpenAI 兼容的 `/chat/completions`。
下面这些都能直接用，只要换 base_url / model：

    通义千问   https://dashscope.aliyuncs.com/compatible-mode/v1   qwen-plus
    DeepSeek   https://api.deepseek.com/v1                          deepseek-chat
    MiniMax    https://api.minimax.chat/v1                          MiniMax-M3
    本地 Ollama http://127.0.0.1:11434/v1                           qwen2.5:14b

配置走环境变量（**不写进仓库**）：

    JFA_LLM_BASE_URL   例：https://dashscope.aliyuncs.com/compatible-mode/v1
    JFA_LLM_API_KEY
    JFA_LLM_MODEL      例：qwen-plus

🔴 **提示词里的"规则"全部来自仓库里的技能文档**，不是在这里另写一套。
   本模块只负责把 `skills/*/SKILL.md` 的相关章节**摘出来**塞进提示词，
   以及把课程信息填进去。技能改了，提示词跟着改 —— 不存在两份规则。
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


class LLMError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────
# 技能文档摘录
# ─────────────────────────────────────────────────────────────────
def read_skill(rel):
    p = os.path.join(ROOT, rel.replace("/", os.sep))
    if not os.path.isfile(p):
        raise LLMError("找不到技能文档：%s" % rel)
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def excerpt(text, start, end=None):
    """按二级/三级标题截取一节。找不到就报错 —— 静默取空会让提示词悄悄变弱。"""
    i = text.find(start)
    if i < 0:
        raise LLMError("技能文档里找不到小节：%s" % start)
    j = len(text)
    if end:
        k = text.find(end, i + len(start))
        if k >= 0:
            j = k
    else:
        m = re.search(r"\n## ", text[i + len(start):])
        if m:
            j = i + len(start) + m.start()
    return text[i:j].strip()


class Grounding(dict):
    """技能规则底座。

    `.missing` 记录**因为技能不在本包里**而没有底座的任务。
    """

    def __init__(self, *a, **kw):
        dict.__init__(self, *a, **kw)
        self.missing = []


# 每个任务用哪份技能文档的哪些小节 —— **只此一份**
GROUNDING_PLAN = {
    "outline": {
        "docs": ["skills/teaching-file-builder/SKILL.md",
                 "skills/teaching-slide-designer/SKILL.md"],
        "build": lambda d: "\n\n".join([
            "【大纲先行层（唯一事实源）】\n"
            + excerpt(d["skills/teaching-file-builder/SKILL.md"],
                      "## 大纲先行层", "## 文件类型 1"),
            "【幻灯片规范与自检口径】\n"
            + excerpt(d["skills/teaching-slide-designer/SKILL.md"],
                      "## 易错点", "## 交叉技能"),
        ]),
    },
    "lesson_plan": {
        "docs": ["skills/teaching-file-builder/SKILL.md"],
        "build": lambda d: "\n\n".join([
            "【通用规则】\n"
            + excerpt(d["skills/teaching-file-builder/SKILL.md"],
                      "## 通用规则", "## 文件类型 1"),
            "【教案必备结构】\n"
            + excerpt(d["skills/teaching-file-builder/SKILL.md"],
                      "## 文件类型 2：教案", "## 文件类型 3"),
            "【交付前通用自检】\n"
            + excerpt(d["skills/teaching-file-builder/SKILL.md"],
                      "## 交付前通用自检", "## 交叉技能"),
        ]),
    },
    "exam_paper": {
        "docs": ["skills/exam-question-bank/SKILL.md"],
        "build": lambda d: "\n\n".join([
            "【输出格式】\n"
            + excerpt(d["skills/exam-question-bank/SKILL.md"],
                      "## 输出格式", "## 易错点")
            if "## 输出格式" in d["skills/exam-question-bank/SKILL.md"]
            else excerpt(d["skills/exam-question-bank/SKILL.md"], "## 输出格式"),
        ]),
    },
    "slides": {
        "docs": ["skills/teaching-slide-designer/SKILL.md",
                 "skills/teaching-slide-builder/SKILL.md"],
        "build": lambda d: "\n\n".join([
            "【幻灯片设计口径（写什么）】\n"
            + excerpt(d["skills/teaching-slide-designer/SKILL.md"],
                      "## 这个技能解决什么", "## 交叉技能"),
            "【规格 JSON 字段契约与版式（怎么写进文件）】\n"
            + excerpt(d["skills/teaching-slide-builder/SKILL.md"],
                      "## 输入", "## 执行步骤"),
        ]),
    },
    # 单页重生成：只为一页调一次模型（增量重生成的省钱点）
    "page": {
        "docs": ["skills/teaching-slide-designer/SKILL.md",
                 "skills/teaching-slide-builder/SKILL.md"],
        "build": lambda d: "\n\n".join([
            "【幻灯片设计口径（写什么）】\n"
            + excerpt(d["skills/teaching-slide-designer/SKILL.md"],
                      "## 这个技能解决什么", "## 交叉技能"),
            "【规格 JSON 字段契约与版式（怎么写进文件）】\n"
            + excerpt(d["skills/teaching-slide-builder/SKILL.md"],
                      "## 输入", "## 执行步骤"),
        ]),
    },
    # 判读/审校类：改稿前先让它挑毛病
    "lint": {
        "docs": ["skills/teaching-slide-designer/SKILL.md",
                 "skills/teaching-slide-builder/SKILL.md"],
        "build": lambda d: "\n\n".join([
            "【幻灯片设计口径（改稿依据）】\n"
            + excerpt(d["skills/teaching-slide-designer/SKILL.md"],
                      "## 易错点", "## 交叉技能"),
            "【机械判据表（逐项核对）】\n"
            + excerpt(d["skills/teaching-slide-builder/SKILL.md"],
                      "**表 · 检查项与处置原则**", "### 第 5 步"),
        ]),
    },
    # 学生阅读版讲义（自学者可独立使用）—— 与「逐页讲稿讲义」是**两件不同的东西**
    "handout": {
        "docs": ["skills/teaching-file-builder/SKILL.md"],
        "build": lambda d: "\n\n".join([
            "【讲义的必备结构与原则】\n"
            + excerpt(d["skills/teaching-file-builder/SKILL.md"],
                      "## 文件类型 4：讲义", "## 文件类型 5"),
            "【通用规则】\n"
            + excerpt(d["skills/teaching-file-builder/SKILL.md"],
                      "## 通用规则", "## 文件类型 1"),
        ]),
    },
}


def skill_grounding():
    """把技能文档里的**规格**摘出来，作为提示词的规则底座。

    🔴 **分档包里的分寸**（这条是踩出来的）：
       分档包（research）**不含**教学技能 —— 那些教学任务在那个包里
       本来就没有底座，这是**分档的正常结果**，不是坏了。
       所以「技能目录整个不在」⇒ 跳过该任务并**如实报告**跳过了谁；
       但「目录在、文档摘不出来」（小节标题被改）⇒ 照旧**响亮失败**，
       那才是真的坏了 —— 静默变弱的提示词比报错更危险。
    """
    g = Grounding()
    for task, spec in GROUNDING_PLAN.items():
        docs = {}
        skipped = False
        for rel in spec["docs"]:
            if not os.path.isdir(os.path.join(ROOT, "skills", rel.split("/")[1])):
                g.missing.append((task, rel, "本包未包含该技能（分档包的正常结果）"))
                skipped = True
                break
            docs[rel] = read_skill(rel)
        if skipped:
            continue
        g[task] = spec["build"](docs)
    return g


def load_prompt(name):
    p = os.path.join(PROMPT_DIR, name + ".md")
    if not os.path.isfile(p):
        raise LLMError("找不到提示词文件：%s" % name)
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────
# 提示词组装
# ─────────────────────────────────────────────────────────────────
HARD_RULES = """你是一名中国高校青年教师，正在按学校的格式规范准备教学文件。

必须遵守（违反即交付物作废）：
1. **不得编造**任何事实性内容：课程代码、学分、教材 ISBN 与版次、页码、毕业要求指标点编号、
   期刊分区、实验数据、标准条款号。缺什么就**留空**，并写进「需人工核验清单」说明缺什么。
2. **教学文件必须对齐**：教案里每一段教学过程都要写明「设计意图」和对应的目标编号；
   目标用可观察的行为动词（能…/会…/能够分析…），不用"了解/熟悉/掌握"。
3. **评价权重合计必须 = 100%**：试卷各题分值之和必须等于总分；
   目标—题型映射表、认知层次分布、难度分布三张表的分值合计也各自等于总分。
4. **课程思政要自然融入**，不贴标签、不写空话；确实没有就写明没有。
5. **区分"设计使然"与"你编的"**：凡属你的推断要标注；凡属用户未提供但必须知道的要进清单。

只输出一个 JSON 对象，不要输出任何解释文字、不要用 Markdown 代码块包裹。
JSON 必须能被 json.loads 直接解析。"""


def build_messages(task, course, grounding=None, extra=None):
    """组装一次调用的 messages。task ∈ {outline, lesson_plan, exam_paper, slides, page, handout, lint}。

    `extra` 是本次调用的**额外上下文**（单页重生成时传：这一步的环节信息 +
    要替换的那一页 + 同环节的其他页），以便模型只重写一页而不是重写整份。
    """
    g = grounding if grounding is not None else skill_grounding()
    if task not in g:
        missing = [m for m in getattr(g, "missing", []) if m[0] == task]
        why = missing[0][2] if missing else "未找到对应技能文档"
        raise LLMError("没有 %s 的规则底座（%s）" % (task, why))
    user = (load_prompt(task)
            + "\n\n【课程信息（用户提供的原始输入）】\n"
            + json.dumps(course, ensure_ascii=False, indent=2)
            + "\n\n【规则底座（来自本仓库的技能文档，逐条遵守）】\n"
            + g[task])
    if extra:
        user += ("\n\n【本次调用的额外上下文】\n"
                 + json.dumps(extra, ensure_ascii=False, indent=2))
    return [
        {"role": "system", "content": HARD_RULES},
        {"role": "user", "content": user},
    ]


# ─────────────────────────────────────────────────────────────────
# 按用途路由模型
# ─────────────────────────────────────────────────────────────────
# 任务 → 用途。**按用途而不是按任务**选模型：
#   plan   结构化规划（大纲 / 教案 / 试卷）
#   slides 版式与字数受限的页面写作（含单页重生成）
#   handout 讲稿润色类（讲义本体是纯派生的，默认不调模型）
#   lint   判读/审校（改稿前挑毛病）
TASK_PURPOSE = {
    "outline": "plan",
    "lesson_plan": "plan",
    "exam_paper": "plan",
    "slides": "slides",
    "page": "slides",
    "handout": "handout",
    "lint": "lint",
}

PURPOSES = ("plan", "slides", "handout", "lint")


def resolve_model(task):
    """按用途取模型名；取不到返回空串（离线模式不需要它）。

    环境变量（**不写进仓库**）：
        JFA_LLM_MODEL_PLAN / JFA_LLM_MODEL_SLIDES / JFA_LLM_MODEL_HANDOUT / JFA_LLM_MODEL_LINT
        都没设时回退到 JFA_LLM_MODEL。

    🔴 为什么值得分开：大纲与课件的难度、约束完全不同
       （前者是长程结构，后者是「一页几行、字数受限」）。
       混用一个模型 ⇒ 课件页要么写太长被 L03/L04 判红，要么写得太干。
       分档之后可以用便宜模型跑 plan、贵模型跑 slides。
    """
    purpose = TASK_PURPOSE.get(task, "plan")
    for key in ("JFA_LLM_MODEL_%s" % purpose.upper(), "JFA_LLM_MODEL"):
        v = os.environ.get(key, "").strip()
        if v:
            return v
    return ""


def endpoint(task=None):
    base = os.environ.get("JFA_LLM_BASE_URL", "").strip()
    key = os.environ.get("JFA_LLM_API_KEY", "").strip()
    model = resolve_model(task) if task else os.environ.get("JFA_LLM_MODEL", "").strip()
    if not base:
        raise LLMError("未设 JFA_LLM_BASE_URL（离线模式不需要它）")
    if not model:
        raise LLMError("未设模型名（JFA_LLM_MODEL 或按用途的 "
                       "JFA_LLM_MODEL_%s）" % TASK_PURPOSE.get(task, "plan").upper())
    return base.rstrip("/"), key, model


# ─────────────────────────────────────────────────────────────────
# 调用
# ─────────────────────────────────────────────────────────────────
def call(messages, timeout=180, task=None):
    """调一次 OpenAI 兼容接口，返回文本。

    `task` 决定走哪一档模型（见 `resolve_model`）。
    """
    base, key, model = endpoint(task)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key

    def _post(with_json_mode):
        h = dict(headers)
        pl = dict(payload)
        if with_json_mode:
            pl["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            base + "/chat/completions",
            data=json.dumps(pl, ensure_ascii=False).encode("utf-8"),
            headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    try:
        data = _post(True)
    except urllib.error.HTTPError as e:
        body_txt = ""
        try:
            body_txt = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        # 有的后端不支持 response_format —— 退回普通模式（提示词已要求纯 JSON）
        if e.code in (400, 422):
            try:
                data = _post(False)
            except Exception as e2:
                raise LLMError("调用失败：HTTP %s %s" % (e.code, body_txt or e2))
        else:
            raise LLMError("调用失败：HTTP %s %s" % (e.code, body_txt))
    except urllib.error.URLError as e:
        raise LLMError("网络不可达：%s" % e.reason)

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise LLMError("返回结构不是 OpenAI 兼容格式：%s"
                       % json.dumps(data, ensure_ascii=False)[:200])


def extract_json(text):
    """从模型输出里取出 JSON 对象。

    模型常会加代码块围栏或前后废话 —— 这里做容错，但**不做"猜"**：
    取不到就报错，不给一个半成品继续往下走。
    """
    if not text:
        raise LLMError("模型返回为空")
    s = text.strip()
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", s, re.S)
    if m:
        s = m.group(1).strip()
    if s.startswith("{"):
        try:
            return json.loads(s)
        except ValueError:
            pass
    i = s.find("{")
    j = s.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(s[i:j + 1])
        except ValueError as e:
            raise LLMError("模型输出不是合法 JSON：%s" % e)
    raise LLMError("模型输出里找不到 JSON 对象：%s" % s[:200])
