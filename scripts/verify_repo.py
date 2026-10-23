#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_repo.py —— 文档 ↔ 现实一致性守卫（纯标准库）

检查本仓库的**文档声明**与**仓库实际**是否一致。文档里写错的数字、
过期的清单、不存在的文件名、空口号的覆盖声明，全部在此报出来。

    python scripts/verify_repo.py            # 跑全部检查
    python scripts/verify_repo.py --verbose  # 逐条打印细节

退出码：0 = 全部通过；1 = 有失败项。

可选环境变量：
    JFA_UPSTREAM  上游仓库暂存目录（存在时会额外回源核实候选技能与许可副本）
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "skills")
GLOBAL_SKILLS = os.path.join(
    os.path.dirname(os.path.dirname(ROOT)), "skills")  # ~/.minimax/skills
UPSTREAM = os.environ.get("JFA_UPSTREAM", "")

# 上游仓库在本机的暂存目录名可能与仓库全名不同
UPSTREAM_ALIAS = {
    "education-agent-skills": ["education-agent-skills"],
    "scientific-agent-skills": ["scientific-agent-skills"],
    "academic-research-skills": ["academic-research-skills", "ars2"],
}


def upstream_dirs(repo):
    """返回该上游仓库在本机暂存根下的**全部**候选目录。

    同一个上游可能同时存在「完整仓库」与「抽出的技能目录」两份，
    例如 academic-research-skills（完整仓库，无 SKILL.md）与 ars2（技能目录）。
    两者都要搜，否则会误报「候选技能在上游不存在」。
    """
    dirs = []
    for alias in UPSTREAM_ALIAS.get(repo, [repo]):
        p = os.path.join(UPSTREAM, alias)
        if os.path.isdir(p) and p not in dirs:
            dirs.append(p)
    return dirs


def upstream_dir(repo):
    """第一个存在的候选目录（用于取许可文件等单点资源）。"""
    dirs = upstream_dirs(repo)
    return dirs[0] if dirs else None

RESULTS = []  # (name, ok, detail)


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    return bool(ok)


