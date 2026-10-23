# 定时任务

## 季度技能巡检与自学习

| 项 | 值 |
|---|---|
| **cron_id** | `67c34763-7b58-4983-b6d6-2a4ef3e5657c` |
| **cron 名** | 高校教师 Agent 季度技能巡检与自学习 |
| **调度** | `0 10 1 1,4,7,10 *`（1/4/7/10 月 1 日 10:00，Asia/Shanghai） |
| **执行 Agent** | `junior-faculty-agent` |
| **会话模式** | `new`（每次运行开新会话） |
| **首次触发** | 2027-01-01 10:00 |

> ⚠️ **2026-10-22 变更**：本任务此前是 `c3668180-6dfc-4dac-b59e-23a7b0019c1d`，
> 但读出来是 **paused / 零运行 / 无 nextRun** —— 也就是**自学习实际不会触发**。
> 已用相同调度、时区、执行 Agent 与（扩充后的）提示词重建为上表的新 id。
> 下次巡检前请确认 `status = active` 且 `nextRun` 有值，不要只看"任务存在"。

### 为什么是这个调度

- 「每 3 个月」= 季度。cron 的月份字段只能枚举具体月份，`1,4,7,10` 是唯一能表达季度的写法
  （`*/3` 在标准 cron 里不是季度语义）。
- 选**月初 10:00**：避开学期初周（9 月上、1 月初有教学与申报高峰），
  也给上季度留出复盘时间。
- 距上次巡检 3 个月，对 GitHub 技能生态的更新频率足够——
  教学/科研类技能仓库的典型更新周期是季度级，过密扫描只会浪费 API 配额。

### 任务做什么

1. 扫描 GitHub 技能生态（`scripts/skill_scan.py --scan`）
2. **语义判读**：判断候选技能是否属于高校教师职责范围（这是 Agent 的判断，脚本不代劳）
3. 安装符合的技能（单次上限 10 个，**只装 MIT 许可的**），教学类自动追加中国高校语境适配
   —— **🔴 三条红线**：
   - CC BY-NC / NonCommercial（仅限非商业）→ 一律不装（理由类别 **S9**）
   - CC BY-SA 等 ShareAlike → 本次巡检也不直接装（理由类别 **S10**）——
     仓库的 50 个教学技能已 clean-room 重写为原创 MIT，自有部分按 MIT 授权，
     直接装 SA 改编版会让整仓背上 ShareAlike 义务。SA 候选记入
     `references/rejected-skills.md` 并进报告「待人工确认」段，
     后续走 clean-room 重写流程（`references/skill-rewrite-spec.md` +
     `scripts/verify_rewrite.py`）。
   - **许可台账一致性**（理由类别 **S11**）—— 仓库里有 1 个 **Apache-2.0** 技能
     （`markdown-mermaid-writing`，署名 Superior Byte Works, LLC），
     另有 13 个 **OpenMAIC（MIT / THU-MAIC）衍生技能**。
     ① 不得把 `markdown-mermaid-writing` 改标为 MIT；② `licenses/Apache-2.0-markdown-mermaid-writing.txt`
     必须随包分发；③ **新装技能若带非 MIT 许可，必须同时补齐 `licenses/` 副本
     并在 `THIRD-PARTY-NOTICES.md` 登记署名**，否则 `scripts/verify_repo.py` 会报红；
     ④ `licenses/OpenMAIC-MIT.txt` 必须随包分发（MIT 要求保留版权声明与许可声明），
     且 OpenMAIC 衍生技能的正文**不得出现任何 OpenMAIC 运行时工具名**
     （`create_stage` / `generate_scene` / `patch_stage` 等）——
     本仓库没有 OpenMAIC 运行时，那些调用全是悬空引用，守卫会红。
     > 注：S11 原为「论文类九件不要装回来」的能力分工条目，
     > 已于 2026-10-22 **作废**——那 9 个技能当日回装本仓库（论文线必须随包分发），
     > 现已列入 `references/rejected-skills.md` 的回装记录，不再是排除项。
   - **能力必须随交付物走**（理由类别 **S12**，2026-10-22 起）——
     **不得把核心交付能力挂在本机全局技能 / 运行时内置技能上**。
     那些不随本仓库分发，克隆方就无人接手。已经因此踩坑两次：
     论文线曾外包给 `academic-deep-writer`（ADW），
     幻灯片线曾外包给运行时内置的 `pptx` 与本机全局的 `nature-paper2ppt`，
     两次都已回仓自研。
     判据：**这个能力在「只克隆本仓库」的机器上还成立吗？**
     不成立 ⇒ 要么自研，要么明确写成「可选增强」并让矩阵与守卫都不依赖它。
     `scripts/verify_repo.py` 的「幻灯片能力自足」一组会机械拦截
     `pptx` / `nature-paper2ppt` 重新进入外部技能表或能力矩阵。
   判断依据是打开该技能的 LICENSE 原文，不是仓库标签。
