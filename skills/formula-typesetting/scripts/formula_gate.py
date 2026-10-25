#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""formula_gate.py —— 生成物的**公式验收闸**（纯标准库，Python 3.9 兼容）

为什么要有闸
------------
「生成物都经过公式校正」这句话，只有配上**可证伪的判据**才算数。
本脚本就是那道判据：给定一份生成物（Markdown / JSON 规格 / PPTX），
回答「里面还有没有没被校正的伪公式」。

🔴 **判据只用 `formula_norm` 的上下文判定（`find_spans`），不用 `scan`。**
   `scan` 走原始正则、没有上下文，会把示意图箭头 `→`、标识符 `course_code`、
   甚至**已经写对的 LaTeX** 里的 `^{2}` 都报成命中。
   实测：`scan` 对 9 段已规范化的 LaTeX 文本报出 3 处误伤，
   `find_spans` 报 0 处。用错判据 ⇒ 闸天天误报 ⇒ 闸等于没有。

四条判据
--------
| 规则 | 级别 | 含义 |
|---|---|---|
| FG-01 | ERROR | 仍有**可自动转写却没转**的伪公式（多半是没接规范化那一步） |
| FG-02 | ERROR | PPTX **正文页**残留 LaTeX 源码字面量（应注入 OMML 真公式） |
| FG-03 | WARN  | 正文里夹的单个裸变量（C 类：机器改不了，人工确认） |
| FG-04 | WARN  | 正文还写着「公式一律写成纯文本」这类与 LaTeX 约定冲突的旧措辞 |

🔴 **PPTX 的备注页（notesSlide）不查 FG-02**：讲稿必须与讲义 Markdown
   **逐字同源**，因此备注页**故意保留 LaTeX 源码**。注入 OMML 后备注页抽出来
   的是 `m:t` 里的内容（`ωd`），与讲义里的 `$\\omega_{d}$` 不是同一串字
   ⇒ 同源判据必红。FG-01 仍然查备注页（伪公式在任何载体里都是问题）。

用法
----
    python formula_gate.py 课件.pptx 讲义-第1次课.md slides.spec.json
    python formula_gate.py --json 课件.pptx      # 机器可读

退出码：0 通过 / 1 有 ERROR / 2 参数错误
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import formula_norm  # noqa: E402
import formula_apply  # noqa: E402

ERROR = "ERROR"
WARN = "WARN"

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


class Finding(object):
    """一条判据结果。字段与仓库其它守卫一致：level / rule / where / message。"""

    def __init__(self, level, rule, where, message):
        self.level = level
        self.rule = rule
        self.where = where
        self.message = message

    def as_dict(self):
        return {"level": self.level, "rule": self.rule, "where": self.where,
                "message": self.message}

    def __repr__(self):
        return "<Finding %s %s %s>" % (self.level, self.rule, self.where)


# LaTeX 字面量：`$…$` 且内容像 LaTeX。
# 🔴 「像不像 LaTeX」**判据不重写一份** —— 用 `formula_norm.looks_like_latex`
#    （注入器与验收闸共用；窄判据会漏掉 `F = -BLi` 这种简单关系式 ⇒
#     正文页显示源码而闸还报「零 ERROR」）。
# 🔴 必须要求「像 LaTeX」，否则 `$50`（价格）、`$100 万`（经费）会误报。
_LATEX_LITERAL = re.compile(r"\$(?!\$)([^$\n]+?)(?<!\$)\$")


def _looks_like_latex(s):
    return formula_norm.looks_like_latex(s)


