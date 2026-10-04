# 匿名 CI 与干净环境复现

日期：2026-10-04。对应 SWF-12；验证公开仓库可以独立安装并运行离线工具，不把人工教学审核、真实 OCR、Word 实开或生产接入计为通过。

## 单一验证入口

`tools/ci_check.py` 按脚本位置定位仓库和测试，不依赖启动目录或 Codex 的全局 skill 验证器。必须显式指定不存在或为空的输出目录；拒绝符号链接和已有内容，不删除旧证据。相对输出／配置路径相对于仓库；自定义字体配置遵循 renderer 的绝对字体路径契约。

```bash
PYTHONDONTWRITEBYTECODE=1 /path/to/python3.12 /path/to/repo/tools/ci_check.py \
  --output-root /path/to/new-or-empty/evidence
```

环境检查核对 Python 3.12、requirements.txt 的六项精确直接依赖、可用 pdftoppm 和实际 Noto Sans CJK SC／DejaVu Serif 字体。完整 unittest 必须非空且全部通过；跳过、失败、错误、预期失败、意外通过及 discovery 异常均阻止成功。原来的 unittest 命令可用于诊断，但 CI 必须使用严格入口。

入口用两张合成图片生成完整五册 PDF、DOCX 和五页预览，重新 verify，并在同一输出根重放检查版本复用。demo 明确保留 `human_review`、`word_client`、`ocr`、`learning_effect` 为 `not_tested`，`published=false`。原有计算／几何五册的案例数量是历史回归证据，本入口不读取家庭目录。

| 证据 | 内容 |
| --- | --- |
| summary.json | Git HEAD、整体状态、测试各状态计数、匿名 demo、未验项及失败原因标记 |
| environment.json | Python、直接依赖、Poppler 与字体检查；不包含家庭路径或凭据 |
| tests.log | 发现并实际运行的测试输出 |
| demo/ | 合成输入、运行快照、五册、预览、字体授权及机器验证 |

退出码：0 为本轮全部门禁通过；1 为执行后验证失败；2 为输出目录等前置参数拒绝。前置拒绝不会覆盖已有证据。环境预检失败时仍运行测试并记录失败，不通过 skip 放行。更换目录重跑，不能将旧 summary 当作新执行结果。

## 无宿主挂载的复现

以下安装只发生在新建的临时容器内，容器不挂载宿主目录。首次实测使用官方 Ubuntu 24.04 amd64 镜像摘要 `sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55`；系统包和 Python 3.12 patch 版本可能随仓库更新，具体环境以每次 evidence 为准。该流程需要联网下载公共源码、系统包与 PyPI 依赖。

```bash
docker run --rm -it --cpus=2 --memory=1536m --pids-limit=256 \
  --security-opt=no-new-privileges \
  ubuntu@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55 bash
```

在这个容器内执行：

```bash
apt-get update
apt-get install --no-install-recommends -y \
  git ca-certificates python3 python3-venv poppler-utils fonts-noto-cjk fonts-dejavu-core
git clone --depth 1 --branch main \
  https://github.com/dff652/study-material-workflow.git /work/repo
python3 -m venv /opt/swf-ci-venv
/opt/swf-ci-venv/bin/python -m pip install --requirement /work/repo/requirements.txt
/opt/swf-ci-venv/bin/python -m pip check
git -C /work/repo rev-parse HEAD
cd /tmp
PYTHONDONTWRITEBYTECODE=1 /opt/swf-ci-venv/bin/python /work/repo/tools/ci_check.py \
  --output-root /evidence/anonymous-ci
cat /evidence/anonymous-ci/summary.json
```

如需保留证据，退出前另开终端用 docker cp 复制指定容器的 `/evidence/` 到私有目录；`--rm` 容器退出后会删除容器内部数据。检查 venv 的 prefix/base_prefix、禁用 user site、模块来源位于 venv，并确认容器没有宿主挂载。源码 bundle 在 push 前用于验证候选提交时，必须记录为“GitHub 基线＋本地候选 bundle”；push 后重新从 GitHub clone 才构成远端新版本复现。

独立重新渲染的 PDF／DOCX 可能因时间戳等元数据产生不同字节；不要求跨环境整个压缩包完全一致。验收核对 recipe、内容和验证结果；同一输出根重放则必须复用已验字节。首次 GitHub 基线复现的五张预览与既有匿名案例字节相同，PDF／DOCX 存在元数据差异。

## GitHub Actions

[ci.yml](../.github/workflows/ci.yml)在 main／codex/** push、pull_request 和手动触发时运行。权限为 contents:read，checkout 不保存凭据；没有部署或数据库／NAS 操作。三个官方 action 使用已核对 tag 对应的固定 commit：

| Action | Tag | Commit |
| --- | --- | --- |
| actions/checkout | v7.0.1 | 3d3c42e5aac5ba805825da76410c181273ba90b1 |
| actions/setup-python | v7.0.0 | 5fda3b95a4ea91299a34e894583c3862153e4b97 |
| actions/upload-artifact | v7.0.1 | 043fb46d1a93c77aae656e7c1c64a875d1fc6a0a |

临时 Ubuntu 24.04 runner 准备 Python 3.12、三项系统工具／字体包和固定 Python 依赖，通过 pip check 后调用同一入口。证据上传仅列出 `data/ci/summary.json`、`environment.json`、`tests.log` 与 `data/ci/demo/`，保留七天，不上传整个 data/。验证失败且证据齐全时也上传诊断；安装／前置失败没有结果时不伪造通过。

实际运行以 [Actions run](https://github.com/dff652/study-material-workflow/actions/workflows/ci.yml)为准：应核对 run 的 head SHA 与最终远端提交、conclusion、下载 artifact 的 summary 和零异常测试计数。没有成功的 run 时只能报告 workflow 已配置。权限、触发与条件语法依据 [GitHub 官方 workflow 文档](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)。

## 本轮记录与后续

实施中。主代理已从 public GitHub 匿名 clone 基线 `1133550cd2cf2768e2bb5effa0aaf9a6647247d7`，在无挂载 Ubuntu 容器的新 venv 中完成依赖安装、pip check 和两图／五册／五页机器验证。候选实现严格门禁审查发现 expectedFailure 状态可能误报，通过真实 unittest 结果复现后修正；完整候选检查和独立 review 待记录。

完成本轮不会自动完成 SWF-13～15：新真实照片的完整阅读和数学／逐页审核、Word 客户端实开、新会话 Skill 路由、Workbench／NAS 正式接入仍需各自输入与执行证据。公开记录保留聚合结果，本地原始日志和成果在忽略的 data/、artifacts/。
