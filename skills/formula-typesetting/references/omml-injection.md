# PPTX 注入 OMML 公式：配方、铁律与验收

> 目标：让 PPTX 里的公式成为 **PowerPoint 原生可编辑公式**（双击进公式编辑器），
> 而不是贴图片、不是 Unicode 伪公式。
> 配套脚本：`scripts/pptx_omml_inject.py`（`--scan` / `--spec` / `--dry-run`）。

---

## 1. 为什么必须注入 OMML

PPTX 里的"公式"有三种形态，只有第三种是真公式：

| 形态 | 双击能编辑 | 排版正确 | 说明 |
|---|---|---|---|
| 图片 | ✗ | 看运气 | 截图糊、放大糊、无法改 |
| Unicode 伪公式 | ✗ | ✗ | `e^(−γt)` 这种，渲染出来是脱字符 |
| **OMML（`<a14:m>`）** | ✓ | ✓ | Word/PowerPoint 原生公式对象 |

LaTeX → OMML 用本机已装的 **pandoc**（内含 texmath），零新增第三方依赖：

```
LaTeX --pandoc(texmath)--> <m:oMath> --字符串手术--> <a14:m>
```

不要用第三方 `latex2omml.py`：实测它 `\varepsilon` 出乱码、运算符没置立。
pandoc/texmath 的质量明显更高，且本机已装。

---

## 2. 三条铁律

### 铁律一：`a:p` 的子元素顺序

必须是：

```
pPr, (r | br | fld | a14:m)*, endParaRPr
```

⇒ 只能**就地替换** `<a:r>`，不能把公式节点搬到段落别处。

顺序错 ⇒ PowerPoint 打开时「修复」文件，并**无声删掉整个形状**。
不报错、不提示，用户只会发现内容凭空少了。

### 铁律二：`m:r` 内部顺序

必须是 `m:rPr, a:rPr, m:t`。

拼 `a:rPr` 时（带颜色/字号）必须**整段拼好再闭合**：

```
✅ '<a:rPr ...><a:solidFill><a:srgbClr val="1E293B"/></a:solidFill></a:rPr>'
❌ '<a:rPr .../>' + '<a:solidFill>...'      ← 闭合标签跑到 </a:rPr> 之后
```

第二种写法会在 `m:r` 里留下**游离的 `/>` 文本节点**。
PowerPoint 不报错，直接把它当字面量渲染出来——整页满屏 `/>`。

### 铁律三：一行一个公式用 inline `m:oMath`

不要用 `m:oMathPara`：PowerPoint 会把相邻的 `oMathPara` 合并，
多个独立公式会粘成一坨。

---

## 3. 🔴 偏移陷阱（实测踩到，本轮修掉）

用正则遍历 `<a:r>...</a:r>` 并**原地替换**时：

```python
# ❌ 错的
for m in re.finditer(r"<a:r>...", xml):        # 偏移量基于原始 xml
    xml = xml[:m.start()] + 新内容 + xml[m.end():]   # 替换后 xml 变长
```

公式片段比原文字长（`ω₀ = √(k/m)` → `\omega_{0} = \sqrt{\frac{k}{m}}`），
**每次替换都会让 xml 变长**，后面所有匹配的字节偏移全部错位。

实测后果：第 2 个公式被插进错误位置，**吃掉了表格单元格的 `<p:sp>` 标签**，
形状数从 19 掉到 17，XML 仍然合法但结构已坏 ⇒ PowerPoint 打开时会静默修复并删形状。

✅ 正确写法：先收集全部编辑，**从后往前**替换：

```python
edits = []
for m in re.finditer(r"<a:r>...", xml):
    edits.append((m.start(), m.end(), 新内容))
for (s, e, rep) in reversed(edits):          # 倒序 ⇒ 前面改动不影响后面偏移
    xml = xml[:s] + rep + xml[e:]
```

---

## 4. 注入配方

### 4.1 先扫描

```powershell
python scripts\pptx_omml_inject.py --scan 课件.pptx
```

输出 `part 路径 + 文本`，用来写 spec。备注页（`ppt/notesSlides/notesSlideN.xml`）
也在扫描范围内。

### 4.2 写 spec

```json
{
  "parts": [
    {"part": "ppt/slides/slide10.xml",
     "target": "c = B²L²/R",
     "latex": "\\frac{B^{2}L^{2}}{R}",
     "prefix": "阻尼系数 ",
     "suffix": "（由能量耗散等效）"},

    {"part": "ppt/slides/slide11.xml", "auto": true}
  ]
}
```

