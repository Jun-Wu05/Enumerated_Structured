# TODO - 下一轮修复清单（结构优先）

## 目标
- 修复“有索引但没用上、有数据但没结构”的脱节问题。
- 先保证 Markdown 结构可用，再调 LLM 抽取策略。

## P0 - MarkdownCleaner 表格还原（先做）
- 文件: `src/pipeline/markdown_cleaner.py`
- 任务:
  1. 实现列对齐检测: 使用 `re.split(r'\s{3,}', line)` 识别多列。
  2. 强制插入 `|` 分隔符: 当检测到 2 列及以上时转成 Markdown 表格行。
  3. 严禁合并表格行: 含 `|` 的行绝不参与 `\n -> 空格` 合并。
- 验收:
  - `debug_table.md` 中出现可读的 `| --- | --- |` 表格分隔。
  - `word_long.pdf` 第 15 页目标表格可看到列边界。

## P1 - LLM Extractor 标题回溯策略
- 文件: `src/pipeline/llm_extractor.py`
- 任务:
  1. Prompt 增加规则: 若片段内无明确字段定义，回溯 `parent_hierarchy` 最后一个有效标题作为 `field`。
  2. Few-shot 增加“仅表格 + parent_hierarchy 推断 field”的示例。
  3. 保证结构化输出: 返回 JSON 且包含 `field`、`mapping`。
- 验收:
  - `word_long.enums.*.json` 中 `field: null` 显著减少。
  - 表格型候选的字段名可由标题路径稳定填充。

## P1 - Schema 对齐
- 文件: `schema.py`（若不存在，新增模型定义模块）
- 任务:
  1. `EnumExtraction` 允许 `log_field` 缺失时自动回填 `field`。
  2. 输出校验对 `field/mapping` 做硬约束。
- 验收:
  - 输出 JSON 不再出现 `log_field` 缺失或非法结构。

## P1 - Workflow 事件流与可观测性
- 文件: `src/pipeline/workflow.py`
- 任务:
  1. 确保 `ExtractionEvent` 传递 `metadata`（含标题路径、父标题、页码等）。
  2. 在每次调用 LLM 前输出最终 `full_prompt`（debug 开关控制）。
  3. 在日志中记录候选 ID -> parent_title -> overlap_tokens -> prompt 片段映射。
- 验收:
  - 能在日志中确认标题路径确实进入 prompt。
  - `test_structure.log` 可追踪每个候选完整流转链路。

## P2 - 解析器策略回顾
- 文件: `src/pipeline/loader.py`
- 任务:
  1. 继续评估 `fitz.find_tables` + `pdfplumber` 混合策略命中率。
  2. 若表格恢复仍弱，评估切换 LlamaParse（仅作为后备方案）。
- 验收:
  - 第 15 页关键表格在 Loader 输出中可识别为表格块。

## 执行顺序（下次）
1. 只跑 `Loader -> Cleaner`，生成 `debug_table.md`。
2. 确认表格结构恢复后，再跑 `Detector -> Extractor`。
3. 最后跑全流程并对比 `word_long.enums.overlap_check.json`。

## 当前已知症状（用于回归）
- `test_structure.log` 有标题树，但提取结果仍存在字段识别偏差。
- `word_long.enums.overlap_check.json` 仍出现结构化提取不稳定。
- 第 15 页表格在 Markdown 中恢复不足。
