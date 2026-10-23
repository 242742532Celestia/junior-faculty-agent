# 已排除技能记录

> 每季度巡检**先读本文件**，避免重复评估同一批技能。
> 追加格式：`技能名 | 来源 | 排除理由 | 记录日期`

排除理由使用巡检判据中的标准类别（见 `faculty-capability-matrix.md` 第二节）：

- `S1` 与教学科研无关
- `S2` 纯软件开发/运维
- `S3` 营销/增长/SEO
- `S4` 通用商业财务
- `S5` 通用 LLM 工程（提示词自动化、agent 编排、模型部署）
- `S6` 专业执业（医/法/军事）且非本学科教师
- `S7` 教学科研无关的通用数据分析
- `S8` 已被本地现有技能覆盖，无增量
- `S9` **许可不可商用（CC BY-NC / NonCommercial）** —— 与"是否属于教师职责"无关，
  纯粹是许可红线：本项目对外声明整体可商用，装入 NC 内容会破坏这一承诺
- `S10` **许可传染，与本仓库「自有部分为 MIT」声明冲突（CC BY-SA 等 ShareAlike）**
  —— 同样与"是否属于教师职责"无关。2026-10-22 起，仓库里的 50 个教学技能已全部
  clean-room 重写为本项目原创的 MIT 技能，`LICENSE` 声明的**自有原创部分**为 MIT。
  此时直接装入一个 SA 改编版，会让整仓带上 ShareAlike 义务，与声明冲突。
- `S11` **许可台账一致性**（2026-10-22 起；原「能力分工移出：论文类由 ADW 承担」
  已作废——论文线当日回仓，见下方「移出 → 回装」记录）
  —— 本仓库现有 1 个 **Apache-2.0** 技能（`markdown-mermaid-writing`，
  署名 Superior Byte Works, LLC）。它与自有 MIT 部分一样**允许商用**，但义务不同：
  必须随包提供许可副本、保留署名与变更说明。
  ① 不得把它改标为 MIT；② `licenses/Apache-2.0-markdown-mermaid-writing.txt`
  必须随包分发；③ **新装技能若带非 MIT 许可，必须同时补齐 `licenses/` 副本
  并在 `THIRD-PARTY-NOTICES.md` 登记**，否则 `scripts/verify_repo.py` 会报红。

> 🔴 **S9 与 S10 是硬红线，不是偏好。** 判据不是"这个技能有没有用"，
> 而是"它的 LICENSE 原文允许怎么分发"。装之前必须打开 LICENSE 文件读原文，
> 别只看仓库标签。装完后 `scripts/verify_repo.py` 的「skills/ 不含任何
> NonCommercial 技能」会再机械查一遍。
>
> **SA 候选的正确处理**：不是直接装，也不是直接丢。记入本文件，理由类别 **S10**，
> 并在巡检报告的「待人工确认」段写清它能补哪个能力格。若确实有价值，
> 后续走 **clean-room 重写**流程（`references/skill-rewrite-spec.md` +
> `scripts/verify_rewrite.py`），而不是原样装入。

---

## 2026-10-21 首轮基线评估

以下为建库时的整体评估结论，非逐条排除记录。

### 评估为「属于高校教师能力范畴」并已安装

| 技能 | 来源 | 覆盖能力格 |
|---|---|---|
| backwards-design-unit-planner 等 50 项教学技能 | GarethManning/education-agent-skills | A1–A3, B1–B6, C1–C5, D1–D6, F1–F5 |
| scientific-slides / literature-review / scientific-writing / citation-management / experimental-design / statistical-analysis / scientific-critical-thinking / scholar-evaluation / hypothesis-generation / scientific-brainstorming / venue-templates / latex-posters / scientific-visualization / markdown-mermaid-writing / uncertainty-and-units / research-lookup / paper-lookup / scientific-schematics | K-Dense-AI/scientific-agent-skills | E1–E7, B7 |

