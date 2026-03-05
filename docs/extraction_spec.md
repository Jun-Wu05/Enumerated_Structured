# 1 文档目标

该文档定义 **技术文档中枚举字段的识别与抽取规则**。

系统需要从 Word / PDF 技术文档中识别：

```
字段 → 枚举值
```

并输出统一 JSON 结构。

---

# 2 标准输出结构

所有枚举抽取统一输出：

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

| 字段        | 说明    |
| --------- | ----- |
| field     | 文档字段名 |
| log_field | 日志字段名 |
| type      | enum  |
| mapping   | 枚举映射  |

---

# 3 枚举识别规则

系统需要识别以下 **5 类枚举结构**。

---

# 3.1 数字枚举

结构：

```
value : description
```

示例：

```
1：低危
2：中危
3：高危
4：严重
```

抽取：

```
1 → 低危
2 → 中危
3 → 高危
4 → 严重
```

---

# 3.2 Key-Value 枚举

结构：

```
key : value
```

示例：

```
risky：有风险
processed：已处理
ignored：已忽略
```

抽取：

```
risky → 有风险
processed → 已处理
ignored → 已忽略
```

---

# 3.3 表格枚举

结构：

```
Column A | Column B
```

示例：

| 业务名      | MsgId                |
| -------- | -------------------- |
| Webshell | cloudwalker-webshell |
| 反弹 Shell | cloudwalker-revshell |

抽取：

```
Webshell → cloudwalker-webshell
反弹 Shell → cloudwalker-revshell
```

识别条件：

```
表格列数 ≤ 2
且表示 value → mapping
```

---

# 3.4 说明型枚举

部分文档会写成：

```
1：代表低危事件
2：代表中危事件
```

抽取规则：

```
value = 枚举值
description = 标签
```

抽取：

```
1 → 低危事件
2 → 中危事件
```

需要删除：

```
代表
表示
说明
```

---

# 3.5 列表枚举

结构：

```
- GET
- POST
- PUT
```

抽取：

```
GET
POST
PUT
```

输出：

```json
{
 "mapping": {
  "GET": "GET",
  "POST": "POST",
  "PUT": "PUT"
 }
}
```

---

# 4 字段名识别规则

枚举通常对应 **一个字段定义**。

示例：

```
level：事件风险级别
```

字段名：

```
level
```

规则：

```
field = 枚举标题中的 key
```

如果不存在 key：

```
使用标题生成 snake_case
```

示例：

```
事件等级
```

生成：

```
event_level
```

---

# 5 枚举范围识别

枚举通常出现在字段定义后。

示例：

```
level：事件风险级别

1：低危
2：中危
3：高危
```

识别范围：

```
字段标题下方
连续列表
```

终止条件：

```
出现新字段
出现新章节
出现代码块
```

---

# 6 非枚举识别规则

系统需要忽略以下结构。

---

## 6.1 字段说明表

示例：

| 字段名     | 类型     | 说明   |
| ------- | ------ | ---- |
| host_ip | string | 资产IP |

原因：

```
字段说明
不是枚举
```

---

## 6.2 JSON 示例

示例：

```
{
 "host_ip": "10.2.6.83"
}
```

原因：

```
示例数据
不是枚举
```

---

## 6.3 代码示例

示例：

```
python example
```

原因：

```
代码
不是枚举
```

---

# 7 Markdown 标准化

文档解析后统一转为 Markdown，并进行处理：

```
删除页眉页脚
合并断行
保留列表结构
保留表格结构
```

示例：

原文：

```
1
：
低危
```

标准化：

```
1：低危
```

---

# 8 枚举抽取流程

整体流程：

```
Document
    │
    ▼
Markdown Normalization
    │
    ▼
Enum Pattern Detection
    │
    ▼
LLM Extraction
    │
    ▼
JSON Enum Output
```

---

# 9 异常处理

当出现以下情况时：

```
枚举值不完整
枚举描述缺失
字段名不明确
```

处理策略：

```
保留可识别枚举
忽略异常项
```

---

# 10 未来扩展

未来可支持：

```
Schema Extraction
API 文档解析
日志字段自动映射
```

示例：

```json
{
 "field": "host_ip",
 "type": "string",
 "description": "资产IP地址"
}
```

