# 离线 v1 验收记录

日期：2026-10-04，Asia/Shanghai。主代理完成完整 worker 文件、共享契约、集成代码与测试审查，独立执行最终检查。离线 v1 可用于选定来源、已核对内容的五册生成及验证；阅读、数学判断和学习证据仍由 agent／人工核对。家庭历史内容未被自动批准成正式题库。

本文记录首次实现提交 `2bac24a` 前后的离线验收快照；文末“未配置远端／未 push”描述当时范围。后续 public GitHub 仓库及首发授权、审查、远端核验另见[仓库记录](github-publication.md)，不改变本文的家庭内容和生产接入未验项。

## 实际结果

| 检查 | 实际结果 | 证据与范围 |
| --- | --- | --- |
| 全套测试 | 41 项，16.526 秒，全部通过，无跳过 | `data/tests-final.local.log`；匿名合成来源、异常和集成测试 |
| Skill 结构 | `quick_validate.py` 返回 `Skill is valid!` | 入口、引用、UI 元信息；新会话自动路由未实测 |
| 计算结构 | 23 来源、61 大题、81 原条目、91 节点 | 原九字段逐项一致；六组为 23/16/18/7/5/12；W1-8 有序跨页 |
| 几何结构 | 33 来源、73 大题、77 原条目、80 节点 | 六组为 14/6/9/15/18/15；W8-4、W8-10 跨页，W9-1 左右，J4-9、W5-10 子题 |
| 来源保护 | 56 原图解码及逐字节 SHA 与冻结清单一致 | `data/golden-structure.local.json`；未在本轮重查生产 NAS 或无关历史 |
| 未知保留 | 计算 18、几何 20 个未映射辅方法名称记录保留 | warning／gap 和 raw 不删；数字前缀若有效仍单独保留 |
| 五册回归 | 计算 8/12/5/2/2，共 29 页；几何 10/14/3/4/4，共 35 页 | 每套五 PDF、五 DOCX、全页 PNG、字体／授权、packet／manifest |
| 数学 | 16 个诊断答案独立复算通过；63 个非单位公差／端点有理数恒等式回归通过 | `tests/test_math_regressions.py`、`tests/test_packet.py`；未声称所有原题全文已重新解答 |
| 新批次 | 2 张匿名合成 PNG，1 题及理论页，五册 5 页通过 | `data/anonymous-demo-v1/`；只证明流程，不证明真实 OCR 泛化 |
| PDF 视觉 | 主代理检查全部 69 页及独立卷 8 张几何图 | `data/visual-review.local.json`；无缺字、截断或方法／答案提示 |
| Word | CRC／XML／OMML／内嵌图／分页声明／留白结构通过 | 无 LibreOffice／Microsoft Word，客户端实际打开及分页 `not_tested` |
| 预览绑定 | verify 从 PDF 重建每页 PNG，精确比较字节 | 64 页最终预览也与已视觉检查的上一版预览逐字节一致，审核证据绑定最终 recipe |
| 成果 ZIP | 全成员、CRC、文件 SHA 及外部 ZIP checksum 通过 | 计算 50 文件、4,794,669 字节；几何 70 文件、5,130,179 字节 |
| 中断与恢复 | SIGKILL 后进程锁释放；注入渲染失败后可重跑 | 只清理本次暂存，其他暂存与历史版本保留；成功状态不被失败覆盖 |
| 篡改与失效 | 来源／内容／资源／字体／代码变化拒绝旧状态，输出篡改拒绝 | 新字形“铮”、新摘要版本、无提示角色失败、重复运行均有实际测试 |
| Workbench 导出 | 实际计算纯转换及序列化往返通过 | 23 images、81 entries、61 roots、91 nodes、23 observations；未打开数据库 |
| 几何接入 | 完整历史输入因未知辅方法明确拒绝；左右／跨页／鸟头合成转换通过 | 正向合成为 1 entry、1 root、2 nodes；不能扩写成 77 条已正式入库 |
| 本地发布 | 匿名最终版本 24 文件真实交付，再次同身份重用 | `data/anonymous-demo-v1/delivery.local.json`；另测索引修复、冲突／外来索引拒绝 |
| 模型评测 | 冻结文件比较、未知保留／虚构／遗漏及费用状态检查通过 | 不发请求；真实模型、OCR、费用及学习收益 `not_tested` |

视觉核对由主代理直接查看所有联系页，属于 agent 审查；没有替用户、家长或学习者签署批准。历史成果 source.state 保持 `legacy_unreviewed`，run 为 `machine_verified`。完整原题再转录、作者与实际作答认定仍待专门阅读，不将结构和排版通过冒充这些工作完成。

匿名示例的独立审查记录只批准该最小合成样例在受控本地目标交付；它不是家庭内容批准，也没有触发生产写入。其交付身份为 `9fbae7def3d4fcad8c825184aa12046564f8179dc7a76c275b30591548d43de1`，首交付 reused=false、重放 reused=true。

## 最终版本与摘要

以下路径相对项目根；家庭成果与输入全部处于 Git 忽略范围。各 manifest 保存完整 packet、资源、字体及工具配方，验证会读取当前工具重新核对，后续代码变化不能沿用本次检查。

| 案例 | 不可覆盖版本目录 | packet SHA（不含 review） |
| --- | --- | --- |
| 计算 | `data/calculation/run/versions/7876246ca54ad69f201e47c8` | `4843abb2a4e071aa68fe117130f6fa69f2b1d66a96c9a5432ec88f64f60cd2a7` |
| 几何 | `data/geometry/run/versions/34951e84da3902a6fa072da2` | `4b047d12203fd9c8f8b5ce856344265dc71569299c2cc40735d9814274995103` |
| 匿名新批次 | `data/anonymous-demo-v1/run/versions/a80e4a95daec80cc1c099bcb` | `2109ab9ad14e1a4d5c2536be2319b7a33ad0a1ada45dc91a93ba03381a3b5503` |

