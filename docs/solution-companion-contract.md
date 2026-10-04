# 逐题解析契约 v1（SWF-16.1）

冻结日期：2026-10-04。本契约只定义离线逐题解析，不修改五册 packet、已验数论版本或人工审核状态。所有组织版本复用同一题目页面；解析用途固定为 `parent_answers`。不执行历史 Python、不安装、不访问 NAS／数据库、不调用 OCR。

## 输入

UTF-8 JSON 沿用 `workflow_common` 的有界、重复键／非有限数拒绝与规范摘要。内容 schema 为 `swf.solution-companion.v1`，精确字段如下；所有 ID 使用 1～64 字符 ASCII 字母、数字、下划线或连字符，首字符为字母或数字。

- 顶层：`schema_version`、`batch_id`、`revision_id`、`title`、`sources_sha256`、`lectures`、`questions`、`assets`、`outputs`、`unknowns`。
- `sources_sha256` 为既有 `swf.sources.v1` 来源清单的规范 SHA；batch 必须一致。源照片保留原字节，来源清单不得由索引摘要冒充。明确给出的expected_counts.parent_questions／entries须分别与本次大题／叶子答案数量一致，未知数量仍为null。
- `lectures`：有序非空数组，每项 `lecture_id`、`title`；ID 唯一。
- `questions`：有序非空数组，每项 `question_id`、`lecture_id`、`display_number`、`title`、`statement`、`source_refs`、`parts`、`pages`、`unknowns`、`corrections`。每个原编号大题是一项，讲次内题号唯一，不按选项计题。
- `statement`：`text` 为完整文字转录或 null，`status` 为 `complete`／`partial`／`unknown`。partial／unknown 必须有题目 unknowns；complete 且 text 为 null 时必须有角色 question 的来源题面图。文字转录与小问题面必须出现在题目页面中，图片题面仍需代理检查可读性与完整性。
- `source_refs`：有序非空数组，每项 `source_id`、`sequence`、`region`。sequence 从1连续递增；region 为原始像素左上原点、右下边界不含的 `[x0,y0,x1,y1]`，或未知的 null；已知框须落在真实来源尺寸内。
- `parts`：有序非空数组，每项 `part_id`、`parent_id`、`label`、`statement`、`answer`、`unit`。parent_id 为同题父小问 ID 或 null；禁止循环、跨题父项和孤儿。无子项的节点为答案条目；父容器不重复计答案且 answer 为 null。没有小问时用一条叶子记录本题答案。statement／answer／unit 为普通文字或 null；叶子 answer 未知时须在题目 unknowns 中说明。全部已知小问题面须存在于同题页面；每个已知叶子的标签、答案与已知单位须同时出现在一个 answer 文字块中（公式另可附 AST），不能只保存在目录中。
- `pages`：1～100个显式页面，每页为既有 `{kind,content,role}` block 数组。沿用受控文字、表格、math AST 与图示能力；拒绝扩展 block 字段及不支持内容。题面、思路、步骤、答案和易错点由作者按实际题目编写；工具不猜数学、不自动断言掌握情况。每题须包含 question 与 method 角色；叶子有已知答案时须有 answer 角色。文本上标及 AST／OMML 各自核验。
- `unknowns`：普通文字数组；缺日期、作者、单位、题面或证明条件时保持未知。`corrections` 每项为 `kind`（printing_error／naming／draft_correction）、`original`、`replacement`、`basis`；不得覆盖历史输入。
- `assets`：数组，每项 `storage_key`、`sha256`、`kind`、`source_id`、`region`、`basis`。storage_key 为规范相对 POSIX PNG 路径。kind 为 source_crop／source_image／auxiliary；前两种必须关联来源，source_crop 有真实框、source_image 的框为 null，图中字节须为原图／原框转换 RGB 后的相同像素，v1 不支持旋转或缩放。auxiliary 的 source_id、region 均为 null，basis 明确构造条件及新增标记，不能从照片量数值。仅声明实际用到的资源；所有 block 图像须与声明 SHA 一致。裁图与原始来源的联系须在对应题的 source_refs 中出现。PNG 受已有组件 8MiB／400万像素上限约束，超限不静默压缩。
- `outputs` 精确包含 `per_question`、`per_lecture`、`combined`，值为不重复的 pdf／docx 数组，空数组表示省略该组织，至少一种非空。未请求格式仍由底层生成用于验证，交付目录／ZIP仅包含请求格式。

## 编排与模块所有权

实现位于 `scripts/solution_companion/` 子目录，避免改变五册 run 的既有顶层工具集合。主代理拥有 `model.py`、`cli.py`、`make_demo.py`、输入／审核契约、Skill、SOP、公共文档、匿名样例及集成；同一 Luna6 按阶段任务书拥有 `render.py`、`verify.py`、`bundle.py` 及明确分配的测试。不得修改 `print_backend`、五册工具或已有私有成果。

模型公共接口：

```python
validate_content(content, sources=None) -> None
content_digest(content) -> str
compile_documents(content) -> list[dict]
asset_records(content, sources, source_root, asset_root) -> dict
code_records() -> dict[str, str]
validate_review(review, content, recipe_sha256, document_records) -> None
```

