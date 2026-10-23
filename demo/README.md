# 教学交付物最小本地 Demo

**输入课程信息 → 大纲 → 教案 / 试卷 / PPTX / 讲义 + 一份机器自检报告。**

纯标准库，Python 3.9+，不装任何第三方包。

---

## 🧱 为什么中间有一层「大纲」

教案和课件如果**各自写出来**，改了教案忘了改课件就只能靠事后核对去发现——
既慢，又没人能保证自己每次都核对。

本 Demo 把这件事倒过来：

```
课程信息 ──▶ 大纲（唯一事实源）──┬─▶ 教案 Markdown
                               ├─▶ 课件 PPTX
                               └─▶ 讲义 Markdown（讲稿从课件导出）
```

教案与课件**不再各自被写出来**，而是从同一份大纲**派生**。
⇒「教案与课件对不上」这个失败模式，在结构上**不可能发生**；
真要改，改的是大纲一处，两边一起动。

对齐仍然**可被检查**（判据必须能证伪），但形态变了：守卫查的是
**「派生结果 == 重新派生的结果」**，而不是「两份文件碰巧一样」。

在线模式因此也**少一次模型调用**：课件与教案不再各问模型一次。

大纲里还带一份 **UbD 骨架**（持久理解 / 基本问题 / GRASPS / WHERETO）——
回答「这次课凭什么这样设计」，而不只是「这次课怎么讲」。

---

## 30 秒跑通（不需要 API key）

```bash
python demo\run_demo.py --out demo\out
```

产出（在 `demo/out/`）：

| 文件 | 内容 |
|---|---|
| `outline.spec.json` | **大纲**（唯一事实源，也是"模型写了什么"的审计凭据） |
| `教案.md` | 按 `skills/teaching-file-builder` 的十二节结构 |
| `试卷.md` | 按 `skills/exam-question-bank` 的六节结构（A 卷 + 备用卷 B + 覆盖矩阵） |
| `幻灯片.pptx` | 由仓库自研的纯标准库 PPTX 生成器产出，PowerPoint 可直接打开并继续编辑 |
| `讲义.md` | 逐页课件 + **该页讲稿**（讲稿从课件规格导出，**与课件逐字同源**） |
| `自检报告.md` / `.json` | 每一件交付物的机器自检结果 |
| `*.spec.json` | 其余规格（中间产物，也是"模型写了什么"的审计凭据） |

自检全部通过时进程退出码为 0，有 ERROR 时为 1。

## 在线模式（让模型写大纲）

```bash
set JFA_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
set JFA_LLM_API_KEY=...
set JFA_LLM_MODEL=qwen-plus
python demo\run_demo.py --input demo\course_input.example.json --mode live --out demo\out
```

任何 **OpenAI 兼容**的 `/chat/completions` 端点都能用：

| 供应商 | base_url | model |
|---|---|---|
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 本地 Ollama | `http://127.0.0.1:11434/v1` | 任意已拉取的模型 |

在线模式下**两次**模型调用：大纲 1 次（课件与课件讲稿由它派生）、
试卷 1 次（试卷按课程目标编号组织，不从单次课的环节派生）。

### 模型按用途路由

不同用途的活儿难度差别很大：画大纲是长程结构，画课件页是「一页几行、字数受限」，
审校是挑毛病。用同一个模型 ⇒ 要么课件页太长被 L03/L04 判红，要么大纲写得太干。

| 用途 | 覆盖的任务 | 环境变量 |
|---|---|---|
| `plan` | 大纲 / 教案 / 试卷 | `JFA_LLM_MODEL_PLAN` |
| `slides` | 课件 / **单页重生成** | `JFA_LLM_MODEL_SLIDES` |
| `handout` | 学生阅读版讲义 | `JFA_LLM_MODEL_HANDOUT` |
| `lint` | 模型审校 | `JFA_LLM_MODEL_LINT` |

都没设时回退 `JFA_LLM_MODEL`。

### 增量重生成：只重跑一页

改了一页不必重跑整份：

```bash
# 离线：把新页面的 JSON 替换进去，其余页逐字不动
python demo\outline.py --regen-page P5 --page-file new_page.json --out demo\out

# 在线：只调**一次**模型重写那一页（其余页沿用已有大纲）
python demo\run_demo.py --mode live --outline demo\out\outline.spec.json \
       --regen-page P5 --out demo\out
```

