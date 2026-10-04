# Study Material Workflow

离线学习资料整理 skill。将明确选定的讲义／练习册照片或已核对草稿整理成知识总结、分类索引、证据记录、无提示复测和家长答案，使用同一内容快照生成 PDF 与 Word。

GitHub public 仓库：[dff652/study-material-workflow](https://github.com/dff652/study-material-workflow)，默认分支 `main`。仓库保存可复用工具与匿名示例，家庭来源、档案和生成成果留在本机私有工作区；公开范围和首发检查见[GitHub 仓库记录](docs/github-publication.md)。

阅读、知识归纳、解题和评价由 agent／人工负责；工具负责来源、结构、精确算术、图示、渲染、版本、验证与交付。已有分类目录仍有完整题干、逐题区域和独立性缺口，不能自动成为已审核题库。

## 开始使用

Skill 入口为 [SKILL.md](skills/study-material-workflow/SKILL.md)，运行契约见 [workflow-contract](docs/workflow-contract.md)。运行环境是 Linux／POSIX Python 3.12；六项依赖版本在 [requirements.txt](requirements.txt)。先用已有解释器检查依赖和字体，不自动安装或下载。

在项目目录执行，`PYTHON` 换成已验证解释器的路径：

```bash
PYTHON=/path/to/verified/python
SCRIPTS="$PWD/skills/study-material-workflow/scripts"
"$PYTHON" "$SCRIPTS/check_environment.py"
"$PYTHON" "$SCRIPTS/make_demo.py" \
  --output-root "$PWD/data/anonymous-demo" \
  --font-config "$PWD/skills/study-material-workflow/assets/font-config.example.json"
```

字体示例指向本机 Noto SC TTC 和 DejaVu Serif；其他机器先核对真实路径、face index 和授权字体。演示生成两张匿名合成图、完整五册及验证报告，不调用 OCR／供应商、不发布、不评价真实学习者。重复执行复用已验字节；相同路径内容冲突时使用新目录。

处理真实批次按 [workflow.md](skills/study-material-workflow/references/workflow.md) 创建 selection 与 raw-catalog，再 prepare、编写／审核 packet、render、verify。若来源在 NAS，先按已确认范围取得私有原字节与清单；脚本不把 NAS 当本机挂载点。新增资料改变预期数量，不沿用 23／33 或旧分页。

```bash
"$PYTHON" "$SCRIPTS/workflow.py" prepare \
  --source-root /private/batch/sources --selection /private/batch/selection.json \
  --raw-catalog /private/batch/raw-catalog.json \
  --profile "$PWD/skills/study-material-workflow/references/calculation-profile.json" \
  --output-root /private/batch/run
```

`run.json` 保存当前阶段和待审项，`versions/摘要/` 保存不可覆盖成果；`status` 先核对全部依赖，`verify` 产生机器证据。人工 review 必须绑定 packet 与最终 recipe，所有页和新编答案均需核对。Word XML／OMML 校验不代表实际 Office 客户端分页通过。

## 工具与接入

| 入口 | 实际职责 |
| --- | --- |
| collect_sources / adapt_catalog | 选定原图真实解码、hash、数量、稳定身份、跨页与父子、原 raw／未知保留 |
| exact_math / diagrams | 有界有理数计算；可追溯矢量 PDF／PNG 场景，不能代替证明 |
| import_legacy_packet | 只读历史 JSON，保存快照和图示来源，不执行历史 Python |
| render_packet / verify_packet | 五册 PDF／Word／全页预览、字体与资源、严格集合和结构校验 |
| workflow | 准备、生成、继续检查、失效和失败记录，历史结果保留 |
| bundle_packet | 已验成果及可选配对输入快照的 ZIP，全成员字节、CRC、外部 checksum，不自动发布 |
| export_workbench | 经指定版本纯转换器输出私有 bundle，不访问数据库 |
| publish_packet | 显式受控本地或 SSH 目标，已审版本暂存、全 hash、原子目录、索引、幂等／冲突拒绝 |
| benchmark | 比较已有 truth／prediction／usage；没有真实调用记录就 not_tested，不发模型请求 |

当前 skill 源码位于项目内，不改用户全局配置。新会话可先读入口文件，再明确“使用 study-material-workflow 按保存批次继续”；项目发现入口、包及验收状态见 [DEV_STATE](DEV_STATE.md)。

## 文档与验收

- [任务清单](docs/tasks.md)：SWF-00～10 的实际范围与状态。
- [SOP 对照](docs/sop-mapping.md)：会话决策、十阶段、重要勘误与不遗漏的边界。
- [实施方案](docs/implementation-plan.md)、[验收方案](docs/acceptance-plan.md)：职责和签收要求。
- [工作流契约](docs/workflow-contract.md)、[Luna6 交接](docs/luna6-task-brief.md)、[打印组件来源](docs/print-component-provenance.json)。
- [最终验收记录](docs/verification-20261004.md)：41 项测试、16 个诊断答案复算及 69 页视觉复核；私有输入／成果位于忽略的 data/ 和 artifacts/。
- [首次公开提交独立审查](docs/review-20261004.md)：完整待上传实现和历史审查 PASS；独立重跑 41 项测试通过。

测试命令：`PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -m unittest discover -s tests -v`。公开测试仅含合成来源；家庭照片、档案、完整历史内容和凭据不进入 Git 或通用 skill 包。真实 OCR、手机／家庭复测、数据库迁移、生产 NAS 发布和部署需要对应范围和实际证据。

本地首次实现提交为 `2bac24a`。首发文档已更新并提交，独立 review 通过；main 是本次统一首发分支，实际提交可从 GitHub 历史查看。后续提交、发布与部署仍按对应任务授权执行。
