# Junior-Faculty-Agent · 高校青年教师 Agent

一个模拟**中国高校青年教师**的本地 Agent，覆盖两条主线：**教学**与**科研**，
并具备**每 3 个月自动检索 GitHub 技能生态、判断并学习新技能**的自学习能力。

## 它是什么

不是聊天机器人，是**能产出交付物的同事**：

| 用户说 | Agent 交付 |
|---|---|
| 「帮我把这门课的第 3 章写成教案」 | 教案 DOCX：逆向设计三段（目标→考核证据→教学活动）+ Alignment Check 逐条填实 + 板书 + 课后作业 + 课程思政融入点 |
| 「出套期末卷」 | 试卷 DOCX：目标—题型—认知层次映射表 + 难度分布 + 完整试题 + 逐题评分细则 + A/B 等价卷 + 题库覆盖矩阵 |
| 「写个国自然申报书」 | 申报书全文：立项依据（含 3–5 条创新点对应具体缺口）+ 技术路线图 + 经费预算表（合计=申请额）+ 自检表 |
| 「帮我把稿子投出去」 | 投稿件 + 审稿意见逐点回复 + 引用核实报告 + 目标期刊格式适配 |
| 「做个组会汇报」 | PPT：叙事弧（问题→方法→结果→意义）+ 图表规范 + 讲稿要点 |
| 「这学期的课怎么改进」 | 教学诊断 + 改进方案 + 可复用的课堂观察协议 |

## 能力矩阵（6 域 41 格）

能力边界写在 `references/faculty-capability-matrix.md`，**每一格都要有技能接住**。
覆盖计数口径 = **完全覆盖的格数 / 该域总格数**；`部分覆盖` 与 `缺口` 不计入分子。

| 域 | 内容 | 完全覆盖 | 部分覆盖 | 缺口 |
|---|---|---|---|---|
| A 教学准备 | 目标与毕业要求支撑、大纲、学情分层、课程思政 | 4/6 | 1（A5 教材遴选） | 1（A6 教学工作量折算） |
| B 教学实施 | 逆向设计、导入、例题、提问、理解检测、认知负荷 | 6/7 | 1（B7 板书可视化） | 0 |
| C 考核评价 | 量规、效度、学习进阶、批判性思维任务、命题 | 6/7 | 1（C7 成绩分析） | 0 |
| D 学生支持 | 自我调节、错因分析、反馈、迁移、信息素养 | 5/6 | 1（D6 AI 使用规范教学） | 0 |
| E 科研全流程 | 选题、文献、实验、写作、评议、图表、汇报、申报 | 9/10 | 0 | 1（E10 学术简历） |
| F 教研发展 | 课例研究、反思实践、学科教学知识、UDL、AI 素养 | 4/5 | 0 | 1（F5 AI 素养教学） |
| **合计** | | **34/41** | 4 | 3 |

> 矩阵的「覆盖技能」列用 `●`（随仓库分发）/ `○`（上游存在但未装）/ `◐`（本机其他技能）三种标记。
> **没有 `●` 的格不算覆盖** —— 克隆本仓库后该格会退化为缺口。
> 3 个缺口（A6 / E10 / F5）是下一轮巡检的优先输入。
>
> 📌 **论文类四格（E2 / E4 / E5 / E9）随本仓库分发**，不依赖任何本机全局技能：
> 9 个 K-Dense MIT 论文类技能（`literature-review` / `scientific-writing` /
> `venue-templates` / `peer-review` / `scholar-evaluation` / `citation-management` /
> `research-lookup` / `paper-lookup` / `scientific-slides`）
> + 3 个本项目原创（`citation-audit` / `assertive-writing` / `submission-readiness`）。
> 克隆即用。
>
> 📌 **能力矩阵同时是「分档出包」的推导源**：每个已装技能都在某一格里有归属，
> 按**能力域**就能机械推出 teaching / research 两个分档各含哪些技能 ——
> 不必手工枚举清单（手工清单会与矩阵漂移，漂移是静默的）。
> 推导器 `scripts/profile_map.py`（出包器与守卫共用同一份实现），
> 档位数据 `references/profiles.json`，恒等式
> `teaching ∪ research = full − 仓库机制类技能` 由守卫机械校验。
> 详见「分档出包」一节。

## 技能构成（86 个）

### 本项目原创编写（66 个）

| 来源 | 数量 | 内容 | 许可 |
|---|---|---|---|
| 独立创作（clean-room 重写） | 50 | 教学法与课程设计：逆向设计、量规、认知负荷、提问序列、课例研究 | **MIT**（原创） |
| 本 Agent 私有编写 | 5 | 中国基金申报书、命题题库、教学文件产出规范、季度巡检流程、高校语境映射 | **MIT**（原创） |
| 论文线原创编写（2026-10-22 新增） | 3 | `citation-audit`（引用真实性核验 + 编号对账）、`assertive-writing`（防御性写作 + 写作雷区）、`submission-readiness`（投稿前体检） | **MIT**（原创） |
| **OpenMAIC 方法论内核适配（2026-10-22 新增）** | 3 | `authentic-context-course-designer`（真实情境→表现性任务→可观察证据→迁移）、`feynman-diagnostic-cycle`（费曼 8 步理解诊断）、`vocational-task-course`（职业实训任务引擎课程） | **MIT**（原创，方法论内核适配自 OpenMAIC，署名见 `THIRD-PARTY-NOTICES.md` §3） |
| **课件产出与幻灯片线自研（2026-10-22 第 5 版新增）** | 4 | `teaching-slide-designer`（教学幻灯片**设计**：一页一个认知任务、断言式标题、讲稿分离）、`teaching-slide-builder`（课件**生成**：纯标准库 PPTX 生成器 + 版式几何 + 溢出判据 + 实开验收）、`paper-to-talk-designer`（论文→汇报叙事）、`openmaic-courseware`（OpenMAIC 课件产出链接入 + 容器编排） | **MIT**（原创；`openmaic-courseware` 的方法论内核适配自 OpenMAIC，署名见 `THIRD-PARTY-NOTICES.md` §3） |
| **教师风格与个人方法论（2026-10-22 第 5 版新增）** | 2 | `teacher-style-profile`（名师风格画像与迁移）、`personal-course-pattern-builder`（个人做课记录→专属工作法） | **MIT**（原创；方法论内核适配自 OpenMAIC，署名见 `THIRD-PARTY-NOTICES.md` §3） |

