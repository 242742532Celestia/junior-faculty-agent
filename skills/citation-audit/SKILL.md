---
name: citation-audit
description: 面向中文论文稿件的引用核验（citation verification）与引文真实性（citation authenticity）审计工具，逐条比对权威文献数据库并对账正文与文末文献表的文献编号（reference-number reconciliation），输出可复核的问题清单与修订建议。
license: MIT
---

# 引用核验与引用一致性审计

## 任务边界

本技能解决**两类问题**，且只解决这两类：

1. **引文真实性**：稿子里的每一条参考文献是否真实存在，标题、年份、第一作者是否与权威记录一致。
2. **引用一致性**：正文里的引用标记与文末文献表是否一一对应，编号是否错位，作者指代是否前后一致。

**适用对象**：中文高校青年教师撰写的论文初稿、投稿前自检、学位论文、基金申请书、综述稿件、
返修稿的参考文献体检。

**判定依据的数据源**（只读公开 API）：
Crossref（DOI 注册机构）、arXiv（预印本）、Semantic Scholar（论文元数据聚合）。

**不属于本技能的事**：本技能**不评价**文献的学术质量、影响力、期刊分区、被引量，
也**不判断**某条文献是否"值得引用"。真实性成立不等于质量合格，这两件事必须分开。

## 输入与输出

### 输入

| 输入 | 形式 | 说明 |
|---|---|---|
| 单条引用 | 一行引用文本 | 含 DOI、arXiv ID 或标题（可带年份）均可 |
| 批量引用 | `.md` / `.txt` 文件 | 每行一条引用，或一个含文献表段的稿件 |
| 待审稿件 | `.md` / `.txt` / `.docx` | 用于编号对账与作者指代审计 |

### 输出

- **逐条四档判定**：证实 / 存疑 / 证伪 / 查不到，每条附命中记录、标题相似度与具体理由。
- **定位到行号/条目号的问题清单**：正文第 N 行、文献表第 M 条。
- **退出码**：可直接接入 CI 或写作流水线。
  `0` = 无问题；`1` = 发现问题；`2` = 用法错误或运行故障。

> 🔴 **核心取径：只报矛盾，不报缺失。**
> 「查不到」只说明数据库未收录或不可用，**不构成引用错误的结论**。
> 详见 [references/citation-audit-rules.md](references/citation-audit-rules.md) 第 3 节。

---

## 工作流

三段式：**机器枚举 → 逐条判断 → 改稿复核**。
不要跳过第一段直接凭印象检查，也不要在第三段用机器结论覆盖作者的真实意图。

### 第一段：机器枚举（Machine Enumeration）

让脚本先把"可能有问题的地方"全部列出来，人只看这份清单。

```bash
# 1. 逐条核验引文真实性
python scripts/verify_references.py --reference "<作者>. (<年份>). <标题>. <期刊名>. <DOI>"

# 2. 对账正文与文献表
python scripts/audit_citation_index.py --file path/to/manuscript.md
```

- 枚举阶段**只记录事实**：命中了什么、相似度多少、行号在哪。
- 此时不要改稿。先把清单拿全，避免"改到一半发现还有 30 条没查"。

### 第二段：逐条判断（Per-Item Adjudication）

对第一段清单里的每一条，**人工给出结论**，四档判定口径见下节。要点：

- **存疑不等于错**：年份差 3 年可能只是预印本→正式版的正常延迟。
- **证伪要出证据**：必须能展示"引用标题 / 命中标题 / 相似度"三者，缺一不可。
- **查不到不追责**：先问"是不是预印本、会议论文、中文文献、书章"，再考虑是不是真错。
- 逐条在稿件上标记处置意见：`保留` / `改字段` / `改引用` / `补文献` / `删文献`。

### 第三段：改稿复核（Revise & Re-check）

改完之后**必须重新跑一遍**两个脚本：

```bash
python scripts/verify_references.py --file path/to/references.md
python scripts/audit_citation_index.py --file path/to/manuscript.md
```

- 改编号会牵动全稿，改一条就要重排一串——所以复核必须是**全量重跑**，不是抽查。
- 复核时若某个问题**故意不改**（例如正文里的举例引用），在稿件旁留一行注释说明，
  避免下一轮复核又被当成新问题报出来。
