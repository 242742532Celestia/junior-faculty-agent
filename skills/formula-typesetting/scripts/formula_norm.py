#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
formula_norm.py —— 伪公式检测器 + LaTeX 规范化转换器（带自评 + 外部验证）

为什么需要它
------------
AI 写公式时默认写「Unicode 伪公式」（`e^(−γt)`、`ω_d`、`ε/R`、`√(k/m)`），
因为它"看起来像"。这些串渲染出来全是别扭的纯文本。
**靠人工逐条写映射表不可扩展** ⇒ 这个工具把"发现"和"给建议"自动化。

🔴 设计原则：**只建议，不擅改**
- `scan`  ：只报告，绝不动源文件。
- `fix`   ：输出**改造后的副本 + 逐条对照报告**（原文 / 建议 LaTeX / 自评），
            让人或 LLM 过一遍再采纳。原地改写是危险动作。

🔴 三层置信度（自动改造只碰前两层）
- **A 类**：整行公式（代码块内 / 独立段落）、行内代码里的公式 → 自动改。
- **B 类**：中文正文里夹的**带结构信号的**公式（`c·ẋ`、`v²`、`ε = −B(x)·L·v`）→ 自动改，但标「需复核」。
- **C 类**：中文正文里夹的**单个裸变量**（`这里的 v`）→ **只报告不改**，误伤风险高。

实测过的落地路径（本机 pandoc 3.11 + texmath + typst 0.15.1）：
- `\frac{a}{b}`、`\sqrt{\frac{k}{m}}`、`\ddot{x}`、`\hat{\theta}`、`\cdot`、
  `\sum`、`\ln`、`\operatorname{argmin}`、`\left(...\right)` —— typst 与 OMML 双通道均正确。

用法
----
  python formula_norm.py scan  <file.md>                 # 扫描并报告
  python formula_norm.py scan  <file.json> --json         # 扫描 JSON 规格里的字符串
  python formula_norm.py fix   <file.md> --out <new.md>    # 产出改造副本 + 对照报告
  python formula_norm.py fix   <file.md> --out <new.md> --report <rep.md>
  python formula_norm.py rules                           # 列出全部规则
  python formula_norm.py selftest                        # 内置回归自测
  python formula_norm.py validate <file.md>              # 用 pandoc/typst 实测公式能否落地
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata

# 🔴 Windows 控制台默认 GBK，输出 ✓/✗/中文会炸 ⇒ 强制 UTF-8
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════
# 1. 符号表
# ══════════════════════════════════════════════════════════════════

GREEK_LOWER = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta",
    "ε": r"\varepsilon", "ϵ": r"\epsilon", "ζ": r"\zeta", "η": r"\eta",
    "θ": r"\theta", "ϑ": r"\vartheta", "ι": r"\iota", "κ": r"\kappa",
    "λ": r"\lambda", "μ": r"\mu", "ν": r"\nu", "ξ": r"\xi",
    "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau",
    "υ": r"\upsilon", "φ": r"\varphi", "ϕ": r"\phi", "χ": r"\chi",
    "ψ": r"\psi", "ω": r"\omega",
}
GREEK_UPPER = {
    "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta", "Λ": r"\Lambda",
    "Ξ": r"\Xi", "Π": r"\Pi", "Σ": r"\Sigma", "Φ": r"\Phi",
    "Ψ": r"\Psi", "Ω": r"\Omega",
}
GREEK = dict(GREEK_LOWER)
GREEK.update(GREEK_UPPER)

# 组合变音符（U+0300 区）→ LaTeX 命令名
ACCENT_NAMES = {
    "\u0300": "grave", "\u0301": "acute", "\u0302": "hat", "\u0303": "tilde",
    "\u0304": "bar", "\u0305": "overline", "\u0306": "breve", "\u0307": "dot",
    "\u0308": "ddot", "\u0309": "hook", "\u030a": "ring", "\u030b": "hook",
    "\u030c": "check",
}

# Unicode 上标 / 下标字符 → LaTeX 片段
SUP = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5",
       "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁺": "+", "⁻": "-",
       "⁼": "=", "⁽": "(", "⁾": ")"}
SUB = {"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4", "₅": "5",
       "₆": "6", "₇": "7", "₈": "8", "₉": "9", "₊": "+", "₋": "-",
       "₌": "=", "₍": "(", "₎": ")",
       # 字母下标（xₙ / xₙ₊₁ 这类）
       "ₐ": "a", "ₑ": "e", "ₕ": "h", "ᵢ": "i", "ⱼ": "j", "ₖ": "k",
       "ₗ": "l", "ₘ": "m", "ₙ": "n", "ₒ": "o", "ₚ": "p", "ᵣ": "r",
       "ₛ": "s", "ₜ": "t", "ᵤ": "u", "ᵥ": "v", "ₓ": "x"}

# 关系符 / 运算符
REL = {"∝": r"\propto", "⟹": r"\Longrightarrow", "⇒": r"\Rightarrow",
       "→": r"\to", "←": r"\leftarrow", "↔": r"\leftrightarrow",
       "≤": r"\leq", "≥": r"\geq", "≠": r"\neq", "≈": r"\approx",
       "≡": r"\equiv", "∞": r"\infty", "∂": r"\partial", "∇": r"\nabla",
       "×": r"\times", "÷": r"\div", "±": r"\pm", "≪": r"\ll", "≫": r"\gg",
       "∈": r"\in", "∉": r"\notin", "⊂": r"\subset", "⊆": r"\subseteq",
       "∪": r"\cup", "∩": r"\cap", "∅": r"\emptyset",
       "∀": r"\forall", "∃": r"\exists", "∧": r"\land", "∨": r"\lor",
       "⋅": r"\cdot", "≜": r"\triangleq", "⇒": r"\Rightarrow"}

# 函数名 → 直立命令（LaTeX 里必须 upright，且后面不加空格）
FUNC_CMD = {
    "arcsin": r"\arcsin", "arccos": r"\arccos", "arctan": r"\arctan",
    "sinh": r"\sinh", "cosh": r"\cosh", "tanh": r"\tanh",
    "argmin": r"\operatorname{argmin}", "argmax": r"\operatorname{argmax}",
    "log": r"\log", "ln": r"\ln", "lg": r"\lg", "exp": r"\exp",
    "sin": r"\sin", "cos": r"\cos", "tan": r"\tan", "cot": r"\cot",
    "sec": r"\sec", "csc": r"\csc", "max": r"\max", "min": r"\min",
    "det": r"\det", "dim": r"\dim", "gcd": r"\gcd", "lim": r"\lim",
    "sup": r"\sup", "inf": r"\inf",
}

# 🔴 这些名字**同时是常用词或单位**，无条件映射成算子会改错意思：
#    `min` = minute（分钟）、`sec` = second（秒）、`max` = 最大值。
#    `≥2 min`（至少 2 分钟）转成 `$\geq 2 \min$` ⇒ 「2 倍最小值」——
#    **语义被改错**（和「A/B 类不确定度」同一类）。
#    ⇒ 只有在**函数调用（跟左括号）或带上下限（跟 `_` / `^`）**时才当算子。
WORD_COLLISION = {"min", "max", "sec"}

# 单位：斜杠不是分式（rad/s、m/s、N·s/m）
UNIT_TOKENS = {"s", "m", "kg", "rad", "K", "J", "N", "W", "V", "A", "T",
               "Pa", "Hz", "L", "g", "mol"}

MINUS = "\u2212"      # 真减号
MIDDOT = "\u00b7"    # 中点

# 已知命令名：命令后跟字母时补一个空格（\alpha\beta → \alpha \beta）
KNOWN_CMD_SET = set(GREEK.values()) | set(GREEK_LOWER.values()) | {
    r"\frac", r"\sqrt", r"\cdot", r"\sum", r"\prod", r"\operatorname",
    r"\ddot", r"\dot", r"\hat", r"\bar", r"\tilde", r"\check", r"\breve",
    r"\acute", r"\grave", r"\ring", r"\overline", r"\hook",
    r"\propto", r"\Longrightarrow", r"\Rightarrow", r"\to", r"\leftarrow",
    r"\leftrightarrow", r"\leq", r"\geq", r"\neq", r"\approx", r"\equiv",
    r"\infty", r"\partial", r"\nabla", r"\times", r"\div", r"\pm",
    r"\ll", r"\gg", r"\in", r"\notin", r"\subset", r"\subseteq",
    r"\cup", r"\cap", r"\emptyset", r"\forall", r"\exists",
    r"\land", r"\lor", r"\triangleq", r"\ldots", r"\cdots",
}
KNOWN_CMD_SET |= set(v.strip("\\") and "\\" + v.strip("\\") for v in FUNC_CMD.values())
KNOWN_CMD_SET |= {"\\" + v.lstrip("\\") for v in FUNC_CMD.values()}

# ══════════════════════════════════════════════════════════════════
# 2. 转换核心
# ══════════════════════════════════════════════════════════════════

# 伪公式里可能出现在「一个原子」里的字符
_ATOM_CHARS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "\u0391\u0392\u0393\u0394\u0395\u0396\u0397\u0398\u0399\u039a\u039b\u039c"
    "\u039d\u039e\u039f\u03a0\u03a1\u03a3\u03a4\u03a5\u03a6\u03a7\u03a8\u03a9"
    "\u03b1\u03b2\u03b3\u03b4\u03b5\u03b6\u03b7\u03b8\u03b9\u03ba\u03bb\u03bc"
    "\u03bd\u03be\u03bf\u03c0\u03c1\u03c3\u03c4\u03c5\u03c6\u03c7\u03c8\u03c9"
    "\u00b2\u00b3\u00b9\u2070\u2074\u2075\u2076\u2077\u2078\u2079\u207b"
    "\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089"
    "\u208a\u208b\u208c\u208d\u208e\u208f"
    "\u2090\u2091\u2095\u2096\u2097\u2098\u2099\u209a\u209b\u209c"
    + MIDDOT + "_"          # 🔴 `_` 必须在内，否则 `ω_d` 会被截成 `ω` + `_d`
    + "\u2212"               # 🔴 真减号也要在内，否则 `(−BLv/R)` 的分子会丢掉负号
)

_ACC_RE = re.compile(r"^\\([A-Za-z]+)\{(.*)\}$", re.S)


def _sym(ch):
    """希腊字母 → 命令；其余原样。"""
    return GREEK.get(ch, ch)


def _convert_accents(s):
    """变音符（预组合 ẍ 或组合序列 θ̂）→ \\ddot{x} / \\hat{\\theta}。

    🔴 用 unicodedata.NFD 拆预组合字符 ⇒ 不用手写几百个映射表。
    """
    out = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        d = unicodedata.normalize("NFD", ch)
        if len(d) >= 2 and unicodedata.combining(d[1]):
            out.append("\\%s{%s}" % (ACCENT_NAMES.get(d[1], "tilde"), _sym(d[0])))
            i += 1
            continue
        if unicodedata.combining(ch):
            name = ACCENT_NAMES.get(ch, "tilde")
            if out:
                prev = out.pop()
                m = _ACC_RE.match(prev)
                if m:
                    out.append("\\%s{%s}" % (name, m.group(2)))
                else:
                    out.append("\\%s{%s}" % (name, _sym(prev)))
            else:
                out.append(ch)
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _strip_outer_paren(t):
    """去掉最外层成对括号：(2m) → 2m"""
    t = t.strip()
    if len(t) >= 2 and t[0] == "(" and t[-1] == ")":
        depth = 0
        for i, ch in enumerate(t):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(t) - 1:
                    return t
        return t[1:-1]
    return t


