请按下面的 JSON 结构输出一份**教案**（一节课）。

```json
{
  "meta": {
    "course": "课程名称",
    "course_code": "",
    "college": "",
    "semester": "",
    "teacher": "",
    "major": "",
    "nature": "必修",
    "prerequisites": "",
    "session_no": 1,
    "topic": "本次课题",
    "hours": 2,
    "minutes": 90,
    "date": "",
    "textbook": ""
  },
  "objectives": [
    {"id": "O1", "text": "能解释…", "evidence": "用什么证据检验达成", "course_objective": "CO-3"}
  ],
  "key_points": ["…"],
  "difficulties": ["…"],
  "prior_knowledge": ["…"],
  "barriers": ["学生可能卡在哪里"],
  "methods": ["…"],
  "process": [
    {"minutes": 10, "teacher": "教师做什么", "student": "学生做什么",
     "intent": "这一步为什么这样设计", "objective": "O1"}
  ],
  "board_design": {"main": "主板书结构", "aux": "副板书"},
  "questions": [
    {"q": "预设问题", "expected": "预期回答", "followup": "追问路径"}
  ],
  "ideology_points": [{"point": "思政融入点", "carrier": "承载它的教学内容", "how": "自然融入的方式"}],
  "homework": [{"task": "作业内容", "purpose": "检验哪个目标"}],
  "reflection": ["课后反思要点"],
  "needs_manual_check": [
    {"field": "course_code", "desc": "课程代码：用户未提供，需向教务核对"}
  ]
}
```

硬性要求（自检会逐条判，不满足即报错）：

- `process` 各段 `minutes` 之和**必须等于** `meta.minutes`。
- `objectives` 3–5 条；每条 `text` 必须用可观察动词（能/会/能够分析…），
  **不用**"了解/熟悉/掌握"；每条都要有 `course_objective`。
- `process` 每一段都要有 `teacher`、`student`、`intent`、`objective` 四个字段，
  `intent` 不能空（只写时间不写意图的教案是流水账）。
- `questions` 至少 3 个，每个都要有 `expected`。
- `homework` 至少 1 条。
- `course_code` / `teacher` / `date` / `textbook` 用户没给就**留空**，
  并在 `needs_manual_check` 里逐项说明缺什么（每项写成 `{"field": "…", "desc": "…"}`）。
- **不要**在正文里出现"待补充/待定/TBD/XXX"这类占位符。
