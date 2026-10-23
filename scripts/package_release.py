#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""package_release.py —— 出可商用分发包（纯标准库）

    python scripts/package_release.py --build                     # 出完整包（默认）+ 自检
    python scripts/package_release.py --build --profile teaching   # 出教学分档包
    python scripts/package_release.py --build --profile research  # 出科研分档包
    python scripts/package_release.py --verify <zip>               # 校验已有分发包
    python scripts/package_release.py --list --profile teaching    # 看看会打进什么

出包时**断言**分发物中不存在任何 NonCommercial（CC BY-NC）内容：
NonCommercial 条款会传染到整个分发物 —— 只要有一份 NC 材料在包里，
整个包就不能商用。这是本项目"可商用"承诺的机械保证。

🔴 **分档出包**（`--profile`）：包内技能集合**不是手工枚举**的，而是由
   「能力矩阵的能力域」机械推导（`scripts/profile_map.py` 是唯一推导源，
   数据在 `references/profiles.json`）。推导不自洽 ⇒ **中止出包**，
   绝不打一个来路不明的包。

   · full     —— 全部已装技能（默认，不带后缀文件名）
   · teaching —— 能力域 A/B/C/D/F（教学准备、实施、评价、学生支持、教研）
   · research —— 能力域 E（科研全流程）

   `licenses/` 按**包内实际技能**动态决定：包内没有 Apache 技能就不带 Apache 副本，
   少了副本则是再分发义务未履行（Apache §4(a) / MIT 保留声明）。

分发包内含 MANIFEST.json（文件清单 + 每文件 sha256 + 档位与技能清单），可独立校验。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import profile_map  # noqa: E402  （唯一推导源）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = "1.0.0"
DIST = os.path.join(ROOT, "dist")

# ── 绝对不能进分发物的路径前缀 / 文件名 ─────────────────────────
EXCLUDE_DIRS = {".git", ".cache", "__pycache__", "dist", ".venv",
                "skills-archive", ".pytest_cache"}
EXCLUDE_FILE_PATTERNS = [
    ".agent-instance-id",
    "reports/*-candidates.json",
    "demo/out/*",
    "*.pyc",
    ".env",
    ".env.*",
    "~$*",
]
# NC 技能名单：出现即中止出包
NC_SKILLS = {"academic-paper", "academic-paper-reviewer", "deep-research",
             "sr-screener"}
# NC 许可全文
NC_LICENSE_MARKERS = ("CC-BY-NC", "by-nc")

# 顶层文件：白名单。社区文件（CHANGELOG / CONTRIBUTING / SECURITY …）也进包 ——
# 一个分发物应该自带"这是什么、怎么改、怎么报问题、许可是什么"。
TOP_LEVEL_FILES = ["agent.md", "README.md", "LICENSE", "NOTICE.md",
                   "THIRD-PARTY-NOTICES.md", ".gitignore",
                   "CHANGELOG.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
                   "SECURITY.md", ".gitattributes", ".editorconfig"]
TOP_LEVEL_DIRS = ["skills", "references", "scripts", "licenses", "crons",
                  "reports", "demo", ".github"]


def _excluded_file(rel):
    import fnmatch
    base = os.path.basename(rel)
    for pat in EXCLUDE_FILE_PATTERNS:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(base, pat):
            return True
    return False


def skill_dirs_in(files):
    """文件集合里出现的技能目录名集合。"""
    out = set()
    for rel in files:
        parts = rel.split("/")
        if len(parts) >= 3 and parts[0] == "skills":
            out.add(parts[1])
    return out


def license_copies_in(files):
    """文件集合里 `licenses/` 下的文件名集合。"""
    return set(os.path.basename(r) for r in files
               if r.startswith("licenses/") and os.path.basename(r))