> 2026-10-22 变更（其一）：建库时还装了 `academic-paper` / `academic-paper-reviewer` /
> `deep-research`（Imbad0202/academic-research-skills，CC BY-NC 4.0）。
> 因 **S9 许可红线**，这 3 个已移出到 `skills-archive/`（不随本仓库分发），
> E2 / E4 / E5 改用 MIT 等效技能覆盖。详见 `skills-archive/README.md`。
>
> 2026-10-22 变更（其二）：上表 K-Dense 一行中的 **9 个论文类技能**
> （`scientific-writing` / `venue-templates` / `scholar-evaluation` / `peer-review` /
> `literature-review` / `research-lookup` / `paper-lookup` / `citation-management` /
> `scientific-slides`）**已移出本仓库**。
> 移出原因**不是许可**（MIT 可商用），而是**能力分工**：
> 论文线统一由本机全局技能 `academic-deep-writer`（ADW 论文智能体）承担，
> 其引用核验（`cite_verify.py`）与审稿内核（`adw-review` §6）能力更强，
> 避免两套并行产生分歧。**ADW 不随本仓库分发** ⇒ E2 / E4 / E5 / E9
> 四格如实降级为「部分覆盖」。保留 11 个 K-Dense 技能承担科研**方法**侧。

### 评估为「不属于高校教师能力范畴」的整体排除

| 源/技能族 | 排除理由 | 说明 |
|---|---|---|
| sickn33/agentic-awesome-skills 绝大多数条目 | S1 / S2 / S3 | 1600+ 技能中，主体是 web 安全、营销、DevOps、AWS、数据库等。与教学科研相关的仅 `teach`（面向学习者自学，非教师备课）。其 165 项教育技能已由 GarethManning 仓库覆盖且证据更完整 |
| ComposioHQ/awesome-claude-skills 索引中多数条目 | — | 该仓库是**索引**不是技能本体，内容已通过上述三个主源覆盖 |
| VoltAgent/awesome-agent-skills | — | 同为索引 |
| ankad0202/academic-research-skills 中的 `academic-pipeline` / `sr-screener` | S8 / S9 | 本机已有 `academic-deep-writer` 全流程管线（含 citation-check / rebuttal-audit 模式）与 `nature-literature-pipeline`，覆盖相同职责，无增量；**且该上游为 CC BY-NC 4.0，非商业不可入仓** |
| ECC / graphify / archify / hallmark 等 | S1 / S2 / S5 | 通用 agent 工程与设计系统，与教学科研无关 |

### 观察但暂缓

| 技能 | 原因 |
|---|---|
| `book-to-skill` | 把技术书 PDF 转成技能。可用于教师自研教材，但当前非教学交付物缺口，暂缓；下季度复查 |
| `edu-physics-solve`（本机已有全局技能） | 已装在全局 skills 目录，非本 Agent 私有。它是**物理题解网页**生成器，适合物理教师做课堂演示页，但与教学技能体系不重叠。若使用者是物理学科教师，建议将其复制进本 Agent 的 skills/ |
| `pptx-posters` | 可编辑 PPT 海报生成。本机已有 `latex-posters` 与全局 `pptx` 技能，暂不重复装；需求明确时再装 |

### 领域方法库技能（S7 类，2026-Q4 首轮自动识别 52 个）

这些技能是**某个科学计算包的调用封装**，不是高校教师的基本能力。
判据：技能名指向一个具体技术栈/包，而不是一门教学或科研的**方法**。

**K-Dense-AI/scientific-agent-skills 中的库型技能**（部分清单）：

```
scikit-learn / scikit-bio / scikit-survival / torch / torch-geometric / torchdrug /
transformers / pymc / pymoo / pymatgen / pybamm / pycalphad / pydeseq2 / pyhealth /
pylabrobot / pydicom / polars / polars-bio / statsmodels / sympy / matplotlib / seaborn /
plotly / umap-learn / vaex / zarr-python / scanpy / scvi-tools / anndata / scvelo /
squidpy / spatialdata / rdkit / deepchem / cellprofiler / cantera / cobrapy / biopython /
qiskit / qutip / tellurium / tamarind / astropy / healpy / openmm / mdanalysis / ...
```

**理由**：教师不会因为「会调 scanpy」就多一项教学/科研职责。
这些技能只在**使用者本人是该学科研究者**时才有意义。

**例外处理**：若使用者是生物信息 / 量子计算 / 材料等方向的教师，
可在巡检时手动 `npx skills add` 或按决策 JSON 安装对应库技能。
本 Agent **默认不装**，不为其设立能力项。

> 🔴 这条排除由 `scripts/skill_scan.py` 的 `is_domain_library()` 前缀表 +
> 描述嗅探自动执行。但**配额耗尽时嗅探会跑不完**，库型技能会漏进候选列表。
> 漏进候选时**不要批量安装**——必须逐个打开 SKILL.md 确认。
> 这条约束也写进了 cron 任务的步骤 1。

---

## 2026-10-22 论文类移出 → **当日回装**（S11 能力分工条目已撤销）