两条路径都会**逐页比对指纹**：只重跑一页 ⇒ 其余页必须一字未动；
动了别的页 ⇒ 立即报错（增量替换漏到了别处）。
页能定位到，是因为大纲里每页都有**稳定 id**（`P1`/`P2`/…）。

### 其它在线开关

```bash
python demo\run_demo.py --mode live --handout-extra   # 额外生成「学生阅读版讲义」
python demo\run_demo.py --mode live --lint             # 额外做一次模型审校
```

### 提示词里的规则**来自仓库自己的技能文档**

`demo/llm.py` 把 `skills/teaching-file-builder`、`skills/exam-question-bank`、
`skills/teaching-slide-designer` 三份 SKILL.md 的相关章节**摘出来**塞进提示词，
而不是在这里另写一套。技能改了，提示词跟着改 —— 不存在两份规则。

---

## 自检查什么

这才是 Demo 的重点：**不是「AI 帮你写教案」，是「给你一份能直接交上去、而且它自己检查过的文件」**。

### 大纲（`demo/selfcheck.py`，OL-P01–OL-P19）

| 判据 | 内容 |
|---|---|
| OL-P03/P04/P05 | **时间三层闭合**：本次课分钟 = Σ 模块分钟 = Σ 环节分钟 |
| OL-P06/P07 | 每个环节/模块绑定的目标都存在于教学目标里 |
| OL-P08 | 每个环节都有教师活动/学生活动/**设计意图** |
| OL-P09 | 环节既没有页面也没写 `no_slide_reason` ⇒ 分不清是「不投影」还是「漏做课件」 |
| OL-P10 | 每页正文课件都有讲稿 |
| OL-P11 | **封面唯一**：全稿 `title` 版式最多一个（续讲课的分节页用 `section`，合法） |
| OL-P12/P13/P14 | 目标 3–5 条 / 绑定课程目标编号 / 预设提问 ≥ 3 |
| OL-P01/P02 | 全文无占位符残留；留空的事实字段进了需人工核验清单 |
| **OL-P15** | **UbD · 持久理解**：1–3 条，每条必须写成「学生能理解 …… 并在 …… 情境中用它」（缺任一半即报错 —— 写成了知识点就无法迁移） |
| **OL-P16** | **UbD · 基本问题**：3–5 个，不允许写成能背定义回答的题（「什么是频域？」⇒ 红） |
| **OL-P17** | **UbD · GRASPS**：六要素齐全；缺 G/R/A/S 记 WARN，**缺 P（产物）/ S（标准）记 ERROR** |
| **OL-P18** | **UbD · WHERETO**：七项都要写明「落在哪个环节」，且该环节真实存在；**E·Experience 与 R·Rethink 的说明不得为空**（最常漏的两项） |
| **OL-P19** | 每页有**稳定 id** 且不重复 —— 增量重生成靠它定位 |

### 讲义（`demo/selfcheck.py`，HD-P01–HD-P04）

| 判据 | 内容 |
|---|---|
| HD-P01 | 每页有 id 且不重复 |
| HD-P02 | 正文页讲稿不为空 |
| HD-P03 | 讲义页数与课件一致；每页都能在课件里找到 |
| **HD-P04** | **讲义讲稿与课件讲稿逐字相同** —— 不一致 ⇒ 有人绕过派生层手改了讲义 |

### 教案（`demo/selfcheck.py`）

| 判据 | 内容 |
|---|---|
| LP-P04 | 各环节时间合计 **必须等于** 本次课总时长（不是流水账） |
| LP-P06 | 教学目标 3–5 条 |
| LP-P07/P08 | 目标用可观察动词；不用"了解/熟悉/掌握" |
| LP-P09 | 每条目标绑定课程目标编号（目标—证据可对齐） |
| LP-P10/P11 | 每一段教学过程都有教师活动/学生活动/**设计意图**/对应目标 |
| LP-P12 | 预设提问 ≥ 3，且有预期回答 |
| LP-P01 | 全文无占位符残留 |
| LP-P02 | 留空的事实字段（课程代码/教师/日期/教材）**必须**进需人工核验清单 |

### 试卷（`demo/selfcheck.py`）

| 判据 | 内容 |
|---|---|
| EX-P08 | 各题分值合计 **必须等于** 总分 |
| EX-P09/P10/P11 | 目标—题型映射、认知层次分布、难度分布**三张表各自合计 = 总分** |
| EX-P03/P04/P05 | 每题有题干、答案、**评分细则** |
| EX-P06/P07 | 每题绑定考核目标、认知层次、难度 |
| EX-P13 | 有备用卷 B（防泄题） |
| EX-P01 | 全文无占位符残留 |