def _is_unitish(t):
    """t 看起来像「量纲片段」而不是公式分子/分母。

    🔴 带上下标 ⇒ 更像变量（`T₀` 是周期不是特斯拉），不算量纲。
    """
    t = _strip_outer_paren(t)
    t = re.sub(r"[\u2080-\u209c\u00b2\u00b3\u2070-\u207f]", "", t)
    t = t.replace(MIDDOT, "")
    if not re.fullmatch(r"[A-Za-z]+", t):
        return False
    return any(tok in t for tok in UNIT_TOKENS)


def _expand_left(s, i):
    """从 s[i-1] 向左扩展，取一个「原子串」。返回 (文本, 起点)。

    🔴 已经写成 LaTeX 命令的片段（`\\pi`、`\\alpha`）要**整体**算作一个原子。
       否则 `\\pi/2` 会在 `\\pi` 中间被切开 ⇒ 反斜杠留在 `\\frac` 外面、
       字母 `pi` 落进分子 ⇒ 渲染成字面量 `\\frac{pi}{2}`（`\\` 在 LaTeX 里是换行）。
    """
    j = i - 1
    while j >= 0 and s[j] in " \t":
        j -= 1
    if j < 0:
        return None, i
    k = j
    while k >= 0 and s[k] in _ATOM_CHARS:
        k -= 1
    # 🔴 把紧邻左侧的 LaTeX 命令（反斜杠 + 字母）并进原子
    if k >= 0 and s[k] == "\\" and k + 1 <= j and s[k + 1:k + 2].isalpha():
        m = k + 1
        while m <= j and s[m].isalpha():
            m += 1
        k = m - 1
    if k == j:
        return None, i
    return s[k + 1:j + 1], k + 1


def _expand_right(s, i):
    """从 s[i] 向右扩展，取一个「原子串」。返回 (文本, 终点)。"""
    j = i
    while j < len(s) and s[j] in " \t":
        j += 1
    if j >= len(s):
        return None, i
    if s[j] == "(":
        depth = 0
        k = j
        while k < len(s):
            if s[k] == "(":
                depth += 1
            elif s[k] == ")":
                depth -= 1
                if depth == 0:
                    return s[j:k + 1], k + 1
            k += 1
        return None, i
    k = j
    while k < len(s) and s[k] in _ATOM_CHARS:
        k += 1
    if k == j:
        return None, i
    return s[j:k], k


def _slash_ok(s, i):
    """这个 '/' 是不是分号（而不是 URL 里的 //）。"""
    if i + 1 < len(s) and s[i + 1] == "/":
        return False
    if i > 0 and s[i - 1] in ":.":
        return False
    return True


# 类别并列的标记词：分母后面跟这些字 ⇒ 「A/B 类」是**两类**，不是「A 除以 B」
# 🔴 「A 类不确定度 / B 类不确定度」是计量学里的固定说法（GUM），
#    转成 \frac{A}{B} 会把「两类」说成「A 除以 B」——**语义被改错了**。
#    这类误报的代价不是「排版难看」，是「意思变了」，比漏转严重得多。
CATEGORY_MARKS = ("类", "型", "级", "组", "档", "族", "式")

# 「X/Y」形状：两个**单个大写拉丁字母**
_CATEGORY_PAIR = re.compile(r"^([A-Z])\s*/\s*([A-Z])$")


def _is_category_pair(num, den, tail):
    """`A/B` 后面紧跟类别标记字 ⇒ 是「A 类与 B 类」的并列，不是分式。

    判据（三条同时成立）：
      ① 分子、分母**各自只有一个大写拉丁字母**（标签的典型形状）；
      ② 分母后面紧跟类别标记词（类/型/级/组/档/族/式）；
      ③ 分子前面不是数字/等号/运算符（排除「= A/B 类」这种真公式）。

    🔴 为什么只挡大写单字母：`m/k`、`γ/ω₀`、`x_{n}/x_{n+1}` 这些**真分式**
       的分子分母都是小写或带下标 ⇒ 不受影响。
       大写单字母对（R/N、B/L）在物理里极少见，但「A 类、B 类、X 型、Y 组」
       在中文教学材料里是高频词 —— 宁可漏转，也不能把「两类」说成「相除」。

    🔴 `tail` 必须是**表达式后面紧跟的那段文字**：中文切分会把「A/B」和
       「类不确定度」拆成两个片段，类别标记字在**下一个**片段里 ——
       只看表达式自己，永远看不到这个上下文。
    """
    if not (num and den):
        return False
    if not _CATEGORY_PAIR.match(("%s/%s" % (num, den)).strip()):
        return False
    t = str(tail or "").lstrip()
    return bool(t) and t[0] in CATEGORY_MARKS


def _is_category_pair_in_segs(body, segs, idx):
    """跨片段判「X/Y 类」：片段 `body` 后面紧跟的 CJK 片段是不是类别标记。

    🔴 中文切分会把 `A/B 类不确定度` 拆成 `['A/B ', '类不确定度']` ——
       类别标记字在**下一个片段**里。只看 `body` 的话永远看不到它，
       于是「两类」就被改写成了「A 除以 B」。
    """
    if idx + 1 >= len(segs):
        return False
    nxt_is_cjk, nxt = segs[idx + 1]
    if not nxt_is_cjk:
        return False
    m = _CATEGORY_PAIR.match(str(body or "").strip())
    if not m:
        return False
    return _is_category_pair(m.group(1), m.group(2), nxt)


def _frac_pass(s, depth=0):
    """斜杠分式 → \\frac{...}{...}。

    🔴 必须在**其它转换之前**跑：此时源还是原始 Unicode，
       分子分母的切分才不会被 `\\varepsilon`、`^{2}` 这些命令打断。
    """
    if depth > 6:
        return s
    matches = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "/" and _slash_ok(s, i):
            num, nstart = _expand_left(s, i)
            den, dend = _expand_right(s, i + 1)
            if (num and den and not (_is_unitish(num) and _is_unitish(den))
                    and not _is_category_pair(num, den, s[dend:])):
                matches.append((nstart, i, dend, num, den))
                i = dend
                continue
        i += 1
    if not matches:
        return s
    out = []
    pos = 0
    for (nstart, slash, dend, num, den) in matches:
        out.append(s[pos:nstart])
        out.append(r"\frac{%s}{%s}" % (
            to_latex(num.rstrip(), depth + 1),
            to_latex(_strip_outer_paren(den), depth + 1)))
        pos = dend
    out.append(s[pos:])
    return "".join(out)


def _sum_pass(s):
    """Σ/Π：当成算子（\\sum/\\prod）还是希腊字母（\\Sigma/\\Pi）。

    判据：去掉它以后还剩「项」⇒ 是算子；否则是希腊字母。
    """
    for ch, op, greek in (("\u2211", r"\sum", r"\Sigma"), ("\u03a3", r"\sum", r"\Sigma"),
                          ("\u220f", r"\prod", r"\Pi"), ("\u03a0", r"\prod", r"\Pi")):
        if ch not in s:
            continue
        rest = s.replace(ch, "")
        has_term = bool(re.search(r"[A-Za-z\u0391-\u03a9\u03b1-\u03c9 0-9]", rest))
        s = s.replace(ch, op if has_term else greek)
    return s


def _func_pass(s):
    """函数名 → 直立命令。🔴 用前后向断言防止劈坏 \\varepsilon 这种命令。"""
    for name in sorted(FUNC_CMD, key=len, reverse=True):
        cmd = FUNC_CMD[name]
        if name in WORD_COLLISION:
            # 🔴 min/max/sec 兼作单位或普通词 ⇒ 只有函数调用/带上下限才当算子
            pat = (r"(?<![A-Za-z\\])" + name
                   + r"(?=\s*[\(\^_])(?![A-Za-z])")
        else:
            pat = r"(?<![A-Za-z\\])" + name + r"(?![A-Za-z])"
        s = re.sub(pat, lambda m, c=cmd: c + " ", s)
    return s


_ATOM_END = r"[A-Za-z0-9\u0391-\u03a9\u03b1-\u03c9\u00b2\u00b3)\]}]"
_ATOM_START = r"(?:[A-Za-z0-9\u0391-\u03a9\u03b1-\u03c9\u00b2\u00b3(\[{]|\\[A-Za-z]+)"


def _dot_pass(s):
    """中点当乘号 → \\cdot。

    🔴 边界要放宽到 `)`/`}`/希腊/命令，否则 `m·\\ddot{x}`、`-(...)·v` 会漏。
       同时要求左右都有「原子」，否则 `带 · 的是乘号` 这种会误判。
    """
    pat = r"(?<=%s)[ \t]*%s[ \t]*(?=%s)" % (_ATOM_END, MIDDOT, _ATOM_START)
    return re.sub(pat, r" \\cdot ", s)


_CMD_RE = re.compile(r"\\([A-Za-z]+)")

# 🔴 只有「符号型命令」需要补空格（希腊字母 / 变音符）。
#    函数命令（\ln \sin …）由 _func_pass 处理；\int 这类词形命令绝不能被劈开。
_SPACE_COMMANDS = sorted(
    set(GREEK.values()) | {
        r"\ddot", r"\dot", r"\hat", r"\bar", r"\tilde", r"\check",
        r"\breve", r"\acute", r"\grave", r"\ring", r"\overline", r"\hook",
        # 关系符也要补空格（`ε→i` ⇒ `\varepsilon \to i`）
        # 🔴 排除 `\in`：`\int` 会被劈坏
        r"\to", r"\rightarrow", r"\Longrightarrow", r"\Rightarrow",
        r"\leftarrow", r"\leftrightarrow", r"\propto", r"\approx",
        r"\leq", r"\geq", r"\neq", r"\equiv", r"\times", r"\pm", r"\gg", r"\ll",
    },
    key=len, reverse=True)
_SPACE_RE = re.compile("|".join(re.escape(c) for c in _SPACE_COMMANDS))


def _space_cmds(s):
    """符号命令后紧跟字母时补空格（\\alpha\\beta → \\alpha \\beta）。

    🔴 用「已知符号命令的最长匹配」而不是贪婪字母串：
       贪婪会把 `\\gammat` 整段当成一个未知命令，从而漏补空格。
    """
    def rep(m):
        cmd = m.group(0)
        end = m.end()
        if end < len(s):
            nxt = s[end]
            if nxt == "{":
                return cmd
            if nxt.isalnum() or nxt == "\\":
                return cmd + " "
        return cmd
    return _SPACE_RE.sub(rep, s)


def _is_single_frac(t):
    """t 是不是「恰好一个 \\frac{..}{..}」（允许内部再嵌套花括号）。"""
    t = t.strip()
    if not t.startswith("\\frac{"):
        return False
    depth = 0
    for k in range(len("\\frac"), len(t)):
        if t[k] == "{":
            depth += 1
        elif t[k] == "}":
            depth -= 1
            if depth == 0:
                # 分子结束，后面必须是分母的 {
                if k + 1 >= len(t) or t[k + 1] != "{":
                    return False
                d2 = 0
                for m in range(k + 1, len(t)):
                    if t[m] == "{":
                        d2 += 1
                    elif t[m] == "}":
                        d2 -= 1
                        if d2 == 0:
                            return m == len(t) - 1
                return False
    return False


