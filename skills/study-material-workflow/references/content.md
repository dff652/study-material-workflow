# 五册内容及输入

packet 使用 swf.packet.v1，带 batch_id、sources_sha256、catalog_sha256、documents、omitted_purposes；review 可选。摘要均按规范 JSON 计算。每册 document 使用 swf.print.v1、document_id、title、purpose、pages、source。每块必须有 kind/content/role；见 assets/example-packet.json 的匿名例子与脚本校验。

五种用途：知识 knowledge_summary、索引 classification_index、观察 evidence_report、孩子卷 independent_practice、家长 parent_answers。每用途至多一册；需要分卷时同册 pages 增加或新批次计划明确说明。遗漏用途写 omitted_purposes。

- 文字 kind：title/sub/h/p/small/key/warn/bridge/erratum；受控 b、br、super、font 颜色标记，不可含文件加载、外链或任意 HTML。
- table：content=[rows,widths_in_points]，每格字符串；math：t/r/f/u/d 的嵌套 JSON AST；space 为真实书写高度 points；map 为 root 和最多六个 groups，可分多页。
- diagram：PNG storage_key、sha256、source_ref、alt、width_mm、no_hint_confirmed；路径相对 asset_root，源文件与导出内容一致。保留矢量源与构造记录。它不是 formula_image。
- formula_image 是未支持公式的明确图片回退，保留来源／替代说明；优先可编辑 AST／Word OMML。来源中的完整公式不得因不支持静默丢掉。
- 独立卷 role 只允许 title/instruction/question/answer_space。其他文档可以使用 body/answer/method/classification/assessment。分类和答案不能伪装进 question 角色；语义还需逐项核对。

source 保存 source_id、sha256、state、revision_id。sha256 应指本批次 catalog 摘要；draft 和 legacy_unreviewed 不冒充 accepted。accepted 要有明确内容版本与匹配人工审核记录。整理旧索引不自动创建正式业务审核。

人工 review：packet_sha256（不含 review 的 packet 规范摘要）、recipe_sha256（最终 render-manifest 中的配方摘要）、content、math、independent、pdf_visual、word_client；各项为 status、reviewer、notes。pass 需有明确核对人；不适用／Word 未实开须记录原因。review.json 可单独供发布读取；任何字体、资源或渲染代码变更后必须重审新配方。实际源观察、未知和待测应写进正文；不能只写入机器报告。

字体配置 fonts.json 必须显式包含四个键：regular_source、bold_source、math_source 为实际绝对字体路径，face_index 为非负整数（本机 Noto SC TTC 使用2，其他字体须核对）。Noto SC 源字体和 DejaVu 数学字体版权说明随 skill 保存。准备时查最终字符覆盖；新增字形后重新准备，不压小字号逃避溢页。