**时间线**：本日上午以 S11「能力分工」为由移出 9 个论文类技能，论文线移交本机
全局技能 `academic-deep-writer`（ADW）；**同日**按新的部署决策改回 —— 论文线
**必须随本仓库分发**（ADW 不随包分发，克隆后论文类需求会无人接手，
与"整体可商用、可交付"的定位冲突）。

| 技能 | 来源 | 现状 | 许可 |
|---|---|---|---|
| `scientific-writing` | K-Dense-AI/scientific-agent-skills | ✅ 已回装 | MIT |
| `venue-templates` | K-Dense-AI/scientific-agent-skills | ✅ 已回装 | MIT |
| `scholar-evaluation` | K-Dense-AI/scientific-agent-skills | ✅ 已回装 | MIT |
| `peer-review` | K-Dense-AI/scientific-agent-skills | ✅ 已回装 | MIT |
| `literature-review` | K-Dense-AI/scientific-agent-skills | ✅ 已回装 | MIT |
| `research-lookup` | K-Dense-AI/scientific-agent-skills | ✅ 已回装 | MIT |
| `paper-lookup` | K-Dense-AI/scientific-agent-skills | ✅ 已回装 | MIT |
| `citation-management` | K-Dense-AI/scientific-agent-skills | ✅ 已回装 | MIT |
| `scientific-slides` | K-Dense-AI/scientific-agent-skills | ✅ 已回装 | MIT |

> ⚠️ **这 9 个名字已从 `scripts/skill_scan.py` 的排除名单中移除** ——
> 它们现在**已安装**，不是"已排除项"。保留在排除名单里会让巡检报告失真。
>
> ADW 仍可作为**可选增强**由用户自行搭配，但本仓库的能力矩阵与守卫
> **不再依赖它**（E2 / E4 / E5 / E9 由仓库自带技能承担，标「已覆盖」）。
>
> 📌 **能力折损已如实记录**：ADW 的引用核验与审稿内核强于被移出的九件，
> 但**表格 / 海报 / 图表规范**仍由保留的 `latex-posters`、
> `scientific-visualization`、`scientific-schematics` 兜底。

---

## 2026-10-22 OpenMAIC：22 个技能**只适配 7 个的方法论内核**，其余不复用

**来源**：本机部署的 [OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) v1.0.3
（MIT，Copyright (c) 2026 THU-MAIC）—— 多智能体互动课堂生成引擎。

| 上游技能 | 处置 | 落到本仓库哪里 |
|---|---|---|
| `k12-core-literacy-planning` | ✅ 适配方法论内核 | 新建 `authentic-context-course-designer`；并给 `he-context-adapter` 增补核心素养映射段 |
| `feynman-learning` | ✅ 适配方法论内核 | 新建 `feynman-diagnostic-cycle` |
| `vocational` | ✅ 适配方法论内核 | 新建 `vocational-task-course` |
| `understanding-by-design` | ✅ 适配方法论内核 | `backwards-design-unit-planner` 增补 UbD 三阶段 + GRASPS + WHERETO |
| `spiral-curriculum` | ✅ 适配方法论内核 | `scope-and-sequence-designer` + `learning-progression-builder` 增补概念脊柱/升阶操作符/假螺旋检查 |
| `zone-of-proximal-development` | ✅ 适配方法论内核 | `formative-assessment-loop-designer` + `error-analysis-protocol` 增补诊断—支持—撤架—复核闭环 |
| `curriculum-planner` | ✅ 适配方法论内核 | `project-brief-designer` + `agent.md` 增补澄清轮次/确认门/长上下文纪律 |
| `teacher-style-clone` | ✅ 适配方法论内核（2026-10-22 第 5 版追加） | 新建 `teacher-style-profile`（名师风格画像与迁移） |
| `build-personal-skill` | ✅ 适配方法论内核（2026-10-22 第 5 版追加） | 新建 `personal-course-pattern-builder`（个人做课记录→专属工作法） |
| 其余 13 个（`stage-design`、`slide-dsl`、`slide-craft`、`pro-editing`、`page-clone`、`style-clone`、`deep-interactive`、`deep-research`、`fact-check`、`k12-core-literacy-planning` 的运行时部分、`learning-to-learn`、`social-emotional-learning`、`lecture-style`） | ❌ **不复用** | —— |

