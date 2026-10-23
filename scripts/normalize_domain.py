#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""normalize_domain.py —— 统一 50 个教学技能的 `metadata.domain` 取值（纯标准库）

为什么需要它：50 个技能是并行改写的，不同作者给同一教学域起了不同的中文名
（"教学评价" / "考核评价" / "学生支持" / "学生学习支持" …）。
取值不受控 = 这个字段等于没有 = 既没法按域检索，也没法写守卫检查它。

做法：把 domain 统一成**上游目录 → 规范中文名**的确定性映射。
判据来自 `references/rewrite-manifest.json` 里的 `domain` 字段（上游目录），
不靠人工维护第二张表 —— 两张表必然漂移。

    python scripts/normalize_domain.py --check     # 只报告差异
    python scripts/normalize_domain.py --apply     # 写回
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

# 上游目录 → 规范中文名（**唯一权威表**，守卫也用它）
DOMAIN_CN = {
    "ai-learning-science": "AI 与学习科学",
    "curriculum-alignment": "课程体系",
    "curriculum-assessment": "考核评价",
    "explicit-instruction": "显性教学",
    "inclusive-design": "通用学习设计",
    "literacy-critical-thinking": "批判性思维与学术素养",
    "memory-learning-science": "记忆与学习科学",
    "original-frameworks": "教学设计框架",
    "professional-learning": "教研与专业发展",
    "questioning-discussion": "提问与讨论",
    "self-regulated-learning": "自我调节学习",
    "student-learning": "学生学习支持",
}


def read(p):
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write(p, text):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    manifest = json.loads(read(MANIFEST)).get("skills", {})
    drift = []
    for name in sorted(manifest):
        up_dom = manifest[name].get("domain")
        want = DOMAIN_CN.get(up_dom)
        if not want:
            continue
        p = os.path.join(SKILLS, name, "SKILL.md")
        if not os.path.exists(p):
            continue
        t = read(p)
        m = re.search(r"(?m)^(\s*domain:\s*)(.+?)\s*$", t)
        if not m:
            drift.append((name, "(缺 domain)", want))
            continue
        cur = m.group(2).strip().strip('"')
        if cur == want:
            continue
        drift.append((name, cur, want))
        if args.apply:
            t = t[:m.start()] + m.group(1) + want + t[m.end():]
            write(p, t)

    if not drift:
        print("全部 %d 个技能的 metadata.domain 已是规范取值。" % len(manifest))
        return 0
    for name, cur, want in drift:
        print("%-48s %-16s -> %s" % (name, cur, want))
    print("\n%d 个技能取值不统一。" % len(drift))
    if args.check:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
