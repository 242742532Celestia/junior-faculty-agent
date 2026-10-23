# 变更记录

本文件记录**公开发行版**的变更。
本仓库内部的每一次判断与依据（含被推翻的）记在
[`reports/skill-scan-2026-Q4.md`](reports/skill-scan-2026-Q4.md) 的变更记录里 ——
**那份报告保留原样，是为了记录当时的判断，不做事后修饰。**

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [1.0.0] - 2026-10-24

首个公开版。**可商用**：本仓库原创内容 MIT；第三方内容各自保留原许可，
副本在 `licenses/`，台账在 `THIRD-PARTY-NOTICES.md`。
**NonCommercial 内容不随本仓库与任何分发包分发。**

### 一、大纲先行层（唯一事实源）

- 教案 / 课件 / 讲义改为**从同一份大纲派生**（`demo/outline.py`），
  不再各自写出来 —— "改了教案忘了改课件"从**检查问题**变成**结构问题**。
- 判据查的是「派生结果 == 重新派生的结果」（可证伪），不是"看起来对不对"。

### 二、UbD 骨架进大纲

- 大纲新增 `ubd` 块：持久理解 1–3 条、基本问题 3–5 个、GRASPS 表现性任务六要素、
  WHERETO 七项覆盖（每项写明落在哪个环节）。
- 写法要求落在 `skills/teaching-file-builder`「UbD 骨架」一节，
  提示词从那里摘 —— **不另写一套规则**。
- 判据 `OL-P15`–`OL-P18`。

### 三、讲义改为纯派生

- 讲稿只有一份（写在大纲的 `slides[].notes` 里），讲义从**课件规格**导出 ⇒
  「讲义讲稿 ≠ 课件讲稿」在结构上不可能发生。
- 判据 `HD-P01`–`HD-P04`（含逐字比对）。

### 四、增量重生成

- `python demo/outline.py --regen-page <页id>`：改一页只重跑一页，在线模式只调**一次**模型。
- 判据是**逐页指纹比对**（sha256）：只重跑一页 ⇒ 其余页必须一字未动。
  为此每页必须有**稳定 id**（`OL-P19`）。

### 五、模型按用途路由

- `demo/llm.py` 支持 `plan` / `slides` / `handout` / `lint` 四种用途，
  各自可用 `JFA_LLM_MODEL_*` 指定，未设则回退 `JFA_LLM_MODEL`。

### 六、分档出包

- `scripts/package_release.py --profile full|teaching|research`：
  包内技能集合**不是手工枚举**的，而是由**能力矩阵的能力域**机械推导
  （数据在 `references/profiles.json`，推导器 `scripts/profile_map.py`，
  出包器与守卫**共用同一份实现** —— 两套推导必然漂移，且漂移是静默的）。
- 推导不自洽 ⇒ **中止出包**，绝不打一个来路不明的包。
- `licenses/` 按**包内实际技能**动态决定：有 Apache 技能才带 Apache 副本
  （Apache §4(a) 与 MIT 保留声明是**再分发义务**，少了副本即未履行）。

### 七、许可台账与"可商用"承诺的机械保证

- NonCommercial（CC BY-NC）内容移入本机自用的 `skills-archive/`，
  **不随仓库与分发包分发** —— NC 条款会传染整个分发物。
- 出包时**断言**分发物中不存在任何 NC 内容；守卫独立再查一遍。
- 守卫机械核对：每个已装技能都声明 license、每份许可副本都被引用、
  NOTICES 覆盖全部已装技能、README 的许可表述与实际一致。

### 八、判据会红的证明

- `scripts/test_verify_repo.py`：在仓库副本上注入典型错误，
  要求每一条都让守卫**在预期的那条检查上变红**。
- `demo/selftest.py`：判据自身的变异测试。
- 🔴 **改守卫必须配变异**：没有变异的新守卫 = 没人证明它会红 = 它可能已经在空转。

### 九、文档 ↔ 现实一致性

- README / 报告 / cron 文档里的每个数字都被**机械核对**
  （守卫自己算出实际值，再与文档比对）。
- "文档说 N 个技能"和"磁盘上有 N+1 个技能"这种漂移会立刻变红。

### 十、GitHub 开源化

- `.github/workflows/ci.yml`：把仓库**已有的机器判据**接到 CI 上
  （Linux + Windows × Python 3.9 / 3.13）——
  Windows 必须保留：GBK 编码类问题只在 Windows 暴露。
- `.github/workflows/release.yml`：打 tag 即出三档包 + 源码包 + 发布说明，
  并在发布前把产物**真的解开跑一遍**。
- `CONTRIBUTING.md` / `CODE_OF_CONDUCT.md` / `SECURITY.md` / `CHANGELOG.md` /
  `.gitattributes` / `.editorconfig` / Issue 与 PR 模板。
- `scripts/github_release.py`：产 GitHub 源码包与发布说明，并对产物做独立校验
  （NC、密钥、必备件、可解压、克隆即用）。

### 已知限制

- `scripts/verify_rewrite.py` 的检查数**取决于上游原文在不在**：
  无上游原文时是 666，带上上游原文会多跑 50 项 clean-room 相似度核对（716）。
  **上游仓库不随本仓库分发**，克隆方默认看到的是 666 那个口径。
- `references/faculty-capability-matrix.md` 里的能力格是**当前机器判据下的结论**，
  不是"某人的判断" —— 但它记录的是建库当时的快照，最新状态以 README 为准。

[1.0.0]: https://github.com/OWNER/REPO/releases/tag/v1.0.0