compile_documents 的每项精确含 `document`（ExportDocument）、`delivery_stem`（相对路径且无扩展名）、`formats`、`question_ids`、`page_questions`（每页对应 question_id，目录页为 null）。文档 ID 为 `question-ID`、`lecture-ID`、`combined`；交付 stem 为 `per-question/讲ID/题ID`、`per-lecture/讲ID`、`combined`。目录每页至多12题，以题号、主线标题、叶子答案汇总；正文保持原题页序，不暗中改页。底层单文档100页约束保留，超过时明确返工或选择组织方式。

asset_records 核对真实来源及资源，返回 `storage_key -> {sha256,size}`；不写文件。code_records 覆盖本模式 model／render／verify／bundle／cli、实际复用的共同 I/O／来源／打印与包装 helper 源码，不把绝对家庭路径纳入身份。

渲染公共接口：

```python
render_companion(content, sources, source_root, font_config, output_root,
                 asset_root=None) -> dict
verify_companion(version_dir, source_root=None) -> dict
bundle_companion(version_dir, output, review=None) -> dict
```

render 的 output_root 是不可覆盖版本的父目录，版本目录为配方SHA前24字符；返回 directory、content_sha256、recipe_sha256、documents、delivery_files、reused。配方绑定完整内容／来源清单、资源、原字体与face index、许可、源码和实际Python／依赖环境。暂存后原子且不覆盖完成；同配方重放须重新verify后复用。拒绝输出与source／asset根重叠及不受控路径。

`solution-manifest.json` 为 `swf.solution-render.v1`，含 `recipe`、`content_sha256`、`recipe_sha256`、`documents`、`files`。documents每项为 `document_id`、`title`、`purpose`、`page_count`、`word_equations`、`delivery_stem`、`formats`、`question_ids`、`page_questions`、`previews`；files为所有实际成员相对路径到size／SHA，排除manifest自身。版本至少保存 content.json、sources.json、documents-content.json、fonts／资源、所有底层PDF／DOCX、所有页预览和仅所选格式的delivery。机器验证不写人工pass。

verify重新编排并比较全部文档与覆盖映射，核对精确文件／目录集合、大小／SHA、配方代码／环境、字体／图资源、PDF实际页数／边界／全文、Word ZIP／OOXML／正文／上标／OMML／图像／显式分页和逐页预览。重复正文证明同页栅格一致后可复用人工视觉审查。来源根提供时重验原始字节与裁图像素；未提供时 source_originals 为 not_tested，不能声称现场原图已核对。无实开证据时 human_review、word_client 均为 not_tested。

bundle只包含所选delivery文件、清单、验证摘要、阅读说明、字体许可及显式提供的审核记录，默认不含源照片、历史草稿、未请求格式、主机配置。无审核可打包draft并清楚披露未验；提供审核必须核对绑定与实际覆盖，失效审核或任一检查／独立复审fail拒绝打包，失败版本原地保留用于诊断。ZIP逐成员集合／CRC／size／SHA／回读验证；包摘要置外部checksum，拒绝已有不同输出，绝不自动发布。

## 审核与继续

外部 review 为 `swf.solution-review.v1`，精确含 schema_version、content_sha256、recipe_sha256、content、math、pdf_visual、word_client、independent_reviews。

- content／math：status（pass／fail／not_tested）、reviewer、notes、question_ids、part_ids；pass须有实际审核人并覆盖全部大题／叶子。独立复审另记实际题／小问范围，不把部分范围扩大为全题。
- pdf_visual：status、reviewer、notes、pages（`document_id:一基页号`数组）；pass覆盖全部实际文档页，或由已验证重复正文支撑对应页面审核后记录全覆盖。
- word_client：status、reviewer、notes、platforms。PC与macOS每项status、word_version、os_version、document_ids、evidence_sha256（文档ID到导出证据SHA）。pass需两端明确版本、全部实际文档和配对证据；缺证据保持not_tested。工具校验绑定与覆盖，不验证人类陈述真实性，不自动批准家庭内容。
- independent_reviews：数组，每项status、reviewer、notes、question_ids、part_ids；只记录真实子集。pass必须至少包含一道实际复核的题目，不能把空范围记为通过；只核对题面／来源时可不列答案条目，所列叶子仍须属于所列题目。

CLI为 `python /path/to/scripts/solution_companion/cli.py`：

```text
render --content FILE --sources FILE --source-root ROOT --font-config FILE
       --output-root ROOT [--asset-root ROOT]
status --run FILE [--source-root ROOT]
verify --version DIR [--source-root ROOT]
bundle --version DIR --output FILE [--review FILE]
```

render核对来源后写私有run.json输入路径／原字节SHA、环境／工具、active_version和pending；status重验全部输入与实际输出。新内容进入新摘要版本，旧成果不覆盖；输入／代码／字体变化拒绝旧状态。失败追加本次记录，不改成功指针、不删除无关数据。成功stdout单JSON、退出0，错误单JSON、退出2。Word／家庭批准／NAS复制各状态独立保存；本CLI不调用五册发布器。
