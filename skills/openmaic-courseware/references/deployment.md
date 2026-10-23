# OpenMAIC 增量部署指南

> 本文件只写**本仓库随包提供的增量部分**：怎么把 OpenMAIC 跑起来、怎么把本仓库的 override 接上去、怎么验收、怎么排障。
> **不复制上游 README / Dockerfile / docker-compose.yml 全文** —— 上游会升级，复制过来就会过期，也会造成"两份编排哪个生效"的困惑。上游内容一律以你 clone 下来的仓库为准。

## 1. 前置

- **Docker** + **Docker Compose v2**（用 `docker compose` 子命令，不是 `docker-compose`）。
- **Node 22.19+** —— **仅在不用容器、要本地直接跑时**需要；走容器编排不需要在宿主机装 Node。
- 磁盘与内存：视频导出 profile 的镜像很重，见第 5 节。

## 2. 获取 OpenMAIC 本体

**本仓库不随包分发 OpenMAIC 本体。** 需要你自己 clone：

```bash
git clone https://github.com/THU-MAIC/OpenMAIC.git /path/to/OpenMAIC
cd /path/to/OpenMAIC
```

- 托管版站点：`https://open.maic.chat`（其 `Authorization: Bearer` 用法**只适用于托管版**，本地部署不认，见 `references/api-contract.md`）。
- 许可：OpenMAIC 以 **MIT** 许可发布（Copyright (c) 2026 THU-MAIC）。本仓库的技能与增量编排同样按 MIT 适配并标注来源。
- 若上面的仓库路径有变动，以官方站点给出的地址为准 —— **clone 前先核对**，拉错仓库不要用。

## 3. 准备环境变量

最小必需清单（逐条：变量名 → 用途 → 缺了会怎样）：

| 变量 | 用途 | 缺了会怎样 |
|---|---|---|
| `DEFAULT_MODEL` | 默认模型名 | 服务端**无法解析模型**，生成请求直接失败 |
| `OPENMAIC_AGENT_RUNTIME_ENABLED` | 打开 agent runtime | `/api/stages*` 全部返回 **404 纯文本** |
| `DATABASE_URL` | 持久化数据库连接串 | 与上一条**同时**满足，`/api/stages*` 才不 404 |
| `MODEL_ROUTES` | 模型路由映射 | runtime 开启时**必须显式路由 `maic-agent-driver`**，否则驱动选不到模型 |
| `PERSISTENCE_DEV_TOKEN` | 持久化令牌（服务端侧） | 持久化链路不通 |
| `NEXT_PUBLIC_PERSISTENCE_TOKEN` | 持久化令牌（前端侧） | **必须与上一项完全一致**；它是**编译期变量**，改了要重新构建镜像 |
| `NEXT_PUBLIC_PERSISTENCE` | 前端持久化能力声明 | 前端不声明持久化能力，存取行为异常 |

**LLM provider：至少配一类。** 可选变量名：`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` / `QWEN_API_KEY` / `MINIMAX_API_KEY` / `GLM_API_KEY` / `KIMI_API_KEY` / `SILICONFLOW_API_KEY` / `DOUBAO_API_KEY` / `OPENROUTER_API_KEY` / `GROK_API_KEY` 等；也可以用 `OLLAMA_BASE_URL` 走**本地免 key** 路线。**一个都不配 = 没有可调用的模型**。

**可选能力（按需）**：web search / 图像 / 视频 / TTS 各自对应的变量名，**以上游 `.env.example` 为准**，不要凭空造名。它们与请求体的对应关系见 `references/api-contract.md`：搜索对应 `webSearchProviderId` / `webSearchApiKey` / `webSearchModelId` / `baiduSubSources`，图像 / 视频 / 语音对应 `enableImageGeneration` / `enableVideoGeneration` / `enableTTS`。

**访问与传输：**

| 变量 | 用途 | 缺了会怎样 |
|---|---|---|
| `ACCESS_CODE` | 全局访问码 | 可选。**设了就必须先 verify 换 cookie**，否则受保护端点一律 401 |
| `COOKIE_SECURE` | cookie 的 `Secure` 属性 | **纯 HTTP 部署必设为 `0`**：否则浏览器拒收 `Secure` cookie → owner 分区漂移、历史丢失 |

模板见 `deploy/env.local.example`，复制成 `.env.local`（**不要提交版本库**）。

## 4. 端口

- 容器内**固定 3000**。
- **宿主端口默认 3001**（避开 3000 的常用占用）。用环境变量 `OPENMAIC_HOST_PORT` 改。

## 5. 启动

```bash
# 基础编排
docker compose up --build

# 需要 PostgreSQL 持久化
docker compose --profile server-persistence up --build

# 需要 MP4 导出（镜像很重，慎用）
docker compose --profile video-export up --build
```

`video-export` profile 会拉入体量很大的媒体依赖，磁盘与构建时间都显著上升；**只在确实要做 MP4 导出时启用**。

## 6. 本仓库随包提供的增量编排

`deploy/docker-compose.jfa.yml` 是 **override 文件**（增量），用法：

```bash
cd /path/to/OpenMAIC
docker compose -f docker-compose.yml \
               -f /path/to/junior-faculty-agent/skills/openmaic-courseware/deploy/docker-compose.jfa.yml \
               up --build
```