### 幻灯片（复用仓库自带的 `slide_spec_lint.py`）

L01–L15 全部生效：一页几条要点、标题是不是断言、讲稿有没有、
封面是否唯一、有没有"如上图"这种线性指代、事实类页面有没有来源标注……

判据**不重写一份** —— 直接加载 `skills/teaching-slide-designer/scripts/slide_spec_lint.py`，
避免两份规则漂移。

---

## 自检会不会在空转？

```bash
python demo\selftest.py
# selftest: 57/57 checks passed
```

35 个变异用例，每个注入一处典型错误（时间合计不符、目标没绑定编号、
占位符残留、分值合计 ≠ 总分、缺评分细则、一页 9 条要点、封面出现两次、
大纲层少 minutes / 模块分钟对不上 / 环节绑错目标 / 环节无页面也没写原因、
**UbD 缺骨架 / 持久理解写成知识点 / 基本问题写成能背的题 / GRASPS 缺产物 /
WHERETO 落在不存在的环节 / 页面没有 id**、
**讲义讲稿被手改 / 讲义少一页**……），
要求**指定的判据**必须报出来。另有 5 项基线检查、12 项在线路径接线检查
（提示词能否从技能文档摘到规则、模型返回带围栏/带废话时 JSON 能否提取），
以及 3 项**不变量测试**（增量重生成只动一页；模型按用途路由）。
只跑绿不算数 —— 必须证明它会红。

仓库级守卫另有一层（`scripts/verify_repo.py`）：**教案与课件确由大纲派生**
（重算一遍，与已提交示例逐字段比对）+ **离线 Demo 真的走了大纲层**
（产物里必须有大纲凭据）+ **增量重生成只动一页** + **模型四档用途齐全**
+ **变异测试覆盖了 UbD / 页面 id / 讲义同源这些规则码**。它同样配了变异用例。

---

## 边界（说清楚比吹得漂亮重要）

- **只保证形式站得住**：自检管的是「时间对不对、分值对不对、有没有编造、格式齐不齐」，
  **不管教学内容本身对不对** —— 那是教师的事。
- **不做 DOCX**：教案与试卷目前输出 Markdown。导出成学校模板的 DOCX 需要一个
  纯标准库的 DOCX 写出器（下一步）；本仓库不依赖运行时的 `docx` 技能
  （那不随包分发，违反 S12）。
- **在线模式会把课程信息发给模型端点**：默认离线模式不会联网。
- **示例内容是编的**：示例课程「数字图像处理」与其中的题目、答案、参数**均为演示用途的虚构内容**，
  不是真实教材或真实考试。真要用请替换 `demo/spec/outline.example.json` 与 `exam_paper.example.json`。

## 目录

```
demo/
├── run_demo.py              # 主程序：读输入 → 大纲 → 派生/生成 → 渲染 → 自检报告
├── outline.py               # 大纲先行层：大纲 → 教案 / 课件 / 讲义 的派生器（--check 自证 / --regen-page 增量重生成）
├── selfcheck.py             # 大纲/教案/试卷/讲义的形式合规判据 + 幻灯片判据的加载
├── llm.py                   # OpenAI 兼容客户端 + 按用途路由 + 从技能文档摘规则
├── selftest.py              # 判据的变异测试（57/57）
├── course_input.example.json  # 示例课程信息（在线模式的输入）
├── prompts/                 # 七个任务的任务书与输出结构
│   ├── outline.md
│   ├── lesson_plan.md
│   ├── exam_paper.md
│   ├── slides.md
│   ├── page.md              # 单页重生成（增量重生成用的任务书）
│   ├── handout.md           # 学生阅读版讲义
│   └── lint.md              # 模型审校
├── spec/                    # 示例大纲（唯一事实源）+ 示例试卷规格
│   ├── outline.example.json
│   ├── lesson_plan.example.json     # ← 由大纲派生（--regen 可重生成）
│   ├── slides.example.json          # ← 由大纲派生（--regen 可重生成）
│   ├── handout.example.json         # ← 由大纲派生（--regen 可重生成）
│   └── exam_paper.example.json
└── out/                     # 运行产物（不进版本库、不进分发包）
```
