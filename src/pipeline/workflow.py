from __future__ import annotations

import asyncio
from pathlib import Path
import re
from typing import Any, Optional

try:
    from llama_index.core.workflow import (
        Context,
        Event,
        StartEvent,
        StopEvent,
        Workflow,
        step,
    )
    _WORKFLOW_IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # pragma: no cover - env dependent
    Context = Any  # type: ignore
    Event = object  # type: ignore
    StartEvent = object  # type: ignore
    StopEvent = object  # type: ignore
    Workflow = object  # type: ignore

    def step(fn):  # type: ignore
        return fn

    _WORKFLOW_IMPORT_ERROR = exc

from src.pipeline.enum_detector import EnumDetector
from src.pipeline.enum_validator import EnumValidator
from src.pipeline.llm_extractor import LLMExtractor
from src.pipeline.loader import Loader
from src.pipeline.markdown_cleaner import MarkdownCleaner
from src.pipeline.title_indexer import TitleIndexer


class LoadedEvent(Event):
    input_path: str
    raw_text: str


class CleanedEvent(Event):
    input_path: str
    raw_text: str
    cleaned_text: str


class DetectedEvent(Event):
    input_path: str
    raw_text: str
    cleaned_text: str
    candidates: list[dict[str, Any]]


class ExtractedEvent(Event):
    input_path: str
    raw_text: str
    cleaned_text: str
    candidates: list[dict[str, Any]]
    extracted: list[dict[str, Any]]
    llm_metrics: dict[str, Any]


