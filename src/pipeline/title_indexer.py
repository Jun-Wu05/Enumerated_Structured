from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class TitleNode:
    level: int
    title: str
    line_index: int
    parent_line_index: Optional[int]

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "title": self.title,
            "line_index": self.line_index,
            "parent_line_index": self.parent_line_index,
        }


class TitleIndexer:
    _heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

    def build(self, markdown_text: str) -> list[TitleNode]:
        nodes: list[TitleNode] = []
        stack: list[TitleNode] = []
        for idx, line in enumerate(markdown_text.splitlines(), start=1):
            m = self._heading_re.match(line.strip())
            if not m:
                continue
            level = len(m.group(1))
            title = m.group(2).strip()
            while stack and stack[-1].level >= level:
                stack.pop()
            parent = stack[-1] if stack else None
            node = TitleNode(
                level=level,
                title=title,
                line_index=idx,
                parent_line_index=parent.line_index if parent else None,
            )
            nodes.append(node)
            stack.append(node)
        return nodes

    def get_title_path_for_line(self, nodes: list[TitleNode], line_index: int) -> list[TitleNode]:
        valid_nodes = [n for n in nodes if n.line_index <= line_index]
        if not valid_nodes:
            return []
        leaf = max(valid_nodes, key=lambda n: n.line_index)
        by_line = {n.line_index: n for n in nodes}
        path: list[TitleNode] = [leaf]
        parent_idx = leaf.parent_line_index
        while parent_idx is not None and parent_idx in by_line:
            parent = by_line[parent_idx]
            path.append(parent)
            parent_idx = parent.parent_line_index
        path.reverse()
        return path

    def format_tree(self, nodes: list[TitleNode]) -> str:
        lines = []
        for node in nodes:
            indent = "  " * (node.level - 1)
            lines.append(f"{indent}- H{node.level} {node.title} (line={node.line_index})")
        return "\n".join(lines)
