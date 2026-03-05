from __future__ import annotations

import asyncio
from pathlib import Path
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
        return DetectedEvent(
            input_path=ev.input_path,
            raw_text=ev.raw_text,
            cleaned_text=ev.cleaned_text,
            candidates=candidates,
        )

    @step
    async def extract_step(self, ctx: Context, ev: DetectedEvent) -> ExtractedEvent:
        extracted = self.extractor.extract_many(ev.candidates)
        return ExtractedEvent(
            input_path=ev.input_path,
            raw_text=ev.raw_text,
            cleaned_text=ev.cleaned_text,
            candidates=ev.candidates,
            extracted=extracted,
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
            "enums": validated,
        }
        return StopEvent(result=payload)


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
