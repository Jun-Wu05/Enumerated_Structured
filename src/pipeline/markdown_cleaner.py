from __future__ import annotations

import re
from collections import Counter


class MarkdownCleaner:
    """
    Normalize extracted text while keeping list/table structures intact.
    """

    _page_line_re = re.compile(
        r"^\s*(?:第?\s*\d+\s*页|page\s*\d+(?:\s*/\s*\d+)?)\s*$", re.IGNORECASE
    )
    _list_line_re = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
    _enum_line_re = re.compile(r"^\s*(?:\d+|[A-Za-z_][\w\-/\.]{0,24})\s*[：:]\s+\S+")
    _header_footer_noise_re = re.compile(
        r"^\s*(?:长亭科技(?:\s+\S+)?)\s*$|^\s*\S+\s+长亭科技\s*$"
    )
    _preserve_line_breaks = True

    def clean(self, text: str) -> str:
        if not text:
            return ""
        normalized = self._normalize_newlines(text)
        lines = [line.rstrip() for line in normalized.split("\n")]
        lines = self._remove_page_noise(lines)
        lines = self._remove_repeated_headers_or_footers(lines)
        lines = self._merge_wrapped_lines(lines)
        lines = self._normalize_heading_lines(lines)
        lines = self._convert_space_columns_to_markdown(lines)
        return self._squash_blank_lines("\n".join(lines)).strip()

    def _normalize_newlines(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\u00a0", " ")
        return text

    def _remove_page_noise(self, lines: list[str]) -> list[str]:
        cleaned: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                cleaned.append("")
                continue
            if self._page_line_re.match(stripped):
                continue
            if self._header_footer_noise_re.match(stripped):
                continue
            if stripped.isdigit() and len(stripped) <= 3:
                continue
            cleaned.append(line)
        return cleaned

    def _remove_repeated_headers_or_footers(self, lines: list[str]) -> list[str]:
        candidates = [
            line.strip()
            for line in lines
            if line.strip()
            and len(line.strip()) <= 40
            and "|" not in line
            and not self._list_line_re.match(line)
            and ":" not in line
            and "：" not in line
        ]
        counter = Counter(candidates)
        repeated = {line for line, count in counter.items() if count >= 3}
        if not repeated:
            return lines
        return [line for line in lines if line.strip() not in repeated]

    def _merge_wrapped_lines(self, lines: list[str]) -> list[str]:
        if self._preserve_line_breaks:
            # Preserve original line boundaries to avoid flattening table/list structure.
            return [ln.strip() if ln.strip() else "" for ln in lines]

        merged: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                merged.append("")
                continue

            if not merged:
                merged.append(stripped)
                continue

            prev = merged[-1]
            if not prev:
                merged.append(stripped)
                continue

            if self._should_keep_separate(prev, stripped):
                merged.append(stripped)
            else:
                # Conservative merge only for plain paragraph flow.
                if self._can_paragraph_merge(prev, stripped):
                    merged[-1] = f"{prev} {stripped}"
                else:
                    merged.append(stripped)
        return merged

    def _should_keep_separate(self, prev: str, curr: str) -> bool:
        if "|" in prev or "|" in curr:
            return True
        if self._looks_like_table_row(prev) or self._looks_like_table_row(curr):
            return True
        if self._list_line_re.match(prev) or self._list_line_re.match(curr):
            return True
        if self._enum_line_re.match(prev) or self._enum_line_re.match(curr):
            return True
        if re.match(r"^\s*#{1,6}\s+", curr):
            return True
        if re.match(r"^\s*```", prev) or re.match(r"^\s*```", curr):
            return True
        if re.search(r"[。！？.!?：:；;]$", prev):
            return True
        if re.match(r"^\s*\d+\s*[：:]", curr):
            return True
        if re.match(r"^\s*[A-Za-z_][\w.-]*\s*[：:]\s*", curr):
            return True
        return False

    def _can_paragraph_merge(self, prev: str, curr: str) -> bool:
        # Stop global newline flattening: merge only when both lines look like prose.
        if len(prev) < 8 or len(curr) < 8:
            return False
        if prev.endswith(("。", "！", "？", ".", "!", "?", "；", ";", "：", ":")):
            return False
        if re.match(r"^\s*[A-Z0-9_/\-.]{2,}\s*$", curr):
            return False
        if re.match(r"^\s*#{1,6}\s+", curr):
            return False
        if re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", curr):
            return False
        if self._enum_line_re.match(curr):
            return False
        if self._looks_like_table_row(prev) or self._looks_like_table_row(curr):
            return False
        return True

    def _looks_like_table_row(self, line: str) -> bool:
        s = line.rstrip()
        if "|" in s:
            return True
        # PDF often encodes columns as large gaps.
        if len(re.findall(r"\S(?:\s{3,})\S", s)) >= 1:
            return True
        # Common table headers with multiple columns.
        if re.search(r"(字段|类型|说明)\s{2,}(字段|类型|说明)", s):
            return True
        return False

    def _squash_blank_lines(self, text: str) -> str:
        return re.sub(r"\n{3,}", "\n\n", text)

    def _normalize_heading_lines(self, lines: list[str]) -> list[str]:
        normalized: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                normalized.append("")
                continue
            if re.match(r"^\[H([1-6])\]\s+", stripped):
                level = int(re.match(r"^\[H([1-6])\]\s+", stripped).group(1))
                title = re.sub(r"^\[H[1-6]\]\s+", "", stripped).strip()
                normalized.append(f"{'#' * level} {title}")
                continue
            if re.match(r"^#{1,6}\s+", stripped):
                normalized.append(stripped)
                continue
            level = self._heuristic_heading_level(stripped)
            if level > 0:
                normalized.append(f"{'#' * level} {stripped}")
            else:
                normalized.append(stripped)
        return normalized

    def _heuristic_heading_level(self, line: str) -> int:
        if len(line) > 60:
            return 0
        if re.match(r"^\d+(?:\.\d+){0,3}\s+\S+", line):
            dots = line.split()[0].count(".")
            return min(3, dots + 1)
        if re.match(r"^[一二三四五六七八九十]+[、.]\s*\S+", line):
            return 2
        if re.match(r"^第[一二三四五六七八九十\d]+[章节部分]\s*\S*", line):
            return 1
        return 0

    def _convert_space_columns_to_markdown(self, lines: list[str]) -> list[str]:
        """
        Convert blocks with column-like spacing into markdown table rows.
        Example: "字段名   类型   说明" -> "| 字段名 | 类型 | 说明 |"
        """
        out: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if not self._looks_like_space_column_row(line):
                out.append(line)
                i += 1
                continue

            block: list[str] = []
            while i < len(lines) and self._looks_like_space_column_row(lines[i]):
                block.append(lines[i].strip())
                i += 1

            parsed_rows = [self._split_space_columns(row) for row in block]
            parsed_rows = [r for r in parsed_rows if len(r) >= 2]
            if len(parsed_rows) < 2:
                out.extend(block)
                continue

            col_count = max(len(r) for r in parsed_rows)
            if col_count < 2 or col_count > 5:
                out.extend(block)
                continue

            normalized = [r + [""] * (col_count - len(r)) for r in parsed_rows]
            header = normalized[0]
            out.append("| " + " | ".join(header) + " |")
            out.append("| " + " | ".join(["---"] * col_count) + " |")
            for row in normalized[1:]:
                out.append("| " + " | ".join(row) + " |")
        return out

    def _looks_like_space_column_row(self, line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        if "|" in s:
            return False
        if re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", s):
            return False
        if re.match(r"^\s*#{1,6}\s+", s):
            return False
        return bool(re.search(r"\S\s{3,}\S", s))

    def _split_space_columns(self, line: str) -> list[str]:
        parts = re.split(r"\s{3,}", line.strip())
        parts = [re.sub(r"\s+", " ", p).strip() for p in parts if p.strip()]
        return parts


def clean_markdown(text: str) -> str:
    return MarkdownCleaner().clean(text)
