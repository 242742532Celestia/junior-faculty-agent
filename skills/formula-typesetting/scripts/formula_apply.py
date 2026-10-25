#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""formula_apply.py —— 把公式规范化**接到生成链路上**（纯标准库，Python 3.9 兼容）

为什么需要它
------------
`formula_norm.py` 是**检测 + 转换引擎**（回答「哪些是伪公式」「该写成什么」）；
本脚本是**接线层**（回答「谁在什么时候必须过一遍」）。

没有接线层，「所有产物都经过公式校正」就只是一句提示词里的话：
模型忘了、老代码路径绕过了、或者某个新载体没接上，伪公式照样出现在交付物里。
本脚本把这件事变成**链路上的一步**。

三条硬约束
----------
① **规范化只在源层做一次**。
   教案 / 讲义 / 课件 / 讲稿因此**必然**是同一份公式 ——
   不是「各自都改一遍、改得一样」，是「只有一份可改」。

② **字段上下文决定行内还是独立成行**。
   讲义 / 课件的字段（标题、要点、讲稿）一律用行内 `$…$`：
   `$$…$$` 是**整块**公式的写法，出现在列表项或表格单元格里会被排版器
   当成块级公式 ⇒ 列表被撑断。独立成行的公式属于**整篇文档**的形态，
   不是字段的形态。

③ **需要人工复核的改动不自动应用**。
   公式里夹中文常量这类机器改不了的（`residual_check` 会标出来），
   宁可停下来报错，也不要改出一个没人看过的公式 —— 那比伪公式更危险，
   因为它看起来像被处理过了。

用法
----
    python formula_apply.py spec.json --out spec.normalized.json --report 对照报告.md

编程接口
--------
    normalize_text(text)          -> (新文本, 变更列表)
    normalize_obj(node)           -> (新对象, 变更列表)
    needs_review(changes)         -> bool
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import formula_norm  # noqa: E402


# 字段名黑名单：这些字段装的是**标识符 / 枚举**，不是散文。
# 🔴 为什么需要它：`formula_norm` 的上下文判定已经很严（`course_code`、
#    `solve_ivp` 这类标识符不会被当成公式），但黑名单是**第二道防线** ——
#    标识符一旦被改写成 `e_{c}` 这样的下标，字段名本身就废了，
#    而且这种错误**不会**被任何"公式残留"判据发现（因为它是合法 LaTeX）。
IDENTIFIER_KEYS = frozenset(["id", "field", "code", "slug", "key", "name"])

# 行内公式：字段上下文里禁用 `$$…$$`
_DISPLAY_SPAN = re.compile(r"\$\$(.+?)\$\$", re.S)


def _to_inline(text):
    """把字段里的 `$$…$$` 降成 `$…$`（字段不是块级公式的位置）。"""
    if "$$" not in text:
        return text
    return _DISPLAY_SPAN.sub(lambda m: "$%s$" % m.group(1), text)


def normalize_text(text, inline=True):
    """规范化一段文本。返回 (新文本, 变更列表)。

    `inline` 决定**独立成行的公式**用什么形态：

    · `True`（默认，**字段上下文**）：标题 / 要点 / 讲稿 / 表格单元 ——
      公式一律写成行内 `$…$`。字段不是块级公式的位置，
      `$$…$$` 会被排版器当成块公式 ⇒ 列表被撑断。
    · `False`（**文档上下文**）：整篇讲义 / 教案 ——
      独立成行的公式保留 `$$…$$`。

    🔴 **两者不能混用**（实测踩过）：文档里被降成行内的 `$$…$$`，
       下一遍会被当成「已经带定界符的代码块公式」重新处理，
       `$` 于是被 `to_latex` 转义成 `\\$` ⇒ 规范化**不幂等**。

    变更列表的元素是 `formula_norm.Change`，带 `.review`（需人工复核）与
    `.residuals`（残留自检命中项）。

    🔴 **只在「确实含可转写公式」时才动手**（判据 = `formula_norm.find_spans`）。
       这一条同时买到三样东西：

       ① **幂等**：已规范化的文本 `find_spans` 为空 ⇒ 原样返回。
          少了这一条，第二遍会把 `$x = …$` 再包成 `$$…$$` 并把 `$` 转义成 `\\$`
          （实测踩过）—— 而**幂等是硬要求**：讲义讲稿必须与课件讲稿逐字同源，
          派生两次不一致就等于破坏同源判据。

       ② **不碰标识符**：`O1`、`course_code`、`P3` 这类字符串
          `find_spans` 本来就不命中，原样返回。

       ③ **不碰 C 类裸变量**：正文里夹的单个字母本来就不自动改（只报告），
          `find_spans` 不收它 ⇒ 不会被误当成"该改的"而整段重写。
    """
    if not isinstance(text, str) or not text:
        return text, []
    if not formula_norm.find_spans(text):
        return text, []
    new, changes = formula_norm.fix_text(text)
    if inline and "$$" in new:
        new = _to_inline(new)
    return new, changes


