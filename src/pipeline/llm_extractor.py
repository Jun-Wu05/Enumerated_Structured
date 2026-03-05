from __future__ import annotations

import os
import re
from typing import Any, Optional

from src.prompts.enum_prompt import SYSTEM_PROMPT, build_user_prompt
from src.utils.config import build_llamaindex_llm
from src.utils.json_utils import parse_json_from_text


class LLMExtractor:
    """
    Extract enum JSON from candidates with LLM as primary path.
    Rule fallback is optional and disabled by default.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        enable_rule_fallback: Optional[bool] = None,
    ) -> None:
        resolved, llm = build_llamaindex_llm(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
        )
        self.provider = resolved.provider
        self.model = resolved.model
        self.base_url = resolved.base_url
        self.api_key = resolved.api_key
        self.temperature = temperature
        self._llm = llm
        if enable_rule_fallback is None:
            self.enable_rule_fallback = os.getenv("EXTRACTOR_RULE_FALLBACK", "0").strip() == "1"
        else:
            self.enable_rule_fallback = enable_rule_fallback
        self._usage = self._init_usage()

    def _init_usage(self) -> dict[str, int]:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "llm_calls": 0,
        }

    def extract_many(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._usage = self._init_usage()
        results: list[dict[str, Any]] = []
        for candidate in candidates:
            extracted = self.extract_one(candidate)
            if extracted:
                results.extend(extracted)
        return results

    def get_usage(self) -> dict[str, int]:
        return dict(self._usage)

    def extract_one(self, candidate: dict[str, Any]) -> list[dict[str, Any]]:
        if self._can_call_llm():
            try:
                llm_result = self._extract_with_llm(candidate)
                if llm_result:
                    return llm_result
            except Exception:
                if not self.enable_rule_fallback:
                    return []
            if not self.enable_rule_fallback:
                return []
        if not self.enable_rule_fallback:
            return []
        fallback = self._extract_with_rules(candidate)
        return [fallback] if fallback else []

    def _can_call_llm(self) -> bool:
        return self._llm is not None and bool(self.api_key)

    def _extract_with_llm(self, candidate: dict[str, Any]) -> list[dict[str, Any]]:
        chunk = str(candidate.get("chunk", "")).strip()
        field_hint = candidate.get("field_hint")
        if not chunk:
            return []

        from llama_index.core.base.llms.types import ChatMessage, MessageRole

        resp = self._llm.chat(
            messages=[
                ChatMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
                ChatMessage(
                    role=MessageRole.USER,
                    content=build_user_prompt(chunk, field_hint),
                ),
            ]
        )
        self._accumulate_usage(resp)
        content = getattr(resp.message, "content", "") or ""
        parsed = parse_json_from_text(content)
        normalized = self._normalize_response(parsed)
        if not normalized:
            return []
        return normalized

    def _accumulate_usage(self, response: Any) -> None:
        usage = self._extract_usage(response)
        self._usage["llm_calls"] += 1
        self._usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        self._usage["completion_tokens"] += usage.get("completion_tokens", 0)
        self._usage["total_tokens"] += usage.get("total_tokens", 0)

    def _extract_usage(self, response: Any) -> dict[str, int]:
        candidates = []
        raw = getattr(response, "raw", None)
        if raw is not None:
            candidates.append(raw)
        additional = getattr(response, "additional_kwargs", None)
        if additional is not None:
            candidates.append(additional)
        message = getattr(response, "message", None)
        if message is not None:
            msg_additional = getattr(message, "additional_kwargs", None)
            if msg_additional is not None:
                candidates.append(msg_additional)

        for payload in candidates:
            if isinstance(payload, dict):
                usage = payload.get("usage")
                if isinstance(usage, dict):
                    return self._normalize_usage(usage)
                # Some providers return usage at root level.
                if any(k in payload for k in ("prompt_tokens", "completion_tokens", "total_tokens")):
                    return self._normalize_usage(payload)
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _normalize_usage(self, usage: dict[str, Any]) -> dict[str, int]:
        prompt = int(usage.get("prompt_tokens", 0) or 0)
        completion = int(usage.get("completion_tokens", 0) or 0)
        total = int(usage.get("total_tokens", 0) or 0)
        if total == 0:
            total = prompt + completion
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
        }

    def _normalize_response(self, data: Any) -> list[dict[str, Any]]:
        if data is None:
            return []
        if isinstance(data, dict) and data.get("enum") is None:
            return []
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    def _extract_with_rules(self, candidate: dict[str, Any]) -> Optional[dict[str, Any]]:
        chunk = str(candidate.get("chunk", "")).strip()
        field = self._normalize_field(str(candidate.get("field_hint") or "unknown_field"))
        candidate_type = str(candidate.get("candidate_type", "")).lower()
        if not chunk:
            return None

        mapping: dict[str, str] = {}
        if "table" in candidate_type:
            mapping = self._parse_table_mapping(chunk)
        elif "list" in candidate_type:
            items = [line.strip() for line in chunk.splitlines() if line.strip()]
            mapping = {item: item for item in items}
        else:
            mapping = self._parse_kv_mapping(chunk)

        if len(mapping) < 2:
            return None
        if not self._is_plausible_enum_mapping(mapping):
            return None

        return {
            "field": field,
            "log_field": field,
            "type": "enum",
            "mapping": mapping,
        }

    def _parse_kv_mapping(self, chunk: str) -> dict[str, str]:
        mapping: dict[str, str] = {}
        bad_value_markers = (
            "必选",
            "可选",
            "字符串",
            "数字",
            "字典",
            "列表",
            "字段如下",
            "请求参数",
            "api",
            "python",
        )
        for line in chunk.splitlines():
            match = re.match(r"^\s*([A-Za-z0-9_\-./]+|\d+)\s*[:\uFF1A]\s*(.+?)\s*$", line.strip())
            if not match:
                continue
            key, value = match.group(1).strip(), match.group(2).strip()
            value = re.sub(r"^(?:\u4EE3\u8868|\u8868\u793A|\u8BF4\u660E)\s*", "", value)
            value = self._normalize_enum_value(value)
            lower_value = value.lower()
            if any(marker in lower_value for marker in bad_value_markers):
                continue
            if key and value:
                mapping[key] = value
        return mapping

    def _parse_table_mapping(self, chunk: str) -> dict[str, str]:
        mapping: dict[str, str] = {}
        rows = [line.strip() for line in chunk.splitlines() if "|" in line]
        if len(rows) < 2:
            return mapping
        for row in rows[1:]:
            cols = [col.strip() for col in row.split("|") if col.strip()]
            if len(cols) != 2:
                continue
            if all(set(col) <= {"-", ":"} for col in cols):
                continue
            left, right = cols
            if left and right:
                mapping[left] = right
        return mapping

    def _normalize_field(self, field: str) -> str:
        value = field.strip()
        value = re.sub(r"[^\w]+", "_", value, flags=re.UNICODE)
        value = re.sub(r"_+", "_", value).strip("_").lower()
        return value or "unknown_field"

    def _normalize_enum_value(self, value: str) -> str:
        text = value.strip()
        # Remove page counters frequently merged from PDF lines.
        text = re.sub(r"\s+\d+\s*/\s*\d+\s*$", "", text)
        # Keep canonical status/level labels when extra section words are appended.
        canonical_prefixes = (
            "低危事件",
            "中危事件",
            "高危事件",
            "严重事件",
            "有风险",
            "已处理",
            "已忽略",
            "低危",
            "中危",
            "高危",
            "严重",
        )
        for prefix in canonical_prefixes:
            if text.startswith(prefix):
                return prefix
        return text

    def _is_plausible_enum_mapping(self, mapping: dict[str, str]) -> bool:
        if not mapping or len(mapping) < 2 or len(mapping) > 20:
            return False

        keys = list(mapping.keys())
        values = list(mapping.values())

        long_value_ratio = sum(1 for v in values if len(v) > 24) / len(values)
        if long_value_ratio > 0.3:
            return False

        noisy_value_ratio = sum(
            1
            for v in values
            if any(x in v for x in ("http://", "https://", "{", "}", "import ", "class "))
        ) / len(values)
        if noisy_value_ratio > 0.0:
            return False

        numeric_key_ratio = sum(1 for k in keys if k.isdigit()) / len(keys)
        clean_key_ratio = sum(1 for k in keys if re.match(r"^[A-Za-z0-9_-]{1,20}$", k)) / len(keys)
        if max(numeric_key_ratio, clean_key_ratio) < 0.7:
            return False

        return True


def extract_enums(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return LLMExtractor().extract_many(candidates)