def _unwrap_frac_parens(s):
    """去掉只包着一个 \\frac 的冗余括号：(a/b) → \\frac{a}{b}。

    🔴 \\frac 本身就有分组语义，外面再套一层括号既难看又会多算一次括号尺寸。
       用括号配对扫描而不是正则，才能处理 `{B^{2}L^{2}}` 这种嵌套花括号。
    """
    changed = True
    while changed:
        changed = False
        for i, ch in enumerate(s):
            if ch != "(":
                continue
            depth = 0
            end = None
            for j in range(i, len(s)):
                if s[j] == "(":
                    depth += 1
                elif s[j] == ")":
                    depth -= 1
                    if depth == 0:
                        end = j
                        break
            if end is None:
                continue
            inner = s[i + 1:end]
            if _is_single_frac(inner):
                s = s[:i] + inner + s[end + 1:]
                changed = True
                break
    return s


def _rest(s, depth=0):
    """除「分式」以外的���部转换。"""
    s = _convert_accents(s)

    # 脱字符冒充上标： x^(−γt) → x^{−\gamma t}
    s = re.sub(r"\^\(([^()]*)\)", lambda m: "^{%s}" % _light(m.group(1)), s)
    s = re.sub(r"\^\{([^{}]*)\}", lambda m: "^{%s}" % _light(m.group(1)), s)

    # Σ / Π
    s = _sum_pass(s)

    # 希腊字母（Σ/Π 已处理）
    for k, v in GREEK.items():
        if k in ("\u03a3", "\u03a0"):
            continue
        s = s.replace(k, v)

    # 下划线冒充下标： ω_d → \omega_{d}
    # 🔴 多字符下标（δ_rel、I0_meas）必须**整体**收进一组：
    #    只吃单字符会把 `δ_rel` 切成 `\delta_{r}el` —— 下标只拿到 r，`el` 掉在外面。
    # 🔴 多字符下标用 \mathrm{} 转正体：`rel` 若走斜体，渲染出来像 r·e·l 相乘。
    def _sub(m):
        body = m.group(1)
        if len(body) > 1 and body.isalpha():
            return r"_{\mathrm{%s}}" % body
        return r"_{%s}" % body
    s = re.sub(r"(?<!\\)_([A-Za-z0-9]+)", _sub, s)

    # 根号带括号： √(k/m) → \sqrt{k/m}
    s = re.sub(r"\u221a\(([^()]*)\)", lambda m: r"\sqrt{%s}" % _light(m.group(1)), s)

    # Unicode 上标 / 下标（连续一段合并成一个组）
    s = re.sub(r"[\u2070\u00b9\u00b2\u00b3\u2074-\u2079\u207a\u207b\u207c\u207d\u207e]+",
               lambda m: "^{%s}" % "".join(SUP.get(c, c) for c in m.group(0)), s)
    s = re.sub(r"[\u2080-\u209c]+",
               lambda m: "_{%s}" % "".join(SUB.get(c, c) for c in m.group(0)), s)

    # 关系符 / 运算符
    for k, v in REL.items():
        s = s.replace(k, v)

    # 函数名
    s = _func_pass(s)

    # 中点乘号
    s = _dot_pass(s)

    # 真减号 → 普通减号
    s = s.replace(MINUS, "-")

    # LaTeX 特殊字符
    s = re.sub(r"(?<!\\)([&%$#])", r"\\\1", s)

    # 命令后补空格
    s = _space_cmds(s)

    # 空白整理
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def _light(t):
    """轻量转换（用于 ^{...} 内部 / 根号内部）：变音 + 希腊 + 上下标。"""
    t = _convert_accents(t)
    for k, v in GREEK.items():
        if k in ("\u03a3", "\u03a0"):
            continue
        t = t.replace(k, v)
    t = re.sub(r"[\u2070\u00b9\u00b2\u00b3\u2074-\u2079\u207a\u207b\u207c\u207d\u207e]+",
               lambda m: "^{%s}" % "".join(SUP.get(c, c) for c in m.group(0)), t)
    t = re.sub(r"[\u2080-\u209c]+",
               lambda m: "_{%s}" % "".join(SUB.get(c, c) for c in m.group(0)), t)
    # 🔴 `e^(−γt)` 的上标内容里 `γt` 会被黏成 `\gammat` ⇒ 这里也要补空格
    t = _space_cmds(t)
    return t.strip()


def to_latex(span, depth=0):
    """把一段伪公式转成 LaTeX（尽力而为，**必须复核**）。"""
    s = span.strip()
    if not s:
        return ""
    s = _frac_pass(s, depth)
    s = _rest(s, depth)
    s = _unwrap_frac_parens(s)
    return s.strip()


# ══════════════════════════════════════════════════════════════════
# 3. 自评：转换完还有没有「伪公式残留」
# ══════════════════════════════════════════════════════════════════

def residual_check(latex):
    """返回残留问题列表；空列表 = 转换干净。"""
    issues = []
    if MIDDOT in latex:
        issues.append("残留中点乘号 ·")
    if re.search(r"[\u0391-\u03a9\u03b1-\u03c9]", latex):
        issues.append("残留希腊字母")
    if re.search(r"[\u2211\u220f\u03a3\u03a0]", latex):
        issues.append("残留求和/连乘符")
    if "\u221a" in latex:
        issues.append("残留根号")
    if re.search(r"(?<!\\)\^(?!\{)", latex):
        issues.append("残留裸上标")
    if re.search(r"(?<!\\)_(?![{A-Za-z0-9])", latex):
        issues.append("残留裸下标")
    if re.search(r"[A-Za-z0-9}]\s*/\s*[A-Za-z0-9({]", latex):
        issues.append("残留斜杠分式")
    if any(unicodedata.combining(c) for c in latex):
        issues.append("残留组合变音符")
    if MINUS in latex:
        issues.append("残留真减号 U+2212")
    if latex.count("{") != latex.count("}"):
        issues.append("花括号不配对")
    if re.search(r"(?<!\\)[&%$#]", latex):
        issues.append("未转义的 LaTeX 特殊字符")
    if re.search(r"\)\s*\(", latex):
        issues.append("可能缺失运算符")
    if re.search(r"\\frac\{[^{}]*\}\{[^{}]*\}\s*\\frac", latex):
        issues.append("相邻分式（疑似变量列表或链式除法，待确认）")
    return issues


# ══════════════════════════════════════════════════════════════════
# 4. 片段识别：什么算「一行公式」/「一个单位」
# ══════════════════════════════════════════════════════════════════

CJK_RE = re.compile(r"[\u2e80-\u303f\u3040-\u9fff\uf900-\ufaff\uff00-\uffef"
                    r"\u2013\u2014\u2026\u2027]+")

# 结构信号：有它才像公式（避免把英文单词当公式）
# 🔴 Unicode 上下标也算结构信号：`ω₀`、`log₁₀` 本身就是公式片段
STRUCT_RE = re.compile(r"[=\u221d\u2192\u2190\u2194\u2264\u2265\u2260\u2248\u2261"
                        r"\u221a^_/\u00b7\u00d7\u00f7\u00b1"
                        r"\u00b2\u00b3\u00b9\u2070-\u209c]")

# 关系符：没有变量但有关系符的也算公式（`2 × 0.434 ≈ 0.87`）
_RELATION_RE = re.compile(r"[=\u2248\u221d\u2192\u21d2\u27f9\u2264\u2265\u2260\u2261]")


def _is_unit_expr(s):
    """整段是不是量纲（rad/s、N·s/m）——量纲不是分式，也不该排成公式。

    🔴 每个「/」或「·」分出来的片段都必须是**完整的单位词**：
       否则 `B²L²/R` 会因为含 `B`（特斯拉）被误判成量纲。
    🔴 带**下标**的是变量（`T₀` 是周期）不是量纲；带上标的可以是量纲（`s⁻¹`）。
    🔴 允许「数值 + 单位」形态（`3.2 W/m²`）——那是「某个量的单位」，
       不是公式。只允许**纯数字**前缀，带字母就不是了（`B²L²/R` 仍判为公式）。
    """
    t = s.strip()
    if not t:
        return False
    if re.search(r"[=\u221d\u2192]", t):
        return False
    if CJK_RE.search(t):
        return False
    if re.search(r"[\u2080-\u209c]", t):
        return False
    # 🔴 剥掉纯数字前缀（`3.2 W/m²` → `W/m²`）；带字母的不许剥
    m = re.match(r"^(\d+(?:\.\d+)?)\s+(?=[A-Za-z\u03a9])", t)
    if m:
        t = t[m.end():]
    if not re.fullmatch(r"[A-Za-z\u03a9\u00b5\u00b0\u00b7/\u00b9\u00b2\u00b3"
                        r"\u2070-\u207f]+", t):
        return False
    for p in re.split(r"[/·]", t):
        base = re.sub(r"[\u2070-\u207f\u00b2\u00b3\u00b9]", "", p)
        if base and base not in UNIT_TOKENS:
            return False
    return True


# 🔴 「比较符 + 数值(+单位)」是**阈值**，不是数学表达式。
#    `≥2 min` = 至少 2 分钟 —— 转成 `$\geq 2 \min$` 会把「分钟」说成「最小值」，
#    语义被改错；而且与已有的 D7「数值+量纲不算公式」自相矛盾
#    （`5 s`、`30 min` 都不转，只因为前面多了个 `≥` 就转了）。
_THRESHOLD_PREFIX = re.compile(r"^[\u2264\u2265<>\u226a\u226b]\s*")
_NUM_UNIT = re.compile(r"^\d+(?:\.\d+)?(?:\s*[A-Za-z\u00b0\u00b5]{1,})?$")


def _is_threshold_expr(s):
    """比较符开头 + 「数字（可带单位词）」⇒ 阈值，不是公式。

    🔴 单位词里出现希腊字母/下标 ⇒ 是公式不是阈值（`≥2π`）。
    """
    t = s.strip()
    m = _THRESHOLD_PREFIX.match(t)
    if not m:
        return False
    rest = t[m.end():]
    if not rest:
        return False
    if re.search(r"[\u03b1-\u03c9\u0391-\u03a9\u2080-\u209c\u00b2\u00b3]", rest):
        return False
    return bool(_NUM_UNIT.match(rest))


def _is_name_like(t):
    """像代码标识符（solve_ivp / curve_fit / np.polyfit）而不是公式。

    🔴 `_` 后面只跟一个字符 ⇒ 那是下标（`ω_d`），不是名字的一部分。
    """
    if not re.match(r"^[A-Za-z][A-Za-z0-9_.]*$", t):
        return False
    if re.search(r"_[A-Za-z0-9]$", t):
        return False
    return len(t) >= 4


_NAME_WORD = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{3,}$")


def _all_name_words(t):
    """整段都是「多字符英文词」⇒ 是模块名/路径，不是公式。

    🔴 `numpy / scipy`、`skills/teaching-file-builder` 都是这种情况；
       而 `R / N / μ`、`i = ε/R` 里有单字母或希腊字母，是真公式。
    """
    toks = [x for x in re.split(r"[/\u00b7\s]+", t.strip()) if x]
    if not toks:
        return False
    return all(_NAME_WORD.match(x) for x in toks)


