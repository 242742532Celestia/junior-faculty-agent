# 高校教师能力矩阵（巡检基线）

> 这是**巡检基线**。每季度巡检后更新。
> 「覆盖状态」记录某能力格是否已有技能接住；`—` 表示缺口，是巡检时优先补的候选。
> 维护人：junior-faculty-agent ｜ 最近更新：2026-10-26（第 8 版：**公式校正线回仓** —— 新增原创技能 `formula-typesetting`（伪公式检测 / LaTeX 规范化 / OMML 注入 / 验收闸），同挂 B7（教学侧：课件、讲义、教案的公式）与 E4（科研侧：论文公式）。它不是"再加一个能力"，而是**给所有生成物接上一道必经工序**：课件 / 讲义 / 教案 / 试卷 / 论文的公式统一在**源层**规范化一次，各载体只负责渲染自己那一份（Markdown 走 typst、PPTX 注入 OMML）。**覆盖计数不变（34/41）**，B7 仍为「部分覆盖」。第 7 版：**课件线拆分** —— `teaching-slide-designer` 拆成**设计**（写什么：认知任务 / 断言式标题 / 讲稿分离 / 阈值）与**生成**（怎么生成：PPTX 生成器 / 版式几何 / 溢出判据 / 实开验收）两个技能，后者名为 `teaching-slide-builder`，三支脚本随之迁入其 `scripts/`；两技能同挂 B7 与 E7。**覆盖计数不变（34/41）**，B7 仍为「部分覆盖」。第 6 版：**分档出包** —— 本矩阵同时成为「分档出包」的推导源：6 个此前未入任何格的新技能补进 A1/A2/B7/D5/F2，`teaching-slide-designer` 另挂 B7（教学侧，它本来就挂在 E7）；档位数据 `references/profiles.json`，推导器 `scripts/profile_map.py`，恒等式 `teaching ∪ research = full − {skill-scan}` 由守卫机械校验。**覆盖计数不变（34/41）。** 第 5 版：幻灯片线自研回仓 —— 新增 `teaching-slide-designer` / `paper-to-talk-designer` / `openmaic-courseware` / `teacher-style-profile` / `personal-course-pattern-builder` 共 5 个技能；E7 去掉 `◐nature-paper2ppt`；外部技能表移除 `pptx` 与 `nature-paper2ppt`）

## 一、能力格清单

格式：`能力格 | 判定标准（怎样算"高校教师该掌握"） | 覆盖技能 | 覆盖状态`

**覆盖技能列的标注含义**（决定这一格在**克隆本仓库之后**还算不算覆盖）：

| 标记 | 含义 | 随本仓库分发 |
|---|---|---|
| `●` | **已装**：随本仓库分发，克隆即可用 | ✅ |
| `○` | **候选未装**：上游仓库存在但未安装，是巡检优先补的对象 | ❌ |
| `◐` | **本机其他技能**：全局技能库 / 其他 Agent / 插件提供，不随本仓库分发 | ❌ |

