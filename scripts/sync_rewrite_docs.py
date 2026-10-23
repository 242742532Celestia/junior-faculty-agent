#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_rewrite_docs.py —— 按改写进度**机械重生成**文档里的技能清单（纯标准库）

为什么需要它：50 个教学技能从「上游改编版」变成「本项目原创版」之后，
它们在 LICENSE / NOTICE.md / THIRD-PARTY-NOTICES.md / README.md 里的归属
要跟着搬家（上游清单 → 自有清单），技能总数、来源计数、许可表述全都要变。
手工改一定会漏一处 —— 而漏掉的那一处就是"文档在撒谎"。

    python scripts/sync_rewrite_docs.py --check     # 只检查，不改
    python scripts/sync_rewrite_docs.py --apply     # 应用改动
    python scripts/sync_rewrite_docs.py --status    # 看进度

判据来自**磁盘实际**：SKILL.md 里还带 `skill_id:` 的 = 仍是上游改编版；
没有的 = 已独立改写为原创版。不依赖任何人工维护的状态字段。
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
NOTICES = os.path.join(ROOT, "THIRD-PARTY-NOTICES.md")
LICENSE = os.path.join(ROOT, "LICENSE")
NOTICE = os.path.join(ROOT, "NOTICE.md")
README = os.path.join(ROOT, "README.md")

EDU_SKILLS = 50
KDENSE_SKILLS = 20
NC_ARCHIVE = ["academic-paper", "academic-paper-reviewer", "deep-research"]


def own_base_skills():
    """本项目自有、但使用**自有格式**的技能清单（不走中文教学模板）。

    🔴 名单放在 `references/rewrite-manifest.json` 的 `own_base` 键里，
       与守卫 `verify_rewrite.py` 共用同一份来源 ——
       两处各写一份必然漂移，漂移后"哪些技能该走哪套模板"就说不清了。
    """
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            return list(json.load(f).get("own_base", []))
    except Exception:
        return []

# 🔴 OpenMAIC 衍生技能的名单**不在这里写死** ——
#    判据取自各技能自己的 `metadata.origin`（提到 OpenMAIC 即为衍生），
#    与守卫 `verify_repo.py::openmaic_derived_skills()` 同源。
#    两份名单必然漂移，漂移后归属说明就与实际不符了。
sys.path.insert(0, os.path.join(ROOT, "scripts"))
try:
    from verify_repo import openmaic_derived_skills
except Exception:                      # pragma: no cover —— 守卫不可用时退化为空
    def openmaic_derived_skills():
        return set()


def own_new_skills(done, derived):
    """本项目**新写**的原创技能。

    🔴 为什么需要这一组：`own_block` 原本只列三组 ——
       ① own_base（自有格式）② 改写清单里的 50 个 ③ OpenMAIC 衍生。
       但 2026-10-22 第 5 版新写的 `teaching-slide-designer` /
       `paper-to-talk-designer` **既不在改写清单，也不是 own_base，更不是 OpenMAIC 衍生** ——
       它们会被三组全部漏掉，于是从 LICENSE / NOTICE / NOTICES 的归属清单里消失。
       归属清单漏一个技能 = 那一项的许可状态在文档上是空白。

    判据 = 已装技能 **减去** 上面三组，再去掉 K-Dense 与 NC。
    🔴 判据只问「属于哪一组」，**不問「原创到什么程度」** ——
       所以不会因为某个技能改写得好或差而被踢出清单（那会变成循环判据）。
    """
    try:
        from verify_repo import installed_skills, classify
    except Exception:                  # pragma: no cover
        return []
    own_base = set(own_base_skills())
    out = []
    for n in sorted(installed_skills()):
        if n in own_base or n in set(done) or n in set(derived):
            continue
        if classify(n) != "own":
            continue
        out.append(n)
    return out


def read(p):
    with open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write(p, text):
    # 🔴 **拒绝写入非字符串**。曾经因为标记没找到，`replace_block` 返回 None，
    #    这里照单全收 → `f.write(None)` 抛异常，但文件已经以 "w" 模式打开，
    #    **整个文档被截成空文件**。一次失败的同步 = 丢一份归属声明。
    if not isinstance(text, str):
        raise TypeError("拒绝写入非字符串内容到 %s（拿到 %s）"
                        % (p, type(text).__name__))
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def is_still_upstream(name):
    p = os.path.join(SKILLS, name, "SKILL.md")
    if not os.path.exists(p):
        return False
    return bool(re.search(r"(?m)^\s*skill_id:", read(p)))


