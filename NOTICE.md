# NOTICE

## 署名与致谢

### 主题与命名参考自 education-agent-skills（CC BY-SA 4.0）

本项目的 50 个教学技能在**主题选择与命名**上参考了
[GarethManning/education-agent-skills](https://github.com/GarethManning/education-agent-skills)
（原作者：Copyright (c) 2026 Gareth Manning；上游许可：CC BY-SA 4.0）。

- **上游正文未被复制。** 这 50 个技能是本项目**独立创作**的 MIT 许可技能，
  撰写依据是公开发表的教育研究文献（各技能 SKILL.md 的「方法论依据」段
  逐条列明出处）。
- **机械相似度核验。** `scripts/verify_rewrite.py` 对每个技能比对上游原文：
  8-gram Jaccard 相似度须 < 0.10、长行（≥25 字符）重合率须 < 5%。
  上游原文仅作该比对用途，**未进入本仓库任何交付文件**。
- **上游 `skill_id` 字段已全部移除** —— 保留它就等于声明"这是上游改编版"。
- **致谢与承诺。** 保留其 CC BY-SA 4.0 许可全文副本
  （`licenses/CC-BY-SA-4.0-education-agent-skills.txt`）**仅供追溯其原始许可**。
  若任何人认为某一技能的命名或主题选择仍构成其表达，欢迎提 issue ——
  我们会在保留署名与链接的前提下调整。

> 完整声明见 `references/third-party-provenance.md`。

### 对 scientific-agent-skills（MIT / Apache-2.0）的 20 个科研技能

**改动**：**未修改内容本体**，仅复制到 `skills/` 目录。
唯一例外：`latex-posters` 的 frontmatter 原本**漏写** `license:` 字段，
本仓库补上了 `license: MIT`（上游仓库根目录 `LICENSE.md` 即为 MIT，
这是补正上游遗漏的声明，不是内容改写）。详见 `THIRD-PARTY-NOTICES.md` §5。

> 该上游原有 20 个技能，**已全部装入本仓库**：其中 9 个论文类技能
> （`scientific-writing`、`venue-templates`、`scholar-evaluation`、`peer-review`、
> `literature-review`、`research-lookup`、`paper-lookup`、`citation-management`、
> `scientific-slides`）曾于 2026-10-22 上午以「能力分工」为由移出，
> **当日回装** —— 论文线必须随包分发，不能依赖本机全局技能。
> 另 11 个承担科研**方法**侧（实验设计、统计、假设生成、基金申报、
> 图表、海报、示意图等）。
>
> ⚠️ **许可不是一刀切 MIT**：19 个为 MIT；
> `markdown-mermaid-writing` 声明的是 **Apache-2.0**（署名 Clayton Young /
> Superior Byte Works, LLC）—— 上游未随该技能提供 Apache-2.0 全文，
> 本仓库按 Apache-2.0 §4(a) 补齐副本（`licenses/Apache-2.0-markdown-mermaid-writing.txt`）
> 并在此登记署名。

### 对 OpenMAIC（MIT / THU-MAIC）的方法论内核适配：6 个新建 + 7 个既有技能内增补

本仓库的 **13 个技能**（6 个新建 + 7 个既有技能内增补章节）含
[OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) 的方法论内核适配
（原作者：Copyright (c) 2026 **THU-MAIC**；上游许可：**MIT**）。

- **许可副本已补齐**：`licenses/OpenMAIC-MIT.txt`，与上游 `LICENSE` **逐字节一致**。
  MIT 的义务是「保留版权声明与许可声明」，副本必须随本作品的实质性部分一起分发。
- **改动已标注**：本仓库**只抽方法论内核重写**，未复制上游任何 SKILL.md 原文，
  逐条对应关系（抽了什么、改了什么、没复制什么）见 `THIRD-PARTY-NOTICES.md` **§3**。
- **未复制绑定运行时的部分**：上游 22 个技能正文绑死 `create_stage` /
  `generate_scene` 等运行时工具，本仓库没有该运行时，整份复制只会得到悬空引用；
  守卫会机械拦住任何此类残留。
- **致谢与承诺**：保留其 MIT 许可全文副本与署名。若认为某一处改写仍构成其表达，
  欢迎提 issue —— 我们会在保留署名与链接的前提下调整。

---

## 本项目不含 NonCommercial 内容

本项目的**分发版不含任何 CC BY-NC（NonCommercial）内容**，
因此整体可用于商业用途。

曾纳入考虑的 3 个 CC BY-NC 4.0 技能
（`academic-paper` / `academic-paper-reviewer` / `deep-research`，
上游 `Imbad0202/academic-research-skills`）已移出到 `skills-archive/`，
该目录**不随本仓库分发**（见根目录 `.gitignore` 与 `scripts/package_release.py`）。

若你从上游另行安装这些技能到自己的环境，请注意它们**仅限非商业使用**，
且不得与本项目的分发物混在一起。

---

## 本项目自有原创部分

以下内容为原创，版权归本项目作者所有，按本仓库根目录 `LICENSE` 授权；
其中标注为 OpenMAIC 衍生的一组另受 MIT 许可约束（署名见上节与
`THIRD-PARTY-NOTICES.md` §3）：

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
reports/（巡检报告与验证产出）
```

> 该清单与根目录 `LICENSE`、`THIRD-PARTY-NOTICES.md` 的「自有原创部分」
> **必须三方一致**，由 `scripts/verify_repo.py` 比对。

---

## 第三方依赖

本项目运行时**不要求**安装任何第三方 Python 包。
`scripts/skill_scan.py`、`scripts/verify_repo.py`、`scripts/package_release.py`、
`scripts/verify_rewrite.py`、`scripts/check_citations_crossref.py`
均仅使用标准库。

可选：设置环境变量 `GITHUB_TOKEN` 以提高 GitHub API 限额
（未认证 60 req/h → 已认证 5000 req/h）。**token 不会被写入任何文件**。

---

## 商标与致谢

- 本项目与 Gareth Manning、K-Dense Inc.、THU-MAIC 无隶属关系。
- 上游项目名称与商标归各自权利人所有。
- 文中出现的教材名称（如 Gonzalez & Woods《Digital Image Processing》）
  为其作者与出版方的财产，仅作为方法示例引用。