def normalize_document(text):
    """规范化**整篇文档**（`inline=False`）：独立成行的公式保留 `$$…$$`。

    与 `normalize_obj`（字段级，`inline=True`）配对使用。
    """
    return normalize_text(text, inline=False)


def needs_review(changes):
    """这批改动里有没有「机器改不了、必须人看」的条目。"""
    return any(c.review for c in changes)


def _walk(node, path, out_changes, skip_keys=IDENTIFIER_KEYS):
    """递归规范化 JSON 结构里的每个字符串。"""
    if isinstance(node, dict):
        return {k: (v if k in skip_keys else _walk(v, path + [str(k)], out_changes, skip_keys))
                for k, v in node.items()}
    if isinstance(node, list):
        return [_walk(v, path + [str(i)], out_changes, skip_keys)
                for i, v in enumerate(node)]
    if isinstance(node, str):
        new, changes = normalize_text(node)
        for c in changes:
            c.line = "/".join(path) + ":" + str(c.line)
        out_changes.extend(changes)
        return new
    return node


def normalize_obj(node, skip_keys=IDENTIFIER_KEYS):
    """规范化整个 JSON 结构。返回 (新结构, 变更列表)。"""
    changes = []
    new = _walk(node, [], changes, skip_keys)
    return new, changes


# ─────────────────────────────────────────────────────────────────
# 命令行
# ─────────────────────────────────────────────────────────────────
def _read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _report(changes, src):
    lines = ["# 公式规范化对照报告", "",
             "源：`%s`" % src, "",
             "自动改造 **%d** 处，其中 **%d** 处需人工复核。" %
             (len(changes), sum(1 for c in changes if c.review)), ""]
    if changes:
        lines += ["## 逐条对照", "", "| 位置 | 类型 | 原文 | 改写后 | 自评 |",
                  "|---|---|---|---|---|"]
        for c in changes:
            resid = "、".join(c.residuals) if c.residuals else "✓ 通过"
            lines.append("| %s | %s | `%s` | `%s` | %s |" %
                         (c.line, c.kind, c.before.replace("|", "\\|"),
                          c.after.replace("|", "\\|"), resid))
        lines.append("")
    if any(c.review for c in changes):
        lines += ["## ⚠ 需人工复核（机器改不了，不要直接采纳）", ""]
        for c in changes:
            if c.review:
                lines.append("- `%s`：%s → %s（残留 %s）"
                             % (c.line, c.before, c.after, "、".join(c.residuals)))
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="把公式规范化接进生成链路（字段级、行内形式、需复核即停）")
    ap.add_argument("path", help="源文件（.json 走结构化，其余走文本）")
    ap.add_argument("--out", help="输出文件（默认不写盘，只报告）")
    ap.add_argument("--report", help="对照报告（markdown）")
    ap.add_argument("--apply-review", action="store_true",
                    help="连「需人工复核」的改动一起应用（默认拒绝）")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.path):
        raise SystemExit("文件不存在：%s" % args.path)
    raw = _read(args.path)

    if args.path.lower().endswith(".json"):
        try:
            obj = json.loads(raw)
        except ValueError as e:
            raise SystemExit("JSON 解析失败：%s" % e)
        new, changes = normalize_obj(obj)
        text = json.dumps(new, ensure_ascii=False, indent=2) + "\n"
    else:
        new, changes = normalize_text(raw)
        text = new

    review = [c for c in changes if c.review]
    print("=== 公式规范化 ===")
    print("  改动 %d 处；需人工复核 %d 处" % (len(changes), len(review)))
    for c in review[:8]:
        print("  ⚠ %s %r → %r（残留 %s）"
              % (c.line, c.before, c.after, "、".join(c.residuals)))

    if args.out:
        if review and not args.apply_review:
            print("!! 存在需人工复核的改动 —— **不写文件**。"
                  "先按报告逐条看过，或显式加 --apply-review。")
            return 2
        _write(args.out, text)
        print("  已写出：%s" % os.path.abspath(args.out))
    if args.report:
        _write(args.report, _report(changes, args.path))
        print("  对照报告：%s" % os.path.abspath(args.report))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
