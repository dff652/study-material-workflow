# 当前状态

更新日期：2026-10-04（Asia/Shanghai）。

## 当前结论

离线 v1 和匿名 CI 已完成；本轮新真实数论三页生成五册18页，机器验证、完整转录、数学和全部页代理审查通过。Codex CLI 新会话的自动匹配、普通数学不触发、保存阶段继续与新增数论参考匹配四例通过。用户确定 PC 和 macOS Word 实开，交接材料已准备，两端实际检查尚未执行；不能将代理审查或 XML 通过填为客户端 pass。

本轮范围是 SWF-13／14；一个 luna6-worker 先只读查找已知连接方式，再独立核对原图和仅孩子卷的数学。主代理拥有数论 reference/profile、内容、集成、文档及最终签收。只读取得用户选定 NAS 原图，未向 NAS 写入、改服务、安装宿主依赖、调用 OCR／供应商 API 或访问 Workbench 数据库。公共仓库只保存通用源码与匿名资料。

当前批次和行为验收见 [session-and-holdout-acceptance](docs/session-and-holdout-acceptance.md)，两端 Word 接续见 [word-client-acceptance](docs/word-client-acceptance.md)，任务状态见 [tasks](docs/tasks.md)。

本轮独立复审覆盖候选 15774fe 和当前私有 v3，结论 PASS；首轮 v2 FAIL 及旧签收撤销保留。50 项独立回归、匿名重放、四个 CLI 新会话和 v3 全部18页及交接包均有证据，见 [本轮 review](docs/review-holdout-20261004.md)。该结论属于 push 前签收，最终远端 SHA 与新 Actions 仍须实际核对。

## 已核对基线

- 独立 Git 项目，public [dff652/study-material-workflow](https://github.com/dff652/study-material-workflow)，默认 main。用户追加授权文档提交→独立 review→统一 push，取代前一阶段留待手动 push 的范围；不授权生产发布。首次实现 2bac24a，首发文档 3198db0，首发验收 1133550，未重写历史。
- 离线 v1：41 项测试；计算23图／61大题／81条目／91节点、五册29页；几何33图／73大题／77条目／80节点、五册35页；匿名2图五册5页，共69页由主代理逐页检查，16个历史诊断答案独立复算。见 [v1 验收](docs/verification-20261004.md)与 [首发 review](docs/review-20261004.md)。
- SWF-12：CI 实现 0e1404f，失败路径修复 58b1e7e，签收文档 09a1ac5。一个 Luna6 限定修改 CI/helper/tests，主代理及独立 verifier PASS。09a1ac579df8b9f875ac1e4e0a944c2ed620500c 与远端一致，其 [Actions](https://github.com/dff652/study-material-workflow/actions/runs/37196458612) success，50项测试零异常、匿名五册／重放通过。
- public GitHub 匿名 clone 在无宿主挂载容器的新 venv 复现通过，容器已清理。runner Python3.12.14，本地／容器3.12.3；CI artifact 字节与结构通过，宿主正式配方验证因 patch 不同拒绝，门禁未放宽。见 [CI 复现](docs/ci-reproduction.md)与 [独立 review](docs/review-ci-20261004.md)。
- 输入包括会话计算／几何五册、SWB-SOP-IMG-001 v1.0 四册流程资料与已有纯打印组件；来源摘要、真实资料和日志只在忽略的 data/。SOP 映射、数学勘误、数量口径及原组件来源分别有项目文档。
- SWF-08～10：Workbench 纯导出、受控本地版本发布／重放／冲突／索引恢复、冻结文件评测与成果 ZIP 已实现。完整几何导出因未知辅助映射拒绝并保留 raw；左右／跨页合成导出通过。未改另一个会话中的 Study Workbench 工作树，不打开其数据库。

## 本轮真实批次

数论3图／8大题／12条目／14节点，五册分页4／4／2／4／4。新 reference/profile 使用独立 namespace，沿用已有契约，核心代码未变。所选页面全部阅读，完整题干保存在台账及索引；印刷页码与精确区域未知，保留整图引用，不宣称整章完整。

先前两张候选计算照片经题干核对是开发内容重拍，虽哈希不同也拒绝计为保留集。某轮复核把正确初稿的上标误读并错误订正，后续独立 verifier 按原始像素局部确认后创建 v3，并追加撤销 v2 签收记录；缺字表达也通过受支持形式修正，没有跳过字体门禁。12原题及12新复测条目精确核算，全部18页视觉核对；未见可归属手写答案，评价保持未知／待测。

当前私有入口是 data/holdout-number-theory-20261004/run-v3/run.json、packet-v3.json、reading-ledger-v3.json、review-v3.json；无后缀初稿及被拒绝的 v2 保留诊断；v2 的旧 pass 已明确撤销，不能用于发布。run 为 machine_verified，内容为 draft，代理审核 pass 不替代家庭批准或 Word 实开。源码分发及家庭成果 ZIP 位于忽略的 artifacts/／data/，不进入 Git。

## 从保存状态继续

读取 README、任务表、相关契约与 run.json，先 status 核对来源和全部依赖，再继续待办。来源、内容、字体、图示或核心代码变化后生成新版本并重验；原图、历史尝试与已验版本不覆盖。

项目 .agents/skills/study-material-workflow 指向仓库 skill，未改用户全局配置。Codex CLI 0.159.2 四个不同新 thread 的匹配／排除／继续及数论参考读取行为已检查实际事件，匿名目录全部37文件SHA不变；该证据不覆盖 desktop／IDE。首次嵌套 read-only sandbox 被 bwrap 拒绝的运行不计通过，实际通过场景采用与父任务一致的执行环境，详见行为报告。

接续：回填同一版本在 PC 与 macOS Word 的逐册实开／打印预览结果；没有实际客户端证据前维持 not_tested。SWF-15 的真实业务标签、权限、数据库／文件联合恢复和生产 NAS 交付仍需具体接入范围及实际验收。家庭复测、手机实用、OCR／模型真实调用、费用和学习收益仍未验。