def _bare_slash_count(t):
    """**顶层**（不在括号里）且分母不带括号的斜杠个数。

    🔴 `R / N / μ` 有 2 个 ⇒ 是变量列表不是公式；
       `γ = c/(2m) = N²·L² / (2m·R)` 分母都带括号 ⇒ 0 个，正常转换；
       `F = −BL·(ε/R) = −BL·(−BLv/R)` 的斜杠都在括号里 ⇒ 0 个，正常转换。
    """
    depth = 0
    n = 0
    i = 0
    while i < len(t):
        ch = t[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "/" and depth == 0:
            j = i + 1
            while j < len(t) and t[j] in " \t":
                j += 1
            if j >= len(t) or t[j] != "(":
                n += 1
        i += 1
    return n


def is_formula_line(s):
    """判断一段文本是不是「纯公式」。

    🔴 误报防线（每一条都对应实测踩过的坑）：
       ① 必须有**字母/希腊字母，或「关系符 + 数字」** ⇒ `× 3`、`30% /` 不算公式；
       ② 运算符在首尾 ⇒ 是列表分隔符或残片（`ODE / 欠阻尼`、`G · 目标`）；
       ③ 标识符样式且够长 ⇒ 是函数名（`solve_ivp`）不是公式；
       ④ 整段都是英文词 ⇒ 是模块名/路径（`numpy / scipy`）；
       ⑤ 量纲（`rad/s`、`N·s/m`）不是公式；
       ⑥ 阈值（`≥2 min`、`≤ 30 s`）是**条件**不是公式 —— 转成 `$\\geq 2 \\min$`
          会把单位「分钟」说成「最小值」。
    """
    t = s.strip()
    if not t:
        return False
    if CJK_RE.search(t):
        return False
    # ① 必须有变量（字母/希腊），或「关系符 + 数字」
    #    🔴 不能只要关系符：正文里的单独一个 `=` 不是公式；
    #       也不能只要数字：`× 3` 是散文里的乘法。
    if not (re.search(r"[A-Za-z\u0391-\u03a9\u03b1-\u03c9]", t)
            or (re.search(_RELATION_RE, t) and re.search(r"[0-9]", t))):
        return False
    # 必须有结构信号
    if not STRUCT_RE.search(t):
        return False
    # ② 运算符在首尾 ⇒ 列表分隔符 / 残片
    for ch in ("/", "\u00b7", "\u00d7", "\u00f7", "="):
        if ch in t and (t.startswith(ch) or t.endswith(ch)):
            return False
    # ③ 标识符 ⇒ 名字
    if _is_name_like(t):
        return False
    # ④ 整段都是英文词 ⇒ 模块名 / 路径
    if _all_name_words(t):
        return False
    # ④' 两个以上「裸」分母 ⇒ 变量列表（`R / N / μ`）不是公式
    if _bare_slash_count(t) >= 2:
        return False
    # ⑤ 量纲
    if _is_unit_expr(t):
        return False
    # ⑥ 阈值（比较符 + 数值(+单位)）不是公式
    if _is_threshold_expr(t):
        return False
    return True


# ══════════════════════════════════════════════════════════════════
# 2b. 「像不像一个要排版成公式的片段」—— **唯一出处**
#
# 🔴 为什么必须是共享的一份：注入器（要不要注 OMML）与验收闸（正文页还有没有
#    LaTeX 源码）用的是**同一个问题**。两边各写一份 ⇒ 两边同时漏判，
#    而且漏了没人知道（实测：`F = -BLi` 这种简单关系式两边都放过，
#    课件正文页直接显示 `$F = -BLi$` 源码，闸还报「零 ERROR」）。
#
#    窄判据（只认 LaTeX 命令 / 上下标 / 花括号）会漏掉**只有字母和运算符**的
#    简单式；但只看「有字母」又会把 `$50`（价格）、`$100 万`（经费）当公式。
#    ⇒ 三条任一成立即算「像公式」。
_LATEXISH = re.compile(r"\\[A-Za-z]+|\^|_\{|\{|\}")
_SINGLE_VAR = re.compile(r"^[A-Za-z\u0391-\u03a9\u03b1-\u03c9]$")
_REL_OR_OP = re.compile(r"[=<>\u2264\u2265\u221d\u2248\u2261\u2260+\-*/\u00b7\u00d7\u00f7]")


def looks_like_latex(s):
    """这段文本像不像一个**要排版成公式**的片段。

    ① 带 LaTeX 命令 / 上标 / 下标 / 花括号（`\\frac{B^{2}}{R}`）；
    ② 就是一个单字母变量（`$v$`）；
    ③ **关系式**：含运算符**且**含字母（`F = -BLi`、`ε = -BLv`）。
       没有字母的 `$50` / `$100 万` 仍然排除 —— 货币与经费不是公式。
    """
    s = (s or "").strip()
    if not s:
        return False
    if _LATEXISH.search(s) or _SINGLE_VAR.match(s):
        return True
    if not _REL_OR_OP.search(s):
        return False
    return bool(re.search(r"[A-Za-z\u0391-\u03a9\u03b1-\u03c9]", s))


def _split_cjk(text):
    """切成 (is_cjk, seg) 序列。"""
    segs = []
    pos = 0
    for m in CJK_RE.finditer(text):
        if m.start() > pos:
            segs.append((False, text[pos:m.start()]))
        segs.append((True, m.group(0)))
        pos = m.end()
    if pos < len(text):
        segs.append((False, text[pos:]))
    return segs


# ══════════════════════════════════════════════════════════════════
# 5. 检测规则（scan 模式）
# ══════════════════════════════════════════════════════════════════

RULES = [
    ("unicode_sup", "Unicode 上标字符（应写 ^{}）",
     r"[\u2070\u00b9\u00b2\u00b3\u2074-\u2079\u207a\u207b]"),
    ("unicode_sub", "Unicode 下标字符（应写 _{}）",
     r"[\u2080-\u209c]"),
    ("caret_paren", "脱字符 + 圆括号冒充上标",
     r"\^\([^()]*\)"),
    ("caret_brace", "脱字符 + 花括号冒充上标",
     r"\^\{[^}]*\}"),
    ("underscore_sub", "下划线冒充下标",
     r"[A-Za-z\u0391-\u03a9\u03b1-\u03c9]_[A-Za-z0-9]"),
    ("slash_frac", "斜杠代替分式（应写 \\frac）",
     r"(?<![:/A-Za-z0-9])([A-Za-z\u0391-\u03a9\u03b1-\u03c90-9\u00b2\u00b3\u2080-\u209c]+)"
     r"/([A-Za-z\u0391-\u03a9\u03b1-\u03c90-9\u00b2\u00b3\u2080-\u209c]*)"),
    ("paren_frac", "带括号的分式（应写 \\frac）",
     r"[A-Za-z0-9\u0391-\u03a9\u03b1-\u03c9\u00b2\u00b3]\s*/\s*\([^()]*\)"),
    ("sqrt_paren", "根号带括号（应写 \\sqrt）",
     r"\u221a\([^()]*\)"),
    ("combining", "组合变音字符（应写 \\ddot/\\dot 等）",
     r"[\u0300-\u036f]"),
    ("greek_bare", "裸希腊字母（应写 \\varepsilon 等）",
     r"[\u0391-\u03a9\u03b1-\u03c9]"),
    ("mul_dot", "中点当乘号（应写 \\cdot）",
     r"[A-Za-z0-9\u0391-\u03a9\u03b1-\u03c9)\]}]\s*\u00b7\s*"
     r"[A-Za-z0-9\u0391-\u03a9\u03b1-\u03c9(\[{]"),
    ("rel_symbol", "裸关系符（应写 \\propto 等）",
     r"[\u221d\u27f9\u21d2\u2192\u2190\u2194\u2264\u2265\u2260\u2248\u2261]"),
    ("sum_symbol", "裸求和/连乘符（应写 \\sum/\\prod）",
     r"[\u2211\u220f]"),
    ("func_name", "函数名未直立（应写 \\ln/\\sin 等）",
     r"(?<![A-Za-z\\])(ln|log|sin|cos|tan|exp|argmin|argmax)(?![A-Za-z])"),
    ("var_in_cjk", "中文里夹着裸变量（应写成 $v$）",
     r"([\u4e00-\u9fff])\s*([A-Za-z\u0391-\u03a9\u03b1-\u03c9])\s*"
     r"(?=[\u4e00-\u9fff\uff0c\u3002\u3001\uff1b\uff1a\uff08\u300c\u300d])"),
]

RULE_DESC = {rid: desc for rid, desc, _ in RULES}


# ══════════════════════════════════════════════════════════════════
# 6. 改造（产出副本 + 逐条对照报告）
# ══════════════════════════════════════════════════════════════════

class Change(object):
    def __init__(self, line, kind, before, after, latex=None, residuals=None):
        self.line = line
        self.kind = kind
        self.before = before
        self.after = after
        self.latex = latex
        self.residuals = residuals or []

    @property
    def review(self):
        return bool(self.residuals)

    def as_dict(self):
        return {"line": self.line, "kind": self.kind, "before": self.before,
                "after": self.after, "latex": self.latex,
                "residuals": self.residuals, "need_review": self.review}


_TRIM = " \t*~`"

# 🔴 源里已经写好的行内公式 `$...$`（或 display `$$...$$`）
#    ⇒ 内容已经是 LaTeX，**只做规范化、不再套分隔符**。
#    否则会变成 `$$...$$`（双美元）⇒ pandoc 判为字面文本，PDF 里直接出现 `$$`。
#    扫描式（不锚定）⇒ 一行里多次出现 `$...$` 也能逐个摘出来。
_INLINE_MATH = re.compile(r"\$(?!\$)([^$\n]+?)(?<!\$)\$")
_DISPLAY_MATH = re.compile(r"\$\$(.+?)\$\$", re.S)
_DISPLAY_WRAP = re.compile(r"^\$\$(.+?)\$\$$", re.S)


def _trim_frag(seg):
    lead = seg[:len(seg) - len(seg.lstrip(_TRIM))]
    body = seg.strip(_TRIM)
    trail = seg[len(body) + len(lead):]
    return lead, body, trail


# ── markdown 结构标记 ──────────────────────────────────────────
_HEADING = re.compile(r"^\s{0,3}#{1,6}(\s|$)")
_QUOTE = re.compile(r"^(\s*(?:>\s*)+)")
CODE_LANGS = {"python", "py", "bash", "sh", "shell", "zsh", "js", "javascript",
              "json", "yaml", "yml", "toml", "c", "cpp", "java", "go", "rs",
              "r", "sql", "html", "css", "text", "txt", "ini", "conf"}

# 代码块特征：这些一旦出现，块里就不是公式
_CODE_HINT = re.compile(
    r"(?:^\s*(?:import|from|def|return|for|while|elif|else|class|print|assert)\b)"
    r"|(?:\b(?:np|numpy|scipy|sol|plt)\.)"
    r"|(?:[A-Za-z_]\w*\s*==)"
    r"|(?:\b(?:True|False|None|self|lambda)\b)")

# 只有运算符的片段（⟹ 之类）—— 是公式链的连接件，不是独立公式
# 🔴 ⟹(U+27F9) / ⇒(U+21D2) 必须在内，否则公式链会被拆成好几个独立公式
_OPERATOR_ONLY = re.compile(
    r"^[=+\u2212\u00d7\u00f7\u221d\u27f9\u21d2\u2192\u2190\u2194\u00b7\u00b1/,\s]+$")


def _split_prefix(line):
    """拆出行首的 markdown 结构标记 → (quote, heading, body)。"""
    quote = ""
    m = _QUOTE.match(line)
    if m:
        quote = m.group(1)
        line = line[m.end():]
    head = ""
    m = _HEADING.match(line)
    if m:
        head = m.group(0)
        line = line[m.end():]
    return quote, head, line


def _split_table_row(body):
    """表格行 → 单元格列表；不是表格行返回 None。"""
    if not body.strip().startswith("|"):
        return None
    parts = re.split(r"(?<!\\)\|", body)
    if len(parts) < 3:
        return None
    return parts


def _fix_plain(text, ln, changes, spans=None, base=0):
    """处理一段不含行内代码的文本：中文段落里的公式。

    🔴 `spans` 非空时，额外吐出可自动转写片段的**绝对位置**，
       供 PPTX 侧把「文字 + 公式 + 文字」拆成多段注入。
    """
    # 🔴 先按 `$...$` 把已有的行内公式摘出来，剩下部分再走中文切分逻辑。
    #    否则「切分后逐段处理」会把 `$E_0$` 的两个 `$` 拆到不同片段，
    #    重组时多出一个 `$` ⇒ `$$`（pandoc 判为字面文本）。
    out = []
    cur = 0
    pos = 0
    for m in _INLINE_MATH.finditer(text):
        if m.start() > pos:
            out.append(_fix_plain_nomath(text[pos:m.start()], ln, changes, spans, base + pos))
        inner = m.group(1)
        lat = to_latex(inner)
        out.append("$%s$" % lat)
        changes.append(Change(ln, "B_已有行内公式", inner.strip(), "$%s$" % lat,
                              lat, residual_check(lat)))
        pos = m.end()
    if pos < len(text):
        out.append(_fix_plain_nomath(text[pos:], ln, changes, spans, base + pos))
    return "".join(out)


def _fix_plain_nomath(text, ln, changes, spans=None, base=0):
    """不含 `$...$` 的正文片段：中文段落里的伪公式。"""
    out = []
    cur = 0
    segs = list(_split_cjk(text))
    for si, (is_cjk, seg) in enumerate(segs):
        if is_cjk or not seg.strip():
            out.append(seg)
            cur += len(seg)
            continue
        lead, body, trail = _trim_frag(seg)
        if not body:
            out.append(seg)
            cur += len(seg)
            continue
        if is_formula_line(body):
            # 🔴 「A/B 类」是**两类并列**，不是除法。
            #    类别标记字在**下一个 CJK 片段**里（中文切分把两者拆开了），
            #    所以必须跨片段看上下文 —— 只看 `body` 永远看不到。
            if _is_category_pair_in_segs(body, segs, si):
                out.append(seg)
                cur += len(seg)
                continue
            lat = to_latex(body)
            if spans is not None:
                start = base + cur + len(lead)
                spans.append((start, start + len(body), lat))
            out.append("%s$%s$%s" % (lead, lat, trail))
            changes.append(Change(ln, "B_正文内公式", seg.strip(), "$%s$" % lat,
                                  lat, residual_check(lat)))
        else:
            out.append(seg)
        cur += len(seg)
    return "".join(out)


_INLINE_CODE = re.compile(r"`([^`\n]+)`")


def _is_heading_formula(t):
    """标题里的公式片段判定（比正文更严）。

    🔴 `### 9.2 A / B 两类不确定度` 里的 A/B 是章节号，不是分式；
       但 `### …而不是 v² 阻尼` 里的 v² 是真公式。
    """
    if re.search(r"[\u0391-\u03a9\u03b1-\u03c9\u00b2\u00b3\u2070-\u209c]", t):
        return True
    sig = set(re.findall(STRUCT_RE, t))
    sig.discard("/")
    return bool(sig)


def _fix_prose_line(line, ln, changes):
    """处理一行普通正文。

    🔴 markdown 结构标记必须先剥掉，否则 `|`、`>`、`###` 会被当成公式的一部分。
    """
    quote, head, body = _split_prefix(line)
    if head:
        # 标题行：只改「明确的公式片段」，避免 "### 9.2 A / B" 被吃成公式
        out = []
        for is_cjk, seg in _split_cjk(body):
            if is_cjk or not seg.strip():
                out.append(seg)
                continue
            lead, frag, trail = _trim_frag(seg)
            # 🔴 已经是行内/围栏公式的片段：**原样保留**。
            #    `to_latex` 会把 `$` 当 LaTeX 特殊字符转义成 `\$`
            #    （见 `_rest` 末尾的转义表），于是标题里的
            #    `$v^{2}$` 变成 `\$v^{2}\$` —— 渲染出来是一对美元符号，
            #    而且第二遍还会再改一次 ⇒ 不幂等。
            if frag and (_INLINE_MATH.fullmatch(frag)
                         or _DISPLAY_WRAP.match(frag)):
                out.append(seg)
            elif frag and _is_heading_formula(frag) and is_formula_line(frag):
                lat = to_latex(frag)
                out.append("%s$%s$%s" % (lead, lat, trail))
                changes.append(Change(ln, "B_标题内公式", seg.strip(), "$%s$" % lat,
                                      lat, residual_check(lat)))
            else:
                out.append(seg)
        return line[:len(line) - len(body)] + "".join(out)
    cells = _split_table_row(body)
    if cells is not None:
        out = []
        for cell in cells:
            out.append(_fix_text_body(cell, ln, changes, allow_display=False))
        return quote + "|".join(out)
    return quote + _fix_text_body(body, ln, changes)


def _fix_display_body(line, ln, changes):
    """`$$ ... $$` 跨行围栏**内部**的一行：只规范化公式内容，不加围栏。

    🔴 围栏已经在外面了，这里再包一层 `$$` 就是嵌套 display math。
    """
    q, _h, body = _split_prefix(line)
    stripped = body.strip()
    if not stripped:
        return line
    # 单行内既有 `$$...$$` ⇒ 取出内部规范化，外面已有围栏就不要再加
    m = _DISPLAY_WRAP.match(stripped)
    if m:
        inner = m.group(1).strip()
        if not inner:
            return line
        lat = to_latex(inner)
        changes.append(Change(ln, "A_已有围栏公式段", inner, "$$%s$$" % lat,
                              lat, residual_check(lat)))
        return q + "$$%s$$" % lat
    if is_formula_line(stripped):
        lat = to_latex(stripped)
        changes.append(Change(ln, "A_已有围栏公式段", stripped, lat,
                              lat, residual_check(lat)))
        return q + lat
    # 围栏内不是公式 ⇒ 原样保留（可能是 \\begin{pmatrix} 之类的多行结构）
    return line


def _fix_text_body(body, ln, changes, allow_display=True):
    """正文主体：行内代码 + 中文里夹的公式。"""
    stripped = body.strip()
    # 🔴 源里已经有 $$ 围栏（独立成行的 display math）时，**不能再套一层**。
    #    否则嵌套 display math ⇒ 渲染器把内层当字面文本，
    #    实测 Jones 矢量整段消失、马吕斯定律渲染成 `I = I_{0} ^2`。
    m = _DISPLAY_WRAP.match(stripped)
    if m:
        inner = m.group(1).strip()
        if inner:
            lat = to_latex(inner)
            changes.append(Change(ln, "A_已有围栏公式段", inner, "$$%s$$" % lat,
                                  lat, residual_check(lat)))
            return "$$%s$$" % lat
        return stripped
    # 🔴 整段已经是**行内公式** `$…$` 时：保持行内，**不要**再套一层。
    #    套一层的代价比想象中大：`to_latex` 会把 `$` 当 LaTeX 特殊字符转义成 `\$`
    #    （见 `_rest` 末尾的转义表），于是结果变成 `$$\$x\$\$$` ——
    #    而且**第二遍还会再改一次**（再转义、再套层）⇒ 规范化**不幂等**。
    #    不幂等 ⇒ 派生产物重算一次就变形 ⇒ 「讲义讲稿 ≠ 课件讲稿」凭空出现。
    im = _INLINE_MATH.fullmatch(stripped)
    if im:
        inner = im.group(1).strip()
        if inner:
            lat = to_latex(inner)
            changes.append(Change(ln, "B_已有行内公式", inner, "$%s$" % lat,
                                  lat, residual_check(lat)))
            # 🔴 **首尾空白必须原样保留**。
            #    表格单元是 `| $\omega_{0}$ | 说明 |` ——
            #    单元格内容被 strip 过，若返回时把空白丢了，
            #    就变成 `|$\omega_{0}$| 说明 |`：markdown 表格仍然成立，
            #    但**每跑一遍规范化，表格就变形一次** ⇒ 不幂等。
            lead = body[:len(body) - len(body.lstrip())]
            trail = body[len(body.rstrip()):]
            return "%s$%s$%s" % (lead, lat, trail)
        return body
    if allow_display and stripped and is_formula_line(stripped):
        lat = to_latex(stripped)
        changes.append(Change(ln, "A_独立公式段", stripped, "$$%s$$" % lat,
                              lat, residual_check(lat)))
        return "$$%s$$" % lat

    out = []
    pos = 0
    for m in _INLINE_CODE.finditer(body):
        out.append(_fix_plain(body[pos:m.start()], ln, changes))
        frag = m.group(1).strip()
        if is_formula_line(frag):
            lat = to_latex(frag)
            out.append("$%s$" % lat)
            changes.append(Change(ln, "A_行内代码", frag, "$%s$" % lat,
                                  lat, residual_check(lat)))
        else:
            out.append(m.group(0))
        pos = m.end()
    out.append(_fix_plain(body[pos:], ln, changes))
    return "".join(out)


def _emit_code_block(buf, start_line, changes, fence_line):
    """把一个 ``` 代码块转成 display math。

    🔴 代码块里的公式**必须移出围栏**——围栏里的 `$...$` 不会被排版。
    🔴 但真正的代码块（python/bash）必须原样保留，绝不能当公式改。
    🔴 速查卡一行里可能有多个公式（用 2+ 空格分隔）⇒ 拆成多个 display。
    """
    q, _h, fence_body = _split_prefix(fence_line)
    lang = fence_body.strip().lstrip("`").strip().lower()
    raw = []
    for l in buf:
        _, _, b = _split_prefix(l)
        raw.append(b)
    if not any(l.strip() for l in raw):
        return list(buf)
    # ① 代码块 → 原样保留
    if lang in CODE_LANGS or any(_CODE_HINT.search(l) for l in raw if l.strip()):
        return list(buf)

    out = []
    for k, line in enumerate(raw):
        ln = start_line + k
        if not line.strip():
            out.append(q.rstrip() if q.strip() else "")
            continue
        # 标签：行首中文 + 2+ 空格（速查卡："三参数     γ = c/(2m) ..."）
        label = ""
        rest = line
        m = re.match(r"^(\s*[^\x00-\x7f]{1,16}?)\s{2,}(\S.*)$", line)
        if m and CJK_RE.search(m.group(1)):
            label = m.group(1).strip()
            rest = m.group(2)
            out.append(q + label)

        # 公式中间夹了中文 ⇒ 整行不可自动转写（拆开会产生残缺的公式）
        # 🔴 区分「中文在公式中间」和「公式后面跟中文说明」：
        #    `ln γ = 常数 + n·ln(参数)`  ⇒ 中间，不能拆
        #    `γ = c/(2m)      衰减速率`  ⇒ 后面，是说明文字，可以拆
        segs = _split_cjk(rest)
        mid_cjk = False
        for i2, (is_cjk, _seg) in enumerate(segs):
            if not is_cjk or i2 == 0:
                # 第一个 CJK 段是「其中」「三参数」这类引导词，不是夹在公式中间
                continue
            for _j, (is_cjk2, seg2) in enumerate(segs[i2 + 1:], i2 + 1):
                if is_cjk2:
                    continue
                if re.search(r"[=\u221d\u27f9\u2192\u00b7^\u221a]|[\u0391-\u03a9\u03b1-\u03c9]", seg2):
                    mid_cjk = True
                break
        if mid_cjk:
            changes.append(Change(ln, "C_公式夹中文", line.strip(), line.strip(), None,
                                  ["公式中间夹了中文（需要 \\text{}），未自动改造"]))
            out.append(q + line)
            continue

        # 拆块：CJK 段 + 2+ 空格分段
        items = []
        for is_cjk, seg in _split_cjk(rest):
            if is_cjk:
                items.append(("text", seg))
                continue
            for part in re.split(r"\s{2,}", seg):
                p = part.strip()
                if p:
                    items.append(("raw", p))

        # 合并：运算符片段接到公式链上；公式链整体算一条
        merged = []
        pending_op = ""
        for kind, t in items:
            if kind == "raw" and _OPERATOR_ONLY.match(t):
                pending_op = (pending_op + " " + t).strip()
                continue
            if kind == "raw" and is_formula_line(t):
                if pending_op:
                    if merged and merged[-1][0] == "math":
                        merged[-1] = ("math", merged[-1][1] + " " + pending_op + " " + t)
                        pending_op = ""
                        continue
                    t = pending_op + " " + t
                    pending_op = ""
                merged.append(("math", t))
                continue
            if pending_op:
                if merged and merged[-1][0] == "math":
                    merged[-1] = ("math", merged[-1][1] + " " + pending_op)
                pending_op = ""
            merged.append(("text", t))

        text_buf = []
        for kind, t in merged:
            if kind == "math":
                # 🔴 已经是 `$$…$$` 的公式：**原样保留**。
                #    再套一层 + `to_latex` 转义 `$` ⇒ `$$\$…\$\$$`，
                #    而且第二遍还会再改一次 ⇒ 规范化不幂等。
                #    （围栏里装着上一轮已经转写好的公式，是**正常**的输入 ——
                #      规范化后的文档再规范化一次，遇到的就是它。）
                if _DISPLAY_WRAP.match(t.strip()):
                    if text_buf:
                        out.append(q + "".join(text_buf).strip())
                        text_buf = []
                    out.append(q + t.strip())
                    continue
                if text_buf:
                    out.append(q + "".join(text_buf).strip())
                    text_buf = []
                lat = to_latex(t)
                out.append(q + "$$%s$$" % lat)
                changes.append(Change(ln, "A_代码块公式", t.strip(), "$$%s$$" % lat,
                                      lat, residual_check(lat)))
            else:
                # 公式中间夹了中文 ⇒ 自动转写不了，标出来让人处理
                if re.search(r"[=\u221d\u2192\u00b7^\u221a]|[Α-Ωα-ω]", t):
                    changes.append(Change(
                        ln, "C_公式夹中文", t.strip(), t.strip(), None,
                        ["公式中间夹了中文（需要 \\text{}），未自动改造"]))
                text_buf.append(t)
        if text_buf:
            out.append(q + "".join(text_buf).strip())
    return out


def fix_text(text):
    """把伪公式改写成 LaTeX。返回 (新文本, 变更列表)。"""
    lines = text.split("\n")
    out = []
    changes = []
    i = 0
    in_code = False
    code_buf = []
    code_start = 0
    fence_line = ""
    in_display = False        # 🔴 处在 `$$ ... $$` 跨行围栏里
    while i < len(lines):
        line = lines[i]
        _q, _h, stripped = _split_prefix(line)
        if stripped.startswith("```"):
            if not in_code:
                in_code = True
                code_buf = []
                code_start = i + 2      # 🔴 1-based 的首行内容行号
                fence_line = line
                i += 1
                continue
            in_code = False
            # 🔴 开围栏行必须原样写回：`_emit_code_block` 只返回**块内容**，
            #    围栏本身要在这里补上，否则代码块会失去围栏 ⇒ 变成正文 ⇒
            #    变量名的 `_` 被转义、`*` 被转义，代码直接被改坏。
            out.append(fence_line)
            out.extend(_emit_code_block(code_buf, code_start, changes, fence_line))
            out.append(line)
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue
        # 🔴 `$$` 跨行围栏：块内已经是 display math，只做规范化、不再套一层。
        #    再套一层会变成嵌套 display math ⇒ 渲染器把内层当字面文本
        #    （实测 Jones 矢量整段消失、马吕斯定律渲染成 `I = I_{0} ^2`）。
        if stripped.strip() == "$$":
            in_display = not in_display
            out.append(line)
            i += 1
            continue
        if in_display:
            out.append(_fix_display_body(line, i + 1, changes))
            i += 1
            continue
        out.append(_fix_prose_line(line, i + 1, changes))
        i += 1
    if in_code and code_buf:
        out.append(fence_line)
        out.extend(_emit_code_block(code_buf, code_start, changes, fence_line))
    return "\n".join(out), changes


def find_spans(text):
    """找出文本里**可自动转写**的公式片段及其绝对位置。

    返回 [(start, end, latex)]；start/end 是 text 里的字符下标。

    🔴 只收 A/B 类（整段公式、含结构信号的行内公式），
       单个裸变量（C 类）不收——误伤风险太高。
    """
    spans = []
    _fix_plain(text, 0, [], spans=spans, base=0)
    return spans


# 旧约定残留：公式写成纯文本 —— 与新约定（LaTeX）直接冲突
CONVENTION_PATTERNS = [
    (r"公式[^。\n]{0,12}一律[^。\n]{0,8}纯文本", "「公式一律写成纯文本」"),
    (r"带\s*`?·`?\s*的是乘号", "「带 · 的是乘号」"),
    (r"公式[^。\n]{0,10}写成[^。\n]{0,6}文本", "「公式写成文本」"),
]

# 建议的替换措辞
CONVENTION_FIX = ("公式一律用 LaTeX 写（行内 `$...$`、独立成行 `$$...$$`），"
                  "由排版管线渲染成真正的公式；乘号写作 `\\cdot`，分式写作 `\\frac{}{}`。")


def find_convention_conflicts(text):
    """找出与「LaTeX 公式约定」冲突的旧措辞。返回 [(行号, 命中的措辞)]。"""
    hits = []
    for ln, line in enumerate(text.split("\n"), 1):
        for pat, name in CONVENTION_PATTERNS:
            if re.search(pat, line):
                hits.append((ln, name, line.strip()[:120]))
                break
    return hits


def find_bare_vars(text):
    """C 类：中文正文里夹的单个裸变量（只报告，不改）。"""
    found = []
    for ln, line in enumerate(text.split("\n"), 1):
        for m in re.finditer(RULE_DESC and r"([\u4e00-\u9fff])\s*([A-Za-z\u0391-\u03a9\u03b1-\u03c9])\s*"
                             r"(?=[\u4e00-\u9fff\uff0c\u3002\u3001\uff1b\uff1a\uff08\u300c\u300d])",
                             line):
            found.append((ln, m.group(0), "$%s$" % m.group(2)))
    return found


# ══════════════════════════════════════════════════════════════════
# 7. 扫描
# ══════════════════════════════════════════════════════════════════

class Finding(object):
    def __init__(self, rid, line, col, snippet, latex=None, in_code=False):
        self.rid = rid
        self.line = line
        self.col = col
        self.snippet = snippet
        self.latex = latex
        self.in_code = in_code

    def as_dict(self):
        return {"rule": self.rid, "desc": RULE_DESC.get(self.rid, ""),
                "line": self.line, "col": self.col, "snippet": self.snippet,
                "latex": self.latex, "in_code": self.in_code}


def scan_text(text):
    """扫描一段文本，返回 Finding 列表。"""
    findings = []
    lines = text.split("\n")
    in_code = False
    for ln, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        for rid, desc, pat in RULES:
            for m in re.finditer(pat, line):
                frag = m.group(0)
                if not frag.strip():
                    continue
                if rid == "var_in_cjk":
                    frag = m.group(2)
                if rid == "slash_frac" and m.lastindex and m.lastindex >= 2:
                    den = m.group(2).rstrip("\u2080-\u209c")
                    if den in UNIT_TOKENS and not re.search(r"[\u00b2\u00b3\u2080-\u209c]", m.group(2)):
                        continue
                if rid == "func_name" and re.search(r"[A-Za-z]", m.group(0)[1:-1]):
                    pass
                lat = to_latex(frag) if rid != "var_in_cjk" else "$%s$" % frag
                findings.append(Finding(rid, ln, m.start() + 1, frag, lat, in_code))
    return findings


def scan_file(path, as_json=False):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    if not as_json:
        return scan_text(raw)
    findings = []
    try:
        data = json.loads(raw)
    except Exception as e:
        raise SystemExit("JSON 解析失败：%s" % e)

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, path + [str(k)])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + [str(i)])
        elif isinstance(node, str):
            for f in scan_text(node):
                f.snippet = "%s :: %s" % ("/".join(path), f.snippet)
                findings.append(f)
    walk(data, [])
    return findings


