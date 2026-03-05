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

    def clean(self, text: str) -> str:
        if not text:
            return ""
        normalized = self._normalize_newlines(text)
        lines = [line.rstrip() for line in normalized.split("\n")]
        lines = self._remove_page_noise(lines)
        lines = self._remove_repeated_headers_or_footers(lines)
        lines = self._merge_wrapped_lines(lines)
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
                merged[-1] = f"{prev} {stripped}"
        return merged

    def _should_keep_separate(self, prev: str, curr: str) -> bool:
        if "|" in prev or "|" in curr:
            return True
        if self._list_line_re.match(prev) or self._list_line_re.match(curr):
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

    def _squash_blank_lines(self, text: str) -> str:
        return re.sub(r"\n{3,}", "\n\n", text)


def clean_markdown(text: str) -> str:
    return MarkdownCleaner().clean(text)
