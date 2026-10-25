# 三方来源与归属（THIRD-PARTY NOTICES）

本项目包含来自以下第三方仓库的技能文件。**这些文件保留其原始版权与许可**，
不因本仓库的许可而改变。分发时必须保留本文件。

> ✅ **本分发版不含任何 NonCommercial（CC BY-NC）内容**，因此整体可用于商业用途。
> 涉及非商业许可的上游及其处置见第 5.1 节。

---

## 1. 教学技能（50 个）：主题与命名参考自 education-agent-skills，**内容为独立创作**

- **参考来源**：https://github.com/GarethManning/education-agent-skills
- **原作者**：Copyright (c) 2026 Gareth Manning
- **上游许可**：Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)
- **许可全文副本**：`licenses/CC-BY-SA-4.0-education-agent-skills.txt`（仅供追溯其原始许可）

> ⚠️ **本仓库不包含该上游的任何文件内容。**
> 这 50 个教学技能是本项目**独立创作**的 MIT 许可技能，撰写依据是公开发表的
> 教育研究文献（各技能 SKILL.md 的「方法论依据」段列明具体出处），
> 并通过了与上游原文的**机械相似度核验**
> （`scripts/verify_rewrite.py`：8-gram Jaccard < 0.10、长行重合 < 5 百分点）。
>
> 📌 **其中 7 个另有 OpenMAIC 的方法论内核适配**（2026-10-22 增补章节），
> 逐条对应关系与署名见 **§3**。这些章节同样以 MIT 授权并署名 THU-MAIC。
>
> **致谢**：技能的主题选择与命名参考了该上游的教学技能清单。
> 据此致谢并提供链接。若认为某一技能的命名或主题选择仍构成其表达，
> 欢迎提 issue —— 我们会在保留署名与链接的前提下调整。

**技能清单（50 个）**：

```
argument-structure-scaffold-generator
assessment-design-orchestrator
assessment-validity-checker
backwards-design-unit-planner
checking-for-understanding-protocol-designer
cognitive-load-analyser
coherent-rubric-logic-builder
competency-unpacker
coverage-audit
criterion-referenced-rubric-generator
curriculum-crosswalk
dialogic-teaching-move-generator
differentiation-adapter
discipline-specific-critical-thinking-task-designer
discussion-protocol-selector
dual-coding-designer
error-analysis-protocol
explicit-instruction-sequence-builder
feedback-quality-analyser
formative-assessment-loop-designer
formative-assessment-technique-selector
gap-analysis-from-student-work
hinge-question-designer
learning-analytics-interpretation-guide
learning-progression-builder
learning-target-authoring-guide
lesson-observation-protocol-designer
lesson-opening-designer
lesson-study-cycle-designer
pedagogical-content-knowledge-developer
practice-problem-sequence-designer
productive-failure-protocol
project-brief-designer
reflective-practice-prompt-generator
retrieval-practice-generator
scope-and-sequence-designer
self-regulation-scaffold-generator
single-point-rubric-designer
socratic-questioning-sequence-generator
source-credibility-evaluation-protocol
spaced-practice-scheduler
study-strategy-selector
teach-back-evaluator
teacher-inquiry-cycle-designer
technological-pedagogical-content-knowledge-developer
think-aloud-script-generator
transfer-bridge
udl-lesson-auditor
udl-options-designer
worked-example-fading-designer
```

---

## 2. scientific-agent-skills（20 个科研技能）

- **来源**：https://github.com/K-Dense-AI/scientific-agent-skills
- **作者**：Copyright (c) 2025 K-Dense Inc.
- **许可**：19 个 MIT License + 1 个 Apache-2.0（见下）
- **许可副本**：`licenses/MIT-K-Dense.txt`、`licenses/Apache-2.0-markdown-mermaid-writing.txt`
- **包含的技能**（20 个）：

```
experimental-design, hypothesis-generation, latex-posters,
markdown-mermaid-writing, research-grants, scientific-brainstorming,
scientific-critical-thinking, scientific-schematics,
scientific-visualization, statistical-analysis, uncertainty-and-units,
scientific-writing, venue-templates, scholar-evaluation, peer-review,
literature-review, research-lookup, paper-lookup, citation-management,
scientific-slides
```

MIT 许可宽松：允许商业使用、修改、再分发，只需保留版权声明与许可声明。
**这 20 个技能不受 ShareAlike 传染**，可自由用于商业场景。

