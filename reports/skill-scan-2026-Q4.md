# 技能巡检报告 · 2026-Q4（建库首轮）

- **执行时间**：2026-10-21
- **执行 Agent**：junior-faculty-agent
- **触发方式**：建库时手工执行（非 cron 触发）
- **cron 任务**：`67c34763-7b58-4983-b6d6-2a4ef3e5657c`（每 1/4/7/10 月 1 日 10:00）
  —— 注：本报告执行时该 cron 的 id 为 `c3668180-6dfc-4dac-b59e-23a7b0019c1d`，
  2026-10-22 因该任务处于 **paused**（零运行、无 nextRun，自学习实际不会触发）
  而以同参数重建，新 id 如上。详见 `crons/quarterly-skill-scan.md`。

> ⚠️ **本报告是 2026-10-21 建库当时的快照，后续仓库状态已变。**
> 报告正文里「70 个外部技能」「教学技能为 CC BY-SA 4.0 改编版」等描述
> **描述的是当时的状态**，不是当前状态。截至 2026-10-22：
> - 50 个教学技能已全部 **clean-room 重写为本项目原创的 MIT 技能**
>   （上游正文未复制、`skill_id` 已移除，通过 `scripts/verify_rewrite.py` 的
>   机械相似度核验）。
> - 3 个 NC 技能已按 **S9** 移入 `skills-archive/`（不随分发）。
> - **2026-10-22 变更（其一，论文线移出）**：K-Dense 的 **9 个论文类技能**
>   曾以「能力分工」为由移出，拟交给本机全局技能 `academic-deep-writer`（ADW）。
> - **2026-10-22 变更（其二，论文线回装，当日）**：上述 9 个技能**已装回**。
>   理由：ADW **不随本仓库分发**，克隆后论文类需求会无人接手，
>   与"整体可商用、可交付"的定位直接冲突 —— **能力必须随分发物走**。
>   同时另行编写 3 个本项目原创技能吸收其核心判据：
>   `citation-audit` / `assertive-writing` / `submission-readiness`。
>   仓库现为 **78 个技能 = 58 原创 + 20 个 K-Dense（19 MIT + 1 Apache-2.0）**；
>   能力矩阵 E2 / E4 / E5 / E9 恢复「已覆盖」，全局完全覆盖 **34/41**。
> - **2026-10-22 变更（其三，许可账目）**：发现 `markdown-mermaid-writing`
>   的 frontmatter 声明 **Apache-2.0**（署名 Superior Byte Works, LLC），
>   而 `licenses/` 只有一份 MIT 副本、README 却写"全仓 MIT" —— 两处都错。
>   已补齐 Apache-2.0 规范全文副本（与 apache.org 官方原文逐字一致）、
>   在 `THIRD-PARTY-NOTICES.md` 登记署名，并把守卫加了一组「许可台账完整性」检查。
> - **2026-10-22 变更（其四，OpenMAIC 方法论内核适配）**：把本机 OpenMAIC
>   （MIT，Copyright (c) 2026 THU-MAIC）的**方法论内核**适配进教学技能线 ——
>   新建 3 个技能（`authentic-context-course-designer` / `feynman-diagnostic-cycle` /
>   `vocational-task-course`），并给 8 个既有技能增补章节
>   （UbD 三阶段与 GRASPS/WHERETO、概念脊柱与升阶操作符与假螺旋检查、
>   诊断—支持—撤架—复核闭环、撤架判定与最小学习记录、澄清轮次与确认门、
>   课程目标—毕业要求—核心素养映射）。
>   **只抽方法论内核重写，未复制绑定 OpenMAIC 运行时的原文**（那 22 个 SKILL.md
>   正文写死 `create_stage` 等运行时工具，整份复制进来就是悬空引用）。
>   仓库现为 **81 个技能 = 61 原创 + 20 个 K-Dense**；
>   能力矩阵完全覆盖仍为 **34/41**（补进的都是已覆盖格里的更细颗粒能力）。
>   归属与署名见 `THIRD-PARTY-NOTICES.md` §3，许可副本 `licenses/OpenMAIC-MIT.txt`
>   （与上游逐字节一致）。
> - **2026-10-22 变更（其五，第 5 版）**：**幻灯片线自研回仓 + P1/P2 开工**。
>   ① 幻灯片线原本挂在**不随包分发**的外部技能上（运行时内置的 `pptx`
>   与本机全局的 `nature-paper2ppt`）—— 与论文线外包给 ADW 是**同一个坑**。
>   现自研：`teaching-slide-designer`（含纯标准库 PPTX 生成器
>   `build_pptx.py` 与教学规范审查器 `slide_spec_lint.py`）+
>   `paper-to-talk-designer`（论文→汇报叙事）。外部技能表移除那两条登记，
>   E7 的 `◐nature-paper2ppt` 改标 `●`，**覆盖计数不变**。
>   ② P1：新建 `openmaic-courseware` —— OpenMAIC 课件产出链接入
>   （纯标准库 HTTP 客户端 + API 契约速查 + **容器编排增量**；
>   OpenMAIC 本体仍不随包分发）。
>   ③ P2：新建 `teacher-style-profile`（名师风格画像与迁移）+
>   `personal-course-pattern-builder`（个人做课记录→专属工作法）。
>   仓库现为 **86 个技能 = 66 原创 + 20 个 K-Dense**；
>   能力矩阵完全覆盖仍为 **34/41**（补进的都是已覆盖格里的更细颗粒能力）。
>   新增红线 **S12 能力必须随交付物走**，并加了「幻灯片能力自足」一组守卫
>   —— 其中最硬的一条是**直接跑自研脚本的 `--selftest`**，
>   证明的是「克隆下来就能用」，而不只是「文件在」。
> - **2026-10-22 变更（其六，第 6 版，分档出包）**：`package_release.py` 增加
>   `--profile teaching|research|full`，出**分档分发包**。
>   ① 分档的技能集合**不是手工枚举**的，而是由**能力矩阵的能力域**机械推导
>   （档位数据 `references/profiles.json`，推导器 `scripts/profile_map.py`，
>   出包器与守卫**共用同一份实现** —— 两套推导必然漂移，漂移是静默的）。
>   ② 恒等式 **`teaching ∪ research == full − {skill-scan}`**
>   （`skill-scan` 是仓库自身的季度巡检机制，不是师生素能力）。
>   `teaching` 62 个 / `research` 24 个 / `full` 86 个；
>   两档交集只有 `teaching-slide-designer`（教学幻灯片 + 学术汇报两用）。
>   ③ 顺带把 **6 个此前未入任何能力格的新技能**补进矩阵
>   （A1 ×2 / A2 ×1 / B7 ×1 / D5 ×1 / F2 ×2），**覆盖计数不变（34/41）**。
>   ④ `licenses/` 按**包内实际技能**动态决定：research 包里没有 Apache-2.0 技能
>   就不带 Apache 副本（research 包只有 `MIT-K-Dense.txt` 一份）；
>   反之包内有技能却缺副本 = 再分发义务未履行 ⇒ **中止出包**。
>   ⑤ 新增守卫 8 项（每个已装技能都有归属 / 三档并集恒等式 / 能力域被认领 /
>   每档非空且不越界 / 每档许可副本齐备 …），
>   守卫检查数 **78 → 86**；变异测试新增 6 例（35 + 3 + 3），
>   其中 **3 例直接针对出包器** —— 证明它**会拒绝**出包，而不只是会出包。
> - **2026-10-23 变更（其七，第 7 版，大纲先行层 + 版式原型表）**：
>   ① **大纲先行层**（新增 `demo/outline.py` + `demo/spec/outline.example.json`）：
>      教案与课件改为**从同一份大纲派生**，不再各自写出来 ——
>      "改了教案忘了改课件"从**检查问题**变成**结构问题**。
>      判据查的是「派生结果 == 重新派生的结果」（可证伪），
>      不是「两份文件碰巧一样」（靠不住：碰巧一样时可能已经各改各的）。
>      在线模式的模型调用由 3 次降到 2 次（课件与讲稿不再各问模型一次）。
>      守卫新增 3 项（文件齐全 / 唯一事实源 / 离线 Demo 真的走大纲层），
>      变异测试新增 3 例（手改教案示例 / 改派生器 / Demo 绕过大纲层）。
>   ② **版式原型表**（新增 `skills/teaching-slide-designer/scripts/slide_layouts.py`）：
>      七种版式的几何与**文字高度表**从渲染代码里抽成**数据**，
>      渲染器与判据**共用同一份** ⇒ 判据不会与渲染器漂移。
>      配套新增 **L15 几何溢出判据**：PowerPoint 文本框带 `normAutofit`，
>      文字超出框高不会露出来，而是**自动缩小字号** —— 静默失效，
>      字数规则（L03/L04）抓不到（21 字封面标题字数合规但放不下）。
>      产物**逐字节不变**（12 页 slide XML 的 sha256 前后一致）。
>   守卫检查数 **90 → 94**；变异测试 **42 → 46**（40 + 3 + 3）；
>   Demo 自检 **24 → 40**；分发包 **493 → 497** 个文件。
> - **2026-10-23 变更（其八，第 8 版：UbD 骨架 / 讲义派生 / 增量重生成 / 模型路由）**：
>   ① **UbD 骨架进大纲**（大纲新增 `ubd` 块）：
>      持久理解 1–3 条（写法固定为「学生能理解 …… 并在 …… 情境中用它」）、
>      基本问题 3–5 个（不允许写成能背定义回答的题）、
>      GRASPS 表现性任务六要素（P 与 S 必须实）、
>      WHERETO 七项覆盖（每项写明落在哪个环节，E·Experience 与 R·Rethink 最常漏）。
>      判据 **OL-P15–OL-P18**，教案里也多了「2.1 设计骨架（UbD）」一节。
>      写法要求落在 `skills/teaching-file-builder`「UbD 骨架」一节（内核适配自
>      `skills/backwards-design-unit-planner`）—— 提示词从那里摘，**不另写一套规则**。
>   ② **讲义改为纯派生**（新增 `demo/spec/handout.example.json`）：
>      讲稿只有一份（写在大纲的 `slides[].notes` 里），讲义从**课件规格**导出 ⇒
>      「讲义讲稿 ≠ 课件讲稿」在结构上不可能发生。
>      判据 **HD-P01–HD-P04**（含逐字比对）。
>   ③ **增量重生成**（`outline.py --regen-page`）：改一页只重跑一页，
>      在线模式只调**一次**模型；判据是**逐页指纹比对** ——
>      只重跑一页 ⇒ 其余页必须一字未动。为此每页必须有**稳定 id**（OL-P19）。
>   ④ **模型按用途路由**（`llm.py`）：`plan` / `slides` / `handout` / `lint` 四档，
>      各自可用 `JFA_LLM_MODEL_*` 指定，未设则回退 `JFA_LLM_MODEL`。
>   ⑤ 守卫新增 4 项（讲义产出 / 变异测试覆盖 UbD 与讲义规则码 /
>      增量重生成只动一页 / 模型四档用途齐全），并把「封面唯一」的判据
>      从「封面必须是 title」改成「**全稿 title 版式最多一个**」——
>      续讲课的分节页（section）本来就承担「这一讲的开场」角色。
>   守卫检查数 **94 → 99**；变异测试 **46 → 51**（45 + 3 + 3）；
>   Demo 自检 **40 → 57**；分发包 **497 → 501** 个文件。
>   🔴 同一轮还修了两个**文档/环境撒谎**：`verify_rewrite` 的检查数取决于
>      上游原文在不在（716 有上游 / 666 无上游），README 原先写 716 ⇒
>      新增守卫按「无上游口径」机械核对；以及中文 Windows 的 GBK 会让守卫
>      在自己母语环境下不绿（子进程打 `✅` 崩了，父进程只看到「退出码 1」）。
> - **2026-10-24 变更（其九，第 9 版：三条变异自己没生效）**：
>   第 8 版把五项能力做完了，但那一轮结束时写的「51 项全绿」**并不成立** ——
>   变异测试**自己**抓出了三条变异没生效。这一版记的是那次返工。
>   ① **变异无效（变异测试里最贵的一种浪费）**：`mutate_readme_selfcount_numerator`
>      把 README 的 `verify_repo: N/N` 改成 `99/N`，而当时的实际值**正好是 99** ⇒
>      替换后文本没变 ⇒ 变异被判「无效」⇒ **这一项其实什么都没验**。
>      改法：分子写死成**不可能等于实际值**的 `999`。
>   ② **局部替换冒充全局替换**：`mutate_selftest_drop_ubd_case` 只替换了
>      `selftest.py` 里 `, "OL-P15"` 的**第一处**，而该串出现两处
>      （缺 UbD 骨架 / 持久理解写成知识点）⇒ 守卫的文本检查照样找得到 ⇒ 守卫没红。
>      改法：**所有出现处**一起替换；守卫的匹配也收窄到 `, "OL-P15"`
>      （**期望码的位置**）而不是裸串 —— 裸串会出现在注释里，也会出现在别的用例里，
>      匹配太宽 = 守卫太松。
>   ③ **变异的作用域小于被测判据的输入空间**：`mutate_regen_leaks_to_sibling`
>      把泄漏写在「内容页分支 + 同环节的下一页」上，而守卫当时挑中的目标是**封面页**
>      （deck 分支、没有下一页）⇒ 泄漏**从未发生** ⇒ 守卫绿着，
>      而「只重跑一页」这条承诺早就破了。
>      两处同时改：泄漏改成**与重跑哪一页无关**（总是改掉另一页）；
>      守卫改成**每一页都试**（原来只试 `sorted(before)[0]`）。
>      ⇒ **只试一个样本的判据 = 押注那个样本恰好能触发缺陷。**
>   ④ 终态：守卫检查数仍 **99**（**没有新增检查，是既有检查变严**），
>      变异测试仍 **51**（45 + 3 + 3），Demo 自检仍 **57**，分发包仍 **501** 个文件。
>   🔴 这一版的教训比它的改动更重要：**「变异测试跑完了」不等于「变异都生效了」。**
>      变异脚本自己抛异常时，测试框架把它记成「这一项没验成」并继续跑其余的 ——
>      这是对的（一次手滑不该毁掉整轮），但**必须把「没验成」记进终态数字**，
>      否则「51/51」会掩盖「其中 3 项从未真正被验过」。
> - **2026-10-24 变更（其十，第 10 版：GitHub 开源化）**：
>   ① **开源件入库**：`.github/workflows/ci.yml`（CI）+ `release.yml`（打 tag 即发布）、
>      Issue/PR 模板、`CONTRIBUTING.md` / `CODE_OF_CONDUCT.md` / `SECURITY.md` /
>      `CHANGELOG.md`、`.gitattributes`（文本一律 LF，优先于 `core.autocrlf`）、
>      `.editorconfig`。
>   ② **CI 不引入新判据**，只把仓库里**已有的**机器判据接上去：
>      Linux + Windows × Python 3.9 / 3.13。
>      🔴 **Windows 必须留在矩阵里** —— 中文控制台默认 GBK，子进程打 `✅` 会当场崩、
>         父进程只看到「退出码 1」，这类问题**只在 Windows 暴露**；
>         3.9 是兼容下限，少了它就没人证明下限还成立。
>   ③ **GitHub 源码包**（新增 `scripts/github_release.py`）：产
>      `dist/junior-faculty-agent-1.0.0-source.zip`（整仓 + `MANIFEST.json`，
>      顶层目录带版本号）与 `dist/RELEASE_NOTES.md`；
>      独立校验三件事：NC 断言、必备件齐全、**克隆即用**（解压到副本里真跑一遍）。
>      仓库名/描述/topics 的**唯一出处**是 `references/github-release.json` ——
>      填 `owner` 后重跑一次出包脚本即可，不必改别处。
>   ④ **社区件进分发包**：CHANGELOG / CONTRIBUTING / SECURITY / CODE_OF_CONDUCT /
>      `.gitattributes` / `.editorconfig` 与 `.github/` 一并进三档包 ——
>      一个分发物应该自带"这是什么、怎么改、怎么报问题、许可是什么"。
>   ⑤ **新增 5 条守卫**（开源件齐全 / CI 真的跑判据 / CI 覆盖 Windows 与 3.9 /
>      发布配置完整 / CHANGELOG 覆盖当前版本）+ **对应的 4 条变异**。
>      🔴 「开源性」是最容易悄悄烂掉的东西：CI 文件还在但里面跑的命令早就改了，
>         社区文件还在但内容指向已消失的路径 —— 这些**不会让任何既有检查变红**。
>      ⇒ 所以必须有守卫盯着它们，也必须有变异证明这些守卫会红。
>   守卫检查数 **99 → 104**；变异测试 **51 → 55**（49 + 3 + 3）；
>   Demo 自检仍 **57**；分发包 **501 → 515** 个文件。
> - 本报告保留原样是为了记录**当时的判断与依据**（不做事后修饰）。
>   当前仓库的实际状态以 `README.md` 与 `THIRD-PARTY-NOTICES.md` 为准，
>   并由 `scripts/verify_repo.py` 机械核对。