# ══════════════════════════════════════════════════════════════════
# 8. 外部验证：pandoc / typst 实测公式能不能落地
# ══════════════════════════════════════════════════════════════════

class _ProcResult(object):
    """subprocess 结果的最小替身：工具缺失时也能安全读 returncode / stderr。"""

    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _run(cmd, **kw):
    """跑外部命令。

    🔴 工具**没装**时 subprocess 会抛 FileNotFoundError，直接崩掉整个脚本。
       外部用户的机器上没装 pandoc/typst 是常态 ⇒ 这里兜住，
       转换成 returncode=127 + 可读的 stderr，让上层如实标「这一步没跑成」。
    """
    try:
        return subprocess.run(cmd, capture_output=True, text=True, **kw)
    except FileNotFoundError:
        exe = cmd[0] if cmd else "?"
        return _ProcResult(
            127, "",
            "未找到可执行文件：%s\n"
            "请先安装它（pandoc: https://pandoc.org/installing.html ；"
            "typst: https://typst.app/），或用环境变量指定路径。" % exe)
    except OSError as e:
        return _ProcResult(126, "", "执行 %s 失败：%s" % (cmd[0] if cmd else "?", e))


def _find_typst():
    """找 typst 可执行文件：PATH → 常见安装位置 → 环境变量 TYPST。

    找不到就返回 None（validate 会跳过 typst 这一步并如实标注跳过），
    不要假装验证过。
    """
    import shutil as _sh
    p = _sh.which("typst")
    if p:
        return p
    env = os.environ.get("TYPST")
    if env and os.path.exists(env):
        return env
    # 常见安装位置（不写死任何人的个人路径——那种路径对外来用户毫无意义）
    for c in (r"C:\Program Files\Typst\typst.exe",
              os.path.expanduser(r"~\AppData\Local\Programs\Typst\typst.exe"),
              "/usr/local/bin/typst", "/opt/homebrew/bin/typst",
              os.path.expanduser("~/.cargo/bin/typst")):
        if os.path.exists(c):
            return c
    return None


