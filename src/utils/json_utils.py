from __future__ import annotations

import json
import re
from typing import Any


def safe_json_loads(text: str) -> Any:
    return json.loads(text)


def extract_json_block(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty response")

    if stripped.startswith("{") or stripped.startswith("["):
        return stripped

    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if fence_match:
        candidate = fence_match.group(1).strip()
        if candidate.startswith("{") or candidate.startswith("["):
            return candidate

    start = min([i for i in [stripped.find("{"), stripped.find("[")] if i != -1], default=-1)
    if start == -1:
        raise ValueError("No JSON object/array found in response")

    stack = []
    pairs = {"{": "}", "[": "]"}
    for idx in range(start, len(stripped)):
        ch = stripped[idx]
        if ch in pairs:
            stack.append(pairs[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
            if not stack:
                return stripped[start : idx + 1]
    raise ValueError("Unclosed JSON block in response")


def parse_json_from_text(text: str) -> Any:
    return safe_json_loads(extract_json_block(text))