---

## 一、本次扫描概况

| 项 | 值 |
|---|---|
| 扫描方式 | GitHub API（仓库内容比对 + 关键词搜索 + SKILL.md 描述嗅探） |
| 主源仓库 | K-Dense-AI/scientific-agent-skills、GarethManning/education-agent-skills、Imbad0202/academic-research-skills |
| 扫描是否完整 | **否** —— 见下节 |
| 网络请求 | 27 / 90（预算内） |
| 自动排除的领域方法库技能 | 52 |
| 候选总数 | 105（其中大部分是嗅探未完成的库技能，见下节） |

### ⚠️ 扫描不完整的原因（如实记录）

本机 GitHub **未认证 API 配额（60 req/h/IP）在扫描过程中耗尽**，
`education-agent-skills` 与 `academic-research-skills` 两个主源在列举阶段失败：

```
GarethManning/education-agent-skills: 403 rate limit exhausted (no Retry-After)
Imbad0202/academic-research-skills: 403 rate limit exhausted (no Retry-After)
```

脚本已按设计**如实标记**：`scan_complete: false`，退出码 **2**。

**这不是 bug，是刻意设计的行为**——拉取失败绝不静默变成「本季度无新技能」。
建库所需的三个主源技能已通过 git 稀疏检出与 GitHub API 直接取回，
**不受本次扫描配额影响**（安装完整性见第五节）。

