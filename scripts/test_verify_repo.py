#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_repo.py 的变异测试：在仓库副本上注入典型错误，确认守卫能抓到。

守卫自己也是被测对象 —— 只跑通不算数，必须证明它会红。

    python scripts/test_verify_repo.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 仓库根


def run(cwd, rel="scripts/verify_repo.py", extra=None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    script = os.path.join(cwd, rel.replace("/", os.sep))
    if not os.path.exists(script):
        raise RuntimeError("副本里缺少 %s" % script)
    cmd = [sys.executable, script] + list(extra or [])
    p = subprocess.run(cmd, cwd=cwd, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def _rd(dst, rel):
    with open(os.path.join(dst, rel), encoding="utf-8") as f:
        return f.read()


def _wr(dst, rel, text):
    with open(os.path.join(dst, rel), "w", encoding="utf-8", newline="") as f:
        f.write(text)


# ── 各变异：在副本内注入一种典型错误 ──────────────────────────
def mutate_readme_grid(dst):
    t = _rd(dst, "README.md")
    _wr(dst, "README.md",
        t.replace("## 能力矩阵（6 域 41 格）", "## 能力矩阵（6 域 45 格）"))


def mutate_matrix_empty(dst):
    rel = os.path.join("references", "faculty-capability-matrix.md")
    t = _rd(dst, rel)
    t = re.sub(r"(\| F5 AI 素养教学 \|[^|]*\|)[^|]*\|[^|]*\|",
               r"\1 ○ai-expertise-interrogation-designer | 已覆盖 |", t)
    _wr(dst, rel, t)


def mutate_license_rename(dst):
    os.rename(os.path.join(dst, "licenses", "MIT-K-Dense.txt"),
              os.path.join(dst, "licenses", "MIT-K-Dense-2.txt"))


def mutate_license_field_drop(dst):
    """删掉某个已装技能的 license 声明 —— 许可不明 = 商用风险。"""
    rel = os.path.join("skills", "exam-question-bank", "SKILL.md")
    t = _rd(dst, rel)
    t2 = re.sub(r"(?m)^license:[^\n]*\n", "", t, count=1)
    if t2 == t:
        raise RuntimeError("变异无效：exam-question-bank 里找不到 license 字段")
    _wr(dst, rel, t2)


def mutate_apache_copy_remove(dst):
    """删掉 Apache-2.0 许可副本 —— 违反 Apache-2.0 §4(a) 的再分发要求。"""
    p = os.path.join(dst, "licenses", "Apache-2.0-markdown-mermaid-writing.txt")
    if not os.path.exists(p):
        raise RuntimeError("变异无效：Apache-2.0 许可副本不存在")
    os.remove(p)


def mutate_orphan_license_copy(dst):
    """塞一份 NOTICES 没引用的许可副本 —— 有许可义务却没交代。"""
    p = os.path.join(dst, "licenses", "Apache-2.0-orphan.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write("Apache License\nVersion 2.0\n" + ("x" * 6000))


def mutate_readme_all_mit_claim(dst):
    """README 谎称整个仓库都是 MIT —— 实际有 1 个 Apache-2.0 技能。

    🔴 这条变异同时验证守卫**能分辨断言与否定**：
    README 里本来就有"不是『全仓 MIT』"的如实交代，那句不能被误报；
    但这里注入的**肯定句**必须被抓到。
    """
    t = _rd(dst, "README.md")
    t2 = t.replace("## 开源与许可",
                    "## 开源与许可\n\n本仓库全部内容为 MIT 许可。", 1)
    if t2 == t:
        raise RuntimeError("变异无效：README 里找不到『## 开源与许可』")
    _wr(dst, "README.md", t2)


def mutate_hardcoded_path(dst):
    # 注入的路径字面量必须**拼接**出来，否则本文件自身会被 verify_repo
    # 的「无硬编码绝对路径」检查判为不合格（守卫不该给测试夹具开豁免）。
    injected = "/ho" + "me/lc" + "003/x"
    with open(os.path.join(dst, "agent.md"), "a", encoding="utf-8") as f:
        f.write("\n\n<!-- 注入：" + injected + " -->\n")


def mutate_secret(dst):
    rel = os.path.join("references", "rejected-skills.md")
    t = _rd(dst, rel)
    _wr(dst, rel, t + "\n\nsk-" + "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6" + "\n")


def mutate_extra_skill(dst):
    d = os.path.join(dst, "skills", "zzz-fake-skill")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: zzz-fake-skill\ndescription: fake\n---\n")


def mutate_bom(dst):
    p = os.path.join(dst, "README.md")
    with open(p, "rb") as f:
        data = f.read()
    with open(p, "wb") as f:
        f.write(b"\xef\xbb\xbf" + data)


def mutate_typo_author(dst):
    t = _rd(dst, "NOTICE.md")
    _wr(dst, "NOTICE.md", t.replace("Gareth Manning", "Gartner Manning"))


def mutate_notices_drop(dst):
    """从 NOTICES 的清单里抹掉一个技能。

    🔴 必须**两处都删**：§1 的 50 技能名单里有一行，
       §3 的「自有原创部分」里还有一行 `skills/<name>/`。
    只删第 1 处 → 技能仍然出现在 §3 → 守卫照不到 → 这个变异变成空操作
    （测试看起来跑了，实际什么都没测出来）。
    """
    t = _rd(dst, "THIRD-PARTY-NOTICES.md")
    before = t
    t = re.sub(r"(?m)^[ \t]*udl-lesson-auditor[ \t]*\r?\n", "", t)
    t = re.sub(r"(?m)^[ \t]*skills/udl-lesson-auditor/[ \t]*\r?\n", "", t)
    if t == before:
        raise RuntimeError("变异无效：NOTICES 里找不到 udl-lesson-auditor")
    _wr(dst, "THIRD-PARTY-NOTICES.md", t)


def mutate_notices_ghost(dst):
    """NOTICES 里声称一个仓库中并不存在的技能 —— 清单在撒谎。"""
    t = _rd(dst, "THIRD-PARTY-NOTICES.md")
    _wr(dst, "THIRD-PARTY-NOTICES.md",
        t + "\n\n```\nzzz-ghost-skill-not-installed\n```\n")


def mutate_skill_id_back(dst):
    """给已原创化的技能塞回上游 skill_id —— 归属声明被改回去了。"""
    rel = os.path.join("skills", "backwards-design-unit-planner", "SKILL.md")
    t = _rd(dst, rel)
    t = t.replace("license: MIT",
                  "license: MIT\nskill_id: curriculum-assessment/backwards-design-unit-planner",
                  1)
    _wr(dst, rel, t)


def mutate_manifest_stale(dst):
    rel = os.path.join("references", "upstream-candidates.json")
    t = _rd(dst, rel)
    _wr(dst, rel, t.replace('"metacognitive-prompt-library"',
                             '"metacognitive-prompt-library-X"'))


def mutate_own_list_drift(dst):
    t = _rd(dst, "LICENSE")
    _wr(dst, "LICENSE", t.replace("scripts/verify_repo.py\n", ""))


def mutate_matrix_domain_drift(dst):
    rel = os.path.join("references", "faculty-capability-matrix.md")
    t = _rd(dst, rel)
    injected = "C:" + "\\U" + "sers\\someuser\\.minimax"
    # 追加一行，而不是替换 —— 替换目标串可能在该文件里不存在，
    # 那样这个变异就是空操作，测不出任何东西（曾踩过）。
    t = t.rstrip() + "\n\n适配表路径：`" + injected + "\\skills\\x`\n"
    _wr(dst, rel, t)


def mutate_dot_to_circle(dst):
    """把一个 ● 已装技能误标成 ○ 候选 —— 标记过期。"""
    rel = os.path.join("references", "faculty-capability-matrix.md")
    t = _rd(dst, rel)
    t = t.replace("●backwards-design-unit-planner", "○backwards-design-unit-planner", 1)
    _wr(dst, rel, t)


def mutate_drop_mark(dst):
    """漏加 ● 标记 —— 回到"无标记 = 已装"的隐式约定。"""
    rel = os.path.join("references", "faculty-capability-matrix.md")
    t = _rd(dst, rel)
    t = t.replace("●scope-and-sequence-designer", "scope-and-sequence-designer", 1)
    _wr(dst, rel, t)


def mutate_nc_skill_back(dst):
    """把 NC 技能放回 skills/ —— 商业可用性被破坏。"""
    src = os.path.join(dst, "skills-archive", "deep-research")
    if not os.path.isdir(src):
        # 归档不存在时，用一份最小 SKILL.md 造一个同名的（仍应被守卫拦下）
        d = os.path.join(dst, "skills", "deep-research")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: deep-research\ndescription: fake\n"
                    "metadata:\n  status: active\n---\n")
        return
    import shutil as _sh
    _sh.copytree(src, os.path.join(dst, "skills", "deep-research"))


def mutate_nc_license_back(dst):
    """把 NC 许可全文放回 licenses/ —— 分发物里出现 NC 材料。"""
    import shutil as _sh
    cand = os.path.join(dst, "skills-archive", "licenses",
                        "CC-BY-NC-4.0-academic-research-skills.txt")
    dstf = os.path.join(dst, "licenses",
                        "CC-BY-NC-4.0-academic-research-skills.txt")
    if os.path.exists(cand):
        _sh.copyfile(cand, dstf)
    else:
        with open(dstf, "w", encoding="utf-8") as f:
            f.write("CC BY-NC 4.0 fake license text\n" * 40)


def mutate_readme_ghost_license(dst):
    """README 目录树里列出一份已移出仓库的许可副本 —— 文档在撒谎。

    🔴 目录树的连接符是 `├──` 还是 `└──` 取决于它在列表里的位置，
    写死一种就会在文档调整后变成**空操作**。这里用正则匹配两种。
    """
    t = _rd(dst, "README.md")
    t2 = re.sub(r"(│\s*[├└]──\s*MIT-K-Dense\.txt)",
                r"\1\n│   └── CC-BY-NC-4.0-academic-research-skills.txt",
                t, count=1)
    if t2 == t:
        raise RuntimeError("变异无效：README 目录树里找不到 MIT-K-Dense.txt")
    _wr(dst, "README.md", t2)


def mutate_matrix_partial_no_skill(dst):
    """「部分覆盖」格既无 ● 也无 ◐ —— 应当判为空覆盖。

    这条针对守卫的语义细化：部分覆盖**允许**只有 ◐（外部技能），
    但一个技能都不列就是在编。

    ⚠️ 锚点选 **A5**（教材遴选，仍是「部分覆盖」），不能用 E2 ——
    论文线回仓后 E2/E4/E5/E9 已改成「已覆盖」，锚在它上面会变成空变异。
    """
    rel = os.path.join("references", "faculty-capability-matrix.md")
    t = _rd(dst, rel)
    old = ("| A5 教材与参考书遴选 | 能基于课程目标选配套教材并给真实书目 | "
           "●teaching-file-builder（ISBN 不得编造规则） | "
           "部分覆盖（无检索工具，需人工/外部补充） |")
    new = ("| A5 教材与参考书遴选 | 能基于课程目标选配套教材并给真实书目 | — | "
           "部分覆盖（无检索工具，需人工/外部补充） |")
    if old not in t:
        raise RuntimeError("变异无效：矩阵里找不到 A5 那一行的原文")
    _wr(dst, rel, t.replace(old, new, 1))


def mutate_matrix_unregistered_external(dst):
    """矩阵里写一个没登记在 external-skills.json 的 ◐ 技能 —— 应当报"未登记"。

    ◐ 原本是自由文本，谁都能写个名字当"外部技能"。收成受控词表后，
    编造的名字会被机械抓到。
    """
    rel = os.path.join("references", "faculty-capability-matrix.md")
    t = _rd(dst, rel)
    old = "◐empirical-lint（功效/样本量/MDE）"
    new = "◐zzz-fake-external-skill（功效/样本量/MDE）"
    if old not in t:
        raise RuntimeError("变异无效：矩阵里找不到 ◐empirical-lint")
    _wr(dst, rel, t.replace(old, new, 1))


def mutate_readme_stale_selfcount(dst):
    """README「验证」章节里把守卫自己的检查数写成旧值 —— 守卫加了检查但 README 没跟。"""
    t = _rd(dst, "README.md")
    t2 = re.sub(r"verify_repo:\s*\d+/\d+\s*checks passed",
                "verify_repo: 52/52 checks passed", t, count=1)
    if t2 == t:
        raise RuntimeError("变异无效：README 里找不到 verify_repo 的检查数")
    _wr(dst, "README.md", t2)


def mutate_readme_selfcount_numerator(dst):
    """README 里 verify_repo 的分子写错（999/99）—— 只比分母的守卫会漏掉这种。

    🔴 分子必须写成**不可能恰好等于实际值**的数。
       上一版写死「99」：README 当时的实际值正好是 99 ⇒ 替换后文本没变 ⇒
       变异自己被判「无效」，整轮白跑一次 —— 变异测试里最贵的一种浪费：
       **以为验过了，其实什么都没验。**
    """
    t = _rd(dst, "README.md")
    t2 = re.sub(r"verify_repo:\s*\d+/(\d+)\s*checks passed",
                lambda m: "verify_repo: 999/%s checks passed" % m.group(1), t, count=1)
    if t2 == t:
        raise RuntimeError("变异无效：README 里找不到 verify_repo 的检查数")
    _wr(dst, "README.md", t2)


def mutate_readme_rewrite_count(dst):
    """README 里 verify_rewrite 的检查数写成「有上游」口径的数字。

    🔴 verify_rewrite 的检查数**取决于上游原文目录在不在**：
    带上游会多跑 clean-room 相似度核对。而**上游仓库不随本仓库分发** ——
    克隆方默认没有上游，README 却写着自己手边有上游时的数字 ⇒ 读者实跑对不上，
    却完全不知道差在哪（写文档的人和跑文档的人不是同一个环境）。
    """
    t = _rd(dst, "README.md")
    t2 = re.sub(r"verify_rewrite:\s*\d+/\d+\s*checks passed",
                "verify_rewrite: 716/716 checks passed", t, count=1)
    if t2 == t:
        raise RuntimeError("变异无效：README 里找不到 verify_rewrite 的检查数")
    _wr(dst, "README.md", t2)


def mutate_openmaic_runtime_tool(dst):
    """在 OpenMAIC 衍生技能里写入上游的运行时工具名 —— 悬空引用。

    🔴 这条针对一个具体的失败模式：OpenMAIC 的 22 个技能正文绑死
    `create_stage` / `generate_scene` 等运行时工具。本仓库没有 OpenMAIC 运行时，
    整份复制那些 SKILL.md 进来只会得到一堆执行不了的调用。
    """
    rel = os.path.join("skills", "feynman-diagnostic-cycle", "SKILL.md")
    t = _rd(dst, rel)
    t2 = t.replace("## 执行步骤",
                    "## 执行步骤\n\n用 create_stage 建课，用 generate_scene 逐页生成。", 1)
    if t2 == t:
        raise RuntimeError("变异无效：找不到『## 执行步骤』")
    _wr(dst, rel, t2)


def mutate_openmaic_license_copy_remove(dst):
    """删掉 OpenMAIC 的 MIT 许可副本 —— MIT 要求保留版权声明与许可声明。"""
    p = os.path.join(dst, "licenses", "OpenMAIC-MIT.txt")
    if not os.path.exists(p):
        raise RuntimeError("变异无效：OpenMAIC 许可副本不存在")
    os.remove(p)


def mutate_openmaic_attribution_drop(dst):
    """把 NOTICES 里的 THU-MAIC 署名抹掉 —— 有 MIT 义务却没交代。"""
    rel = "THIRD-PARTY-NOTICES.md"
    t = _rd(dst, rel)
    t2 = t.replace("THU-MAIC", "某上游")
    if t2 == t:
        raise RuntimeError("变异无效：NOTICES 里找不到 THU-MAIC")
    _wr(dst, rel, t2)


def mutate_openmaic_skill_id_back(dst):
    """给 OpenMAIC 衍生技能塞上游 skill_id —— 归属声明互相矛盾。"""
    rel = os.path.join("skills", "authentic-context-course-designer", "SKILL.md")
    t = _rd(dst, rel)
    t2 = t.replace("license: MIT",
                   "license: MIT\nskill_id: curriculum-alignment/authentic-context-course-designer",
                   1)
    if t2 == t:
        raise RuntimeError("变异无效：找不到 license 字段")
    _wr(dst, rel, t2)


def mutate_domain_uncontrolled(dst):
    """给技能的 metadata.domain 塞一个受控词表外的值 —— 域字段失守。"""
    rel = os.path.join("skills", "feynman-diagnostic-cycle", "SKILL.md")
    t = _rd(dst, rel)
    t2 = t.replace("domain: 记忆与学习科学", "domain: 记忆与学习", 1)
    if t2 == t:
        raise RuntimeError("变异无效：找不到 domain 字段")
    _wr(dst, rel, t2)


# ── 分档出包相关 ─────────────────────────────────────────────────
# 🔴 为什么必须有这一组：分档包（teaching / research）的技能集合是
#    **从能力矩阵推导**出来的。推导链一旦与仓库现实脱节，就会静默地
#    打出「与仓库宣称不符」的包 —— 而包一旦发出去，收件人拿到的是那个版本。
#    所以守卫与出包器两条闸门都必须**证明会红**。
def _rw_json(dst, rel, fn):
    p = os.path.join(dst, rel)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    fn(data)
    with open(p, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def mutate_matrix_drop_assignment(dst):
    """把某个已装技能从能力矩阵里摘掉。

    后果：它在 teaching 与 research **两档里同时消失**，
    而 full 档里还在 —— 三档不再自洽。
    """
    rel = os.path.join("references", "faculty-capability-matrix.md")
    t = _rd(dst, rel)
    t2 = t.replace("●competency-unpacker, ", "", 1)
    if t2 == t:
        raise RuntimeError("变异无效：矩阵里找不到 ●competency-unpacker")
    _wr(dst, rel, t2)


def mutate_profiles_drop_domain(dst):
    """把 teaching 档的一个能力域删掉 —— 该域的技能在两个分档里都会蒸发。"""
    def fix(data):
        data["profiles"]["teaching"]["domains"] = [
            d for d in data["profiles"]["teaching"]["domains"] if d != "F"]
    _rw_json(dst, os.path.join("references", "profiles.json"), fix)


def mutate_profiles_drop_research(dst):
    """把整个 research 档删掉 —— 三档结构被破坏。"""
    def fix(data):
        del data["profiles"]["research"]
    _rw_json(dst, os.path.join("references", "profiles.json"), fix)


def mutate_openmaic_license_copy_gone(dst):
    """删掉 OpenMAIC 的 MIT 许可副本 —— 分档包里带 OpenMAIC 技能却无署名依据。"""
    p = os.path.join(dst, "licenses", "OpenMAIC-MIT.txt")
    if not os.path.exists(p):
        raise RuntimeError("变异无效：OpenMAIC 许可副本不存在")
    os.remove(p)


# ── verify_rewrite.py 的变异 ─────────────────────────────────
# 🔴 为什么单独一组：verify_rewrite.py 之前只查改写清单里的 50 个技能，
#    本项目自己新写的技能全是校验盲区（结构不合规、交叉引用悬空都没人管）。
#    新增了「全仓交叉引用校验」与「教学模板技能」判定后，
#    这两条新判据必须证明会红 —— 否则它们只是看起来在工作。
def mutate_rewrite_dangling_ref(dst):
    """让一个技能指向根本不存在的技能名。"""
    rel = os.path.join("skills", "authentic-context-course-designer", "SKILL.md")
    t = _rd(dst, rel)
    t2 = t.replace("## 交叉技能",
                    "## 交叉技能\n\n- 关联 → `zzz-not-a-real-skill`", 1)
    if t2 == t:
        raise RuntimeError("变异无效：找不到『## 交叉技能』")
    _wr(dst, rel, t2)


def mutate_rewrite_missing_section(dst):
    """把标准章节改个名字 —— 结构模板不再满足。"""
    rel = os.path.join("skills", "feynman-diagnostic-cycle", "SKILL.md")
    t = _rd(dst, rel)
    t2 = t.replace("## 易错点", "## 常见错误", 1)
    if t2 == t:
        raise RuntimeError("变异无效：找不到『## 易错点』")
    _wr(dst, rel, t2)


def mutate_rewrite_license_not_mit(dst):
    """把技能的 license 改成非 MIT —— 结构校验必须拦下。"""
    rel = os.path.join("skills", "vocational-task-course", "SKILL.md")
    t = _rd(dst, rel)
    t2 = t.replace("license: MIT", "license: Apache-2.0", 1)
    if t2 == t:
        raise RuntimeError("变异无效：找不到 license 字段")
    _wr(dst, rel, t2)


def mutate_pptx_temp_leak(dst):
    """把 PPTX 自检的临时目录清理去掉 —— 守卫必须抓到 TEMP 泄漏。"""
    rel = os.path.join("skills", "teaching-slide-designer", "scripts",
                       "build_pptx.py")
    t = _rd(dst, rel)
    old = ("    try:\n"
           "        return _selftest_in(tmp)\n"
           "    finally:\n"
           "        shutil.rmtree(tmp, ignore_errors=True)\n")
    if old not in t:
        raise RuntimeError("变异无效：build_pptx.py 里找不到 selftest 的清理块")
    _wr(dst, rel, t.replace(old, "    return _selftest_in(tmp)\n", 1))


def mutate_lesson_plan_handedit(dst):
    """有人绕过大纲，直接手改了教案示例 —— 唯一事实源守卫必须抓到。

    这是"大纲先行层"要根治的那个真实失败模式：改了教案忘了改课件。
    """
    rel = "demo/spec/lesson_plan.example.json"
    spec = json.loads(_rd(dst, rel))
    spec["objectives"].append({
        "id": "O5",
        "text": "能评价直方图均衡化在医学影像中的适用边界",
        "evidence": "课堂讨论中给出适用边界判断",
        "course_objective": "CO-4",
    })
    _wr(dst, rel, json.dumps(spec, ensure_ascii=False, indent=2) + "\n")


def mutate_outline_deriver_slip(dst):
    """派生器悄悄少派生一个字段（溯源没了）—— 守卫必须抓到。"""
    rel = "demo/outline.py"
    t = _rd(dst, rel)
    old = ('                "module": m.get("id", ""),\n'
           '                "module_title": m.get("title", ""),\n')
    if old not in t:
        raise RuntimeError("变异无效：outline.py 里找不到 module 溯源字段")
    _wr(dst, rel, t.replace(old, "", 1))


def mutate_run_demo_no_outline_artifact(dst):
    """Demo 不再落盘大纲凭据 —— 说明大纲层被绕过了，守卫必须抓到。"""
    rel = "demo/run_demo.py"
    t = _rd(dst, rel)
    old = ('        write_text(os.path.join(out_dir, "outline.spec.json"),\n'
           '                   json.dumps(outline, ensure_ascii=False, indent=2))\n')
    if old not in t:
        raise RuntimeError("变异无效：run_demo.py 里找不到大纲凭据的落盘语句")
    _wr(dst, rel, t.replace(old, "        pass  # 变异：不再落盘大纲凭据\n", 1))


def mutate_slide_layouts_table(dst):
    """把文字高度表改得不自洽（2 行比公式要求矮）—— 版式表自检必须抓到。

    🔴 用正则定位而不是写死整行：表里的数值会随行高系数调整，
       写死字符串的锚点**一改就过期**，而过期的锚点会让这个变异
       抛"变异无效"、把整轮 47 项一起带崩。
    """
    rel = os.path.join("skills", "teaching-slide-designer", "scripts",
                       "slide_layouts.py")
    t = _rd(dst, rel)
    m = re.search(r"^    24: \{1: (\d+), 2: (\d+)(.*)$", t, re.M)
    if not m:
        raise RuntimeError("变异无效：slide_layouts.py 里找不到 24pt 的高度表行")
    one = int(m.group(1))
    # 2 行的高度改到比 1 行还矮 ⇒ 同时破坏"逐格等于 ceil(字号×1.35×行数)"
    new = "    24: {1: %d, 2: %d%s" % (one, one - 3, m.group(3))
    _wr(dst, rel, t[:m.start()] + new + t[m.end():])


def mutate_demo_no_handout(dst):
    """Demo 不再产出讲义 —— 「讲稿与课件同源」这件事就没人守了。"""
    rel = "demo/run_demo.py"
    t = _rd(dst, rel)
    old = '    if "handout" in specs:\n        p = os.path.join(out_dir, "讲义.md")'
    if old not in t:
        raise RuntimeError("变异无效：run_demo.py 里找不到讲义的渲染分支")
    _wr(dst, rel, t.replace(
        old, '    if False and "handout" in specs:\n'
             '        p = os.path.join(out_dir, "讲义.md")', 1))


def mutate_selftest_drop_ubd_case(dst):
    """变异测试里删掉 UbD 的变异用例 —— 「判据会红」这件事没人证明了。

    🔴 这条针对的失败模式很隐蔽：判据**还在** selfcheck.py 里，
       但**没有任何变异用例证明它会红** ⇒ 判据可能早就空转了，
       而所有检查都绿。

    🔴 必须把 `, "OL-P15"` **所有**出现处都抹掉。
       上一版只替换了**第一处** —— 而 selftest.py 里有两个用例都返回 "OL-P15"
       （缺 UbD 骨架 / 持久理解写成知识点）。守卫查的是「这个规则码在不在文件里」，
       剩下一处就照样找到 ⇒ 守卫没红，而变异其实什么都没删干净。
       ⇒ **局部替换冒充全局替换**：改判据时最容易踩的一个坑。
    """
    rel = "demo/selftest.py"
    t = _rd(dst, rel)
    old = ', "OL-P15"'
    n = t.count(old)
    if n == 0:
        raise RuntimeError("变异无效：selftest.py 里找不到 OL-P15 的用例")
    _wr(dst, rel, t.replace(old, ', "OL-P99"'))


def mutate_regen_leaks_to_sibling(dst):
    """增量替换漏到邻页 —— 「只重跑一页」的承诺破了。

    🔴 泄漏必须**与重跑的是哪一页无关**。
       上一版把泄漏写在「内容页分支」里、且只改「同环节的下一页」：
       守卫当时挑中的目标是封面页（deck 分支）⇒ 压根走不到那段代码，
       泄漏从未发生 ⇒ 守卫绿着，而「只动一页」这条承诺早就破了。
       ⇒ **变异的作用域要覆盖被测判据的全部输入空间**，不能只押一种。
    """
    rel = "demo/outline.py"
    t = _rd(dst, rel)
    old = "    new_out = copy.deepcopy(outline)"
    if old not in t:
        raise RuntimeError("变异无效：outline.py 里找不到 replace_page 的拷贝行")
    new = old + (
        "\n    # 变异：不管重跑的是哪一页，都偷偷改掉**另一页**\n"
        "    _leaked = []\n"
        "    for _mm in new_out.get('modules') or []:\n"
        "        for _ss in _mm.get('steps') or []:\n"
        "            for _pp in (_ss.get('slides') or []):\n"
        "                if _pp.get('id') != page_id:\n"
        "                    _leaked.append(_pp)\n"
        "                    break\n"
        "            if _leaked:\n"
        "                break\n"
        "        if _leaked:\n"
        "            break\n"
        "    if _leaked:\n"
        "        _leaked[0]['title'] = '被误改的邻页'\n")
    _wr(dst, rel, t.replace(old, new, 1))


def mutate_llm_drop_lint_purpose(dst):
    """模型路由里删掉 lint 用途 —— 四档变三档。"""
    rel = "demo/llm.py"
    t = _rd(dst, rel)
    old = 'PURPOSES = ("plan", "slides", "handout", "lint")'
    if old not in t:
        raise RuntimeError("变异无效：llm.py 里找不到 PURPOSES 定义")
    _wr(dst, rel, t.replace(old, 'PURPOSES = ("plan", "slides", "handout")', 1))


def mutate_github_drop_ci(dst):
    """GitHub 骨架件被删 —— 这份仓库就发不出去了（开源性会悄悄烂掉）。"""
    rel = os.path.join(".github", "workflows", "ci.yml")
    p = os.path.join(dst, rel)
    if not os.path.isfile(p):
        raise RuntimeError("变异无效：%s 不存在" % rel)
    os.remove(p)


def mutate_ci_stops_running_gates(dst):
    """CI 不再跑本仓库的判据 —— workflow 还在，但它是**空的**。

    🔴 这条针对的失败模式很阴：CI 还在、badge 还在绿的，
       但它跑的不再是本仓库的判据 ⇒ 任何东西变坏都不会让 CI 变红。
    """
    rel = os.path.join(".github", "workflows", "ci.yml")
    t = _rd(dst, rel)
    old = "python scripts/verify_repo.py"
    if old not in t:
        raise RuntimeError("变异无效：ci.yml 里找不到守卫的调用")
    _wr(dst, rel, t.replace(old, "echo 'skipped'", 1))


def mutate_github_config_broken(dst):
    """发布配置被写坏（topics 清空）—— 发布说明与仓库元数据会变成空的。"""
    rel = os.path.join("references", "github-release.json")
    t = _rd(dst, rel)
    try:
        cfg = json.loads(t)
    except Exception as e:
        raise RuntimeError("变异无效：github-release.json 解析不了：%s" % e)
    cfg["topics"] = []
    _wr(dst, rel, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")


def mutate_changelog_drops_version(dst):
    """CHANGELOG 少了当前版本的条目 —— 发布的说明里就没有本版内容。"""
    t = _rd(dst, "CHANGELOG.md")
    old = "## [1.0.0]"
    if old not in t:
        raise RuntimeError("变异无效：CHANGELOG.md 里找不到 1.0.0 的条目")
    _wr(dst, "CHANGELOG.md", t.replace(old, "## [0.9.0]", 1))


MUTATIONS = [
    # (说明, 变异函数, 预期被触发的检查名关键词)
    ("README 格数改回 45", mutate_readme_grid, "格数"),
    ("README 目录树列出已移出的 NC 许可", mutate_readme_ghost_license, "许可副本清单"),
    ("README 写错守卫检查数（整对过期）", mutate_readme_stale_selfcount, "verify_repo 检查数"),
    ("README 守卫检查数分子写错", mutate_readme_selfcount_numerator, "verify_repo 检查数"),
    ("README 写错 verify_rewrite 检查数（口径错）", mutate_readme_rewrite_count,
     "verify_rewrite 检查数"),
    ("矩阵把空覆盖格标成已覆盖", mutate_matrix_empty, "已装技能"),
    ("部分覆盖格既无 ● 也无 ◐", mutate_matrix_partial_no_skill, "既无"),
    ("矩阵 ◐ 技能未登记在外部技能表", mutate_matrix_unregistered_external,
     "external-skills.json 登记"),
    ("重命名一份许可副本", mutate_license_rename, "许可副本"),
    ("注入硬编码绝对路径", mutate_hardcoded_path, "硬编码"),
    ("注入伪密钥", mutate_secret, "密钥"),
    ("多塞一个技能目录", mutate_extra_skill, "技能总数"),
    ("给 README 加 BOM", mutate_bom, "UTF-8"),
    ("作者名拼错", mutate_typo_author, "Gareth"),
    ("NOTICES 漏列一个技能", mutate_notices_drop, "NOTICES 覆盖全部已装技能"),
    ("NOTICES 列了不存在的技能", mutate_notices_ghost, "不存在的技能"),
    ("原创技能被塞回上游 skill_id", mutate_skill_id_back, "全部已原创化"),
    ("候选清单条目与矩阵脱节", mutate_manifest_stale, "登记"),
    ("LICENSE 自有清单漂移", mutate_own_list_drift, "自有清单一致"),
    ("矩阵里写回绝对路径", mutate_matrix_domain_drift, "硬编码"),
    ("● 误标成 ○（标记过期）", mutate_dot_to_circle, "标记没过期"),
    ("漏加 ● 标记", mutate_drop_mark, "都带标记"),
    ("NC 技能放回 skills/", mutate_nc_skill_back, "NonCommercial"),
    ("NC 许可全文放回 licenses/", mutate_nc_license_back, "NC 家族许可全文"),
    ("技能漏声明 license", mutate_license_field_drop, "都声明 license"),
    ("Apache-2.0 许可副本被删", mutate_apache_copy_remove,
     "Apache-2.0 技能有对应的许可副本"),
    ("塞入孤儿许可副本", mutate_orphan_license_copy, "每份副本都被 NOTICES 引用"),
    ("README 谎称全仓 MIT", mutate_readme_all_mit_claim, "许可表述"),
    ("OpenMAIC 衍生技能夹带运行时工具名", mutate_openmaic_runtime_tool,
     "运行时工具悬空引用"),
    ("OpenMAIC 许可副本被删", mutate_openmaic_license_copy_remove,
     "OpenMAIC 的 MIT 许可副本"),
    ("NOTICES 抹掉 THU-MAIC 署名", mutate_openmaic_attribution_drop,
     "THU-MAIC 署名"),
    ("OpenMAIC 衍生技能被塞回上游 skill_id", mutate_openmaic_skill_id_back,
     "无上游 skill_id 溯源字段"),
    ("metadata.domain 塞词表外的值", mutate_domain_uncontrolled,
     "受控词表内"),
    ("矩阵里摘掉一个已装技能的归属", mutate_matrix_drop_assignment, "归属"),
    ("档位定义删掉一个能力域", mutate_profiles_drop_domain, "恒等式"),
    ("档位定义删掉整个 research 档", mutate_profiles_drop_research, "三档"),
    ("PPTX 自检不再清理临时目录", mutate_pptx_temp_leak, "不遗留临时目录"),
    ("绕过大纲手改教案示例", mutate_lesson_plan_handedit, "唯一事实源"),
    ("派生器悄悄漏掉溯源字段", mutate_outline_deriver_slip, "唯一事实源"),
    ("Demo 不再落盘大纲凭据", mutate_run_demo_no_outline_artifact,
     "离线 Demo 走大纲层"),
    ("文字高度表被改得不自洽", mutate_slide_layouts_table, "版式原型表自检通过"),
    ("Demo 不再产出讲义", mutate_demo_no_handout, "产出讲义"),
    ("变异测试漏掉 UbD 的用例", mutate_selftest_drop_ubd_case, "判据变异测试覆盖"),
    ("增量重生成漏到邻页", mutate_regen_leaks_to_sibling, "增量重生成只动一页"),
    ("模型路由删掉 lint 用途", mutate_llm_drop_lint_purpose, "模型按用途路由"),
    ("GitHub 骨架件被删", mutate_github_drop_ci, "GitHub 开源件齐全"),
    ("CI 不再跑本仓库的判据", mutate_ci_stops_running_gates, "CI 真的跑本仓库的判据"),
    ("发布配置被写坏", mutate_github_config_broken, "GitHub 发布配置完整"),
    ("CHANGELOG 少了当前版本", mutate_changelog_drops_version, "CHANGELOG 覆盖当前版本"),
]

# 🔴 出包器自己也必须"证明会红"：分档包一旦打出来就收不回去了。
#    守卫红了但出包器照样出包，等于闸门只装了一半。
MUTATIONS_PACKAGE = [
    ("矩阵归属漂移 → 必须中止出包", mutate_matrix_drop_assignment, "未归类"),
    ("档位域被删 → 必须中止出包", mutate_profiles_drop_domain, "full_only_skills"),
    ("包内缺许可副本 → 必须中止出包", mutate_openmaic_license_copy_gone, "许可副本"),
]

MUTATIONS_REWRITE = [
    # (说明, 变异函数, 预期被触发的检查名关键词)
    ("交叉技能指向不存在的技能", mutate_rewrite_dangling_ref,
     "交叉技能指向真实存在的技能"),
    ("标准章节被改名", mutate_rewrite_missing_section, "标准章节齐全"),
    ("license 改成非 MIT", mutate_rewrite_license_not_mit, "license 标 MIT"),
]


def copy_repo(dst):
    # dist/ 里是几个 MB 的压缩包，与被测逻辑无关 —— 复制它只是让每个变异慢一拍。
    shutil.copytree(ROOT, dst,
                    ignore=shutil.ignore_patterns(".git", "__pycache__",
                                                  ".cache", "dist"))


def _pptx_temp_dirs():
    """TEMP 里 PPTX 自检留下的临时目录名集合。"""
    t = tempfile.gettempdir()
    try:
        return set(n for n in os.listdir(t) if n.startswith("jfa_pptx_"))
    except OSError:
        return set()


def _cleanup_pptx_temp(before):
    """把**本轮新增**的 jfa_pptx_* 目录清掉（只清新增的，不动别人的）。

    🔴 变异「PPTX 自检不再清理临时目录」**故意**破坏清理逻辑，
       那一次运行会在**真实 TEMP** 里留下一个 jfa_pptx_* 目录。
       守卫有一条「自研 PPTX 自检不遗留临时目录」—— 而**变异测试自己**
       每跑一轮就漏一个目录，等于测试框架在违反它自己守的规矩。
       ⇒ 跑完一轮，把本轮新增的收干净。
    """
    for n in _pptx_temp_dirs() - before:
        shutil.rmtree(os.path.join(tempfile.gettempdir(), n), ignore_errors=True)


def run_suite(title, mutations, script, baseline_label, extra=None):
    """跑一组变异：基线必须绿，每个错误都必须让被测脚本在预期检查项上变红。

    🔴 外面套一层 finally：把本轮新增的 jfa_pptx_* 临时目录收干净
       （有一个变异**故意**破坏清理逻辑，见 `_cleanup_pptx_temp`）。
    """
    before = _pptx_temp_dirs()
    try:
        return _run_suite(title, mutations, script, baseline_label, extra)
    finally:
        _cleanup_pptx_temp(before)


def _run_suite(title, mutations, script, baseline_label, extra=None):
    print("=== %s ===" % title)
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "base")
        copy_repo(base)
        rc, out = run(base, script, extra)
        print("  %s: exit=%d" % (baseline_label, rc))
        if rc != 0:
            print(out)
            print("  !! 基线就不绿，后续变异测试无意义")
            return 1, ["基线不绿"], []

    print()
    print("  --- 变异：每个错误都必须让 %s 在预期检查项上变红 ---" % script)
    missed = []
    wrong = []
    for label, fn, expect in mutations:
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "mut")
            copy_repo(dst)
            # 🔴 **变异自己坏了（锚点过期等）不能带崩整轮**。
            #    抛异常会让这 47 项的结果全丢 —— 一次手滑 = 整轮白跑。
            #    这里把它记成"这一项没验成"，继续跑其余的。
            try:
                fn(dst)
            except Exception as e:
                missed.append("%s（变异无效：%s）" % (label, e))
                print("  !! 变异无效  %s（%s）" % (label, e))
                continue
            rc, out = run(dst, script, extra)
            caught = rc != 0
            on_target = expect in out
            if not caught:
                status = "!! 漏检"
                missed.append(label)
            elif not on_target:
                status = "!! 红在别处（预期命中 '%s'）" % expect
                wrong.append(label)
            else:
                status = "抓到 OK"
            print("  %-34s exit=%d  %s" % (label, rc, status))
            if caught:
                # 打印**全部**失败项：只打首个会掩盖信号
                for ln in out.splitlines():
                    if ln.startswith("FAIL"):
                        print("       " + ln.strip()[:120])
    print()
    return (1 if (missed or wrong) else 0), missed, wrong


def main():
    total = 0
    bad = 0

    rc, missed, wrong = run_suite(
        "verify_repo.py：文档 ↔ 现实一致性", MUTATIONS,
        "scripts/verify_repo.py", "基线")
    total += len(MUTATIONS)
    bad += rc
    if missed:
        print("漏检 %d 项: %s" % (len(missed), "; ".join(missed)))
    if wrong:
        print("红错位置 %d 项: %s" % (len(wrong), "; ".join(wrong)))

    rc, missed, wrong = run_suite(
        "verify_rewrite.py：结构合规 + 全仓交叉引用", MUTATIONS_REWRITE,
        "scripts/verify_rewrite.py", "基线")
    total += len(MUTATIONS_REWRITE)
    bad += rc
    if missed:
        print("漏检 %d 项: %s" % (len(missed), "; ".join(missed)))
    if wrong:
        print("红错位置 %d 项: %s" % (len(wrong), "; ".join(wrong)))

    rc, missed, wrong = run_suite(
        "package_release.py：分档出包必须拒绝来路不明的包", MUTATIONS_PACKAGE,
        "scripts/package_release.py", "基线",
        extra=["--build", "--profile", "teaching"])
    total += len(MUTATIONS_PACKAGE)
    bad += rc
    if missed:
        print("漏检 %d 项: %s" % (len(missed), "; ".join(missed)))
    if wrong:
        print("红错位置 %d 项: %s" % (len(wrong), "; ".join(wrong)))

    print()
    if bad:
        print("变异测试未全部通过。")
        return 1
    print("全部 %d 项变异均被守卫在预期检查项上抓到。" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