- `target`：该 part 里**单个 run 内**完整承载的文字。跨 run 拆开的文本匹配不到。
- `latex`：LaTeX 源码（JSON 里反斜杠要双写）。
- `prefix` / `suffix`：公式前后的文字。**整条 bullet 是公式时留空**；
  "文字 + 公式 + 文字" 时填上，得到真正的行内公式。
- `auto: true`：自动检测该 part 里的公式片段并行内注入（用 `formula_norm.find_spans` 定位）。
  备注页用这个最省事。`auto` 只收 A/B 类片段，单个裸变量不收。

### 4.3 注入

```powershell
# 先看会改成什么，不写文件
python scripts\pptx_omml_inject.py 课件.pptx 课件_公式版.pptx --spec spec.json --dry-run

# 真写
python scripts\pptx_omml_inject.py 课件.pptx 课件_公式版.pptx --spec spec.json
```

### 4.4 命名空间

根元素（`<p:sld>` 或 `<p:notes>`）要补：

```
xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main"
xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
mc:Ignorable="a14"
```

脚本的 `patch_root` 自动处理（已有则跳过）。

---

## 5. 验收判据

注入完**不能只看文件生成了**。按下面四条验：

| # | 判据 | 怎么查 | 合格线 |
|---|---|---|---|
| 1 | 形状数前后一致 | 数 `<p:sp>` / `<p:pic>` / `<p:graphicFrame>`，或比 `cNvPr id` 集合 | 完全相等 |
| 2 | XML 良构 | `xml.etree.ElementTree.fromstring` | 不抛 ParseError |
| 3 | 无游离 `/>` | 用**解析器**读 `m:t`/`a:t` 的 `.text`，查 `/>` | 0 处 |
| 4 | PowerPoint 实开不修复 | COM 打开，看有无修复提示 + 形状数 | 无提示、形状数一致 |

🔴 **判据 3 必须用解析器，不能用正则**。正则跨元素匹配会产生大量假阳性
（实测把正常的 `<m:fPr>` 结构误报成 4 处游离标记，解析器复核后真实数量是 0）。

🔴 **判据 1 的等价检查**：`cNvPr id` 集合比对比形状计数更严，能定位到**具体丢了哪个形状**
（实测靠它定位到丢失的是表格单元格 `Cell1_0`）。

### 关于 `TextFrame2.TextRange.MathZones.Count`

❌ **不能用它判断"是不是真公式"**——纯文本对照组同样报 `5`，存在假阳性。

✅ 有效判据组合：
1. 对照组与原版**逐像素一致**（证明对比公平）；
2. 形状数量前后一致（防静默删形状）；
3. 文本抽取形态变化（`ε = −BLv` → `𝜀=−𝐵𝐿𝑣`，数学斜体 Unicode）；
4. 渲染出现真分式/真重音（纯文本做不到）。

---

## 6. 脚本内置的守卫

`pptx_omml_inject.py` 在写文件前逐 part 校验：

- XML 必须良构（`ET.fromstring`）；
- 形状数必须与注入前相等；
- `cNvPr id` 集合不能少。

任一不满足就抛错、**不写文件**。理由：坏文件比没有文件更糟——
它会在用户打开时才炸，而且 PowerPoint 的表现是"静默删内容"，事后极难定位。

脚本不会替你做的：真开一次 PowerPoint 看有没有修复提示。步骤 4 仍需人工/自动化跑一遍。

---

## 7. 一份最小可用的 spec

在一份 32 页的物理课件上实测可用（下面 `slide10`/`slide11` 是那份课件的实际页号）：

```json
{
  "parts": [
    {"part": "ppt/slides/slide10.xml",
     "target": "m·ẍ + c·ẋ + k·x = 0",
     "latex": "m\\ddot{x} + c\\dot{x} + kx = 0"},
    {"part": "ppt/slides/slide10.xml",
     "target": "c = B²L²/R",
     "latex": "\\frac{B^{2}L^{2}}{R}",
     "prefix": "阻尼系数 "},
    {"part": "ppt/slides/slide11.xml", "auto": true}
  ]
}
```

实测结果：5 处公式注入成功，slide10 形状 12→12、slide11 形状 19→19、
`cNvPr` 集合完全一致、XML 良构、解析器判定游离标记 0 处、PowerPoint 实开无修复提示。

**part 路径怎么拿**：先 `--scan` 看输出，路径形如 `ppt/slides/slideN.xml`
与 `ppt/notesSlides/notesSlideN.xml`。注意备注页和幻灯片页是两套编号，不要混。
