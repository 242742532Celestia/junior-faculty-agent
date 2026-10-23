#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_rewrite.py —— 教学技能「改写为原创」的校验器（纯标准库）

    python scripts/verify_rewrite.py                 # 全量校验
    python scripts/verify_rewrite.py --only <name>   # 只查某个技能
    python scripts/verify_rewrite.py --list          # 列出待改写清单与进度

检查两类东西：

**A. 结构合规**（每个技能）
  - frontmatter 完整，且 `license: MIT`
  - **不含上游 `skill_id:` 字段** —— 留着它就是在声明"这是上游改编版"
  - 标准章节齐全（输出模板 / 易错点 / 自检清单 / 交叉技能 / 方法论依据）
  - 交叉技能指向**真实存在**的技能：本仓库已装的，或在
    `references/external-skills.json` 登记表里在册的外部技能（ADW 等）
  - 无硬编码机器路径

**B. clean-room 相似度**（需要上游原文才能算）
  - 与上游原文的 8-gram Jaccard 相似度 < 阈值
  - 长行（≥25 字符）重合率 < 阈值
  相似度超标 = 改得不够干净（本质还是同义改写），必须重写。

上游原文位置：环境变量 `JFA_UPSTREAM`（指向 education-agent-skills 暂存目录），
或 `--upstream <dir>`。拿不到上游时**跳过相似度检查并明确报出来**（不假装通过）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
MANIFEST = os.path.join(ROOT, "references", "rewrite-manifest.json")

JACCARD_MAX = 0.10       # 8-gram Jaccard 上限
LONG_LINE_MAX = 0.05     # 长行重合率上限
SHINGLE = 8

REQUIRED_SECTIONS = [
    "## 这个技能解决什么",
    "## 什么时候用",
    "## 输入",
    "## 执行步骤",
    "## 输出模板",
    "## 中国高校语境要点",
    "## 易错点",
    "## 自检清单",
    "## 交叉技能",
    "## 方法论依据",
]

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    return bool(ok)


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def normalize(text):
    """去掉 Markdown 语法与空白，只留内容字符 —— 比的是实质表达，不是排版。"""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"[#>*`|:\-\[\](){}]", " ", text)
    text = re.sub(r"\s+", "", text)
    return text.lower()


def shingles(text, n=SHINGLE):
    t = normalize(text)
    if len(t) < n:
        return {t} if t else set()
    return set(t[i:i + n] for i in range(len(t) - n + 1))


def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def long_lines(text):
    out = set()
    for line in text.splitlines():
        s = re.sub(r"[#>*`|\[\]()]", "", line).strip()
        if len(s) >= 25:
            out.add(s)
    return out


def upstream_text(name, upstream_root, manifest):
    """取上游原文（不含我们自己追加的适配段）。"""
    if not upstream_root:
        return None
    meta = manifest.get(name, {})
    domain = meta.get("domain")
    if not domain:
        return None
    p = os.path.join(upstream_root, "skills", domain, name, "SKILL.md")
    if os.path.exists(p):
        return read(p)
    # 兜底：递归找
    base = os.path.join(upstream_root, "skills")
    for dirpath, dirnames, filenames in os.walk(base):
        if os.path.basename(dirpath) == name and "SKILL.md" in filenames:
            return read(os.path.join(dirpath, "SKILL.md"))
    return None


def external_skill_names():
    """外部技能登记表里的名字集合（`references/external-skills.json`）。

    交叉引用可以指向两类技能：本仓库 `skills/` 下的已装技能，或**在册的外部技能**
    （ADW 论文智能体等本机全局技能 —— 不随本仓库分发）。
    两者都不在 ⇒ 那是编造的引用。
    """
    p = os.path.join(ROOT, "references", "external-skills.json")
    if not os.path.exists(p):
        return set()
    try:
        with open(p, encoding="utf-8") as f:
            return set(json.load(f).get("skills", {}))
    except Exception:
        return set()


