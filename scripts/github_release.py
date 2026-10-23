#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""github_release.py —— 产 GitHub 开源包（源码包 + 发布说明）

    python scripts/github_release.py --build      # 出源码包 + RELEASE_NOTES.md 并自检
    python scripts/github_release.py --verify     # 校验已有的源码包
    python scripts/github_release.py --list       # 看看会打进什么

为什么要有「源码包」，而不用 GitHub 自动生成的 source code (zip)
--------------------------------------------------------------------------
GitHub 会自动为每个 tag 生成源码归档，但**那只是 git 树的一个切片**：
它不带本项目的发布用元数据（MANIFEST、发布说明），也不做**独立校验**。
本脚本产出的源码包是「**可以直接挂到 Release 上**」的那一份，并且带三道自检：

    ① NC 内容断言        —— NC 条款会传染整个分发物（仓库自己的纪律）
    ② 必备件齐全        —— 许可证 / 署名 / CI / 社区文件
    ③ 克隆即用          —— 解压到临时目录，**在副本里**跑 demo 的三层自检

🔴 **第 ③ 条是踩出来的**：文件清单对、sha256 对、包能解开 —— 这三件事全过，
   仍可能一跑就炸（分档包曾因变量未绑定而崩在克隆方第一次运行时）。
   **只有真跑一遍才看得见。**

配置唯一出处：`references/github-release.json`（仓库名 / 描述 / topics）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import package_release as PR  # noqa: E402  （复用排除规则与 NC 断言，避免漂移）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
VERSION = PR.VERSION
CONFIG_REL = "references/github-release.json"

# 源码包 = **整个仓库**（不是某个分档）。因此除了分档包的排除项，
# 还要额外排掉「仓库自己没打算分发的东西」。
SOURCE_EXCLUDE_DIRS = set(PR.EXCLUDE_DIRS) | {"dist", ".github_cache"}
SOURCE_EXCLUDE_FILE_PATTERNS = list(PR.EXCLUDE_FILE_PATTERNS) + [
    "skills-archive/*",
    "*.bak",
    "*.orig",
    "*.rej",
]

# 源码包里**必须**有的件（少一个就不是一个合格的 GitHub 开源项目）
REQUIRED_FILES = [
    "LICENSE",
    "NOTICE.md",
    "THIRD-PARTY-NOTICES.md",
    "README.md",
    "agent.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "references/github-release.json",
]

# 必须**非空**的目录（zip 里空目录等于没有）
REQUIRED_DIRS = ["skills", "scripts", "demo", "licenses", "references"]

# 真实密钥的样子（不是"疑似"，是真的会用的形态）
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),                     # OpenAI
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),              # Anthropic
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),                    # GitHub PAT
    re.compile(r"AKIA[0-9A-Z]{16}"),                        # AWS access key id
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),                  # Google API key
]


def load_config():
    p = os.path.join(ROOT, CONFIG_REL.replace("/", os.sep))
    if not os.path.isfile(p):
        sys.stderr.write("!! 缺发布配置：%s\n" % CONFIG_REL)
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def slug(cfg):
    owner = (cfg.get("owner") or "").strip()
    repo = (cfg.get("repo") or "").strip()
    return ("%s/%s" % (owner, repo)) if owner else ("OWNER/%s" % repo)


def _excluded_file(rel):
    import fnmatch
    base = os.path.basename(rel)
    for pat in SOURCE_EXCLUDE_FILE_PATTERNS:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(base, pat):
            return True
    return False


def collect_source_files():
    """收集**整个仓库**里该进源码包的文件（相对路径，POSIX 风格，排序）。"""
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SOURCE_EXCLUDE_DIRS]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            if _excluded_file(rel):
                continue
            files.append(rel)
    return sorted(set(files))


def find_secrets(files):
    """在源码包里扫真实密钥。"""
    hits = []
    for rel in files:
        if not rel.lower().endswith((".md", ".json", ".py", ".txt", ".yml",
                                     ".yaml", ".toml", ".cfg", ".sh", ".ps1")):
            continue
        p = os.path.join(ROOT, rel.replace("/", os.sep))
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        for pat in SECRET_PATTERNS:
            m = pat.search(text)
            if m:
                hits.append("%s: %s…" % (rel, m.group(0)[:12]))
    return hits


def missing_required(files):
    """返回「缺哪些必备件」：文件必须在列表里，目录必须**非空**。

    🔴 目录不能按"在不在文件列表里"判 —— 空目录在 zip 里等于没有，
       而"有目录名但一个文件都没有"是最容易被漏掉的一种残缺。
    """
    out = []
    for r in REQUIRED_FILES:
        if r not in files:
            out.append(r)
    for d in REQUIRED_DIRS:
        if not any(f.startswith(d + "/") for f in files):
            out.append(d + "/")
    return out


