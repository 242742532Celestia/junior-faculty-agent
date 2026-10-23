---
name: submission-readiness
description: 面向论文投稿前的终稿体检（submission readiness）流程——用本地脚本做摘要检查、控制变量核对、公式审计与格式转换，再按严重度分流人工改稿与复检；触发词：投稿前检查、终稿体检、摘要检查、公式审计、格式转换、投稿就绪。
license: MIT
compatibility: Requires Python 3.9+ (standard library only, no third-party packages). All bundled scripts run fully offline and need no API key. Format conversion additionally requires pandoc on PATH.
metadata:
  version: "1.0"
  last-reviewed: "2026-10-22"
  skill-author: junior-faculty-agent
---

# 投稿前机器体检

## 任务边界

本技能只做**投稿前的机械体检**：把稿件里那些"机器能确定"的问题（摘要缺哪一项要素、
控制变量是否写清、公式是否残缺、文件格式是否转换到位）提前找出来，把作者的注意力留给
真正需要判断的部分。

面向的使用场景是**中国高校青年教师**：稿件常为中文或中英混排，常在 Word 里编辑，
投稿前常需从 Markdown/LaTeX 转成 DOCX，或反向取回可修改的文本。

### 本技能负责

1. 枚举摘要中**逐句可疑片段**（长句、被动堆叠、缺主语、模糊指代、过强断言、数字与
   结论不匹配），并检查摘要的**结构五要素**与**字数**。
2. 枚举**控制变量（control variable）/ 参考状态**的事实缺口：模糊的"其余条件保持不变"、
   参数区间、例外项、缺失的基线定义。
3. 审计 **DOCX 中的公式**：统计 OMML 公式（Office Math Markup Language）节点，检出空公式、
   占位符公式、编号引用缺失，并给出"按纯文本改稿会丢公式"的硬护栏。
4. 包装 **Pandoc** 完成格式转换（Markdown/LaTeX ⇄ DOCX/PDF），并在工具缺失时给出替代方案。

### 本技能不做什么

- **不做语义判断**。机器只报确定性结论：命中了哪条规则、在第几行、依据是什么。
  "这句话读起来是否别扭""这个结论是否成立"由人判断，脚本不代替。
- **不做学术质量评价**。创新性、方法是否严谨、结论是否被证据支持，交给
  `peer-review` 与 `statistical-analysis`。
- **不自动改稿**。脚本只读不写稿件正文；所有改动由作者本人在 Word/编辑器里完成。
- **不替代目标期刊的官方要求**。字数上限、参考文献格式、图表尺寸、模板版本一律
  **需查目标期刊官网**（作者指南 / 投稿须知 / 模板下载页），并记录查阅日期。
  本技能不内置任何期刊的具体数值要求，避免过期或臆造。
- **不联网、不上传稿件**。全部脚本离线运行，稿件不离开本机。
- **不生成、不补全任何数据、结果或引用**。缺失就报告缺失。

## 四类体检

| # | 体检类 | 脚本 | 回答的问题 |
|---|--------|------|-----------|
| 1 | 摘要体检 | `scripts/audit_abstract.py` | 摘要该有的五要素齐不齐？哪些句子需要人再看一眼？字数超没超？ |
| 2 | 控制变量体检 | `scripts/audit_control_vars.py` | "其余条件保持不变"到底固定了什么？参数是区间还是单值？基线是谁？ |
| 3 | 公式与文件体检 | `scripts/audit_docx_formulas.py` | DOCX 里的公式完整吗？编号对得上吗？纯文本流程会不会把公式抹掉？ |
| 4 | 格式转换体检 | `scripts/convert_format.py` | 目标格式文件生成成功了吗？工具缺失时怎么办？ |

第 3 类是**唯一需要读 DOCX 内部结构**的一类，也是最容易翻车的一类：DOCX 中的公式以
OMML 节点存储，用 `paragraph.text`、复制粘贴、或任何"逐段读文本再重写"的脚本处理，
都会**静默丢掉全部公式**。这正是硬护栏存在的原因。

## 工作流

```
机器体检 → 按严重度分流 → 人工判断 → 改稿 → 复检
```