4. 更新 `references/faculty-capability-matrix.md` 能力矩阵
   —— **新装技能必须落到某一格**：没落到格里的技能会**既不在教学包也不在科研包里**
   （恒等式 `teaching ∪ research = full − {skill-scan}` 被打破），
   `verify_repo.py` 会红、`package_release.py` 会中止出包。
5. 产出 `reports/skill-scan-<年>-Q<N>.md` 巡检报告
6. 跑四个自检（都必须全绿）：
   - `scripts/skill_scan.py --selftest` —— 20/20（验巡检器本身）
   - `scripts/verify_repo.py` —— 文档↔现实一致性 + **skills/ 无 NC 内容**
     + **分档推导自洽**（每个已装技能都有能力格归属 / 三档并集恒等式）
     + **大纲先行层**（教案与课件确由 `demo/spec/outline.example.json` 派生，
     离线 Demo 真的走了大纲层 —— 改了这层要同步 `demo/` 与技能文档）
     + **讲义产出 / UbD 判据覆盖 / 增量重生成只动一页 / 模型四档用途齐全**
     + **版式原型表自检**（`slide_layouts.py` 的几何与文字高度表自洽）
   - `scripts/verify_rewrite.py` —— 结构合规 + **全仓交叉引用**
   - `scripts/package_release.py --build` —— 出可商用分发包并自检
     （分档包用 `--profile teaching|research`，技能集合由能力矩阵机械推导）
7. 跑 Demo 的两层自检（都必须全绿）：
   - `python demo/selftest.py` —— 57/57（判据的变异测试：会红，不是空转）
   - `python demo/run_demo.py --out demo/out` —— 离线零 ERROR
   - `python scripts/test_verify_repo.py` —— 全部 51 项变异（45 + 3 + 3）

> 📌 **当前仓库状态（2026-10-22 第 6 版）**：86 个技能 = **66 个本项目原创**
> （50 个教学技能 clean-room 重写 + 5 个私有 + 3 个论文线原创
> + **6 个 OpenMAIC 方法论内核适配** + **2 个纯原创**（幻灯片线与教师风格线））
> + **20 个 K-Dense**（19 MIT + 1 Apache-2.0）。**论文线与幻灯片线都随包分发**，
> 不依赖任何本机全局技能 —— 能力矩阵 E2 / E4 / E5 / E9 四格为「**已覆盖**」，
> E7（学术汇报）也已去掉 `◐nature-paper2ppt`，改由
> `teaching-slide-designer` / `paper-to-talk-designer` 承担。
>
> 📌 **分档出包（第 6 版新增）**：`package_release.py --profile teaching|research|full`。
> 技能集合由能力矩阵的能力域**机械推导**（`references/profiles.json` +
> `scripts/profile_map.py`），恒等式
> `teaching ∪ research == full − {skill-scan}`，由 `verify_repo.py` 机械校验。
> 巡检新增技能时**必须回填到某一格**，否则两个分档都会漏掉它。
>
> 📌 **OpenMAIC 衍生（13 个）**：6 个新建（`authentic-context-course-designer` /
> `feynman-diagnostic-cycle` / `vocational-task-course` / `openmaic-courseware` /
> `teacher-style-profile` / `personal-course-pattern-builder`）
> + 7 个既有技能内增补章节（UbD/GRASPS/WHERETO、概念脊柱与升阶操作符与假螺旋检查、
> 诊断—支持—撤架—复核闭环、撤架判定与最小学习记录、澄清轮次与确认门、核心素养映射）。
> 只抽方法论内核重写，**未复制绑定 OpenMAIC 运行时的原文**；
> 归属与署名见 `THIRD-PARTY-NOTICES.md` §3。

### 需要知道的两个限制

1. **GitHub API 限流**：未认证时 60 req/h。脚本有 12 小时磁盘缓存（`.cache/`），
   关键词组扫描遇限流会提前停止并把未完成组数写进报告（`search_groups_completed`）。
   巡检报告会标注扫描完整性。**设置 `GITHUB_TOKEN` 后限额升到 5000 req/h，扫描更完整。**
2. **扫描不完整 ≠ 没有新技能**：主源拉取失败时脚本以退出码 2 结束，
   报告必须保留「本次扫描不完整」的判断，不能报成「本季度无新技能」。

### 手动触发

```bash
cd <AGENT_DIR>    # 换成本机 Agent 安装目录

python scripts\skill_scan.py --selftest          # 离线自检
python scripts\skill_scan.py --scan               # 扫描（需联网）
python scripts\skill_scan.py --install spec.json  # 按决策安装
```

### 调整调度

```bash
mavis mcp ...   # 或在客户端的定时任务界面直接改
```

用 `cron_update` 改 `schedule` / `enabled` / `prompt`；
用 `cron_delete` 删除。**改调度时同步更新本文件的表格。**