def read(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def read_bytes(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return b""
    with open(p, "rb") as f:
        return f.read()


def installed_skills():
    if not os.path.isdir(SKILLS_DIR):
        return set()
    return set(d for d in os.listdir(SKILLS_DIR)
               if os.path.isdir(os.path.join(SKILLS_DIR, d)))


def frontmatter_of(skill):
    txt = read(os.path.join("skills", skill, "SKILL.md"))
    m = re.match(r"(?s)^---\r?\n(.*?)\n---", txt)
    return m.group(1) if m else ""


def rewrite_manifest():
    """50 个「上游改编 → 本项目原创」的改写清单。

    这是**判据的来源**，不是状态记录 —— 清单本身不变，
    每个技能当前是改编版还是原创版，由它 SKILL.md 里有没有 skill_id 现场判定。
    """
    p = os.path.join(ROOT, "references", "rewrite-manifest.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("skills", {})


def classify(skill):
    """按 frontmatter 特征判定技能来源。"""
    fm = frontmatter_of(skill)
    if re.search(r"(?m)^skill_id:", fm):
        return "edu"          # education-agent-skills, CC BY-SA 4.0
    if "K-Dense" in fm:
        return "kdense"       # scientific-agent-skills, MIT
    if re.search(r"(?m)^\s*status:\s*active", fm):
        return "nc"           # academic-research-skills, CC BY-NC 4.0（非商业，不应入仓）
    return "own"              # 本项目原创


# ─────────────────────────────────────────────────────────────
# OpenMAIC 衍生技能：方法论内核适配自 OpenMAIC（MIT / THU-MAIC）
#
# 🔴 **名单写在技能自己的 frontmatter 里**（`metadata.origin` 提到 OpenMAIC），
#    脚本里**不维护第二份名单** —— 两份名单必然漂移，漂移后归属检查就形同虚设。
#    判据来源 = 磁盘实际，与 `classify()` 同源。
# ─────────────────────────────────────────────────────────────
def openmaic_derived_skills():
    """返回声明了 OpenMAIC 衍生来源的技能集合。"""
    out = set()
    for s in installed_skills():
        fm = frontmatter_of(s)
        if re.search(r"(?m)^\s*origin:.*OpenMAIC", fm):
            out.add(s)
    return out


# 🔴 OpenMAIC 的 22 个运行时技能是**绑死运行时工具**的（正文写 create_stage /
#    generate_scene / patch_stage 等）。把那些 SKILL.md 整份复制进来，会在本仓库
#    里留下**悬空引用** —— 本仓库没有 OpenMAIC 运行时，这些调用谁也执行不了。
#    P0 只抽方法论内核重写，所以这批工具名一个都不许出现。
OPENMAIC_RUNTIME_TOOLS = (
    "create_stage", "generate_scene", "generate_actions", "generate_tts",
    "patch_stage", "read_stage", "grep_stage", "list_scenes", "set_roster",
    "set_role", "set_speech", "set_spotlight", "import_pptx",
    "render_scene_preview", "edit_deck", "create_folder", "create_skill",
    "set_project", "set_microtask", "set_milestone", "set_config",
    "read_chat", "read_classroom", "read_stage_outline", "list_voices",
    "list_materials", "read_material", "list_folder_stages",
    "move_to_folder", "ask_user",
)


# 非商业（CC BY-NC）技能名单：这些技能**不允许**出现在 skills/ 与任何分发物里。
NC_SKILLS = {"academic-paper", "academic-paper-reviewer", "deep-research",
             "sr-screener"}

# 同姓不同人：这些姓氏在教育/心理测量文献里对应**多个不同作者**，
# 跨技能比对"同姓不同首字母"时属于正常，不算错。
# 每一条都经过人工核实，不是为了让检查变绿而塞进去的：
#   Schwartz —— S. A.（Spady 1997）、M. S.（1998）、D. L.（Bransford 1999/2000）
#   Sfard    —— A.（Avigdor, 2008）、D.（Daphne, 2004）
#   Bjork    —— E. L.（Elizabeth）、R. A.（Robert）
#   Johnson  —— D. W. & R. T.（1994 合作学习）、J.（Mayer & Johnson 1991）
#   Cooper   —— R.（Cooper & Weld 2007）、P. A.（Sweller & Cooper 1985）
#   Butler   —— D. L.（Butler & Winstone 1995）、A. C.（2010 重复测试迁移）
#   Lewis    —— C.（Catherine, 2006 课例研究）、M. L.（Chi et al. 1989）
#   Broadbent—— H.（Berry & Broadbent 1984）、J.（Broadbent & Poon 2015）
#   Martin   —— N. J.（Martin & Lange, 2015, Nature「优化学习空间」）、
#               R. C.（Martin, 2009,《The Design of Everything Thing》）
SAME_SURNAME_MULTI_AUTHOR = {
    "Schwartz", "Sfard", "Bjork", "Johnson",
    "Cooper", "Butler", "Lewis", "Broadbent", "Martin",
}


# ─────────────────────────────────────────────────────────────
# 1. 技能总量与分源归属
# ─────────────────────────────────────────────────────────────
def check_skill_counts():
    skills = installed_skills()
    total = len(skills)
    check("技能总数 = 86", total == 86, "实际 %d" % total)

    buckets = {"edu": [], "kdense": [], "nc": [], "own": []}
    for s in sorted(skills):
        buckets[classify(s)].append(s)

    # 🔴 期望值不能写死 —— 50 个教学技能正在从「上游改编」迁移为「本项目原创」，
    # 归属桶的构成会随改写进度变化。写死数字 = 写死一个必然失效的断言。
    # 正确做法：期望值从**改写清单**推导 —— 清单 50 个全部原创化后，
    # 「上游改编」桶必然为空，「自有」桶必然等于总数减 K-Dense 数。
    manifest = rewrite_manifest()
    check("改写清单存在且含 50 个技能", len(manifest) == 50,
          "实际 %d" % len(manifest))

    still_upstream = sorted(
        n for n in manifest
        if re.search(r"(?m)^\s*skill_id:", frontmatter_of(n)))
    check("改写清单 50 个技能全部已原创化（无上游 skill_id）",
          not still_upstream,
          "仍有 %d 个未改写：%s" % (len(still_upstream),
                                    ", ".join(still_upstream[:8])))

    # metadata.domain 取值必须受控 —— 同一批技能并行改写时最容易出现
    # "教学评价 / 考核评价 / 学生支持 / 学生学习支持" 这类同义分裂。
    # 取值不受控 = 这个字段没法按域检索，也没法校验。
    # 规范表只有一份（normalize_domain.py），守卫与规范化脚本共用它。
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        from normalize_domain import DOMAIN_CN
    except Exception:
        DOMAIN_CN = {}
    dom_bad = []
    for n in sorted(manifest):
        want = DOMAIN_CN.get(manifest[n].get("domain"))
        if not want:
            continue
        m = re.search(r"(?m)^\s*domain:\s*(.+?)\s*$", frontmatter_of(n))
        got = m.group(1).strip().strip('"') if m else "(缺)"
        if got != want:
            dom_bad.append("%s: %s（应 %s）" % (n, got, want))
    check("50 个技能 metadata.domain 取值受控", bool(DOMAIN_CN) and not dom_bad,
          "; ".join(dom_bad[:6]) if DOMAIN_CN else "规范表缺失")

    # 🔴 超集判据：**任何**声明了 metadata.domain 的技能，取值都必须在受控词表内。
    #    上面那条是「清单内的技能必须等于清单指定的域」；这条是「全仓带 domain
    #    字段的技能都不得出现词表外的值」——
    #    新写的技能不在改写清单里，只能靠这条兜住，否则词表会悄悄失守。
    allowed_domains = set(DOMAIN_CN.values())
    uncontrolled = []
    for n in sorted(skills):
        m = re.search(r"(?m)^\s*domain:\s*(.+?)\s*$", frontmatter_of(n))
        if not m:
            continue
        got = m.group(1).strip().strip('"').strip("'")
        if got not in allowed_domains:
            uncontrolled.append("%s: %s" % (n, got))
    check("全仓 metadata.domain 取值都在受控词表内", not uncontrolled,
          ", ".join(uncontrolled[:6]))

    kdense_n = sum(1 for s in skills if classify(s) == "kdense")
    expect = {"edu": 0, "kdense": kdense_n, "nc": 0, "own": total - kdense_n}
    for k, n in expect.items():
        check("分源归属 %s = %d" % (k, n), len(buckets[k]) == n,
              "实际 %d：%s" % (len(buckets[k]),
                              ", ".join(buckets[k]) if len(buckets[k]) != n else ""))

    # 🔴 商业可用性的底线：skills/ 里绝不能有 NonCommercial 内容
    nc_in_skills = sorted(NC_SKILLS & skills)
    check("skills/ 不含任何 NonCommercial 技能", not nc_in_skills,
          ", ".join(nc_in_skills))

    # 也不能混进"长得像 NC 家族"的其他技能（按 frontmatter 特征兜底）
    check("skills/ 无 CC BY-NC 家族技能（frontmatter 特征）",
          not buckets["nc"], ", ".join(buckets["nc"]))

    # 每个技能必须有 SKILL.md 且 frontmatter 含 name + description
    bad = []
    for s in sorted(skills):
        fm = frontmatter_of(s)
        if not fm:
            bad.append(s + "(无 frontmatter)")
        elif not re.search(r"(?m)^name:\s*\S", fm):
            bad.append(s + "(缺 name)")
        elif not re.search(r"(?m)^description:", fm):
            bad.append(s + "(缺 description)")
    check("全部技能 frontmatter 有效", not bad, "; ".join(bad[:6]))
    return buckets


# ─────────────────────────────────────────────────────────────
# 2. THIRD-PARTY-NOTICES 清单 ↔ 磁盘（**结构无关**的集合比对）
# ─────────────────────────────────────────────────────────────
# 🔴 为什么必须结构无关：清单块可能写成「domain/  name, name」分域格式，
# 也可能写成「一行一个名字」的纯名单格式（改写完成后就是后者）。
# 硬编码其中一种的解析逻辑 = 文档一改结构，守卫立刻误报或漏报。
# 这里按**每行自身的形状**判断，不看它在第几个块、第几行。
SKILL_TOKEN = re.compile(r"^[a-z0-9][a-z0-9\-]{2,}$")
SKILL_LINE = re.compile(r"^[a-z0-9][a-z0-9\-]*(?:\s*,\s*[a-z0-9][a-z0-9\-]*)*$")
DOMAIN_LINE = re.compile(r"^([a-z0-9][a-z0-9\-]*)/\s+(.+)$")


def parse_notices_blocks(text):
    """从 NOTICES 的代码块里抽出「技能名 -> 上游域」。

    返回 dict：键为技能名，值为该技能被标注的上游域（None = 未标域）。
    三种行形状：
      1. `skills/<name>/`            —— 显式路径（自有清单用）
      2. `domain/  name[, name...]` —— 分域行（上游改编版清单用）
      3. `name[, name...]`          —— 纯名单行（原创技能清单用）
    """
    mentioned = {}
    for blk in re.findall(r"```\n(.*?)```", text, re.S):
        for line in blk.splitlines():
            l = line.strip()
            if not l:
                continue
            # 形式一：显式路径
            for m in re.finditer(r"skills/([a-z0-9][a-z0-9\-]*)/?", l):
                mentioned.setdefault(m.group(1), None)
            # 形式二：分域行
            m = DOMAIN_LINE.match(l)
            if m:
                dom, rest = m.group(1), m.group(2)
                for t in rest.split(","):
                    t = t.strip()
                    if SKILL_TOKEN.match(t):
                        mentioned.setdefault(t, dom)
                continue
            # 形式三：纯名单行（容忍行尾逗号）
            l2 = l.rstrip(",").strip()
            if SKILL_LINE.match(l2):
                for t in l2.split(","):
                    t = t.strip()
                    if SKILL_TOKEN.match(t):
                        mentioned.setdefault(t, None)
    return mentioned


def check_notices(buckets):
    text = read("THIRD-PARTY-NOTICES.md")
    if not text:
        check("THIRD-PARTY-NOTICES.md 存在", False, "文件缺失")
        return

    mentioned = parse_notices_blocks(text)
    installed = installed_skills()

    check("NOTICES 含技能清单代码块", len(mentioned) >= 3,
          "只解析到 %d 个技能名" % len(mentioned))

    # 方向 A：NOTICES 必须覆盖全部已装技能（漏一个 = 归属没交代）
    missing = sorted(installed - set(mentioned))
    check("NOTICES 覆盖全部已装技能（%d）" % len(installed), not missing,
          "漏 %d 个：%s" % (len(missing), ", ".join(missing[:8])))

    # 方向 B：NOTICES 提到的技能必须真实存在（漏改 = 过期名字还挂着）
    # 只看**带连字符**的 token：仓库里 66 个技能名无一例外都含连字符，
    # 而普通单词（license、tool 这类）会在其他上下文里被误当成技能。
    dangling = sorted(n for n in set(mentioned) - installed if "-" in n)
    check("NOTICES 未提及不存在的技能（无过期/悬空名）", not dangling,
          ", ".join(dangling[:8]))

    check("NOTICES 声明数 = 已装技能数", len(mentioned) == len(installed),
          "声明 %d / 磁盘 %d" % (len(mentioned), len(installed)))

    # 🔴 商业可用性底线：NOTICES 的技能清单里不得出现 NC 技能
    nc_in_notices = sorted(NC_SKILLS & set(mentioned))
    check("NOTICES 清单不含 NonCommercial 技能", not nc_in_notices,
          ", ".join(nc_in_notices))

    # 域前缀 ↔ skill_id 域（只对**仍为上游改编版**的技能有效）
    mismatch = []
    for name, domain in mentioned.items():
        if domain is None:
            continue
        fm = frontmatter_of(name)
        m = re.search(r'(?m)^skill_id:\s*"?([^"\r\n]+?)"?\s*$', fm)
        if not m:
            continue          # 已改写为原创，不再声称上游归属
        actual = m.group(1).strip().split("/")[0]
        if actual != domain:
            mismatch.append("%s: NOTICES 域 %s ≠ skill_id 域 %s"
                            % (name, domain, actual))
    check("NOTICES 域 ↔ skill_id 域逐条一致（仅对仍为上游改编版的技能）",
          not mismatch, "; ".join(mismatch[:5]))

    # 已原创化的技能不得再被归入上游域分组 —— 否则归属表就在撒谎
    manifest = rewrite_manifest()
    done = {n for n in manifest
            if not re.search(r"(?m)^\s*skill_id:", frontmatter_of(n))}
    still_grouped = sorted(done & {n for n, d in mentioned.items() if d})
    check("已原创化的技能不再出现在上游域分组里",
          not still_grouped, ", ".join(still_grouped[:8]))

    # 自有技能（5 个基础原创）不得被标成上游域
    base_own = set(buckets["own"]) - set(manifest)
    wrongly = sorted(n for n in base_own if mentioned.get(n))
    check("自有基础技能未被标上游域", not wrongly, ", ".join(wrongly))

    # 许可副本：**结构无关**的校验 —— licenses/ 里每一份都必须被 NOTICES 引用，
    # 且不得含 NC 家族许可全文。
    # 🔴 之前这里是硬编码白名单（只允许两份），加一份 Apache-2.0 就会误报。
    #    硬编码白名单 = 把"文档结构"写进判据，文档一改结构就失真。
    #    正确做法是**关系判据**：副本 ↔ 归属声明，双向都要闭合。
    lic_dir = os.path.join(ROOT, "licenses")
    have_lic = set(os.listdir(lic_dir)) if os.path.isdir(lic_dir) else set()
    referenced = set(re.findall(r"licenses/([A-Za-z0-9._-]+\.txt)", text))
    orphan = sorted(have_lic - referenced)
    check("licenses/ 每份副本都被 NOTICES 引用（无孤儿副本）", not orphan,
          ", ".join(orphan))
    missing_copy = sorted(referenced - have_lic)
    check("NOTICES 提到的许可副本都存在", not missing_copy,
          ", ".join(missing_copy))
    nc_lic = sorted(f for f in have_lic if re.search(r"NC|NonCommercial", f, re.I))
    check("licenses/ 不含 NC 家族许可全文", not nc_lic, ", ".join(nc_lic))

    # 作者署名拼写
    all_docs = text + read("LICENSE") + read("NOTICE.md") + read("README.md")
    check("作者署名 'Gareth Manning' 拼写正确",
          "Gartner Manning" not in all_docs and "Gareth Manning" in all_docs,
          "发现 'Gartner Manning' 误拼" if "Gartner Manning" in all_docs else "")


# ─────────────────────────────────────────────────────────────
# 2b. 许可台账完整性 —— 商用分发的前置条件
# ─────────────────────────────────────────────────────────────
# 🔴 为什么要单独一组检查：本项目对外声明"整体可商用"，那么**每一个**
# 已装技能的许可都必须**说得清**。说不清 = 商用时是风险，不是"先这样"。
#
# 本仓库曾经藏着一个真实的缺口：`markdown-mermaid-writing` 的 frontmatter
# 声明的是 **Apache-2.0**（署名 Superior Byte Works, LLC），
# 而 `licenses/` 里只有一份 MIT 副本、README 却写着"全仓 MIT"——
# 两处都是错的，守卫当时**一条都没报**。
#
# 现在四件事必须机械成立：
#   ① 每个已装技能的 frontmatter 都声明 license（缺声明 = 许可不明）
#   ② 声明 Apache-2.0 的技能，licenses/ 里有对应副本
#      （Apache-2.0 §4(a)：再分发时必须向接收方提供许可副本）
#   ③ licenses/ 里没有 NC 家族许可全文（NC 会传染整个分发物）
#   ④ README 的许可表述与实际一致 —— 存在非 MIT 技能时不得声称"全仓 MIT"
LICENSE_ID_RE = re.compile(r"(?m)^license:\s*([^\r\n]+?)\s*$")


def skill_license(skill):
    """返回该技能 frontmatter 声明的许可标识（归一化后）；没声明返回 ""。"""
    m = LICENSE_ID_RE.search(frontmatter_of(skill))
    if not m:
        return ""
    v = m.group(1).strip().strip('"').strip("'")
    low = v.lower()
    if "apache" in low:
        return "Apache-2.0"
    if low.startswith("mit"):
        return "MIT"
    if re.search(r"noncommercial|\bcc.?by.?nc\b", low):
        return "NC"
    if re.search(r"sharealike|\bcc.?by.?sa\b", low):
        return "SA"
    return v


def check_license_completeness():
    skills = sorted(installed_skills())

    # ① 每个技能都声明许可
    no_lic = [s for s in skills if not skill_license(s)]
    check("每个已装技能都声明 license（许可不明 = 商用风险）", not no_lic,
          "%d 个未声明：%s" % (len(no_lic), ", ".join(no_lic[:8])))

    # ② Apache-2.0 技能必须有许可副本
    lic_dir = os.path.join(ROOT, "licenses")
    have_lic = set(os.listdir(lic_dir)) if os.path.isdir(lic_dir) else set()
    apache_skills = [s for s in skills if skill_license(s) == "Apache-2.0"]
    apache_copies = sorted(f for f in have_lic if f.lower().startswith("apache"))
    check("Apache-2.0 技能有对应的许可副本（Apache §4(a)）",
          not apache_skills or bool(apache_copies),
          "技能 %s 无 Apache 副本" % ", ".join(apache_skills) if apache_skills
          and not apache_copies else "")

    # 副本本身要含许可标识（防止放个空文件或别的许可冒充）
    bad_copy = []
    for f in apache_copies:
        p = os.path.join(lic_dir, f)
        t = read_bytes(p).decode("utf-8", "replace")
        if "Apache License" not in t or "Version 2.0" not in t:
            bad_copy.append(f)
        elif os.path.getsize(p) < 5000:
            bad_copy.append(f + "(过小)")
    check("Apache-2.0 副本内容完整（含许可标识与正文）", not bad_copy,
          ", ".join(bad_copy))

    # ③ NC / SA 家族不得出现在已装技能里（SA 是传染性许可，见 S10）
    nc_or_sa = [s for s in skills if skill_license(s) in ("NC", "SA")]
    check("已装技能无 NC / SA 家族许可", not nc_or_sa, ", ".join(nc_or_sa))

    # ④ README 的许可表述 ↔ 实际
    # 🔴 判据必须是**肯定句式**，不能是裸短语：
    #    "本仓库全部内容为 MIT" 是撒谎；
    #    "不是『全仓 MIT』：其中 1 个是 Apache-2.0" 是如实交代；
    #    "README 不得谎称『全仓 MIT』" 是**在描述这条检查本身**。
    #    后两种都会包含裸短语 —— 用裸短语做判据，检查会逼着文档绕开自己的表述，
    #    反而更容易写出真话。所以只认**肯定句式**，并再叠一层否定窗口兜底。
    readme = read("README.md")
    non_mit = [s for s in skills if skill_license(s) not in ("MIT", "")]
    CLAIMS = ("本仓库全部内容为 MIT", "本仓库全部为 MIT", "全部内容为 MIT 许可",
              "全仓都是 MIT", "全仓均为 MIT", "全仓统一为 MIT",
              "整个仓库都是 MIT", "所有内容均为 MIT", "全部技能均为 MIT")
    NEGATORS = ("不", "非", "否", "没")
    over_claim = []
    for line in readme.splitlines():
        for claim in CLAIMS:
            idx = line.find(claim)
            if idx < 0:
                continue
            before = line[max(0, idx - 12):idx]
            if any(n in before for n in NEGATORS):
                continue          # 否定语境
            over_claim.append(claim)
    check("README 许可表述 ↔ 实际（存在非 MIT 技能时不得称『全仓 MIT』）",
          not over_claim or not non_mit,
          ("README 声称 %s，但实际有非 MIT 技能：%s"
           % ("/".join(sorted(set(over_claim))), ", ".join(non_mit)))
          if over_claim and non_mit else "")


# ─────────────────────────────────────────────────────────────
# 2c. OpenMAIC 衍生技能的归属与许可台账
#
# 🔴 为什么要单独一组：OpenMAIC 是 MIT（Copyright (c) 2026 THU-MAIC），
#    允许闭源商用分发，**唯一义务是保留版权声明与许可声明**。
#    但 MIT 的义务是"随本作品的实质性部分一并提供"——
#    我们抽了它的方法论内核重写，就必须把它的版权声明与许可声明一起带上，
#    否则这份分发物在许可上是失实的。
#
#    同时要挡住一个具体的失败模式：把 OpenMAIC 那 22 个运行时技能的 SKILL.md
#    整份复制进来（正文绑死 create_stage / generate_scene 等运行时工具）。
#    本仓库没有 OpenMAIC 运行时 ⇒ 那些调用全是悬空引用。
# ─────────────────────────────────────────────────────────────
OPENMAIC_LICENSE_COPY = "OpenMAIC-MIT.txt"


def check_openmaic_attribution():
    derived = sorted(openmaic_derived_skills())
    check("OpenMAIC 衍生技能已登记（≥1 个）", bool(derived),
          "未发现 metadata.origin 提到 OpenMAIC 的技能")

    # ① 衍生技能必须自标 MIT（MIT 衍生允许以 MIT 继续授权）
    bad_lic = [s for s in derived if skill_license(s) != "MIT"]
    check("OpenMAIC 衍生技能均以 MIT 授权（MIT 可再授权）", not bad_lic,
          ", ".join(bad_lic))

    # ② 许可副本必须在场，且含真实署名
    lic_dir = os.path.join(ROOT, "licenses")
    copy_path = os.path.join(lic_dir, OPENMAIC_LICENSE_COPY)
    check("licenses/ 含 OpenMAIC 的 MIT 许可副本", os.path.exists(copy_path),
          "缺 %s" % OPENMAIC_LICENSE_COPY)
    if os.path.exists(copy_path):
        t = read_bytes("licenses/" + OPENMAIC_LICENSE_COPY).decode("utf-8", "replace")
        check("OpenMAIC 许可副本含 MIT 标识与 THU-MAIC 署名",
              "MIT License" in t and "THU-MAIC" in t,
              "副本内容与预期不符")

    # ③ 三方声明必须各自交代这份归属
    notices = read("THIRD-PARTY-NOTICES.md")
    check("THIRD-PARTY-NOTICES.md 交代 OpenMAIC 归属（含 THU-MAIC 署名）",
          "OpenMAIC" in notices and "THU-MAIC" in notices,
          "NOTICES 未提到 OpenMAIC / THU-MAIC")
    check("THIRD-PARTY-NOTICES.md 引用 OpenMAIC 许可副本路径",
          ("licenses/" + OPENMAIC_LICENSE_COPY) in notices,
          "NOTICES 未引用 licenses/%s" % OPENMAIC_LICENSE_COPY)
    check("NOTICE.md 交代 OpenMAIC 归属",
          "OpenMAIC" in read("NOTICE.md"), "NOTICE.md 未提到 OpenMAIC")

    # ④ 衍生技能不得声称「上游改编版」（那会与「OpenMAIC 衍生」冲突，
    #    且等于把 education-agent-skills 的 skill_id 声明又挂回来了）
    with_sid = [s for s in derived
                if re.search(r"(?m)^\s*skill_id:", frontmatter_of(s))]
    check("OpenMAIC 衍生技能无上游 skill_id 溯源字段", not with_sid,
          ", ".join(sorted(with_sid)))

    # ⑤ 🔴 核心：正文不得出现 OpenMAIC 运行时工具名 —— 那是悬空引用
    dangling = []
    for s in derived:
        txt = read(os.path.join("skills", s, "SKILL.md"))
        for tool in OPENMAIC_RUNTIME_TOOLS:
            if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(tool), txt):
                dangling.append("%s → %s" % (s, tool))
    check("OpenMAIC 衍生技能无运行时工具悬空引用", not dangling,
          ", ".join(sorted(set(dangling))[:6]))

    # ⑥ 副本与上游字节一致（上游可定位时核；否则跳过并注明）
    up = os.environ.get("JFA_OPENMAIC", "")
    if up and os.path.exists(copy_path):
        src = os.path.join(up, "LICENSE")
        if os.path.exists(src):
            with open(src, "rb") as f:
                a = f.read()
            same = a == read_bytes("licenses/" + OPENMAIC_LICENSE_COPY)
            check("OpenMAIC 许可副本与上游字节一致", same,
                  "与上游 LICENSE 不一致")
        else:
            check("OpenMAIC 许可副本与上游字节一致", True, "跳过（上游无 LICENSE）")
    else:
        check("OpenMAIC 许可副本与上游字节一致", True,
              "跳过（未设 JFA_OPENMAIC）")


# ─────────────────────────────────────────────────────────────
# 3. 能力矩阵：每格必须真有已装技能接住
#
# 🔴 矩阵解析的**唯一实现**在 `scripts/profile_map.py`（出包器与守卫共用）。
#    两份解析实现必然漂移，漂移是静默的 —— 守卫和出包器会各信各的。
# ─────────────────────────────────────────────────────────────
if os.path.isdir(os.path.join(ROOT, "scripts")):
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
try:
    from profile_map import parse_cell, matrix_rows
    PROFILE_MAP_OK = True
    PROFILE_MAP_ERR = ""
except Exception as _e:  # pragma: no cover
    PROFILE_MAP_OK = False
    PROFILE_MAP_ERR = str(_e)

    def parse_cell(cell):
        return {"i": [], "c": [], "e": [], "u": []}

    def matrix_rows():
        return []


def external_skills():
    """读外部技能登记表（references/external-skills.json）→ {名字: 登记项}。"""
    p = os.path.join(ROOT, "references", "external-skills.json")
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("skills", {})
    except Exception:
        return {}


def check_matrix():
    text = read("references/faculty-capability-matrix.md")
    if not text:
        check("能力矩阵存在", False, "文件缺失")
        return
    skills = installed_skills()
    manifest_path = os.path.join(ROOT, "references", "upstream-candidates.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            manifest = {k: v for k, v in json.load(f).items()
                        if not k.startswith("_")}

    rows = matrix_rows()
    check("能力矩阵 41 格", len(rows) == 41, "实际 %d 格" % len(rows))

    empty = []
    for cid, cell, status in rows:
        p = parse_cell(cell)
        s = status.replace("*", "").strip()
        if "缺口" in s:
            continue
        if "部分覆盖" in s:
            # 「部分覆盖」允许**只有外部技能（◐）**：本机由 ADW 论文智能体等
            # 全局技能承担、仓库本身不含 —— 这是三态模型的应有之义
            # （克隆后该格退化为缺口，矩阵已如实标注）。
            # 但一个技能都不列 = 在编，必须报错。
            if not p["i"] and not p["e"]:
                empty.append("%s 标为「%s」但既无 ● 已装技能也无 ◐ 外部技能" % (cid, s))
        elif not p["i"]:
            # 「已覆盖」= 随本仓库分发、克隆即可用 ⇒ 必须有 ●
            empty.append("%s 标为「%s」但无 ● 已装技能" % (cid, s))
    check("「已覆盖」的格有 ● 已装技能；「部分覆盖」的格有 ● 或 ◐", not empty,
          "; ".join(empty))

    # ● 标记的技能必须真的装了（标记过期是最隐蔽的一种撒谎）
    bad_dot = []
    for cid, cell, status in rows:
        for nm in parse_cell(cell)["i"]:
            if nm not in skills:
                bad_dot.append("%s -> ●%s（未安装）" % (cid, nm))
    check("● 标记的技能确实已安装", not bad_dot, "; ".join(bad_dot))

    # ○ 候选必须同时在 upstream-candidates.json 里登记
    cand_in_matrix = set()
    for cid, cell, status in rows:
        cand_in_matrix |= set(parse_cell(cell)["c"])
    unregistered = sorted(cand_in_matrix - set(manifest))
    check("矩阵里的 ○ 候选都在 upstream-candidates.json 登记",
          not unregistered, ", ".join(unregistered))

    stale = sorted(set(manifest) - cand_in_matrix)
    check("upstream-candidates.json 无失效条目", not stale,
          ", ".join(stale))

    # ○ 候选确实没装
    wrongly = [c for c in cand_in_matrix if c in skills]
    check("○ 候选确实未安装（标记没过期）", not wrongly, ", ".join(wrongly))

    # ◐ 外部技能不应该出现在本仓库里（那就该标 ●）
    wrong_ext = []
    for cid, cell, status in rows:
        for nm in parse_cell(cell)["e"]:
            if nm in skills:
                wrong_ext.append("%s -> ◐%s（本仓库已装，应标 ●）" % (cid, nm))
    check("◐ 标记的技能确实不在本仓库", not wrong_ext, "; ".join(wrong_ext))

    # 未标记的技能名：要么是悬空引用，要么是漏加标记
    dangling = []
    for cid, cell, status in rows:
        for nm in parse_cell(cell)["u"]:
            dangling.append("%s -> %s" % (cid, nm))
    check("矩阵里每个技能名都带标记（无悬空引用）", not dangling,
          "; ".join(dangling[:6]))

    # 统计，与 README 比对
    counts = {}
    for cid, cell, status in rows:
        s = status.replace("*", "").strip()
        dom = cid[0]
        c = counts.setdefault(dom, {"已覆盖": 0, "部分覆盖": 0, "缺口": 0})
        if "缺口" in s:
            c["缺口"] += 1
        elif "部分覆盖" in s:
            c["部分覆盖"] += 1
        elif "已覆盖" in s:
            c["已覆盖"] += 1
    return counts


def check_external_skills():
    """◐ 外部技能必须登记在 `references/external-skills.json`。

    🔴 为什么要有这张登记表：`◐` 原本是**自由文本** —— 谁想写个名字当"外部技能"
    就能写，矩阵里就会多出一个查无实据的依赖。
    把它收成受控词表（同 `metadata.domain` 的思路），才能机械校验：
      ① 矩阵里每个 ◐ 都必须在册（不能编）
      ② 在册的都不能已经装进 skills/（装了就该标 ●）
    """
    reg = external_skills()
    marked_ext = set()
    for cid, cell, status in matrix_rows():
        marked_ext |= set(parse_cell(cell)["e"])

    unregistered = sorted(marked_ext - set(reg))
    check("矩阵 ◐ 标记的技能都在 external-skills.json 登记", not unregistered,
          ", ".join(unregistered))

    shadowed = sorted(set(reg) & set(installed_skills()))
    check("external-skills.json 登记的技能都不在 skills/ 里", not shadowed,
          ", ".join(shadowed))


# ─────────────────────────────────────────────────────────────
# 幻灯片能力自足性
#
# 🔴 为什么单独设一条：2026-10-22 之前，「做 PPT」这件事挂在本机运行时内置的
#    `pptx` 技能上，还有 `nature-paper2ppt` 负责「论文转 PPT」。两者**都不随本仓库
#    分发** ⇒ 克隆本仓库后，「做个组会汇报」这类需求无人接手。
#    这正是论文线（ADW）踩过的同一个坑。
#
#    本仓库自研了纯标准库的 PPTX 生成器与幻灯片规范审查器，所以这条守卫要保证：
#      ① 生成器与审查器**在仓库里**（不是"计划做"）；
#      ② 外部技能表里**不再登记** PPTX 生成类外部技能；
#      ③ 能力矩阵的幻灯片相关格**不再依赖**外部技能；
#      ④ 两个脚本的 --selftest **真的跑得过** —— 这一条最硬：它证明的是
#         「克隆下来就能用」，而不只是「文件在」。
# ─────────────────────────────────────────────────────────────
SLIDE_PPTX_MAKER = "skills/teaching-slide-designer/scripts/build_pptx.py"
SLIDE_SPEC_LINT = "skills/teaching-slide-designer/scripts/slide_spec_lint.py"
SLIDE_LAYOUTS = "skills/teaching-slide-designer/scripts/slide_layouts.py"

# 已知会做 PPTX 的外部技能名。任何一个重新出现在外部技能表或矩阵里，
# 都说明"幻灯片能力又外包出去了"。
SLIDE_EXTERNAL_NAMES = ("pptx", "nature-paper2ppt", "pptx-posters",
                         "slide-deck", "slides")


def _utf8_stdio():
    """把 stdout / stderr 切到 UTF-8（Windows 中文控制台默认 GBK）。

    🔴 守卫自己的检查名里就有 `↔`（U+2194，**GBK 里没有这个字**），
       在默认 GBK 控制台上 `-v` 模式会当场抛 UnicodeEncodeError 打死自己。
       子进程更糟：Demo 打印 `✅`（U+2705，GBK 也没有）时崩，
       父进程拿到的却是「退出码 1」——**看起来像判据红，其实是编码问题**。
    """
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _child_env():
    """子进程环境：**强制 UTF-8 输出**。

    🔴 `PYTHONIOENCODING` 不设的话，子进程在中文 Windows 上会用 GBK 写 stdout，
       碰到 `✅` / `↔` / `⚠` 这类 GBK 里没有的字符就抛 UnicodeEncodeError。
       父进程把 stdout 用 utf-8 解码，**解码失败会被 errors="replace" 吃掉**——
       于是子进程的死因（编码）在父进程眼里是「退出码 1 + 一堆乱码」，
       判据红的原因和真正的原因对不上号。
       ⇒ 这里显式钉死，别指望继承。
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run_script(rel, args=None):
    """跑一个脚本的 --selftest（或指定参数），返回 (ok, 输出)。"""
    import subprocess
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return False, "文件不存在：%s" % rel
    try:
        r = subprocess.run([sys.executable, p] + list(args or []),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           env=_child_env(), timeout=180)
    except Exception as e:
        return False, "执行失败：%s" % e
    out = (r.stdout or b"").decode("utf-8", "replace").strip()
    if r.returncode != 0:
        return False, "退出码 %d：%s" % (r.returncode, out.splitlines()[-1] if out else "")
    return True, out.splitlines()[-1] if out else ""


def _run_script_full(rel, args=None):
    """跑一个脚本并返回 (ok, 完整输出)。

    🔴 为什么单独有一个「拿完整输出」的版本：`_run_script` 只回传**最后一行**，
    而有些判据要从输出里**取事实**（比如自检用了哪个临时目录），
    拿最后一行就什么都取不到 ⇒ 判据会退化成「找不到就当过了」——
    那是典型的静默漏检。
    """
    import subprocess
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return False, "文件不存在：%s" % rel
    try:
        r = subprocess.run([sys.executable, p] + list(args or []),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           env=_child_env(), timeout=180)
    except Exception as e:
        return False, "执行失败：%s" % e
    return r.returncode == 0, (r.stdout or b"").decode("utf-8", "replace")


# ─────────────────────────────────────────────────────────────
# 6. 演示程序（demo/）：端到端跑通 + 判据不空转
#
# 🔴 为什么单独设一组：
#    Demo 是这个仓库对外的「试用入口」，它一旦腐化（示例 spec 与判据脱节、
#    渲染链路坏掉），别人克隆下来第一眼看到的就是坏的。
#    而且「自检全绿」有两种可能 —— 真的没问题，或者**检查在空转**。
#    所以既要跑通，也要有变异测试证明判据会红。
# ─────────────────────────────────────────────────────────────
DEMO_RUN = "demo/run_demo.py"
DEMO_SELFTEST = "demo/selftest.py"


def check_demo():
    ok, d = _run_script(DEMO_SELFTEST)
    check("Demo 自检判据的变异测试全绿（判据不会空转）", ok, d)

    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="jfa_demo_")
    try:
        ok2, d2 = _run_script(DEMO_RUN, ["--out", tmp])
        check("Demo 端到端跑通（离线模式零 ERROR）", ok2, d2)
        must = ["教案.md", "试卷.md", "幻灯片.pptx", "讲义.md", "自检报告.md"]
        gone = [f for f in must if not os.path.isfile(os.path.join(tmp, f))]
        check("Demo 产出四件交付物与自检报告", not gone,
              "缺：%s" % ", ".join(gone))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_slide_selfsufficiency():
    check("仓库自带 PPTX 生成器（幻灯片能力不外包）",
          os.path.isfile(os.path.join(ROOT, SLIDE_PPTX_MAKER)),
          "缺 %s" % SLIDE_PPTX_MAKER)
    check("仓库自带幻灯片规范审查器",
          os.path.isfile(os.path.join(ROOT, SLIDE_SPEC_LINT)),
          "缺 %s" % SLIDE_SPEC_LINT)

    reg = external_skills()
    bad = sorted(n for n in SLIDE_EXTERNAL_NAMES if n in reg)
    check("外部技能表未再登记 PPTX 生成类外部技能", not bad,
          "仍在册：%s（幻灯片能力已由本仓库自研脚本承担）" % ", ".join(bad))

    marked = set()
    for cid, cell, status in matrix_rows():
        marked |= set(parse_cell(cell)["e"])
    bad2 = sorted(n for n in SLIDE_EXTERNAL_NAMES if n in marked)
    check("能力矩阵的幻灯片相关格不依赖 PPTX 生成类外部技能", not bad2,
          "仍依赖：%s" % ", ".join(bad2))

    # 🔴 自检不许在系统 TEMP 里留垃圾目录。
    #    这条不是洁癖：守卫每跑一次调它一次、变异测试一轮调几十次，
    #    不清理 ⇒ TEMP 里堆出上百个 `jfa_pptx_*`（本轮实测就是 160 个）。
    #
    #    判据：脚本**报告**它用了哪个临时目录，守卫**独立**核对该目录
    #    跑完还在不在。不用「前后对比 TEMP 目录数」那种写法 ——
    #    并发跑两个守卫时会把对方的临时目录算成自己的泄漏，误报。
    #    脚本只报事实（路径），不下结论；判断由守卫做。
    ok1, full = _run_script_full(SLIDE_PPTX_MAKER, ["--selftest"])
    check("自研 PPTX 生成器自检通过（幻灯片能力随包可跑）", ok1,
          (full or "").strip().splitlines()[-1] if (full or "").strip() else "")
    m = re.search(r"selftest:\s*tmpdir=(.+)", full or "")
    if not m:
        check("自研 PPTX 自检不遗留临时目录", False,
              "自检输出里找不到 tmpdir 行，无法核对它有没有清理")
    else:
        tmpdir = m.group(1).strip()
        check("自研 PPTX 自检不遗留临时目录", not os.path.exists(tmpdir),
              "自检用的临时目录仍在：%s" % tmpdir)
    ok2, d2 = _run_script(SLIDE_SPEC_LINT, ["--selftest"])
    check("自研幻灯片规范审查器自检通过", ok2, d2)

    # 版式原型表：渲染器与判据共用的那一份几何。表坏了 ⇒ 渲染和判据一起坏。
    ok3, d3 = _run_script(SLIDE_LAYOUTS, [])
    check("版式原型表自检通过（几何与文字高度表自洽）", ok3, d3)


# ─────────────────────────────────────────────────────────────
# 4b. 大纲先行层：教案与课件的唯一事实源
#
# 🔴 为什么这条守卫值得单列一组：
#    "改了教案忘了改课件"是两份文件各自写出来时的经典失败模式。
#    靠人工核对去发现它，既慢又不可靠 —— 而且**没人能保证自己每次都核对**。
#    大纲先行层把它变成**结构问题**：两边都从同一份事实源派生，
#    "对不上"在结构上就不可能发生。
#
#    守卫查的是「派生结果 == 重新派生的结果」（可证伪），
#    不是「两份文件碰巧一样」（靠不住 —— 碰巧一样时可能已经各改各的）。
# ─────────────────────────────────────────────────────────────
OUTLINE_DERIVER = "demo/outline.py"
OUTLINE_SPEC = "demo/spec/outline.example.json"
OUTLINE_PROMPT = "demo/prompts/outline.md"


def check_outline_layer():
    missing = [rel for rel in (OUTLINE_DERIVER, OUTLINE_SPEC, OUTLINE_PROMPT)
               if not os.path.isfile(os.path.join(ROOT, rel.replace("/", os.sep)))]
    check("大纲先行层的文件齐全（派生器 / 事实源 / 在线任务书）", not missing,
          "缺：%s" % ", ".join(missing))
    if missing:
        return

    ok, d = _run_script(OUTLINE_DERIVER, ["--check"])
    check("教案与课件确由大纲派生（唯一事实源）", ok, d)

    # 离线 Demo 必须**真的**走大纲层：产物里要有大纲凭据。
    # 🔴 "示例文件碰巧一致"证明不了流水线走了大纲 —— 有人可以把 run_demo
    #    改回直接读示例 spec，那样上面那条守卫照样绿。所以要单独查产物。
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="jfa_outline_")
    try:
        ok2, d2 = _run_script(DEMO_RUN, ["--out", tmp])
        p = os.path.join(tmp, "outline.spec.json")
        if not ok2:
            check("离线 Demo 走大纲层（产出大纲凭据）", False, d2)
        elif not os.path.isfile(p):
            check("离线 Demo 走大纲层（产出大纲凭据）", False,
                  "Demo 产物里没有 outline.spec.json —— 大纲层被绕过了")
        else:
            check("离线 Demo 走大纲层（产出大纲凭据）", True, "")
        # 讲义也必须是**产物**：讲稿与课件同源，靠的就是「讲义是派生的」这件事。
        handout = os.path.join(tmp, "讲义.md")
        check("离线 Demo 产出讲义（讲稿与课件同源）",
              os.path.isfile(handout), "Demo 产物里没有讲义.md")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ── 判据覆盖面：UbD 骨架与页面 id 的规则码必须**真的被验过** ──
    # 🔴 「规则写在判据里」不等于「判据会红」；「判据会红」也不等于
    #    「这一条规则被覆盖到了」。这里查的是**变异测试用例的期望命中码** ——
    #    有 ⇒ 有人专门破坏过它 ⇒ 它会红。
    #    匹配的是 `, "OL-P15"`（**期望码的位置**），不是裸的 "OL-P15"：
    #    裸串会出现在注释里，也会出现在别的用例里 ⇒ 匹配太宽 = 守卫太松。
    st = read("demo/selftest.py")
    need_codes = ["OL-P15", "OL-P16", "OL-P17", "OL-P18", "OL-P19",
                  "HD-P03", "HD-P04"]
    miss_codes = [c for c in need_codes if (', "%s"' % c) not in st]
    check("判据变异测试覆盖 UbD 骨架 / 页面 id / 讲义同源", not miss_codes,
          "selftest 里没有这些规则码的变异用例：%s" % ", ".join(miss_codes))

    # ── 增量重生成：只重跑一页 ⇒ 其余页逐字不动 ──
    #    这是「只重跑一页」这件事的**可证伪**判据：
    #    替换一旦漏到别处，其余页的指纹就会变。
    #    🔴 **每一页都要试**：只试一页 = 押注「那一页恰好有邻页、恰好走同一条分支」。
    #       曾经就栽在这里：守卫挑的是封面页（deck 分支，没有下一页），
    #       注入的泄漏根本没触发 ⇒ 守卫绿着，而这条承诺早就破了。
    try:
        import importlib.util
        mod_spec = importlib.util.spec_from_file_location(
            "jfa_outline_mod", os.path.join(ROOT, "demo", "outline.py"))
        om = importlib.util.module_from_spec(mod_spec)
        mod_spec.loader.exec_module(om)
        with open(os.path.join(ROOT, "demo", "spec", "outline.example.json"),
                  "r", encoding="utf-8") as f:
            ol = json.load(f)
        before = om.page_fingerprints(ol)
        leaks = []
        for pid in sorted(before):
            newp = dict(om.page_context(ol, pid)["current"])
            newp["title"] = "守卫自检用的改写标题"
            ol2, changed = om.replace_page(ol, pid, newp)
            after = om.page_fingerprints(ol2)
            touched = sorted(k for k in before if before[k] != after.get(k))
            if not (changed and touched == [pid] and len(before) == len(after)):
                leaks.append("%s 动了 %s" % (pid, ",".join(touched) or "无"))
        check("增量重生成只动一页（其余页逐字不变）", not leaks,
              "；".join(leaks[:4]))
    except Exception as e:
        check("增量重生成只动一页（其余页逐字不变）", False,
              "%s: %s" % (type(e).__name__, e))

    # ── 模型按用途路由：四个用途都要有（**行为**判据，不是文本匹配）──
    # 🔴 文本匹配挡不住「文档里还写着 lint、代码里已经删了」。
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "jfa_llm_mod", os.path.join(ROOT, "demo", "llm.py"))
        lm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lm)
        need_purposes = ("plan", "slides", "handout", "lint")
        miss_p = [p for p in need_purposes if p not in tuple(lm.PURPOSES)]
        check("模型按用途路由（plan/slides/handout/lint）", not miss_p,
              "llm.PURPOSES 里缺这些用途：%s" % ", ".join(miss_p))
    except Exception as e:
        check("模型按用途路由（plan/slides/handout/lint）", False,
              "%s: %s" % (type(e).__name__, e))


# ─────────────────────────────────────────────────────────────
# 3b. GitHub 开源件：这份仓库能不能**直接**发到 GitHub 上
#
# 🔴 为什么这些要进守卫：开源项目的"可发布性"是最容易悄悄烂掉的东西 ——
#    CI 文件还在，但里面跑的命令早就改了；社区文件还在，但内容指向已消失的路径。
#    这些都不会让任何既有检查变红 ⇒ 没有守卫 = 慢慢烂掉。
# ─────────────────────────────────────────────────────────────
GITHUB_REQUIRED = [
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    ".gitattributes",
    ".editorconfig",
    "references/github-release.json",
    "scripts/github_release.py",
]

# 🔴 CI 必须**真的**跑本仓库的判据。
#    一个只写"跑一下测试"的 workflow 等于没有 CI —— 它不会在任何东西变坏时变红。
CI_MUST_RUN = [
    "scripts/verify_repo.py",
    "scripts/verify_rewrite.py",
    "demo/selftest.py",
    "scripts/package_release.py",
]


def check_github_open_source():
    missing = [rel for rel in GITHUB_REQUIRED
               if not os.path.isfile(os.path.join(ROOT, rel.replace("/", os.sep)))]
    check("GitHub 开源件齐全（CI / 社区文件 / 模板 / 出包脚本）", not missing,
          "缺：%s" % ", ".join(missing))

    ci = read(".github/workflows/ci.yml")
    # 🔴 **只看代码行，不看注释行**。
    #    上一版用 `"scripts/verify_repo.py" in ci` 判，结果被 ci.yml 里的
    #    一句注释喂饱了 —— 而真正的 `run:` 命令还在。
    #    ⇒ **文本匹配会把注释当成执行**，而 CI 里真正跑什么只有 run: 行说了算。
    ci_code = [ln.strip() for ln in ci.splitlines()
               if ln.strip() and not ln.strip().startswith("#")]
    ci_runs = [ln for ln in ci_code if ln.startswith("run:")]

    def _ci_runs(cmd):
        return any(cmd in ln for ln in ci_runs)

    miss_run = [c for c in CI_MUST_RUN if not _ci_runs(c)]
    check("CI 真的跑本仓库的判据（不是空 workflow）", not miss_run,
          "ci.yml 的 run: 行里没跑：%s" % ", ".join(miss_run))

    # Windows 与 Python 3.9 都要在矩阵里：
    #   · Windows —— 中文控制台 GBK 那类问题**只在 Windows 暴露**，
    #     只跑 ubuntu 会把"自己母语环境下不绿"的守卫漏过去；
    #   · 3.9 —— 本项目的兼容下限，少了它就没人证明下限还成立。
    #   同样**只看代码行**：注释里提一句 3.9 不等于矩阵里有 3.9。
    win = any("windows-latest" in ln for ln in ci_code)
    py39 = any('"3.9"' in ln for ln in ci_code)
    check("CI 覆盖 Windows 与 Python 3.9（编码坑 / 兼容下限）", win and py39,
          "windows-latest=%s / 3.9=%s" % (win, py39))

    # 发布配置：仓库名 / 描述 / topics 必填；owner 允许为空（还没建仓库），
    # 但**填了就不能是乱码** —— 链接会直接印在发布说明上。
    cfg = {}
    cfg_path = os.path.join(ROOT, "references", "github-release.json")
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    repo = str(cfg.get("repo") or "").strip()
    desc = str(cfg.get("description") or "").strip()
    topics = cfg.get("topics") or []
    owner = str(cfg.get("owner") or "").strip()
    bad_owner = bool(owner) and not re.match(r"^[A-Za-z0-9][A-Za-z0-9-]*$", owner)
    ok_cfg = (bool(repo) and bool(desc) and isinstance(topics, list)
              and len(topics) >= 3 and not bad_owner)
    check("GitHub 发布配置完整（仓库名 / 描述 / topics / owner 合法）", ok_cfg,
          "repo=%r 有描述=%s topics=%d owner=%r" % (repo, bool(desc),
                                                    len(topics) if isinstance(topics, list) else -1,
                                                    owner))

    # CHANGELOG 必须覆盖**当前版本** —— 否则发布说明会是一份没有本版内容的文档
    ver = ""
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import package_release
        ver = package_release.VERSION
    except Exception:
        ver = ""
    ch = read("CHANGELOG.md")
    has = bool(ver) and ("## [%s]" % ver) in ch
    check("CHANGELOG 覆盖当前版本（%s）" % (ver or "?"), has,
          "CHANGELOG 里没有 ## [%s] 的条目" % (ver or "?"))

    # 🔴 占位符：owner 一填上，文档里就不该还留 OWNER/REPO。
    #    owner 为空是**正常的**（还没建仓库）⇒ 此时发布说明自动用占位；
    #    但一旦填了 owner 还没清占位 ⇒ 公开仓库里就挂着指向不存在仓库的链接，
    #    而**没有任何既有检查会为此变红**。
    #    （与 check_upstream 同一处理法：环境相关的检查也要计入总数，
    #      否则守卫的检查数会随环境变化，README 里的「N/N」就不是一句话了。）
    if owner:
        stale = [rel for rel in (".github/ISSUE_TEMPLATE/config.yml", "CHANGELOG.md")
                 if "OWNER/REPO" in read(rel)]
        check("owner 已填 ⇒ 文档里不再留 OWNER/REPO 占位", not stale,
              "仍含占位：%s" % ", ".join(stale))
    else:
        check("owner 已填 ⇒ 文档里不再留 OWNER/REPO 占位", True,
              "owner 尚未填写（发布前填上即可）")


# ─────────────────────────────────────────────────────────────
# 5. 分档出包（teaching / research / full）的一致性
#
# 🔴 为什么必须有这一组：分档包的技能集合是**从能力矩阵推导**出来的。
#    推导链一旦与仓库现实脱节，就会静默打出一个「与仓库宣称不符」的包 ——
#    而包一旦发出去，改不了了（收件人拿到的是那个版本）。
#
#    判据必须**可证伪**，不是装饰：
#      ① 每个已装技能都要有归属（矩阵内 or 仓库机制类）—— 否则它会
#         在 teaching ∪ research 两档里**双双消失**，而没人发现；
#      ② 恒等式 teaching ∪ research == full − 仓库机制类；
#      ③ 每个能力域都被至少一个分档覆盖 —— 新加一格却没人认领 =
#         该格的技能在两个分档里都蒸发；
#      ④ 每档非空、不含未安装技能；
#      ⑤ 每档所需的许可副本齐备。
#
#    推导逻辑只有一份：`scripts/profile_map.py`（出包器与守卫共用）。
#    两套实现必然漂移，漂移是静默的。
# ─────────────────────────────────────────────────────────────
def check_profiles():
    try:
        if os.path.isdir(os.path.join(ROOT, "scripts")):
            sys.path.insert(0, os.path.join(ROOT, "scripts"))
        from profile_map import (full_only_skills, installed_skills,
                                 invariant_problems, load_profiles,
                                 matrix_domains, matrix_installed_skills,
                                 profile_domains, profile_names,
                                 profile_skill_set, required_license_copies)
    except Exception as e:
        check("分档推导模块 profile_map 可用", False, "导入失败：%s" % e)
        return
    check("分档推导模块 profile_map 可用", True)

    prof = load_profiles()
    names = set(profile_names(prof))
    check("references/profiles.json 含 full/teaching/research 三档",
          names == {"full", "teaching", "research"},
          "实际 %s" % ", ".join(sorted(names)))

    inst = installed_skills()
    mx = matrix_installed_skills()
    fo = full_only_skills(prof)

    unclassified = sorted(inst - mx - fo)
    check("每个已装技能都有归属（矩阵内或仓库机制类）", not unclassified,
          "未归类：%s" % ", ".join(unclassified[:8]))

    # 🔴 缺失的档位不能让它**炸掉**守卫 —— 守卫崩了等于后面的检查一条都没跑。
    #    缺档位是一条可报告的 FAIL，不是一个 traceback。
    def skills_of(name):
        if name not in names:
            return None
        try:
            return profile_skill_set(name, prof=prof)
        except Exception as e:
            check("档案 %s 可推导" % name, False, "推导失败：%s" % e)
            return None

    t = skills_of("teaching")
    r = skills_of("research")
    f = skills_of("full")
    if t is not None and r is not None and f is not None:
        only_a = sorted((t | r) - (f - fo))
        only_b = sorted((f - fo) - (t | r))
        check("分档恒等式：teaching ∪ research = full − 仓库机制类",
              (t | r) == (f - fo),
              "多 %s / 少 %s" % (", ".join(only_a) or "无",
                                 ", ".join(only_b) or "无"))
    else:
        check("分档恒等式：teaching ∪ research = full − 仓库机制类", False,
              "有档位缺失，无法比较")

    covered = set()
    for name in profile_names(prof):
        if name != "full":
            covered |= set(profile_domains(name, prof))
    uncovered = sorted(matrix_domains() - covered)
    check("每个能力域都被至少一个分档覆盖", not uncovered,
          "无人认领：%s" % ", ".join(uncovered))

    bad = []
    for name in profile_names(prof):
        s = skills_of(name)
        if s is None:
            bad.append("%s 无法推导" % name)
            continue
        if not s:
            bad.append("%s 技能集为空" % name)
        stray = sorted(s - inst)
        if stray:
            bad.append("%s 含未安装技能 %s" % (name, ", ".join(stray)))
    check("每个分档的技能集非空且不含未安装技能", not bad, "; ".join(bad))

    have = set()
    lic_dir = os.path.join(ROOT, "licenses")
    if os.path.isdir(lic_dir):
        have = set(os.listdir(lic_dir))
    miss = []
    for name in profile_names(prof):
        s = skills_of(name)
        if s is None:
            continue
        need = required_license_copies(s)
        gone = sorted(need - have)
        if gone:
            miss.append("%s 缺 %s" % (name, ", ".join(gone)))
    check("每个分档所需的许可副本都在 licenses/ 里", not miss, "; ".join(miss))

    # 端到端：出包器自己的闸门（同一份实现）必须也是绿的，
    # 否则「守卫绿但出包中止」或反过来，两边会打架。
    inv = invariant_problems(prof)
    check("分档推导自洽（出包器与守卫共用同一实现）", not inv,
          "; ".join(inv[:4]))


# ─────────────────────────────────────────────────────────────
# 4. README 的数字 ↔ 实际
# ─────────────────────────────────────────────────────────────
def check_readme(counts):
    readme = read("README.md")
    if not readme:
        check("README.md 存在", False)
        return

    m = re.search(r"## 能力矩阵（6 域 (\d+) 格）", readme)
    total = sum(sum(v.values()) for v in counts.values())
    check("README 格数 ↔ 矩阵实际",
          bool(m) and int(m.group(1)) == total,
          "README %s / 实际 %d" % (m.group(1) if m else "无", total))

    claims = {}
    for line in readme.splitlines():
        cm = re.match(r"^\|\s*([A-F])\s+[^|]*\|[^|]*\|\s*(\d+)/(\d+)\s*\|", line)
        if cm:
            claims[cm.group(1)] = (int(cm.group(2)), int(cm.group(3)))
    bad = []
    for dom, (num, den) in claims.items():
        c = counts.get(dom, {})
        actual_full = c.get("已覆盖", 0)
        actual_total = sum(c.values())
        if num != actual_full or den != actual_total:
            bad.append("%s README %d/%d ≠ 实际 %d/%d"
                       % (dom, num, den, actual_full, actual_total))
    check("README 各域覆盖计数 ↔ 矩阵实际", len(claims) == 6 and not bad,
          "; ".join(bad))

    m = re.search(r"├── skills/\s+# (\d+) 个技能", readme)
    check("README 目录树技能数 = %d" % len(installed_skills()),
          bool(m) and int(m.group(1)) == len(installed_skills()),
          "README %s / 实际 %d" % (m.group(1) if m else "无", len(installed_skills())))

    # 「从 GitHub 学习而来」= 真正取自上游仓库的技能数。
    # 50 个教学技能改写后**不再是**「从 GitHub 学习而来」—— 那是本项目原创，
    # 只是主题与命名参考了上游清单。写死 70 会在改写完成时立刻变成谎言。
    kdense_n = sum(1 for s in installed_skills() if classify(s) == "kdense")
    m = re.search(r"<(\d+) 个 GitHub 技能>", readme)
    check("README 目录树 GitHub 技能数 = %d" % kdense_n,
          bool(m) and int(m.group(1)) == kdense_n,
          "README %s / 实际 %d" % (m.group(1) if m else "无", kdense_n))

    # README 里 selftest 的通过数（写法会随文案调整，宽松匹配）
    # 🔴 数字必须**从巡检器自己算出来**，不能写死 ——
    #    写死 14/14 的时候，巡检器加了 5 项检查，README 会一直停在旧数字上，
    #    而且没人会发现（因为守卫自己也在写死同一个数）。
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import skill_scan
        n_self, _fail = skill_scan.selftest()
    except Exception:
        n_self = -1
    m = re.search(r"--selftest`[^\n]*?(\d+)/(\d+)", readme)
    check("README 自检计数 = %d/%d" % (n_self, n_self),
          bool(m) and n_self > 0
          and (m.group(1), m.group(2)) == (str(n_self), str(n_self)),
          "README %s" % (("%s/%s" % (m.group(1), m.group(2))) if m else "无"))

    # README 里 "从 GitHub 学习而来（N 个）"
    m = re.search(r"### 从 GitHub 学习而来（(\d+) 个）", readme)
    check("README 『从 GitHub 学习而来』= %d" % kdense_n,
          bool(m) and int(m.group(1)) == kdense_n,
          "README %s / 实际 %d" % (m.group(1) if m else "无", kdense_n))

    # 商业可用性：README 必须声明可商用，且不得残留"整体不可商用"的说法
    check("README 声明可商用",
          "可以开源，也可以商用" in readme or "整体可用于商业用途" in readme,
          "README 未声明商业可用性")
    check("README 无『整体不可商用』的过期说法",
          "本仓库整体不可商用" not in readme
          and "不得用于任何商业用途" not in readme,
          "README 仍写着不可商用")

    # 目录树里列出的文件必须真的存在
    missing = []
    for rel in ("LICENSE", "NOTICE.md", "THIRD-PARTY-NOTICES.md",
                "licenses", "scripts/verify_repo.py",
                "references/faculty-capability-matrix.md"):
        if not os.path.exists(os.path.join(ROOT, rel.replace("/", os.sep))):
            missing.append(rel)
    check("README 目录树列出的文件都存在", not missing, ", ".join(missing))

    # 🔴 目录树里列出的许可副本清单必须与 licenses/ 磁盘实际一致。
    # NC 许可副本早已移入 skills-archive/，README 若还列着它就是在撒谎。
    # 只取目录树代码块，避免正文里的历史陈述（如"已移出"）造成误报。
    tree_block = ""
    tm = re.search(r"##\s*目录结构.*?```\n(.*?)```", readme, re.S)
    if tm:
        tree_block = tm.group(1)
    lic_dir = os.path.join(ROOT, "licenses")
    actual_lic = set(os.listdir(lic_dir)) if os.path.isdir(lic_dir) else set()
    claimed_lic = set(re.findall(r"([A-Za-z0-9._-]+\.txt)", tree_block))
    stale_lic = sorted(claimed_lic - actual_lic)
    check("README 目录树的许可副本清单 ↔ licenses/ 实际", not stale_lic,
          "README 列出但磁盘没有：%s" % ", ".join(stale_lic))

    # README 正文里引用的仓库内路径（reports/、references/、scripts/…）必须存在
    ref_missing = []
    for ref in re.findall(r"`((?:reports|references|scripts|licenses|crons)/[^`\s]+)`",
                          readme):
        if "<" in ref or ">" in ref:
            continue        # 模板占位符（如 skill-scan-<年>-Q<N>.md），不是真实路径
        if not os.path.exists(os.path.join(ROOT, ref.replace("/", os.sep))):
            ref_missing.append(ref)
    check("README 引用的仓库内路径都存在", not ref_missing,
          ", ".join(sorted(set(ref_missing))))


# ─────────────────────────────────────────────────────────────
# 5. 自有清单：LICENSE ↔ NOTICES ↔ NOTICE.md 三方一致
# ─────────────────────────────────────────────────────────────
def check_own_lists():
    lic = read("LICENSE")
    notices = read("THIRD-PARTY-NOTICES.md")
    notice = read("NOTICE.md")

    def block(text):
        blocks = re.findall(r"```\n(.*?)```", text, re.S)
        if not blocks:
            return set()
        # 取含 skills/grant-proposal-writer 的那一块
        for b in blocks:
            if "skills/grant-proposal-writer" in b:
                # 🔴 `#` 开头的是**分组注释**（如 OpenMAIC 衍生那一组），
                #    不是清单项 —— 注释里的路径不存在，不能拿去核存在性。
                return set(x.strip() for x in b.strip().splitlines()
                           if x.strip() and not x.strip().startswith("#"))
        return set()

    a, b = block(lic), block(notices)
    check("LICENSE ↔ NOTICES 自有清单一致", a and a == b,
          "LICENSE %d 项 / NOTICES %d 项；差异 %s"
          % (len(a), len(b), sorted(a ^ b)))

    missing_in_repo = []
    for item in a:
        name = item.split("/")[0].strip()
        if name.endswith("/"):
            name = name[:-1]
        if not name or "(" in name:
            continue
        if not os.path.exists(os.path.join(ROOT, name.replace("/", os.sep))):
            missing_in_repo.append(item)
    check("自有清单里的路径都真实存在", not missing_in_repo,
          ", ".join(missing_in_repo))

    # NOTICE.md 的自有说明应覆盖 scripts/verify_repo.py
    check("NOTICE.md 覆盖 scripts/verify_repo.py",
          "scripts/verify_repo.py" in notice, "NOTICE.md 未提及")


# ─────────────────────────────────────────────────────────────
# 8. 引文一致性：同一作者在不同技能里不能有两个首字母
# ─────────────────────────────────────────────────────────────
def check_citations():
    """同一作者被引成 "Messick, S." 与 "Messick, H." —— 至少有一处写错了。

    50 个技能是并行写出来的，同一作者被不同作者手抄进不同文件时，
    首字母/拼写最容易走样。逐个技能看是看不出来的，**跨技能比对**才抓得到。

    ⚠️ 但**同姓不同人**是合法情况：Schwartz（S. A. / M. S. / D. L.）、
    Sfard（A. = Avigdor，D. = Daphne）、Bjork（E. L. = Elizabeth，R. A. = Robert）
    都是真实存在的不同作者。这类姓氏必须显式列入白名单 ——
    白名单是**人工核实的**，写在这里就是给人看的，不是为了让检查变绿。
    """
    manifest = rewrite_manifest()
    pat = re.compile(r"([A-Z][A-Za-z'’\-]+),\s+([A-Z])\.")
    seen = {}
    # 🔴 覆盖范围 = 改写清单 50 个 **+ OpenMAIC 衍生技能**。
    #    后者是本项目新写的技能，同样会把作者首字母手抄进文件 ——
    #    只查清单的话，新写的技能就成了校验盲区。
    for n in sorted(set(manifest) | openmaic_derived_skills()):
        txt = read(os.path.join("skills", n, "SKILL.md"))
        i = txt.find("## 方法论依据")
        if i < 0:
            continue
        sec = txt[i:i + 2500]
        for m in pat.finditer(sec):
            surname, initial = m.group(1), m.group(2)
            seen.setdefault(surname, set()).add(initial)
    split = {k: sorted(v) for k, v in seen.items()
             if len(v) > 1 and k not in SAME_SURNAME_MULTI_AUTHOR}
    check("同一作者的首字母在全仓一致", not split,
          "; ".join("%s: %s" % (k, "/".join(v)) for k, v in list(split.items())[:6]))


# ─────────────────────────────────────────────────────────────
# 9. README「验证」章节里的自检数字 ↔ 实际
# ─────────────────────────────────────────────────────────────
def check_readme_selfcheck_counts():
    """README「验证」章节里写的数字必须与实际一致。

    🔴 这一段是最容易过期的地方（守卫加了检查、变异加了用例、出包文件多了，
    README 里的示例输出却还停在旧数字）。**写成机器检查**才不会复发。

    ⚠️ 本守卫自己的检查总数是**自指**的，单独放在
    `check_readme_guard_total()` 里做，且必须是 main() 的**最后一项**。
    """
    readme = read("README.md")
    if not readme:
        return

    # ① 变异测试的用例数（从 test_verify_repo 的 MUTATIONS 列表直接读）
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import test_verify_repo
        n_mut = len(test_verify_repo.MUTATIONS)
    except Exception:
        n_mut = -1
    m = re.search(r"(\d+)/(\d+)\s*项变异", readme)
    got_num = int(m.group(1)) if m else -1
    got_den = int(m.group(2)) if m else -1
    # 分子分母都要等于实际：全绿时 README 只能写 n/n。
    # ⚠️ 只取分子会漏掉「21/99」这种分母写错的情况（与下面同源的老毛病）。
    check("README 写的变异用例数 = 实际（%d）" % n_mut,
          n_mut > 0 and got_num == n_mut and got_den == n_mut,
          "README %s / 实际 %d/%d" % (m.group(0) if m else "无", n_mut, n_mut))

    # ② 分发包文件数（从 package_release 的 collect_files 直接读）
    try:
        import package_release
        n_files = len(package_release.collect_files())
    except Exception:
        n_files = -1
    m = re.search(r"（(\d+)\s*个文件\s*\+\s*MANIFEST\.json）", readme)
    got = int(m.group(1)) if m else -1
    check("README 写的分发包文件数 = 实际（%d）" % n_files,
          n_files > 0 and got == n_files,
          "README %s / 实际 %d" % (m.group(0) if m else "无", n_files))

    # ③ verify_rewrite 的检查数（README「验证」章节里写的 N/N）
    #
    # 🔴 **这个数取决于上游原文目录在不在** ——
    #    带上游（--upstream / JFA_UPSTREAM）会多跑 clean-room 相似度核对，
    #    每个技能多 1–2 项；而**上游仓库不随本仓库分发**，克隆方默认没有上游。
    #    ⇒ README 写哪个数，取决于「读者手边有没有上游」。
    #    本守卫**显式清掉 JFA_UPSTREAM 再跑**，量到的就是**克隆方会看到的那个数**，
    #    README 必须写这个口径；另一个口径只能作为括注出现。
    #
    #    之前 README 写的是「有上游」的数字（716），克隆方实跑是 666 ——
    #    文档在撒谎，而且没人发现，因为写文档的人和跑文档的人不是同一个环境。
    n_rw = n_rw_den = -1
    try:
        import subprocess
        env = dict(os.environ)
        env.pop("JFA_UPSTREAM", None)      # 量「无上游」口径
        env["PYTHONIOENCODING"] = "utf-8"   # 中文控制台不因 ⚠️ 崩掉
        r = subprocess.run([sys.executable, os.path.join("scripts", "verify_rewrite.py")],
                           cwd=ROOT, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
        out = (r.stdout or b"").decode("utf-8", "replace")
        m2 = re.search(r"verify_rewrite:\s*(\d+)/(\d+)\s*checks passed", out)
        if m2:
            n_rw, n_rw_den = int(m2.group(1)), int(m2.group(2))
    except Exception:
        pass
    m = re.search(r"verify_rewrite:\s*(\d+)/(\d+)\s*checks passed", readme)
    got = int(m.group(1)) if m else -1
    got_den = int(m.group(2)) if m else -1
    check("README 写的 verify_rewrite 检查数 = 实际（无上游口径 %d）" % n_rw,
          n_rw > 0 and got == n_rw and got_den == n_rw,
          "README %s / 实际 %d/%d" % (m.group(0) if m else "无", n_rw, n_rw_den))


def check_readme_guard_total():
    """README 写的「verify_repo: N/N」必须等于本守卫的最终检查数。

    ⚠️ 必须是 main() 的**最后一项** —— 此时最终总数 = len(RESULTS) + 1
    （+1 是本检查自己）。新增检查必须加在它**之前**，否则期望值会算错。
    """
    readme = read("README.md")
    m = re.search(r"verify_repo:\s*(\d+)/(\d+)\s*checks passed", readme)
    want = len(RESULTS) + 1          # +1 = 本检查自己
    if not m:
        check("README 写的 verify_repo 检查数 = 实际（%d）" % want, False,
              "README 无 verify_repo 检查数 / 实际 %d/%d" % (want, want))
        return
    got_num, got_den = int(m.group(1)), int(m.group(2))
    # ⚠️ 分子分母**都要**等于实际：全绿时 README 只能写 want/want。
    # 只比分母会漏掉「99/55」这种分子写错的情况 —— 曾真实漏检过一次，
    # 由变异测试发现（守卫自己也是被测对象）。
    check("README 写的 verify_repo 检查数 = 实际（%d）" % want,
          got_num == want and got_den == want,
          "README %s / 实际 %d/%d" % (m.group(0), want, want))


# ─────────────────────────────────────────────────────────────
# 6. 可移植性：硬编码机器路径 / 密钥 / 编码
# ─────────────────────────────────────────────────────────────
TEXT_EXT = {".md", ".py", ".json", ".txt", ".yaml", ".yml", ".cfg", ".ini"}


def iter_text_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "__pycache__", ".cache", ".venv"}]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in TEXT_EXT:
                yield os.path.join(dirpath, fn)


def check_portability():
    hard = []
    # 注意：不要给路径模式加 ^ 锚点 —— 路径常出现在行中间（如 Markdown 注释、
    # 括号补充说明、行尾）。加锚点会让"注入在行中间"的硬编码路径漏检。
    HARD_PATTERNS = [
        re.compile(r"[A-Za-z]:\\Users\\"),
        re.compile(r"[A-Za-z]:\\\S*工具"),
        re.compile(r"/home/[A-Za-z0-9]"),
        re.compile(r"/Users/[A-Za-z0-9]"),
    ]
    for p in iter_text_files():
        rel = os.path.relpath(p, ROOT)
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if any(pat.search(line) for pat in HARD_PATTERNS):
                    hard.append("%s:%d" % (rel, i))
    check("无硬编码机器绝对路径", not hard,
          "%d 处：%s" % (len(hard), ", ".join(hard[:6])))

    secrets = []
    SECRET_RE = re.compile(
        r"(sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
        r"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{25,})")
    for p in iter_text_files():
        rel = os.path.relpath(p, ROOT)
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if SECRET_RE.search(line):
                    secrets.append("%s:%d" % (rel, i))
    check("无真实 API 密钥", not secrets, ", ".join(secrets[:6]))

    bom, badenc = [], []
    for p in iter_text_files():
        rel = os.path.relpath(p, ROOT)
        with open(p, "rb") as f:
            data = f.read()
        if data[:3] == b"\xef\xbb\xbf":
            bom.append(rel)
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            badenc.append(rel)
    check("全部文本文件 UTF-8 无 BOM", not bom and not badenc,
          "BOM: %s / 非 UTF-8: %s" % (bom[:3], badenc[:3]))


# ─────────────────────────────────────────────────────────────
# 7. 可选：回源核实（上游暂存目录可用时）
# ─────────────────────────────────────────────────────────────
def check_upstream():
    if not UPSTREAM or not os.path.isdir(UPSTREAM):
        # 🔴 跳过的检查**也要计入总数** —— 否则守卫的检查数会随环境变化
        #    （有/无上游暂存目录差 2 项），README 里的「N/N」就不是一句
        #    可复现的话。判为通过并注明跳过原因。
        check("上游候选逐条回源核实", True, "跳过（未设 JFA_UPSTREAM）")
        check("许可副本与上游字节一致", True, "跳过（未设 JFA_UPSTREAM）")
        return
    manifest_path = os.path.join(ROOT, "references", "upstream-candidates.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = {k: v for k, v in json.load(f).items()
                    if not k.startswith("_")}
    missing = []
    for name, meta in manifest.items():
        bases = upstream_dirs(meta["upstream"])
        if not bases:
            continue
        hit = None
        for base in bases:
            for dirpath, dirnames, _ in os.walk(base):
                if os.path.basename(dirpath) == name:
                    hit = dirpath
                    break
            if hit:
                break
        if not hit:
            missing.append("%s(%s)" % (name, meta["upstream"]))
    check("上游候选逐条回源核实", not missing, ", ".join(missing))

    # 许可副本与上游一致
    pairs = [
        ("education-agent-skills", "LICENSE",
         "licenses/CC-BY-SA-4.0-education-agent-skills.txt"),
        ("scientific-agent-skills", "LICENSE.md", "licenses/MIT-K-Dense.txt"),
    ]
    diff, skipped = [], []
    for repo, fname, local in pairs:
        base = upstream_dir(repo)
        if not base:
            skipped.append(repo)
            continue
        src = os.path.join(base, fname)
        if not os.path.exists(src):
            skipped.append("%s/%s" % (repo, fname))
            continue
        with open(src, "rb") as f:
            a = f.read()
        b = read_bytes(local)
        if a != b:
            diff.append(local)
    check("许可副本与上游字节一致", not diff and not skipped,
          ("字节不一致: %s" % ", ".join(diff)) if diff
          else ("未找到上游许可文件: %s" % ", ".join(skipped)))


# ─────────────────────────────────────────────────────────────
def _guard_call(label, fn, *args):
    """跑一组检查；**检查本身崩了也要报红**。

    🔴 为什么必须有这层：守卫抛异常时退出码也是 1，看起来像"发现问题"，
    实际上**后面的检查一条都没跑** —— 那是「静默漏检」，比红更危险。
    变异测试实测抓到过这个失败模式（缺档位 ⇒ 守卫 traceback ⇒
    预期命中的检查项根本没输出）。

    所以：异常 ⇒ 一条 FAIL，detail 里带异常类型与消息，红在**这一组**上。
    """
    try:
        return fn(*args)
    except Exception as e:
        check("%s 执行异常" % label, False, "%s: %s" % (type(e).__name__, e))
        return None


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    _utf8_stdio()
    if not PROFILE_MAP_OK:
        sys.stdout.write("FAIL  无法导入 scripts/profile_map.py（分档推导模块）：%s\n"
                         % PROFILE_MAP_ERR)
        return 1
    buckets = _guard_call("技能总量与分源归属", check_skill_counts) or {}
    _guard_call("NOTICES 清单", check_notices, buckets)
    _guard_call("许可台账完整性", check_license_completeness)
    _guard_call("OpenMAIC 归属台账", check_openmaic_attribution)
    counts = _guard_call("能力矩阵", check_matrix) or {}
    _guard_call("README 一致性", check_readme, counts)
    _guard_call("自有清单三方一致", check_own_lists)
    _guard_call("可移植性", check_portability)
    _guard_call("引文一致性", check_citations)
    _guard_call("上游一致性", check_upstream)
    _guard_call("README 自检数字", check_readme_selfcheck_counts)
    _guard_call("外部技能登记表", check_external_skills)
    _guard_call("幻灯片能力自足", check_slide_selfsufficiency)
    _guard_call("分档出包", check_profiles)
    _guard_call("演示程序", check_demo)
    _guard_call("大纲先行层", check_outline_layer)
    _guard_call("GitHub 开源件", check_github_open_source)
    # ⚠️ 必须最后跑：它用 len(RESULTS)+1 推出本守卫的最终检查总数
    _guard_call("README 守卫检查数", check_readme_guard_total)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    if verbose:
        for name, ok, detail in RESULTS:
            mark = "PASS" if ok else "FAIL"
            line = "[%s] %s" % (mark, name)
            if detail and not ok:
                line += "  -> " + detail
            elif detail and ok:
                line += "  (%s)" % detail
            sys.stdout.write(line + "\n")
    else:
        for name, ok, detail in RESULTS:
            if not ok:
                sys.stdout.write("FAIL  %s  -> %s\n" % (name, detail))
    sys.stdout.write("\nverify_repo: %d/%d checks passed\n"
                     % (passed, len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
