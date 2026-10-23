---
name: openmaic-courseware
description: 用于把 OpenMAIC 互动课堂引擎接入教学课件产出链：探测能力、提交异步生成任务、轮询到终态并取回可访问的课堂地址；触发词：OpenMAIC、互动课堂、课件产出、课堂生成、courseware。
license: MIT
metadata:
  domain: 课程体系
  version: "1.0"
  origin: 原创（方法论内核适配自 OpenMAIC，MIT / THU-MAIC）
---

# OpenMAIC 互动课堂接入

## 这个技能解决什么

教师要的不是"会调一个 API"，而是**知道什么时候值得把课件产出交给引擎、怎么提交、怎么等、出错了怎么判断是"设计使然"还是"接线故障"**。

OpenMAIC 是能生成**互动课堂**（多页、可交互、带讲解动作）的引擎。它对本仓库的价值是**一条可选加速路径**：课件需要"学生点选 / 拖拽 / 逐步揭示"这类互动页时，交互动作的编排成本很高，交给它产出能省下逐页手写动作脚本的时间。

**定位边界（不能含糊）**

- **OpenMAIC 是可选加速路径，不是唯一路径。** 本仓库自带的 `teaching-file-builder`（教学文件）、`teaching-slide-designer`（幻灯片）、`paper-to-talk-designer`（汇报叙事）才是**主线**，不依赖外部服务，离线也能跑完。
- **OpenMAIC 本体不随本仓库分发。** 本技能随包分发；OpenMAIC 要使用者自己 clone 部署。本技能只提供**部署增量编排**与**契约文档**，不含上游源码。
- **生成内容里的事实性内容仍受本仓库纪律约束。** 数据、文献、案例不得编造；引擎生成的课堂交付前**必须人工核事实**。引擎负责"形式与交互"，不负责"事实为真"。
- **成本是真实的。** 每次生成都是一次真实上游调用；重复提交、轮询过密、盲目重跑都直接烧钱。

## 什么时候用

**用：** 需要学生可交互的课堂页（点选、分支、拖拽、逐步揭示）；一次产出多页结构化课堂且含讲解动作；上线前要可演示版本供试讲或评审；已有本地或内网实例且有可用 provider 配额。

**不用：** 纯讲授型课程；只要一份 PDF 或幻灯片（`teaching-slide-designer` 更可控）；需要逐字可审计的讲稿（`paper-to-talk-designer` 更适合人工精修）；没有实例、没有配额或网络不许出内网（**不要为了用一次而临时搭一套**）；涉及学生个人信息或未公开科研数据。

**表 1 · 该不该用 OpenMAIC 的判据**

| 场景特征 | 结论 |
|---|---|
| 点选 / 拖拽 / 分支的互动页 | 划算：交互动作编排成本高 |
| 多页结构化课堂（含讲解动作） | 划算：手工搭壳重复劳动多 |
| 纯讲授大纲 / 知识点清单 | 不划算：改用 `scope-and-sequence-designer` |
| 只要一份幻灯片 | 不划算：改用 `teaching-slide-designer` |
| 需逐字可审计的讲稿 | 不划算：引擎产出须人工精修 |
| 学生数据 / 未公开科研数据 | 禁止送外部：合规边界不清 |
| 只想"试一次" | 不划算：部署与配额成本大于收益 |

## 输入

- **目标课堂定位**：受众、时长、互动需求；缺失则无法设定验收标准。
- **需求描述文本**：对应 `requirement` 字段；必填，缺失返回 `400 MISSING_REQUIRED_FIELD`。它是**唯一的内容输入**，越具体产出越可判。
- **OpenMAIC 基址**：本机或内网实例根地址；缺失则无法调用。
- **是否已配访问码**：实例是否设置 `ACCESS_CODE`；未配却发鉴权请求，或配了没先 verify，都会被拦。
- **provider 配置状态**：`capabilities` 四项实际状态；缺失则无法判断该开哪个开关。
- **期望交付形态**：可编辑源文件 / 可放映版本；缺失则验收表无法填。

## 执行步骤

**步骤 1 · 先判断该不该用。** 过一遍「表 1」。不划算就**停在这里**，改走主线技能，并在交付说明里写清结论 —— 别让下游误以为生成失败。