**改进项**：设置 `GITHUB_TOKEN` 可把限额从 60 req/h 提到 5000 req/h，
下次巡检即可完整覆盖三个主源。已写入 cron 的步骤 0。

### 关于「105 个候选」的重要提醒

这 105 个**不全是真候选**。描述嗅探因配额耗尽而未完成，
所以 K-Dense 仓库里的一批库型技能（`pymc`、`pymatgen`、`pydeseq2`、`pyhealth` 等）
没有被自动识别为「领域方法库」而留在了候选列表里。

**下季度处理方式**：不能批量安装，必须逐个打开 SKILL.md 确认
它解决的是教学/科研任务，而不是某个科学计算包的调用封装。
这条约束已写入 cron 的步骤 1。

---

## 二、新学会的技能

建库阶段从 GitHub 主源学习并适配完成（**70 个外部技能**，全部为可商用许可）：

| 来源 | 数量 | 许可 | 适配动作 |
|---|---|---|---|
| GarethManning/education-agent-skills | 50 | CC BY-SA 4.0 | 全部追加中国高校语境适配块；抽查 K-12 学段残留，追加 `references/he-context-adapter.md` 映射表引用 |
| K-Dense-AI/scientific-agent-skills | 20 | MIT | 无 K-12 语境问题，未追加适配块；`research-grants` 与 `peer-review` 于首轮扫描中补装 |