- 复核退出码为 `0` 才算收尾。

---

## 判定阈值

四档判定的阈值由 `difflib.SequenceMatcher(None, a, b).ratio()` 计算的**标题相似度**（title similarity）
与字段偏差共同决定。

| 判据 | 阈值 | 结论 |
|---|---|---|
| 标题相似度 | `>= 0.85` | 标题匹配 |
| 标题相似度 | `0.70 ~ 0.85` | 标题存疑 |
| 标题相似度 | `< 0.70` | 标题证伪 |
| 年份差 | `> 2` 年 | 存疑，标注"年份不符" |
| 第一作者姓氏 | 不匹配 | 存疑，标注"作者不符" |

| 判定 | 充分必要条件 |
|---|---|
| **证实** | 命中权威数据源 **且** 标题相似度 `>= 0.85` **且** 年份差 `<= 2` **且** 第一作者姓氏一致（不可得的字段视为满足，但须注明未核验） |
| **存疑** | 命中数据源，但标题相似度落在 `[0.70, 0.85)`、或年份差 `> 2`、或第一作者姓氏不符、或多源结论互相冲突 |
| **证伪** | 命中数据源 **且** 标题相似度 `< 0.70` |
| **查不到** | 所有数据源无匹配，或数据源访问失败，或输入不足以定位 |

> 🔴 **查不到 ≠ 错。** 查不到时输出必须写明
> "数据库未收录，可能是预印本/会议论文/非英文文献"，**严禁**输出"证伪"。

完整的充分必要条件、取径理由与失败模式处理，见
[references/citation-audit-rules.md](references/citation-audit-rules.md)。

---

## 脚本用法

两个脚本都在 `scripts/` 下，**只用 Python 标准库**（Python 3.9+），无需安装任何依赖。

### `scripts/verify_references.py` — 引文真实性核验

```bash
# 单条
python scripts/verify_references.py --reference "<作者>. (<年份>). <标题>. <期刊名>. <DOI>"

# 多条（可重复传入）
python scripts/verify_references.py --reference "<第1条>" --reference "<第2条>"

# 批量：每行一条引用
python scripts/verify_references.py --file references.txt

# 机器可读输出
python scripts/verify_references.py --file references.txt --json

# 离线自检（不联网）
python scripts/verify_references.py --selftest
```

| 选项 | 说明 |
|---|---|
| `--reference` | 一条引用文本，可重复传入 |
| `--file` | 批量核验，每行一条引用 |
| `--json` | JSON 输出 |
| `--offline` | 不联网，仅做本地解析与判定 |
| `--selftest` | 离线自检，不访问网络 |

数据源与请求方式：
- Crossref：`https://api.crossref.org/works/<DOI>`、`https://api.crossref.org/works?query.bibliographic=<标题>&rows=3`
- arXiv：`http://export.arxiv.org/api/query?search_query=ti:"<标题>"&max_results=3`
- Semantic Scholar：`https://api.semanticscholar.org/graph/v1/paper/DOI:<DOI>?fields=title,year,authors,venue`

网络鲁棒性：超时 15 秒；HTTP 429 / 5xx 触发**指数退避重试**（exponential backoff retry），最多 3 次；
仍不可用则该数据源降级为"查不到"，并在报告中写明失败原因。

### `scripts/audit_citation_index.py` — 引用指代一致性审计

```bash
python scripts/audit_citation_index.py --file manuscript.md
python scripts/audit_citation_index.py --file manuscript.docx
python scripts/audit_citation_index.py --file manuscript.md --json
python scripts/audit_citation_index.py --selftest
```

| 检查 | 报出的问题 |
|---|---|
| 正文编号 ↔ 文献表编号对账 | **悬空引用**（dangling citation）、**幽灵条目**（orphan entry）、**编号错位**（number misalignment） |
| 作者指代一致性 | 正文 `Zhang et al. (2021)` 与文献表第一作者姓氏不一致 |
| 编号风格 | 数字编号制与作者-年份制混用 |

支持的引用标记：`[1]`、`[1,2]`、`[1-3]`、`[1-3,5]`、`（Smith, 2020）`、`Zhang et al. (2021)`。
支持 `.md` / `.txt` / `.docx`；`.docx` 用标准库 zipfile 读取 `word/document.xml`，
再由 xml.etree 提取纯文本（**不依赖 python-docx**）。