class EnumExtractionWorkflow(Workflow):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.loader = Loader()
        self.cleaner = MarkdownCleaner()
        self.detector = EnumDetector()
        self.extractor = LLMExtractor()
        self.validator = EnumValidator()

    @step
    async def load_step(self, ctx: Context, ev: StartEvent) -> LoadedEvent:
        input_path = ev.get("input_path")
        if not input_path:
            raise ValueError("Missing required workflow input: input_path")
        raw_text = self.loader.load(input_path)
        return LoadedEvent(input_path=str(input_path), raw_text=raw_text)

    @step
    async def clean_step(self, ctx: Context, ev: LoadedEvent) -> CleanedEvent:
        cleaned_text = self.cleaner.clean(ev.raw_text)
        return CleanedEvent(
            input_path=ev.input_path,
            raw_text=ev.raw_text,
            cleaned_text=cleaned_text,
        )

    @step
    async def detect_step(self, ctx: Context, ev: CleanedEvent) -> DetectedEvent:
        candidates = self.detector.detect(ev.cleaned_text)
        candidates = self._apply_overlap_context(
            candidates=candidates,
            cleaned_text=ev.cleaned_text,
            overlap_tokens=200,
        )
        self._write_structure_log(ev.input_path, ev.cleaned_text, candidates)
        return DetectedEvent(
            input_path=ev.input_path,
            raw_text=ev.raw_text,
            cleaned_text=ev.cleaned_text,
            candidates=candidates,
        )

    @step
    async def extract_step(self, ctx: Context, ev: DetectedEvent) -> ExtractedEvent:
        extracted = self.extractor.extract_many(ev.candidates)
        llm_metrics = self.extractor.get_metrics()
        return ExtractedEvent(
            input_path=ev.input_path,
            raw_text=ev.raw_text,
            cleaned_text=ev.cleaned_text,
            candidates=ev.candidates,
            extracted=extracted,
            llm_metrics=llm_metrics,
        )

    @step
    async def validate_step(self, ctx: Context, ev: ExtractedEvent) -> StopEvent:
        validated = self.validator.validate_many(ev.extracted)
        payload = {
            "input": ev.input_path,
            "raw_length": len(ev.raw_text),
            "cleaned_length": len(ev.cleaned_text),
            "candidate_count": len(ev.candidates),
            "extracted_count": len(ev.extracted),
            "validated_count": len(validated),
            "llm_metrics": ev.llm_metrics,
            "enums": validated,
        }
        return StopEvent(result=payload)

    def _write_structure_log(
        self, input_path: str, cleaned_text: str, candidates: list[dict[str, Any]]
    ) -> None:
        output_path = Path("output") / "test_structure.log"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        indexer = TitleIndexer()
        nodes = indexer.build(cleaned_text)
        lines = []
        lines.append(f"INPUT: {input_path}")
        lines.append("=== TITLE TREE ===")
        lines.append(indexer.format_tree(nodes) or "(no headings)")
        lines.append("")
        lines.append("=== ENUM CANDIDATES ===")
        for i, cand in enumerate(candidates, start=1):
            title_path = cand.get("title_path") or []
            lines.append(
                f"[{i}] type={cand.get('candidate_type')} "
                f"line={cand.get('start_line')}-{cand.get('end_line')} "
                f"field={cand.get('field_hint')} "
                f"title={' > '.join(title_path) if title_path else '(none)'} "
                f"parent={cand.get('parent_title') or '(none)'}"
            )
            preview = str(cand.get("chunk", "")).replace("\n", " | ")
            lines.append(f"    chunk: {preview[:260]}")
        output_path.write_text("\n".join(lines), encoding="utf-8")

    def _apply_overlap_context(
        self, candidates: list[dict[str, Any]], cleaned_text: str, overlap_tokens: int
    ) -> list[dict[str, Any]]:
        if not candidates or not cleaned_text.strip():
            return candidates

        tokens = list(re.finditer(r"\S+", cleaned_text))
        if not tokens:
            return candidates

        line_start_offsets = self._line_start_offsets(cleaned_text)
        for cand in candidates:
            start_line = int(cand.get("start_line") or 1)
            end_line = int(cand.get("end_line") or start_line)
            start_line = max(1, min(start_line, len(line_start_offsets)))
            end_line = max(start_line, min(end_line, len(line_start_offsets)))
            start_char = line_start_offsets[start_line - 1]
            end_char = (
                line_start_offsets[end_line] - 1
                if end_line < len(line_start_offsets)
                else len(cleaned_text)
            )
            center_idx = self._find_first_token_idx(tokens, start_char)
            tail_idx = self._find_last_token_idx(tokens, end_char)
            if center_idx is None:
                continue
            if tail_idx is None or tail_idx < center_idx:
                tail_idx = center_idx
            left = max(0, center_idx - overlap_tokens)
            right = min(len(tokens) - 1, tail_idx + overlap_tokens)
            overlap_chunk = cleaned_text[tokens[left].start() : tokens[right].end()]

            title_path = cand.get("title_path") or []
            heading_context = ""
            if title_path:
                heading_context = "\n".join(
                    [
                        f"{'#' * int(part.split(':', 1)[0].replace('H', ''))} {part.split(':', 1)[1]}"
                        for part in title_path
                        if ":" in part and part.startswith("H")
                    ]
                )
            if heading_context:
                cand["context_chunk"] = f"{heading_context}\n\n{overlap_chunk}"
            else:
                cand["context_chunk"] = overlap_chunk
            cand["overlap_tokens"] = overlap_tokens
        return candidates

    def _line_start_offsets(self, text: str) -> list[int]:
        offsets = [0]
        for m in re.finditer(r"\n", text):
            offsets.append(m.end())
        return offsets

    def _find_first_token_idx(self, tokens: list[re.Match], char_pos: int) -> Optional[int]:
        for i, tk in enumerate(tokens):
            if tk.end() >= char_pos:
                return i
        return None

    def _find_last_token_idx(self, tokens: list[re.Match], char_pos: int) -> Optional[int]:
        for i in range(len(tokens) - 1, -1, -1):
            if tokens[i].start() <= char_pos:
                return i
        return None


def run_enum_workflow(input_path: str | Path) -> dict[str, Any]:
    if _WORKFLOW_IMPORT_ERROR is not None:
        raise ImportError(
            "LlamaIndex workflow is required. Install dependencies: "
            "pip install llama-index llama-index-readers-file llama-index-llms-openai-like"
        ) from _WORKFLOW_IMPORT_ERROR

    workflow = EnumExtractionWorkflow(timeout=120)

    async def _run() -> dict[str, Any]:
        return await workflow.run(input_path=str(input_path))

    try:
        return asyncio.run(_run())
    except RuntimeError as exc:
        if "asyncio.run() cannot be called from a running event loop" not in str(exc):
            raise
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
