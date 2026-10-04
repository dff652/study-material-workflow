# 批次准备与继续

用已验证解释器直接执行脚本，不执行历史生成 Python 来读取目录。脚本帮助页说明参数；运行配置和输出位于私有目录。

1. 创建 selection.json：batch_id、files（path/book/token/page_order），可选 expected_counts。路径相对 source_root；未知页序为 null。清单只列明确选定的资料。
2. `collect_sources.py --source-root ROOT --selection selection.json --output sources.json`：原图哈希、尺寸、真实格式和缺口。JPEG/PNG 单帧；脚本拒绝坏文件、越界和符号链接，不修改原图。
3. `adapt_catalog.py --manifest sources.json --profile PROFILE --catalog raw-catalog.json --output catalog.json`：生成父子、主辅、引用与缺口。九字段旧索引为 book/num/group/photo/feature/method/tag/tip/aux。手工新索引也可按此结构录入；当前 v1 六组 profile 适配已支持专题，新增体系先修订契约，不能硬塞或静默丢题。
4. 编写／核对 packet，执行 `workflow.py render --packet packet.json --sources sources.json --catalog catalog.json --source-root ROOT --asset-root ASSETS --output-root OUTPUT --font-config fonts.json`。同摘要复用，冲突或已验文件变化拒绝。
5. `workflow.py status --run OUTPUT/run.json --source-root ROOT` 核对阶段文件与来源；`workflow.py verify --run OUTPUT/run.json --source-root ROOT` 生成机器报告，仍需全部页视觉和数学审核。

批次内可能存在没有题号的理论／说明页，仍应阅读并在来源清单保留。引用图号相同不一定字节相同；来源 token 与 book 共同定位。完整题库与仅分类目录的缺口在报告中分别说明。

修改内容后生成新的摘要目录；旧成果和已填写复测卷不覆盖。状态失效只表示需重做相关阶段，不删除原始记录。环境依赖用 requirements.txt 和 check_environment 的实测报告复核。