**步骤 2 · 部署与健康探测。** `GET /api/health` → 看 `success` 与 `status` 是否为 `"ok"`，再读 `capabilities` 四项。实例起不来先看 `references/deployment.md`。

> **`version` 字段不可信**（可能是占位值）。**不要用版本号做特性门控**，用 `capabilities` 判断能力。

**步骤 3 · 鉴权准备。** 先 `GET /api/access-code/status`：`enabled:false` → 未设 `ACCESS_CODE`，直接继续；`enabled:true` → 先 `POST /api/access-code/verify`，body `{"code":"<访问码>"}`，拿到 `openmaic_access` cookie 后再访问受保护端点。

> **本地部署不支持 `Authorization: Bearer`**（托管版 `open.maic.chat` 的用法）；本地发 Bearer 头不在鉴权层被拒，而是延后报错。

**步骤 4 · 能力探测与开关对齐。** `capabilities` 四项：`webSearch` / `imageGeneration` / `videoGeneration` / `tts`。

> **只把对应 flag 置 `true`**（`enableWebSearch` / `enableImageGeneration` / `enableVideoGeneration` / `enableTTS`）。不支持的能力被强开通常表现为中途失败或挂起；**服务器若不返回 `capabilities`（旧版实例）**，就不要发任何新的开关字段。

**步骤 5 · 提交生成任务。** `POST /api/generate-classroom`，body 字段见「表 2」。响应 202，取 `jobId`。

**表 2 · 提交请求体字段**

| 字段 | 说明 |
|---|---|
| `requirement` | 必填：需求描述文本 |
| `pdfContent` | 参考材料 |
| `enableWebSearch` | 仅当 `capabilities.webSearch` 为 `true` |
| `webSearchProviderId` / `webSearchApiKey` / `webSearchModelId` | 搜索三项配置 |
| `baiduSubSources` | 搜索子源配置 |
| `enableImageGeneration` | 仅当 `capabilities.imageGeneration` 为 `true` |
| `enableVideoGeneration` | 仅当 `capabilities.videoGeneration` 为 `true` |
| `enableTTS` | 仅当 `capabilities.tts` 为 `true` |
| `agentMode` | 生成模式 |

> **一次只提交一个任务。** 提交后无法修改。

**步骤 6 · 轮询到终态。** `GET /api/generate-classroom/{jobId}`，**约 60 秒一次**。`status ∈ {queued, running}` 是进行中；`status ∈ {succeeded, failed}` 是终态，停止轮询；终态布尔 `done` 与 `status` 交叉校验。字段：`status`（终止判据）、`step`（进度阶段）、`progress`（粗略感知）、`error`（失败输入）。

> **单次轮询失败绝不重提任务。** 抖动与偶发 5xx 只是"这一次没拿到"，**不是"任务不存在"**；正确做法是**等约 60 秒后重试同一个 job**，重提会生成**重复课堂**并再耗一次配额。单轮上限约 10 分钟；服务端对**超过 30 分钟无更新的 running 任务**会读作 failed。

**步骤 7 · 取回课堂地址。** 成功时读 `result.classroomId` 与 `result.url`。

> **自己拼 URL，不要盲信响应里的 `pollUrl` 的 host。** 它的 origin 来自 `x-forwarded-host` 或请求 origin，在反代 / 容器部署下常指向**外部访问不到**的地址。用**确认可达的基址 + `result.url` 路径**拼出最终地址。

**步骤 8 · 失败分类与处置。** 把失败映射到「表 3」，按表处置。

> **「空结果」必须先问：设计的还是故障的？**
> - **设计使然**：门按预期拦下（能力未开启却请求该能力）、任务本就不产出该字段、鉴权被拒 —— **预期行为**，记录后继续。
> - **接线故障**：一个字都没产出、全臂报错、服务端日志为空 —— **接线坏了**，整轮作废，修好再跑。
>
> 两者在报表上都表现为"结果为空"。**先分清再决定要不要重跑** —— 否则要么白跑，要么漏掉真故障。

**表 3 · 失败分类与处置**