1. **机器体检**：对摘要、方法/实验部分、终稿 DOCX 分别运行三个审计脚本，格式转换用
   `convert_format.py`。所有输出先落到一份记录里（建议保存为 JSON，便于前后对比）。
2. **按严重度分流**：按下面的严重度定义，把条目分到"必须改""建议改""可以不"。
   高严重度条目优先；同一类问题一次性合并改，避免反复触发同一处。
3. **人工判断**：逐条读候选条目，判断它是不是真问题。**脚本命中 ≠ 稿件有错**；
   关键词未命中也 ≠ 要素缺失。本技能的输出只是线索，最终判断必须由作者（或合作者）签字。
4. **改稿**：在 Word 或源文件里改。改动后重新跑对应脚本，确认该条目消失，
   且没有引入新条目（例如删掉公式后正文里残留"式(3)"）。
5. **复检**：三个审计脚本全部重跑一遍 + 打开最终 DOCX 人工翻一遍
   （Word 里公式、图表、编号、交叉引用），再按目标期刊官网的要求核对格式。

## 严重度

| 级别 | 含义 | 处置 |
|------|------|------|
| **high** | 审稿人极可能据此质疑稿件可信度，或直接导致退稿：结构要素缺失、篇幅超出目标、比较对象（基线）未定义、公式内容为占位符 | 投稿前必须处理，处理不了则必须在稿件中显式说明缺失原因 |
| **medium** | 可复现性或表达精确度受损：模糊指代、过强断言无统计量支撑、数值与幅度词冲突、模糊的"保持不变"、参数区间未说明取值、例外项未交代、公式编号引用缺失 | 投稿前尽量处理；保留则需有理由 |
| **low** | 可读性与效率问题：长句、被动结构堆叠、疑似缺主语、篇幅未超目标 | 有余力再改；不作为阻塞项 |

分级是**处置顺序**，不是对稿件的评价。脚本退出码与严重度的关系：

- `audit_abstract.py` / `audit_control_vars.py`：枚举出候选即退出码 `1`（**候选不等于判定**）。
- `audit_docx_formulas.py`：出现 **error** 退出码 `1`；仅 warning 时退出码 `0`，
  加 `--strict` 后 warning 也算失败。
- `convert_format.py`：成功 `0`；转换失败 `1`；用法错误或工具缺失 `2`。

## 脚本用法

四个脚本都只用 Python 标准库（`zipfile` / `xml.etree` / `shutil` / `argparse` / `re`），
不需要 `python-docx`、`lxml`、`pypandoc` 等第三方包；也都支持 `--selftest` 离线自检。

### 1) 摘要体检

```bash
python scripts/audit_abstract.py --file paper/abstract.md
python scripts/audit_abstract.py --file paper/abstract.docx --target-words 250
python scripts/audit_abstract.py --file paper/abstract.md --json
```

输出分三段：结构要素检出情况（背景/目标/方法/结果/结论，缺哪个报哪个）、字数统计
（中文按汉字数、英文按词数，目标上限请按目标期刊官网填写）、逐条候选条目。
每条候选固定四件套：**位置 + 候选片段 + 判据 + 需要人工判断什么**。

### 2) 控制变量体检

```bash
python scripts/audit_control_vars.py --file paper/methods.md
python scripts/audit_control_vars.py --file paper/methods.docx --json
```

报四类事实缺口：模糊的"保持不变"表述、参数区间取值（如 `10-50`）、例外项（"除 B 组外"）、
比较对象（基线/对照组）未定义。**只报可确定的事实缺口，不推断作者本意。**

### 3) 公式审计（DOCX）

```bash
python scripts/audit_docx_formulas.py --docx paper/main.docx
python scripts/audit_docx_formulas.py --docx paper/main.docx --strict
python scripts/audit_docx_formulas.py --docx paper/main.docx --json
```

统计 XML 里的 `m:oMath` 节点，检出空公式、疑似占位符公式（`xxx` / `TODO` / `公式` /
`待补` / 单字母加问号）、正文引用了"式(N)"却数不到对应编号的条目。
**硬护栏**：当"正文纯文本里的公式数 = 0，而 XML 里公式数 > 0"时，脚本报警告——
说明这份文档的公式只存在于 OMML，任何按纯文本改稿的操作都会丢掉全部公式，
请在 Word 中改稿，或先做保真转换。`--strict` 时空公式计为错误。