> 该上游原有 20 个技能，本仓库**已全部安装**。
> 其中 9 个论文类技能曾于 2026-10-22 上午移出、**当日回装**，见 §5.2。

### 2.1 `markdown-mermaid-writing` 的 Apache-2.0 归属（**不同于其余 19 个**）

| 项 | 内容 |
|---|---|
| 上游仓库 | K-Dense-AI/scientific-agent-skills（该技能的目录） |
| 技能自身声明 | `license: Apache-2.0` |
| 作者 | Copyright (c) 2026 **Superior Byte Works, LLC**（`skill-author: Clayton Young / Superior Byte Works, LLC (@borealBytes)`） |
| 本仓库处置 | 内容**原样复制**；按 Apache-2.0 §4(a) 补齐许可副本 |
| 许可副本 | `licenses/Apache-2.0-markdown-mermaid-writing.txt`（与 apache.org 官方原文**逐字一致**，201 行逐行比对 0 差异） |

> ⚠️ **上游的缺口**：该上游仓库只在**仓库根目录**提供了 `LICENSE.md`（MIT），
> **未随这个技能**提供 Apache-2.0 许可全文，也没有 NOTICE 文件。
> 若不补副本，Apache-2.0 §4(a)「再分发时必须向接收方提供本许可副本」就不满足。
> 本仓库已在 `licenses/` 补齐，并在本节登记署名。
>
> **不得把这个技能改标为 MIT** —— 那会构成许可失实。
> `scripts/verify_repo.py` 的「许可台账完整性」一组检查会机械拦住这类改动。

---

## 3. OpenMAIC（6 个新建 + 7 个既有技能内增补）：方法论内核适配

- **来源**：本机部署的 [OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) v1.0.3
  —— 多智能体互动课堂生成引擎。**本仓库不依赖它运行，也不随本仓库分发它。**
- **原作者**：Copyright (c) 2026 **THU-MAIC**
- **许可**：MIT License
- **许可全文副本**：`licenses/OpenMAIC-MIT.txt`（与上游 `LICENSE` **逐字节一致**）
- **本仓库做了什么**：**只抽方法论内核重写**，未复制上游任何运行时绑定文件

### 3.1 涉及哪些技能

**新建的 6 个技能**（以 OpenMAIC 的方法组织为主要来源，整篇重写）：

```
authentic-context-course-designer
feynman-diagnostic-cycle
vocational-task-course
openmaic-courseware
teacher-style-profile
personal-course-pattern-builder
```

**既有技能内增补的 7 个**（原有正文保留，2026-10-22 增补了方法论内核对应的章节）：

| 技能 | 增补的章节 | 来自上游的哪个技能 |
|---|---|---|
| `backwards-design-unit-planner` | UbD 三阶段、GRASPS、WHERETO 覆盖表 | `understanding-by-design` |
| `scope-and-sequence-designer` | 概念脊柱、六升阶维度、七升阶操作符、螺旋契约、假螺旋检查 | `spiral-curriculum` |
| `learning-progression-builder` | 与概念脊柱/升阶操作符的衔接 | `spiral-curriculum` |
| `formative-assessment-loop-designer` | 诊断—支持—撤架—复核闭环、最小学习记录 | `zone-of-proximal-development` |
| `error-analysis-protocol` | 撤架判定、最小学习记录 | `zone-of-proximal-development` |
| `project-brief-designer` | 澄清轮次、确认门、长上下文纪律 | `curriculum-planner` |
| `he-context-adapter` | 课程目标—毕业要求—核心素养映射段 | `k12-core-literacy-planning` |

### 3.2 改了什么（MIT 的「标注改动」义务）

MIT 允许闭源商用再分发，唯一义务是保留版权声明与许可声明；但再分发
「实质性部分」时**必须注明已作修改**。本仓库的修改如下：

