# 技术文档枚举抽取 Agent

PRD v1.3（精简版）

---

# 1 项目目标

构建一个自动化系统，从 **Word / PDF 技术文档** 中识别并抽取 **枚举字段 (Enum Fields)**，并转换为 **标准 JSON 结构**。

系统主要用于：

* 技术文档 Schema 解析
* 日志字段映射
* 安全规则结构化
* Agent 知识库构建

---

# 2 输入

支持文档格式：

```
.docx
.pdf
```

文档类型示例：

* HTTP API 文档
* Syslog 文档
* 安全产品说明书
* 技术架构文档

---

# 3 输出

统一输出为 **JSON 枚举结构**：

```json
{
  "field": "level",
  "log_field": "event_level",
  "type": "enum",
  "mapping": {
    "1": "低危",
    "2": "中危",
    "3": "高危",
    "4": "严重"
  }
}
```

字段说明：

| 字段        | 说明                |
| --------- | ----------------- |
| field     | 文档中的字段名           |
| log_field | 日志中的字段名（用于日志解析映射） |
| type      | 固定为 enum          |
| mapping   | 枚举值映射             |

说明：

* `field` 表示文档中的原始字段名
* `log_field` 表示日志系统中的字段名
* 当文档字段名与日志字段名一致时，两者可以相同

---

# 4 枚举识别范围

系统需要识别以下三类枚举。

---

## 4.1 数字枚举

示例：

```
level：事件风险级别

1：低危事件
2：中危事件
3：高危事件
4：严重事件
```

抽取结果：

```
1 → 低危事件
2 → 中危事件
3 → 高危事件
4 → 严重事件
```

---

## 4.2 Key-Value 枚举

示例：

```
state：事件状态

risky：有风险
processed：已处理
ignored：已忽略
```

抽取结果：

```
risky → 有风险
processed → 已处理
ignored → 已忽略
```

---

## 4.3 表格枚举

示例：

| 业务名      | MsgId                |
| -------- | -------------------- |
| Webshell | cloudwalker-webshell |
| 反弹 Shell | cloudwalker-revshell |

抽取结果：

```
Webshell → cloudwalker-webshell
反弹 Shell → cloudwalker-revshell
```

规则：

仅当表格表示 **值 → 映射关系** 时识别为枚举。

---

## 4.4 说明型枚举

部分技术文档会将枚举值写在说明中，例如：

```
level：事件风险级别

1：代表低危事件
2：代表中危事件
3：代表高危事件
4：代表严重事件
```

系统需要识别：

```
value → description
```

并转换为枚举映射：

```
1 → 低危事件
2 → 中危事件
3 → 高危事件
4 → 严重事件
```

---

# 5 不在抽取范围

系统不抽取以下内容：

### 字段说明表

示例：

| 字段名     | 类型     | 说明     |
| ------- | ------ | ------ |
| host_ip | string | 资产IP地址 |

原因：

该表用于 **字段说明而非枚举定义**。

---

### JSON 示例

```
{
 "host_ip": "10.2.6.83"
}
```

---

### 代码示例

```
python requests example
```

---

# 6 系统流程

系统处理流程：

```
Word / PDF
     │
     ▼
Document Loader
     │
     ▼
Markdown 标准化
     │
     ▼
Enum Detection
     │
     ▼
LLM Extraction
     │
     ▼
JSON Output
```

---

# 7 Markdown 标准化

文档解析后统一转换为 Markdown，并进行基础清洗：

```
删除页眉页脚
合并断行
保留列表结构
保留表格结构
```

Markdown 标准化用于提高枚举识别稳定性。

---

# 8 技术栈

| 模块        | 技术                  |
| --------- | ------------------- |
| 文档解析      | LlamaIndex Readers  |
| Word解析    | DocxReader          |
| PDF解析     | PyMuPDFReader       |
| LLM       | DeepSeek            |
| Embedding | BGE-M3              |
| 向量库       | ChromaDB            |
| 缓存        | SQLite              |
| 工作流       | LlamaIndex Workflow |
| API平台     | SiliconFlow         |

---

# 9 项目结构

```
logagent/

data/
storage/
database/

src/

  utils/
    hasher.py
    loader.py

  core/
    engine.py
    workflow.py

  schema.py

main.py
```

---

# 10 MVP 范围

第一阶段实现：

```
Docx/PDF 解析
Markdown 标准化
枚举识别
LLM 抽取
JSON 输出
```

暂不实现：

```
自动 Schema 推断
API 文档解析
多语言支持
```
