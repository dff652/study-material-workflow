# PC 与 macOS Word 实开验收 SOP

日期：2026-10-04；接续补充：2026-10-05。用户选择 PC 与 macOS 两端验收。目前只有 PDF、DOCX XML／OMML 和全部 PDF 预览通过；两端实际 Word 结果均为 `not_tested`。本机没有办公客户端，也没有连接的 Word 会话；不以结构校验替代实开。以下五册数量属于数论 v3；逐题附册按文末对应范围检查，不混用记录。

## 交接内容

私有交接目录含五册各一份 DOCX／PDF、文件 SHA 清单、当前 packet／recipe 摘要、`word-client-results.json` 未验表和操作说明。家长答案单独保管，孩子卷只有题目与留白。交接 ZIP 保存于本批次私有目录，不上传公共仓库或 Release；原图不包含在该客户端检查包中。

PDF 是已核对的 18 页打印参照：知识 4、索引 4、证据 2、独立卷 4、家长答案 4。Word 因客户端与字体可能有分页差异，不能在实开前承诺相同页数；记录实际页数，并核对完整性、内容顺序和留白。

## 两端检查

1. 在 PC 和 macOS 分别解压到本地目录。记录操作系统、Word 具体版本、检查人、日期和字体可用情况；系统和版本没提供时保持未知。
2. 逐册打开全部五份 DOCX。记录有无修复／格式错误，查看每一页，核对中文、上标、可编辑公式、表格、页脚和手动分页；对照同册 PDF 确认全文、来源及题目条件没有丢失。
3. 检查独立卷：没有方法或答案提示，实际有足够书写空间；家长解析未混入孩子文件。核对长索引表无截断、行重叠和异常空页。
4. 查看各册打印预览并导出本地 PDF，核对末页、页脚和可读性，记录实际页数与异常。若需实体打印，再另记打印机／纸张与样张结果；导出 PDF 不冒充纸张验收。
5. 在 `word-client-results.json` 各平台逐册填写实际结果，并保存异常页截图或导出的 PDF；无执行结果保持 not_tested。有问题保留原成果，只在副本或新内容修订中返工。
6. 主代理复核结果与证据的文件 SHA、packet／recipe 是否匹配。当两端全部检查通过时才可汇总 word_client=pass，说明覆盖两端的客户端版本、审核人及证据。任一端未测、失败或改用了其他版本，分别记录；一端通过不能覆盖另一端未验。

两端结果表是本次用户约定的验收证据，不是数据库导入格式。现有 review 契约保持不变；先独立存结果，核对后再形成匹配当前版本的 review 修订。不得把机器 verification、代理审查或仅打开首册的成功填入两端 pass。

## 手动实开的保存方式

解压后保留五份原 DOCX、基准 PDF 和原始未验表。另建 `客户端结果/PC/` 与 `客户端结果/macOS/`，各放一份结果表副本；每端仅填写自己的平台条目，另一端保持未验。客户端导出的 PDF 保存在该端目录，不覆盖包内同名基准 PDF。返工的 DOCX 也另存，不能把另存后的 SHA 填成原输入 SHA。

PC 可从 Word“文件 → 帐户 → 关于 Word”记录版本和 build；Mac 从“Word → 关于 Word”记录版本。已确认两端安装 Word 时可先开始检查；“Office 2016 以上”只能作为用户提供的大致范围，具体版本在检查时记录，未取得时保持未知。菜单入口参照 [Microsoft 版本查看说明](https://support.microsoft.com/en-us/office/lifecycle/lc-account/about-office-what-version-of-office-am-i-using?ns=OLWACB&version=90)。

PC 在“文件 → 打印”查看各页预览，另存／导出 PDF 到 PC 结果目录；Mac 查看“文件 → 打印”，再用“文件 → 另存为”选择 PDF 导出到 macOS 结果目录。记录实际导出方式、纸张、方向和缩放；如果软件提供在线转换选项，使用本机打印保存 PDF，家庭文档保留在本地。操作参照 [Microsoft 打印预览说明](https://support.microsoft.com/en-us/office/printing-and-print-preview)、[桌面 PDF 导出说明](https://support.microsoft.com/en-us/office/collab-files/save-or-convert-to-pdf-or-xps-in-office-desktop-apps)和 [Mac PDF 导出说明](https://support.microsoft.com/en-us/word/save-or-convert-to-pdf-on-your-mac)。

不方便编辑 JSON 时，先逐册记录：文件名、无修复打开、所有页视觉、公式／表格／图示／页脚、打印预览、实际页数、导出 PDF 位置及异常。孩子卷另记留白充足及无提示。每项未执行保持 `not_tested`；分页与基准不同先说明差异，检查内容完整与可用留白后判断，不单凭页数相同填 pass。主代理将真实观察转入结果表并计算 PDF 摘要，不能用推测补齐检查。

## 接续请求示例

“使用 study-material-workflow 继续该批次：先核对 run.json、review、PC／macOS 的 word-client-results.json 和客户端导出 PDF 的摘要；保留旧记录，报告两端真实结果，再处理实际失败项。”

本 SOP 只承接客户端验收，不触发字体安装、上传、目录清理或生产发布。文件变化后重验受影响版本；正式归档和生产接入按当次范围另行执行。

## 逐题附册的两端验收

讲义方法修订批次见 [讲义方法与边界复核](lecture-methods-and-boundary-review.md)，当前为 render-v6：40 份逐题、4 份分讲、2 份合集，共 46 份 DOCX 和 46 份基准 PDF。每端须分别实开全部 46 份 DOCX 并查看打印预览；PDF 重复正文一致的证据不能代替不同 Word 文件的客户端检查。通用逐题试跑 content-v4 与数论 v3 分别使用各自的输入与结果表。

保留原包及未验表，另存本批接续填写版。实开前核对取得的原 ZIP SHA；只取得解压文件时，逐份核对输入 DOCX／PDF 与本批模板中的 SHA。需要主代理计算时，提供文件所在私有本地路径，先确认输入版本再签收结果。结果顶部绑定批次、render 版本、原包 SHA、清单 SHA 和验收摘要 SHA；逐份保留原 DOCX／PDF 路径及 SHA。明确区分基准 PDF 页数、Word 实际页数、打印预览页数和客户端导出 PDF 页数，记录全页检查、字体替换、方法标题分页、页脚、导出方式及异常页码。导出 PDF 单独保存，主代理回读后计算 SHA；未执行项目保持 `not_tested`。

可先检查几何第一讲第 2 题当前更正版，再检查计算第二讲第 6 题的求和系数和第 10 题的括号嵌套／上标，随后完成其余文件。只检查这三份时记部分覆盖；一端通过不覆盖另一端。知识出处、构造目的和完整推导仍按 [解法选择与编写](../skills/study-material-workflow/references/solution-methods.md) 核对。