> **2026-10-22 补充**：建库时还装了 3 个 `Imbad0202/academic-research-skills` 的技能
> （`academic-paper` / `academic-paper-reviewer` / `deep-research`）。
> 其许可是 **CC BY-NC 4.0（仅限非商业）**，NonCommercial 会传染到整个分发物，
> 使本项目整体不可商用。为保住"整体可商用"，这 3 个技能已移出到
> `skills-archive/`（不随本仓库分发），能力矩阵相应格位改用 MIT 等效技能。
> 详见 `skills-archive/README.md` 与 `LICENSE`。

### 私有编写（5 个）

补的是 GitHub 上确实没有、或缺口明确的部分：

| 技能 | 补的缺口 |
|---|---|
| `grant-proposal-writer` | 上游 `research-grants` 只覆盖 NSF/NIH/DOE/DARPA/台湾 NSTC，**缺中国基金的形式要件**（立项依据写法、创新点对应缺口、经费预算表、年度计划） |
| `exam-question-bank` | 上游无命题技能；本技能定义「目标—题型—认知层次映射表 → 难度分布 → 逐题评分细则 → A/B 等价卷 → 题库覆盖矩阵」 |
| `teaching-file-builder` | 定义大纲/教案/课件脚本/讲义/板书/思政融入点/支撑矩阵七类文件的必备结构与统一自检表 |
| `skill-scan` | 季度巡检流程定义（含三条踩坑纪律） |
| `he-context-adapter` | K-12 → 中国高校的速查映射 + 判断规则 |

