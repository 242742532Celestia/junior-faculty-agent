#!/usr/bin/env python3
"""
技能巡检器（junior-faculty-agent 的自学习执行体）

用法:
    python scripts/skill_scan.py --scan          # 只扫描 GitHub，产出候选清单（不安装）
    python scripts/skill_scan.py --scan --json   # 机器可读输出
    python scripts/skill_scan.py --install <spec.json>   # 按巡检决策安装技能
    python scripts/skill_scan.py --selftest      # 自检（不联网）

设计约束:
  - 纯标准库，不装依赖（本机有 Python 3.14 但不应假设有 requests）
  - GitHub API 未认证时有限流（60 req/h），因此严格限制请求数并缓存
  - 扫描结果写 reports/skill-scan-<YYYY>-Q<N>-candidates.json，供人工/Agent 判读
  - **本脚本不做"是否属于高校教师能力"的最终判定** —— 那是 Agent 的判断。
    脚本只负责「找到候选」与「按决策安装」，避免把语义判断硬编码成正则。

作者: junior-faculty-agent | 纯标准库
"""

import argparse
import base64
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(AGENT_DIR, "reports")
SKILLS_DIR = os.path.join(AGENT_DIR, "skills")
MATRIX = os.path.join(AGENT_DIR, "references", "faculty-capability-matrix.md")
REJECTED = os.path.join(AGENT_DIR, "references", "rejected-skills.md")

GITHUB_API = "https://api.github.com"
UA = "junior-faculty-agent-skill-scan"

# 技能名的形状：小写字母/数字/连字符，至少 3 个字符。
# 文档里表格的第一列可能是表头或散文，必须用形状过滤掉 —— 排除名单是逐行读的，
# 形状不受控就会把文档结构变成数据。
SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{2,}$")

# 巡检关键词 —— 按能力矩阵的缺口域构造，不是泛泛的 "skills"
SEARCH_QUERIES = [
    # A/C 教学与考核
    ("lesson-plan", "A1-A2,B1,B2,C5,C6"),
    ("curriculum-design", "A1,A2,A3"),
    ("rubric-assessment", "C1,C2,C3"),
    ("exam-question-bank", "C6"),
    ("textbook-selection", "A5"),
    ("course-syllabus", "A2"),
    ("syllabus-generator", "A2"),
    ("grading-feedback", "C1,C7,D4"),
    # E 科研
    ("grant-proposal", "E8"),
    ("research-grant-application", "E8"),
    ("nsf-proposal", "E8"),
    ("paper-writing", "E4"),
    ("peer-review", "E5"),
    ("literature-review", "E2"),
    ("data-visualization", "E6"),
    ("teaching-research", "E9"),
    ("academic-cv", "E10"),
    ("faculty-profile", "E10"),
    # B/F 教学法与教研
    ("pedagogical-content-knowledge", "F3"),
    ("formative-assessment", "C2,C3"),
    ("cognitive-load", "B6"),
]

# 主源仓库 —— 直接比对是否有新技能目录
TRACKED_REPOS = [
    ("K-Dense-AI/scientific-agent-skills", "research"),
    ("GarethManning/education-agent-skills", "teaching"),
    ("Imbad0202/academic-research-skills", "research"),
]

MAX_NEW_PER_RUN = 10
SEARCH_PER_QUERY = 5
# 描述嗅探的样本上限：识别「库型措辞」的模式不需要全量检查，
# 全量会拖到超时。未嗅探的项保守保留为候选，交给 Agent 判读。
# 每个嗅探项要 2 次请求（目录内容 + blob），所以上限不宜大。
SNIFF_LIMIT = 25

# 全局请求预算：一次扫描最多发多少个网络请求。
# 预算耗尽 → 停止扫描并如实报告"配额不足"，而不是无限重试到超时。
# 缓存命中不计入预算。
REQUEST_BUDGET = 90
_request_counter = {"n": 0}


def budget_exhausted():
    return _request_counter["n"] >= REQUEST_BUDGET

