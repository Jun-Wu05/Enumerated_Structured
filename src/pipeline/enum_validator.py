from __future__ import annotations

import re
from typing import Any, Optional


class EnumValidator:
    def __init__(self, min_mapping_size: int = 2) -> None:
        self.min_mapping_size = min_mapping_size
        self.field_aliases = {
            "range_days": "time_window_days",
        }

    def validate_many(self, enums: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        order: list[str] = []

        for enum_item in enums:
            valid = self.validate_one(enum_item)
            if not valid:
                continue
            field = valid["field"]
            if field not in merged:
                merged[field] = valid
                order.append(field)
            else:
                merged[field]["mapping"].update(valid["mapping"])

        result = []
        for field in order:
            item = merged[field]
            if len(item["mapping"]) >= self.min_mapping_size:
                result.append(item)
        return result

    def validate_one(self, enum_item: Any) -> Optional[dict[str, Any]]:
        if not isinstance(enum_item, dict):
            return None

        field_raw = str(enum_item.get("field", "")).strip()
        field = self._normalize_field(field_raw)
        field = self.field_aliases.get(field, field)
        if not field:
            return None

        log_field_raw = str(enum_item.get("log_field", "")).strip() or field
        log_field = self._normalize_field(log_field_raw) or field
        log_field = self.field_aliases.get(log_field, log_field)

        mapping_raw = enum_item.get("mapping")
        if not isinstance(mapping_raw, dict):
            return None

        mapping: dict[str, str] = {}
        for k, v in mapping_raw.items():
            key = str(k).strip()
            value = str(v).strip()
            if not key or not value:
                continue
            mapping[key] = value

        if len(mapping) < self.min_mapping_size:
            return None
        if field == "unknown_field":
            return None
        if not self._is_plausible_enum_mapping(mapping):
            return None

        return {
            "field": field,
            "log_field": log_field,
            "type": "enum",
            "mapping": mapping,
        }

    def _normalize_field(self, value: str) -> str:
        text = value.strip()
        if not text:
            return ""
        text = re.sub(r"[^\w]+", "_", text, flags=re.UNICODE)
        text = re.sub(r"_+", "_", text).strip("_").lower()
        return text

    def _is_plausible_enum_mapping(self, mapping: dict[str, str]) -> bool:
        if len(mapping) > 20:
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
        if noisy_value_ratio > 0:
            return False

        numeric_key_ratio = sum(1 for k in keys if k.isdigit()) / len(keys)
        clean_key_ratio = sum(1 for k in keys if re.match(r"^[A-Za-z0-9_-]{1,20}$", k)) / len(keys)
        return max(numeric_key_ratio, clean_key_ratio) >= 0.7


def validate_enums(enums: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return EnumValidator().validate_many(enums)