---

## 三、评估后拒绝的技能

见 `references/rejected-skills.md` 的首轮基线表。整体拒绝的来源：

| 来源 | 理由类别 | 说明 |
|---|---|---|
| sickn33/agentic-awesome-skills（1600+ 条目） | S1/S2/S3 | 主体是 web 安全、营销、DevOps、AWS、数据库。其 `teach` 技能面向学习者自学，非教师备课；其教育类已被 GarethManning 仓库以更完整证据覆盖 |
| ComposioHQ/awesome-claude-skills | — | 索引仓库，内容已通过三个主源覆盖 |
| VoltAgent/awesome-agent-skills | — | 同为索引 |
| academic-research-skills 的 `academic-pipeline` / `sr-screener` | S8 | 本机已有 `academic-deep-writer` 全流程管线（含 citation-check / rebuttal-audit 模式）与 `nature-literature-pipeline`，职责重叠无增量 |
| ECC / graphify / archify / hallmark | S1/S2/S5 | 通用 agent 工程与设计系统 |

### 本轮新增识别出的库型技能（52 个，自动排除）

`is_domain_library()` 前缀表 + 描述嗅探识别，包括：
scikit-* / torch* / pymc / pymatgen / pydeseq2 / pyhealth / scanpy / rdkit /
deepchem / zarr / statsmodels / sympy / matplotlib / seaborn / qiskit / qutip 等。