def validate_markdown(path):
    """把一个 markdown 里的公式过一遍真实管线（pandoc→typst→typst compile、pandoc→docx）。

    返回 (ok, report_dict)。
    """
    report = {"file": path, "ok": True, "steps": []}
    with open(path, encoding="utf-8") as f:
        text = f.read()
    n_math = text.count("$$") // 2 + len(re.findall(r"(?<!\$)\$(?!\$)", text)) // 2
    report["math_blocks"] = n_math

    tmp = tempfile.mkdtemp(prefix="fmlnorm_")
    md = os.path.join(tmp, "probe.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write(text)

    # ① pandoc → typst
    # 🔴 没装 pandoc ⇒ 标「跳过」而不是「失败」：
    #    本机缺工具 ≠ 公式有问题，混为一谈会让使用者误判自己的文件。
    typ = os.path.join(tmp, "probe.typ")
    r = _run(["pandoc", "-f", "markdown", "-t", "typst", md, "-o", typ])
    if r.returncode == 127:
        report["steps"].append({
            "name": "pandoc→typst", "ok": None,
            "skipped": "未找到 pandoc 可执行文件（未安装）——这一步没跑，不代表公式有问题"})
        report["pandoc_skipped"] = True
    else:
        step = {"name": "pandoc→typst", "ok": r.returncode == 0}
        if r.returncode != 0:
            step["stderr"] = (r.stderr or "").strip()[:2000]
        report["steps"].append(step)
        report["ok"] = report["ok"] and step["ok"]

    # ② typst compile（编 PDF；多页导出 PNG 需要页码模板，用 PDF 更稳）
    pdf = os.path.join(tmp, "probe.pdf")
    typst = _find_typst()
    if typst and not report.get("pandoc_skipped"):
        r = _run([typst, "compile", typ, pdf])
        step = {"name": "typst compile", "ok": r.returncode == 0}
        if r.returncode != 0:
            step["stderr"] = (r.stderr or "").strip()[:2000]
        report["steps"].append(step)
        report["ok"] = report["ok"] and step["ok"]
        report["pdf_bytes"] = os.path.getsize(pdf) if os.path.exists(pdf) else 0
    elif report.get("pandoc_skipped"):
        report["steps"].append({
            "name": "typst compile", "ok": None,
            "skipped": "上游 pandoc→typst 没跑成（缺 pandoc），这一步无从谈起"})
        report["typst_skipped"] = True
    else:
        # 🔴 找不到 typst 就如实标「跳过」，不要让人以为验证过了
        report["steps"].append({"name": "typst compile", "ok": None,
                                "skipped": "未找到 typst 可执行文件（PATH / TYPST 环境变量 / 常见安装位置都没有）"})
        report["typst_skipped"] = True

    # ③ pandoc → docx，检查 OMML 数量
    docx = os.path.join(tmp, "probe.docx")
    r = _run(["pandoc", "-f", "markdown", "-t", "docx", md, "-o", docx])
    if r.returncode == 127:
        report["steps"].append({
            "name": "pandoc→docx", "ok": None,
            "skipped": "未找到 pandoc 可执行文件（未安装）——这一步没跑，不代表公式有问题"})
        report["pandoc_skipped"] = True
    else:
        step = {"name": "pandoc→docx", "ok": r.returncode == 0}
        if r.returncode != 0:
            step["stderr"] = (r.stderr or "").strip()[:2000]
        report["steps"].append(step)
        report["ok"] = report["ok"] and step["ok"]
    if os.path.exists(docx):
        import zipfile
        try:
            with zipfile.ZipFile(docx) as z:
                xml = z.read("word/document.xml").decode("utf-8")
            report["omml"] = {
                "oMath": xml.count("<m:oMath"),
                "frac": xml.count("<m:f>"),
                "rad": xml.count("<m:rad>"),
                "nary": xml.count("<m:nary>"),
                "delimiter": xml.count("<m:d>"),
            }
        except Exception as e:
            report["omml_error"] = str(e)
    # 🔴 全部步骤都跳过 ⇒ 不能报 ok:true（那会让人以为「验证过了」）。
    #    明确区分三种状态：真跑过且通过 / 真跑过但失败 / 根本没跑。
    ran = [s for s in report["steps"] if s.get("ok") is not None]
    if not ran:
        report["ok"] = None
        report["not_verified"] = True
    report["verified_steps"] = len(ran)
    report["tmpdir"] = tmp
    return report["ok"], report


# ══════════════════════════════════════════════════════════════════
# 9. 自测（回归）
# ══════════════════════════════════════════════════════════════════

SELFTEST_CASES = [
    ("\u03b5 = \u2212BLv", r"\varepsilon = -BLv"),
    ("i = \u03b5/R", r"i = \frac{\varepsilon}{R}"),
    ("F = \u2212BL\u00b7(\u03b5/R) = \u2212BL\u00b7(\u2212BLv/R) = \u2212(B\u00b2L\u00b2/R)\u00b7v = \u2212cv",
     r"F = -BL \cdot \frac{\varepsilon}{R} = -BL \cdot \frac{-BLv}{R} = -\frac{B^{2}L^{2}}{R} \cdot v = -cv"),
    ("m\u00b7\u1e8d + c\u00b7\u1e8b + k\u00b7x = 0",
     r"m \cdot \ddot{x} + c \cdot \dot{x} + k \cdot x = 0"),
    ("\u03b3 = c/(2m)", r"\gamma = \frac{c}{2m}"),
    ("\u03c9\u2080 = \u221a(k/m)", r"\omega_{0} = \sqrt{\frac{k}{m}}"),
    ("\u03b6 = \u03b3/\u03c9\u2080", r"\zeta = \frac{\gamma}{\omega_{0}}"),
    ("\u03c9_d = \u221a(\u03c9\u2080\u00b2 \u2212 \u03b3\u00b2)",
     r"\omega_{d} = \sqrt{\omega_{0}^{2} - \gamma^{2}}"),
    ("x(t) = A\u2080\u00b7e^(\u2212\u03b3t)\u00b7cos(\u03c9_d\u00b7t + \u03c6)",
     r"x(t) = A_{0} \cdot e^{-\gamma t} \cdot \cos (\omega_{d} \cdot t + \varphi)"),
    ("\u039b = ln(x\u2099 / x\u2099\u208a\u2081)", r"\Lambda = \ln \frac{x_{n}}{x_{n+1}}"),
    ("\u039b = \u03b3\u00b7T_d", r"\Lambda = \gamma \cdot T_{d}"),
    ("T_d = 2\u03c0 / \u03c9_d", r"T_{d} = \frac{2\pi}{\omega_{d}}"),
    ("\u03b3 = c/(2m) = N\u00b2\u00b7\u03bc\u00b2\u00b7L\u00b2 / (2m\u00b7R)",
     r"\gamma = \frac{c}{2m} = \frac{N^{2} \cdot \mu^{2} \cdot L^{2}}{2m \cdot R}"),
    ("1/ln10 \u2248 0.434", r"\frac{1}{\ln 10} \approx 0.434"),
    ("\u03b8\u0302 = argmin \u2211 [ y_i \u2212 f(x_i; \u03b8) ]\u00b2",
     r"\hat{\theta} = \operatorname{argmin} \sum [ y_{i} - f(x_{i}; \theta) ]^{2}"),
    ("u_c = \u221a( \u2211 u_i\u00b2 )", r"u_{c} = \sqrt{\sum u_{i}^{2}}"),
    ("\u03b5 = \u2212B(x)\u00b7L\u00b7v", r"\varepsilon = -B(x) \cdot L \cdot v"),
    ("\u03b3 \u221d (1/R) \u00b7 N\u00b2 \u00b7 \u03bc\u00b2",
     r"\gamma \propto \frac{1}{R} \cdot N^{2} \cdot \mu^{2}"),
]


# ══════════════════════════════════════════════════════════════════
# 9b. 文档级回归（fix_text 全流程）
# ══════════════════════════════════════════════════════════════════
# 🔴 这批用例来自一轮真实 eval：单元级 to_latex 测试**全部通过**，
#    但 fix_text 在整篇文档上产出了坏结果。
#    ⇒ 凡是"在整篇文档上才暴露"的问题，必须在这一层设回归。
#
# 每条 = (用例名, 源文本, 输出里必须出现的片段, 输出里必须不出现的片段)
DOC_TEST_CASES = [
    ("D1 已有 $$ 围栏不二次包裹",
     "$$\nI = I_0 \\cos^2\\theta\n$$\n",
     ["$$\nI = I_{0} \\cos^2\\theta\n$$"],
     ["$$$$", "$$I = I_{0}"]),

    ("D2 行内已有 $ 不变双美元",
     "其中 $E_0$ 是振幅。\n",
     ["其中 $E_{0}$ 是振幅。"],
     ["$$E_{0}$$"]),

    ("D3 LaTeX 命令不被斜杠切开",
     "当 $\\delta = \\pi/2$ 时称为四分之一波片。\n",
     ["$\\delta = \\pi/2$"],
     ["\\\\frac{pi}{2}", "\\frac{pi}{2}"]),

    ("D4 多字符下标整体收组",
     "相对误差定义为 $\\delta_rel = x$。\n",
     ["\\delta_{\\mathrm{rel}}"],
     ["\\delta_{r}el"]),

    ("D5 代码块围栏与内容原样保留",
     "前面。\n\n```python\nomega_0 = 2 * np.pi\n```\n\n后面。\n",
     ["```python", "omega_0 = 2 * np.pi", "```"],
     ["\\_", "\\*"]),

    ("D6 围栏内多行结构不被破坏",
     "$$\n\\begin{pmatrix} \\cos\\theta \\\\ \\sin\\theta \\end{pmatrix}\n$$\n",
     ["\\begin{pmatrix}", "\\end{pmatrix}"],
     ["$$\\begin{pmatrix}"]),

    ("D7 数值+量纲不算公式",
     "拟合得到的 I0_hat 与理论值 3.2 W/m\u00b2 相差约 5%。\n",
     ["3.2 W/m\u00b2 相差"],
     ["$3.2 W/m^{2}$"]),

    ("D8 字母开头的仍是公式",
     "阻尼系数 c = B\u00b2L\u00b2/R 是常数。\n",
     ["\\frac{B^{2}L^{2}}{R}"],
     []),

    ("D9 整段行内公式不被套层、不被转义",
     "$\\varepsilon = -BLv$\n",
     ["$\\varepsilon = -BLv$"],
     ["$$", "\\$"]),

    ("D10 代码块里已是围栏公式时不重复包裹",
     "```\n$$\\varepsilon = -BLv$$\n```\n",
     ["$$\\varepsilon = -BLv$$"],
     ["\\$\\$"]),

    # 🔴 「A/B 类」是**两类并列**（计量学 GUM：A 类不确定度 / B 类不确定度），
    #    转成 \frac{A}{B} 会把「两类」说成「A 除以 B」——**语义被改错**。
    #    这类误报比漏转严重：漏转只是排版朴素，改错是意思变了。
    ("D11 类别并列不是除法",
     "A/B 类不确定度\n",
     ["A/B 类不确定度"],
     ["\\frac{A}{B}", "$A/B$"]),

    ("D12 类别并列在正文中间也不转",
     "非线性拟合与 A/B 类不确定度现场计算。\n",
     ["与 A/B 类不确定度现场计算"],
     ["\\frac{A}{B}"]),

    ("D13 真分式照转（大写单字母且无类别标记）",
     "V/I 是电压电流比。\n",
     ["\\frac{V}{I}"],
     []),

    # 🔴 「≥2 min」是**阈值 + 单位**，不是公式。
    #    转成 `$\geq 2 \min$` 会把「2 分钟」说成「2 倍最小值」（`\min` 是最小值算子），
    #    而且与 D7 自相矛盾：`5 s`、`30 min` 都不转，只因为前面多个 `≥` 就转了。
    ("D14 阈值（比较符+数值+量纲）保持纯文本",
     "每个模块结束留 ≥2 min 提问与停顿纠错窗口\n",
     ["≥2 min 提问与停顿纠错窗口"],
     ["\\min", "\\geq"]),

    # 🔴 单位词 `min`（分钟）不许被映射成 LaTeX 算子 `\min`（最小值）。
    #    这是「函数名 → 直立命令」这条通则的例外：min/max/sec 兼作普通词或单位。
    ("D15 单位 min 不被映射成 \\min 算子",
     "采样周期 t = 2 min。\n",
     ["2 min"],
     ["\\min"]),
]


# 🔴 **幂等回归**：规范化跑两遍，第二遍必须**一字不改**。
#
# 为什么这是硬要求：派生产物会被**反复重算**（增量重生成、重新构建、
# 交叉验证）。不幂等 ⇒ 每重算一次公式就变形一次 ⇒
# 「讲义讲稿 ≠ 课件讲稿」这类**同源判据**会凭空变红，
# 而变红的原因还完全看不出来（公式看起来是对的，只是多了一层 `\$`）。
#
# 实测踩过的坑：`to_latex` 会把 `$` 当 LaTeX 特殊字符转义成 `\$`，
# 于是「已带定界符的公式」被再套一层、再转义 ⇒ `$$\$x\$\$$`，
# 第二遍再改一次 ⇒ 永远收敛不了。
IDEMPOTENT_TEST_CASES = [
    ("整段行内公式", "$\\varepsilon = -BLv$\n"),
    ("整段围栏公式", "$$\\varepsilon = -BLv$$\n"),
    ("代码块里的围栏公式", "```\n$$\\varepsilon = -BLv$$\n```\n"),
    ("行内公式夹中文",
     "判据 $\\frac{\\tau}{T_{0}} < 0.1$ 的物理含义：电路的时间常数要短。\n"),
    ("表格单元里的公式",
     "| 忽略自感 | 电路时间常数 $\\frac{\\tau}{T_{0}} < 0.1$ | 电流滞后 |\n"),
    ("伪公式整行", "c = B\u00b2L\u00b2/R\n"),
    ("伪公式夹中文", "品质因数 Q = \u03c9\u2080L/R 与说明。\n"),
    # 🔴 类别并列（A/B 类）**不能**变成 \frac{A}{B}：
    #    语义从「两类」变成「相除」，而且改完就再也看不出来原来是什么意思。
    ("类别并列不转分式", "A/B 类不确定度\n"),
    ("类别并列在正文中间", "示范把 A/B 类不确定度分成两项。\n"),
    # 🔴 阈值跑两遍必须一字不改（否则「≥2 min」会在第二遍变成公式）
    ("阈值不转公式", "每个模块结束留 ≥2 min 提问与停顿纠错窗口\n"),
]


def selftest():
    print("=== formula_norm 自测 ===")
    ok = 0
    bad = []
    for src, want in SELFTEST_CASES:
        got = to_latex(src)
        if got == want:
            ok += 1
        else:
            bad.append((src, want, got))
    print("用例 %d 条，通过 %d 条" % (len(SELFTEST_CASES), ok))
    for src, want, got in bad:
        print("\n  ✗ 源:   %s" % src)
        print("    期望: %s" % want)
        print("    实际: %s" % got)
    # 片段判定
    cases = [
        ("\u00b7", False, "单个中点不是公式"),
        ("\u5e26 \u00b7 \u7684\u662f\u4e58\u53f7", False, "中文句子不是公式"),
        ("c\u00b7\u1e8b", True, "c·ẋ 是公式"),
        ("rad/s", False, "量纲不是公式"),
        ("N\u00b7s/m", False, "量纲不是公式"),
        ("v", False, "单个变量不算公式（只报告）"),
        # 🔴 阈值（比较符 + 数值 + 单位）不是公式：`≥2 min` = 至少 2 分钟。
        ("≥2 min", False, "阈值不是公式（单位会被误当算子）"),
        ("≥ 25 °C", False, "阈值不是公式"),
        ("≥2π", True, "带希腊字母的是公式不是阈值"),
        ("\u03b5 = \u2212BLv", True, "整行公式"),
    ]
    print("\n--- 片段判定 ---")
    for s, want, why in cases:
        got = is_formula_line(s)
        flag = "\u2713" if got == want else "\u2717"
        print("  %s %-22s %s" % (flag, repr(s), why))
        if got != want:
            bad.append((s, want, got))
    # 文档级回归（整篇文档才暴露的问题）
    print("\n--- 文档级回归 ---")
    doc_ok = 0
    for (name, src, must, mustnot) in DOC_TEST_CASES:
        got, _changes = fix_text(src)
        missing = [m for m in must if m not in got]
        present = [m for m in mustnot if m in got]
        if missing or present:
            bad.append((name, "must=%s" % must, "got=%r missing=%s present=%s"
                        % (got, missing, present)))
            print("  ✗ %s" % name)
            print("    输出: %r" % got)
            if missing:
                print("    缺少: %s" % missing)
            if present:
                print("    不该出现: %s" % present)
        else:
            doc_ok += 1
            print("  ✓ %s" % name)
    print("文档级用例 %d 条，通过 %d 条" % (len(DOC_TEST_CASES), doc_ok))

    # ── 幂等回归 ──────────────────────────────────────────────
    print("\n--- 幂等回归（跑两遍必须一字不改）---")
    idem_ok = 0
    for (name, src) in IDEMPOTENT_TEST_CASES:
        once, _c1 = fix_text(src)
        twice, _c2 = fix_text(once)
        if once != twice:
            bad.append((name, "幂等", "第一遍 %r ／ 第二遍 %r" % (once, twice)))
            print("  ✗ %s" % name)
            print("    第一遍: %r" % once)
            print("    第二遍: %r" % twice)
        else:
            idem_ok += 1
            print("  ✓ %s" % name)
    print("幂等用例 %d 条，通过 %d 条" % (len(IDEMPOTENT_TEST_CASES), idem_ok))
    return 0 if not bad else 1


# ══════════════════════════════════════════════════════════════════
# 10. CLI
# ══════════════════════════════════════════════════════════════════

def _report_markdown(changes, bare_vars, src_path, conflicts=None):
    lines = ["# 公式规范化对照报告", "",
             "源文件：`%s`" % src_path, "",
             "自动改造 **%d** 处，其中 **%d** 处自评未通过（需人工复核）。" %
             (len(changes), sum(1 for c in changes if c.review)), ""]
    if changes:
        lines += ["## 逐条对照", "",
                  "| 行 | 类型 | 原文 | 建议 | 自评 |",
                  "|---|---|---|---|---|"]
        for c in changes:
            resid = "、".join(c.residuals) if c.residuals else "✓ 通过"
            lines.append("| %d | %s | `%s` | `%s` | %s |" %
                         (c.line, c.kind, c.before.replace("|", "\\|"),
                          c.after.replace("|", "\\|"), resid))
        lines.append("")
    if bare_vars:
        lines += ["## 中文正文里的裸变量（只报告，未自动改）", "",
                  "| 行 | 上下文 | 建议 |", "|---|---|---|"]
        for ln, ctx, sug in bare_vars:
            lines.append("| %d | `%s` | `%s` |" %
                         (ln, ctx.replace("|", "\\|"), sug))
        lines.append("")
    if conflicts:
        lines += ["## ⚠ 书写约定冲突（改完公式后必须同步改这几行）", "",
                  "原文里还在说「公式写成纯文本」，与现在的 LaTeX 约定矛盾；",
                  "不改的话，读者（和后续的 AI）会按旧约定继续写伪公式。", "",
                  "| 行 | 旧措辞 | 原文 |", "|---|---|---|"]
        for ln, name, ctx in conflicts:
            lines.append("| %d | %s | `%s` |" %
                         (ln, name, ctx.replace("|", "\\|")))
        lines += ["", "建议统一改成：", "", "> %s" % CONVENTION_FIX, ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="伪公式检测器 + LaTeX 规范化转换器")
    ap.add_argument("mode", choices=["scan", "fix", "rules", "selftest", "validate"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--out", help="scan: JSON 报告；fix: 改造后的副本")
    ap.add_argument("--report", help="fix: 对照报告（markdown）")
    ap.add_argument("--json", action="store_true", help="按 JSON 规格扫描")
    ap.add_argument("--only", help="只看某一类规则")
    args = ap.parse_args()

    if args.mode == "rules":
        for rid, desc, pat in RULES:
            print("%-16s %-34s %s" % (rid, desc, pat))
        return 0

    if args.mode == "selftest":
        return selftest()

    if not args.path:
        raise SystemExit("缺少文件路径")
    if not os.path.exists(args.path):
        raise SystemExit("文件不存在：%s" % args.path)

    if args.mode == "validate":
        ok, rep = validate_markdown(args.path)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        # 退出码语义：0 = 跑过且通过；1 = 跑过但失败；2 = 根本没跑（缺工具）
        # 🔴 「没验证」不能算「通过」——否则调用方会以为文件是好的。
        if ok is None:
            return 2
        return 0 if ok else 1

    if args.mode == "scan":
        fs = scan_file(args.path, as_json=args.json)
        if args.only:
            fs = [f for f in fs if f.rid == args.only]
        by = {}
        for f in fs:
            by.setdefault(f.rid, []).append(f)
        print("=== %s ===" % args.path)
        print("命中 %d 处，涉及 %d 类规则\n" % (len(fs), len(by)))
        for rid, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
            print("【%s】%s —— %d 处" % (rid, RULE_DESC.get(rid, ""), len(items)))
            for f in items[:12]:
                code = " [在代码块内]" if f.in_code else ""
                print("   L%-4d %-30s → %s%s" % (f.line, f.snippet, f.latex, code))
            if len(items) > 12:
                print("   ... 还有 %d 处" % (len(items) - 12))
            print()
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump([f.as_dict() for f in fs], f, ensure_ascii=False, indent=2)
            print("JSON 报告：%s" % args.out)
        return 0

    # fix
    with open(args.path, encoding="utf-8") as f:
        text = f.read()
    new, changes = fix_text(text)
    bare = find_bare_vars(text)
    conflicts = find_convention_conflicts(text)
    out = args.out or (os.path.splitext(args.path)[0] + ".normalized.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(new)
    rep = args.report or (os.path.splitext(out)[0] + ".report.md")
    with open(rep, "w", encoding="utf-8") as f:
        f.write(_report_markdown(changes, bare, args.path, conflicts))

    print("=== 改造对照（%d 处，其中 %d 处需复核）===" %
          (len(changes), sum(1 for c in changes if c.review)))
    for c in changes:
        flag = "⚠" if c.review else "✓"
        print("%s L%-4d %-14s %-32s → %s" %
              (flag, c.line, c.kind, c.before.replace("\n", " "), c.after))
        if c.review:
            print("        残留：%s" % "、".join(c.residuals))
    print("\n已写出：%s" % out)
    print("对照报告：%s" % rep)
    if bare:
        print("另有 %d 处中文正文里的裸变量，只报告未改（见报告）。" % len(bare))
    print("⚠  自动转换是**尽力而为**，必须逐条复核后再采纳。")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
