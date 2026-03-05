from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.pipeline.workflow import run_enum_workflow


def run_pipeline(input_path: str | Path) -> dict[str, Any]:
    return run_enum_workflow(input_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LlamaIndex enum extraction workflow: Loader -> Cleaner -> Detector -> LLM -> Validator"
    )
    parser.add_argument("--input", required=True, help="Path to .pdf/.docx/.txt/.md document")
    parser.add_argument("--output", help="Optional output JSON file path")
    args = parser.parse_args()

    result = run_pipeline(args.input)
    payload = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        print(f"Wrote result to: {output_path}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