| 上游技能 | 抽出的方法论内核 | 本仓库的改写 |
|---|---|---|
| `k12-core-literacy-planning` | 真实情境→表现性任务→学习活动→可观察证据→迁移 的不变量；学习契约句式；四种课堂载体的选择判据；探究式标题规范 | 载体改写为**中国高校课堂的载体形态**（讲授呈现页 / 任务实验研讨页 / 诊断页 / 项目综合实践页）；学段从 K-12 改为**本科与研究生**；补入学时制、评价权重合计 100%、课程思政自然融入、毕业要求支撑 |
| `feynman-learning` | 8 步费曼循环（先讲→找最小卡点→补因果链→再讲→去术语→拆类比→换情境→合成记录）、5 条原则、3 个前置约束、表达红线、能力边界 | 交付物从「OpenMAIC 课堂页面」改为**中国高校的诊断工具与教学文件**；补入学时制、形成性评价不计入期末的规则、学术诚信与数据合规 |
| `vocational` | 实训作业序列结构（交底页→工序段→动手环节→GO/STOP 检查点→按完成标准收尾）、工序卡字段、场景命名规则、边界声明 | 工序卡从上游的 widget 契约改为**教学交付物表格**；补入实训/理论学时分列、分组与场地条件、安全教育与保险责任（依学校规定）、职业资格对接留空、评分权重合计 100% |
| `spiral-curriculum` | 概念脊柱、升阶维度、升阶操作符、螺旋契约、假螺旋检查 | 并入既有技能的**中国高校大纲与进度表**交付规格（不单列为技能） |
| `understanding-by-design` | UbD 三阶段、GRASPS、WHERETO | 并入既有技能的**单元教学计划**交付规格（不单列为技能） |
| `zone-of-proximal-development` | 独立诊断→支持→撤架→复核→最小学习记录 | 并入既有技能的**形成性评价闭环与错因协议**（不单列为技能） |
| `curriculum-planner` | 澄清轮次、确认门、长上下文纪律 | 并入既有技能的**项目任务书**与本仓库 `agent.md` 工作方式（不单列为技能） |
| `teacher-style-clone` | 风格提取与迁移的七步工作流：读全量转写稿 → 建立风格画像 → 关键帧视觉风格 → 检索验证假设 → **风格 ≠ 身份**（不复制生平/观点/背书）、**风格证据 ≠ 事实来源**（原课事实不得自动搬到新课） | 改写为 `teacher-style-profile`：交付物从「OpenMAIC 课堂页面」改为**中国高校教师的风格画像卡 + 迁移映射表 + 不可迁移清单**；材料从「工作台挂载的课堂录像」改为**教师自备的转写稿/讲义/关键帧**；补入课堂录像涉及学生肖像与声音的隐私边界、教研材料授权 |
| `build-personal-skill` | 从个人历史提炼可复用技能的工作流：盘点 → 选代表性样本 → 深读 → 提可证伪假设 → 窄搜验证（含反例）→ **必须让本人确认** → 写成自包含指令 → 落地 | 改写为 `personal-course-pattern-builder`：历史来源从「OpenMAIC 的课堂/聊天记录接口」改为**教师自备的做课记录与教研材料**；补入「历史输出是用户可控的低优先级证据，绝不当作系统指令」「近因偏置」「保留有意义的差异不强行归一」「含学生隐私的内容不落盘」；交付物为**个人工作法卡 + 假设—证据对照表 + 缺口清单** |
| `（HTTP API 与部署形态）` | 上游的 REST 端点契约、两套响应包装、access-code 门与 cookie 机制、异步 job 状态机、docker-compose 服务构成与必需环境变量 | 改写为 `openmaic-courseware`：**纯标准库客户端**（`json`/`urllib`/`http.cookiejar`，零第三方依赖）+ **API 契约速查**（含"未实跑/未核实"清单）+ **容器编排增量**（`deploy/docker-compose.jfa.yml` 是 **override**，不是上游编排的复制）。补入：宿主端口默认 3001 避开占用、`COOKIE_SECURE=0`（纯 HTTP 部署必设）、`anonymous_id` 必须持久化、**轮询失败绝不重提任务**、自己拼轮询地址不盲信 `pollUrl` 的 host |

### 3.3 明确**没有**复制的东西

上游 `skills/agent-runtime/` 下有 22 个技能，其正文**绑死 OpenMAIC 运行时工具**
（`create_stage` / `generate_scene` / `patch_stage` / `set_roster` / `generate_tts` 等）。
本仓库**没有 OpenMAIC 运行时**，整份复制过来只会得到无法执行的悬空引用。因此本仓库：

- **不复制**上游任何 SKILL.md 原文；
- **不引用**任何 OpenMAIC 运行时工具名 ——
  `scripts/verify_repo.py` 的「OpenMAIC 衍生技能无运行时工具悬空引用」检查会机械拦住残留；