> ⚠️ **没有 `●` 的格不是"已覆盖"。** 一格若只有 `○`/`◐`，克隆本仓库后该格会退化为缺口。
> 本文件由 `scripts/verify_repo.py` 机械校验：任何被引用但不存在的技能名都会报错。
>
> 📌 **`◐` 与外部技能登记表**：`◐` 不是自由文本 —— 每个 `◐` 技能都必须登记在
> `references/external-skills.json`（外部技能登记表），由 `scripts/verify_repo.py`
> 机械校验。矩阵里出现未登记的 `◐` = 编造依赖，守卫会报错。
>
> 📌 **论文线已回仓（2026-10-22）**：E2 文献调研、E4 论文写作与投稿、
> E5 同行评议与回应、E9 教学研究论文四格由**本仓库自带技能**承担
> （9 个 K-Dense MIT 论文类技能 + 3 个本项目原创：`citation-audit` /
> `assertive-writing` / `submission-readiness`），故标 `●`「已覆盖」——
> 克隆本仓库即可用，**不依赖任何本机全局技能**。
> 用户本机若已装 `academic-deep-writer`（ADW），仍可作为**可选增强**搭配使用，
> 但矩阵与守卫都不依赖它。
>
> 📌 **幻灯片线已自研并回仓（2026-10-22 第 5 版）**：E7 原先依赖本机全局技能
> `nature-paper2ppt`（◐，**不随本仓库分发**）与运行时内置的 `pptx` 技能。
> 现已由本仓库自研的 `teaching-slide-designer`（课件**设计**：认知任务、断言式标题、
> 讲稿分离、来源标注）与 `teaching-slide-builder`（课件**生成**：含**纯标准库 PPTX 生成器**
> `build_pptx.py`、**版式原型表** `slide_layouts.py` 与**教学规范审查器** `slide_spec_lint.py`）与
> `paper-to-talk-designer`（论文→汇报叙事）承担，**克隆即可用**。
> 这与论文线回仓是同一个理由：**能力必须随交付物走** ——
> 挂在不随包分发的外部技能上，克隆方就没人接手。
> 守卫会机械拦截 `pptx` / `nature-paper2ppt` 重新进入外部技能表或矩阵。
> **覆盖计数不变**（E7 本来就是「已覆盖」，只是把 ◐ 换成 ●）。
>
> 📌 **本矩阵同时是「分档出包」的推导源（2026-10-22 第 6 版）**：
> 分档包（`teaching` / `research`）里装哪些技能，**不是手工枚举**的，
> 而是由本表的**能力域**机械推导：
>
> | 档位 | 能力域 | 技能数 |
> |---|---|---|
> | `teaching` | A 教学准备 / B 教学实施 / C 考核评价 / D 学生支持 / F 教研发展 | 63 |
> | `research` | E 科研全流程 | 25 |
> | `full` | 全部 + 仓库机制类 | 88 |
>
> 恒等式：`teaching ∪ research == full − {skill-scan}`
> （`skill-scan` 是**仓库自身的季度巡检机制**，不是师生素能力，因此只在完整包里）。
>
> 🔴 **每个已装技能都必须在本表某一格里有归属** —— 没归属的技能会在两个分档里
> **双双消失**，而 `full` 档里还在。守卫 `scripts/verify_repo.py` 会红，
> 出包器 `scripts/package_release.py` 会**直接中止出包**。
> 档位数据：`references/profiles.json`；推导器：`scripts/profile_map.py`
> （出包器与守卫共用同一份实现 —— 两套推导必然漂移，漂移是静默的）。
>
> 📌 **OpenMAIC 方法论内核适配（2026-10-22 第 4 版）**：新增 3 个技能
> （`authentic-context-course-designer` / `feynman-diagnostic-cycle` /
> `vocational-task-course`），并给 8 个既有技能增补了方法论内核对应的章节
> （UbD 三阶段与 GRASPS/WHERETO、概念脊柱与升阶操作符与假螺旋检查、
> 诊断—支持—撤架—复核闭环、澄清轮次与确认门、核心素养映射）。
> 补进的都是**已覆盖格**里的更细颗粒能力，**覆盖计数不变**（34/41）。
> 归属与署名见 `THIRD-PARTY-NOTICES.md` §3。

### A. 教学准备与设计

