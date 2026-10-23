#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""profile_map.py —— 分档出包技能集合的**唯一推导源**（纯标准库，Python 3.9 兼容）

分档（teaching / research / full）的技能集合**不是手工枚举**的，而是从能力矩阵
机械推导：

    包内技能 = 能力矩阵中该档案所辖能力域下的全部「● 已装」技能

🔴 **为什么必须机械推导**：手工枚举的清单会与矩阵漂移 —— 矩阵改了、清单没改，
出包器就会静默打出一个**与仓库宣称不符**的包，而且没有任何检查会红。
本仓库已经吃过一次「两套收集逻辑必然漂移」的亏（package_release 里 build 与
verify 曾经各写一份收集器），所以这里只允许一份实现。

两个数据源（都是**数据**不是代码，便于人工审阅与改动）：
    `references/faculty-capability-matrix.md` —— 能力格 ← 技能的归属
    `references/profiles.json`                   —— 能力域 ← 档案的归属

本模块被 `package_release.py`（出包）与 `verify_repo.py`（守卫）**共用**。

命令行：
    python scripts/profile_map.py            # 打印三档的推导结果
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATRIX_REL = "references/faculty-capability-matrix.md"
PROFILES_REL = "references/profiles.json"
REWRITE_MANIFEST_REL = "references/rewrite-manifest.json"
SKILLS_REL = "skills"

# ── 能力矩阵的标记约定（与 verify_repo 共用同一份） ──────────────────
MARK_INSTALLED, MARK_CANDIDATE, MARK_EXTERNAL = "●", "○", "◐"

# 技能标识 + 其前置标记（●已装 / ○候选未装 / ◐本机其他技能）
# 约定：每个技能名**必须**带标记，不允许"无标记 = 已装"这种隐式约定。
MARKED = re.compile(r"(●|○|◐)?\s*\**`?([a-z0-9][a-z0-9\-]{2,})")
IGNORE_WORDS = {"skills", "artifacts", "tool", "ai", "literacy", "etc",
                "项", "item", "items"}


def read_text(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────
# 能力矩阵解析
# ─────────────────────────────────────────────────────────────────
def parse_cell(cell):
    """返回 dict：i=已装(●) c=候选(○) e=外部(◐) u=未标记/悬空"""
    out = {"i": [], "c": [], "e": [], "u": []}
    # 括号内是注记（如 venue-templates(grant)、empirical-lint（功效/样本量/MDE）），
    # 不是技能名 —— 匹配前先剥掉，否则会把注记当成技能引用。
    stripped = re.sub(r"[（(][^）)]*[）)]", " ", cell)
    for m in MARKED.finditer(stripped):
        mark, name = m.group(1), m.group(2)
        if name in IGNORE_WORDS:
            continue
        if mark == MARK_INSTALLED:
            out["i"].append(name)
        elif mark == MARK_CANDIDATE:
            out["c"].append(name)
        elif mark == MARK_EXTERNAL:
            out["e"].append(name)
        else:
            out["u"].append(name)
    return out


def matrix_rows(text=None):
    """读能力矩阵，返回 [(格号, 覆盖技能单元格, 状态单元格)]。"""
    if text is None:
        text = read_text(MATRIX_REL)
    rows = []
    for line in text.splitlines():
        m = re.match(r"^\|\s*([A-F]\d+)\b[^|]*\|([^|]*)\|([^|]*)\|([^|]*)\|", line)
        if m:
            rows.append((m.group(1), m.group(3).strip(), m.group(4).strip()))
    return rows


def matrix_installed_skills(text=None):
    """矩阵里全部「● 已装」技能。"""
    out = set()
    for _cid, cell, _status in matrix_rows(text):
        out |= set(parse_cell(cell)["i"])
    return out


def matrix_domains(text=None):
    """矩阵覆盖到的能力域前缀集合。"""
    return set(cid[0] for cid, _c, _s in matrix_rows(text))


# ─────────────────────────────────────────────────────────────────
# 档案数据
# ─────────────────────────────────────────────────────────────────
def load_profiles():
    p = os.path.join(ROOT, PROFILES_REL)
    if not os.path.isfile(p):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def profile_names(prof=None):
    prof = prof if prof is not None else load_profiles()
    return sorted((prof.get("profiles") or {}).keys())


def full_only_skills(prof=None):
    prof = prof if prof is not None else load_profiles()
    return set(prof.get("full_only_skills") or [])


def installed_skills():
    d = os.path.join(ROOT, SKILLS_REL)
    if not os.path.isdir(d):
        return set()
    return set(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x)))