它逐条只改这四件事：

1. **宿主端口** → `${OPENMAIC_HOST_PORT:-3001}:3000`（容器内仍是 3000）。
2. **`COOKIE_SECURE=0`** → 纯 HTTP 本地部署必须，否则浏览器拒收 `Secure` cookie。
3. **`ACCESS_CODE` 透传** → `${ACCESS_CODE:-}`，不设就是空，等于不开访问码。
4. **数据卷** → 追加 `openmaic-data:/app/data`（**追加而非覆盖**：用列表项追加语法，不重写上游的 `volumes`）。

**它不含上游全部服务定义**（`postgres`、`render-service` 等由上游 compose 提供，用 `--profile` 启用）—— **必须与上游 compose 同时使用**，单独跑这个 override 没有意义。

两点注意：

- 上游 compose 若也发布了宿主端口，Compose 会把两组端口**都**映射，3000 仍会暴露。要只保留 3001，**在上游 compose 里改端口**，或把 override 的 `ports` 段改成 `ports: !override`（需 Compose v2.24+，该写法不能被普通 YAML 解析器解析，故本文件保持标准 YAML）。
- 上游 compose 若用**列表形式**写 `environment`，本 override 的**映射形式**会与之冲突；此时把 override 里那两行改成列表形式（`- COOKIE_SECURE=0` / `- ACCESS_CODE=${ACCESS_CODE:-}`）。

## 7. 验收

起好之后依次验：

1. `GET /api/health` → 看 `status` 是否 `ok`，并**读 `capabilities` 四项**（`webSearch` / `imageGeneration` / `videoGeneration` / `tts`）；`version` 不可信。
2. `GET /api/access-code/status` → 看 `enabled` / `authenticated`；若 `enabled:true`，先 `POST /api/access-code/verify` 换到 `openmaic_access` cookie 并**持久化**（含 `anonymous_id`）。
3. 提交一个**极简**任务：

```bash
curl -s -X POST "http://127.0.0.1:3001/api/generate-classroom" \
  -H 'Content-Type: application/json' \
  -b cookies.txt -c cookies.txt \
  -d '{"requirement":"生成一页关于导数定义的互动页，含一个自测点"}'
```

4. 拿到 `jobId` 后**约 60 秒一次**轮询 `GET /api/generate-classroom/{jobId}`，直到 `status` 变成 `succeeded` 或 `failed`；成功后**自己拼**基址 + `result.url` 得到可访问的课堂地址。

## 8. 排障

| 症状 | 可能原因 | 处置 |
|---|---|---|
| 连接被拒 / health 非 200 | 容器没起、宿主端口不是 3001 | `docker compose ps` 看状态；核对 `OPENMAIC_HOST_PORT` |
| `/api/stages*` 返回纯文本 `Not found` | `OPENMAIC_AGENT_RUNTIME_ENABLED` 与 `DATABASE_URL` 未**同时**满足 | 两项都补齐并重启 |
| 生成任务 `failed`，报模型解析错误 | `DEFAULT_MODEL` 未设或拼错 | 补 `DEFAULT_MODEL`，与 `MODEL_ROUTES` 里的路由对齐 |
| runtime 开了但驱动选不到模型 | `MODEL_ROUTES` 未显式路由 `maic-agent-driver` | 在 `MODEL_ROUTES` 里补上该路由 |
| 每次请求都像"换了个用户" | `anonymous_id` cookie 没持久化 | 客户端保存 cookie（curl 用 `-c/-b`） |
| verify 通了但仍 401 | 没带 `openmaic_access` cookie，或两处持久化 token 不一致 | 带上 cookie；核对 `PERSISTENCE_DEV_TOKEN` 与 `NEXT_PUBLIC_PERSISTENCE_TOKEN` |
| 改了 token 前端没变化 | `NEXT_PUBLIC_PERSISTENCE_TOKEN` 是**编译期**变量 | 重新构建镜像 |
| cookie 写了但浏览器不认 | 纯 HTTP 下 cookie 带 `Secure` | 设 `COOKIE_SECURE=0` 并重启 |
| 解析响应直接抛异常 | 拿到的是纯文本错误页（如 404 `Not found`） | 先看状态码与原文，别硬 `JSON.parse` |
| 轮询一直 `running` | 任务卡住或上游异常 | 客户端上限约 10 分钟；服务端 30 分钟无更新会读作 failed |
| 生成结果为空 | 可能是"设计使然"（门拦截），也可能是接线故障 | 先看有没有拦截记录：没有记录 = 接线故障，整轮作废 |
| 磁盘被占满 | `video-export` profile 的镜像与产物 | 不用就移除该 profile；清理镜像与数据卷 |

## 9. 安全边界

- **默认只监听本机**（`127.0.0.1` / localhost）。要做局域网内共享，**先配访问码与反代**。
- 对外暴露时，**`ACCESS_CODE` 是唯一屏障**（本地部署不支持 `Authorization: Bearer`），务必：配反代、限流、定期轮换访问码、只用 HTTPS。
- **不要把 provider key 写进 compose 文件** —— 一律走 `.env.local` 或环境变量。
- **`.env.local` 不进版本库**；确认上游 `.gitignore` 覆盖了 `.env*`，没覆盖就自己补。
- 学生个人信息、未公开科研数据**不进外部服务**。
