# OpenMAIC API 契约速查

> 面向使用者的契约速查。**字段名与语义按上游实现逐条核实**；未实跑 / 未核实的条目集中列在第 7 节，**不要当成事实使用**。
> 与 `SKILL.md` 配套：`SKILL.md` 讲"怎么做"，本文讲"线长什么样"。

## 1. 两套响应包装（最容易踩的坑，先讲）

| 包装 | 形状 | 谁在用 |
|---|---|---|
| `apiSuccess(data)` | 响应体是 `{"success": true, ...业务字段}` —— **业务字段平铺在同一层，没有 `data` 嵌套** | 绝大多数端点 |
| `ownerJson(body)` | **裸 body，没有任何信封** | `/api/stages*` 全部端点 |

错误信封：`{"success": false, "errorCode": "...", "error": "...", "details": "..."}`（`details` **可能不存在**）。

**404 可能是纯文本 `Not found`（不是 JSON）** —— 客户端必须容忍：先看状态码与响应原文，再决定要不要解析；直接 `JSON.parse` 会抛异常并把整条流程带崩。

**唯一带 `data` 嵌套的端点是 `POST /api/parse-pdf`**（`{success, data:{...}}`）。

## 2. 鉴权

- **全局 access-code 门**：`ACCESS_CODE` **未设 = 无鉴权**；设了 = 除白名单（`/api/access-code/*`、`/api/health`）外，**全部要求 `openmaic_access` cookie**。
- **换 cookie**：`POST /api/access-code/verify`，body `{"code": "<非空字符串>"}` → 200 `{"success":true,"valid":true}`，并下发 `Set-Cookie: openmaic_access`（httpOnly / sameSite=lax / path=/ / maxAge 604800 秒）。**token 不在响应体里**，只能从 cookie 拿。
- **本地部署不支持 `Authorization: Bearer`** —— 那是托管版 `open.maic.chat` 的用法。
- **状态查询**：`GET /api/access-code/status` → `{"success":true,"enabled":bool,"authenticated":bool}`。
- **owner 隔离 cookie** `anonymous_id`（UUIDv4，首次请求下发）—— **客户端必须持久化**，否则每次请求都换一个 owner 分区，历史与归属都不稳定。

## 3. 端点表

### 3.1 健康与访问码

| 方法 | 路径 | 请求 | 成功响应 | 错误 | 鉴权 |
|---|---|---|---|---|---|
| GET | `/api/health` | 无 | `{success, status:"ok", version, capabilities:{webSearch,imageGeneration,videoGeneration,tts}}` | — | 免鉴权（白名单） |
| GET | `/api/access-code/status` | 无 | `{success, enabled, authenticated}` | — | 免鉴权 |
| POST | `/api/access-code/verify` | JSON `{"code": "..."}` | 200 `{success, valid:true}` + `Set-Cookie` | 400 `invalid JSON body`；401 `Invalid access code`；429 `RATE_LIMITED`（需 `TRUST_PROXY_HEADERS=true`） | 免鉴权 |

### 3.2 阶段与场景（`/api/stages*`，全部裸 body）

| 方法 | 路径 | 请求 | 成功响应 | 错误 | 鉴权 |
|---|---|---|---|---|---|
| GET | `/api/stages` | 无 | 裸 `{stages:[{id,name,description?,interactiveMode?,taskEngineMode?,createdAt,updatedAt,sceneCount,folderId?}]}` | 404 **纯文本** `Not found`（agent runtime 未配置）；500 纯文本 | 需鉴权 |
| POST | `/api/stages` | JSON `{name(必填,≤120字符), description?}` | 201 裸 `{stage:{id,name,description?,createdAt,updatedAt,sceneCount}}` | 400 `MISSING_REQUIRED_FIELD` / `INVALID_REQUEST` | 需鉴权 |
| GET | `/api/stages/{id}` | 无 | 裸 `{stage, scenes, outline, dslVersion?}` | 404 纯文本 | 需鉴权 |
| PATCH | `/api/stages/{id}` | JSON `{name(必填,非空,≤120)}` | `{success:true, name}` | 400 `INVALID_REQUEST` | 需鉴权 |
| PUT | `/api/stages/{id}` | JSON `{stage:{id,...}, scenes:[...]}`；**`stage.id` 必须等于路径 id** | `{success:true}` | 400 `INVALID_REQUEST`（id 不匹配 / 结构非法 / 版本冲突）；404 纯文本 | 需鉴权 |
| DELETE | `/api/stages/{id}` | 无 | `{ok:true}` | 404 纯文本 | 需鉴权 |
| GET | `/api/stages/{id}/scenes?ids=a,b` | query `ids` 逗号分隔；去重、≤200 | 裸 `{scenes:[...]}`（只返命中的，按文档顺序） | 400 `empty_scene_ids`；400 `too_many_scene_ids`；404 纯文本 | 需鉴权 |
| GET | `/api/stages/{id}/manifest` | 无 | 裸 `{rev, scenes:[{id,order,rev}]}` | 404 纯文本 | 需鉴权 |
| POST | `/api/stages/{id}/publish` | 无 | 200 `{success:true, publishedAt, name}` | **这一族用 `{error:"..."}` 而非错误信封**：401 `login_required` / 404 `not_found` / 403 `forbidden` / 500 `internal_error` | 需鉴权（另有登录态要求） |

### 3.3 课堂生成（`/api/generate*`）

