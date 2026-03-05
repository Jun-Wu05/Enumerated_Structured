# Enumerated Structured Extraction

一个用于 **从技术文档（Word / PDF）中自动抽取枚举字段（Enum Fields）** 的 AI 系统。

该系统可以从安全产品日志文档、接口文档等资料中识别 **枚举结构**，并输出标准 JSON 格式。

---

# Project Structure

```
data/
    word_long.pdf
    word_short.pdf

docs/
    prd.md
    architecture.md
    extraction_spec.md
    prompt_spec.md
    learning_log.md

evaluation/
    enum_benchmark_dataset.json
    metrics.py
    run_eval.py

src/
    pipeline/
        loader.py
        markdown_cleaner.py
        enum_detector.py
        llm_extractor.py
        enum_validator.py

    prompts/
        enum_prompt.py

    utils/
        json_utils.py

main.py
```

---

# Pipeline Architecture

系统处理流程：

```
Document
  ↓
Loader
  ↓
Markdown Cleaner
  ↓
Enum Detector
  ↓
LLM Extractor
  ↓
Enum Validator
  ↓
JSON Output
```

---

# Example Output

输入文档：

```
风险等级：
1：低
2：中
3：高
```

输出 JSON：

```json
{
 "field": "risk_level",
 "mapping": {
  "1": "低",
  "2": "中",
  "3": "高"
 }
}
```

---

# Evaluation

项目提供 Benchmark Dataset：

```
evaluation/enum_benchmark_dataset.json
```

可以使用：

```
run_eval.py
```

进行自动评测。

未来计划支持：

* Prompt A/B Test
* 自动评测（Ragas）
* Prompt 优化

---

# Documentation

详细设计文档位于：

```
docs/
```

包括：

* PRD
* Architecture
* Extraction Spec
* Prompt Spec
* Learning Log

---

# Roadmap

未来计划：

* Enum Extraction Pipeline
* Schema Extraction
* Log Field Mapping
* Agent-based Extraction

---

# License

AI-powered enum extraction from technical documentation