def collect_files(profile="full", skills=None):
    """收集要进包的文件（相对路径，POSIX 风格，排序）。

    build 与 verify 共用这一个实现 —— 两套收集逻辑必然漂移，
    且漂移是静默的（包看起来正常，实际少打/多打了文件）。

    分档时按 `skills` 筛掉不在本档的技能目录，按**包内实际技能**筛 `licenses/`。
    """
    if skills is None:
        skills = profile_map.profile_skill_set(profile)
    licenses = profile_map.required_license_copies(skills)

    files = []
    for name in TOP_LEVEL_FILES:
        p = os.path.join(ROOT, name)
        if os.path.isfile(p):
            files.append(name)
    for d in TOP_LEVEL_DIRS:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if x not in EXCLUDE_DIRS]
            at_top = os.path.abspath(dirpath) == os.path.abspath(base)
            if d == "skills" and at_top:
                # 只保留本档的技能目录（子目录不受影响）
                dirnames[:] = [x for x in dirnames if x in skills]
            if d == "licenses" and at_top:
                filenames = [f for f in filenames if f in licenses]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
                if _excluded_file(rel):
                    continue
                files.append(rel)
    return sorted(set(files))


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_no_nc(files):
    """断言文件集合里没有任何 NonCommercial 内容。"""
    problems = []
    for rel in files:
        parts = rel.split("/")
        if any(p in NC_SKILLS for p in parts):
            problems.append("含 NC 技能目录: " + rel)
        if parts[0] == "skills-archive":
            problems.append("含 skills-archive 路径: " + rel)
        if any(m in rel for m in NC_LICENSE_MARKERS):
            problems.append("含 NC 许可全文: " + rel)
    return problems


def assert_license_copies(files, read_text=None):
    """断言：**有再分发义务的许可**，其副本必须**在包内**。

    🔴 为什么出包器也要查这一条（verify_repo 已经查过）：
    Apache-2.0 §4(a) 要求"再分发时必须向接收方提供本许可的副本"；
    MIT 要求"保留版权声明与许可声明"。仓库里有副本 ≠ 包里有副本 ——
    出包器是**最后一道闸**，它面对的是"最终交付物"，判据必须落在交付物上。
    （verify_repo 查的是仓库状态，package_release 查的是分发物状态。）

    判据**从包内技能自己的 frontmatter 派生**，不写死技能名（见 profile_map）：
      ① frontmatter 提到 K-Dense        → 需 MIT-K-Dense.txt
      ② 声明 Apache-2.0                 → 需 Apache-2.0-<技能名>.txt
      ③ 在改写清单里（教育侧上游改编）   → 需 CC-BY-SA-4.0-education-agent-skills.txt
      ④ origin 提到 OpenMAIC            → 需 OpenMAIC-MIT.txt
    """
    if read_text is None:
        def read_text(rel):
            p = os.path.join(ROOT, rel)
            if not os.path.isfile(p):
                return ""
            with open(p, encoding="utf-8", errors="replace") as f:
                return f.read()

    skills = skill_dirs_in(files)
    need = profile_map.required_license_copies(
        skills, fm_reader=lambda n: read_text("skills/%s/SKILL.md" % n)[:4000])
    have = license_copies_in(files)
    missing = sorted(need - have)
    problems = ["包内缺许可副本 %s（对应技能需要它）" % m for m in missing]
    return problems


def manifest_licenses(skills):
    """按包内实际技能生成 MANIFEST 的许可台账。"""
    out = {"own_original": "MIT"}
    rewritten = profile_map.rewrite_manifest_skills()
    kdense = apache = openmaic = edu = False
    for name in sorted(skills):
        fm = profile_map.read_text(os.path.join("skills", name, "SKILL.md"))[:4000]
        if not fm:
            continue
        if "K-Dense" in fm:
            kdense = True
        m = re.search(r"(?m)^license:\s*([^\r\n]+?)\s*$", fm)
        if m and "apache" in m.group(1).lower():
            apache = True
        if re.search(r"(?m)^\s*origin:.*OpenMAIC", fm):
            openmaic = True
        if name in rewritten:
            edu = True
    if kdense:
        out["kdense_skills"] = "MIT"
    if apache:
        out["markdown-mermaid-writing"] = "Apache-2.0"
    if openmaic:
        out["openmaic_derived"] = "MIT（Copyright (c) 2026 THU-MAIC；只适配方法论内核）"
    if edu:
        out["education_agent_skills"] = "CC BY-SA 4.0 (仅供追溯；本仓库未复制其内容)"
    return out