| 能力格 | 判定标准 | 覆盖技能 | 状态 |
|---|---|---|---|
| A1 课程目标与毕业要求支撑 | 能把课程目标映射到毕业要求指标点 | ●backwards-design-unit-planner, ●curriculum-crosswalk, ●learning-target-authoring-guide, ●competency-unpacker, ●coverage-audit | 已覆盖 |
| A2 教学大纲与进度编排 | 能产出含学时分配的教学大纲 | ●scope-and-sequence-designer, **●teaching-file-builder**, ●authentic-context-course-designer, ●vocational-task-course, ●openmaic-courseware | 已覆盖 |
| A3 学情分析与分层教学 | 能据学生前测/作业数据设计分层任务 | ●differentiation-adapter, ●gap-analysis-from-student-work | 已覆盖 |
| A4 课程思政融入 | 能在专业内容中自然融入价值引领 | **●he-context-adapter** + **●teaching-file-builder**（文件类型 6）, ●authentic-context-course-designer | 已覆盖 |
| A5 教材与参考书遴选 | 能基于课程目标选配套教材并给真实书目 | ●teaching-file-builder（ISBN 不得编造规则） | 部分覆盖（无检索工具，需人工/外部补充） |
| A6 教学工作量与课时折算 | 能算教学工作量、学分折算 | — | **缺口** |

### B. 教学实施

| 能力格 | 判定标准 | 覆盖技能 | 状态 |
|---|---|---|---|
| B1 课时/单元设计（逆向设计） | 产出目标-证据-活动三段对齐的教学设计 | ●backwards-design-unit-planner, ●explicit-instruction-sequence-builder, ●vocational-task-course | 已覆盖 |
| B2 课堂导入与先行组织者 | 产出激活先备知识的开场设计 | ●lesson-opening-designer, ●think-aloud-script-generator | 已覆盖 |
| B3 概念讲授与例题序列 | 产出完整例题→渐隐→变式的序列 | ●practice-problem-sequence-designer, ●worked-example-fading-designer, ○digital-worked-example-sequence | 已覆盖 |
| B4 课堂提问与讨论组织 | 产出提问序列、讨论协议、苏格拉底式追问 | ●hinge-question-designer, ●socratic-questioning-sequence-generator, ●discussion-protocol-selector, ●dialogic-teaching-move-generator | 已覆盖 |
| B5 理解检测 | 为每个教学环节配理解检查技术 | ●checking-for-understanding-protocol-designer, ●formative-assessment-technique-selector, ●feynman-diagnostic-cycle | 已覆盖 |
| B6 认知负荷与记忆设计 | 能做认知负荷分析、间隔与提取练习安排 | ●cognitive-load-analyser, ●dual-coding-designer, ●retrieval-practice-generator, ●spaced-practice-scheduler | 已覆盖 |
| B7 板书与可视化 | 产出板书结构/示意图/教学幻灯片 | ●markdown-mermaid-writing, ●scientific-schematics, ●teaching-slide-designer, ●teaching-slide-builder, ●formula-typesetting | 部分覆盖（示意图与幻灯片已覆盖；板书结构无已装技能） |

### C. 考核与评价

| 能力格 | 判定标准 | 覆盖技能 | 状态 |
|---|---|---|---|
| C1 评分量规 | 产出含描述性等级的 rubric | ●criterion-referenced-rubric-generator, ●single-point-rubric-designer, ●coherent-rubric-logic-builder | 已覆盖 |
| C2 考核效度审查 | 能审查考核是否真的测到了目标 | ●assessment-validity-checker, ●assessment-design-orchestrator | 已覆盖 |
| C3 学习进阶 | 产出从初学到精通的进阶路径 | ●learning-progression-builder, ●formative-assessment-loop-designer, ●scope-and-sequence-designer（概念脊柱与升阶操作符） | 已覆盖 |
| C4 批判性思维与高阶任务 | 产出学科专属的批判性思维任务 | ●discipline-specific-critical-thinking-task-designer, ○critical-thinking-task-designer, ●argument-structure-scaffold-generator, ●feynman-diagnostic-cycle | 已覆盖 |
| C5 作业与项目任务设计 | 产出大作业/项目任务书 | ●project-brief-designer | 已覆盖 |
| C6 试题命题与试卷结构 | 产出试卷结构、题型配比、难度分布、答案与评分细则 | **●exam-question-bank** | 已覆盖 |
| C7 教学数据/成绩分析 | 能分析成绩分布并给教学改进建议 | ●learning-analytics-interpretation-guide | 部分覆盖 |

