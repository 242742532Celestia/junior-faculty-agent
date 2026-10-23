#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""openmaic_client.py —— OpenMAIC HTTP API 客户端（纯标准库，零第三方依赖）

为什么自己写
------------
本仓库要把「课件产出链」接到 OpenMAIC 上。OpenMAIC 本体**不随本仓库分发**
（使用者自己 clone 部署），但**接入能力必须随本仓库分发** —— 否则克隆方就没人
接手这条路径。所以这里自研一个纯标准库客户端：`json` / `urllib` / `http.cookiejar`，
不装任何第三方包。

    python openmaic_client.py --base-url http://localhost:3001 health
    python openmaic_client.py verify --code 你的访问码
    python openmaic_client.py generate --requirement "..." --wait
    python openmaic_client.py --selftest

🔴 三个最容易踩的坑（都已在下面处理，别绕过）
-------------------------------------------
1. **两套响应包装并存**，不能统一处理：
   - `apiSuccess(data)` → `{"success": true, ...业务字段}`，字段**平铺**，没有 `data` 嵌套
   - `ownerJson(body)` → **裸 body，什么信封都没有**（`/api/stages*` 全部走这套）
   → 本客户端**按内容判断**（有没有 `success` 键），不按端点硬编码。
2. **404 的 body 可能是纯文本 `Not found`**，不是 JSON。
   → 解析失败不当致命错误，按纯文本处理并保留状态码。
3. **轮询失败绝不重提任务**。
   → 单次轮询失败时复用**同一个 jobId** 继续等；重提会生成重复课堂并烧掉配额。

其它已处理的坑：
* 本地部署**不支持** `Authorization: Bearer`（那是托管版 `open.maic.chat` 的用法）。
  鉴权靠 `openmaic_access` cookie，本客户端用 `http.cookiejar` 自动管理。
* `anonymous_id` cookie 会被服务端在首次请求时下发。**必须持久化**，否则每次请求
  都换一个 owner 分区，owner-scoped 的写入会互相看不见。
* 响应里的 `pollUrl` 的 host 来自 `x-forwarded-host` 或请求 origin，**不可全信** ——
  本客户端一律**自己拼**轮询地址。

退出码：0 成功 / 1 参数或调用失败 / 2 自检失败
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = "http://localhost:3001"
DEFAULT_COOKIE_FILE = os.path.join(
    os.path.expanduser("~"), ".jfa-openmaic-cookies.txt")

# 轮询纪律（与上游仓库自带的 generate-flow 建议一致）
DEFAULT_POLL_INTERVAL = 60      # 秒。上游建议约 60s 一次
DEFAULT_POLL_TIMEOUT = 600      # 秒。单轮主动轮询上限约 10 分钟


class OpenmaicError(Exception):
    """调用失败（网络、协议、HTTP 错误都归到这里）。"""

    def __init__(self, message, status=None, error_code=None, details=None):
        Exception.__init__(self, message)
        self.message = message
        self.status = status
        self.error_code = error_code
        self.details = details

    def __str__(self):
        bits = [self.message]
        if self.status is not None:
            bits.append("HTTP %s" % self.status)
        if self.error_code:
            bits.append("errorCode=%s" % self.error_code)
        if self.details:
            bits.append("details=%s" % self.details)
        return " | ".join(bits)


class Response(object):
    """一次调用的结果。`json` 为 None 表示 body 不是 JSON（纯文本）。"""

    def __init__(self, status, body, text, headers=None):
        self.status = status
        self.body = body
        self.text = text
        self.headers = headers or {}

    @property
    def is_enveloped(self):
        """是否是 apiSuccess 那种带 `success` 键的包装。"""
        return isinstance(self.body, dict) and "success" in self.body

    @property
    def is_bare(self):
        """是否是 ownerJson 那种裸 body（无 success 键）。"""
        return isinstance(self.body, dict) and "success" not in self.body

    def get(self, key, default=None):
        if isinstance(self.body, dict):
            return self.body.get(key, default)
        return default

    def as_text(self):
        if self.body is not None:
            return json.dumps(self.body, ensure_ascii=False, indent=2)
        return self.text


