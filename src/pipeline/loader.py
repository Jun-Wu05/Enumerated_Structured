from __future__ import annotations

import statistics
from pathlib import Path
from typing import Iterable
import re

try:
    from llama_index.core import SimpleDirectoryReader
    _LOADER_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - env dependent
    SimpleDirectoryReader = None  # type: ignore
    _LOADER_IMPORT_ERROR = exc


class Loader:
    """Load document text via LlamaIndex readers."""

    SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}

    def __init__(self) -> None:
        if _LOADER_IMPORT_ERROR is not None:
            raise ImportError(
                "LlamaIndex loader is required. Install dependencies: "
                "pip install llama-index llama-index-readers-file"
            ) from _LOADER_IMPORT_ERROR
        self._file_extractor = self._build_file_extractor()

    def load(self, file_path: str | Path) -> str:
        nodes = self.load_nodes(file_path=file_path, debug=False)
        return "\n\n".join(str(node["text"]).strip() for node in nodes if str(node["text"]).strip())

    def load_nodes(self, file_path: str | Path, debug: bool = False) -> list[dict[str, object]]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {path}")

        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_SUFFIXES:
            raise ValueError(
                f"Unsupported file type: {suffix}. "
                f"Supported types: {sorted(self.SUPPORTED_SUFFIXES)}"
            )

        if suffix == ".pdf":
            pdf_nodes = self._load_pdf_nodes_with_layout(path, debug=debug)
            if pdf_nodes:
                return pdf_nodes

        reader = SimpleDirectoryReader(
            input_files=[str(path)],
            file_extractor=self._file_extractor,
            filename_as_id=True,
            required_exts=[suffix],
        )
        documents = reader.load_data()
        nodes: list[dict[str, object]] = []
        for idx, doc in enumerate(documents, start=1):
            text = (doc.text or "").strip()
            if not text:
                continue
            metadata = dict(getattr(doc, "metadata", {}) or {})
            metadata.setdefault("page_label", str(idx))
            metadata.setdefault("file_name", path.name)
            metadata.setdefault("source", str(path))
            nodes.append({"text": text, "metadata": metadata})
        return nodes

    def load_many(self, file_paths: Iterable[str | Path]) -> str:
        paths = [Path(p) for p in file_paths]
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(f"File does not exist: {path}")
            if path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
                raise ValueError(
                    f"Unsupported file type: {path.suffix.lower()}. "
                    f"Supported types: {sorted(self.SUPPORTED_SUFFIXES)}"
                )

        chunks: list[str] = []
        for path in paths:
            nodes = self.load_nodes(path)
            chunks.extend([str(node["text"]).strip() for node in nodes if str(node["text"]).strip()])
        return "\n\n".join(chunks)

    def _build_file_extractor(self) -> dict[str, object]:
        file_extractor: dict[str, object] = {}
        try:
            from llama_index.readers.file import DocxReader, PDFReader

            file_extractor[".pdf"] = PDFReader()
            file_extractor[".docx"] = DocxReader()
        except Exception:
            # Keep default SimpleDirectoryReader behavior when optional readers are unavailable.
            pass
        return file_extractor

    def _load_pdf_nodes_with_layout(self, path: Path, debug: bool = False) -> list[dict[str, object]]:
        """
        Use PyMuPDF span metadata to add heading hints into extracted text.
        Lines detected as headings are prefixed with [H1]/[H2]/[H3].
        """
        try:
            import fitz
        except Exception:
            return []

        page_lines: dict[int, list[dict[str, object]]] = {}
        page_tables: dict[int, list[dict[str, object]]] = {}
        plumber_tables = self._extract_tables_with_pdfplumber(path)
        with fitz.open(path) as doc:
            for page_idx, page in enumerate(doc):
                page_lines.setdefault(page_idx, [])
                page_tables.setdefault(page_idx, [])
                page_dict = page.get_text("dict")
                for block in page_dict.get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        if not spans:
                            continue
                        text = "".join(span.get("text", "") for span in spans).strip()
                        if not text:
                            continue
                        sizes = [float(span.get("size", 0) or 0) for span in spans]
                        max_size = max(sizes) if sizes else 0.0
                        avg_size = sum(sizes) / len(sizes) if sizes else 0.0
                        is_bold = any(int(span.get("flags", 0)) & 16 for span in spans)
                        y0 = float(line.get("bbox", [0, 0, 0, 0])[1])
                        page_lines[page_idx].append(
                            {
                                "text": text,
                                "max_size": max_size,
                                "avg_size": avg_size,
                                "is_bold": is_bold,
                                "y0": y0,
                            }
                        )
                # Try extracting table structures and keep them as markdown.
                try:
                    finder = getattr(page, "find_tables", None)
                    if callable(finder):
                        tables = finder()
                        for tb in getattr(tables, "tables", []):
                            rows = tb.extract() or []
                            md = self._rows_to_markdown_table(rows)
                            if md:
                                y0 = float(getattr(tb, "bbox", [0, 0, 0, 0])[1])
                                page_tables[page_idx].append({"markdown": md, "y0": y0})
                except Exception:
                    pass
                # Merge pdfplumber tables as fallback source.
                for tb in plumber_tables.get(page_idx, []):
                    page_tables[page_idx].append(tb)
        all_line_records = [row for rows in page_lines.values() for row in rows]
        if not all_line_records:
            return []
        size_baseline = statistics.median(float(r["avg_size"]) for r in all_line_records)
        nodes: list[dict[str, object]] = []
        for page_idx in sorted(page_lines.keys()):
            merged_items: list[tuple[float, str, str]] = []
            for rec in page_lines.get(page_idx, []):
                text = str(rec["text"])
                heading_level = self._estimate_heading_level(
                    text=text,
                    avg_size=float(rec["avg_size"]),
                    max_size=float(rec["max_size"]),
                    is_bold=bool(rec["is_bold"]),
                    baseline=size_baseline,
                )
                rendered = f"[H{heading_level}] {text}" if heading_level else text
                merged_items.append((float(rec["y0"]), "line", rendered))

            for tb in page_tables.get(page_idx, []):
                merged_items.append((float(tb["y0"]), "table", str(tb["markdown"])))

            merged_items.sort(key=lambda x: x[0])
            page_out_lines: list[str] = []
            for _, typ, content in merged_items:
                if typ == "table":
                    page_out_lines.append(content)
                    page_out_lines.append("")
                else:
                    page_out_lines.append(content)
            page_text = "\n".join(page_out_lines).strip()
            if not page_text:
                continue
            metadata = {
                "page_label": str(page_idx + 1),
                "file_name": path.name,
                "source": str(path),
            }
            if debug:
                metadata["table_count"] = len(page_tables.get(page_idx, []))
                metadata["line_count"] = len(page_lines.get(page_idx, []))
            nodes.append({"text": page_text, "metadata": metadata})
        return nodes

    def _extract_tables_with_pdfplumber(self, path: Path) -> dict[int, list[dict[str, object]]]:
        tables_by_page: dict[int, list[dict[str, object]]] = {}
        try:
            import pdfplumber  # type: ignore
        except Exception:
            return tables_by_page

        try:
            table_settings = {
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "snap_tolerance": 3,
                "join_tolerance": 3,
                "intersection_tolerance": 3,
                "min_words_vertical": 2,
                "min_words_horizontal": 1,
            }
            with pdfplumber.open(str(path)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    rows = []
                    extracted_tables = page.extract_tables(table_settings=table_settings) or []
                    if not extracted_tables:
                        one = page.extract_table(table_settings=table_settings)
                        if one:
                            extracted_tables = [one]
                    for table in extracted_tables:
                        md = self._rows_to_markdown_table(table or [])
                        if md:
                            rows.append({"markdown": md, "y0": 1e9})  # append after text on page
                    if rows:
                        tables_by_page[page_idx] = rows
        except Exception:
            return {}
        return tables_by_page

    def _rows_to_markdown_table(self, rows: list[list[str]]) -> str:
        cleaned_rows: list[list[str]] = []
        for row in rows:
            if not row:
                continue
            cells = [self._clean_cell(str(c or "")) for c in row]
            if sum(1 for c in cells if c) < 2:
                continue
            cleaned_rows.append(cells)
        if len(cleaned_rows) < 2:
            return ""

        max_cols = max(len(r) for r in cleaned_rows)
        normalized = [r + [""] * (max_cols - len(r)) for r in cleaned_rows]
        header = normalized[0]
        divider = ["---"] * max_cols
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(divider) + " |",
        ]
        for row in normalized[1:]:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    def _clean_cell(self, text: str) -> str:
        text = text.replace("\n", " ").replace("\r", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text.replace("|", "\\|")

    def _estimate_heading_level(
        self, text: str, avg_size: float, max_size: float, is_bold: bool, baseline: float
    ) -> int:
        t = text.strip()
        if len(t) > 80:
            return 0
        if t.startswith("#"):
            return 1
        if avg_size >= baseline * 1.45 or max_size >= baseline * 1.55:
            return 1
        if avg_size >= baseline * 1.3 or (is_bold and avg_size >= baseline * 1.15):
            return 2
        if avg_size >= baseline * 1.15 and self._looks_like_section_title(t):
            return 3
        if self._looks_like_section_title(t):
            return 3
        return 0

    def _looks_like_section_title(self, text: str) -> bool:
        import re

        if re.match(r"^\d+(?:\.\d+){0,3}\s+\S+", text):
            return True
        if re.match(r"^[一二三四五六七八九十]+[、.]\s*\S+", text):
            return True
        if re.match(r"^第[一二三四五六七八九十\d]+[章节部分]\s*\S*", text):
            return True
        return False


def load(file_path: str | Path) -> str:
    return Loader().load(file_path)