# ⚠️ 主源仓库里有一批「领域方法库」技能（如 scikit-learn / torchdrug / zarr-python /
# scanpy / rdkit ...）。它们是某个学科的工具封装，**不是高校教师的基本能力**——
# 教师不会因为会调 scanpy 就多一项教学/科研职责。
#
# 若不排除，扫描会把 60+ 个领域库技能报成"新增"，把真正的教学/科研技能缺口淹没。
# 判据：技能名指向一个**具体技术栈/科学计算包**，而不是一门教学或科研的**方法**。
# 科研方法类（experimental-design / statistical-analysis / hypothesis-generation /
# research-grants / scientific-critical-thinking ...）必须保留。
#
# ⚠️ 论文类（scientific-writing / literature-review / citation-management /
# peer-review / venue-templates / paper-lookup / research-lookup /
# scholar-evaluation / scientific-slides）**已于 2026-10-22 回装本仓库** ——
# 论文线随包分发，不依赖本机全局技能。它们的**许可状态由另一条判据**把关
# （见 `load_rejected_names()` 与 verify_repo 的许可完整性检查），
# 不在本前缀排除表里。
#
# 注意：正则用「前缀列表」而非大杂烩字符组——字符组里的 `|` 不是或运算符。
DOMAIN_LIBRARY_PREFIXES = [
    # 通用机器学习 / 深度学习框架与生态
    "scikit-", "scikit", "torch", "pytorch", "transformers", "tensorflow", "keras",
    "jax", "flax", "optuna", "ray", "mlflow", "dvc", "wandb", "huggingface",
    "shap", "lime", "statsmodels", "sympy", "numba", "cython", "pybind",
    # 生物信息 / 生化 / 生态
    "rdkit", "scanpy", "scvi", "anndata", "scvelo", "scanorama", "scrublet",
    "palantir", "velocyto", "squidpy", "spatialdata", "cellxgene", "cellprofiler",
    "arbor", "arboreto", "decoupler", "biopython", "bioservices", "biomart",
    "cobrapy", "cantera", "deeptools", "diffdock", "esm", "ete3", "galaxy",
    "gemmi", "qiime2", "qiime", "rnaseq", "chembl", "europepmc", "fba", "firefly",
    "hmmer", "ibis", "medaka", "mne", "modeller", "nanopore", "nf-core",
    "openbabel", "opentrons", "pacsomatic", "pyopenms", "pysam", "primer3",
    "snaky", "teaching", "deepchem", "diffusion", "eqs", "gmx", "hetero",
    "hmr", "mplus", "nlme", "obabel", "penn", "physic", "pint", "poppler",
    "psi4", "pytdc", "qiskit", "qutip", "relion", "rowan", "seaborn", "simpy",
    "stable-baselines3", "tamarind", "tellurium", "tiledbvcf", "timesfm",
    "treatment-plans", "usfiscaldata", "waypoint-bio", "what-if-oracle",
    "zarr", "zeep", "zotero", "pymupdf", "pdfplumber", "matplotlib", "plotly",
    "pygal", "sunpy", "astropy", "pyephem", "poliastro", "sep", "lightkurve",
    "healpy", "camb", "classy", "dustmaps", "rebound", "pyrockt", "yt-project",
    "yt", "ytb", "yt-project", "numpydoc", "mdanalysis", "mdtraj", "openmm",
    "pdbfixer", "prody", "openbabel", "pysam",
    # 基础设施 / 运维 / 通用开发（明显不属于教师职责）
    "docker", "kubernetes", "k8s", "terraform", "ansible", "helm", "istio",
    "postgres", "mysql", "mongodb", "redis", "kafka", "spark", "hadoop",
    "flask", "django", "fastapi", "uvicorn", "gunicorn", "celery", "airflow",
    "prefect", "dagster", "mlflow", "dvc", "kedro", "dbt", "airbyte",
    "serverless", "lambda", "s3", "gcs", "azure", "aws", "gcp",
]


# 科研侧技能名标记 —— 用于自检时把教学技能与科研技能区分开
_RESEARCH_SKILL_MARKERS = (
    "scientific-", "literature-", "experimental-", "statistical-", "citation-",
    "scholar-", "hypothesis-", "venue-", "latex-", "research-", "paper-",
    "peer-review", "deep-research", "academic-", "uncertainty-", "grant",
)


def _is_research_skill(name):
    """粗判某技能是否属于科研侧（用于自检时排除科研技能不做教学适配检查）。"""
    n = name.lower()
    return any(n.startswith(m) or f"-{m}" in n for m in _RESEARCH_SKILL_MARKERS)


def is_domain_library(name):
    """判断是否为「领域方法库」技能（工具封装，非教师基本能力）。

    先看名称前缀表；再对未命中者做**描述嗅探**——
    库型技能的描述几乎必然出现「Python library」「package for」
    「wrapper around」「bindings for」这类措辞，而方法型技能不会。
    """
    n = name.lower()
    for p in DOMAIN_LIBRARY_PREFIXES:
        if n.startswith(p):
            return True
    return False


# 描述嗅探：命中即判为库型技能（只用于主源新增项，不用于搜索命中）
_LIBRARY_DESC_PATTERNS = re.compile(
    r"(python (library|package|module)|wrapper around|bindings for|"
    r"for (the )?[a-z0-9_-]+ (library|package|framework)|"
    r"\b(library|package) for [a-z]+ (analysis|processing|modeling)|"
    r"toolkit for [a-z]+|"
    r"install(ing)? (the )?[a-z0-9_-]+ (package|library)|"
    r"uses? the [a-z0-9_-]+ (library|package)|"
    r"基于 [a-z0-9_-]+ 库)",
    re.I,
)