class OpenmaicClient(object):
    """OpenMAIC HTTP 客户端。

    cookie 处理：`http.cookiejar` 自动保存服务端下发的 `openmaic_access`
    （访问码）与 `anonymous_id`（owner 隔离）。用 `LWPCookieJar` 落盘到文件，
    这样**跨进程**也能保持同一个 owner 分区。
    """

    def __init__(self, base_url=DEFAULT_BASE_URL, cookie_file=None,
                 timeout=60, verbose=False):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verbose = verbose
        self.cookie_file = cookie_file
        self._jar = http.cookiejar.CookieJar()
        if cookie_file and os.path.isfile(cookie_file):
            try:
                lwp = http.cookiejar.LWPCookieJar(cookie_file)
                lwp.load(ignore_discard=True, ignore_expires=True)
                self._jar = lwp
            except Exception:
                # cookie 文件损坏时不要让整个客户端起不来 —— 重新走一次 verify 即可
                self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar))

    # ------------------------------------------------------------ 底层

    def _url(self, path):
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def request(self, method, path, body=None, headers=None, params=None):
        """发一次请求。**不抛异常**（除网络层），HTTP 错误以 Response 返回，
        便于调用方区分「服务没起」与「服务说不行」。"""
        url = self._url(path)
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)

        data = None
        hdrs = {"Accept": "application/json, text/plain, */*",
                "User-Agent": "jfa-openmaic-client/1.0"}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            hdrs["Content-Type"] = "application/json; charset=utf-8"
        if headers:
            hdrs.update(headers)

        req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
        if self.verbose:
            print("[%s] %s" % (method, url), file=sys.stderr)

        try:
            resp = self._opener.open(req, timeout=self.timeout)
            raw = resp.read()
            status = resp.getcode()
            rh = dict(resp.headers.items())
        except urllib.error.HTTPError as e:
            raw = e.read() if hasattr(e, "read") else b""
            status = e.code
            rh = dict(e.headers.items()) if e.headers else {}
        except urllib.error.URLError as e:
            raise OpenmaicError("连不上 %s：%s" % (url, e.reason))
        except OSError as e:
            raise OpenmaicError("网络错误 %s：%s" % (url, e))

        text = raw.decode("utf-8", "replace")
        parsed = None
        stripped = text.strip()
        if stripped:
            try:
                parsed = json.loads(stripped)
            except ValueError:
                # 🔴 纯文本 body（典型是 404 的 "Not found"）—— 不是错误，是合法形态
                parsed = None
        return Response(status, parsed, text, rh)

    def call(self, method, path, body=None, headers=None, params=None):
        """发请求并在 4xx/5xx 时抛 OpenmaicError。"""
        r = self.request(method, path, body=body, headers=headers, params=params)
        if r.status >= 400:
            code = r.get("errorCode")
            msg = r.get("error") or r.get("message")
            details = r.get("details")
            if not msg:
                # `{error: "login_required"}` 那一族，或纯文本
                msg = r.get("error") or (r.text.strip() or "HTTP %d" % r.status)
            raise OpenmaicError(msg, status=r.status, error_code=code,
                                details=details)
        return r

    def save_cookies(self):
        if not self.cookie_file:
            return
        d = os.path.dirname(os.path.abspath(self.cookie_file))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        jar = self._jar
        if not isinstance(jar, http.cookiejar.LWPCookieJar):
            jar = http.cookiejar.LWPCookieJar(self.cookie_file)
            for c in self._jar:
                jar.set_cookie(c)
        jar.save(ignore_discard=True, ignore_expires=True)
        try:
            os.chmod(self.cookie_file, 0o600)
        except OSError:
            pass

    # ------------------------------------------------------------ 端点

    def health(self):
        """GET /api/health —— 免鉴权白名单。"""
        return self.call("GET", "/api/health")

    def access_status(self):
        """GET /api/access-code/status —— 判断要不要先 verify。"""
        return self.call("GET", "/api/access-code/status")

    def verify(self, code):
        """POST /api/access-code/verify —— 换 openmaic_access cookie。

        ⚠️ token **不在响应体里**，靠 Set-Cookie 下发。所以调用后必须 save_cookies()。
        """
        r = self.call("POST", "/api/access-code/verify", body={"code": code})
        self.save_cookies()
        return r

    def list_stages(self):
        """GET /api/stages —— 裸 body（ownerJson，无 success 键）。"""
        return self.call("GET", "/api/stages")

    def create_stage(self, name, description=None):
        """POST /api/stages —— 201，裸 body。"""
        body = {"name": name}
        if description:
            body["description"] = description
        return self.call("POST", "/api/stages", body=body)

    def get_stage(self, stage_id):
        """GET /api/stages/{id} —— 裸 body。"""
        return self.call("GET", "/api/stages/" + urllib.parse.quote(stage_id))

    def delete_stage(self, stage_id):
        """DELETE /api/stages/{id}。"""
        return self.call("DELETE", "/api/stages/" + urllib.parse.quote(stage_id))

    def get_scenes(self, stage_id, scene_ids):
        """GET /api/stages/{id}/scenes?ids=a,b —— 裸 body。ids 上限 200。"""
        if not scene_ids:
            raise OpenmaicError("scene id 列表不能为空（服务端会返回 empty_scene_ids）")
        if len(scene_ids) > 200:
            raise OpenmaicError("scene id 超过 200 个（服务端上限）")
        return self.call("GET", "/api/stages/%s/scenes" % urllib.parse.quote(stage_id),
                          params={"ids": ",".join(scene_ids)})

    def generate(self, requirement, enable_web_search=False,
                 enable_image_generation=False, enable_video_generation=False,
                 enable_tts=False, agent_mode=None):
        """POST /api/generate-classroom —— 202，返回 jobId。

        ⚠️ 省略的可选布尔一律为 false。**只把 health 探测到的能力置 true**，
        否则会白白要求服务端调用没有 provider 的通道。
        """
        body = {"requirement": requirement}
        if enable_web_search:
            body["enableWebSearch"] = True
        if enable_image_generation:
            body["enableImageGeneration"] = True
        if enable_video_generation:
            body["enableVideoGeneration"] = True
        if enable_tts:
            body["enableTTS"] = True
        if agent_mode:
            body["agentMode"] = agent_mode
        return self.call("POST", "/api/generate-classroom", body=body)

    def job_status(self, job_id):
        """GET /api/generate-classroom/{jobId}。"""
        return self.call("GET", "/api/generate-classroom/" + urllib.parse.quote(job_id))

    def wait_for_job(self, job_id, poll_interval=DEFAULT_POLL_INTERVAL,
                     timeout=DEFAULT_POLL_TIMEOUT, sleep=time.sleep,
                     on_poll=None):
        """轮询到终态。

        🔴 三条纪律（都来自上游的踩坑记录）：
          1. **只重试同一个 jobId**，绝不重新提交 —— 重提会生成重复课堂并烧配额。
          2. 只在 `succeeded` / `failed` 时停；`queued` / `running` 都算进行中。
          3. 单次轮询失败（网络抖动）**不算失败**，等一个间隔后重试同一个 jobId。

        `sleep` 与 `on_poll` 是为自检注入的（自检里不能真等 60 秒）。
        """
        deadline = time.time() + timeout
        attempts = 0
        while True:
            attempts += 1
            try:
                r = self.job_status(job_id)
            except OpenmaicError as e:
                # 轮询失败 ≠ 任务失败。重试同一个 job。
                if time.time() >= deadline:
                    raise OpenmaicError("轮询超时（%ds），最后一次错误：%s" % (timeout, e))
                if on_poll:
                    on_poll({"attempt": attempts, "error": str(e)})
                sleep(poll_interval)
                continue
            body = r.body or {}
            status = body.get("status")
            if on_poll:
                on_poll({"attempt": attempts, "status": status,
                         "step": body.get("step"), "progress": body.get("progress")})
            if status in ("succeeded", "failed"):
                return body
            if time.time() >= deadline:
                raise OpenmaicError("轮询超时（%ds），任务仍在 %s/%s"
                                    % (timeout, status, body.get("step")))
            sleep(poll_interval)

    def get_classroom(self, classroom_id):
        """GET /api/classroom?id=。"""
        return self.call("GET", "/api/classroom", params={"id": classroom_id})