**判据**：技能名指向一个**具体技术栈/科学计算包**，而不是一门教学或科研的**方法**。
科研方法类（scientific-writing / literature-review / experimental-design /
statistical-power / citation-management / research-grants）**全部保留**。

> 例外：若使用者本人是某学科教师（如生物信息、量子计算），
> 可单独评估安装对应库技能——本 Agent 默认不为「会用某个包」设立能力项。

---

## 四、待人工确认的技能

| 技能 | 来源 | 待确认原因 | 建议 |
|---|---|---|---|
| `book-to-skill` | virgiliojr94/book-to-skill | 把技术书 PDF 转成技能，可用于自研教材，但当前不是教学交付物缺口 | 下季度复查 |
| `edu-physics-solve` | 本机全局 skills | 物理题解网页生成器，适合物理教师做课堂演示页，与现有教学技能不重叠 | 若使用者是物理教师，复制进本 Agent 的 `skills/` |
| `pptx-posters` | K-Dense | 可编辑 PPT 海报生成，本机已有 `latex-posters` 与全局 `pptx` 技能 | 暂不装；需求明确时再装 |

---

## 五、能力矩阵变化

| 能力格 | 变化 |
|---|---|
| A4 课程思政融入 | **缺口 → 已覆盖**（`he-context-adapter` + `teaching-file-builder`） |
| C6 试题命题与试卷结构 | **缺口 → 已覆盖**（`exam-question-bank`） |
| E8 项目申报书 | **缺口 → 已覆盖**（`grant-proposal-writer` + `research-grants`） |
| A5 教材与参考书遴选 | 缺口 → **部分覆盖**（有"不得编造 ISBN"的规则，无检索工具） |
| E9 教学研究论文 | 缺口 → **部分覆盖**（有 academic-paper 模式，缺教研选题方法） |
| 其余 42 格 | 维持已覆盖 / 部分覆盖状态 |