| 信号 | 分类 | 根因假设 | 处置动作 | 重试 |
|---|---|---|---|---|
| health 非 200 / 连接失败 | 接线故障 | 实例没起、端口错 | 查部署与端口 | 否 |
| `/api/stages*` 纯文本 404 | 接线故障 | runtime 与数据库变量未同时满足 | 补环境变量 | 否 |
| verify 或受保护端点 401 / 403 | 鉴权问题 | 没先 verify 或访问码不对 | verify 后持久化 cookie | 否 |
| `failed`，error 指向能力 | 能力缺失 | 请求了不支持的开关 | 对齐 `capabilities` | 修好后重提 |
| `failed`，error 指向限流 | 上游限流 | provider 配额受限 | 降频、错峰、换配额 | 是（退避） |
| `failed`，error 指向生成 | 任务失败 | 需求文本或上游异常 | 读 error 改需求 | 视情况 |
| 轮询单次失败 | 接线故障（瞬时） | 网络抖动、实例重启 | **等约 60 秒重试同一 job** | 是（同 job） |
| 响应是纯文本非 JSON | 接线故障 | 404 或代理错误页 | 看状态码与原文 | 视情况 |
| 结果为空但门正常拦截 | 设计使然 | 预期行为 | 记录，继续 | 否 |

> 字段名、端点、错误码的完整定义见 `references/api-contract.md`；部署与排障见 `references/deployment.md`。

## 输出模板

**表 4 · 能力探测记录表**

| 端点 | 探测结果 | 结论 | 下一步 |
|---|---|---|---|
| `GET /api/health` | `status=ok`；`capabilities` 四项取值 | 支持 / 不支持 / 未返回 | 只把为 `true` 的项在请求里置 `true` |
| `GET /api/access-code/status` | `enabled=?` `authenticated=?` | 需鉴权 / 无需鉴权 | 需鉴权则先 verify |

**表 5 · 任务提交与轮询记录表**

| jobId | 提交时间 | 轮询次数 | status+step+progress | 终态 | 耗时 |
|---|---|---|---|---|---|
| | | | | `succeeded` / `failed` | |

**表 6 · 失败分类处置表**

| 信号 | 分类 | 根因假设 | 处置动作 | 重试 |
|---|---|---|---|---|
| | | | | |

**表 7 · 产出验收表**

| 课堂 URL | 页数 | 互动点 | 事实核验项 | 责任人与结论 |
|---|---|---|---|---|
| | | | 数据 / 文献 / 案例逐条核 | |

## 中国高校语境要点

- **双形态交付**：存档要**可编辑**（源文件）与**可放映**（演示、直播）两种。互动课堂的网页形态**不能替代**这两份；主线技能负责双形态，OpenMAIC 负责互动形态。
- **三类课堂场景**：**机房**（学生自己动手，交互要抗误操作、有回退）、**大教室**（投影距离远，字号对比度更高）、**线上直播**（延迟高，互动动作要有等待提示）。
- **中文排版与字体**：中英混排、公式、上下标常见；放映前必须查字体替换导致的换行错位、公式缺字、标点挤压。
- **课程思政要点不能被自动生成带偏**：要点要人工给定并落在明确位置，不能指望引擎"自然带出"。
- **生成后必须人工核事实**：引擎会**自信地编出**具体数据、文献与案例。逐条核对，核不上的**删掉**。
- **访问码与内网部署的安全边界**：对外暴露时**访问码是唯一屏障**，需配反代、限流与定期轮换。
- **学生数据不进外部服务**：涉及学生姓名、学号、成绩、作业的素材**一律不送**外部服务；个性化需求用主线技能本地处理。
- **本地 GPU 资源占用**：本地部署 + 本地模型占显存与内存；并行其它任务时注意资源争抢，**别和别的服务抢同一个宿主端口**。

## 易错点

1. **不做 health 探测就提交** —— 只能靠报错反推能力。
2. **把 `capabilities` 全置 `true`** —— 不支持的能力被强开，表现为中途失败。
3. **盲信 `pollUrl` 的 host** —— 反代 / 容器部署下常指向不可达地址。
4. **轮询间隔太密** —— 秒级轮询烧配额，还易被限流。
5. **单次轮询失败就重提任务** —— **最贵的错**：生成重复课堂再付费；应重试**同一个 job**。
6. **把 `failed` 当"还没好"继续等** —— `failed` 是终态。
7. **用 `version` 做特性判断** —— `version` 不可信，须用 `capabilities`。
8. **以为本地支持 `Authorization: Bearer`** —— 本地只认 `openmaic_access` cookie。
9. **没先 verify 就访问受保护端点** —— 白跑一轮。
10. **把 404 纯文本当 JSON 解析** —— `/api/stages*` 未配 runtime 时返回纯文本 `Not found`。
11. **把生成的课堂当成"事实已核验"** —— 引擎只负责形式与交互。
12. **以为 OpenMAIC 随包分发** —— 本体不在包里，要自己 clone。

