# 当前状态

更新日期：2026-10-04（Asia/Shanghai）。

## 本次范围

离线 v1 已完成 skill、工具、测试、案例回归和主代理审查，首次本地提交为 `2bac24a`。用户随后授权创建 public GitHub 仓库，更新项目文档并提交，再 review，最后统一 push。此前“留待手动 push”是上一阶段的范围，本次以最新授权执行。离线验收见[最终验收记录](docs/verification-20261004.md)，远程首发见[仓库记录](docs/github-publication.md)。

## 已完成与基线

- 独立 Git 项目，初始开发分支 `codex/workflow-v1` 已改名为默认分支 `main`，没有重写 `2bac24a`。public 仓库为 `dff652/study-material-workflow`，origin 的 fetch／push URL 均为 `https://github.com/dff652/study-material-workflow.git`。首发文档提交为 `3198db0`，独立审查已 PASS，main 按本次授权统一首发。
- 独立 verifier 重跑 41 项测试（16.922 秒，无跳过），检查 33 个 Python 文件、全部两个可达提交／69 个唯一 blob，三套成果重新验证通过。报告见 [review-20261004](docs/review-20261004.md)；最终远端 SHA 与可见性以本地 receipt 和 GitHub main 核验，不从本地提交推断 push 成功。
- GitHub 源码公开与资料／应用部署分别记录；本次未安装依赖、启用模型 API、改生产 NAS、迁移数据库或变更服务。
- 输入为会话计算／几何五册、SWB-SOP-IMG-001 v1.0 四册流程资料及现有纯打印源码；来源摘要和真实资料只在忽略的 data/ 内。
- SWF-00～07 的离线实现和主代理验收完成；一个 luna6-worker 分两轮负责来源／索引及 render／verify，主代理审查全部实际修改，负责共享契约、知识边界、集成、恢复及最终检查。
- 41 项测试全部通过。计算 23 图／61 大题／81 条目／91 节点，五册 29 页；几何 33 图／73 大题／77 条目／80 节点，五册 35 页；匿名新批次 2 图、五册 5 页。69 页均完成主代理视觉复核，16 个历史诊断答案另用有理数与坐标方法复算。
- Workbench 接入只调用显式选择的纯转换器，运行前后核对源码摘要，不打开数据库。本项目未改另一个会话中的 Study Workbench 工作树；初始打印副本来源见 docs/print-component-provenance.json。
- SWF-08～10 工具已实现：计算纯导出通过，完整几何因未知辅助方法明确拒绝；几何左右／跨页合成导出通过；匿名本地版本发布及幂等通过；评测只比较现成文件。真实数据库、SSH 生产交付、OCR／供应商与家庭学习效果未验。

## 从保存状态继续

读取 README、任务表、契约与对应 run.json；先运行 status 核对输入与输出，再继续所需阶段。已验版本不能覆盖；代码、字体或资源变化后重新生成并绑定新审核。

项目内 `.agents/skills/study-material-workflow` 指向实际 skill，未改用户全局配置。结构与引用通过检查；新会话自动发现／自动路由尚未实测，可显式读取入口继续。源码分发 ZIP 和字节清单保存在忽略的 artifacts/，不含家庭资料。

家庭成果保持 `legacy_unreviewed`，运行记录为 `machine_verified`：主代理检查排版和诊断答案，不替代原题全文再转录、家庭内容批准或实际 Word 客户端验收。新的真实家庭保留集、Word 实开、业务联合恢复和生产接入见任务表未验项。