### 仍是缺口（下一季度的输入）

| 能力格 | 说明 |
|---|---|
| A6 教学工作量与课时折算 | 无对应技能，需新建或找 GitHub 方案 |
| E9 教学研究论文 | 缺"把教学改进转为可投稿研究"的选题与设计方法 |
| E10 学术简历与个人主页 | 无对应技能 |

---

## 六、下季度重点关注方向

1. **配额问题**：配 `GITHUB_TOKEN`；无 token 时优先用 `--scan --no-search`。
2. **补 A6 / E9 / E10 三个缺口**，重点搜：
   - "teaching workload calculation" / "course credit hours"
   - "pedagogical research" / "teaching effectiveness study"
   - "academic CV" / "faculty homepage"
3. **盯 education-agent-skills 的新增域**：该仓库 20 个域中，
   `original-frameworks`、`professional-learning`、`wellbeing-motivation-agency`
   三个域我只精选了高价值条目，值得复查是否有遗漏的高价值技能。
4. **复查被拒清单**：`references/rejected-skills.md` 里的条目本季度不重复评估，
   但若生态发生变化（如某仓库转向教学用途），下季度可重新评估。
5. **验证 skill-scan 脚本自身**：改了判据或过滤规则后，
   必须重跑历史扫描并比对结果——**判读器自己也是被测对象**。

---

## 七、自检

```
python scripts\skill_scan.py --selftest
selftest: 20/20 checks passed

python scripts\verify_repo.py
verify_repo: 104/104 checks passed

python scripts\verify_rewrite.py
verify_rewrite: 666/666 checks passed
（无上游原文时的口径；带上游原文会多 50 项相似度核对 ⇒ 716）

python scripts\test_verify_repo.py
全部 55 项变异均被守卫在预期检查项上抓到。

python scripts\github_release.py --build
GitHub 源码包校验通过（515 个文件 + MANIFEST.json；克隆即用已通过）。
```

自检项：技能数量下限、frontmatter 完整性（name/description）、
**全量**教学技能的语境适配覆盖、5 个私有技能存在性、
关键引用文件存在性、agent.md 关键段落存在性。

> 📌 本报告正文是 **2026-10-21 建库当时的快照**，其中的数字（如「70 个外部技能」
> 「教学技能为 CC BY-SA 4.0 改编版」「selftest 14/14」「42 格」）
> **描述的是当时的状态**。当前状态见文首的变更记录与 `README.md`。
