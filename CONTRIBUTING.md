# 贡献指南

感谢你愿意动手。本项目对自己的要求比一般仓库严：**凡是能变成机器判据的，就不写成"大家注意一下"**。
所以这份指南的重点不是"请守规矩"，而是**告诉你怎么知道自己的改动真的对**。

---

## 先决条件

| 项 | 要求 |
|---|---|
| Python | **3.9 及以上**（本项目按 3.9 兼容下限写，纯标准库，**不装任何第三方依赖**） |
| 平台 | Linux / macOS / Windows 均可（Windows 上的编码坑见下文） |
| 编辑器 | 建议按 `.editorconfig` 与 `.gitattributes` 走：**UTF-8 无 BOM、LF** |

不需要 `pip install` 任何东西。克隆下来就能跑。

---

## 三十秒自检

```bash
python scripts/verify_repo.py      # 文档 ↔ 现实一致性
python scripts/verify_rewrite.py   # 改写清单结构合规 + 全仓交叉引用
python demo/selftest.py            # 判据的变异测试：证明判据会红
python scripts/skill_scan.py --selftest   # 巡检器自检
```

四条全绿再提交。**Windows 上务必先设 `PYTHONIOENCODING=utf-8`**（原因见「已知坑」）。

> 各条判据的**具体条数见 [README](README.md) 的「验证」章节** —— 那里写的数是机械核对过的
> （守卫自己算实际值再与文档比对）。本文件刻意**不写死条数**：
> 写死的数字迟早会过期，而过期的数字比没有数字更糟。

---

## 仓库结构

```
skills/          每个技能一个目录（SKILL.md + 可选 scripts/ references/）
scripts/         巡检器、守卫、出包器（纯标准库）
demo/            最小可运行示例：大纲先行层 + 判据 + 端检
references/      能力矩阵、分档定义、GitHub 发布配置
reports/         巡检报告（记录当时的判断与依据，不做事后修饰）
licenses/        第三方许可全文副本
```

**规则唯一出处**：写进提示词的每一条规则，都必须能从 `skills/*/SKILL.md` 的某个小节**摘录**出来
（`demo/llm.py` 的 `skill_grounding()` 负责摘）。**不要另写一套规则**——
两套规则必然漂移，而漂移是静默的。

---

## 五条硬纪律（违反了 PR 会被要求改）

1. **不得编造事实。** 数字、题号、文献、评分细则都要有出处；没有出处就写"待人工核验"，
   不要编一个看起来合理的数。
2. **教学文件必须对齐。** 教案 / 课件 / 讲义**从同一份大纲派生**（`demo/outline.py`）。
   不要手工改派生产物 —— 手改会被 `demo/selfcheck.py` 的判据抓出来。
3. **评价权重合计 100%。** 试卷、量表、形成性评价都一样。
4. **课程思政自然融入。** 不另开"思政板块"塞内容。
5. **区分「设计使然」与「我编的」。** 判据报错时，先问"这是设计要它红，还是接线坏了"。

---

## 改了守卫怎么办？（最重要的一条）

`scripts/verify_repo.py` 是**被测对象**。只跑通不算数，**必须证明它会红**：

```bash
python scripts/test_verify_repo.py     # 守卫的变异测试，约 20–30 分钟
```

它会在仓库副本上注入典型错误，确认**每一条都在预期的那条检查上变红**。

🔴 **新加一条守卫，必须同时加一条对应的变异。** 没有变异的新守卫 =
没人证明它会红 = 它可能已经在空转，而所有检查都是绿的。

🔴 变异脚本自己抛异常时，框架会记成"这一项没验成"并继续跑其余的——
这是对的，但**必须把"没验成"记进终态数字**。否则"N/N 全绿"会掩盖
"其中几项从未真正被验过"。

---

## 改了数字怎么办

README、报告、cron 文档里的数字**都是被机械核对**的。改了任何一处计数，
请同步：

| 改了什么 | 要同步哪里 |
|---|---|
| 守卫检查项 | `README.md` 的验证章节（守卫会自己算实际值并比对） |
| 判据数量 | `README.md`、`demo/README.md` |
| 分发包文件数 | `README.md`（守卫按实际包内容核对） |
| 技能数量 | `README.md` 目录树、能力矩阵 |

跑一遍 `python scripts/verify_repo.py` 就知道漏了哪。

---

## 提交前检查清单

- [ ] `python scripts/verify_repo.py` 全绿
- [ ] `python scripts/verify_rewrite.py` 全绿
- [ ] `python demo/selftest.py` 全绿
- [ ] `python scripts/skill_scan.py --selftest` 全绿
- [ ] 改了守卫 → `python scripts/test_verify_repo.py` 全绿
- [ ] 改了文件内容 → `python scripts/package_release.py --build` 通过（它会验「克隆即用」）
- [ ] 新文件是 UTF-8 无 BOM + LF
- [ ] 没有硬编码绝对路径（守卫会扫）
- [ ] 没有真实密钥（守卫会扫）
- [ ] README / 报告里的数字与实际一致

---

## 已知坑

### Windows 控制台默认 GBK

中文 Windows 的控制台/管道默认 cp936(GBK)。Python 的 stdout 编码 = locale 首选编码。
GBK 里没有 `✅ ❌ ⚠ ★` 这类符号 —— 写 stdout 时直接 `UnicodeEncodeError` → 脚本当场死。

最阴险的形态不是"用户看到乱码"，而是：**守卫派生子进程，子进程崩了，父进程只看到「退出码 1」**
⇒ 判据红的原因和真正的原因对不上号。

**做法**（两层，缺一不可）：

```python
# ① 子进程环境显式钉死（别指望继承）
env["PYTHONIOENCODING"] = "utf-8"
# ② 脚本自己重配 stdout（否则用户直接跑就崩）
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
```

**自查判据**：跑守卫时**故意不带** `PYTHONIOENCODING` 再跑一遍。
带着跑 = 把问题藏起来了。

### 中文 Windows 下的 git

`.gitattributes` 里 `* text=auto eol=lf` 优先于 `core.autocrlf`。
如果你发现某文件被 git 反复提示"修改"，先确认 `.gitattributes` 在**仓库根目录**。

---

## 许可

本仓库原创内容为 **MIT**；第三方内容各自保留原许可，副本在 `licenses/`，
台账在 `THIRD-PARTY-NOTICES.md`。

🔴 **NonCommercial（CC BY-NC）内容不得进入本仓库或任何分发包** ——
NC 条款会传染整个分发物。本机自用的 NC 副本在 `skills-archive/`，
已被 `.gitignore` 与出包器双重排除。

新增或改写技能时：
- 改写上游技能 → 去掉上游 `skill_id`、在 frontmatter 写明 `origin`，并在 `NOTICE.md` 登记
- 引入新的第三方许可 → 在 `licenses/` 放**全文副本**，在 `THIRD-PARTY-NOTICES.md` 登记
- 守卫会机械核对：每个已装技能都要有 license 声明、每份许可副本都要被引用

---

## 行为准则

参与即同意 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
安全问题请按 [SECURITY.md](SECURITY.md) 私下报告，不要开公开 issue。