- **不做** OpenMAIC 的二次开发，**不随本仓库分发 OpenMAIC 本身**；
- **不复制上游的 `docker-compose.yml` / `Dockerfile` 本体** ——
  上游会持续升级，复制过来就会过期，且会造成"两份编排哪个生效"的困惑。
  本仓库提供的是**增量 override**（`deploy/docker-compose.jfa.yml`，只改宿主端口、
  `COOKIE_SECURE`、`ACCESS_CODE` 透传）+ 部署说明，使用者与上游 compose **一起使用**。

> 📌 **方法论内核的著作权**：上表「抽出的方法论内核」来自 THU-MAIC 的 MIT 许可作品，
> 本仓库以 MIT 继续授权并署名。若认为某一处的改写仍构成其表达，
> 欢迎提 issue —— 我们会在保留署名与链接的前提下调整。

---

## 4. 本项目自有原创部分

以下内容为原创，版权归本项目作者所有，按本仓库根目录 `LICENSE` 授权；
其中标注为 OpenMAIC 衍生的一组另受 MIT 许可约束（署名见 §3）：

```
agent.md
README.md
LICENSE
NOTICE.md
references/he-context-adapter.md
references/faculty-capability-matrix.md
references/rejected-skills.md
references/upstream-candidates.json
references/external-skills.json
references/profiles.json
references/skill-rewrite-spec.md
references/rewrite-manifest.json
references/third-party-provenance.md
scripts/skill_scan.py
scripts/profile_map.py
scripts/verify_repo.py
scripts/test_verify_repo.py
scripts/verify_rewrite.py
scripts/package_release.py
scripts/sync_rewrite_docs.py
scripts/normalize_domain.py
demo/README.md
demo/run_demo.py
demo/selfcheck.py
demo/llm.py
demo/selftest.py
demo/course_input.example.json
demo/prompts/lesson_plan.md
demo/prompts/exam_paper.md
demo/prompts/slides.md
demo/spec/lesson_plan.example.json
demo/spec/exam_paper.example.json
demo/spec/slides.example.json
crons/quarterly-skill-scan.md
# ── 以下为 OpenMAIC（MIT / THU-MAIC）方法论内核适配，署名见 THIRD-PARTY-NOTICES.md §3 ──
skills/grant-proposal-writer/
skills/exam-question-bank/
skills/teaching-file-builder/
skills/skill-scan/
skills/he-context-adapter/
skills/citation-audit/
skills/assertive-writing/
skills/submission-readiness/
skills/argument-structure-scaffold-generator/
skills/assessment-design-orchestrator/
skills/assessment-validity-checker/
skills/backwards-design-unit-planner/
skills/checking-for-understanding-protocol-designer/
skills/cognitive-load-analyser/
skills/coherent-rubric-logic-builder/
skills/competency-unpacker/
skills/coverage-audit/
skills/criterion-referenced-rubric-generator/
skills/curriculum-crosswalk/
skills/dialogic-teaching-move-generator/
skills/differentiation-adapter/
skills/discipline-specific-critical-thinking-task-designer/
skills/discussion-protocol-selector/
skills/dual-coding-designer/
skills/error-analysis-protocol/
skills/explicit-instruction-sequence-builder/
skills/feedback-quality-analyser/
skills/formative-assessment-loop-designer/
skills/formative-assessment-technique-selector/
skills/gap-analysis-from-student-work/
skills/hinge-question-designer/
skills/learning-analytics-interpretation-guide/
skills/learning-progression-builder/
skills/learning-target-authoring-guide/
skills/lesson-observation-protocol-designer/
skills/lesson-opening-designer/
skills/lesson-study-cycle-designer/
skills/pedagogical-content-knowledge-developer/
skills/practice-problem-sequence-designer/
skills/productive-failure-protocol/
skills/project-brief-designer/
skills/reflective-practice-prompt-generator/
skills/retrieval-practice-generator/
skills/scope-and-sequence-designer/
skills/self-regulation-scaffold-generator/
skills/single-point-rubric-designer/
skills/socratic-questioning-sequence-generator/
skills/source-credibility-evaluation-protocol/
skills/spaced-practice-scheduler/
skills/study-strategy-selector/
skills/teach-back-evaluator/
skills/teacher-inquiry-cycle-designer/
skills/technological-pedagogical-content-knowledge-developer/
skills/think-aloud-script-generator/
skills/transfer-bridge/
skills/udl-lesson-auditor/
skills/udl-options-designer/
skills/worked-example-fading-designer/
skills/authentic-context-course-designer/
skills/feynman-diagnostic-cycle/
skills/he-context-adapter/
skills/openmaic-courseware/
skills/personal-course-pattern-builder/
skills/teacher-style-profile/
skills/vocational-task-course/
# ── 以下为本项目新写的原创技能（不进改写清单、也不由 OpenMAIC 衍生）──
skills/paper-to-talk-designer/
skills/teaching-slide-builder/
skills/teaching-slide-designer/
skills/formula-typesetting/
reports/（巡检报告与验证产出）
```

