请按下面的 JSON 结构输出一份**教学大纲**（本次课）。

这份大纲是**唯一事实源**：教案与课件都会由它派生出来。
所以你只写**一次**内容，派生是机械过程，不要在两处写两遍。

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
  "modules": [
    {
      "id": "M1",
      "title": "模块名",
      "minutes": 30,
      "objectives": ["O1"],
      "steps": [
        {
          "id": "S1",
          "minutes": 10,
          "teacher": "教师做什么",
          "student": "学生做什么",
          "intent": "这一步为什么这样设计",
          "objective": "O1",
          "slides": [
            {"layout": "bullets", "title": "这一页要让学生知道什么",
             "bullets": [{"text": "要点", "level": 0}],
             "notes": "讲稿：说什么、不说什么",
             "footer": "来源标注（涉及事实/数据时必填）"}
          ]
        }
      ]
    }
  ],
  "deck": {
    "meta": {"title": "课件标题", "author": "", "subject": "课题"},
    "cover": {"layout": "title", "title": "课件标题", "subtitle": "学时 · 副题", "notes": "讲稿"},
    "agenda": {"layout": "section", "title": "本节课回答几个问题", "subtitle": "问题一 · 问题二"}
  },
  "key_points": ["…"],
  "difficulties": ["…"],
  "prior_knowledge": ["…"],
  "barriers": ["学生可能卡在哪里"],
  "methods": ["…"],
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

- **时间三层闭合**：`meta.minutes` = 各 `modules[].minutes` 之和 = 各 `steps[].minutes` 之和。
- `objectives` 3–5 条；每条 `text` 必须用可观察动词（能/会/能够分析…），
  **不用**"了解/熟悉/掌握"；每条都要有 `course_objective`。
- 每个 `step` 的 `objective` 必须是 `objectives` 里已存在的编号；
  每个 `modules[].objectives` 同理。
- 每个 `step` 都要有 `teacher`、`student`、`intent`，`intent` 不能空
  （只写时间不写意图的教案是流水账）。
- **每个 `step` 要么有 `slides`，要么写 `no_slide_reason`**（说明这一环节为什么不投影）。
  两种成因要分清：「本环节就是学生活动」是设计使然，「漏做课件」是缺陷。
- `slides[].layout` 取值：`title` / `section` / `bullets` / `two-column` /
  `image-focus` / `quote`。**封面只能用 `title` 且有且只有一个**，章节过渡用 `section`。
- `layout` 为 `bullets` / `two-column` / `image-focus` 的页面**必须有 `notes` 讲稿**。
- 一页要点 ≤ 6 条、单条 ≤ 30 字；页面标题 ≤ 20 字且是一句断言（不写"小结/概述"这类分类词）。
- 页面里不要出现"如上图/如下图"这类线性指代（并置版面里它不成立）。
- `questions` 至少 3 个，每个都要有 `expected`。
- `homework` 至少 1 条。
- `course_code` / `teacher` / `date` / `textbook` 用户没给就**留空**，
  并在 `needs_manual_check` 里逐项说明缺什么（每项写成 `{"field": "…", "desc": "…"}`）。
- **不要**在正文里出现"待补充/待定/TBD/XXX"这类占位符。
