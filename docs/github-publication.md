# GitHub 仓库与首次公开提交

日期：2026-10-04，Asia/Shanghai。用户本次要求创建 GitHub public 仓库，先更新项目文档并提交，再进行 review，最后统一 push。此前留待手动 push 的安排属于上一阶段，本次采用最新授权。

## 仓库与历史

- public 仓库：[dff652/study-material-workflow](https://github.com/dff652/study-material-workflow)。创建时没有自动初始化 README／license，也没有随创建执行 push，避免引入与本地首次提交无关的历史。
- `origin` 的 fetch／push URL：`https://github.com/dff652/study-material-workflow.git`。
- 默认分支：`main`；本地初始分支 `codex/workflow-v1` 改名为 main，保留原提交身份。
- 首次实现提交：`2bac24af4ddf99317238159876149a42f2d22f56`，64 个跟踪文件。文档更新和审查记录通过后续正常提交保存，不重写该提交。

GitHub 公开仓库承载可复用 SOP skill 和源码。本地家庭输入与计算／几何完整生成成果仍在私有工作目录；它们不通过 Git、源码包或本次 GitHub 首发上传。

## 公开文件边界

| 可进入仓库 | 留在本机、不上传 |
| --- | --- |
| SKILL.md、专题参考、schema／配置示例、源码、字体授权文本 | 真实照片、家庭身份与档案、原索引全文、完整历史对话 |
| 合成图片／题目生成代码、通用异常及集成测试 | data/、outputs/、artifacts/、.venv/ 与本地验收日志 |
| README、协作约定、任务、契约、验收结论及审查记录 | 密钥、token、cookie、NAS 内网地址／具体家庭路径及其他凭据 |

公开验收结论含匿名案例数量、版本摘要和能力边界，原始证据保存在本机。不能只检查当前 `.gitignore`：首发前须检查全部待上传提交的树和 blob，确认历史也未包含私有文件／凭据。初始化阶段已检查一项提交、64 个唯一 blob，无私有路径或凭据模式命中；最终提交集合在 push 前再次核对。

## 提交、review 与统一 push

1. 文档先说明真实实现、首个提交、public 范围与未验项目，并创建正常文档提交。
2. 使用独立只读 verifier 检查本次完整待上传历史、源码边界、文档事实、入口及测试；使用已验证 Python 环境运行必要检查。审查代理不编辑文件、不操作远端，主代理负责处理问题和最终签收。
3. 未通过时修正具体问题，重跑受影响检查并复审；不得把 reviewer 自述或旧测试日志当作当前通过证据。审查报告随后保存并提交。
4. 主代理复核最终新增的报告／文档、完整历史边界、`git diff --check`、干净工作树和 origin URL，再统一 `git push --set-upstream origin main`。不 force push、不创建无关分支／tag，也不上传 artifacts。
5. 读取 GitHub 可见性及默认分支，比较远端 main 与本地 HEAD 的完整 SHA；一致后记录本地 receipt 并报告 push 成功。远端检查失败时继续核实，不能以本地 commit 或命令发出推断上传完成。

本次没有 CI workflow、GitHub Release、安装、插件市场发布或应用部署。后续可增加匿名 CI、新真实小批次阅读验收及实际 Office 检查；它们不被首次源码上传自动计为已完成。

## 状态与证据

仓库创建和 origin 已实际确认；独立 review 及最终首发核验按上述顺序执行。review 结论保存于后续审查记录；最终远端 SHA／可见性 receipt 保存于忽略的 `data/github-publication.local.json`。从后续会话继续时，直接核对 GitHub main 与本地 git 状态，不依赖旧聊天或尚未执行的计划。
