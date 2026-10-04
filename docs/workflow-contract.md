# 离线工作流契约 v1

确定日期：2026-10-04。本轮实施 SWF-01～07，并实现 SWF-08～10 的离线适配／发布／评测工具；不向既有数据库迁移，不开启真实模型，不改运行服务。工具实际动作由明确命令及配置决定；无模型配置时评测记 not_tested。

## 文件与版本

统一使用 UTF-8 JSON；拒绝重复键、非有限数和过大输入。稳定摘要为 JSON 按键排序、无额外空白、ensure_ascii=False 的 UTF-8 SHA-256。CLI 成功退出 0、错误 2，stdout 是单个 JSON；工具不得隐式安装、发布或执行历史代码。

- `selection.json`：`batch_id`、`files` 数组；每项 `path`（相对来源根）、`book`、`token`（六位照片定位 token）、`page_order`（正整数或 null）。可选 `expected_counts` 包含 sources、parent_questions、entries。数量按批次配置，不写死历史案例。
- `sources.json`：`schema_version="swf.sources.v1"`、batch_id、expected_counts、sources；每项 source_id、storage_key、book、token、page_order、sha256、size、width、height、format。source_id 基于批次和相对路径；不将绝对路径当身份。
- `catalog.json`：`schema_version="swf.catalog.v1"`、batch_id、profile_id、namespace、classification_revision、source_manifest_sha256、counts、entries、nodes、warnings。`counts` 为 sources、parent_questions、entries、question_nodes；父容器单独保存。
- 每条 entry：question_id、parent_id、book、display_number、raw（九个原字段保持）、photo_refs、primary_method_id、auxiliary_method_ids、gaps、review_state=draft。photo_refs 保存 source_id、sequence、granularity=whole_image、region=null；完整题干／精确区域／独立性缺口保留。未知辅助方法加入 warnings／gaps，不猜映射。
- 每个 node：question_id、parent_id、book、display_number、node_type（entry 或 parent）。expected_counts 若指定三项数量，均需与实际来源／根大题／原条目数一致。
- 专题 profile：profile_id、namespace、classification_revision、books、photo_separator、allow_sides、groups（数字组号到名称）、aux_aliases（名称到数字组号）。数字前缀和名称显式映射；未知名称保留。同号方法按 namespace 分开。
- 题号支持 N、N(k)、N(k)-m；allow_sides=true 时支持 N(左)／N(右)。父容器由层级推导，原条目不丢；原大题按 book＋根整数计数。

## 首轮 Luna6 的唯一所有权

Worker：`skills/study-material-workflow/scripts/collect_sources.py`、`check_environment.py`、`adapt_catalog.py`、必要的 `catalog_adapters/`、`tests/test_sources.py`、`tests/test_catalog.py`。不改 workflow_common.py、print_backend、profiles、SKILL.md 或其他文档。

共享工具为 workflow_common.py：WorkflowError(code,message)、fail、canonical、digest(bytes)、read_json(path)、write_json(path,value,replace=False)、root_path、resolve_under、ensure_output_outside、cli_result。公共 helper 缺口先报告主代理，不自行复制一份。

`collect_sources.py` CLI：`--source-root ROOT --selection FILE --output FILE`，可选 `--max-bytes`／`--max-pixels`（默认 32 MiB／4000 万）；`collect_sources(source_root, selection, output=None, max_bytes=..., max_pixels=...)` 返回 manifest；`validate_manifest(manifest)` 校验结构，`verify_sources(manifest,source_root)` 核对真实字节。单帧 JPEG／PNG，实际解码和尺寸核对；来源目录及文件不允许 symlink，输出不落来源树。重复 source path、重复 book/token 和错误范围拒绝。

`adapt_catalog.py` CLI：`--manifest FILE --profile FILE --catalog FILE --output FILE`；`adapt_catalog(rows,manifest,profile)` 返回转换结果。manifest 已经过结构校验；来源 book/token 引用必须唯一且匹配。九字段原行严格保留；无效题号、缺来源、重复原题号、错误组拒绝。稳定 ID 包含 batch_id＋namespace＋book＋原题号。same-content write 幂等，不同内容拒绝覆盖。

`check_environment.py` CLI：无必需参数，允许 `--font-root ROOT`；仅返回解释器、依赖版本、可用字体与 missing，不创建／安装环境。

## 内容与后续运行

内容包 `swf.packet.v1` 包含 batch_id、sources_sha256、catalog_sha256、documents、review。每册 document：document_id、title、purpose、pages（语义 block 数组）、source；block 为 kind、content、role。五种 purpose 对应 knowledge_summary、classification_index、evidence_report、independent_practice、parent_answers；可选择子集并记录 omitted_purposes。

复用固定的纯离线 print_backend，禁止 Django／数据库依赖。支持受控文字／表格、math AST(t/r/f/u/d)、map、space；教学图使用独立 `diagram` 类型，带相对 PNG path、sha256、source_ref、alt、width_mm、no_hint_confirmed；不将教学图假称公式。无提示卷角色仅 title／instruction／question／answer_space，图还需明确无提示确认。

review 是人工记录，不是 CLI 自动批准：包含 packet_sha256 和 recipe_sha256；content、math、independent、pdf_visual、word_client 各记录 status、reviewer、notes。pass 必须有核对人，not_applicable／Word not_tested 必须说明原因。发布需要内容、数学、所选独立卷及 PDF 逐页审核通过，Word 客户端未验须明确披露。内容和最终渲染配方均须匹配，字体或代码变化使旧排版审核失效。机器 verify 不能自动写这些 pass；未核对可生成草稿预览。

渲染接口 render_packet(packet,font_config,output_root,asset_root=None)，验收接口 verify_packet(version_dir)。版本目录以 recipe_sha256 前 24 字符命名，含 packet.json 和 render-manifest.json（swf.render.v1）；manifest 保存规范配方、packet_sha256、recipe_sha256、documents 以及 files（相对路径到 sha256／size）。packet_sha256 排除 review，便于内容审核绑定；配方另含 packet_record_sha256，绑定保留 review 的完整 packet。配方包含资源字节、字体源字节／face index、backend／helper／render／verify wrapper 源码、Python／依赖及 pdftoppm 版本；不使用时间或绝对私有路径作版本身份。审核记录改变也产生新版本，不能丢掉旧 review 来复用已验状态。

所有 PDF 页生成预览，verify 从 PDF 重建 PNG 并比较精确字节。manifest 自身不列入 files；验证实际文件集合、字节、PDF／Word结构和页面约束，预先限制单文件及总字节，不能替代人工语义和实际 Word 打开验收。进程锁在崩溃后释放；版本暂存后用 Linux renameat2 原子且不覆盖地发布。

bundle_packet 将已验版本打成 ZIP，可显式配对加入 hash 匹配的 sources/catalog 快照；校验每个成员、CRC 和字节。bundle-files.json 不将自身纳入其哈希表，ZIP 的摘要放在外部 checksum 文件，避免循环摘要。成果包不会自动发布。

run 状态保存各阶段的输入摘要、输出文件和字节摘要、环境／工具摘要、失败及 pending。继续运行重新核对上游及输出；内容、来源、资源或依赖变更使下游失效，不复用旧 pass。新输出进入摘要版本目录，拒绝覆盖旧成果。

公共源码只保存匿名合成样例；案例原图、输入、结果和验收记录在被忽略的 data／artifacts 内。已有源码的状态可继续变化；本项目纯打印副本的初始来源字节记录在 print-component-provenance.json。
