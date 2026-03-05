from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Optional

from src.pipeline.title_indexer import TitleIndexer, TitleNode


@dataclass
class EnumCandidate:
    candidate_type: str
    chunk: str
    start_line: int
    end_line: int
    field_hint: Optional[str] = None
    debug_reason: Optional[str] = None
    title_path: Optional[list[str]] = None
    parent_title: Optional[str] = None
    context_chunk: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnumDetector:
    """
    Regex/rule-based enum candidate detector.
    """

    _kv_re = re.compile(r"^\s*([A-Za-z0-9_\-/\.]+|\d+)\s*[：:]\s*(.+?)\s*$")
    _field_re = re.compile(r"^\s*([A-Za-z_][\w\-.]*)\s*[：:]\s*(.+)?$")
    _list_re = re.compile(r"^\s*[-*+]\s+(.+?)\s*$")
    _type_word_re = re.compile(
        r"^(?:str|string|int|integer|float|double|bool|boolean|datetime|long)$",
        re.IGNORECASE,
    )
    _code_fence_re = re.compile(r"^\s*```")
    _datetime_key_re = re.compile(r"^\d{4}-\d{2}-\d{2}T?\d{0,2}$")
    _enum_word_keys = {
        "risky",
        "processed",
        "ignored",
        "ignore",
        "success",
        "failed",
        "true",
        "false",
        "allow",
        "deny",
        "drop",
        "open",
        "closed",
        "timeout",
        "info",
        "warn",
        "error",
        "get",
        "post",
        "put",
        "delete",
        "low",
        "medium",
        "high",
        "critical",
    }
    _non_enum_key_blacklist = {
        "id",
        "method",
        "params",
        "data",
        "events",
        "host_id",
        "host_ip",
        "host_name",
        "created_at",
        "updated_at",
        "description",
        "solution",
        "path",
        "offset",
        "count",
        "group_id",
        "group_name",
        "jsonrpc",
    }
    _noise_value_markers = (
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
        "示范调用",
        "import ",
        "class ",
        "http://",
        "https://",
        "字段如下",
        "事件列表",
        "主机信息",
        "业务组",
        "文件路径",
        "事件类型",
        "风险级别",
        "事件状态",
        "事件数量",
        "发现时间",
        "创建时间",
        "更新时间",
        "字段",
        "说明",
    )
    _space_table_row_re = re.compile(r"^\s*\S.+\s{3,}\S.+$")
    _title_table_hint_words = ("列表", "对照表", "定义", "枚举", "字段")

    def detect(self, markdown_text: str) -> list[dict[str, Any]]:
        if not markdown_text.strip():
            return []

        lines = markdown_text.splitlines()
        self._title_indexer = TitleIndexer()
        self._title_nodes = self._title_indexer.build(markdown_text)
        candidates: list[EnumCandidate] = []

        candidates.extend(self._detect_kv_blocks(lines))
        candidates.extend(self._detect_table_blocks(lines))
        candidates.extend(self._detect_space_table_blocks(lines))
        candidates.extend(self._detect_list_blocks(lines))
        candidates.extend(self._detect_sentence_enums(lines))

        merged = self._deduplicate(candidates)
        merged.sort(key=lambda x: (x.start_line, x.end_line))
        self._attach_title_context(merged, self._title_nodes)
        return [item.to_dict() for item in merged]

    def _detect_kv_blocks(self, lines: list[str]) -> list[EnumCandidate]:
        results: list[EnumCandidate] = []
        i = 0
        in_code = False

        while i < len(lines):
            line = lines[i]
            if self._code_fence_re.match(line):
                in_code = not in_code
                i += 1
                continue
            if in_code:
                i += 1
                continue

            start = i
            block: list[str] = []
            kv_count = 0

            while i < len(lines):
                current = lines[i]
                if self._code_fence_re.match(current):
                    break
                if not current.strip():
                    break
                if "|" in current:
                    break
                if self._kv_re.match(current):
                    key, value = self._kv_re.match(current).groups()
                    if self._looks_like_field_definition(key, value):
                        break
                    kv_count += 1
                    block.append(current.strip())
                    i += 1
                    continue
                break

            if kv_count >= 2:
                field_hint = self._guess_field_hint(lines, start)
                block, field_hint = self._strip_header_like_kv_line(block, field_hint)
                segments = self._extract_kv_segments(block, field_hint)
                for seg_lines, seg_field in segments:
                    results.append(
                        EnumCandidate(
                            candidate_type="kv_enum",
                            chunk="\n".join(seg_lines),
                            start_line=start + 1,
                            end_line=i,
                            field_hint=seg_field,
                            debug_reason="kv_segment_filtered",
                        )
                    )
                continue

            if i == start:
                inline_candidate = self._extract_inline_kv_line(line)
                if inline_candidate:
                    field_hint, chunk = inline_candidate
                    results.append(
                        EnumCandidate(
                            candidate_type="inline_enum",
                            chunk=chunk,
                            start_line=i + 1,
                            end_line=i + 1,
                            field_hint=field_hint,
                            debug_reason="inline_enum_filtered",
                        )
                    )
                i += 1
            else:
                i += 1

        return results

    def _strip_header_like_kv_line(
        self, block: list[str], field_hint: Optional[str]
    ) -> tuple[list[str], Optional[str]]:
        if len(block) < 2:
            return block, field_hint
        first = self._kv_re.match(block[0])
        second = self._kv_re.match(block[1])
        if not first or not second:
            return block, field_hint

        first_key, first_val = first.group(1).strip(), first.group(2).strip()
        second_key = second.group(1).strip()
        if first_key.isdigit():
            return block, field_hint

        # Heuristic: "<field>: 描述" followed by real enum items.
        if second_key.isdigit() or len(first_val) >= 4:
            if not field_hint:
                field_hint = first_key
            return block[1:], field_hint
        return block, field_hint

    def _detect_table_blocks(self, lines: list[str]) -> list[EnumCandidate]:
        results: list[EnumCandidate] = []
        i = 0
        in_code = False

        while i < len(lines):
            line = lines[i]
            if self._code_fence_re.match(line):
                in_code = not in_code
                i += 1
                continue
            if in_code:
                i += 1
                continue

            if "|" not in line:
                i += 1
                continue

            start = i
            block: list[str] = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                block.append(lines[i].strip())
                i += 1

            if len(block) < 2:
                continue

            if self._is_non_enum_field_table(block):
                continue

            if not self._is_two_column_table(block):
                continue

            field_hint = self._guess_field_hint(lines, start)
            results.append(
                EnumCandidate(
                    candidate_type="table_enum",
                    chunk="\n".join(block),
                    start_line=start + 1,
                    end_line=i,
                    field_hint=field_hint,
                    debug_reason="table_2col_markdown",
                )
            )
        return results

    def _detect_space_table_blocks(self, lines: list[str]) -> list[EnumCandidate]:
        """
        Detect pseudo table rows split by large spaces:
        Key<3+spaces>Value
        """
        results: list[EnumCandidate] = []
        i = 0
        in_code = False
        while i < len(lines):
            line = lines[i]
            if self._code_fence_re.match(line):
                in_code = not in_code
                i += 1
                continue
            if in_code:
                i += 1
                continue
            if not self._space_table_row_re.match(line) or "|" in line:
                i += 1
                continue

            start = i
            block: list[str] = []
            while i < len(lines):
                cur = lines[i]
                if not cur.strip():
                    break
                if "|" in cur:
                    break
                if self._space_table_row_re.match(cur):
                    block.append(cur.rstrip())
                    i += 1
                    continue
                break

            title_hint = self._has_tableish_title(start + 1)
            min_rows = 2 if title_hint else 3
            if len(block) < min_rows:
                i += 1
                continue

            md_rows = self._space_rows_to_markdown(block)
            if len(md_rows) < min_rows:
                i += 1
                continue
            md_block = self._markdown_table_from_pairs(md_rows)
            if not md_block:
                i += 1
                continue

            field_hint = self._guess_field_hint(lines, start)
            results.append(
                EnumCandidate(
                    candidate_type="table_enum_space",
                    chunk=md_block,
                    start_line=start + 1,
                    end_line=i,
                    field_hint=field_hint,
                    debug_reason="space_table_detected",
                )
            )
        return results

    def _detect_list_blocks(self, lines: list[str]) -> list[EnumCandidate]:
        results: list[EnumCandidate] = []
        i = 0
        in_code = False

        while i < len(lines):
            line = lines[i]
            if self._code_fence_re.match(line):
                in_code = not in_code
                i += 1
                continue
            if in_code:
                i += 1
                continue

            if not self._list_re.match(line):
                i += 1
                continue

            start = i
            items: list[str] = []
            while i < len(lines):
                m = self._list_re.match(lines[i])
                if not m:
                    break
                value = m.group(1).strip()
                if value:
                    items.append(value)
                i += 1

            if len(items) >= 2:
                field_hint = self._guess_field_hint(lines, start)
                results.append(
                    EnumCandidate(
                        candidate_type="list_enum",
                        chunk="\n".join(items),
                        start_line=start + 1,
                        end_line=i,
                        field_hint=field_hint,
                        debug_reason="list_block",
                    )
                )
        return results

    def _detect_sentence_enums(self, lines: list[str]) -> list[EnumCandidate]:
        """
        Detect enum values embedded in prose, e.g.:
        "包含的值有：FTP，HTTP，HTTPS"
        """
        results: list[EnumCandidate] = []
        for idx, line in enumerate(lines):
            text = line.strip()
            if not text:
                continue
            if "包含的值有" not in text and "取值为" not in text and "取值有" not in text:
                continue
            values = self._extract_sentence_enum_values(text)
            if len(values) < 2:
                continue
            field_hint = self._guess_field_hint(lines, idx)
            if not field_hint:
                field_hint = self._guess_field_from_sentence(text)
            chunk = "\n".join(values)
            results.append(
                EnumCandidate(
                    candidate_type="list_enum_sentence",
                    chunk=chunk,
                    start_line=idx + 1,
                    end_line=idx + 1,
                    field_hint=field_hint,
                    debug_reason="sentence_value_list",
                )
            )
        return results

    def _extract_inline_kv_line(self, line: str) -> Optional[tuple[Optional[str], str]]:
        # Example: nNetAction：动作 1：允许 2：拒绝
        matches = re.findall(r"([A-Za-z0-9_\-/\.]+|\d+)\s*[：:]\s*([^：:\s][^：:]*)", line)
        if len(matches) < 2:
            return None

        parsed = [(k.strip(), v.strip()) for k, v in matches if k.strip() and v.strip()]
        if len(parsed) < 2:
            return None

        field_hint = None
        first_key = parsed[0][0]
        if re.match(r"^[A-Za-z_][\w\-.]*$", first_key):
            field_hint = first_key

        if field_hint:
            parsed = parsed[1:]
        if len(parsed) < 2:
            return None
        filtered = [(k, v) for k, v in parsed if self._is_enum_pair(k, v)]
        if len(filtered) < 2:
            return None

        # Inline enum must be compact; otherwise it's usually log/noise line.
        if len(line) > 180:
            return None

        chunk = "\n".join([f"{k}: {v}" for k, v in filtered])
        return field_hint, chunk

    def _guess_field_hint(self, lines: list[str], index: int) -> Optional[str]:
        # Look upward for nearest field declaration line.
        for j in range(index - 1, max(-1, index - 4), -1):
            line = lines[j].strip()
            if not line:
                continue
            m = self._field_re.match(line)
            if not m:
                continue
            key = m.group(1).strip()
            if key and not key.isdigit():
                return key
        return None

    def _looks_like_field_definition(self, key: str, value: str) -> bool:
        key = key.strip()
        value = value.strip().split()[0].strip(",;.")
        if key.isdigit():
            return False
        return bool(self._type_word_re.match(value))

    def _is_two_column_table(self, table_lines: list[str]) -> bool:
        if len(table_lines) < 2:
            return False
        # Require markdown table separator row to avoid log lines with "|".
        has_separator = any(
            re.match(r"^\s*\|?\s*:?-{2,}:?\s*\|\s*:?-{2,}:?\s*\|?\s*$", row)
            for row in table_lines[1:3]
        )
        # For extracted PDF text, many real 2-col tables lose separator row.
        # If no separator, require a small/clean 2-col block to keep recall controllable.
        if not has_separator and len(table_lines) > 8:
            return False
        for row in table_lines:
            cols = [c.strip() for c in row.split("|") if c.strip()]
            if len(cols) != 2:
                return False
        return True

    def _is_non_enum_field_table(self, table_lines: list[str]) -> bool:
        header = table_lines[0].lower().replace(" ", "")
        signals = ("字段名", "类型", "说明", "field", "type", "description")
        return all(signal in header for signal in signals[:3]) or (
            "field" in header and "type" in header and "description" in header
        )

    def _filter_kv_block(self, block: list[str]) -> list[tuple[str, str]]:
        filtered_pairs: list[tuple[str, str]] = []
        for line in block:
            m = self._kv_re.match(line)
            if not m:
                continue
            key, value = m.group(1).strip(), m.group(2).strip()
            if self._is_enum_pair(key, value):
                filtered_pairs.append((key, value))
        return filtered_pairs

    def _space_rows_to_markdown(self, rows: list[str]) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for row in rows:
            parts = re.split(r"\s{3,}", row.strip(), maxsplit=1)
            if len(parts) != 2:
                continue
            left, right = parts[0].strip(), parts[1].strip()
            if not left or not right:
                continue
            if len(left) > 40 or len(right) > 120:
                continue
            pairs.append((left, right))
        return pairs

    def _markdown_table_from_pairs(self, pairs: list[tuple[str, str]]) -> str:
        if len(pairs) < 2:
            return ""
        lines = [
            "| key | value |",
            "| --- | --- |",
        ]
        for left, right in pairs:
            lines.append(f"| {left} | {right} |")
        return "\n".join(lines)

    def _extract_kv_segments(
        self, block: list[str], default_field: Optional[str]
    ) -> list[tuple[list[str], Optional[str]]]:
        pairs = self._filter_kv_block(block)
        if len(pairs) < 2:
            return []

        segments: list[tuple[list[str], Optional[str]]] = []
        current: list[tuple[str, str]] = []
        current_field = default_field
        prev_key: Optional[str] = None
        prev_kind: Optional[str] = None

        def flush() -> None:
            nonlocal current, current_field, prev_key, prev_kind
            if len(current) >= 2:
                seg_lines = [f"{k}：{v}" for k, v in current]
                normalized_field = self._normalize_field_from_segment(seg_lines, current_field)
                segments.append((seg_lines, normalized_field))
            current = []
            prev_key = None
            prev_kind = None

        for key, value in pairs:
            if self._is_field_header_key_value(key, value):
                flush()
                current_field = key
                continue

            kind = "num" if key.isdigit() else "word"
            if prev_kind and kind != prev_kind:
                flush()
            elif (
                kind == "num"
                and prev_key
                and prev_key.isdigit()
                and key == "1"
                and int(prev_key) >= 2
            ):
                # Numeric enum restarts indicate a new field section.
                flush()

            current.append((key, value))
            prev_key = key
            prev_kind = kind

        flush()
        return segments

    def _is_field_header_key_value(self, key: str, value: str) -> bool:
        if key.isdigit():
            return False
        lower_key = key.lower()
        lower_val = value.lower()
        if lower_key in {"level", "state", "severity", "priority", "status", "type"}:
            return True
        header_markers = ("风险级别", "事件状态", "状态", "等级", "级别", "取值")
        return any(marker in lower_val for marker in header_markers)

    def _normalize_field_from_segment(
        self, seg_lines: list[str], current_field: Optional[str]
    ) -> Optional[str]:
        text = " ".join(seg_lines)
        keys = []
        for line in seg_lines:
            m = self._kv_re.match(line)
            if m:
                keys.append(m.group(1).strip())
        if any(x in text for x in ("低危", "中危", "高危", "严重事件")):
            return "level"
        if any(x in text for x in ("有风险", "已处理", "已忽略")):
            return "state"
        if set(keys).issubset({"7", "30", "180"}) and any("天内" in x for x in seg_lines):
            return "range_days"
        return current_field

    def _guess_field_from_sentence(self, text: str) -> Optional[str]:
        m = re.search(r"([A-Za-z_][\w\-.]{1,40})[^。；;]{0,30}(?:包含的值有|取值为|取值有)", text)
        if m:
            return m.group(1)
        return None

    def _extract_sentence_enum_values(self, text: str) -> list[str]:
        # Focus on code-like enum tokens to control noise.
        token_pattern = re.compile(r"\b[A-Z][A-Z0-9_]{1,14}\b")
        tokens = token_pattern.findall(text)
        dedup: list[str] = []
        for token in tokens:
            if token in {"RFC5424", "RFC3339", "INT64", "ID", "GMT", "HH", "MM"}:
                continue
            # Drop long hash-like IDs and generic noisy tokens.
            if re.fullmatch(r"[A-F0-9]{8,}", token):
                continue
            if token not in dedup:
                dedup.append(token)
        return dedup

    def _is_enum_pair(self, key: str, value: str) -> bool:
        k = key.strip()
        v = value.strip()
        if not k or not v:
            return False
        score = self._enum_pair_score(k, v)
        # Numeric keys are more likely enum values; allow slightly lower threshold.
        threshold = 1 if k.isdigit() else 2
        return score >= threshold

    def _enum_pair_score(self, key: str, value: str) -> int:
        k = key.strip()
        v = value.strip()
        lower_key = k.lower()
        lower_val = v.lower()

        score = 0
        if k.isdigit():
            score += 2
        if lower_key in self._enum_word_keys:
            score += 2
        if re.match(r"^[A-Z][A-Z0-9_]{1,14}$", k):
            score += 1
        if len(v) <= 40:
            score += 1
        if any(x in v for x in ("低危", "中危", "高危", "严重", "有风险", "已处理", "已忽略")):
            score += 2

        if self._datetime_key_re.match(k):
            score -= 3
        if re.search(r"[{}\\[\\]\"]", v):
            score -= 2
        if self._looks_like_field_definition(k, v):
            score -= 2
        if lower_key in self._non_enum_key_blacklist:
            score -= 2
        if any(marker in lower_val for marker in self._noise_value_markers):
            score -= 2
        if "http://" in lower_val or "https://" in lower_val:
            score -= 3
        return score

    def _deduplicate(self, candidates: list[EnumCandidate]) -> list[EnumCandidate]:
        seen: set[tuple[str, str]] = set()
        result: list[EnumCandidate] = []
        for item in candidates:
            key = (item.field_hint or "", item.chunk)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def _attach_title_context(self, candidates: list[EnumCandidate], title_nodes: list[TitleNode]) -> None:
        indexer = TitleIndexer()
        for item in candidates:
            path_nodes = indexer.get_title_path_for_line(title_nodes, item.start_line)
            path = [f"H{n.level}:{n.title}" for n in path_nodes]
            item.title_path = path
            item.parent_title = path[-1] if path else None
            if path:
                heading_context = "\n".join([f"{'#' * n.level} {n.title}" for n in path_nodes])
                item.context_chunk = f"{heading_context}\n\n{item.chunk}"
            else:
                item.context_chunk = item.chunk

    def _has_tableish_title(self, line_index: int) -> bool:
        if not hasattr(self, "_title_indexer") or not hasattr(self, "_title_nodes"):
            return False
        path = self._title_indexer.get_title_path_for_line(self._title_nodes, line_index)
        text = " ".join(n.title for n in path)
        return any(word in text for word in self._title_table_hint_words)


def detect_enum_candidates(markdown_text: str) -> list[dict[str, Any]]:
    return EnumDetector().detect(markdown_text)