def looks_like_library(description):
    """按技能描述判断是否为「库封装」而非「方法」。"""
    if not description:
        return False
    return bool(_LIBRARY_DESC_PATTERNS.search(description))

# 未认证的 GitHub API 限额是 60 req/h/IP。季度 cron 是无人值守的，
# 撞上限流会让扫描失败。因此：
#   1) 命中缓存的 URL 不再发请求
#   2) 缓存 TTL 默认 12 小时（季度巡检当天重试足够）
#   3) 设置 GITHUB_TOKEN 后限额升到 5000 req/h
CACHE_DIR = os.path.join(AGENT_DIR, ".cache")
CACHE_TTL_SECONDS = 12 * 3600


def cache_path(url):
    import hashlib
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    return os.path.join(CACHE_DIR, f"{h}.json")


def cache_read(url, allow_stale=False):
    """读缓存。allow_stale=True 时过期数据也返回（降级用）。"""
    p = cache_path(url)
    if not os.path.isfile(p):
        return None
    try:
        stale = (time.time() - os.path.getmtime(p)) > CACHE_TTL_SECONDS
        if stale and not allow_stale:
            return None
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if stale:
            data = dict(data) if isinstance(data, dict) else data
            if isinstance(data, dict):
                data["_cache_stale"] = True
        return data
    except (OSError, json.JSONDecodeError):
        return None