### D. 学生支持与素养

| 能力格 | 判定标准 | 覆盖技能 | 状态 |
|---|---|---|---|
| D1 自我调节支架 | 产出学习计划、元认知提示 | ●self-regulation-scaffold-generator, ○metacognitive-prompt-library | 已覆盖 |
| D2 错因分析与个别辅导 | 能从学生错误反推认知障碍 | ●error-analysis-protocol, ○stuck-and-error-diagnosis-coach | 已覆盖 |
| D3 学习策略指导 | 按题型/科目给策略 | ●study-strategy-selector | 已覆盖 |
| D4 反馈质量 | 产出高质量反馈句式 | ●feedback-quality-analyser | 已覆盖 |
| D5 迁移与自我解释 | 设计促进迁移的衔接任务（含先行失败—后教学协议） | ●transfer-bridge, ●teach-back-evaluator, ○self-explanation-prompt-designer, ●feynman-diagnostic-cycle, ●productive-failure-protocol | 已覆盖 |
| D6 学术诚信与信息素养 | 设计引用核查与 AI 使用规范教学 | ●source-credibility-evaluation-protocol, ○ai-hallucination-fact-check-protocol, ○ai-output-critical-audit-designer | 部分覆盖（引用核查已覆盖；AI 使用规范教学无已装技能） |

### E. 科研全流程

| 能力格 | 判定标准 | 覆盖技能 | 状态 |
|---|---|---|---|
| E1 选题与假设生成 | 产出有证据边界的研究问题与竞争性解释 | ●hypothesis-generation, ●scientific-brainstorming, ●scientific-critical-thinking | 已覆盖 |
| E2 文献调研与综述 | 产出系统/叙述性综述 | ●literature-review, ●research-lookup, ●paper-lookup, ●citation-management, ●citation-audit | 已覆盖 |
| E3 实验设计与统计 | 产出实验设计、功效分析、统计方法选择 | ●experimental-design, ●statistical-analysis, ◐empirical-lint（功效/样本量/MDE）, ●uncertainty-and-units | 已覆盖 |
| E4 论文写作与投稿 | 产出 IMRaD 稿件与投稿件 | ●scientific-writing, ●venue-templates, ●submission-readiness, ●formula-typesetting | 已覆盖 |
| E5 同行评议与回应 | 产出审稿意见与逐点回复 | ●peer-review, ●scholar-evaluation, ●assertive-writing, ◐nature-response | 已覆盖 |
| E6 图表与可视化 | 产出投稿级图表 | ●scientific-visualization, ◐nature-figure | 已覆盖 |
| E7 学术汇报 | 产出会议 slides / 海报 | ●latex-posters, ●scientific-slides, ●paper-to-talk-designer, ●teaching-slide-designer, ●teaching-slide-builder | 已覆盖 |
| E8 **项目申报书** | 产出基金/项目申报书全文本 | **●grant-proposal-writer**（中文基金专用）, ●citation-audit（引用核验）, ◐nature-proposal-writer, ◐researchwrite | 已覆盖 |
| E9 教学研究论文 | 把教学改进写成可投稿论文 | ●scientific-writing（正文）, ●research-grants, ●statistical-analysis, 教研类技能（教学改进→可投稿设计） | 已覆盖 |
| E10 学术简历与个人主页 | 产出 CV / 主页文案 | — | **缺口** |

### F. 教研与专业发展