def split_state(manifest):
    todo, done = [], []
    for name in sorted(manifest.get("skills", {})):
        (todo if is_still_upstream(name) else done).append(name)
    return todo, done


def edu_block(todo, manifest):
    """上游改编版技能清单（按上游域分组）。"""
    by_dom = {}
    for n in todo:
        dom = manifest["skills"][n].get("domain", "")
        by_dom.setdefault(dom, []).append(n)
    lines = []
    for dom in sorted(by_dom):
        names = by_dom[dom]
        lines.append("%s/" % dom)
        col = 30
        for i, n in enumerate(names):
            prefix = "" if i == 0 else " " * col
            sep = "" if i == len(names) - 1 else ","
            lines.append("%s%s%s" % (prefix, n, sep))
    return "\n".join(lines)


def own_block(done):
    """自有原创清单（基础原创 + 已改写完成的教学技能 + OpenMAIC 衍生技能）。

    🔴 三组分开列，而不是混成一坨 —— 它们的**归属说明不同**：
      ① 本项目原创
      ② 本项目原创（由上游主题参考而来）
      ③ OpenMAIC（MIT / THU-MAIC）方法论内核适配
    混在一起时，"本项目自有原创部分"这个标题就在替第 ③ 组撒谎。
    注释行以 `#` 开头：解析器忽略它们，`check_own_lists` 也会跳过。
    """
    lines = [
        "agent.md", "README.md", "LICENSE", "NOTICE.md",
        "references/he-context-adapter.md",
        "references/faculty-capability-matrix.md",
        "references/rejected-skills.md",
        "references/upstream-candidates.json",
        "references/external-skills.json",
        "references/profiles.json",
        "references/skill-rewrite-spec.md",
        "references/rewrite-manifest.json",
        "references/third-party-provenance.md",
        "scripts/skill_scan.py",
        "scripts/profile_map.py",
        "scripts/verify_repo.py",
        "scripts/test_verify_repo.py",
        "scripts/verify_rewrite.py",
        "scripts/package_release.py",
        "scripts/sync_rewrite_docs.py",
        "scripts/normalize_domain.py",
        "demo/README.md",
        "demo/run_demo.py",
        "demo/selfcheck.py",
        "demo/llm.py",
        "demo/selftest.py",
        "demo/course_input.example.json",
        "demo/prompts/lesson_plan.md",
        "demo/prompts/exam_paper.md",
        "demo/prompts/slides.md",
        "demo/spec/lesson_plan.example.json",
        "demo/spec/exam_paper.example.json",
        "demo/spec/slides.example.json",
        "crons/quarterly-skill-scan.md",
    ]
    derived = sorted(openmaic_derived_skills() - set(done))
    if derived:
        lines.append("# ── 以下为 OpenMAIC（MIT / THU-MAIC）方法论内核适配，"
                     "署名见 THIRD-PARTY-NOTICES.md §3 ──")
    for n in own_base_skills():
        lines.append("skills/%s/" % n)
    for n in sorted(done):
        lines.append("skills/%s/" % n)
    for n in derived:
        lines.append("skills/%s/" % n)
    new_own = own_new_skills(done, derived)
    if new_own:
        lines.append("# ── 以下为本项目新写的原创技能（不进改写清单、"
                     "也不由 OpenMAIC 衍生）──")
    for n in new_own:
        lines.append("skills/%s/" % n)
    lines.append("reports/（巡检报告与验证产出）")
    return "\n".join(lines)


def replace_block(text, start_marker, end_marker, new_body):
    """把 start_marker 之后的代码块内容替换为 new_body。

    🔴 标记找不到时**必须报错，不能静默返回 None** ——
       章节标题一改（比如 §3 → §4），旧标记就失效了；
       静默失败会让写文件那一步把 None 写进去，把整份文档截空。
    """
    i = text.find(start_marker)
    if i < 0:
        raise RuntimeError("找不到标记 %r —— 文档的章节标题改了？"
                           "请同步更新本脚本里的标记字符串。" % start_marker)
    j = text.find("```", i)
    if j < 0:
        raise RuntimeError("标记 %r 之后没有代码块" % start_marker)
    k = text.find("```", j + 3)
    if k < 0:
        raise RuntimeError("标记 %r 之后的代码块没有闭合" % start_marker)
    return text[:j + 3] + "\n" + new_body + "\n" + text[k:]


