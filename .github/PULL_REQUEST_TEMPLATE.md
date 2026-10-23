## 这个 PR 做了什么

<!-- 一句话。 -->

## 类型

- [ ] 新增 / 修改**技能**（`skills/`）
- [ ] 修改**判据**（`demo/selfcheck.py`、`scripts/verify_repo.py`）
- [ ] 修改**大纲先行层**（`demo/outline.py`）
- [ ] 文档 / 报告
- [ ] 打包与发布

## 🔴 必答：如果动了判据

- [ ] **同时加了对应的变异用例**（`scripts/test_verify_repo.py`）——
      没有变异的新守卫 = 没人证明它会红 = 它可能已经在空转
- [ ] `python scripts/test_verify_repo.py` 全绿
- [ ] 说明这条新判据**在防什么失败模式**：

<!-- 写不出来的，说明这条判据还没想清楚。 -->

## 🔴 必答：如果动了计数

- [ ] 同步了 `README.md`（守卫会机械核对：README 写的数 = 实际数）
- [ ] 同步了 `reports/skill-scan-2026-Q4.md` 的变更记录
- [ ] 同步了 `demo/README.md`（如涉及判据数量）

## 硬纪律自检

- [ ] 没有编造事实（数字、文献、题号都有出处；没有出处就写"待人工核验"）
- [ ] 教学文件仍由**同一份大纲派生**，没有手工改派生产物
- [ ] 评价权重合计 100%
- [ ] 课程思政自然融入，没有另开"思政板块"
- [ ] 新文件是 **UTF-8 无 BOM + LF**
- [ ] 没有硬编码绝对路径
- [ ] 没有真实密钥
- [ ] 没有引入 NonCommercial（CC BY-NC）内容
- [ ] 若改写自上游：已去掉上游 `skill_id`、frontmatter 写明 `origin`、
      并在 `NOTICE.md` / `THIRD-PARTY-NOTICES.md` 登记

## 自检命令（全部应全绿）

```bash
python scripts/verify_repo.py
python scripts/verify_rewrite.py
python demo/selftest.py
python scripts/skill_scan.py --selftest
python scripts/package_release.py --build
```

> Windows 上请先设 `PYTHONIOENCODING=utf-8`（中文控制台默认 GBK，
> 子进程打 `✅` 会崩，父进程只看到"退出码 1"——判据红在错的原因上）。