def profile_skill_set(profile, text=None, prof=None):
    """某个档案应当包含的技能集合。

    · full     → 全部已装技能（含仓库机制类）
    · 其他档   → 该档案所辖能力域下，矩阵里标「● 已装」的全部技能
    """
    prof = prof if prof is not None else load_profiles()
    pmap = prof.get("profiles") or {}
    if profile not in pmap:
        raise KeyError("未知档案: %s（可选 %s）"
                       % (profile, ", ".join(sorted(pmap.keys()))))
    if profile == "full":
        return installed_skills()
    doms = set(pmap[profile].get("domains") or [])
    out = set()
    for cid, cell, _status in matrix_rows(text):
        if cid[0] in doms:
            out |= set(parse_cell(cell)["i"])
    return out


def profile_label(profile, prof=None):
    prof = prof if prof is not None else load_profiles()
    return ((prof.get("profiles") or {}).get(profile) or {}).get("label", profile)


def profile_domains(profile, prof=None):
    prof = prof if prof is not None else load_profiles()
    return list(((prof.get("profiles") or {}).get(profile) or {}).get("domains") or [])


# ─────────────────────────────────────────────────────────────────
# 许可副本：按**包内实际技能**决定要带哪几份
# ─────────────────────────────────────────────────────────────────
def rewrite_manifest_skills():
    p = os.path.join(ROOT, REWRITE_MANIFEST_REL)
    if not os.path.isfile(p):
        return set()
    with open(p, "r", encoding="utf-8") as f:
        return set(json.load(f).get("skills", {}).keys())


def required_license_copies(skills, fm_reader=None):
    """给定技能集合，算出这个包**必须**携带的许可副本文件名。

    `fm_reader(name)` → 该技能 SKILL.md 的 frontmatter 文本（缺技能返回 ""）。
    判据全部从**技能自己身上**派生，不写死技能名：

      ① frontmatter 提到 K-Dense        → MIT-K-Dense.txt
      ② frontmatter 声明 Apache-2.0      → Apache-2.0-<技能名>.txt
      ③ 该技能在改写清单里（教育侧上游改编）→ CC-BY-SA-4.0-education-agent-skills.txt
      ④ frontmatter 的 origin 提到 OpenMAIC → OpenMAIC-MIT.txt

    🔴 这套判据是**按包内实际内容**算的，不是按仓库整体 ——
       分档包里没有 Apache 技能，就不该带 Apache 副本；
       反之少了副本就是再分发义务没履行（Apache §4(a) / MIT 保留声明）。
    """
    if fm_reader is None:
        def fm_reader(name):
            return read_text(os.path.join(SKILLS_REL, name, "SKILL.md"))[:4000]
    rewritten = rewrite_manifest_skills()
    need = set()
    for name in sorted(skills):
        fm = fm_reader(name)
        if not fm:
            continue
        if "K-Dense" in fm:
            need.add("MIT-K-Dense.txt")
        m = re.search(r"(?m)^license:\s*([^\r\n]+?)\s*$", fm)
        if m and "apache" in m.group(1).lower():
            need.add("Apache-2.0-%s.txt" % name)
        if name in rewritten:
            need.add("CC-BY-SA-4.0-education-agent-skills.txt")
        if re.search(r"(?m)^\s*origin:.*OpenMAIC", fm):
            need.add("OpenMAIC-MIT.txt")
    return need