def build(todo, done, manifest):
    """返回 {文件名: 新内容}；None 表示该文件本次无需改。"""
    out = {}
    all_done = not todo

    # ── THIRD-PARTY-NOTICES.md ──
    t = read(NOTICES)
    orig = t
    if all_done:
        # 上游内容已全部不包含：§1 换成"主题与命名参考，内容独立创作"
        # 🔴 模板里含字面量百分号（如 "长行重合 < 5%。"），
        #    用 % 格式化会把 "%。" 当成格式符直接抛 ValueError。
        #    这里用占位符替换，不走 % 格式化。
        #    数量也用占位符 —— 写死"50 个"的话，技能一增文档就开始撒谎。
        new_sec = """## 1. 教学技能（__N__ 个）：主题与命名参考自 education-agent-skills，**内容为独立创作**

- **参考来源**：https://github.com/GarethManning/education-agent-skills
- **原作者**：Copyright (c) 2026 Gareth Manning
- **上游许可**：Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)
- **许可全文副本**：`licenses/CC-BY-SA-4.0-education-agent-skills.txt`（仅供追溯其原始许可）

> ⚠️ **本仓库不包含该上游的任何文件内容。**
> 这 __N__ 个教学技能是本项目**独立创作**的 MIT 许可技能，撰写依据是公开发表的
> 教育研究文献（各技能 SKILL.md 的「方法论依据」段列明具体出处），
> 并通过了与上游原文的**机械相似度核验**
> （`scripts/verify_rewrite.py`：8-gram Jaccard < 0.10、长行重合 < 5 百分点）。
>
> 📌 **其中 7 个另有 OpenMAIC 的方法论内核适配**（2026-10-22 增补章节），
> 逐条对应关系与署名见 **§3**。这些章节同样以 MIT 授权并署名 THU-MAIC。
>
> **致谢**：技能的主题选择与命名参考了该上游的教学技能清单。
> 据此致谢并提供链接。若认为某一技能的命名或主题选择仍构成其表达，
> 欢迎提 issue —— 我们会在保留署名与链接的前提下调整。

**技能清单（__N__ 个）**：

```
__SKILL_LIST__
```
""".replace("__SKILL_LIST__", "\n".join(sorted(done))).replace("__N__", str(len(done)))
        # 替换 §1 整节：从 "## 1." 到 "## 2." 之前
        i = t.find("## 1. ")
        j = t.find("## 2. ")
        if i >= 0 and j > i:
            t = t[:i] + new_sec + "\n---\n\n" + t[j:]
    else:
        t = replace_block(t, "## 1. ", "```", edu_block(todo, manifest))
    # 自有清单
    t = replace_block(t, "## 4. 本项目自有原创部分", "```", own_block(done))
    if t != orig:
        out[NOTICES] = t

    # ── LICENSE ──
    t = read(LICENSE)
    orig = t
    t = replace_block(t, "## 自有原创部分的许可", "```", own_block(done))
    if t != orig:
        out[LICENSE] = t

    # ── NOTICE.md ──
    t = read(NOTICE)
    orig = t
    t = replace_block(t, "## 本项目自有原创部分", "```", own_block(done))
    if t != orig:
        out[NOTICE] = t

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    manifest = json.loads(read(MANIFEST))
    todo, done = split_state(manifest)
    total = len(todo) + len(done)

    print("改写进度: %d / %d 已原创化（剩余 %d 个仍为上游改编版）"
          % (len(done), total, len(todo)))
    if todo:
        print("  待改写: %s" % ", ".join(todo))
    if args.status:
        return 0

    changes = build(todo, done, manifest)
    if not changes:
        print("文档已是最新，无需改动。")
        return 0

    for path, content in changes.items():
        rel = os.path.relpath(path, ROOT)
        cur = read(path)
        if cur == content:
            continue
        if args.check:
            print("DRIFT  %s" % rel)
        else:
            write(path, content)
            print("UPDATED %s" % rel)
    if args.check and changes:
        print("\n检测到文档与改写状态不一致（--apply 可修复）。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