def package_path(profile):
    if profile == "full":
        return os.path.join(DIST, "junior-faculty-agent-%s.zip" % VERSION)
    return os.path.join(DIST, "junior-faculty-agent-%s-%s.zip" % (VERSION, profile))


def build(profile="full"):
    prof = profile_map.load_profiles()

    # 🔴 推导不自洽 ⇒ 中止。先验后动：代价最小的失败点应该在打包之前。
    inv = profile_map.invariant_problems(prof)
    if inv:
        sys.stderr.write("!! 中止出包：分档推导不自洽\n")
        for p in inv:
            sys.stderr.write("   - " + p + "\n")
        return 2

    skills = profile_map.profile_skill_set(profile, prof=prof)
    files = collect_files(profile, skills)
    problems = assert_no_nc(files) + assert_license_copies(files)

    # 包内技能集必须与推导结果**逐个相等**（多一个少一个都要报出来）
    got = skill_dirs_in(files)
    if got != set(skills):
        problems.append("包内技能集与推导不一致：多 %s / 少 %s"
                        % (", ".join(sorted(got - set(skills))) or "无",
                           ", ".join(sorted(set(skills) - got)) or "无"))

    if problems:
        sys.stderr.write("!! 中止出包：分发物里混入了 NonCommercial 内容"
                         "或缺少必须的许可副本\n")
        for p in problems:
            sys.stderr.write("   - " + p + "\n")
        return 1

    all_skills = profile_map.installed_skills()
    manifest = {
        "name": "junior-faculty-agent",
        "version": VERSION,
        "profile": profile,
        "profile_label": profile_map.profile_label(profile, prof),
        "profile_domains": profile_map.profile_domains(profile, prof),
        "commercial_use": True,
        "licenses": manifest_licenses(skills),
        "license_copies": sorted(license_copies_in(files)),
        "skill_count": len(skills),
        "skills_included": sorted(skills),
        "skills_excluded": sorted(all_skills - set(skills)),
        "noncommercial_included": False,
        "file_count": len(files),
        "files": {rel: sha256_of(os.path.join(ROOT, rel)) for rel in files},
    }
    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")

    os.makedirs(DIST, exist_ok=True)
    out = package_path(profile)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(os.path.join(ROOT, rel), rel)
        z.writestr("MANIFEST.json", manifest_bytes)

    print("已出包: %s" % out)
    print("  档位    : %s（%s）" % (profile, manifest["profile_label"]))
    print("  文件数  : %d（另含 MANIFEST.json）" % len(files))
    print("  技能数  : %d（未包含 %d）" % (len(skills),
                                          len(manifest["skills_excluded"])))
    print("  许可副本: %d 份" % len(manifest["license_copies"]))
    print("  体积    : %.1f KB" % (os.path.getsize(out) / 1024))
    return verify(out)


