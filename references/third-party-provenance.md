# 溯源说明（Third-Party Provenance）

> 本文件记录本项目与第三方来源的**关系性质**——尤其是那些
> **本项目没有复制其内容**、但主题/命名受其启发的来源。
>
> 归属与许可义务见 [`THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md)；
> 改动说明见 [`NOTICE.md`](../NOTICE.md)。

---

## 一、GarethManning/education-agent-skills

- **来源**：https://github.com/GarethManning/education-agent-skills
- **原作者**：Copyright (c) 2026 Gareth Manning
- **上游许可**：CC BY-SA 4.0
- **上游许可副本**：`licenses/CC-BY-SA-4.0-education-agent-skills.txt`

### 关系性质：主题与命名的启发，**不含任何上游文件内容**

本项目的 50 个教学技能曾经直接复制自该上游（CC BY-SA 4.0），并在其基础上追加
「中国高校语境适配」段。**2026-10-22 起，这 50 个技能已被完全独立重写**：

| 维度 | 事实 |
|---|---|
| 上游文件内容 | **未复制**。重写版不含任何上游的正文、表格、示例、agent 列表或章节结构 |
| 上游 `skill_id` 溯源字段 | **已全部移除**（保留它就等于声明"这是上游改编版"） |
| 撰写依据 | 公开发表的**教育研究文献**，各技能 SKILL.md 的「方法论依据」段逐条列明出处 |
| 相似度核验 | `scripts/verify_rewrite.py` 机械比对：8-gram Jaccard < 0.10、长行（≥25 字符）重合 < 5% |
| 主题选择与命名 | **参考了该上游的教学技能清单**（哪些教学主题值得做成技能、叫什么名字） |

### 为什么保留同样的名字

"认知负荷分析""错因分析""通用学习设计"这类**方法名与功能性命名**指向的是
教学法本身的概念，不属于著作权保护的对象。但为避免任何争议，本项目：

1. 主动**致谢**该上游并提供链接；
2. 在 `THIRD-PARTY-NOTICES.md` 与 `LICENSE` 中说明关系性质；
3. 保留其 CC BY-SA 4.0 许可全文副本以供追溯；
4. 承诺：若任何人认为某一技能的命名或主题选择仍构成其表达，
   欢迎提 issue —— 我们会在**保留署名与链接**的前提下调整。

### 这与"逐句改写"的区别

把上游文本换同义词仍然构成改编，仍受 SA 约束。**clean-room 重写不是这样做的**：

- 起点是**方法论文献**（Biggs、Black & Wiliam、Sweller、Toulmin、Hattie…），
  不是上游文本；
- 章节结构、输出模板、案例、判据全部按本项目自己的理解重新设计；
- 相似度上限写死在 `scripts/verify_rewrite.py` 里，**超标即须重写，不许放宽**。

---

## 二、K-Dense-AI/scientific-agent-skills

- **来源**：https://github.com/K-Dense-AI/scientific-agent-skills
- **原作者**：Copyright (c) 2025 K-Dense Inc.
- **许可**：MIT
- **许可副本**：`licenses/MIT-K-Dense.txt`

### 关系性质：**原样复制，未修改内容本体**

20 个科研技能整体复制自该上游，**内容未作任何修改**（MIT 许可不要求声明改动，
此处一并说明）。这 20 个技能**仍受 MIT 授权，可自由商用**。

> 注意：上游 `experimental-design` / `uncertainty-and-units` /
> `scientific-brainstorming` 三个技能正文里提到的同级技能 `statistical-power`，
> **不存在于该上游的 20 个技能中**（已逐条核实）。这是上游自带的悬空交叉引用，
> 本项目**未修改**这些文件正文（以保持"原样复制"的准确表述），
> 而是在本项目自己的文档里改用真实存在的技能。

---

## 三、Imbad0202/academic-research-skills

- **来源**：https://github.com/Imbad0202/academic-research-skills
- **原作者**：Copyright (c) 2026 Cheng-I Wu (Imbad0202)
- **许可**：CC BY-NC 4.0（**仅限非商业**）
- **许可副本**：`skills-archive/licenses/CC-BY-NC-4.0-academic-research-skills.txt`

### 关系性质：**已移出，不随本仓库分发**

3 个技能（`academic-paper` / `academic-paper-reviewer` / `deep-research`）
曾被安装，后因 **NonCommercial 条款会传染到整个分发物**（只要包里有 NC 材料，
整个仓库就不能商用）而移出到 `skills-archive/`（本地自用副本，已 `.gitignore`）。

**本仓库的分发版不含任何 NonCommercial 内容。** 详见 `skills-archive/README.md`。

---

## 四、自有原创部分

`agent.md`、`README.md`、`LICENSE`、`NOTICE.md`、`references/`、
`scripts/`、`crons/`、`reports/`，
以及 5 个私有技能（`grant-proposal-writer`、`exam-question-bank`、
`teaching-file-builder`、`skill-scan`、`he-context-adapter`），
以及 50 个独立重写的教学技能 —— 均为本项目原创，按 MIT 授权。

---

## 五、核验方式

| 想确认什么 | 跑什么 |
|---|---|
| 50 个教学技能确实不含上游内容 | `python scripts/verify_rewrite.py`（需 `JFA_UPSTREAM` 指向上游暂存） |
| 文档与磁盘实际一致 | `python scripts/verify_repo.py` |
| 分发包里没有禁商用内容 | `python scripts/package_release.py --build` |
| 守卫本身没坏 | `python scripts/test_verify_repo.py` |

**每一项都是机械检查，不依赖人读。**