def source_zip_path():
    return os.path.join(DIST, "junior-faculty-agent-%s-source.zip" % VERSION)


def top_dir():
    return "junior-faculty-agent-%s" % VERSION


def build(cfg):
    files = collect_source_files()

    problems = []
    problems += PR.assert_no_nc(files)
    problems += find_secrets(files)

    missing = missing_required(files)
    if missing:
        problems.append("源码包缺必备件：%s" % ", ".join(missing))

    # skills/ 下必须真的有技能（空目录在 zip 里等于没有）
    if not any(f.startswith("skills/") for f in files):
        problems.append("源码包里没有任何技能")

    if problems:
        sys.stderr.write("!! 中止出源码包：\n")
        for p in problems:
            sys.stderr.write("   - %s\n" % p)
        return 1

    manifest = {
        "name": "junior-faculty-agent",
        "version": VERSION,
        "kind": "github-source",
        "slug": slug(cfg),
        "description": cfg.get("description", ""),
        "topics": cfg.get("topics", []),
        "primary_branch": cfg.get("primary_branch", "main"),
        "commercial_use": True,
        "noncommercial_included": False,
        "profile": "source",
        "profile_label": "源码包（整个仓库）",
        "skill_count": len(PR.profile_map.installed_skills()),
        "file_count": len(files),
        "files": {rel: PR.sha256_of(os.path.join(ROOT, rel.replace("/", os.sep)))
                  for rel in files},
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False,
                                sort_keys=True, indent=2).encode("utf-8")

    os.makedirs(DIST, exist_ok=True)
    out = source_zip_path()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(os.path.join(ROOT, rel.replace("/", os.sep)),
                    "%s/%s" % (top_dir(), rel))
        z.writestr("%s/MANIFEST.json" % top_dir(), manifest_bytes)

    notes = write_release_notes(cfg, files)
    print("已出源码包: %s" % out)
    print("  文件数  : %d（另含 MANIFEST.json）" % len(files))
    print("  顶层目录: %s/" % top_dir())
    print("  发布说明: %s" % notes)
    print("  体积    : %.1f KB" % (os.path.getsize(out) / 1024))
    return verify(out, cfg)


def write_release_notes(cfg, files):
    """生成发布说明：CHANGELOG 的当期内容 + 本次产物清单。"""
    out = os.path.join(DIST, "RELEASE_NOTES.md")
    sl = slug(cfg)
    ver = VERSION

    body = ""
    ch = os.path.join(ROOT, "CHANGELOG.md")
    if os.path.isfile(ch):
        with open(ch, encoding="utf-8") as f:
            text = f.read()
        m = re.search(r"^## \[%s\][^\n]*\n(.*?)(?=^## \[|\Z)" % re.escape(ver),
                      text, re.S | re.M)
        if m:
            body = m.group(1).strip()

    # 产物清单：从已经打出来的包里读（不在包里就不列）
    assets = []
    for name in sorted(os.listdir(DIST)) if os.path.isdir(DIST) else []:
        if not name.endswith(".zip"):
            continue
        p = os.path.join(DIST, name)
        try:
            with zipfile.ZipFile(p) as z:
                # 🔴 MANIFEST 可能不在根（源码包在带版本号的顶层目录下）——
                #    只读 "MANIFEST.json" 会 KeyError，然后被 except 静默跳过
                #    ⇒ **源码包会从下载表里消失**，而表看起来是完整的。
                mans = [n for n in z.namelist() if n.endswith("MANIFEST.json")]
                if not mans:
                    continue
                man = json.loads(z.read(mans[0]).decode("utf-8"))
        except Exception:
            continue
        label = man.get("profile_label") or man.get("profile") or "?"
        assets.append((name, label, man.get("file_count", 0),
                       man.get("skill_count", 0)))

    lines = [
        "# %s v%s" % (cfg.get("repo", "junior-faculty-agent"), ver),
        "",
        (cfg.get("release_notes_intro") or "").strip(),
        "",
        "## 下载",
        "",
        "| 资产 | 档位 | 文件数 | 技能数 |",
        "|---|---|---|---|",
    ]
    for name, prof, fc, sc in assets:
        lines.append("| `%s` | %s | %d | %d |" % (name, prof, fc, sc))
    src = "junior-faculty-agent-%s-source.zip" % ver
    if not any(a[0] == src for a in assets):
        lines.append("| `%s` | 源码包（整个仓库） | — | — |" % src)
    lines += [
        "",
        "> 源码包 `%s` 内含完整仓库与 `MANIFEST.json`（逐文件 sha256）。" % src,
        "> 三档分发包是**内容切片**（技能集合由能力矩阵的能力域机械推导，不是手工枚举）。",
        "",
        "## 安装与自检",
        "",
        "```bash",
        "unzip %s && cd junior-faculty-agent-%s" % (src, ver),
        "",
        "python scripts/verify_repo.py        # 文档 ↔ 现实一致性",
        "python scripts/verify_rewrite.py     # 结构合规 + 全仓交叉引用",
        "python demo/selftest.py              # 判据的变异测试",
        "python demo/run_demo.py --out demo/out   # 离线端到端",
        "```",
        "",
        "> Windows 上请先设 `PYTHONIOENCODING=utf-8`（中文控制台默认 GBK，",
        "> 子进程输出非 GBK 字符会崩，父进程只看到「退出码 1」）。",
        "",
        "## 许可",
        "",
        "- 本仓库原创内容：**MIT**",
        "- 第三方内容：各自保留原许可，全文副本在 `licenses/`，台账在 `THIRD-PARTY-NOTICES.md`",
        "- **NonCommercial（CC BY-NC）内容不随本仓库与任何分发包分发**",
        "",
    ]
    if body:
        lines += ["## 本版内容", "", body, ""]
    lines += [
        "---",
        "",
        "仓库：https://github.com/%s" % sl,
        "",
    ]

    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return out


