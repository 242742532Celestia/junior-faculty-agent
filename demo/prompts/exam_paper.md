请按下面的 JSON 结构输出一份**试卷**（A 卷）与一份备用卷（B 卷）。

```json
{
  "meta": {
    "course": "课程名称",
    "course_code": "",
    "date": "",
    "paper": "A",
    "total_score": 100,
    "duration_minutes": 120
  },
  "design": {
    "objective_type_matrix": [
      {"objective": "CO-1", "type": "单项选择", "count": 4, "score": 20}
    ],
    "cognitive_distribution": [
      {"level": "记忆", "score": 20}
    ],
    "difficulty_distribution": [
      {"level": "易", "score": 20}
    ],
    "design_note": "命题思路：为什么这样配比"
  },
  "questions": [
    {"no": 1, "type": "单项选择", "score": 5,
     "objective": "CO-1", "cognitive": "记忆", "difficulty": "易", "minutes": 2,
     "stem": "题干",
     "options": ["A …", "B …", "C …", "D …"],
     "answer": "B",
     "scoring": "每选对得 5 分，选错或多选不得分"}
  ],
  "backup": {
    "paper": "B",
    "note": "与 A 卷同结构、难度相当，题目不同",
    "questions": []
  },
  "needs_manual_check": [
    {"field": "course_code", "desc": "课程代码：用户未提供，需向教务核对"}
  ]
}
```

硬性要求（自检会逐条判，不满足即报错）：

- `questions` 各题 `score` 之和**必须等于** `meta.total_score`。
- `design` 里三张表的 `score` 各自合计**也必须等于** `meta.total_score`：
  `objective_type_matrix`（目标—题型映射）、`cognitive_distribution`（认知层次分布）、
  `difficulty_distribution`（难度分布）。
- 每道题都要有：`stem`、`answer`、`scoring`（评分细则）、`objective`（绑定考核目标）、
  `cognitive`（认知层次）、`difficulty`（难度）、`minutes`（建议用时）。
- 题号 `no` 从 1 开始连续编号。
- `backup.questions` 要有与 A 卷**同结构、同分值分配**的一套题（防泄题）。
- `course_code` / `date` 用户没给就留空，并写进 `needs_manual_check`。
- 认知层次用这四档：记忆 / 理解 / 应用 / 分析。难度用：易 / 中 / 难。
- **不要**在正文里出现"待补充/待定/TBD/XXX"这类占位符。
