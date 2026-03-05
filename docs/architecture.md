# 1 系统概览

系统用于从 **Word / PDF 技术文档** 中自动抽取 **枚举字段（Enum Fields）**，并输出标准 JSON 结构。

系统整体处理流程：

```
Document
   │
   ▼
Loader
   │
   ▼
Markdown Cleaner
   │
   ▼
Enum Detector
   │
   ▼
LLM Extractor
   │
   ▼
Enum Validator
   │
   ▼
JSON Output
```

系统采用 **Pipeline 架构**，每个模块职责单一。

---

# 2 系统模块

系统由五个核心模块组成：

| 模块               | 功能     |
| ---------------- | ------ |
| Loader           | 文档加载   |
| Markdown Cleaner | 文本标准化  |
| Enum Detector    | 枚举候选检测 |
| LLM Extractor    | 枚举结构抽取 |
| Enum Validator   | 结果校验   |

---

# 3 模块设计

---

# 3.1 Loader

负责加载文档。

支持格式：

```
docx
pdf
```

实现：

```
LlamaIndex Readers
```

模块位置：

```
src/pipeline/loader.py
```

示例：

```python
documents = loader.load(file_path)
```

输出：

```
raw_text
```

---

# 3.2 Markdown Cleaner

负责文本清洗与标准化。

主要处理：

```
删除页眉页脚
合并断行
保留表格结构
保留列表结构
```

目标：

```
提高枚举识别稳定性
```

模块位置：

```
src/pipeline/markdown_cleaner.py
```

输出：

```
markdown_text
```

---

# 3.3 Enum Detector

该模块用于 **检测疑似枚举区域**。

目的：

```
减少 LLM 调用
提高识别准确率
```

检测模式：

### 数字枚举

```
1：
2：
3：
```

### KeyValue 枚举

```
risky：
processed：
```

### 表格枚举

```
value | mapping
```

检测逻辑：

```
regex + rule
```

模块位置：

```
src/pipeline/enum_detector.py
```

输出：

```
enum_candidates[]
```

每个 candidate 为：

```
text chunk
```

---

# 3.4 LLM Extractor

该模块负责调用 LLM 抽取枚举结构。

输入：

```
enum_candidate
```

使用：

```
prompt_spec.md
```

模型：

```
DeepSeek
```

模块位置：

```
src/pipeline/llm_extractor.py
```

输出：

```
enum_json
```

---

# 3.5 Enum Validator

用于验证 LLM 输出结果。

主要检查：

```
mapping ≥ 2
field != null
JSON 格式合法
```

异常处理：

```
过滤错误枚举
```

模块位置：

```
src/pipeline/enum_validator.py
```

输出：

```
validated_enums
```

---

# 4 数据流

完整数据流：

```
Word/PDF
   │
   ▼
Loader
   │
   ▼
Raw Text
   │
   ▼
Markdown Cleaner
   │
   ▼
Markdown Text
   │
   ▼
Enum Detector
   │
   ▼
Enum Candidates
   │
   ▼
LLM Extractor
   │
   ▼
Enum JSON
   │
   ▼
Enum Validator
   │
   ▼
Final JSON
```

---

# 5 项目结构

项目代码结构：

```
src/

pipeline/

loader.py
markdown_cleaner.py
enum_detector.py
llm_extractor.py
enum_validator.py

schema.py
```

文档结构：

```
docs/

PRD.md
architecture.md
extraction_spec.md
prompt_spec.md
```

---

# 6 技术栈

| 模块        | 技术         |
| --------- | ---------- |
| 文档解析      | LlamaIndex |
| PDF解析     | PyMuPDF    |
| LLM       | DeepSeek   |
| Embedding | BGE-M3     |
| 向量数据库     | ChromaDB   |
| 缓存        | SQLite     |

---

# 7 性能优化

系统采用以下策略减少 LLM 调用：

```
Enum Detector
```

流程：

```
Document
↓
Enum Detection
↓
Only enum candidates → LLM
```

优化效果：

```
LLM调用减少 70–90%
```

---

# 8 错误处理

异常情况：

```
枚举值缺失
字段名缺失
JSON格式错误
```

处理策略：

```
丢弃异常枚举
记录日志
```

---

# 9 未来扩展

未来系统可以扩展为：

```
Schema Extraction
Log Field Mapping
API 文档解析
```

示例：

```
字段名 | 类型 | 说明
```

可抽取为：

```json
{
 "field": "host_ip",
 "type": "string",
 "description": "资产IP地址"
}
```
