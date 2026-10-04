# 当前状态

更新日期：2026-10-05（Asia/Shanghai）。

## 当前结论

最新连续执行结果见[2026-10-05接续验收](docs/continuous-acceptance-20261005.md)：三批 Word 每端55份仍待真实结果；源码修复空范围独立复审 pass，76项严格回归及匿名五册／重放通过。通用内容仍v4，新配方在独立私有目录；数论v3成品独立验证通过，旧run因新增独立工具报stale_run。历史与原成果不覆盖。用户随后授权整理项目文档、本地提交并review，实际签收及提交阶段见[本地review](docs/review-solution-companion-20261005.md)；后续统一手动push。

逐题实现、测试及配套文档已本地提交为`72e9a3d178859d47581db17a71bee3babaa31ee8`，25文件与提交前已审字节一致；源码与文档review为PASS。该提交的父节点为另项`c9477100a2d5b40ebae620228fb24e5f399eb99a`，原历史保留。签收状态由后续文档提交追加，本轮未push，三批实际Word仍not_tested。

离线 v1 和匿名 CI 已完成；本轮新真实数论三页生成五册18页，机器验证、完整转录、数学和全部页代理审查通过。Codex CLI 新会话的自动匹配、普通数学不触发、保存阶段继续与新增数论参考匹配四例通过。用户确定 PC 和 macOS Word 实开，并确认两端已安装 Word，提供大致版本为 Office 2016 以上；具体版本及实际检查结果尚未取得。交接材料已准备，不能将安装确认、代理审查或 XML 通过填为客户端 pass。

SWF-13／14 原生成验收阶段中，一个 luna6-worker 先只读查找已知连接方式，再独立核对原图和仅孩子卷的数学。主代理拥有数论 reference/profile、内容、集成、文档及最终签收。该阶段只读取得用户选定 NAS 原图，未向 NAS 写入、改服务、安装宿主依赖、调用 OCR／供应商 API 或访问 Workbench 数据库。后续用户追加授权的副本交付单独记录。公共仓库只保存通用源码与匿名资料。

当前批次和行为验收见 [session-and-holdout-acceptance](docs/session-and-holdout-acceptance.md)，两端 Word 接续见 [word-client-acceptance](docs/word-client-acceptance.md)，任务状态见 [tasks](docs/tasks.md)。