## 自检清单

1. [ ] 已用「表 1」判断该不该用，并记录结论。
2. [ ] 已执行 `GET /api/health` 并记录 `capabilities` 四项。
3. [ ] 特性判断依据是 `capabilities`，不是 `version`。
4. [ ] 已执行 `GET /api/access-code/status`。
5. [ ] 若 `enabled:true`，已先 verify 并带上 `openmaic_access` cookie。
6. [ ] 未使用 `Authorization: Bearer`。
7. [ ] 请求体开关字段与 `capabilities` **逐项一致**。
8. [ ] 服务端未返回 `capabilities` 时，请求体无额外新开关字段。
9. [ ] 任务**只提交了一次**，`jobId` 已记录。
10. [ ] 轮询间隔约 60 秒，不是秒级。
11. [ ] 轮询上限约 10 分钟，超时按服务端 30 分钟无更新口径判定。
12. [ ] 只在 `succeeded` / `failed` 停轮询。
13. [ ] 单次轮询失败时重试**同一个 job**，没有重提任务。
14. [ ] 课堂 URL 由可达基址 + `result.url` 路径拼出，未盲信 `pollUrl`。
15. [ ] 失败已按「表 3」分类，区分了"设计使然"与"接线故障"。
16. [ ] 已逐条核对数据、文献、案例，核不上的已删改。

## 交叉技能

**表 8 · 交叉技能**

| 技能 | 方向与衔接点 |
|---|---|
| `teaching-file-builder` | 主线→OpenMAIC：教学文件→需求描述 |
| `teaching-slide-designer` | 主线→OpenMAIC：幻灯片→互动页 |
| `paper-to-talk-designer` | 主线→OpenMAIC：叙事→互动版 |
| `scope-and-sequence-designer` | 上游→本技能：大纲→需求描述 |
| `backwards-design-unit-planner` | 上游→本技能：单元目标→互动点 |
| `authentic-context-course-designer` | 上游→本技能：真实情境→场景素材 |
| `project-brief-designer` | 上游→本技能：项目约束→需求边界 |
| `dual-coding-designer` | 上游→本技能：图文并置→图文配对 |
| `cognitive-load-analyser` | 上游→本技能：认知负荷→互动点上限 |
| `formative-assessment-technique-selector` | 上游→本技能：评价形式→可承载题型 |
| `vocational-task-course` | 上游→本技能：职业任务→情境设计 |
| `he-context-adapter` | 上游→本技能：高校语境→场景选择 |
| `source-credibility-evaluation-protocol` | 质量把关：文献与案例核验 |
| `citation-audit` | 质量把关：引文逐条核对 |
| `feynman-diagnostic-cycle` | 质量把关：复述检验→互动逻辑 |

## 方法论依据

- **能力探测优先于调用（capability-first）**：先问"你有什么"，再问"你要什么"。用 `capabilities` 而非版本号做门控，因为版本字段不可信；探测前置才能让失败变成"前置判断"而非"事后归因"。
- **异步任务的状态机与终态判定**：难点不是"发出去"，而是"什么时候算结束"。显式四态（`queued` / `running` / `succeeded` / `failed`）+ 终态布尔 `done` 交叉校验，只在终态停；`running` 超时按服务端"30 分钟无更新读作 failed"兜底。终态判错就会"任务已死还在等"或"成功被判失败"。
- **空结果的两类成因（设计使然 vs 接线故障）**：最核心的判读纪律。**设计使然**是门按预期拦下，信号是"门通过 0/0 但有拦截记录"；**接线故障**是产出一个字都没有，信号是"全臂报错或全臂空且无拦截记录"。混为一谈会瞎改配置或漏掉真故障 —— 都等于白烧配额。
- **事实与表达的分离**：引擎优化的是"表达与交互形式"，不是"事实为真"。因此把"生成"与"核验"拆两段，验收表里事实核验项与责任人是必填。形式可交给工具，事实必须有人签字。
