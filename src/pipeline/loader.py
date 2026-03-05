from __future__ import annotations

import statistics
from pathlib import Path
from typing import Iterable

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
            pdf_text = self._load_pdf_with_layout(path)
            if pdf_text.strip():
                return pdf_text

        reader = SimpleDirectoryReader(
            input_files=[str(path)],
            file_extractor=self._file_extractor,
            filename_as_id=True,
            required_exts=[suffix],
        )
        documents = reader.load_data()
        return "\n\n".join(doc.text.strip() for doc in documents if doc.text and doc.text.strip())

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

        reader = SimpleDirectoryReader(
            input_files=[str(p) for p in paths],
            file_extractor=self._file_extractor,
            filename_as_id=True,
        )
        documents = reader.load_data()
        return "\n\n".join(doc.text.strip() for doc in documents if doc.text and doc.text.strip())

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

    def _load_pdf_with_layout(self, path: Path) -> str:
        """
        Use PyMuPDF span metadata to add heading hints into extracted text.
        Lines detected as headings are prefixed with [H1]/[H2]/[H3].
        """
        try:
            import fitz
        except Exception:
            return ""

        line_records = []
        with fitz.open(path) as doc:
            for page_idx, page in enumerate(doc):
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
                        line_records.append(
                            {
                                "page": page_idx,
                                "text": text,
                                "max_size": max_size,
                                "avg_size": avg_size,
                                "is_bold": is_bold,
                            }
                        )

        if not line_records:
            return ""

        size_baseline = statistics.median(r["avg_size"] for r in line_records)
        lines = []
        for rec in line_records:
            text = rec["text"]
            heading_level = self._estimate_heading_level(
                text=text,
                avg_size=rec["avg_size"],
                max_size=rec["max_size"],
                is_bold=rec["is_bold"],
                baseline=size_baseline,
            )
            if heading_level:
                lines.append(f"[H{heading_level}] {text}")
            else:
                lines.append(text)
        return "\n".join(lines)

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