本轮独立复审覆盖候选 15774fe 和当前私有 v3，结论 PASS；首轮 v2 FAIL 及旧签收撤销保留。50 项独立回归、匿名重放、四个 CLI 新会话和 v3 全部18页及交接包均有证据，见 [本轮 review](docs/review-holdout-20261004.md)。随后已实际核对本地／远端 main 为 a3e00c49005cd26bdaed5247c0d8985698b6ec84，对应 [Actions](https://github.com/dff652/study-material-workflow/actions/runs/37200724378) success，50项测试零异常，匿名五册／重放及artifact全文件集合、尺寸、哈希和文档结构通过。私有receipt为 data/swf13-final-publication.local.json。

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

## SWF-14 本次接续

本次 status 已核对数论 v3 来源、输入、字体、工具和依赖，五册18页仍为 machine_verified，word_client 为 not_tested。原 v3 验收 ZIP 的14成员、CRC、全部文件字节、尺寸、SHA及packet／recipe绑定再次通过；几何12张原图与保存的来源SHA一致。当前没有连接的Word会话，宿主没有办公客户端，两端实际操作由用户在已安装的Word中执行。

用户本次追加授权在飞牛指定目录准备一份数论v3待验副本；已新建独立验收子目录，复制原ZIP、checksum、手动说明和PC／macOS两份记录表，五文件远端SHA与独立全字节回读通过。旧NAS资料保持原位；本次副本交接不构成SWF-15生产工作流发布、权限／故障恢复或Word实开通过。具体私有路径及receipt存于 data/swf14-resume-20261004/。

SOP已补充分平台结果目录、保留原未验表及基准PDF、逐册文字回填和客户端菜单说明。当前公共代码及共享契约未变，数论v3、几何逐题成果和历史拒绝记录保留。后续统一手动push；本次未提交、未push。

## 最新私有配套文档和交接

按用户追加请求，两讲几何逐题解题思路已单独整理：12张原图含19大题／21答案条目，输出汇总21页、两讲各11页、19份逐题文件共20页；22份文档各有Word与PDF，共44个成果文件。主代理阅读全部来源、核算21个答案并检查全部汇总页和两讲目录；一个Luna6独立复核第二讲全部10题及第一讲第2题。题目正文在各组织版本中经逐页图像比对一致，原图12个哈希未变；Word正文、原题图、上标和显式分页通过结构检查，PC／macOS实开仍为not_tested。

私有内容、来源、被拒绝初稿、更正记录和成果包保存在 data/geometry-lecture-solutions-20261004/。本任务复用公共print_backend，不改变五册契约、公共代码或既有批次；逐题成果生成阶段未向NAS写入。随后根据用户明确追加要求，将同一ZIP及44份解压文档复制到指定NAS新目录，远端ZIP哈希与全部49个包成员的回读通过，已有资料未覆盖；不上传家庭成果到公共仓库。该复制不替代SWF-15业务接入与恢复验收，凭证为私有fnos-copy-20261004.local.json。新会话通用起点见 [new-session-start](docs/new-session-start.md)，本机完整交接见 data/session-handoff-20261004.md。本次交接文档尚未提交或push，a3e00c4仍是已发布基线。

## 逐题模式的可复用指引

已把生成解题思路文档的完整过程补入Skill：新增逐题解析路由及UI描述，按需读取 [逐题解析SOP](skills/study-material-workflow/references/solution-companion.md)。SOP覆盖来源与完整题面、大小问计数、思路与证明、原图／辅助图、同一快照的逐题／分讲／汇总编排、数学与全页检查、Word未验边界、不可覆盖版本、ZIP校验和已授权交付。现有Python核心与五册契约没有改变。

SWF-16.1～16.4已完成本地通用化，见 [冻结契约](docs/solution-companion-contract.md)、[开发补充](docs/solution-companion-development.md)和 [本轮验收](docs/solution-companion-acceptance-20261004.md)。独立逐题CLI支持render／status／verify／draft bundle，源码放在新子包，不改变五册工具指纹。主代理冻结契约、集成并审查全部实际改动，一个Luna6仅实现指定渲染／验证／打包文件及测试；最终64项回归零异常，原五册匿名运行与重放通过。三个新的CLI会话实际验证逐题生成、保存后只读继续和普通数学排除；不把过去四例当成本次证据。

SWF-16.5已用此前选定、未做逐题文档的两题完成新私有试跑，保留v1拒绝和后续修订，当前有效内容为v4；全部两题两叶、两张原裁图、数学及独有PDF页由主代理签收，一个Luna6独立复核全部两题并绑定v4。4份文档各有Word／PDF，共8份交付文件，全部PDF含重复共8页、独有正文2页、目录2页；机器及ZIP回读通过。两端Word、家庭批准及实际学习收益仍未验，因此SWF-16.5部分完成，不写全项pass。

完整证据、新私有试跑包与两端未验表在忽略的data/swf16-generalization-20261004/，继续入口在私有交接。原数论v3仍为machine_verified／word_client=not_tested；既有数论与几何成果373文件SHA未变。没有访问／复制到新NAS目标、安装、全局Skill配置、commit或push；后续统一手动push。原有SWF-14客户端任务及其他工作区改动保留。

## 讲义方法补充与阴影修订（2026-10-04）

按用户同意，另生成几何两讲的方法补充册与计算两讲逐题解析，各题划分本讲与其他方法并注明知识来源。几何19大题／21答案、计算21大题／26答案，共46组Word／PDF、92文件；几何合集28页、计算合集22页。主代理核对全部题面、推导与48页独有正文和6页目录，一个Luna6独立复核限定范围；全部结构与重复正文栅格通过。

上文旧几何第1讲第2题的完整边界与答案签收撤销：原图包含此前漏画的一条边及额外三角形，旧答案需更正，新单题、分讲和合集均重生成。旧44份成果与原ZIP字节保留，旧NAS目录已追加更正提示。新包及92解压文档按既有指定路径交付于新修订目录，100成员及远端全字节回读通过，未覆盖原资料。Word两端仍not_tested；本次不作为生产业务流程或学习效果通过。

当前私有讲义版本为data/lecture-methods-20261004/render-v6/，与通用逐题试跑content-v4和数论v3分开。完整证据与继续入口见[讲义方法与边界复核](docs/lecture-methods-and-boundary-review.md)及本机data/lecture-methods-20261004/handoff.md。逐题SOP已补方法分类、原图边界独立核对、打印分页及旧签收撤销规则；本轮没有改公共核心、全局配置、提交或push，其他会话改动保留。

## 优化解法纳入 Skill（2026-10-04）

按本次文档补充请求，将已采用的本讲／其他方法分类整理为[解法选择与编写](skills/study-material-workflow/references/solution-methods.md)，由Skill入口与逐题SOP按需引用。参考覆盖知识归属、每题编写框架、辅助构造目的、等积理由、原图完整边界与旧签收撤销、裂项公差及1/3／1/4系数推导、内容块映射和打印验收。默认先本讲再列有收益的其他方法；知识出处不明时待核，不从讲义内容推断孩子掌握。

文档沿用现有有序内容块与swf.solution-companion.v1，不新增通用字段；当前method角色不能机器区分两类方法。项目任务及[会话起点](docs/new-session-start.md#本讲方法与其他方法修订的接续起点)同步更新。讲义render-v6及原交付证据继续有效，PC／macOS Word仍not_tested；本次仅补充Skill与交接文档，后续统一手动push。

本次Skill格式验证通过，8份相关文档的95个本地链接／锚点、空白和新参考的隐私检查通过；数学示例有完整代数推导，并以102组精确核算补充检查。一个luna6-worker（gpt-6-luna）只读复核新参考的知识归属、等积／裂项与内容块映射，指出的逐叶答案块措辞歧义已修正；主代理审核本次文档补充。此检查不扩大此前成果签收或替代Word实开。

## render-v6 Word 接续（2026-10-05）

本次按最新起点复核既有成果，没有重生成或重复交付。主代理独立回读 ZIP 全部100成员、92文档、21原图与8份验收证据，摘要一致；核对当前第2题三页预览、完整边界与1/6答案、旧签收撤销及4个历史文件摘要。NAS receipt绑定当前包，未进行新的远端操作。一个luna6-worker只读核对两端各46份记录的覆盖、实际文件摘要和未验状态，发现原表缺少明确的全页检查、实际页数及导出PDF字段。

已在私有data/lecture-methods-20261004/word-client-resume-20261005/另存增强未验填写表、逐份文字记录和小型接续ZIP，绑定render-v6、内容、原包、清单和验收摘要；原包及未验表保持不变。当前没有连接的Word会话，也未取得客户端实测结果，PC／macOS均仍not_tested。下一步可先实开几何第一讲第2题，再逐份完成本端46份检查，回传填写记录与本机导出PDF的私有路径。数论v3与通用逐题content-v4独立保留；本次无安装、NAS写入、提交或push，后续统一手动push。

本地HEAD实际为c9477100a2d5b40ebae620228fb24e5f399eb99a，含另项Workbench完整记录与配套示意导出；上文a3e00c4为历史已发布基线。本次保留该提交和其他未提交工作，不扩展其验收。增强接续ZIP全字节回读、两端各46条绑定、118个受保护基线文件及31个本地文档链接／锚点检查通过；这些仍不构成Word客户端通过。

Luna6另对增强表与说明只读复核通过，建议明确取件后先校验输入SHA；主代理已补入SOP及接续说明。当前填写材料在上述私有目录的handoff-v2/，对应接续ZIP为render-v6_PC-macOS_Word验收接续_未验-v2.zip；这里的v2只表示接续说明修订，讲义成果仍为render-v6。v1补充材料保留，v2六成员及全部字节重新核验通过，两端实测字段继续为空／not_tested。

## 按顺序连续执行（2026-10-05）

已执行可独立开展的版本核对、源码复审、门禁修正、匿名回归与三批交接整理。当前未取得Word连接或非模板客户端结果，前三批各自保留未验状态；实开与主代理客户端签收尚未完成。一个luna6-worker只读复现并复核空范围独立复审门禁问题，主代理修正model及回归，最后76项零异常通过，Skill格式通过。

通用content-v4的当前工具配方为e98555b06658e06baa013e0785edb5ac8abf8dbee07969d78bf321bf63a5a81b，保存于data/continuous-acceptance-20261005/generic-v4-current-tools/，内容SHA未变，旧v4全部字节保留；新旧8页完整栅格及全部Word ZIP成员一致。Word容器字节不同，当前工具ZIP与新未验表分别绑定，不能套用旧记录。

数论v3旧run的工具集合仅新增export_content_records.py，原打印配方不受影响，原不可覆盖成品／18页、3原图及14成员验收包均重新核验通过；旧run继续明确stale_run，没有修改其摘要。完整顺序、证据、未验边界及恢复入口见上述接续报告。三批每端55份、共110项未验记录已整理为私有小包；本轮没有NAS写入、安装、外发、提交或push。