def cache_write(url, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(cache_path(url), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError:
        pass  # 缓存失败不影响主流程


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def http_json(url, timeout=45, retries=3):
    """带重试、限流处理与磁盘缓存的 GitHub API 调用。

    大响应体（如 recursive=1 的仓库树，可达数 MB）经常在传输中途
    IncompleteRead 中断 —— 这不是限流，是连接层问题，必须重试。
    因此这里区分三类失败：
      - HTTP 403/429 → 限流，Respect Retry-After 后退避重试
      - IncompleteRead / socket 超时 → 传输中断，指数退避重试
    全部重试失败则抛出明确异常，**不静默返回空结果** ——
    空结果会让巡检误判成「主源没有新技能」。

    缓存：命中则不发请求（未认证限额仅 60 req/h，季度 cron 无人值守）。
    """
    cached = cache_read(url)
    if cached is not None:
        return cached

    if budget_exhausted():
        stale = cache_read(url, allow_stale=True)
        if stale is not None:
            return stale
        raise RuntimeError(
            f"request budget exhausted ({REQUEST_BUDGET}); skipping {url}"
        )

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last = None
    for attempt in range(retries):
        try:
            _request_counter["n"] += 1
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            data = json.loads(raw.decode("utf-8", "replace"))
            cache_write(url, data)
            return data
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                # 限流：GitHub 未认证配额是 60 req/h/IP，耗尽后会一直 403。
                # 此时**继续重试没有意义**——配额不会在几十秒内恢复。
                # 只有带 Retry-After 的才值得等；否则立刻失败，
                # 让调用方看到"配额耗尽"这个真实原因，而不是干等超时。
                retry_after = e.headers.get("Retry-After")
                if not retry_after:
                    # 降级：若有过期缓存，用它继续（标记 stale），比整个扫描失败好
                    stale = cache_read(url, allow_stale=True)
                    if stale is not None:
                        sys.stderr.write(
                            f"[warn] rate limited; using STALE cache for {url}\n"
                        )
                        return stale
                    raise RuntimeError(
                        f"GitHub API rate limit exhausted (403, no Retry-After) for {url}. "
                        f"Set GITHUB_TOKEN to raise the limit to 5000 req/h."
                    ) from e
                wait = int(retry_after) * (attempt + 1)
                sys.stderr.write(f"[warn] rate limited ({e.code}), waiting {wait}s\n")
                time.sleep(wait)
                last = e
                continue
            if e.code == 404:
                return None
            last = e
            time.sleep(2)
        except (http.client.IncompleteRead, ConnectionError, TimeoutError, OSError) as e:
            # 传输层中断（大响应体常见）：指数退避后重试
            wait = 3 * (2 ** attempt)
            sys.stderr.write(f"[warn] transfer interrupted ({type(e).__name__}), retry in {wait}s\n")
            time.sleep(wait)
            last = e
        except json.JSONDecodeError as e:
            sys.stderr.write(f"[warn] bad JSON from {url}, retrying\n")
            time.sleep(2)
            last = e
    raise RuntimeError(f"GitHub API failed for {url}: {last}")


def quarter_now(dt=None):
    dt = dt or datetime.now(timezone.utc)
    return dt.year, (dt.month - 1) // 3 + 1


# --------------------------------------------------------------------------
# 扫描
# --------------------------------------------------------------------------

def installed_skill_names():
    if not os.path.isdir(SKILLS_DIR):
        return set()
    out = set()
    for d in os.listdir(SKILLS_DIR):
        p = os.path.join(SKILLS_DIR, d, "SKILL.md")
        if os.path.isfile(p):
            out.add(d)
    return out


def scan_repositories():
    """比对主源仓库是否有本机没有的新技能。

    🔴 关键：拉取失败 ≠ 主源没有新技能。
    失败必须单独记录到 `errors` 里并让调用方知道，
    否则巡检会把"网络故障"误判成"仓库已无新技能"，从而静默漏掉更新。
    """
    have = installed_skill_names()
    found = []
    errors = []
    for repo, domain in TRACKED_REPOS:
        try:
            # 🔴 不用 `git/trees/main?recursive=1` —— K-Dense 的递归树有几万个节点
            # （含 tests/fixtures/图片），传输动辄几十秒到几分钟，是扫描超时的主因。
            # 改用 contents API 只列 skills/ 一层目录：响应小、快、够用。
            entries = http_json(f"{GITHUB_API}/repos/{repo}/contents/skills")
            if not entries:
                entries = http_json(f"{GITHUB_API}/repos/{repo}/contents/")
        except RuntimeError as e:
            errors.append(f"{repo}: {e}")
            sys.stderr.write(f"[error] list {repo} FAILED (not 'no new skills'): {e}\n")
            continue
        if not isinstance(entries, list):
            errors.append(f"{repo}: unexpected contents payload")
            sys.stderr.write(f"[error] list {repo}: unexpected payload\n")
            continue

        repo_skill_dirs = set()
        for it in entries:
            if it.get("type") == "dir":
                nm = it.get("name")
                if nm and not nm.startswith("."):
                    repo_skill_dirs.add(nm)
        # 领域方法库技能（scikit-learn / torchdrug / scanpy ...）不是教师基本能力，
        # 单独归类，不混进候选——否则真正的缺口会被几十个库技能淹没。
        #
        # 判据用「名称前缀 + 描述嗅探」两层：
        #   前缀表命中 → 直接判库
        #   前缀表未命中 → 读 SKILL.md 的 frontmatter 看描述
        #
        # 🔴 描述嗅探**不能逐个调 contents API** —— 一次要几十个请求，
        # 会撞限流且慢到超时。改为用 git blob API 批量取：
        # 先从 tree 里拿到每个 SKILL.md 的 blob sha，再用一次
        # `git/blobs/{sha}` 逐个取（blob API 走的是 core 限额，不是 search 限额）。
        domain_libs = []
        new = [d for d in sorted(repo_skill_dirs)
               if d not in have and not is_domain_library(d)]
        domain_libs += [d for d in sorted(repo_skill_dirs)
                        if d not in have and is_domain_library(d)]

        real_new = []
        # 只嗅探前 SNIFF_LIMIT 个未命中项：识别库型措辞的模式不需要全量，
        # 而全量会拖到超时。未嗅探的项保守地**不排除**，交给 Agent 判读。
        sniff_targets = new[:SNIFF_LIMIT]
        sniffed = []
        for name in sniff_targets:
            if budget_exhausted():
                # 预算耗尽：停止嗅探。已嗅探过的按结果处理，
                # 未嗅探的一律保守保留为候选（宁可多报，不可静默丢弃）。
                sys.stderr.write(
                    "[warn] request budget exhausted, stopping description sniffing\n"
                )
                break
            desc = ""
            # 只为这一项取一次目录内容拿 SKILL.md 的 blob sha。
            # （之前对**所有**目录都取一遍 → 190+ 次请求，是扫描超时的真正原因。）
            sha = None
            try:
                sub = http_json(f"{GITHUB_API}/repos/{repo}/contents/skills/{name}")
                if isinstance(sub, list):
                    for s2 in sub:
                        if s2.get("name") == "SKILL.md":
                            sha = s2.get("sha")
                            break
            except RuntimeError:
                sha = None
            if sha:
                try:
                    blob = http_json(f"{GITHUB_API}/repos/{repo}/git/blobs/{sha}")
                    if blob and blob.get("content"):
                        content = base64.b64decode(blob["content"]).decode("utf-8", "replace")
                        fm = parse_frontmatter(content) or ""
                        m2 = re.search(r"^description:\s*[\"']?(.*?)[\"']?\s*$", fm, re.M)
                        if m2:
                            desc = m2.group(1)
                except RuntimeError:
                    desc = ""
            sniffed.append(name)
            if desc and looks_like_library(desc):
                domain_libs.append(name)
            else:
                real_new.append(name)
        # 未嗅探的余项一律保留为候选
        real_new.extend([n for n in new if n not in sniffed])

        for name in real_new:
            found.append({
                "name": name,
                "source_repo": repo,
                "source_domain": domain,
                "source_path": f"skills/{name}/SKILL.md",
                "url": f"https://github.com/{repo}/blob/main/skills/{name}/SKILL.md",
                "reason": "tracked repo has new skill directory",
            })
        domain_library_count = len(domain_libs)
    return found, errors, domain_library_count


def scan_search():
    """按关键词搜索 GitHub 仓库，找出可能的技能来源仓库。

    未认证限额 60 req/h。20 组关键词全搜会撞限流，
    因此：主源仓库扫描优先（那是高价值信号），关键词搜索放后面；
    一旦某次搜索因限流失败，**停止后续搜索**并记录已完成的组数——
    继续搜只会把每次退避时间累加，把整个扫描拖到超时。
    """
    results = []
    errors = []
    done_groups = 0
    for keyword, covers in SEARCH_QUERIES:
        q = urllib.parse.quote(f"{keyword} skills in:name,description")
        try:
            data = http_json(f"{GITHUB_API}/search/repositories?q={q}&sort=updated&order=desc&per_page={SEARCH_PER_QUERY}")
        except RuntimeError as e:
            errors.append(f"search '{keyword}': {e}")
            sys.stderr.write(f"[warn] search '{keyword}' failed, stopping keyword sweep: {e}\n")
            break
        done_groups += 1
        if not data or "items" not in data:
            continue
        for item in data.get("items", []):
            results.append({
                "name": item.get("full_name"),
                "source_repo": item.get("full_name"),
                "source_domain": "search",
                "covers_gaps": covers,
                "url": item.get("html_url"),
                "stars": item.get("stargazers_count"),
                "pushed_at": item.get("pushed_at"),
                "description": (item.get("description") or "")[:200],
                "reason": f"search hit for '{keyword}' (covers {covers})",
            })
    return results, errors, done_groups


def load_rejected_names():
    """从 references/rejected-skills.md 的表格里读出「排除名单」。

    🔴 两条必须机械化的过滤，否则这份名单会被文档结构污染：

      ① **只认真技能名** —— 该文档里有若干表格的第一列是表头（"技能"）
         或散文（"backwards-design-unit-planner 等 50 项教学技能"），
         它们不是技能名；进了排除名单就变成垃圾条目，而名单是**逐行**读的，
         文档结构一变就会静默失真。
      ② **剔除已安装的** —— 「已安装」与「已排除」是互斥状态。
         2026-10-22 论文线 9 个技能移出后又回装，若仍留在排除名单里，
         巡检报告会把"已装的东西"记成"已排除"，是假信息。
    """
    if not os.path.isfile(REJECTED):
        return set()
    text = open(REJECTED, encoding="utf-8", errors="replace").read()
    have = installed_skill_names()
    names = set()
    for line in text.splitlines():
        if line.startswith("|") and "|" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0] and not cells[0].startswith("-"):
                name = cells[0].strip("`* ")
                if not SKILL_NAME_RE.match(name):
                    continue          # 表头 / 散文，不是技能名
                if name in have:
                    continue          # 已安装 ⇒ 不该再是"已排除"
                names.add(name)
    return names


# --------------------------------------------------------------------------
# 安装
# --------------------------------------------------------------------------

def fetch_skill_md(repo, path):
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    data = http_json(url)
    if not data or data.get("type") != "file":
        return None, None
    content = base64.b64decode(data["content"]).decode("utf-8", "replace")
    return content, data.get("download_url")


def install_skill(spec):
    """按巡检决策安装一个技能。返回 (ok, message)。"""
    name = spec["name"]
    repo = spec.get("source_repo")
    path = spec.get("source_path")
    if not repo or not path:
        return False, "spec missing source_repo/source_path"

    target = os.path.join(SKILLS_DIR, name)
    if os.path.isdir(target):
        return False, f"already installed: {name}"

    content, download_url = fetch_skill_md(repo, path)
    if content is None and download_url:
        try:
            req = urllib.request.Request(download_url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                content = r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            return False, f"download failed: {e}"
    if not content:
        return False, f"could not fetch {repo}/{path}"

    if not content.lstrip().startswith("---"):
        return False, "no YAML frontmatter — not a valid skill"

    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(content)
    return True, f"installed {name} from {repo}"


def append_he_adapter(name):
    """给教学类技能追加中国高校语境适配块。"""
    sk = os.path.join(SKILLS_DIR, name, "SKILL.md")
    if not os.path.isfile(sk):
        return False
    text = open(sk, encoding="utf-8", errors="replace").read()
    if "he-context-adapter" in text:
        return False
    block = (
        "\n\n---\n\n## 高校语境适配（必读 · junior-faculty-agent 追加）\n\n"
        "本技能上游为英式 K-12 语境。执行前**必须**先读本仓库的 "
        "`references/he-context-adapter.md`（相对本技能目录的仓库根路径："
        "`../../references/he-context-adapter.md`），按其中的映射表把学段、课时、"
        "评价制度换算成中国高校口径。\n\n"
        "三条硬性要求：\n\n"
        "1. **输入里的 `Year N` / `KS3` 等一律先映射**再执行：Year 7–9 → 本科大一，"
        "Year 10–11 → 本科大二，Year 12–13 → 本科三四年级。\n"
        "2. **产出正文用中文**，专业术语首次出现时中英并列"
        "（形成性评价 / formative assessment）。\n"
        "3. **不得编造** ISBN、学分号、毕业要求编号、参考文献、政策文件号。"
        "查不到就写「待补充」。\n\n"
        "上游示例中的具体学科内容只作方法演示，**主产出必须是用户自己的课程内容**。\n"
    )
    with open(sk, "a", encoding="utf-8") as f:
        f.write(block)
    return True


# --------------------------------------------------------------------------
# 自检
# --------------------------------------------------------------------------

def parse_frontmatter(text):
    """提取 YAML frontmatter 文本。

    注意：部分上游技能的 frontmatter 内含注释行（如
    `# AGENT SKILLS STANDARD FIELDS (v2)`），不能用
    `text.split('---')[1]` —— 那样会因为注释行出现在分隔符之前而取错段。
    这里用「第一个 --- 行」到「下一个 --- 行」的位置切片，
    注释行留在段内不影响 name/description 的正则匹配。
    行尾需兼容 CRLF（Windows 上游文件常见），故统一 strip 后比较。
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return None


def he_adapter_gaps(teach_skills):
    """返回**缺少中国高校语境适配**的教学技能名单。

    两种合规形态：
      ① 正文显式引用 `he-context-adapter`
         （上游改编 / 未来新装的技能走追加的「高校语境适配（必读）」块）
      ② 正文有「## 中国高校语境要点」段
         （本项目原创技能把语境**写进正文**，不需要追加块）

    🔴 2026-10-22 修正：形态②原来带 `s in rewritten and ...` 限定 ——
       问的是「它在不在改写清单里」，而不是「语境有没有内建」。
       改写清单是**改写流程的产物**，与本技能无关，于是新写的原创技能
       明明有「## 中国高校语境要点」段，却被判成"缺高校适配"。
       现在形态②只看**段是否存在**。

    这不是循环判据：删掉或改名那一段，检查照样会红
    （那正是"缺高校语境适配"该有的表现），
    而且上游技能是英文的、本就没有这个中文段，仍必须走 ①。
    `selftest()` 里有一项专门的自测证明这条判据没被放宽成永远绿。
    """
    gaps = []
    for s, text in teach_skills:
        if "he-context-adapter" in text:
            continue
        if "## 中国高校语境要点" in text:
            continue
        gaps.append(s)
    return gaps


def selftest():
    """离线自检：校验技能包结构与适配覆盖。"""
    failures = []
    checks = 0

    checks += 1
    if not os.path.isdir(SKILLS_DIR):
        failures.append("skills/ dir missing")
        return checks, failures

    skills = sorted(
        d for d in os.listdir(SKILLS_DIR)
        if os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md"))
    )
    checks += 1
    if len(skills) < 10:
        failures.append(f"too few skills installed: {len(skills)}")

    # 每个 SKILL.md 必须有 frontmatter 且含 name/description
    # 注意：必须读全文——部分技能的 frontmatter 本身就超过 8KB
    # （input_schema / output_schema / evidence_sources 很长），
    # 只读前 N 字符会截断在分隔符之前，误判成「无 frontmatter」。
    bad_meta = []
    for s in skills:
        p = os.path.join(SKILLS_DIR, s, "SKILL.md")
        head = open(p, encoding="utf-8", errors="replace").read()
        fm = parse_frontmatter(head)
        if fm is None:
            bad_meta.append(f"{s}: no frontmatter")
            continue
        if not re.search(r"^name:\s*\S", fm, re.M):
            bad_meta.append(f"{s}: no name in frontmatter")
        if not re.search(r"^description:\s*\S", fm, re.M):
            bad_meta.append(f"{s}: no description in frontmatter")
    checks += 1
    if bad_meta:
        failures.append(f"frontmatter issues: {bad_meta[:5]}")

    # 教学技能必须有高校适配
    # 判据不能只抽查几个 —— 任何缺失都会让产出带着 K-12 痕迹漏到用户手里。
    # 判定「教学技能」用 frontmatter 的 tags / skill_id 里是否出现教学域标记，
    # 以及正文里有没有「中国高校语境要点」段（原创教学技能必然有这一段）。
    teach_markers = (
        "curriculum", "assessment", "instruction", "learning", "pedagog",
        "literacy", "teaching", "student", "questioning", "memory",
        "self-regulated", "inclusive", "professional-learning",
        "original-frameworks", "ai-learning-science", "student-learning",
        "中国高校语境要点",
    )
    rewritten = set()
    mpath = os.path.join(AGENT_DIR, "references", "rewrite-manifest.json")
    if os.path.isfile(mpath):
        try:
            with open(mpath, encoding="utf-8") as f:
                rewritten = set(json.load(f).get("skills", {}))
        except Exception:
            rewritten = set()
    teach_skills = []
    for s in skills:
        p = os.path.join(SKILLS_DIR, s, "SKILL.md")
        text = open(p, encoding="utf-8", errors="replace").read()
        fm = parse_frontmatter(text) or ""
        head = text[:12000].lower()
        # 改写清单里的 50 个**都是**教学技能 —— 不能只靠英文标记词识别，
        # 否则一个既没有英文标记词、又没有「中国高校语境要点」段的技能
        # 会被当成"不是教学技能"而**静默跳过**适配检查。
        is_teach = (s in rewritten) or (
            any(m in head for m in teach_markers) and not _is_research_skill(s))
        if is_teach:
            teach_skills.append((s, text))

    # 🔴 教学技能必须体现中国高校语境适配，但有**两种合规形态**：
    #   ① 上游改编 / 未来新装的技能 → 必须带追加的「高校语境适配（必读）」块
    #   ② 本项目自己写的技能 → 语境是**写进正文**的，
    #      体现在「## 中国高校语境要点」段，不需要追加块
    # 只认 ① 会把原创技能全判成缺失；只认 ② 会让未来的上游技能绕过适配。
    # 所以两种都认。
    #
    # 🔴 2026-10-22 修正判据：形态②原来写的是 `s in rewritten and ...` ——
    #    问的是「它在不在改写清单里」，而不是「语境有没有内建」。
    #    改写清单是**改写流程的产物**，与"这个技能的语境写没写进正文"无关 ——
    #    于是 2026-10-22 新写的原创技能（`teaching-slide-designer` /
    #    `personal-course-pattern-builder`）明明有「## 中国高校语境要点」段，
    #    却被判成"缺高校适配"。
    #    改法：形态②只看**段是否存在**，不看它在不在清单里。
    #    这不是循环判据：删掉/改名那一段，检查照样会红
    #    （那正是"缺高校语境适配"该有的表现），
    #    而且上游技能是英文的、本就没有这个中文段，仍必须走 ①。
    missing_adapter = he_adapter_gaps(teach_skills)
    checks += 1
    if missing_adapter:
        failures.append(
            f"teaching skills missing HE adapter ({len(missing_adapter)}): {missing_adapter[:8]}"
        )

    # 🔴 判据自测：证明「高校适配」这条判据**没被放宽成永远绿**。
    #    2026-10-22 放宽过一次（形态②去掉了 `s in rewritten` 限定），
    #    放宽必须有自证 —— 否则「放宽」和「关掉检查」长得一模一样。
    _probe = [
        ("显式引用适配器", "见 he-context-adapter 的映射表\n## 中国高校语境要点\n", False),
        ("语境写进正文", "## 中国高校语境要点\n学时制与评价制度换算\n", False),
        ("两者都没有", "普通正文，没有任何高校语境痕迹\n", True),
        ("段被改名", "## 高校场景说明\n学时制与评价制度换算\n", True),
    ]
    _probe_bad = []
    for _label, _text, _should_gap in _probe:
        _gapped = bool(he_adapter_gaps([("probe-skill", _text)]))
        if _gapped != _should_gap:
            _probe_bad.append("%s（期望%s）" % (
                _label, "报缺失" if _should_gap else "不报"))
    checks += 1
    if _probe_bad:
        failures.append("高校适配判据自测失败: %s" % "；".join(_probe_bad))

    # 私有技能必须存在（Agent 的核心能力，不能被巡检误删）
    for req in ["grant-proposal-writer", "exam-question-bank",
                "teaching-file-builder", "skill-scan", "he-context-adapter"]:
        checks += 1
        if req not in skills:
            failures.append(f"required private skill missing: {req}")

    # 论文线原创技能必须存在（2026-10-22 论文线回仓时新增）
    # 少了它们，论文线就只剩上游件，本项目的引用核验/投稿体检能力会静默消失
    for req in ["citation-audit", "assertive-writing", "submission-readiness"]:
        checks += 1
        if req not in skills:
            failures.append(f"required original skill missing: {req}")

    # 排除名单的两条规则必须真的生效
    # ① 名单里不得有**已安装**的技能 —— 「已安装」与「已排除」互斥
    rejected = load_rejected_names()
    checks += 1
    overlap = sorted(rejected & set(skills))
    if overlap:
        failures.append(f"rejected list contains installed skills: {overlap[:8]}")
    # ② 名单里不得有**非技能名** —— 文档表头/散文被逐行读进来就是垃圾条目
    checks += 1
    junk = sorted(n for n in rejected if not SKILL_NAME_RE.match(n))
    if junk:
        failures.append(f"rejected list contains non-skill-name entries: {junk[:8]}")

    # 关键引用文件必须存在
    for rel in [
        "references/he-context-adapter.md",
        "references/faculty-capability-matrix.md",
        "references/rejected-skills.md",
        "agent.md",
    ]:
        checks += 1
        if not os.path.isfile(os.path.join(AGENT_DIR, rel)):
            failures.append(f"missing required file: {rel}")

    # agent.md 必须含自学习段与能力矩阵
    checks += 1
    agent_md = os.path.join(AGENT_DIR, "agent.md")
    if os.path.isfile(agent_md):
        txt = open(agent_md, encoding="utf-8", errors="replace").read()
        for kw in ["自学习", "能力矩阵", "Stop when", "不得编造"]:
            if kw not in txt:
                failures.append(f"agent.md missing keyword: {kw}")

    return checks, failures


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="junior-faculty-agent skill scanner")
    ap.add_argument("--scan", action="store_true", help="scan GitHub for candidate skills")
    ap.add_argument("--no-search", action="store_true",
                    help="skip keyword search (faster; only compare tracked repos)")
    ap.add_argument("--install", metavar="SPEC_JSON", help="install per a decision spec (file path or inline json)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--selftest", action="store_true", help="offline self test")
    args = ap.parse_args()

    if args.selftest:
        checks, failures = selftest()
        print(f"selftest: {checks - len(failures)}/{checks} checks passed")
        for f in failures:
            print(f"  FAIL: {f}")
        return 1 if failures else 0

    if args.install:
        raw = args.install
        if os.path.isfile(raw):
            raw = open(raw, encoding="utf-8").read()
        spec = json.loads(raw)
        specs = spec if isinstance(spec, list) else [spec]
        if len(specs) > MAX_NEW_PER_RUN:
            print(f"[warn] {len(specs)} specs exceeds per-run cap {MAX_NEW_PER_RUN}")
            specs = specs[:MAX_NEW_PER_RUN]
        results = []
        for s in specs:
            ok, msg = install_skill(s)
            if ok and s.get("source_domain") == "teaching":
                append_he_adapter(s["name"])
                msg += " (+HE adapter)"
            results.append({"name": s.get("name"), "ok": ok, "message": msg})
        print(json.dumps(results, ensure_ascii=False, indent=2) if args.json
              else "\n".join(f"{'OK ' if r['ok'] else 'FAIL'} {r['name']}: {r['message']}" for r in results))
        return 0 if all(r["ok"] for r in results) else 1

    if args.scan:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        year, q = quarter_now()
        repos, repo_errors, domain_lib_count = scan_repositories()
        if args.no_search:
            hits, search_errors, groups_done = [], [], 0
        else:
            hits, search_errors, groups_done = scan_search()
        all_errors = repo_errors + search_errors
        rejected = load_rejected_names()
        candidates = []
        seen = set()
        for c in repos:
            if c["name"] in rejected or c["name"] in seen:
                continue
            seen.add(c["name"])
            candidates.append(c)
        # 搜索命中的仓库需要 Agent 二次检视，单独分组
        search_hits = [h for h in hits if h["name"] not in rejected]

        stamp = f"{year}-Q{q}"
        out = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "quarter": stamp,
            "installed_count": len(installed_skill_names()),
            "new_in_tracked_repos": candidates,
            "search_hits": search_hits,
            "search_groups_completed": f"{groups_done}/{len(SEARCH_QUERIES)}",
            "domain_library_skipped": domain_lib_count,
            "requests_used": _request_counter["n"],
            "request_budget": REQUEST_BUDGET,
            "errors": all_errors,
            "scan_complete": not all_errors,
            "note": "安装与否由 Agent 判断；本脚本只负责发现与按决策安装。"
                    "scan_complete=false 表示部分主源或关键词组拉取失败，结论不可全信。"
                    "domain_library_skipped 是被排除的领域方法库技能数（工具封装，非教师基本能力）。",
        }
        path = os.path.join(REPORTS_DIR, f"skill-scan-{stamp}-candidates.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        if args.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(f"quarter: {stamp}")
            print(f"installed skills: {out['installed_count']}")
            print(f"scan_complete: {out['scan_complete']}")
            if all_errors:
                for e in all_errors:
                    print(f"  [ERROR] {e}")
            print(f"search keyword groups completed: {out['search_groups_completed']}")
            print(f"requests used: {out['requests_used']}/{out['request_budget']}")
            print(f"domain-library skills skipped (not faculty capability): {domain_lib_count}")
            print(f"new in tracked repos: {len(candidates)}")
            for c in candidates:
                print(f"  - {c['name']}  <- {c['source_repo']}")
            print(f"search hits (need manual inspection): {len(search_hits)}")
            print(f"report: {path}")
        # 拉取失败时用非零退出码，让调用方（cron）知道这次扫描不完整
        return 0 if out["scan_complete"] else 2

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