> ⚠️ **原创部分不因上游的 ShareAlike 条款而改变许可**，
> 但**本仓库整体的分发条件受最严格的上游条款约束**（见根目录 LICENSE 的说明）。
>
> 这份自有清单与根目录 `LICENSE` 的「自有原创部分」清单**必须一致**，
> 由 `scripts/verify_repo.py` 比对。

---

## 5. 本项目未包含的上游内容（供溯源）

### 5.1 因许可限制而移出的上游

| 仓库 | 许可 | 处置 |
|---|---|---|
| Imbad0202/academic-research-skills | **CC BY-NC 4.0**（仅限非商业） | 其 3 个技能 `academic-paper` / `academic-paper-reviewer` / `deep-research` 已移出到 `skills-archive/`，**不随本仓库分发** |

> 移出的原因：NonCommercial 条款会传染到整个分发物 —— 它们在包里，整个仓库就不能商用。
> **本分发版不含任何 NC 内容，因此整体可商用。**
> 论文线由本仓库内的 MIT 技能承担（9 个 K-Dense + 3 个本项目原创），
> 能力矩阵相应格位为「已覆盖」。
> 详见 `skills-archive/README.md`。

### 5.2 曾因能力分工移出、当日回装的上游（MIT，无许可障碍）

| 仓库 | 许可 | 处置 |
|---|---|---|
| K-Dense-AI/scientific-agent-skills | **MIT**（可商用，无许可障碍） | 其中 9 个论文类技能上午主动移出、**当日回装** |

> **时间线**：2026-10-22 上午以「能力分工」为由移出 9 个论文类技能，
> 拟将论文线交给本机全局技能 `academic-deep-writer`（ADW）——
> 理由是 ADW 的引用核验（`cite_verify.py`）与审稿内核（`adw-review` §6）能力更强。
> **同日改回**：ADW **不随本仓库分发**，克隆后论文类需求会无人接手，
> 与"整体可商用、可交付"的定位直接冲突。**能力必须随分发物走。**
>
> **当日回装的 9 个**：`scientific-writing`、`venue-templates`、
> `scholar-evaluation`、`peer-review`、`literature-review`、
> `research-lookup`、`paper-lookup`、`citation-management`、`scientific-slides`。
> 现全部列于 §2，E2 / E4 / E5 / E9 四格在能力矩阵中为「已覆盖」。
>
> **ADW 的强项没有被丢弃**：本仓库另行编写了 3 个原创技能吸收其核心判据 ——
> `citation-audit`（引用真实性四档判定 + 正文↔文献表编号对账）、
> `assertive-writing`（6 类防御性表达 + 5 条保留判据 + 写作雷区 A1–A6 / B1–B5）、
> `submission-readiness`（摘要体检 / 控制变量体检 / DOCX 公式审计 / 格式转换）。
> 这是**独立实现**（依据公开发表的方法论），不是复制 ADW 代码。
> 用户本机若装有 ADW，仍可作为**可选增强**自行搭配。

### 5.3 与本项目无关的上游

以下仓库在建立能力矩阵时被评估并**排除**，故未打包进本项目：

| 仓库 | 许可 | 排除理由 |
|---|---|---|
| sickn33/agentic-awesome-skills | 见其仓库 | 主体为 web 安全/营销/DevOps，与教学科研无关（S1/S2/S3） |
| ComposioHQ/awesome-claude-skills | 索引 | 内容已由上述三个主源覆盖 |
| VoltAgent/awesome-agent-skills | 索引 | 同上 |