最终 recipe SHA：

```text
计算 7876246ca54ad69f201e47c8b48ba02a7bb2c951771b3cf30935ed3b629889f2
几何 34951e84da3902a6fa072da29ba581349d486a8454db132a2789d809699ef3c4
匿名 a80e4a95daec80cc1c099bcb55256bc331bf0523174fe8c874cee6bf72c87f9f
```

成果 ZIP SHA：

```text
data/calculation/成果回归_v1.zip
724db81642db7389a1f183dc3f65f1e421a9f3a674a1d6cc35c7f202b8029b00
data/geometry/成果回归_v1.zip
445fbfb4f9729470277921d0fa2d73d793a8fddee365e7f654cfb9aaf954fb49
```

原 sources/catalog、导入来源 sidecar 和 render-final.local.json 保存独立基线。几何 22 张派生图保存原资源 key、PNG／矢量 PDF 摘要；新增几何绘图工具还保存完整场景和生成依赖配方。历史 Python 未执行。数据契约与成果打包不会自动复制原照片进通用分发包。

## 环境与实际命令

使用已有 CPython 3.12.3 环境，未安装：Pillow 12.3.0、reportlab 5.0.1、python-docx 1.2.0、fonttools 4.66.1、lxml 6.1.3、PyMuPDF 1.28.2。pdftoppm 可用，发现 440 个字体 face；本次 Noto SC TTC face_index=2 与 DejaVu Serif、授权及原字体摘要均写入配方。完整解释器路径和环境记录保存在 `data/environment-final.local.json`，公开源码没有固定私有路径。

以下命令使用当时已验证的 `PYTHON`；各 CLI 的精确参数以源码 `--help` 为准：

```bash
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -m unittest discover -s tests -v
python3 "$SKILL_CREATOR/scripts/quick_validate.py" skills/study-material-workflow
"$PYTHON" skills/study-material-workflow/scripts/check_environment.py
```

两套私有 batch 通过 workflow.prepare → legacy JSON import → workflow.render → workflow.verify → bundle_packet 完成，输出摘要见上。匿名批次由 make_demo 完成，再写入实际 agent 审查记录，使用 publish_packet 向私有本地目录交付及重放；未传 SSH 目标。命令日志和选择配置在 data/，后续任务按 run.json 重新核对状态继续。

## 原 SOP 的 18 门槛如何承接

原验收 CSV 是 `not_tested` 模板，未被本项目批量改为 pass。下表列出本次可用证据和剩余范围；有剩余范围的门槛不能当作完整标准已经通过。

| 门槛 | 本次已有证据 | 剩余范围 |
| --- | --- | --- |
| G01 原图范围 | 选定清单、书册／token、23＋33 实际来源 | 新真实批次页序及完整逐页阅读 |
| G02 原图哈希 | 本地原字节与冻结来源一致 | 新的远端采集另核对 |
| G03 题目结构 | 原条目／大题／父容器、唯一身份和原字段 | 完整题干与逐题区域尚缺 |
| G04 跨页与缺口 | 有序引用、左右、缺口保留 | 原文的语义重读与缺页判断 |
| G05 分类关联 | 专题分开、显式映射和反查字节 | 未知辅方法核准，全部语义分类再审 |
| G06 数学内容 | 16 诊断答案、非单位 d／端点回归、知识条件审查 | 全部原题的独立重解不能由此推断 |
| G07 勘误隔离 | 勘误依据和原文字保留、不改图、不归咎学习者 | 真实错误归属需证据 |
| G08 证据历史 | 未知／提示／独立规则和追加模板；不造 Attempt | 真实多次作答及业务历史接入 |
| G09 用途隔离 | 五册角色检查、孩子卷文字与全部图示检查 | 新编题仍逐次审核 |
| G10 PDF | 全结构、精确预览对应、全部 69 页视觉检查 | 内容变化后重新核对 |
| G11 Word | ZIP／XML／OMML／图／留白与分页声明 | 目标办公客户端实开与分页 |
| G12 图示字体 | 来源 SHA、字体覆盖、图字母／分数／字号检查 | 新内容和目标设备可读性 |
| G13 交付 | 成果 ZIP、匿名本地全字节交付及重放 | 生产 SSH 远端全量 SHA |
| G14 原资料保护 | 本批 56 原图未变，历史版本不覆盖 | 本轮未重查无关 NAS 历史 |
| G15 幂等追加 | 本地重放、冲突拒绝、状态失效、索引修复 | 数据库重复导入与业务历史 |
| G16 恢复 | 进程中断／自有暂存／本地索引恢复 | 数据库＋文件配套空实例恢复及权限 |
| G17 真实家庭 | 无本次实测 | 实体手机、真实作答、家长耗时／效果 |
| G18 真实模型 | 文件比较工具与费用 null／not_tested | 配置、发送范围、整页保留集、请求／取消／迟到／费用证据 |

## 交付与继续开发

仓库内 skill 的相对链接供项目发现；结构与链接已验，平台在全新会话的自动路由仍未实测。源码 ZIP 从最终 Git HEAD 导出，CRC／成员集合／字节／SHA 清单保存在 `artifacts/distribution-manifest.local.json`，不包含 data/、outputs/、环境、照片或凭据。没有全局安装、配置远端、push、部署或插件发布。

下一步优先实开 Word 和采集一个完整真实小批次，补 reading-ledger、题干／区域及人工审核；需要正式几何接入时先明确未知标签，再验证幂等、权限和联合恢复。需要生产交付或真实模型时再使用对应真实目标／配置完成剩余验收，不能拿本报告扩写为这些能力已上线。