| 能力格 | 判定标准 | 覆盖技能 | 状态 |
|---|---|---|---|
| F1 课堂观察与课例研究 | 产出课堂观察协议与课例研究流程 | ●lesson-observation-protocol-designer, ●lesson-study-cycle-designer | 已覆盖 |
| F2 反思性实践 | 产出反思提示、教师探究循环与个人工作法/讲法迁移 | ●reflective-practice-prompt-generator, ●teacher-inquiry-cycle-designer, ●teacher-style-profile, ●personal-course-pattern-builder | 已覆盖 |
| F3 学科教学知识 | 产出 PCK 层面的教学决策 | ●pedagogical-content-knowledge-developer, ●technological-pedagogical-content-knowledge-developer | 已覆盖 |
| F4 通用学习设计 | 产出多通路（UDL）改造方案 | ●udl-options-designer, ●udl-lesson-auditor | 已覆盖 |
| F5 AI 素养教学 | 产出 AI 素养课程/模块 | ○ai-expertise-interrogation-designer, ○ai-hallucination-fact-check-protocol, ○ai-learning-boundary-mapper, ○ai-output-critical-audit-designer, ○ai-socratic-dialogue-designer, ○disciplinary-ai-literacy-sequence-designer, ○prompt-literacy-sequence-designer | **缺口**（上游 7 个候选技能，**均未装**） |

## 二、巡检判据（**决定一个 GitHub 技能要不要学**）

一个候选技能符合下列**任一条**，即为「高校教师应该掌握」，学习入库：

1. 它直接产出上表 A–F 中某个能力格所需的**交付物**（教案、大纲、量规、试卷、申报书、图表…）。
2. 它提供**可复用的方法框架**（逆向设计、认知负荷、效度分析、PRISMA、统计功效…），
   且该框架在高校教学或科研场景有明确对应。
3. 它解决高校教师**高频真实任务**中的任一类：备课、命题、批改反馈、文献调研、
   论文写作、投稿回复、申报书、学术汇报、教研反思。

**明确排除**（不属于高校教师能力范畴）：
- 纯软件开发、DevOps、数据库、前端框架类技能
- SEO / 营销 / 增长黑客 / 社交媒体运营
- 通用商业分析与财务（除非明确用于科研经费管理）
- 与教学科研无关的通用 LLM 工程（提示词工程自动化、agent 编排框架、模型部署）
- 军事/医疗/法律等**专业执业**技能（除非用户明确是该学科教师）

**边界情况处理**：技能名或描述里出现 "research" "paper" "teaching" 不等于符合。
必须打开 SKILL.md 看它**具体做什么任务**，再看这个任务是否在高校教师职责内。

## 三、扫描源（巡检时按此列表检索）

| 源 | 检索方式 | 备注 |
|---|---|---|
| GitHub 仓库搜索 | `https://api.github.com/search/repositories?q=<关键词>+skills&sort=updated` | 关键词按能力矩阵缺口构造 |
| GitHub 代码搜索 | `https://api.github.com/search/code?q=filename:SKILL.md+<关键词>` | **需认证**，无 token 时跳过 |
| K-Dense-AI/scientific-agent-skills | 定期查 `git ls-tree` 是否有新 skill 目录 | 科研侧主源，已装 20 个（MIT） |
| GarethManning/education-agent-skills | 同上 | 教学侧主源，已装 50 个（**本项目独立创作**，主题与命名参考该上游） |
| awesome 清单 | ComposioHQ/awesome-claude-skills、VoltAgent/awesome-agent-skills | 用于发现新仓库 |
| npx skills find | `npx -y skills find <关键词>` | 交互式，需谨慎 |
| 用户指定仓库 | 用户在对话中给出 | 直接检视 |

## 四、已排除技能记录

见 `references/rejected-skills.md`。**每季度巡检先读它**，避免重复评估。

## 五、巡检产出物

- `reports/skill-scan-<YYYY>-Q<N>.md` —— 本季度巡检报告
- 更新本文件的「覆盖状态」列与「最近更新」
- 新技能写入 `skills/`，并按教学/科研分流做语境适配
- 被拒技能追加进 `references/rejected-skills.md`
