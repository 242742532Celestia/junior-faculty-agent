---
name: skill-scan
description: 高校教师 Agent 的季度技能巡检与自学习流程。每 3 个月扫描 GitHub 技能生态，判断新技能是否属于高校教师能力范畴，符合则学习入库并做中国高校语境适配，不符合则记录排除理由。当需要「扫描新技能」「更新技能库」「巡检技能生态」「看看有没有新的教学/科研技能」时使用。配套 scripts/skill_scan.py 执行。
license: MIT
---

# 季度技能巡检与自学习

## 这个技能解决什么

技能生态在持续变化。**一个只装技能不更新的 Agent 会在半年后落后于生态**，
而"半年后"的新技能往往是工具链换代——不更新的代价是持续踩旧坑。

本技能定义**每季度一次的完整巡检流程**：发现 → 判读 → 安装 → 适配 → 更新矩阵 → 报告。
自动触发由 cron 任务配置（1/4/7/10 月 1 日 10:00 Asia/Shanghai）。

## 核心原则（**每条都对应一个真实的翻车模式**）

### 1. 「是否属于高校教师能力」必须由语义判断，不能用正则

上游脚本 `skill_scan.py` 只负责**发现**与**按决策安装**，
它**不做**最终判定。理由：技能描述里的关键词不可靠——
一个叫 `research-assistant` 的技能可能是个通用 LLM 工程工具，
一个叫 `teach` 的技能可能只是教用户学编程。

**判据**：打开 SKILL.md，看它**具体解决什么任务**，再判断这个任务是否在高校教师职责内。

### 2. 拉取失败 ≠ 没有新技能

主源仓库拉取失败时，脚本会：
- 把失败写进 `errors` 字段
- 令 `scan_complete = false`
- **以退出码 2 结束**（正常是 0）

这样 cron 运行时能识别出"这次扫描不完整"，不会把网络故障
误判成"本季度主源没有更新"。**看到退出码 2 就重跑那部分，并在报告里保留意见。**

### 3. 一次最多装 10 个

技能库膨胀会让能力矩阵失焦——**多而杂不如少而准**。
每季度最多 10 个新技能，优先补**能力矩阵里的缺口**，而不是补新鲜感。

### 4. 排除记录必须留痕

被拒技能写进 `references/rejected-skills.md`，标注理由类别（S1–S8）。
下季度先读它，**避免同一个技能被反复评估**——
重复评估是巡检变慢的主因。

### 5. 安装 ≠ 学完

装进来只是第一步。教学类技能必须做**中国高校语境适配**，
否则产出会带着 "Year 9 生物课自然选择" 这种英式 K-12 痕迹。
脚本会自动追加适配块，但**仍要人工抽查**适配是否到位。

## 巡检流程（照此执行）

### 步骤 1：扫描

```bash
cd <AGENT_DIR>    # 换成本机 Agent 安装目录
python scripts\skill_scan.py --scan
```

产出 `reports/skill-scan-<年>-Q<N>-candidates.json`，含：
- `new_in_tracked_repos` —— 3 个主源仓库里本机还没有的技能（**高优先级**）
- `search_hits` —— 按 20 组能力缺口关键词搜到的仓库（**需逐个检视**）
- `errors` —— 拉取失败的主源
- `scan_complete` —— 本次扫描是否完整

**退出码非 0 → 本次扫描不完整，先修网络/重跑，再往下走。**

### 步骤 2：判读（核心）

先读两份文件：
- `references/faculty-capability-matrix.md` —— 能力矩阵与巡检判据
- `references/rejected-skills.md` —— 已排除技能，避免重复评估

对每个候选技能：
1. 取 SKILL.md 全文（或至少 prompt 段）
2. 回答：**它让教师能完成什么具体任务？**
3. 套用矩阵第二节的三条判据（产出交付物 / 提供可复用方法框架 / 解决高频真实任务）
4. 决策：

| 决策 | 条件 | 动作 |
|---|---|---|
| **学** | 符合任一判据 | 进安装清单 |
| **拒** | 明确属于 S1–S8 排除类 | 记入 `rejected-skills.md`（名称 / 来源 / 理由 / 日期） |
| **待确认** | 说不准 | 写进报告的「待人工确认」段，**不装** |

> **不要因为名字里有 "paper"/"research"/"teach" 就判为符合。**
> 也不要把「跟 AI 编程相关」当成相关——那是 S5。

### 步骤 3：安装

构造决策 JSON（一个或多个对象）：

```json
[
  {
    "name": "技能名",
    "source_repo": "owner/repo",
    "source_path": "skills/技能名/SKILL.md",
    "source_domain": "teaching"
  }
]
```

```bash
python scripts\skill_scan.py --install decision.json
```

- `source_domain` 填 `teaching` 时脚本自动追加高校语境适配块
- 填 `research` 时不追加（科研技能通常无 K-12 问题）
- 脚本会拒绝：已安装的、没有 frontmatter 的、取不到的
- 超过 10 个会被截断并告警

