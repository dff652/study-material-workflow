# 按需要接入

## Workbench

完整内容优先用 `export_content_records.py`：把整理时已经明确的逐题内容写为 `swf.workbench-content.v1`，使用同批 `swf.sources.v1` 输出 `swb.skill-records.v2`。每题一个局部 ID 与 `swb.material-draft.v1`，自动生成题目、知识／方法／题型、答案和关联的命名空间身份；看不清的题干保留 null 并在 missing_fields 中说明，不从五册散文或旧索引反推。

content 的封闭顶层为 schema_version、batch_id、questions、diagrams。questions 是 `{id,draft}` 数组；draft 为 `{schema_version,original_number,sources,proposal}`，sources 为 `{source_id,bbox}` 原图整数框数组，proposal 为 `{printed_text,missing_fields,nodes,answer}`。nodes 每题最多三项 `{kind,data}`，kind 为 knowledge／method／question_type；answer 为 null 或 `{body,formulas,basis}`，公式使用封闭 AST。字段与 Workbench 的内容草稿一致。

diagrams 每项明确提供 `{id,question,placement,png_key,vector_key,source,alt,conditions,width_points,min_label_points,independent_safe,basis}`。question 引用本批题目局部 ID，source 必须等于该题的一个已知区域；PNG 与 PDF／SVG 使用 asset-root 内明确配对文件。题面图需核对无提示，解析构造使用 placement=answer。工具不从图形推断来源或构造，不执行矢量。资源每个最多 512 KiB／PNG 400 万像素且单帧、最多 32 个，完整伴随包最多 1 MiB；超限换小批次，不能静默删图。

```sh
"$PYTHON" "$SCRIPTS/export_content_records.py" \
  --content /private/batch/content.json --sources /private/batch/sources.json \
  --asset-root /private/batch/diagrams --output /private/batch/records.json
```

输出父目录预先设为 0700；工具创建 0600 新文件，不覆盖，不联网或打开数据库。原图不嵌入资产包。再用 Workbench 的 `prepare_skill_exchange.py` 合并同批五册 packet、catalog、可选 ledger、records，以及人工选定的已有资料 page_id／原图 SHA 映射。v2 包保留原 packet 和账本；旧 diagram 的宽度、提示状态、用途和 PNG SHA 必须与伴随记录一致。缺少原生对应的 formula_image 拒绝，先明确提供封闭公式 AST。Workbench 一次核对确认后经原生版本服务保存内容和教学图；工具审核不能替代这次确认或生成孩子作答。重复同请求不重复入库；不同任务不靠题号覆盖已有历史。

旧 `export_workbench.py` 仅将原始索引、来源和显式专题映射交给指定 Workbench 纯 domain 转换器，输出索引骨架 bundle，不是完整题库。它仍不访问数据库；未映射辅助方法保留未知并拒绝，不删除原始条目来通过检查。真实学习档案、逐次作答及评价继续使用 Workbench 的明确事件入口。

## 发布

publish_packet.py 接收已验版本、匹配 review 和目标版本目录。先在受控本地目标验证，只有当任务要求且给定 SSH 目标时使用 NAS。用 batch+recipe 身份、暂存、全部 SHA、原子版本目录及交付 receipt；同内容幂等，不同内容拒绝。目标和暂存失败分别记录；版本与索引不是一笔跨文件事务，索引失败可重新核对重试，不删除正式版本。没有删除入口。

## 模型评测

benchmark.py 对明确冻结的 truth/predictions/usage 文件做比较，记录各任务字段的匹配、未知保留、遗漏及实际用量。没有真实请求记录和供应商配置则 real_model=not_tested；不得拿合成结果说识别已可用。它不执行模型调用。发送照片的范围、供应商、预算和访问凭据在对应用户任务中确定。

现有 Codex／ChatGPT 可在用户任务中帮助看图和写草稿；本 skill 不把这等同于已评测的自动 OCR。真实供应商对比和费用由实际记录支撑，不从脚本耗时或 token 猜家庭收益。