# ─────────────────────────────────────────────────────────────────
# 文本判据
# ─────────────────────────────────────────────────────────────────
def check_text(text, where="", carrier="text", skip_latex_literal=True,
               inline=True):
    """检查一段文本。返回 Finding 列表。

    `skip_latex_literal` 的默认值是 **True**：LaTeX 源码在 Markdown / JSON 里
    是**正确形态**（排版器负责渲染），只有 PPTX 正文页才不该看到源码。

    `inline` 必须与**规范化时用的模式一致**（字段 `True` / 文档 `False`）——
    否则闸会拿另一种形态去比，判出来的"残留"是假的。
    """
    out = []
    if not isinstance(text, str) or not text.strip():
        return out

    # FG-01：残留伪公式
    # 🔴 **判据 = 「再规范化一次会不会变」**，不是「find_spans 有没有命中」。
    #
    #    为什么不用 find_spans 直接判：它是**行内级**的底层工具，
    #    不认 markdown 的表格行、标题、代码围栏 ——
    #    实测对 `| s⁻¹ |` 这种表格单元会命中「整行（含竖线与反引号）」，
    #    而规范化器按单元格处理、根本不会改它 ⇒ 闸会永远报红，
    #    而那道红谁也修不掉（**红得没有出口的判据等于没有判据**）。
    #
    #    为什么不用 fix_text 直接判：fix_text **不幂等** ——
    #    已规范化的 `$…$` 再过一遍会被套成 `$$…$$`（实测踩过）。
    #
    #    用 `formula_apply.normalize_text` 判，三条同时满足：
    #      ① 与规范化器**同一份代码** ⇒ 判据与行为天然一致；
    #      ② 文档级感知（表格按单元格、标题更严、代码块原样）；
    #      ③ 幂等（已规范化的文本原样返回）。
    new_text, changes = formula_apply.normalize_text(text, inline=inline)
    if new_text != text:
        # 🔴 只报**真的变了**的行。`changes` 里混着「已规范化的公式被重新处理一遍」
        #    的记录（before/after 不同，但输出文字一模一样）——
        #    把它们当残留报出来，报的就不是残留了。
        diff_lines = []
        a = text.split("\n")
        b = new_text.split("\n")
        for i in range(max(len(a), len(b))):
            x = a[i] if i < len(a) else ""
            y = b[i] if i < len(b) else ""
            if x != y:
                diff_lines.append("L%d %r" % (i + 1, x.strip()[:60]))
        hit = "；".join(diff_lines[:3])
        more = " 等 %d 行" % len(diff_lines) if len(diff_lines) > 3 else ""
        out.append(Finding(
            ERROR, "FG-01", where,
            "仍有未校正的伪公式：%s%s —— 这些是可自动转写的，"
            "说明规范化那一步没跑到这个产物上" % (hit, more)))

    # FG-02：LaTeX 源码字面量（只对不该出现 LaTeX 源码的载体查）
    if not skip_latex_literal:
        for m in _LATEX_LITERAL.finditer(text):
            inner = m.group(1)
            if _looks_like_latex(inner):
                out.append(Finding(
                    ERROR, "FG-02", where,
                    "残留 LaTeX 源码字面量 $%s$ —— 这个载体要的是渲染后的结果，"
                    "不是 LaTeX 源码" % inner))
                break

    # FG-03：裸变量（C 类，只报告）
    bare = formula_norm.find_bare_vars(text)
    if bare:
        ctx = "、".join("%r" % b[1] for b in bare[:5])
        more = " 等 %d 处" % len(bare) if len(bare) > 5 else ""
        out.append(Finding(
            WARN, "FG-03", where,
            "正文里有裸变量（%s%s）—— 机器不自动改，请人工确认要不要写成公式" % (ctx, more)))

    # FG-04：与 LaTeX 约定冲突的旧措辞
    conflicts = formula_norm.find_convention_conflicts(text)
    if conflicts:
        out.append(Finding(
            WARN, "FG-04", where,
            "正文仍写着「%s」这类旧约定，与 LaTeX 写法冲突，改完公式要同步改掉"
            % conflicts[0][1]))

    return out