# ---------------------------------------------------------------- CLI

def _print(r, as_json):
    if as_json:
        print(json.dumps(r.body if r.body is not None else {"text": r.text},
                         ensure_ascii=False, indent=2))
    else:
        print(r.as_text())


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="OpenMAIC HTTP API 客户端（纯标准库）",
        epilog="示例：python openmaic_client.py --base-url http://localhost:3001 health")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL,
                    help="OpenMAIC 基址（默认 %s）" % DEFAULT_BASE_URL)
    ap.add_argument("--cookie-file", default=DEFAULT_COOKIE_FILE,
                    help="cookie 落盘路径（跨进程保持 owner 分区）")
    ap.add_argument("--timeout", type=int, default=60, help="单次请求超时秒数")
    ap.add_argument("--json", action="store_true", help="输出原始 JSON")
    ap.add_argument("--verbose", action="store_true", help="打印请求行")
    ap.add_argument("--selftest", action="store_true", help="跑内置自检")

    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("health", help="GET /api/health（免鉴权）")
    sub.add_parser("access-status", help="GET /api/access-code/status")

    p = sub.add_parser("verify", help="POST /api/access-code/verify")
    p.add_argument("--code", required=True)

    sub.add_parser("stages", help="GET /api/stages（裸 body）")

    p = sub.add_parser("stage-create", help="POST /api/stages")
    p.add_argument("--name", required=True)
    p.add_argument("--description")

    p = sub.add_parser("stage-get", help="GET /api/stages/{id}")
    p.add_argument("--id", required=True)

    p = sub.add_parser("stage-delete", help="DELETE /api/stages/{id}")
    p.add_argument("--id", required=True)

    p = sub.add_parser("generate", help="POST /api/generate-classroom")
    p.add_argument("--requirement", required=True)
    p.add_argument("--web-search", action="store_true")
    p.add_argument("--image-generation", action="store_true")
    p.add_argument("--video-generation", action="store_true")
    p.add_argument("--tts", action="store_true")
    p.add_argument("--agent-mode")
    p.add_argument("--wait", action="store_true", help="轮询到终态")
    p.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL)
    p.add_argument("--poll-timeout", type=int, default=DEFAULT_POLL_TIMEOUT)

    p = sub.add_parser("classroom", help="GET /api/classroom?id=")
    p.add_argument("--id", required=True)

    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.cmd:
        ap.print_help()
        return 1

    client = OpenmaicClient(base_url=args.base_url, cookie_file=args.cookie_file,
                            timeout=args.timeout, verbose=args.verbose)
    try:
        if args.cmd == "health":
            _print(client.health(), args.json)
        elif args.cmd == "access-status":
            _print(client.access_status(), args.json)
        elif args.cmd == "verify":
            _print(client.verify(args.code), args.json)
        elif args.cmd == "stages":
            _print(client.list_stages(), args.json)
        elif args.cmd == "stage-create":
            _print(client.create_stage(args.name, args.description), args.json)
        elif args.cmd == "stage-get":
            _print(client.get_stage(args.id), args.json)
        elif args.cmd == "stage-delete":
            _print(client.delete_stage(args.id), args.json)
        elif args.cmd == "classroom":
            _print(client.get_classroom(args.id), args.json)
        elif args.cmd == "generate":
            r = client.generate(args.requirement,
                                enable_web_search=args.web_search,
                                enable_image_generation=args.image_generation,
                                enable_video_generation=args.video_generation,
                                enable_tts=args.tts,
                                agent_mode=args.agent_mode)
            body = r.body or {}
            if args.json:
                print(json.dumps(body, ensure_ascii=False, indent=2))
            else:
                print("已提交，jobId=%s  status=%s  step=%s"
                      % (body.get("jobId"), body.get("status"), body.get("step")))
                print("轮询地址（本客户端自拼，不采信响应里的 host）：%s/api/generate-classroom/%s"
                      % (client.base_url, body.get("jobId")))
            if args.wait:
                print("轮询中（约每 %ds 一次，上限 %ds）……" % (args.poll_interval, args.poll_timeout))

                def _on_poll(info):
                    print("  第 %d 次：%s" % (info["attempt"],
                                            info.get("status") or info.get("error")), file=sys.stderr)

                final = client.wait_for_job(body.get("jobId"),
                                            poll_interval=args.poll_interval,
                                            timeout=args.poll_timeout,
                                            on_poll=_on_poll)
                if args.json:
                    print(json.dumps(final, ensure_ascii=False, indent=2))
                else:
                    print("终态：%s / %s" % (final.get("status"), final.get("step")))
                    res = final.get("result") or {}
                    if res.get("url"):
                        print("课堂地址：%s" % res["url"])
                    if final.get("error"):
                        print("失败原因：%s" % final["error"])
                if final.get("status") != "succeeded":
                    return 1
        client.save_cookies()
    except OpenmaicError as e:
        print("调用失败：%s" % e, file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------- 自检

def selftest():
    """内置自检：起一个本地假 OpenMAIC，验证本客户端的**关键行为**。

    验的不是"能不能发请求"，而是那三个最容易踩的坑：
      ① 两套响应包装都能解析；
      ② 纯文本 404 被正确识别成错误而不是崩溃；
      ③ 轮询失败不重提任务、终态能停。
    外加：cookie 跨进程持久化。
    """
    import http.server
    import threading

    state = {"polls": 0, "verifies": 0, "generates": 0, "cookie_seen": ""}

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code, payload, raw=False, headers=None):
            if raw:
                body = payload.encode("utf-8")
                ctype = "text/plain; charset=utf-8"
            else:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                ctype = "application/json; charset=utf-8"
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            state["cookie_seen"] = self.headers.get("Cookie") or ""
            if self.path == "/api/health":
                return self._send(200, {"success": True, "status": "ok",
                                        "version": "0.1.0",
                                        "capabilities": {"webSearch": False,
                                                         "imageGeneration": False,
                                                         "videoGeneration": False,
                                                         "tts": False}})
            if self.path == "/api/access-code/status":
                return self._send(200, {"success": True, "enabled": True,
                                        "authenticated": state["verifies"] > 0})
            if self.path == "/api/stages":
                # 🔴 裸 body：没有 success 键
                return self._send(200, {"stages": [{"id": "stage-x", "name": "课",
                                                     "sceneCount": 2}]})
            if self.path.startswith("/api/stages/"):
                # 🔴 纯文本 404
                return self._send(404, "Not found", raw=True)
            if self.path.startswith("/api/generate-classroom/"):
                state["polls"] += 1
                if "bad" in self.path:
                    # 模拟「轮询时服务端报错」—— 客户端应重试同一 job，而不是重提任务
                    return self._send(500, {"success": False,
                                            "errorCode": "INTERNAL_ERROR",
                                            "error": "boom"})
                if state["polls"] == 1:
                    return self._send(200, {"success": True, "status": "running",
                                            "step": "generating_scenes", "progress": 40})
                return self._send(200, {"success": True, "status": "succeeded",
                                        "step": "completed", "progress": 100,
                                        "result": {"classroomId": "C1", "url": "u"}})
            return self._send(404, "Not found", raw=True)

        def do_POST(self):
            ln = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(ln)
            state["cookie_seen"] = self.headers.get("Cookie") or ""
            if self.path == "/api/access-code/verify":
                state["verifies"] += 1
                return self._send(200, {"success": True, "valid": True},
                                  headers={"Set-Cookie":
                                           "openmaic_access=abc; Path=/; HttpOnly; Max-Age=604800"})
            if self.path == "/api/generate-classroom":
                state["generates"] += 1
                return self._send(202, {"success": True, "jobId": "J1",
                                        "status": "queued", "step": "queued",
                                        "pollUrl": "http://evil.invalid/api/generate-classroom/J1",
                                        "pollIntervalMs": 5000})
            return self._send(404, "Not found", raw=True)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    base = "http://127.0.0.1:%d" % port
    tmp_cookie = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              ".selftest-cookies.txt")

    problems = []
    try:
        c = OpenmaicClient(base_url=base, cookie_file=tmp_cookie)

        # ① health：带 success 的包装
        r = c.health()
        if not r.is_enveloped or r.get("status") != "ok":
            problems.append("health 解析异常：%r" % r.body)
        if "capabilities" not in (r.body or {}):
            problems.append("health 缺 capabilities")

        # ② stages：裸 body（无 success）
        r = c.list_stages()
        if not r.is_bare:
            problems.append("stages 应为裸 body，实际 %r" % r.body)
        if len(r.get("stages") or []) != 1:
            problems.append("stages 解析异常")

        # ③ 纯文本 404 —— 必须是 OpenmaicError，不能是 JSONDecodeError
        try:
            c.get_stage("nope")
            problems.append("纯文本 404 未抛错")
        except OpenmaicError as e:
            if e.status != 404:
                problems.append("404 状态码不对：%s" % e.status)
            if "Not found" not in str(e):
                problems.append("404 正文没被保留：%s" % e)

        # ④ verify → cookie 落盘
        c.verify("code123")
        if not os.path.isfile(tmp_cookie):
            problems.append("cookie 未落盘")
        # 新 client 实例读同一个 cookie 文件 → cookie 应被带上
        # （用 GET 探测，避免污染后面要断言的 generate 提交次数）
        c2 = OpenmaicClient(base_url=base, cookie_file=tmp_cookie)
        c2.list_stages()
        if "openmaic_access=abc" not in state["cookie_seen"]:
            problems.append("cookie 未随请求带回：%r" % state["cookie_seen"])

        # ⑤ 轮询：第一次 running、第二次 succeeded —— 必须停，且**只提交一次**
        c3 = OpenmaicClient(base_url=base, cookie_file=tmp_cookie)
        r = c3.generate("做一节课")
        job = r.get("jobId")
        if job != "J1":
            problems.append("jobId 解析异常：%r" % job)
        final = c3.wait_for_job(job, poll_interval=0, timeout=10, sleep=lambda s: None)
        if final.get("status") != "succeeded":
            problems.append("轮询未到终态：%r" % final)
        if state["generates"] != 1:
            problems.append("轮询期间重复提交了任务：generate 次数=%d" % state["generates"])
        if state["polls"] < 2:
            problems.append("轮询次数异常：%d" % state["polls"])

        # ⑥ 轮询失败不重提：jobStatus 抛错时 wait_for_job 应重试同一个 job
        #    （用一个只会 500 的 jobId 验证：超时应报"轮询超时"而不是"任务失败"）
        c4 = OpenmaicClient(base_url=base, cookie_file=tmp_cookie)
        try:
            c4.wait_for_job("bad", poll_interval=0, timeout=0, sleep=lambda s: None)
            problems.append("轮询超时未抛错")
        except OpenmaicError as e:
            if "轮询超时" not in str(e):
                problems.append("轮询超时文案不对：%s" % e)
        if state["generates"] != 1:
            problems.append("轮询失败时重复提交了任务")
    except Exception as e:
        problems.append("自检抛异常：%s: %s" % (type(e).__name__, e))
    finally:
        server.shutdown()
        server.server_close()
        if os.path.isfile(tmp_cookie):
            try:
                os.remove(tmp_cookie)
            except OSError:
                pass

    if problems:
        print("selftest: 未通过", file=sys.stderr)
        for p in problems:
            print("  - %s" % p, file=sys.stderr)
        return 2
    print("selftest: 全部通过（两套响应包装 / 纯文本 404 / cookie 持久化 / "
          "轮询不重提 / 终态停止）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