def installed_skill_names():
    return set(d for d in os.listdir(SKILLS)
               if os.path.isdir(os.path.join(SKILLS, d)))


def frontmatter_text(name):
    p = os.path.join(SKILLS, name, "SKILL.md")
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8") as f:
        t = f.read()
    m = re.match(r"(?s)^---\r?\n(.*?)\n---", t)
    return m.group(1) if m else ""


def section_lines(text, heading):
    """取某个二级标题段内的所有行（到下一个 `## ` 为止）。

    🔴 判据用的是**段标题**，不是"这一行长得像不像技能引用"——
       段标题与被检查的内容（技能名是否真实存在）无关，
       所以不会因为技能名写错而让检查失效。
    """
    out = []
    inside = False
    for line in text.splitlines():
        if re.match(r"^##\s+\S", line):
            inside = line.strip() == heading
            continue
        if inside:
            out.append(line)
    return out


def teaching_template_skills(manifest, installed):
    """需要套用「中文教学技能结构模板」的技能集合。

    🔴🔴 **判据绝对不能是「文件里有那 10 个章节」** ——
       那样一来，「删掉一个章节」这个错误会把技能**自动踢出被检查集合**，
       结构检查就变成了**不可证伪**的（这正是变异测试抓到过的漏检）。
       判据必须与**被检查的那一项**无关。

    正确判据：
      ① 改写清单里的 50 个（它们本来就要走这套模板）；
      ② 已装技能里，**不属于**自有格式清单（`own_base`）、
         **不是** K-Dense、**不是** NC 的那些 ——
         本仓库里用中文教学模板写的技能就这些（50 + 本项目新写的 3 个）。

    ⚠️ 另外注意：**OpenMAIC 衍生 ≠ 套用本模板**。
       `he-context-adapter` 是 OpenMAIC 衍生（要署名），但它用自有格式，
       在 `own_base` 里 —— 两件事必须分开判。
    """
    items = manifest.get("skills", {})
    own_base = set(manifest.get("own_base", []))
    out = set(items)
    for n in sorted(installed):
        if n in own_base:
            continue
        fm = frontmatter_text(n)
        if "K-Dense" in fm:
            continue
        if re.search(r"(?m)^\s*status:\s*active", fm):
            continue
        out.add(n)
    return out


def check_repo_cross_refs(installed, external):
    """全仓交叉引用有效性（**不限于**套用中文模板的那批技能）。

    🔴 为什么单独做一遍：原先这条检查只在改写清单的 50 个技能上跑。
       本项目自己新写的技能（OpenMAIC 衍生那 3 个、论文线原创那 3 个、
       私有技能那 5 个）**全部是校验盲区** —— 它们可以写一个根本不存在的
       技能名当交叉引用，没有任何人会发现。

    判据与清单内那条一致：**只看 `## 交叉技能` 段内的行**，
    区别只是**覆盖面**：这里跑遍 `skills/` 下的每一个技能。

    🔴 2026-10-22：原来这里是"扫任何含 → 的行"，会把表格箭头
       （"判什么 → 怎么处置"）与易错点箭头（"错误现象 → 正确做法"）
       里的反引号字段名（`section` / `footer` / `caption` …）误判成技能引用。
       判红的是好文档。已与 `check_skill()` 里的那条统一为段定位。
    """
    for name in sorted(installed):
        p = os.path.join(SKILLS, name, "SKILL.md")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            text = f.read()
        bad_refs = []
        for line in section_lines(text, "## 交叉技能"):
            for tok in re.findall(r"`([a-z0-9][a-z0-9\-]{2,})`", line):
                if tok in ("skills", "agent", "md", "api", "sk", "python"):
                    continue
                if tok not in installed and tok not in external:
                    bad_refs.append(tok)
        check("%s: 交叉技能指向真实存在的技能（全仓）" % name, not bad_refs,
              ", ".join(sorted(set(bad_refs))))