def check_obj(node, where="", skip_keys=None, carrier="json"):
    """检查 JSON 结构里的每个字符串。"""
    out = []
    if skip_keys is None:
        skip_keys = frozenset()

    def walk(n, path, prefix):
        if isinstance(n, dict):
            for k, v in n.items():
                if k in skip_keys:
                    continue
                walk(v, path + [str(k)], prefix)
        elif isinstance(n, list):
            for i, v in enumerate(n):
                walk(v, path + [str(i)], prefix)
        elif isinstance(n, str):
            where = prefix + ("/" + "/".join(path) if path else "")
            out.extend(check_text(n, where, carrier))

    walk(node, [], where)
    return out


# ─────────────────────────────────────────────────────────────────
# PPTX
# ─────────────────────────────────────────────────────────────────
def _pptx_texts(path):
    """读出 pptx 里的文本：[(part 名, 段落文本列表)]。

    🔴 只取 `a:t`（DrawingML 文本 run），**不取 `m:t`** ——
       `m:t` 是 OMML 公式的内容，注入成功后的公式就在那里；
       把 `m:t` 也算进来 ⇒ 注入后的课件仍被判「有伪公式」⇒ 闸永远红。
    """
    out = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for name in sorted(names):
            if not name.endswith(".xml"):
                continue
            if not (name.startswith("ppt/slides/slide")
                    or name.startswith("ppt/notesSlides/notesSlide")):
                continue
            try:
                root = ET.fromstring(z.read(name))
            except ET.ParseError:
                continue
            paras = []
            for p in root.iter("{%s}p" % _A):
                buf = []
                for t in p.iter("{%s}t" % _A):
                    buf.append(t.text or "")
                s = "".join(buf)
                if s.strip():
                    paras.append(s)
            if paras:
                out.append((name, paras))
    return out


def check_pptx(path):
    """检查一份 PPTX：正文页查 FG-01/FG-02，备注页只查 FG-01。"""
    out = []
    if not os.path.isfile(path):
        return [Finding(ERROR, "FG-00", path, "文件不存在")]
    for part, paras in _pptx_texts(path):
        is_notes = part.startswith("ppt/notesSlides/")
        for i, s in enumerate(paras):
            where = "%s#p%d" % (part, i + 1)
            # 🔴 备注页不查 FG-02：讲稿必须与讲义逐字同源，故意的 LaTeX 源码。
            out.extend(check_text(s, where, carrier="pptx",
                                  skip_latex_literal=is_notes))
    return out


# ─────────────────────────────────────────────────────────────────
# 文件分发
# ─────────────────────────────────────────────────────────────────
def check_file(path):
    """按扩展名把文件分给对应的判据。"""
    low = path.lower()
    if low.endswith(".pptx"):
        return check_pptx(path)
    if low.endswith(".json"):
        try:
            with io.open(path, encoding="utf-8") as f:
                obj = json.load(f)
        except ValueError as e:
            return [Finding(ERROR, "FG-00", path, "JSON 解析失败：%s" % e)]
        return check_obj(obj, os.path.basename(path))
    with io.open(path, encoding="utf-8") as f:
        text = f.read()
    # 🔴 Markdown 是**文档**上下文：独立成行的公式保留 `$$…$$`。
    #    闸必须用与规范化时**同一种形态**去比，否则报出来的"残留"是假的。
    return check_text(text, os.path.basename(path), carrier="markdown",
                      inline=False)


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成物的公式验收闸")
    ap.add_argument("paths", nargs="+", help="要检查的文件（.md / .json / .pptx）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    findings = []
    for p in args.paths:
        if not os.path.isfile(p):
            findings.append(Finding(ERROR, "FG-00", p, "文件不存在"))
            continue
        findings.extend(check_file(p))

    errs = [f for f in findings if f.level == ERROR]
    warns = [f for f in findings if f.level == WARN]

    if args.json:
        print(json.dumps([f.as_dict() for f in findings], ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print("  %-5s %-7s %s：%s" % (f.level, f.rule, f.where, f.message))
        print("")
        print("公式验收：ERROR %d ｜ WARN %d" % (len(errs), len(warns)))

    if errs:
        print("❌ 公式验收未通过：%d 项 ERROR" % len(errs))
        return 1
    print("✅ 公式验收通过")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