---

## 不做什么

明确边界，避免越界或误伤：

1. **不判定文献的学术质量、影响力、期刊分区、被引量。** 真实存在 ≠ 值得引用。
2. **不把「查不到」当成错误。** 预印本、会议论文、中文期刊、书章、学位论文大量不被检索库收录。
3. **不自动改稿。** 本技能输出问题清单与建议，改不改、怎么改由作者决定。
4. **不编造事实。** 不臆造文献、DOI、作者、期刊名；示例一律用占位符；查不到就写查不到。
5. **不越界到文献检索与综述构建。** 找文献、凑参考文献请用 `citation-management` / `literature-review`。
6. **不做格式排版。** 引文格式统一、APA/GB-T 7714 样式转换不属于本技能。
7. **不替作者判断引文必要性与相关性。** 该不该引这条，是学术判断，不是脚本判断。
8. **不改稿件以外的文件。** 本技能只读取指定输入、只写出报告。

---

## 常见失败模式

| 失败模式 | 表现 | 处理 |
|---|---|---|
| 预印本与正式版 DOI 不同 | 按预印本 DOI 查 Crossref 必然失败 | 记为"查不到"，改按标题跨源检索 |
| 页码差异 | 出版商封面页计入，页码差 1–2 页 | 本技能不比页码，忽略即可 |
| 机构作者无姓氏 | 第一作者记录无 family 字段 | 跳过"作者不符"判据，不判错 |
| 会议论文无卷号 | 无 volume，页码只有起始页 | 同题会议版/期刊版会触发"年份不符"存疑，属正常 |
| DOI 解析重定向 | `doi.org` 302 到出版商页 | 脚本只查 API 不抓出版商页；手工填 URL 会导致查不到 |
| API 限流/超时 | HTTP 429 / 5xx | 指数退避重试 3 次；仍失败则该源降级为"查不到"并写明原因 |
| `.docx` 引用域 | Word 域代码抽出是占位符或空 | 属"查不到"，不是"证伪" |
| 文献表标题非标准 | 写成"主要参考文献""文献与政策" | 脚本切不出文献表 → 报低严重度"文献表缺失"，不报一堆悬空引用 |
| 编号风格混用误判 | 引号内的正文举例被当成引用 | 只报中等严重度的"混用"，由人工判定 |
| 幽灵条目误报 | 作者-年份写法差异导致漏配 | 纯作者-年份制下幽灵条目降为低严重度并注明匹配方式 |

完整版见 [references/citation-audit-rules.md](references/citation-audit-rules.md) 第 4 节。

---

## 与其他技能的分工

| 技能 | 分工 |
|---|---|
| `citation-management` | 文献检索、元数据抽取、BibTeX 生成与格式转换。**本技能的上游**：先用它把文献条目规范化，再交给本技能核验 |
| `literature-review` | 系统性文献综述的选题、筛选、主题梳理。产出文献集合，不做真实性判定 |
| `paper-lookup` | 单篇论文的定位与元数据获取。是查具体一篇时的入口 |
| `source-credibility-evaluation-protocol` | 来源可信度评估（来源权威性、时效性、立场）。本技能只管"是不是真的"，它管"值不值得信" |
| `scientific-writing` | 论文正文写作与行文。改稿阶段配合使用 |
| `venue-templates` | 目标期刊/会议的投稿模板与格式要求。引用格式合规性用它核对 |
| `peer-review` | 模拟审稿与评审意见。本技能的报告可作为审稿输入，但本技能不下审稿结论 |
| `scholar-evaluation` | 学者评价（学术履历、贡献评估）。与本技能无关 |
| `grant-proposal-writer` | 基金申请书写作。申请书里的引文核验用本技能 |
| `research-grants` | 基金政策、申报流程与指南解读。与引文核验无重叠 |
| `citation-audit` | **本技能**：引文真实性核验 + 正文/文献表编号对账，只报矛盾不报缺失 |

典型衔接：

```
citation-management（检索 + 规范化）
        ↓
citation-audit（本技能：真实性 + 编号对账）
        ↓
venue-templates（格式合规）
        ↓
scientific-writing（定稿）
```