def clone_and_run(zip_path, strip_prefix=""):
    """**克隆即用**复核：把包解开，在**解出来的副本**里跑 demo 的三层自检。

    🔴 **这一条是踩出来的**：
       research 分档包不含教学技能，`demo/selftest.py` 曾因变量未绑定而崩溃。
       那时**文件清单对、sha256 对、包能解开** —— 一切校验都绿，
       但克隆方第一次跑就炸。这种问题**只有真跑一遍才看得见**。

    `strip_prefix`：源码包带顶层目录（`junior-faculty-agent-1.0.0/`），
       解压时把它剥掉，副本里才是正常的仓库布局。
       传空串 = 保持原样（分档包没有顶层目录）。

    返回问题列表（空 = 通过）。
    """
    problems = []
    tmp = tempfile.mkdtemp(prefix="jfa_clone_")
    try:
        with zipfile.ZipFile(zip_path) as z:
            if strip_prefix:
                for n in z.namelist():
                    if n.endswith("/"):
                        continue
                    if not n.startswith(strip_prefix):
                        problems.append("包内有不在预期顶层目录下的文件：%s" % n)
                        continue
                    rel = n[len(strip_prefix):]
                    if not rel:
                        continue
                    dest = os.path.join(tmp, rel.replace("/", os.sep))
                    d = os.path.dirname(dest)
                    if d and not os.path.isdir(d):
                        os.makedirs(d)
                    with z.open(n) as src, open(dest, "wb") as out:
                        shutil.copyfileobj(src, out)
            else:
                z.extractall(tmp)
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"

        def _run(args, label):
            p = subprocess.run([sys.executable] + args, cwd=tmp, env=env,
                               capture_output=True, text=True, encoding="utf-8",
                               timeout=300)
            if p.returncode != 0:
                tail = (p.stdout + p.stderr).strip().splitlines()
                problems.append("包内 %s 未通过：%s"
                                % (label, tail[-1] if tail else "退出码 %d" % p.returncode))
            return p.returncode == 0

        selftest = os.path.join(tmp, "demo", "selftest.py")
        if os.path.isfile(selftest):
            _run([selftest], "demo/selftest.py")
        else:
            problems.append("包内缺 demo/selftest.py")

        outline = os.path.join(tmp, "demo", "outline.py")
        if os.path.isfile(outline):
            _run([outline, "--check"], "demo/outline.py --check")
        else:
            problems.append("包内缺 demo/outline.py")

        rundemo = os.path.join(tmp, "demo", "run_demo.py")
        out = os.path.join(tmp, "_out")
        if os.path.isfile(rundemo):
            if _run([rundemo, "--out", out], "demo/run_demo.py"):
                if not os.path.isfile(os.path.join(out, "outline.spec.json")):
                    problems.append("包内 demo 产物缺 outline.spec.json"
                                    "（大纲层被绕过了）")
        else:
            problems.append("包内缺 demo/run_demo.py")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return problems