def verify(zip_path, cfg=None):
    """校验源码包：清单对、sha256 对、无 NC、必备件齐、**克隆即用**。"""
    problems = []
    if not os.path.isfile(zip_path):
        print("FAIL  源码包不存在: %s" % zip_path)
        return 1

    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        man_name = "%s/MANIFEST.json" % top_dir()
        if man_name not in names:
            print("FAIL  包内缺 MANIFEST.json")
            return 1
        manifest = json.loads(z.read(man_name).decode("utf-8"))

        payload = [n for n in names if n != man_name]
        prefix = top_dir() + "/"
        rels = []
        outside = []
        for n in payload:
            if n.startswith(prefix):
                rels.append(n[len(prefix):])
            else:
                outside.append(n)
        if outside:
            problems.append("包内有不在顶层目录下的文件：%s" % ", ".join(outside[:5]))

        registered = set(manifest.get("files") or {})
        extra = sorted(set(rels) - registered)
        missing = sorted(registered - set(rels))
        if extra:
            problems.append("包内有未登记文件: %s" % ", ".join(extra[:5]))
        if missing:
            problems.append("登记了但包里没有: %s" % ", ".join(missing[:5]))

        bad = []
        for rel, want in (manifest.get("files") or {}).items():
            full = prefix + rel
            if full not in names:
                continue
            import hashlib
            got = hashlib.sha256(z.read(full)).hexdigest()
            if got != want:
                bad.append(rel)
        if bad:
            problems.append("校验和不符: %s" % ", ".join(bad[:5]))

        # NC 断言（对**包内实际内容**，不信任登记表）
        problems += PR.assert_no_nc(rels)

        miss_req = missing_required(rels)
        if miss_req:
            problems.append("包内缺必备件: %s" % ", ".join(miss_req[:6]))

    if problems:
        print("FAIL  源码包校验不通过:")
        for p in problems:
            print("   - %s" % p)
        return 1

    # 克隆即用：解压到临时目录，在**副本**里跑 demo 的三层自检
    problems = PR.clone_and_run(zip_path, strip_prefix=top_dir() + "/")
    if problems:
        print("FAIL  源码包「克隆即用」复核未通过:")
        for p in problems:
            print("   - %s" % p)
        return 1

    print("PASS  GitHub 源码包校验通过")
    print("  文件数    : %d" % manifest.get("file_count", 0))
    print("  仓库标识  : %s" % manifest.get("slug", "?"))
    print("  商业可用  : %s（不含 NonCommercial）" % manifest.get("commercial_use"))
    print("  克隆即用  : 已通过（包内 demo 自检 + 大纲唯一事实源 + 端到端）")
    return 0


def show_list(cfg):
    files = collect_source_files()
    print("GitHub 源码包将包含 %d 个文件" % len(files))
    for f in files[:30]:
        print("   %s" % f)
    if len(files) > 30:
        print("   ... 其余 %d 个" % (len(files) - 30))
    print()
    problems = PR.assert_no_nc(files) + find_secrets(files)
    missing = missing_required(files)
    if missing:
        problems.append("缺必备件：%s" % ", ".join(missing))
    if problems:
        print("!! 以下问题会被拦截:")
        for p in problems:
            print("   - %s" % p)
        return 1
    print("预检: 通过")
    return 0


def main():
    ap = argparse.ArgumentParser(description="产 GitHub 开源包（源码包 + 发布说明）")
    ap.add_argument("--build", action="store_true", help="出源码包与发布说明并自检")
    ap.add_argument("--verify", action="store_true", help="校验已有源码包")
    ap.add_argument("--list", action="store_true", help="列出将打进的文件")
    args = ap.parse_args()

    cfg = load_config()
    if cfg is None:
        return 2

    if args.verify:
        return verify(source_zip_path(), cfg)
    if args.list:
        return show_list(cfg)
    if args.build:
        return build(cfg)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