> 📌 **幻灯片线为什么要自研**：第 5 版之前，「做 PPT」这件事挂在**运行时内置**的
> `pptx` 技能和**本机全局**的 `nature-paper2ppt` 上 —— 两者都**不随本仓库分发**，
> 克隆本仓库后「做个组会汇报」就无人接手。这与论文线（ADW）是**同一个坑**。
> 现由本仓库自研：纯标准库 PPTX 生成器（`build_pptx.py`，零第三方依赖，
> 产出可被 PowerPoint 直接打开并继续编辑的 `.pptx`，含讲授者备注）
> + 教学规范审查器（`slide_spec_lint.py`，判的是"这**是不是**一份能用的教学幻灯片"
> 而非"格式对不对"）。守卫会机械拦截 `pptx` / `nature-paper2ppt` 重新进入
> 外部技能表或矩阵。

**50 个教学技能是怎么来的**：主题与命名参考了
[GarethManning/education-agent-skills](https://github.com/GarethManning/education-agent-skills)
（CC BY-SA 4.0），但**正文全部是本项目独立创作**的 —— 撰写依据是公开发表的
教育研究文献（各技能 SKILL.md 的「方法论依据」段逐条列明出处），
并通过了与上游原文的**机械相似度核验**
（`scripts/verify_rewrite.py`：8-gram Jaccard < 0.10、长行重合 < 5%）。
上游正文**未被复制**，上游的 `skill_id` 字段已全部移除。
完整声明见 `references/third-party-provenance.md`。

**中国高校语境是内置的，不是翻译**：学时制、评价制度（期末/过程性考核权重）、
课程思政自然融入、毕业要求支撑、教材 ISBN 核验等维度在写作时就已纳入。
映射表见 `references/he-context-adapter.md`。

**3 个 OpenMAIC 衍生技能是怎么来的**：方法论内核适配自本机的
[OpenMAIC](https://github.com/THU-MAIC/OpenMAIC)（**MIT**，Copyright (c) 2026 THU-MAIC）。
MIT 允许闭源商用再分发，**唯一义务是保留版权声明与许可声明** ⇒ 本仓库补齐了
`licenses/OpenMAIC-MIT.txt`（与上游逐字节一致），并在 `THIRD-PARTY-NOTICES.md` §3 登记署名。

> ⚠️ **只抽方法论内核，不复制运行时绑定的那 22 个 SKILL.md**。
> 那些正文写死了 `create_stage` / `generate_scene` / `patch_stage` 等运行时工具，
> 整份复制进来就是**悬空引用**（本仓库没有 OpenMAIC 运行时，那些调用谁也执行不了）。
> 本仓库只把**教学法内核**（UbD 三阶段与 GRASPS/WHERETO、真实情境不变量与载体决策、
> 概念脊柱与升阶操作符与假螺旋检查、费曼 8 步诊断循环、诊断—支持—撤架—复核闭环、
> 澄清轮次与确认门）重写为**中国高校的交付物规格**（教案/大纲/任务书/评价表）。
> 守卫会机械拦住任何 OpenMAIC 运行时工具名的残留。
>
> 📌 这 3 个技能同时补进了既有技能的缺口：`backwards-design-unit-planner`（UbD 三阶段 +
> GRASPS + WHERETO 覆盖表）、`scope-and-sequence-designer` 与 `learning-progression-builder`
> （概念脊柱 + 升阶操作符 + 假螺旋检查）、`formative-assessment-loop-designer` 与
> `error-analysis-protocol`（诊断→支持→撤架→复核闭环 + 最小学习记录）、
> `project-brief-designer`（澄清轮次 + 确认门 + 长上下文纪律）。

### 从 GitHub 学习而来（20 个）

| 来源 | 数量 | 内容 | 许可（已逐一核实原文） |
|---|---|---|---|
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 19 | 科研**方法**侧：实验设计、统计分析、不确定度与单位、假设生成、科研批判性思维、科研头脑风暴、基金申报（英文口径）、投稿级图表、科学示意图、LaTeX 海报、Markdown/Mermaid 写作、**文献综述、论文写作、投稿模板、同行评议、文献评价、引用管理、检索、学术 slides** | **MIT**（可商用） |
| 同上（第三方贡献） | 1 | `markdown-mermaid-writing`（Mermaid 图表写作） | **Apache-2.0**（可商用，署名 Superior Byte Works, LLC） |

> 📌 **许可不是"一刀切 MIT"**：19 个 K-Dense 技能是 MIT；
> `markdown-mermaid-writing` 的 frontmatter 声明的是 **Apache-2.0**
> （署名 Clayton Young / Superior Byte Works, LLC），
> 上游仓库只发了 MIT 全文、没随该技能提供 Apache-2.0 副本。
> 本仓库已按 Apache-2.0 §4(a) 补齐副本
> （`licenses/Apache-2.0-markdown-mermaid-writing.txt`，与 apache.org 官方原文逐字一致），
> 并在 `THIRD-PARTY-NOTICES.md` 登记署名。**Apache-2.0 同样允许商用**，
> 只是义务不同（须提供副本 + 保留署名 + 标注改动）。
> 守卫会机械检查这三条。

这 20 个 GitHub 技能**内容本体原样复制、未修改**（保持上游内容不变；
仅在 `latex-posters` 的 frontmatter 补上上游漏写的 `license: MIT` 声明；
上游自带的悬空交叉引用改在本项目文档层面处理，见「已知限制」第 6 条）。

> 📌 **论文类九件已回装（2026-10-22）**
>
> 这 9 个 K-Dense MIT 技能上午曾因「能力分工」被移出（论文线拟交给本机全局技能
> `academic-deep-writer` / ADW），**当日改回**：论文线必须随包分发 ——
> ADW 不随分发，克隆后论文类需求会无人接手，与"整体可商用、可交付"的定位冲突。
>
> | 技能 | 职责 | 配合的原创技能 |
> |---|---|---|
> | `scientific-writing` | 论文正文写作 | — |
> | `venue-templates` | 投稿期刊模板与格式 | `submission-readiness`（格式转换） |
> | `scholar-evaluation` / `peer-review` | 同行评议、审稿意见 | `assertive-writing`（防御性写作 lint） |
> | `literature-review` | 文献综述 | `citation-audit`（引用核验） |
> | `research-lookup` / `paper-lookup` | 检索与存在性核验 | `citation-audit` |
> | `citation-management` | 引用著录与格式 | `citation-audit`（逐条真实性） |
> | `scientific-slides` | 学术汇报 slides | — |
>
> ADW 仍可作为**可选增强**由用户自行搭配，但矩阵与守卫**不再依赖它**。

### 私有 5 个技能补的缺口

| 技能 | 补的是什么缺口 |
|---|---|
| `grant-proposal-writer` | 中文基金/项目申报书（上游只有英文 NSF/NIH/Taiwan NSTC 口径，缺中国基金的形式要件） |
| `exam-question-bank` | 课程命题、试卷结构、题库覆盖矩阵、A/B 等价卷 |
| `teaching-file-builder` | 教学文件统一产出规范（大纲/教案/课件大纲/讲义的格式与自检） |
| `skill-scan` | 季度巡检与自动学习的执行流程 |
| `he-context-adapter` | 高校语境映射表（供所有教学技能引用） |

## 自学习机制

**每 3 个月**（1/4/7/10 月 1 日 10:00，Asia/Shanghai）自动唤醒 Agent 执行巡检：

1. **扫描** — `scripts/skill_scan.py --scan` 检索 GitHub（20 组能力缺口关键词 + 3 个主源仓库比对）
2. **判读** — Agent 逐个打开候选 SKILL.md，判断其任务**是否属于高校教师职责**；
   不符合的记入 `references/rejected-skills.md` 并标注理由类别，避免重复评估
3. **安装** — `scripts/skill_scan.py --install` 按决策安装，教学类自动追加语境适配
4. **更新矩阵** — 回填能力矩阵，缺口 → 已覆盖
5. **产出报告** — `reports/skill-scan-<年>-Q<N>.md`
6. **自检** — 三个都要绿：
   `scripts/skill_scan.py --selftest`（20/20，验巡检器本身）
   + `scripts/verify_repo.py`（文档↔现实一致性，验矩阵/README/NOTICES 没写错）
   + `scripts/verify_rewrite.py`（结构合规 + 全仓交叉引用）

### 三条设计纪律

- **判读不能靠正则** —— 脚本只做「发现」与「按决策安装」，
  「是否属于高校教师能力」是 Agent 的语义判断。硬编码成正则就会漏。
- **拉取失败 ≠ 没有新技能** —— 主源拉取失败会写入 `errors` 并让扫描以退出码 2 结束，
  不会静默产出「本季度无新技能」的假结论。
- **单次新增上限 10 个** —— 贪多会让能力矩阵失焦。

### 巡检任务当前状态

`cron 67c34763-7b58-4983-b6d6-2a4ef3e5657c` ｜ `0 10 1 1,4,7,10 *` ｜ Asia/Shanghai
｜ 下次触发 2027-01-01 10:00 ｜ status `active`。

> 2026-10-22 检查发现该任务此前处于 **paused**（零运行、无 nextRun），
> 已用相同参数重建为上表 id。**"任务存在"不等于"会触发"** —— 巡检前要确认
> `status = active` 且 `nextRun` 有值。

## 五条硬纪律（写进系统提示词）

1. **不得编造** ISBN、学分号、毕业要求编号、项目号、DOI、期刊分区、参考文献、数据
2. **教学文件必须对齐** —— Alignment Check 表格要逐条填实，不是"无失配"了事
3. **评价方案权重合计必须 = 100%**
4. **课程思政要自然融入**，不贴标签、不写空话
5. **区分"设计使然"与"我编的"** —— 假设标「假设」，缺项标「待确认」

## 目录结构

```
junior-faculty-agent/
├── agent.md                              # 系统提示词（能力矩阵 + 五条硬纪律 + 工作方式）
├── LICENSE                               # 许可：自有原创部分为 MIT
├── NOTICE.md                             # 署名与致谢说明
├── THIRD-PARTY-NOTICES.md                # 三方来源归属 + 技能清单 + 上游致谢
├── CHANGELOG.md                          # 变更记录（Keep a Changelog）
├── CONTRIBUTING.md                       # 贡献指南（含 Windows 编码坑、「改守卫必须配变异」）
├── CODE_OF_CONDUCT.md                    # 社区行为准则
├── SECURITY.md                           # 漏洞私下报告渠道（不开公开 issue）
├── .gitattributes                        # 文本一律 LF、二进制不转换（优先于 core.autocrlf）
├── .editorconfig                         # 编辑器约定（UTF-8 无 BOM / LF / 缩进）
├── .github/                              # GitHub 开源件
│   ├── workflows/ci.yml                  # CI：把本仓库已有的判据接上去（Linux+Windows × py3.9/3.13）
│   ├── workflows/release.yml             # 打 tag 即出三档包 + 源码包 + 发布说明
│   ├── ISSUE_TEMPLATE/                   # 问题 / 建议模板
│   └── PULL_REQUEST_TEMPLATE.md          # PR 自检清单
├── licenses/                             # 上游许可副本（完整包 4 份；分档包按实际技能动态裁剪）
│   ├── CC-BY-SA-4.0-education-agent-skills.txt   # 仅供追溯上游原始许可
│   ├── MIT-K-Dense.txt                            # 19 个 K-Dense MIT 技能
│   ├── Apache-2.0-markdown-mermaid-writing.txt   # Apache §4(a)：须随包提供副本
│   └── OpenMAIC-MIT.txt                           # MIT (c) 2026 THU-MAIC：3 个衍生技能的署名依据
├── skills/                               # 88 个技能（68 原创 + 20 GitHub）
│   ├── grant-proposal-writer/            # 私有：项目申报书
│   ├── exam-question-bank/               # 私有：命题与题库
│   ├── teaching-file-builder/            # 私有：教学文件产出规范
│   ├── skill-scan/                       # 私有：季度巡检流程
│   ├── he-context-adapter/               # 私有：高校语境映射
│   ├── citation-audit/                   # 原创：引用真实性核验 + 编号对账
│   ├── assertive-writing/                # 原创：防御性写作 + 写作雷区
│   ├── submission-readiness/             # 原创：投稿前体检
│   ├── authentic-context-course-designer/# 原创：真实情境课程设计（OpenMAIC 内核）
│   ├── feynman-diagnostic-cycle/         # 原创：费曼 8 步理解诊断（OpenMAIC 内核）
│   ├── vocational-task-course/           # 原创：职业实训任务课程（OpenMAIC 内核）
│   ├── teaching-slide-designer/          # 原创：教学幻灯片设计（写什么：认知任务/断言式标题/讲稿分离）
│   ├── teaching-slide-builder/           # 原创：课件生成（怎么生成：PPTX 生成器 + 版式几何 + 实开验收）
│   ├── formula-typesetting/              # 原创：公式校正（伪公式 → LaTeX → OMML 真公式 + 验收闸）
│   ├── paper-to-talk-designer/           # 原创：论文→学术汇报叙事
│   ├── openmaic-courseware/              # 原创：OpenMAIC 课件产出链接入（OpenMAIC 内核）
│   ├── teacher-style-profile/            # 原创：名师风格画像与迁移（OpenMAIC 内核）
│   ├── personal-course-pattern-builder/  # 原创：个人做课记录→专属工作法（OpenMAIC 内核）
│   ├── <50 个原创教学技能>
│   └── <20 个 GitHub 技能>
├── references/
│   ├── faculty-capability-matrix.md      # 能力矩阵（巡检基线，41 格；也是分档推导源）
│   ├── profiles.json                     # 分档定义（档案 → 能力域；受控数据）
│   ├── he-context-adapter.md             # K-12 → 中国高校 映射表
│   ├── rejected-skills.md                # 已排除技能记录
│   ├── external-skills.json             # 外部技能登记表（◐ 的受控词表）
│   ├── github-release.json              # GitHub 发布配置（仓库名/描述/topics 的唯一出处）
│   └── upstream-candidates.json          # 矩阵里 ○ 候选技能的登记
├── scripts/
│   ├── skill_scan.py                     # 巡检器（纯标准库）
│   ├── profile_map.py                    # 分档推导（唯一实现；出包器与守卫共用）
│   ├── verify_repo.py                    # 文档↔现实一致性守卫
│   ├── github_release.py                 # GitHub 源码包 + 发布说明（独立校验 + 克隆即用）
│   └── test_verify_repo.py               # 守卫的变异测试（证明它会红）
├── demo/                                # 最小本地演示：课程信息 → 教案/试卷/PPTX/讲义 + 自检报告
│   ├── run_demo.py                      # 主程序（离线用示例大纲 / 在线调模型写大纲）
│   ├── outline.py                       # 大纲先行层：大纲 → 教案 / 课件 / 讲义 的派生器 + 增量重生成
│   ├── selfcheck.py                     # 大纲/教案/试卷/讲义的形式合规判据
│   ├── llm.py                           # OpenAI 兼容客户端 + 按用途路由 + 从技能文档摘规则
│   ├── selftest.py                      # 判据的变异测试（证明它会红）
│   ├── prompts/                         # 七个任务的任务书与输出结构
│   └── spec/                            # 示例大纲 + 示例试卷规格（教案/课件/讲义由大纲派生）
├── reports/                              # 巡检报告
├── crons/                                # 定时任务说明
└── skills-archive/                       # ⚠️ 本机自用，非商业内容，不随分发
```

> 📎 **论文类能力随本仓库分发**：论文写作、投稿、文献综述、审稿回复由仓库内
> 9 个 K-Dense MIT 技能 + 3 个本项目原创技能承担，**不依赖任何本机全局技能**。
> 用户本机若已装 `academic-deep-writer`（ADW），可作为可选增强自行搭配。
> 详见 `agent.md` 的 Hand off 段。

## 使用

```bash
# 直接对话
#   "帮我写《数字图像处理》第 4 章教案，2 学时，本科大三"

# 手动触发巡检
python scripts\skill_scan.py --selftest     # 离线自检
python scripts\skill_scan.py --scan          # 扫描（需联网）
python scripts\skill_scan.py --install spec.json   # 按决策安装
```

## 30 秒看到它能干什么

```bash
python demo\run_demo.py --out demo\out
```

输入一份课程信息，产出**教案 + 试卷 + 可编辑的 PPTX + 讲义**，外加一份**机器自检报告**：

> 🧱 **中间多了一层「大纲」**：教案与课件若各自写出来，改了教案忘了改课件只能靠事后核对。
> 现在两者都从同一份**大纲**派生 —— 对齐是**结构问题**，不再是检查问题。
> （在线模式的模型调用次数也从 3 次降到 2 次：课件与教案不再各问模型一次。）

| 交付物 | 按什么结构 | 自检管什么 |
|---|---|---|
| 大纲（唯一事实源） | `skills/teaching-file-builder`「大纲先行层」 | 时间三层闭合（本次课 = Σ模块 = Σ环节）；目标闭合；每页课件可溯源到环节；无页面的环节写明原因；封面唯一；**UbD 骨架齐全**（大概念 / 基本问题 / GRASPS / WHERETO）；**每页有稳定 id** |
| 教案 Markdown | `skills/teaching-file-builder` 十二节 | 各环节时间合计 = 总学时；目标用可观察动词且绑定课程目标编号；留空的事实项进了需人工核验清单；**含 UbD 设计骨架一节** |
| 试卷 Markdown | `skills/exam-question-bank` 六节 | 各题分值合计 = 总分；目标—题型、认知层次、难度三张表各自合计 = 总分；每题有评分细则；有备用卷 B |
| PPTX | 仓库自研的纯标准库生成器 | L01–L15 教学规范：一页几条要点、标题是不是断言、讲稿有没有、封面是否唯一、有无"如上图"式线性指代 |
| 讲义 Markdown | `skills/teaching-file-builder`「文件类型 4」 | **讲稿与课件逐字同源**（从课件规格导出，不另写一遍）；页数与课件一一对应；正文页讲稿不为空 |

自检不是"我觉得没问题"，是**机器跑的**：判据在 `demo/selfcheck.py`，
并用 57 项自测证明它**会红**而不是空转 —— 35 个变异用例（时间合计不符、目标没绑定编号、
占位符残留、分值合计 ≠ 总分、缺评分细则、一页 9 条要点、封面出现两次、
大纲层少 minutes / 环节绑错目标 / 环节无页面也没写原因、
**UbD 骨架缺项 / 基本问题写成能背的题 / GRASPS 缺产物 / WHERETO 落在不存在的环节**、
**讲义讲稿被手改 / 讲义少一页**……）
+ 5 项基线 + 12 项在线路径接线检查 + 3 项不变量测试
（`python demo\selftest.py` → 57/57）。
完整说明（含在线模式怎么配模型端点）见 `demo/README.md`。

> 📌 示例课程「数字图像处理」及其中的题目、答案、参数**均为演示用途的虚构内容**，
> 不是真实教材或真实考试。真要用请替换 `demo/spec/*.example.json`。

### 大纲先行层的四个能力

| 能力 | 做什么 | 判据 |
|---|---|---|
| **UbD 骨架** | 大纲里带一份「凭什么这么设计」：持久理解 1–3 条、基本问题 3–5 个、GRASPS 表现性任务六要素、WHERETO 七项覆盖（每项写明落在哪个环节） | OL-P15–OL-P18：持久理解必须写成「能理解……并在……情境中用它」；基本问题不能是能背定义回答的题；GRASPS 的 P 与 S 必须实；WHERETO 七项都要落在真实环节上（E·Experience 与 R·Rethink 最常漏） |
| **讲义派生** | 讲义是**纯派生**的：讲稿从课件规格导出，与课件**逐字同源** | HD-P01–HD-P04：页数与课件一一对应；正文页讲稿不为空；**讲义讲稿 ≠ 课件讲稿 ⇒ 报错**（说明有人绕过派生层手改了讲义） |
| **增量重生成** | 改一页只重跑一页：`outline.py --regen-page P5 --page-file …`；在线模式只调**一次**模型 | 守卫逐页比对指纹：**只重跑一页 ⇒ 其余页逐字不动**；动了别的页 ⇒ 增量替换漏到了别处，立即报错 |
| **模型按用途路由** | `plan`（大纲/教案/试卷）、`slides`（课件/单页重生成）、`handout`（学生版讲义）、`lint`（模型审校）四档，各配各的模型 | 行为判据：四档用途必须齐；未设专用模型时回退 `JFA_LLM_MODEL` |

> 🔴 一次课一份大纲（`meta.minutes` / `session_no` 都是**单次课**），
> 多次课的课程要写多份大纲 —— 课件的合并由交付侧完成，仓库只管单次课。

## 验证

```bash
python scripts\skill_scan.py --selftest
# selftest: 20/20 checks passed

python scripts\verify_repo.py
# verify_repo: 122/122 checks passed

python scripts\verify_rewrite.py
# verify_rewrite: 688/688 checks passed
#   （这是**无上游原文**时的口径，也是克隆方默认会看到的数；
#     带上游原文（--upstream / JFA_UPSTREAM）会多跑 50 项 clean-room 相似度核对 ⇒ 738）

python scripts\test_verify_repo.py
# 56/56 项变异均被守卫在预期检查项上抓到
# （另有 3 项 verify_rewrite 变异：交叉引用悬空 / 标准章节改名 / license 非 MIT）
# （另有 3 项出包器变异：矩阵归属漂移 / 档位能力域被删 / 包内缺许可副本 → 必须中止出包）

python scripts\package_release.py --build
# → dist/junior-faculty-agent-1.0.0.zip（523 个文件 + MANIFEST.json）
# PASS  分发包校验通过 / 商业可用 True（不含 NonCommercial）
#   克隆即用  : 已通过（包内 demo 自检 + 大纲唯一事实源 + 端到端）

python scripts\github_release.py --build
# → dist/junior-faculty-agent-1.0.0-source.zip（523 个文件 + MANIFEST.json）
# → dist/RELEASE_NOTES.md
# PASS  GitHub 源码包校验通过 / 克隆即用 已通过

python demo\selftest.py
# selftest: 57/57 checks passed（Demo 自检判据的变异测试）

python demo\run_demo.py --out demo\out
# ✅ 自检通过：全部交付物零 ERROR（教案.md / 试卷.md / 幻灯片.pptx / 讲义.md + 自检报告.md）
```

`skill_scan.py --selftest` 覆盖：技能数量下限、frontmatter 完整性（name/description）、
**全量**教学技能的语境适配覆盖、5 个私有技能存在性、关键引用文件存在性、
agent.md 关键段落存在性。

`verify_repo.py` 是**文档 ↔ 现实一致性守卫**，检查 README / LICENSE /
NOTICE / THIRD-PARTY-NOTICES / 能力矩阵里写的数字与仓库实际是否一致：
技能总数与分源归属、NOTICES 清单 ↔ 磁盘目录 ↔ `skill_id` 域、
**许可台账完整性**（每个技能都声明 license / Apache-2.0 技能有许可副本 /
licenses/ 无孤儿副本 / README 不得谎称"全仓 MIT"）、
**OpenMAIC 衍生技能的归属台账**（MIT 许可副本在位 / 三方声明各有交代 /
衍生技能不得夹带 OpenMAIC 运行时工具名的悬空引用）、
**全仓 `metadata.domain` 取值受控**、
能力矩阵每格的标记与状态是否自洽
（**已覆盖**须有 ●；**部分覆盖**须有 ● 或 ◐）、
**矩阵里每个 ◐ 都登记在 `references/external-skills.json`（◐ 不是自由文本）**、
**分档推导自洽**（每个已装技能都有能力格归属 / 三档并集恒等式 /
每个能力域都被认领 / 每档所需许可副本齐备）、
**自检脚本不留临时目录**（PPTX 生成器的 `--selftest` 跑完不许在 TEMP 里
留下 `jfa_pptx_*` 残骸 —— 守卫每跑一次调它一次，漏清就是上百个空目录）、
README 的格数与覆盖计数、
**README 写的 `verify_rewrite` 检查数 = 实际（按「无上游原文」口径量）** ——
上游仓库不随本仓库分发，读者手边默认没有上游，
README 若写自己手边有上游时的数字，读者实跑对不上却不知差在哪、
硬编码绝对路径、真实密钥、UTF-8 无 BOM。

`verify_rewrite.py` 校验**结构合规**（frontmatter / license / 标准章节 /
无上游 `skill_id`）+ **clean-room 相似度**（需上游原文才可比），
并新增了**全仓交叉引用校验**——此前这条只覆盖改写清单里的 50 个技能，
本项目自己新写的技能全是盲区。

`test_verify_repo.py` 是**守卫自己的变异测试**：在仓库副本上注入典型错误
（格数写错、空覆盖冒充已覆盖、**部分覆盖格既无 ● 也无 ◐**、
**矩阵 ◐ 技能未登记在外部技能表**、漏列技能、许可副本改名、
**技能漏声明 license**、**Apache-2.0 许可副本被删**、**塞入孤儿许可副本**、
**README 谎称全仓 MIT**、
**OpenMAIC 衍生技能夹带运行时工具名**、**OpenMAIC 许可副本被删**、
**NOTICES 抹掉 THU-MAIC 署名**、**衍生技能被塞回上游 skill_id**、
**metadata.domain 塞词表外的值**、
**矩阵里摘掉一个已装技能的归属**、**档位定义删掉一个能力域**、
**档位定义删掉整个 research 档**、**PPTX 自检不再清理临时目录**、
注入路径与密钥、加 BOM、作者名拼错、● 标记过期、漏加标记、**NC 技能放回 skills/**、
**NC 许可全文放回 licenses/**、**README 把守卫自己的检查数写错**、
**README 把 `verify_rewrite` 的检查数写成「有上游」口径**……），
要求每一项都让守卫在
**预期的那条检查**上变红。另有一组针对 `verify_rewrite.py` 的变异
（交叉引用悬空 / 标准章节改名 / license 非 MIT）。
只跑绿不算数——**必须证明它会红**。
改守卫后要重跑它。

`package_release.py` 出可商用分发包，并**断言**包内不含任何 NonCommercial 内容
（NC 技能目录 / NC 许可全文 / `skills-archive/` 路径），有一项混入就中止出包。
包内含 `MANIFEST.json`（逐文件 sha256 + 档位 + 技能清单），`--verify <zip>` 可独立复验。
`--profile teaching|research` 出分档包，技能集合由能力矩阵机械推导，
推导不自洽或包内缺应有许可副本 ⇒ 同样中止出包。

> 这五个脚本是刻意分开的：`--selftest` 验**巡检器本身**，
> `verify_repo.py` 验**文档不撒谎**，`test_verify_repo.py` 验**守卫没坏**，
> `package_release.py` 验**分发物里没有禁商用内容**，
> `github_release.py` 验**源码包能发出去**。
> 五者都绿才算这个仓库状态可信。

### 端到端验证（已通过）

用真实任务跑了一遍：给《数字图像处理》第 4 章写教案 + 考核方案。
产出的文件（`reports/smoke-test-教案-图像增强.md`，54.5KB / 597 行，随仓库分发）实测：

| 交付标准 | 实测 |
|---|---|
| Alignment Check 逐条填实 | ✅ 12.1 正向映射 8 行（G1–G3 + T1–T5，每行含考核证据/教学活动/判定）+ 12.2 反向检查 8 项 |
| 考核权重合计 100% | ✅ 10 + 15 + 45 + 30 = 100% |
| 学时合计 90 分钟 | ✅ (5+11+12+17) + (5+13+13+8+6) = 45 + 45 |
| 课程思政通过"拿掉"检验 | ✅ 9.3 节逐条执行，给出拿掉后缺哪一块的判定 |
| 未编造事实项 | ✅ 课程代码/学分/毕业要求指标点全留空；ISBN 经核验并注明来源 |

## 发到 GitHub 上

本仓库**已经是一个可直接发布的 GitHub 开源项目**：CI、社区文件、Issue/PR 模板、
发布流水线、源码包产出脚本都在仓库里，并由守卫盯着（少一个件、CI 变空、
发布配置写坏、CHANGELOG 少了当前版本 —— 四种情况都会立刻变红）。

### 三步发布

```bash
# ① 建仓库 + 填一次配置：编辑 references/github-release.json 里的 "owner"
#    （仓库名 / 描述 / topics 的唯一出处，填完重跑一次出包脚本即可）
#    ⚠️ owner 一填上，守卫就会要求把文档里残留的 OWNER/REPO 占位换成真名
#       （它会指名道姓地告诉你是哪两个文件：Issue 模板与 CHANGELOG）
#    ✅ 本仓库已填好：242742532Celestia/junior-faculty-agent

# ② 打标签即发布：release.yml 会自动出包、复核、挂到 Release
git tag v1.0.0
git push origin main --tags

# ③ 本地先自己验一遍（发布前最后一道）
python scripts\verify_repo.py
python scripts\github_release.py --build
```

> 🔴 **不要手动上传 zip**：`.github/workflows/release.yml` 会在打 tag 时自动出包，
> 并**在发布前把产物解开跑一遍**（文件清单对、sha256 对、包能解开，这三件事全过
> 仍可能一跑就炸）。手工上传跳过了这道闸。

### 产物

| 产物 | 内容 | 用途 |
|---|---|---|
| `junior-faculty-agent-1.0.0.zip` | 完整包（全部技能） | 默认分发 |
| `junior-faculty-agent-1.0.0-teaching.zip` | 教学档（A/B/C/D/F 域） | 只要教学能力的用户 |
| `junior-faculty-agent-1.0.0-research.zip` | 科研档（E 域） | 只要科研能力的用户 |
| `junior-faculty-agent-1.0.0-source.zip` | 整个仓库 + `MANIFEST.json` | 源码归档 / 二次开发 |

三档的**技能集合不是手工枚举的**，而是由能力矩阵的能力域机械推导
（`references/profiles.json` → `scripts/profile_map.py`，出包器与守卫共用同一份实现）。
推导不自洽 ⇒ **中止出包**，绝不打一个来路不明的包。

### CI 做了什么

`.github/workflows/ci.yml` **不引入任何新判据** —— 它只把仓库里已有的机器判据接上去：
Linux + Windows × Python 3.9 / 3.13，各跑一遍 `verify_repo` / `verify_rewrite` /
`demo/selftest` / 大纲唯一事实源 / 离线 Demo / 三档出包 / 源码包。

🔴 **Windows 必须保留在矩阵里**：中文 Windows 控制台默认 GBK，
子进程打 `✅` 会当场崩，而父进程只看到「退出码 1」——
这类问题**只在 Windows 暴露**，只跑 ubuntu 会把它漏过去。
同理 Python 3.9 是本项目的**兼容下限**，少了它就没人证明下限还成立。

## 开源与许可

**可以开源，也可以商用。** 本仓库整体**不含任何 NonCommercial 内容**。

| 内容 | 数量 | 许可 | 商业使用 | 关键约束 |
|---|---|---|---|---|
| 教学技能（本项目独立创作） | 50 | **MIT** | ✅ 允许 | 独立创作，不承担上游义务 |
| 私有技能与脚本文档 | 8 | **MIT** | ✅ 允许 | 原创 |
| 论文线原创技能 | 3 | **MIT** | ✅ 允许 | 原创（`citation-audit` / `assertive-writing` / `submission-readiness`） |
| **OpenMAIC 方法论内核适配技能** | 3 | **MIT** | ✅ 允许 | **须保留版权声明与许可声明**（MIT）；副本在 `licenses/OpenMAIC-MIT.txt`，署名 THU-MAIC |
| 课件产出与幻灯片线自研技能 | 4 | **MIT** | ✅ 允许 | 原创（`teaching-slide-designer` / `teaching-slide-builder` / `paper-to-talk-designer` / `openmaic-courseware`）；其中 `openmaic-courseware` 另受 OpenMAIC 署名条款约束 |
| 教师风格与个人方法论技能 | 2 | **MIT** | ✅ 允许 | 原创（`teacher-style-profile` / `personal-course-pattern-builder`）；另受 OpenMAIC 署名条款约束 |
| 科研技能（`scientific-agent-skills`） | 19 | **MIT** | ✅ 允许 | 保留版权声明与许可声明 |
| `markdown-mermaid-writing` | 1 | **Apache-2.0** | ✅ 允许 | **须随包提供许可副本 + 保留署名 + 标注改动**（Apache §4） |

- ✅ **本仓库不含任何 NonCommercial（NC）内容，也没有 ShareAlike（SA）改编内容**
  —— 可以开源，也可以商用。
- ⚠️ **不是"全仓 MIT"**：68 个本项目原创部分为 MIT；20 个 GitHub 技能中
  **19 个 MIT + 1 个 Apache-2.0**（`markdown-mermaid-writing`，
  署名 Clayton Young / Superior Byte Works, LLC）。
  Apache-2.0 同样允许商用，义务不同：必须向接收方提供许可副本（已在
  `licenses/Apache-2.0-markdown-mermaid-writing.txt`，与 apache.org 官方原文
  **逐字一致**）、保留归属声明、标注改动。
  守卫会机械检查这三条（声明齐全 / 副本存在 / README 表述与实际一致）。
- 13 个 OpenMAIC 衍生技能（MIT，Copyright (c) 2026 THU-MAIC）同样允许商用：
  MIT 的义务是**保留版权声明与许可声明**，本仓库已在
  `licenses/OpenMAIC-MIT.txt` 提供逐字节一致的副本，并在
  `THIRD-PARTY-NOTICES.md` §3 登记署名与改动说明（只抽方法论内核、
  未复制绑定运行时的原文）。
- 50 个教学技能的主题与命名参考了 `education-agent-skills`（CC BY-SA 4.0），
  但**本项目未复制其任何文件内容**：正文为独立创作（撰写依据为公开发表的
  教育研究文献），并通过了与上游原文的**机械相似度核验**
  （`scripts/verify_rewrite.py`：8-gram Jaccard < 0.10、长行重合 < 5%）。
  上游许可全文副本保留在 `licenses/` **仅供追溯**。
  **若认为某一技能的命名或主题选择仍构成其表达，欢迎提 issue ——
  我们会在保留署名与链接的前提下调整。**
- 本项目曾包含 3 个 **CC BY-NC 4.0**（仅限非商业）技能
  （`academic-paper` / `academic-paper-reviewer` / `deep-research`）。
  NonCommercial 会传染到整个分发物 —— 它们在包里，整个仓库就不能商用。
  这 3 个已移出到 `skills-archive/`（**不随本仓库分发**）。
  论文线由仓库内的 MIT 技能（9 个 K-Dense + 3 个原创）承担，矩阵中如实标为「已覆盖」。
- 完整归属、86 技能清单、署名与致谢见
  [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md)；
  许可副本在 `licenses/`，声明见 [`NOTICE.md`](NOTICE.md)。
- 所有第三方技能均**保留原始版权与许可**，不因本仓库的许可而改变。

### 出包（可商用分发件）

```bash
python scripts\package_release.py --build
# → dist/junior-faculty-agent-1.0.0.zip（含 MANIFEST.json 与校验和）
```

出包脚本会**断言**分发包里不存在 NC 技能目录、不存在 NC 许可副本、
不存在 `skills-archive/` 路径；任何一条不满足即中止。
`--verify <zip>` 可对已有分发包重新做一遍完整校验。

### 分档出包（teaching / research / full）

```bash
python scripts\package_release.py --build --profile teaching
# → dist/junior-faculty-agent-1.0.0-teaching.zip
python scripts\package_release.py --build --profile research
# → dist/junior-faculty-agent-1.0.0-research.zip
```

| 档位 | 能力域 | 技能数 | 许可副本 | 体积 |
|---|---|---|---|---|
| `full` | 全部（A–F）+ 仓库机制类 | 86 | 4 份 | ≈2.2 MB |
| `teaching` | A 教学准备 / B 教学实施 / C 考核评价 / D 学生支持 / F 教研发展 | 62 | 4 份 | ≈0.85 MB |
| `research` | E 科研全流程 | 24 | 1 份（仅 `MIT-K-Dense.txt`） | ≈1.6 MB |

**包内技能集合不是手工枚举的**，而是「能力矩阵的能力域 → 已装技能」机械推导：

```
teaching ∪ research == full − {skill-scan}
```

`skill-scan` 是**仓库自身的季度巡检机制**，不是师生素能力，因此只在完整包里。

- 推导器 `scripts/profile_map.py` 是**唯一实现**，出包器与守卫共用 ——
  两套推导必然漂移，而漂移是静默的（包看起来正常，实际与仓库宣称不符）。
- 档位数据 `references/profiles.json`（档案 → 能力域）是**受控数据**不是代码。
- 推导不自洽（已装技能无能力格归属 / 能力域没人认领 / 三档并集不等于
  full 减仓库机制类）⇒ **中止出包**，绝不打来路不明的包。
- `licenses/` 按**包内实际技能**动态决定：research 包里没有 Apache-2.0 技能，
  就不带 Apache 副本；反之包内有技能却缺对应副本，即再分发义务未履行
  （Apache §4(a) 要求提供副本、MIT 要求保留版权与许可声明）⇒ 同样中止。
- 每个包的 `MANIFEST.json` 记录 `profile` / `skills_included` / `skills_excluded` /
  `license_copies` 与逐文件 sha256；`--verify <zip>` 可独立复验。

> 📌 **本 README 描述的是完整仓库，不是某个分档包。**
> 分档包保留**完整 README 与完整归属清单**（署名义务不因裁剪而消失），
> 只筛 `skills/` 与 `licenses/`；**该包实际含哪些技能，以其 `MANIFEST.json` 为准**。

## 已知限制

1. **GitHub API 限流**：未认证 60 req/h。脚本有 12 小时磁盘缓存（`.cache/`）；
   建议在环境变量里设 `GITHUB_TOKEN`，限额升到 5000 req/h。
2. **关键词搜索慢**：20 组关键词走 search API，耗时长且吃限额。
   cron 默认用 `--scan --no-search`（只比 3 个主源），快且稳。
3. **领域方法库技能被自动排除**：scikit-learn / torchdrug / scanpy 等工具封装
   不算教师基本能力，扫描时自动过滤（计数见 `domain_library_skipped`）。
   若使用者是某学科教师，可单独手动安装。
4. **3 个能力格是真空缺口**：A6 教学工作量折算、E10 学术简历、F5 AI 素养教学
   （上游有 7 个候选技能但一个都没装）。已在矩阵中如实标注为「缺口」。
5. **矩阵里 `◐` 标记的技能不随仓库分发**（`nature-*`、`researchwrite`、
   `empirical-lint` 等属于本机全局库 / 插件 / 其他 Agent）。克隆本仓库后，
   依赖这些技能的格子会退化为「部分覆盖」。
   **论文线与幻灯片线不在此列** —— 两者都已随仓库分发
   （论文线 9 个 K-Dense MIT + 3 个原创；幻灯片线 `teaching-slide-designer`
   + `teaching-slide-builder` + `paper-to-talk-designer` + `openmaic-courseware`，
   自带纯标准库 PPTX 生成器）。
6. **上游自带的悬空交叉引用**（K-Dense 保留技能的两类）：
   - `experimental-design`、`uncertainty-and-units`、`scientific-brainstorming`
     在正文里提到同级技能 `statistical-power`，但该技能**不在该上游仓库已安装的
     技能中**（已逐条核实）。命中时按「功效/样本量计算本仓库不含」
     处理并标「待计算」。
   - `markdown-mermaid-writing`、`scientific-brainstorming` 在正文里提到
     `scientific-writing` / `literature-review` —— 这两个已于 2026-10-22
     **回装本仓库**（论文线随包分发）。命中时直接用即可。
   为保持上游内容原样（见 `NOTICE.md`），本仓库**未修改**这些文件正文，
   改为在本项目自己的文档里改用真实存在的技能。
   （本项目自己编写的 88 个技能**不含**悬空引用 ——
   `scripts/verify_rewrite.py` 的**全仓交叉引用校验**对 `skills/` 下每一个技能
   逐条机械校验，外部技能须登记在 `references/external-skills.json`。）
7. **`skills-archive/` 是本机自用副本，不随分发**：里面是 3 个 CC BY-NC 4.0
   技能（`academic-paper` 12-agent 论文管线 / `academic-paper-reviewer` 多视角审稿面板 /
   `deep-research` 深度研究）。为保住"整体可商用"，它们被移出 `skills/`。
   本机若想继续用，把这三个目录**复制**回 `skills/` 即可（详见该目录下的 README）；
   但复制后本机这份工作副本就不可商用了，**对外发布的版本不受影响**。
8. **移出 NC 技能后的能力折损**：原 `academic-paper` 的 12-agent 论文管线
   （含 revision 模式、双语摘要、引用核查等 12 种模式）**没有完整迁入本仓库**。
   本仓库承接的是论文线的**主干能力**（9 个 K-Dense MIT + 3 个原创：
   引用核验、文献综述、论文写作、投稿模板、同行评议、投稿前体检），
   但**没有"12 种模式"的完整编排**，也没有 ADW 那套 revision 往返流程。
   这是已知的能力折损，已如实记录。
9. **`markdown-mermaid-writing` 的许可与上游不一致（上游的缺口，本仓库已补）**：
   该技能 frontmatter 声明 **Apache-2.0**（署名 Clayton Young /
   Superior Byte Works, LLC），但上游仓库只随仓库根目录提供了 MIT 全文、
   未随该技能提供 Apache-2.0 许可全文，也无 NOTICE 文件。
   本仓库已按 Apache-2.0 §4(a) 补齐副本（`licenses/`）并在 NOTICES 登记署名。
   ⚠️ **不得把它改标为 MIT** —— 那会构成许可失实。
10. **分档包随能力矩阵变化，且已发出的包不会自动更新**：
    teaching / research 两个分档的技能集合由能力矩阵的能力域**机械推导**，
    不是固定清单 —— 矩阵一改，分档内容跟着变；而包是静态文件，
    **已发出的分档包不会自动更新**（其 `MANIFEST.json` 记录了当时的清单与逐文件校验和）。
    分档包里的 README 与归属清单**仍是完整仓库的**（署名义务不因裁剪而消失），
    该包实际含哪些技能，以其 `MANIFEST.json` 的 `skills_included` 为准。