# ─────────────────────────────────────────────────────────────────
# 恒等式：分档推导必须自洽
# ─────────────────────────────────────────────────────────────────
def invariant_problems(prof=None, text=None):
    """返回一组「分档推导不自洽」的问题描述（空列表 = 自洽）。

    这几条是**守卫与出包器的共同前置**：任何一条不成立，
    出包器宁可中止也不打一个来路不明的包。
    """
    prof = prof if prof is not None else load_profiles()
    problems = []
    if not prof or not prof.get("profiles"):
        return ["%s 缺失或为空" % PROFILES_REL]

    inst = installed_skills()
    mx = matrix_installed_skills(text)
    fo = full_only_skills(prof)

    # ① 每个已装技能都要有归属：要么在矩阵里，要么是 full_only（仓库机制）
    extra = sorted(inst - mx - fo)
    missing = sorted(fo - inst)
    if extra or missing:
        problems.append(
            "未归类技能：矩阵外的 %s；full_only 里不存在的 %s"
            % (", ".join(extra) or "无", ", ".join(missing) or "无"))

    # ② 每个非 full 档案都必须有内容，且不得越界（不能含未装技能）
    for name in profile_names(prof):
        if name == "full":
            continue
        s = profile_skill_set(name, text, prof)
        if not s:
            problems.append("档案 %s 推导出的技能集为空" % name)
        stray = sorted(s - inst)
        if stray:
            problems.append("档案 %s 含未安装的技能：%s" % (name, ", ".join(stray)))

    # ③ 能力域必须被某个非 full 档案覆盖 —— 否则该域的技能在两个分档里都会消失
    covered = set()
    for name in profile_names(prof):
        if name == "full":
            continue
        covered |= set(profile_domains(name, prof))
    uncovered = sorted(matrix_domains(text) - covered)
    if uncovered:
        problems.append("能力域未被任何分档覆盖：%s" % ", ".join(uncovered))

    # ③.5 两个分档必须都存在 —— 少一个，恒等式就没法成立，
    #     出包器宁可中止也不打一个来路不明的包。
    for need in ("teaching", "research"):
        if need not in (prof.get("profiles") or {}):
            problems.append("档位 %s 未在 profiles.json 中定义" % need)

    # ④ 恒等式：teaching ∪ research == full − full_only
    names = set(profile_names(prof))
    if "teaching" in names and "research" in names:
        t = profile_skill_set("teaching", text, prof)
        r = profile_skill_set("research", text, prof)
        f = profile_skill_set("full", text, prof)
        if (t | r) != (f - fo):
            only_t = sorted((t | r) - (f - fo))
            only_f = sorted((f - fo) - (t | r))
            problems.append(
                "teaching ∪ research ≠ full − full_only_skills"
                "（多出 %s / 缺少 %s）"
                % (", ".join(only_t) or "无", ", ".join(only_f) or "无"))
    return problems


# ─────────────────────────────────────────────────────────────────
def main():
    prof = load_profiles()
    problems = invariant_problems(prof)
    inst = installed_skills()
    print("已装技能 %d 个；矩阵登记 %d 个" % (len(inst), len(matrix_installed_skills())))
    unmapped = sorted(inst - matrix_installed_skills())
    print("未归类（矩阵外）：%s" % (", ".join(unmapped) or "无"))
    print()
    for name in profile_names(prof):
        s = profile_skill_set(name, prof=prof)
        lic = required_license_copies(s)
        print("%-9s %-6s 技能 %3d 个；许可副本 %d 份：%s"
              % (name, profile_label(name, prof), len(s), len(lic),
                 ", ".join(sorted(lic)) or "无"))
    print()
    if problems:
        print("!! 分档推导不自洽：")
        for p in problems:
            print("   - " + p)
        return 2
    print("分档推导自洽")
    return 0


if __name__ == "__main__":
    sys.exit(main())