🔴 **许可红线（装之前必须先确认）**：
本项目对外声明**整体可商用**，因此——
- 候选技能若为 **CC BY-NC / NonCommercial / "仅限非商业"** 许可 → **一律不装**，
  记入 `references/rejected-skills.md`，理由类别记为 **S9 许可不可商用**。
- 候选技能若为 **CC BY-SA** → 可以装，但要在矩阵与 NOTICES 里记清 ShareAlike 传染。
- 判断依据：打开该技能的 `LICENSE` 或仓库许可文件**读原文**，不要只看仓库简介里的标签 ——
  GitHub 仓库标签与实际 LICENSE 文件不一致是真实存在的。
- 装完后 `python scripts\verify_repo.py` 会替你再查一遍
  （检查项："skills/ 不含任何 NonCommercial 技能"）。
  **不要用自己的判断代替这条机械检查。**

**安装后必须抽查**：读 1–2 个新装技能的 SKILL.md 尾部，
确认适配块在位、且内容没有明显 K-12 硬伤。

### 步骤 4：更新能力矩阵

编辑 `references/faculty-capability-matrix.md`：
- 把新技能填入对应能力格的「覆盖技能」列
- 缺口格从「**缺口**」改为「已覆盖」或「部分覆盖」
- 更新文件头的「最近更新」日期
- 仍无人覆盖的格，**保留在缺口状态**——它是下季度的输入

### 步骤 5：产出巡检报告

写 `reports/skill-scan-<年>-Q<N>.md`，六节固定结构：

```
一、本次扫描概况
    扫描源清单 | 扫描是否完整（对应 scan_complete）| 候选总数 | 装了几个
二、新学会的技能
    表格：技能名 | 来源仓库 | 覆盖能力格 | 做了哪些语境适配
三、评估后拒绝的技能
    表格：技能名 | 来源 | 理由类别（S1-S8 + 具体说明）
四、待人工确认的技能
    表格：技能名 | 来源 | 说不准的原因 | 建议下一步
五、能力矩阵变化
    补上的缺口 | 仍是缺口 | 本季度判断
六、下季度重点关注方向
    仍为缺口的格 + 新出现的技能生态变化
```

### 步骤 6：自检（都要跑）

```bash
python scripts\skill_scan.py --selftest     # 20/20：验巡检器本身
python scripts\verify_repo.py                # 全绿：验文档没写错 + 无 NC 内容 + 分档自洽
python scripts\verify_rewrite.py             # 全绿：验结构合规 + 全仓交叉引用
python scripts\package_release.py --build    # 出可商用分发包并自检
```

`--selftest` 必须 20/20 通过。**不通过就修到通过**，并在报告里说明修了什么。
自检项：技能数量、frontmatter 完整性、教学技能适配覆盖、
关键引用文件存在、agent.md 关键段落存在。

`verify_repo.py` 是**文档 ↔ 现实一致性守卫**：能力矩阵里每格是否有 `●` 已装技能、
README 的格数与覆盖计数、THIRD-PARTY-NOTICES 的清单与 `skill_id` 域、
许可副本存在性、硬编码绝对路径、真实密钥、UTF-8 无 BOM、
**分档推导自洽**（每个已装技能都有能力格归属 / 三档并集恒等式），
以及**「skills/ 不含任何 NonCommercial 技能」**。
**装完技能后一定要跑它** —— 新装的技能会让矩阵、NOTICES、README 的计数失效，
这正是它要抓的。

`package_release.py --build` 出 `dist/junior-faculty-agent-1.0.0.zip`
（含 MANIFEST.json 与逐文件校验和），并断言包内**不含**任何 NonCommercial 内容。
有 NC 内容混入时它会**中止出包**。

**分档包**用同一个脚本：`--profile teaching`（62 个技能）/ `--profile research`（24 个）/ 
`--profile full`（86 个，默认）。包内技能集合由**能力矩阵的能力域**机械推导，
不手工枚举 —— 所以**新装技能必须回填到矩阵的某一格**，
否则它在教学包与科研包里会双双消失，出包器直接中止。

> 守卫生成变异测试：`python scripts/test_verify_repo.py`
> 会在副本上注入 42 种典型错误（含"NC 技能放回 skills/"、
> "NC 许可全文放回 licenses/"、"矩阵里摘掉一个技能的归属"、
> "包内缺许可副本"），确认守卫确实会红在预期检查项上。
> 改守卫后必须重跑它。

## 巡检纪律

- **不要动已装的技能** —— 升级用 `npx skills update`，不在巡检里覆盖。
  覆盖会丢掉已做的语境适配。
- **不要把 `references/` 里的判据改松** —— 判据放宽等于放弃筛选。
  确实需要调整时，在报告里写明改了什么、为什么。
- **拒绝也要给理由** —— "不知道"不构成拒绝理由，要写 S 类别 + 具体说明。
- **报告要如实** —— 扫描不完整就说不完整；本季度没发现新技能就说没发现，
  不要为报告好看而虚报。

## 交叉引用

- 判据与能力清单 → `references/faculty-capability-matrix.md`
- 排除记录 → `references/rejected-skills.md`
- 语境适配表 → `references/he-context-adapter.md`
- 执行脚本 → `scripts/skill_scan.py`