### 4) 格式转换

```bash
python scripts/convert_format.py --check
python scripts/convert_format.py --input paper/main.md --output paper/main.docx --format docx
python scripts/convert_format.py --input paper/main.md --output paper/main.tex --format latex --template template.tex
python scripts/convert_format.py --input paper/main.md --output paper/main.pdf --format pdf
```

先用 `--check` 探测 pandoc 是否在 PATH 中。pandoc 缺失时脚本**不会静默失败**，
而是给出中文提示与替代方案（装 pandoc / 用 Word 手工另存 / 走 LaTeX 路线）。
转换失败（pandoc 返回非 0，或返回成功但产物不存在）时退出码 `1`，并保留 pandoc 的
stderr 原文。中文 PDF 需要本地有 XeLaTeX 之类的引擎，否则请改走 DOCX。

## 常见失败模式

1. **把纯文本当全文**。DOCX 的公式在 OMML 里，`paragraph.text` 看不到；按纯文本改稿
   会把公式全抹掉，而且**不报错**。改 DOCX 前先跑公式审计，看护栏是否触发。
2. **把候选当成判定**。脚本命中"模糊指代"不代表读者看不懂；脚本没命中"结构要素缺失"
   也不代表摘要完整（可能只是换了说法）。跳过人工判断这一步，等于没做体检。
3. **凭记忆套期刊格式**。行数、字号、参考文献样式、图表分辨率各家不同且常变。
   **一律查目标期刊官网**，并把查阅日期记进投稿记录。
4. **关键词粗筛当结构判定**。五要素检测是信号词粗筛：中文摘要完全可能用同义表述，
   英文摘要也可能一个信号词都不命中却结构完整。
5. **区间参数照抄**。参数表写 `10-50` 而实验只用了其中一个值，审稿人一定会问
   "到底用的哪个值"。脚本只提示这件事存在，答案只能由作者给。
6. **基线没定义**。正文写"与基线比较"却没有基线的定义和来源，实验就不可复现，
   这是 `high` 级别。
7. **转换后公式丢失或变形**。Markdown → DOCX 时 LaTeX 公式可能被转成图片或丢失；
   转换完成后必须再跑一次公式审计，别假设转换是无损的。
8. **中文 PDF 乱码**。默认 LaTeX 引擎不认中文字体，需要 XeLaTeX/ctex；
   中文稿优先交 DOCX。
9. **编码带 BOM**。脚本按 UTF-8 读取文本（含 BOM 也会被容忍），但**投稿文件本身**
   建议存为 UTF-8 无 BOM，避免目标系统解析异常。
10. **只跑一次**。改稿之后必须复检：删公式会留下悬空的"式(N)"引用，
    改摘要会让字数重新越界。

## 与其他技能的分工

| 技能 | 负责 | 与本技能的关系 |
|------|------|----------------|
| `scientific-writing` | 正文写作与润色、证据可追溯 | 本技能不写正文；只在其产出之后做投稿前体检 |
| `venue-templates` | 期刊模板、格式细则、模板文件 | 格式细则以该技能和期刊官网为准，本技能不重复维护 |
| `peer-review` | 同行评审式的学术评价 | 本技能不做学术评审，只做机械体检 |
| `scholar-evaluation` | 学术影响力与作者评价 | 与投稿前体检无关 |
| `statistical-analysis` | 统计方法、功效、结果解读 | "过强断言有没有统计支撑"最终由它和作者判断 |
| `paper-lookup` | 文献检索 | 体检发现参考文献缺失时由它补检索 |
| `citation-management` | 引用格式化与一致性 | 参考文献格式问题归它，本技能不碰 |
| `submission-readiness`（本技能） | 投稿前机器体检、严重度分流、改稿复检 | — |

完整检查项表、可机检与需人眼的分界、处置顺序与"投稿前 15 分钟速检清单"见
`references/submission-checklist.md`。