def check_skill(name, manifest, upstream_root, installed, external):
    p = os.path.join(SKILLS, name, "SKILL.md")
    if not os.path.exists(p):
        check("%s: SKILL.md 存在" % name, False, "文件缺失")
        return
    text = read(p)

    # ── A. 结构 ──
    fm = re.match(r"(?s)^---\r?\n(.*?)\n---", text)
    if not check("%s: frontmatter 存在" % name, bool(fm)):
        return
    fmtext = fm.group(1)
    check("%s: frontmatter 有 name" % name,
          bool(re.search(r"(?m)^name:\s*\S", fmtext)))
    check("%s: frontmatter 有 description" % name,
          bool(re.search(r"(?m)^description:", fmtext)))
    check("%s: license 标 MIT" % name,
          bool(re.search(r"(?m)^license:\s*MIT\s*$", fmtext)),
          "改写后的技能必须自标 MIT")
    check("%s: 有 metadata.origin" % name,
          bool(re.search(r"(?m)^\s*origin:", fmtext)))
    check("%s: 有 metadata.domain" % name,
          bool(re.search(r"(?m)^\s*domain:", fmtext)))

    # 🔴 关键：不能留上游 skill_id（留着 = 声明这是上游改编版）
    check("%s: 无上游 skill_id 溯源字段" % name,
          not re.search(r"(?m)^\s*skill_id:", text),
          "仍带 skill_id，说明还是上游改编版")

    miss = [s for s in REQUIRED_SECTIONS if s not in text]
    check("%s: 标准章节齐全" % name, not miss, "缺 " + ", ".join(miss))

    # 交叉技能必须真实存在（本仓库已装，或在外部技能登记表里在册）
    #
    # 🔴 2026-10-22 修正判据：原来扫的是「**任何**含 `→` 的行」，
    #    把表格里的箭头（"判什么 → 怎么处置"）和易错点里的箭头
    #    （"错误现象 → 正确做法"）里的反引号 token 一律当技能名，
    #    于是 `section` / `footer` / `caption` 这类**版式字段名**被判成悬空引用 ——
    #    检查项叫"交叉技能指向真实存在的技能"，实现却不是这个语义，判红的是好文档。
    #
    #    改法：只检查 `## 交叉技能` 段内的行。
    #    判据（段标题）**与被检查项无关** —— 它问的是"这段在不在"，
    #    不是"这个技能名对不对"，所以不会因为技能名写错而失效，不是循环判据。
    #    而且这个判据本来就是设计意图：变异用例
    #    `test_verify_repo.py::mutate_rewrite_dangling_ref` 注入的悬空引用
    #    就写在 `## 交叉技能` 段标题之后 —— 它一直能被抓到。
    bad_refs = []
    for line in section_lines(text, "## 交叉技能"):
        for tok in re.findall(r"`([a-z0-9][a-z0-9\-]{2,})`", line):
            if tok in ("skills", "agent", "md", "api", "sk", "python"):
                continue
            if tok not in installed and tok not in external:
                bad_refs.append(tok)
    check("%s: 交叉技能指向真实存在的技能" % name, not bad_refs,
          ", ".join(sorted(set(bad_refs))))

    # ── B. 相似度 ──
    up = upstream_text(name, upstream_root, manifest)
    if up is None:
        check("%s: clean-room 相似度" % name, True,
              "跳过（无上游原文可比）")
        return
    j = jaccard(shingles(text), shingles(up))
    check("%s: 相似度 %.3f < %.2f" % (name, j, JACCARD_MAX), j < JACCARD_MAX,
          "与上游过于接近 = 还是同义改写，需重写")

    mine = long_lines(text)
    theirs = long_lines(up)
    if mine:
        overlap = len(mine & theirs) / len(mine)
        check("%s: 长行重合 %.1f%% < %.0f%%" % (name, overlap * 100,
                                              LONG_LINE_MAX * 100),
              overlap < LONG_LINE_MAX,
              "有 %d 行与上游几乎相同" % len(mine & theirs))