def verify(zip_path):
    """对分发包做完整校验：文件集合 == 登记表，且每文件 sha256 相符。"""
    problems = []
    if not os.path.exists(zip_path):
        print("FAIL  分发包不存在: %s" % zip_path)
        return 1

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if "MANIFEST.json" in names:
            manifest = json.loads(z.read("MANIFEST.json").decode("utf-8"))
        else:
            print("FAIL  包内缺 MANIFEST.json")
            return 1

        payload = [n for n in names if n != "MANIFEST.json"]
        registered = set(manifest["files"])
        in_zip = set(payload)

        # 🔴 多一个文件或少一个文件都要报出来 ——
        # 只查"登记的在不在包里"会漏掉"包里多了没登记的"
        extra = sorted(in_zip - registered)
        missing = sorted(registered - in_zip)
        if extra:
            problems.append("包内有未登记文件: %s" % ", ".join(extra[:5]))
        if missing:
            problems.append("登记了但包里没有: %s" % ", ".join(missing[:5]))

        # 逐文件校验和
        bad = []
        for rel, want in manifest["files"].items():
            if rel not in in_zip:
                continue
            got = hashlib.sha256(z.read(rel)).hexdigest()
            if got != want:
                bad.append(rel)
        if bad:
            problems.append("校验和不符: %s" % ", ".join(bad[:5]))

        # 商业可用性断言（对**包内实际内容**再查一遍，不信任登记表）
        nc = assert_no_nc(payload)
        if nc:
            problems.append("包内含 NC 内容: %s" % "; ".join(nc[:3]))

        # 再分发义务：包内必须带许可副本（判据来自**包内**技能自己）
        def zread(rel):
            try:
                return z.read(rel).decode("utf-8", "replace")
            except KeyError:
                return ""
        miss = assert_license_copies(payload, read_text=zread)
        if miss:
            problems.append("包内缺必须的许可副本: " + "; ".join(miss[:3]))

        # 分档自洽：包内技能集 / 许可副本集 必须与 MANIFEST 登记的完全一致
        profile = manifest.get("profile", "full")
        declared = set(manifest.get("skills_included") or [])
        actual = skill_dirs_in(payload)
        if declared and actual != declared:
            problems.append("包内技能集与 MANIFEST 不一致：多 %s / 少 %s"
                            % (", ".join(sorted(actual - declared)) or "无",
                               ", ".join(sorted(declared - actual)) or "无"))
        declared_lic = set(manifest.get("license_copies") or [])
        actual_lic = license_copies_in(payload)
        if declared_lic and actual_lic != declared_lic:
            problems.append("包内许可副本与 MANIFEST 不一致：多 %s / 少 %s"
                            % (", ".join(sorted(actual_lic - declared_lic)) or "无",
                               ", ".join(sorted(declared_lic - actual_lic)) or "无"))

        # 关键文件必须在
        for must in ("LICENSE", "NOTICE.md", "THIRD-PARTY-NOTICES.md",
                     "README.md", "agent.md"):
            if must not in in_zip:
                problems.append("包内缺关键文件: %s" % must)

    if problems:
        print("FAIL  分发包校验不通过:")
        for p in problems:
            print("   - " + p)
        return 1

    # 克隆即用：包解开后必须真能跑（文件清单与 sha256 查不出这类问题）
    problems = clone_and_run(zip_path)
    if problems:
        print("FAIL  分发包「克隆即用」复核未通过:")
        for p in problems:
            print("   - " + p)
        return 1

    print("PASS  分发包校验通过")
    print("  档位      : %s（%s）" % (manifest.get("profile", "full"),
                                        manifest.get("profile_label", "")))
    print("  文件数    : %d" % manifest["file_count"])
    print("  商业可用  : %s（不含 NonCommercial）" % manifest["commercial_use"])
    print("  技能目录数: %d" % len(skill_dirs_in(payload)))
    print("  克隆即用  : 已通过（包内 demo 自检 + 大纲唯一事实源 + 端到端）")
    return 0


def show_list(profile="full"):
    prof = profile_map.load_profiles()
    inv = profile_map.invariant_problems(prof)
    skills = profile_map.profile_skill_set(profile, prof=prof)
    files = collect_files(profile, skills)
    problems = assert_no_nc(files)
    print("档位 %s（%s）：将打包 %d 个文件"
          % (profile, profile_map.profile_label(profile, prof), len(files)))
    for f in files[:20]:
        print("   " + f)
    if len(files) > 20:
        print("   ... 其余 %d 个" % (len(files) - 20))
    print()
    if inv:
        print("!! 分档推导不自洽（出包会被中止）:")
        for p in inv:
            print("   - " + p)
        return 1
    if problems:
        print("!! 以下 NC 内容会被拦截:")
        for p in problems:
            print("   - " + p)
        return 1
    print("NC 检查: 通过（无 NonCommercial 内容）")
    return 0


def main():
    ap = argparse.ArgumentParser(description="出可商用分发包")
    ap.add_argument("--build", action="store_true", help="出包并自检")
    ap.add_argument("--verify", metavar="ZIP", help="校验已有分发包")
    ap.add_argument("--list", action="store_true", help="列出将打包的文件")
    ap.add_argument("--profile", default="full",
                    help="分档：full（默认）/ teaching / research")
    args = ap.parse_args()

    if args.profile not in profile_map.profile_names():
        sys.stderr.write("未知档位 %s（可选 %s）\n"
                         % (args.profile, ", ".join(profile_map.profile_names())))
        return 2

    if args.verify:
        return verify(args.verify)
    if args.list:
        return show_list(args.profile)
    if args.build:
        return build(args.profile)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
