from __future__ import annotations

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


def load(file_path: str | Path) -> str:
    return Loader().load(file_path)
