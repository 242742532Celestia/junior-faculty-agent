# OpenMAIC 增量部署速查

> 20 行速查版。完整说明见 `../references/deployment.md`（含环境变量清单、排障表、安全边界）。

## 前置

- Docker + Docker Compose v2；只有"不用容器、本地直接跑"才需要 Node 22.19+。

## 获取本体（本体不随本仓库分发）

```bash
git clone https://github.com/THU-MAIC/OpenMAIC.git /path/to/OpenMAIC   # MIT / THU-MAIC
cd /path/to/OpenMAIC
```

## 准备环境变量

```bash
cp /path/to/junior-faculty-agent/skills/openmaic-courseware/deploy/env.local.example .env.local
```

填好 `.env.local`（**不要提交版本库**）。必填项：`DEFAULT_MODEL`、`OPENMAIC_AGENT_RUNTIME_ENABLED`、`DATABASE_URL`、`MODEL_ROUTES`、`PERSISTENCE_DEV_TOKEN` 与 `NEXT_PUBLIC_PERSISTENCE_TOKEN`（**两处必须一致**）、`NEXT_PUBLIC_PERSISTENCE`；LLM provider **至少配一类**（或用 `OLLAMA_BASE_URL` 走本地免 key）；纯 HTTP 必须 `COOKIE_SECURE=0`。

## 启动（含本仓库的增量 override）

```bash
docker compose -f docker-compose.yml \
               -f /path/to/junior-faculty-agent/skills/openmaic-courseware/deploy/docker-compose.jfa.yml \
               up --build
```

- 宿主端口默认 **3001**（容器内 3000），用 `OPENMAIC_HOST_PORT` 改。
- `--profile server-persistence` 启用 PostgreSQL；`--profile video-export` 启用 MP4 导出（镜像很重）。

## 验收

1. `GET /api/health` → 看 `capabilities` 四项（`version` 不可信）。
2. `GET /api/access-code/status` → 若 `enabled:true`，先 `POST /api/access-code/verify` 换 cookie 并持久化。
3. `POST /api/generate-classroom`（极简 `requirement`）→ 取 `jobId`。
4. **约 60 秒一次**轮询 `GET /api/generate-classroom/{jobId}` 到 `succeeded` / `failed`；成功后**自己拼**基址 + `result.url`。

## 排障

症状 → 原因 → 处置的完整表格见 **`../references/deployment.md` 第 8 节**（纯文本 404 = runtime 与数据库变量未同时满足；401 = 没 verify 或 token 不一致；cookie 不认 = `COOKIE_SECURE` 没设 0；结果为空 = 先分清"设计使然"还是"接线故障"）。
