# 1 文档目标

本文件定义 **LLM 提示词规范 (Prompt Specification)**，用于从技术文档中抽取 **枚举字段 (Enum Fields)**。

系统输入：

```
Markdown 文档片段
```

系统输出：

```
JSON 枚举结构
```

该 Prompt 用于 **Enum Extraction Pipeline 中的 LLM Extractor 模块**。

---

# 2 输出格式规范

LLM 必须输出 **严格 JSON**。

单个枚举：

```json
{
  "field": "level",
  "log_field": "level",
  "type": "enum",
  "mapping": {
    "1": "低危",
    "2": "中危",
    "3": "高危",
    "4": "严重"
  }
}
```

多个枚举：

```json
[
  {
    "field": "level",
    "log_field": "level",
    "type": "enum",
    "mapping": {
      "1": "低危",
      "2": "中危",
      "3": "高危"
    }
  },
  {
    "field": "state",
    "log_field": "state",
    "type": "enum",
    "mapping": {
      "risky": "有风险",
      "processed": "已处理"
    }
  }
]
```

---

# 3 输出规则

LLM 必须遵守以下规则：

```
只输出 JSON
不要输出解释
不要输出 Markdown
不要输出多余文本
不要生成不存在的枚举
```

如果未检测到枚举：

```json
{
 "enum": null
}
```

---

# 4 System Prompt

System Prompt 用于定义 LLM 的行为。

```
你是一个用于从技术文档中抽取枚举字段（ENUM）的系统。

你的任务是从技术文档片段中识别枚举定义，并输出标准 JSON 结构。

枚举是指 “值 → 含义” 的映射关系，例如：

1 → 低危
2 → 中危
3 → 高危

或者：

risky → 有风险
processed → 已处理

请只抽取枚举结构，并忽略以下内容：

- 字段说明表
- JSON 示例
- 代码示例
- API 调用示例

抽取规则：

1. 如果枚举前出现字段名，则使用该字段名作为 "field"
2. 如果没有提供日志字段名，则 "log_field" 与 "field" 相同
3. 只抽取文档中真实存在的枚举值
4. 不要补充或推断不存在的枚举
5. 不要输出解释文本

输出必须严格为 JSON。

输出格式：

{
 "field": "",
 "log_field": "",
 "type": "enum",
 "mapping": {}
}
```

---

# 5 User Prompt 模板

每次调用 LLM 时使用：

```
从以下技术文档中抽取枚举字段。

文档内容：

{markdown_chunk}

只返回 JSON。
```

---

# 6 Few-shot 示例

Few-shot 可以显著提升稳定性。

---

## Example 1 数字枚举

输入：

```
level：事件风险级别

1：低危
2：中危
3：高危
4：严重
```

输出：

```json
{
 "field": "level",
 "log_field": "level",
 "type": "enum",
 "mapping": {
  "1": "低危",
  "2": "中危",
  "3": "高危",
  "4": "严重"
 }
}
```

---

## Example 2 KeyValue 枚举

输入：

```
state：事件状态

risky：有风险
processed：已处理
ignored：已忽略
```

输出：

```json
{
 "field": "state",
 "log_field": "state",
 "type": "enum",
 "mapping": {
  "risky": "有风险",
  "processed": "已处理",
  "ignored": "已忽略"
 }
}
```

---

## Example 3 表格枚举

输入：

```
业务名 | MsgId
Webshell | cloudwalker-webshell
反弹 Shell | cloudwalker-revshell
```

输出：

```json
{
 "field": "msgid",
 "log_field": "msgid",
 "type": "enum",
 "mapping": {
  "Webshell": "cloudwalker-webshell",
  "反弹 Shell": "cloudwalker-revshell"
 }
}
```

---

# 7 文档 Chunk 策略

建议 chunk 大小：

```
800 — 1500 tokens
```

原因：

* 枚举通常不会跨章节
* chunk 太大会增加 hallucination

---

# 8 多枚举检测

当一个文档片段包含多个枚举时：

返回数组：

```json
[
  {enum1},
  {enum2}
]
```

---

# 9 防止 hallucination

LLM 必须遵守：

```
不要生成不存在的枚举值
不要推断枚举
不要补充枚举
```

只允许：

```
extract
```

---

# 10 推荐模型参数

如果使用 DeepSeek：

建议：

```
temperature = 0
top_p = 1
```

原因：

```
减少随机性
提高结构稳定性
```

---

# 11 LLM 调用示例

示例：

```python
response = llm.chat(
    system_prompt=system_prompt,
    user_prompt=user_prompt
)
```

---

# 12 Pipeline 中的调用位置

Prompt 用于：

```
Enum Extraction Pipeline
```

结构：

```
Loader
   │
Markdown Cleaner
   │
Enum Detector
   │
LLM Extractor  ← 使用本 Prompt
   │
Enum Validator
```