| 方法 | 路径 | 请求 | 成功响应 | 错误 | 鉴权 |
|---|---|---|---|---|---|
| POST | `/api/generate-classroom` | JSON `{requirement(必填), pdfContent?, enableWebSearch?, webSearchProviderId?, webSearchApiKey?, webSearchModelId?, baiduSubSources?, enableImageGeneration?, enableVideoGeneration?, enableTTS?, agentMode?}` | 202 `{success, jobId, status:"queued", step:"queued", message, pollUrl, pollIntervalMs}` | 400 `MISSING_REQUIRED_FIELD`；500 `INTERNAL_ERROR` | 需鉴权 |
| GET | `/api/generate-classroom/{jobId}` | 无 | `{success, jobId, status, step, progress, message, pollUrl, pollIntervalMs, scenesGenerated?, totalScenes?, result?, error?, done}` | 400 / 404 的 `errorCode` 都是 **`INVALID_REQUEST`**（不是 NOT_FOUND） | 需鉴权 |
| POST | `/api/generate/scene-content` | JSON `{outline(必填), allOutlines(必填非空), stageId(必填), stageInfo?, pdfImages?, imageMapping?, agents?, languageDirective?, requirements?}` | `{success, content, effectiveOutline}` | 400 `MISSING_REQUIRED_FIELD`；500 `GENERATION_FAILED`；上游 429 → `RATE_LIMITED` | 需鉴权 |
| POST | `/api/generate/scene-actions` | JSON `{outline(必填), allOutlines, content, stageId, agents?, previousSpeeches?, userProfile?, languageDirective?}` | `{success, scene, previousSpeeches}` | 400；500 `GENERATION_FAILED` | 需鉴权 |
| POST | `/api/generate/scene-outlines-stream`（SSE） | JSON `{requirements(必填), pdfText?, pdfImages?, imageMapping?, researchContext?, agents?}` | SSE，每帧 `data: <JSON>`，按 JSON 里的 `type` 分发：`languageDirective` / `courseTitle` / `outline` / `retry` / `done` / `error`；**每 15 秒一条 `:heartbeat` 注释帧，解析器必须忽略以 `:` 开头的行** | 流开始前 400 / 500；流开始后走 `type:"error"` 事件（HTTP 仍 200） | 需鉴权 |

### 3.4 课堂与 PDF

| 方法 | 路径 | 请求 | 成功响应 | 错误 | 鉴权 |
|---|---|---|---|---|---|
| POST | `/api/classroom` | JSON `{stage(必填), scenes(必填数组)}`；**id 由服务端生成** | 201 `{success, id, url}` | 400 `MISSING_REQUIRED_FIELD` / `INVALID_REQUEST`；409 `Classroom id collision` | 需鉴权 |
| GET | `/api/classroom?id=` | query `id` 必填 | `{success, classroom:{id, stage, scenes, createdAt}}` | 400 / 404（`errorCode` 仍是 `INVALID_REQUEST`） | 需鉴权 |
| POST | `/api/parse-pdf` | `multipart/form-data`，字段 `pdf` 必填，`providerId?` / `apiKey?` / `baseUrl?` | `{success, data:{...}}` | 400；403 `INVALID_URL`；500 `PARSE_FAILED` | 需鉴权 |

## 4. 状态机

- `status ∈ {queued, running, succeeded, failed}`
- `step ∈ {queued, initializing, researching, generating_outlines, generating_scenes, generating_media, generating_tts, persisting, completed, failed}`
- `done` = 终态布尔，与 `status` 交叉校验。
- **服务端对 30 分钟无更新的 running 任务会读作 failed** —— 客户端的超时口径要按这个来。

## 5. 模型选择 header

`x-model` / `x-api-key` / `x-base-url` / `x-provider-type` —— 可覆盖服务端默认的模型与 provider。

## 6. 已知的坑

1. **`version` 不可信** —— 可能是占位值（甚至 `0.1.0` 这类固定串），不能用来做特性门控；能力判断一律用 `capabilities`。
2. **`POST /api/generate-classroom` 的 `language` 字段在路由里没有被透传** —— 传了也不生效，**不要依赖它**。
3. **`publish` 在当前形态下 HTTP 路径必然 401** —— 这条是**源码推导，未实跑**（见第 7 节）。
4. **两套响应包装混用** —— `/api/stages*` 是裸 body，其它端点是 `apiSuccess` 平铺；按 `{success:...}` 读裸 body 会全部读成 `undefined`。
5. **`pollUrl` 的 host 不可信** —— origin 来自 `x-forwarded-host` 或请求 origin，容器 / 反代下可能不可达；最终地址要自己拼。

## 7. 未核实项清单

以下条目**未实跑或未核实**，只能作为线索，不能当结论：

- `publish` 必然 401 的结论是**源码推导，未实跑**。
- `progress` 各 step 的**具体数值**未通读。
- `totalScenes` **首次轮询**是否已带，未核实。
- `pdfContent.images` 元素的编码形式（data URL / base64 / asset id）未核实。
- `Scene` / `SlideContent` 的**完整 schema** 与 `validateScene` 的全部规则未通读 ⇒ **手工构造 `POST /api/classroom` 的 `scenes` 有风险**。
- `SceneOutline` **尾部字段**未读全。
- `MaicDocument.outline` 的确切 wire 形状未核实（storage 层是黑盒）。
- **CORS / OPTIONS / HEAD** 行为未核实。
- `MODEL_ROUTES` 的强制校验细节未核实。