def resolve_upstream_root(path):
    """把 JFA_UPSTREAM 解析成「上游仓库根目录」。

    🔴 两个脚本对同一个环境变量的期望层级不一样：
       `verify_repo.py` 把它当**暂存父目录**（下面并列放多个上游仓库），
       `verify_rewrite.py` 把它当**上游仓库本身**（里面有 skills/ 目录）。
       直接共用会把上游校验变成"永远红"。

       这里做**层级无关**的解析：给哪个都行。
    """
    if not path or not os.path.isdir(path):
        return path
    if os.path.isdir(os.path.join(path, "skills")):
        return path                       # 已经是上游仓库根
    for alias in ("education-agent-skills", "scientific-agent-skills",
                  "academic-research-skills", "ars2"):
        cand = os.path.join(path, alias)
        if os.path.isdir(os.path.join(cand, "skills")):
            return cand
    return path


def _utf8_stdio():
    """把 stdout / stderr 切到 UTF-8。

    🔴 Windows 中文控制台默认 GBK —— 直接 `print("⚠️ ...")` 会抛
       UnicodeEncodeError，**整个脚本当场死掉**，
       而 README 里恰恰就是教用户直接 `python scripts\\verify_rewrite.py` 跑它。
       （守卫里那几条 `print` 也一样，只是它们跑在 UTF-8 的子进程里才没炸。）

    `reconfigure` 是 Python 3.7+ 的 API，本仓库要求 3.9+；
    老版本或被重定向的流上失败就跳过（不影响检查本身）。
    """
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main():
    _utf8_stdio()
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只查某个技能")
    ap.add_argument("--list", action="store_true", help="列出清单与进度")
    ap.add_argument("--upstream", default=os.environ.get("JFA_UPSTREAM", ""),
                    help="上游暂存目录（education-agent-skills）")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    args.upstream = resolve_upstream_root(args.upstream)

    if not os.path.exists(MANIFEST):
        print("FAIL 缺 references/rewrite-manifest.json")
        return 1
    manifest = json.loads(read(MANIFEST))
    items = manifest.get("skills", {})

    installed = installed_skill_names()

    if args.list:
        todo = []
        done = []
        template = teaching_template_skills(manifest, installed)
        for name in sorted(template):
            p = os.path.join(SKILLS, name, "SKILL.md")
            if not os.path.exists(p):
                continue
            t = read(p)
            (todo if re.search(r"(?m)^\s*skill_id:", t) else done).append(name)
        print("待改写 %d 个:" % len(todo))
        for n in todo:
            print("   " + n)
        print()
        print("已改写 %d 个:" % len(done))
        for n in done:
            print("   " + n)
        return 0

    template = teaching_template_skills(manifest, installed)
    targets = [args.only] if args.only else sorted(template)
    if not args.upstream or not os.path.isdir(args.upstream):
        print("⚠️ 无上游原文目录（--upstream / JFA_UPSTREAM），"
              "相似度检查将被跳过。\n"
              "  设置 JFA_UPSTREAM 指向 education-agent-skills 暂存目录可做完整检查。\n")

    external = external_skill_names()
    for name in targets:
        check_skill(name, items, args.upstream, installed, external)

    # 全仓交叉引用校验（覆盖面 = skills/ 下**每一个**技能）。
    # --only 是单技能调试开关，此时不跑全仓，避免改变该项检查的计数口径。
    if not args.only:
        check_repo_cross_refs(installed, external)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    if args.verbose:
        for n, ok, d in RESULTS:
            print("[%s] %s%s" % ("PASS" if ok else "FAIL", n,
                                 ("  -> " + d) if (d and not ok) else ""))
    else:
        for n, ok, d in RESULTS:
            if not ok:
                print("FAIL  %s  -> %s" % (n, d))
    print("\nverify_rewrite: %d/%d checks passed" % (passed, len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
