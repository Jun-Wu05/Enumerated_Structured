from __future__ import annotations

SYSTEM_PROMPT = """你是一个用于从技术文档中抽取枚举字段（ENUM）的系统。

你的任务是从技术文档片段中识别枚举定义，并输出标准 JSON 结构。

请只抽取枚举结构，并忽略以下内容：
- 字段说明表
- JSON 示例
- 代码示例
- API 调用示例

输出必须严格为 JSON，不要输出解释文本。
"""


def build_user_prompt(markdown_chunk: str, field_hint: str | None = None) -> str:
    hint_line = (
        f"\n字段名提示（若可靠可使用）: {field_hint}\n" if field_hint else "\n"
    )
    return (
        "从以下技术文档中抽取枚举字段，并只返回 JSON。\n"
        f"{hint_line}\n"
        "输出格式：\n"
        '{\n  "field": "",\n  "log_field": "",\n  "type": "enum",\n  "mapping": {}\n}\n\n'
        "文档内容：\n"
        f"{markdown_chunk}"
    )