> 🔴 **不复用的理由不是"没用"，是"复制过来就是悬空引用"**：
> 上游那 22 个技能正文**绑死 OpenMAIC 运行时工具**
> （`create_stage` / `generate_scene` / `patch_stage` / `set_roster` / `generate_tts` 等）。
> 本仓库**没有 OpenMAIC 运行时**，整份复制那些 SKILL.md 只会得到一堆执行不了的调用。
>
> ⇒ **只抽方法论内核重写**，交付物规格换成中国高校的教案/大纲/任务书/评价表。
> `scripts/verify_repo.py` 的「OpenMAIC 衍生技能无运行时工具悬空引用」检查会机械拦住残留。
>
> 📌 **许可义务已履行**：MIT 要求保留版权声明与许可声明 ⇒
> `licenses/OpenMAIC-MIT.txt`（与上游逐字节一致）+ `THIRD-PARTY-NOTICES.md` §3 登记署名。
>
> 📌 **课件产出链已于 2026-10-22 第 5 版接入**：新建 `openmaic-courseware` 技能，
> 提供**纯标准库 HTTP API 客户端**（`scripts/openmaic_client.py`）+ **API 契约速查**
> （`references/api-contract.md`）+ **容器编排增量**
> （`deploy/docker-compose.jfa.yml`，是 override，不是上游编排的复制）。
> **OpenMAIC 本体仍不随本仓库分发** —— 使用者自己 clone 部署。
> 本仓库提供的是「接入能力 + 部署增量 + 契约」，不是「引擎源码」。
>
> ⚠️ **与第 4 版的方法论适配是两回事，不要混**：
> 第 4 版做的是「把教学法内核重写成本仓库的中文交付物规格」；
> 第 5 版做的是「接一个真实存在的外部引擎来产出互动课堂」。
> 前者不依赖 OpenMAIC 运行时，后者依赖 —— 所以后者**必须**显式写明
> 「本仓库没有 OpenMAIC 运行时，调用要打到使用者自己部署的实例上」。

---

## 2026-10-22 幻灯片线：外部工具**自研替代**（不装外部，直接做）

**背景**：第 5 版之前，「做 PPT」这件事依赖两个**不随本仓库分发**的外部技能：

| 外部技能 | 来源 | 为什么不能继续依赖 |
|---|---|---|
| `pptx` | 运行时内置技能（`.minimax/.builtin-skills/pptx`） | 运行时内置，**不随包分发** ⇒ 克隆方没有 PPTX 生成能力 |
| `nature-paper2ppt` | 本机全局技能库 | 同样不随包分发 ⇒ 克隆方「论文转 PPT」无人接手 |

这与论文线外包给 ADW 是**同一个坑**（见上方「移出 → 回装」记录）。
处置：**自研**。

| 能力 | 自研后的承担者 | 形态 |
|---|---|---|
| PPTX 生成 | `teaching-slide-designer` | `scripts/build_pptx.py` —— 纯标准库（`json`/`zipfile`），零第三方依赖，产出可被 PowerPoint 直接打开并继续编辑的 `.pptx`（含**讲授者备注**） |
| 幻灯片教学规范 | `teaching-slide-designer` | `scripts/slide_spec_lint.py` —— 判的是「这**是不是**一份能用的教学幻灯片」（要点数、字数、断言式标题、讲稿分离、线性指代、来源标注、占位符残留），不是格式对不对 |
| 论文→汇报叙事 | `paper-to-talk-designer` | 技能（论文结构 → 汇报叙事的映射） |

**已从 `references/external-skills.json` 移除** `pptx` 与 `nature-paper2ppt` 两条登记，
并把 E7 格的 `◐nature-paper2ppt` 改标为 `●`（`paper-to-talk-designer` +
`teaching-slide-designer` + 原有 `latex-posters` / `scientific-slides`）。
**覆盖计数不变**（E7 本来就是「已覆盖」）。

🔴 **守卫会机械拦截回归**：`scripts/verify_repo.py` 的「幻灯片能力自足」一组
（6 项）检查 ① 生成器与审查器在仓库里 ② 外部技能表未再登记 PPTX 类外部技能
③ 矩阵不依赖 PPTX 类外部技能 ④ **两个脚本的 `--selftest` 真跑得过**。
最后一条最硬 —— 它证明的是「克隆下来就能用」，而不只是「文件在」。

> 📌 这条也写进了 `agent.md` 的 **S12 能力必须随交付物走**：
> 判据是「这个能力在**只克隆本仓库**的机器上还成立吗？」不成立 ⇒ 自研，
> 或明确降级为「可选增强」并让矩阵与守卫都不依赖它。
