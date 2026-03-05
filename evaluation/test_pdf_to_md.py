from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.loader import Loader
from src.pipeline.markdown_cleaner import MarkdownCleaner


def run(input_pdf: Path, output_md: Path, output_raw: Path | None) -> None:
    if not input_pdf.exists():
        raise FileNotFoundError(f"Input file not found: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise ValueError("This test script expects a PDF input.")

    loader = Loader()
    cleaner = MarkdownCleaner()

    print("[STEP 1] Loading PDF...")
    raw_text = loader.load(input_pdf)
    print(f"  raw_text_length={len(raw_text)}")

    if output_raw is not None:
        output_raw.parent.mkdir(parents=True, exist_ok=True)
        output_raw.write_text(raw_text, encoding="utf-8")
        print(f"  wrote_raw_text={output_raw}")

    print("[STEP 2] Cleaning to Markdown...")
    cleaned_md = cleaner.clean(raw_text)
    print(f"  cleaned_md_length={len(cleaned_md)}")

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(cleaned_md, encoding="utf-8")
    print(f"  wrote_cleaned_md={output_md}")

    print("[DONE] PDF -> Markdown export complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step-by-step test: convert uploaded PDF to full Markdown document."
    )
    parser.add_argument("--input", required=True, help="Path to input PDF file")
    parser.add_argument(
        "--output-md",
        default="output/converted.cleaned.md",
        help="Path to full cleaned markdown output",
    )
    parser.add_argument(
        "--output-raw",
        default="output/converted.raw.txt",
        help="Optional path to raw text output (set empty string to disable)",
    )
    args = parser.parse_args()

    input_pdf = Path(args.input)
    output_md = Path(args.output_md)
    output_raw = Path(args.output_raw) if str(args.output_raw).strip() else None
    run(input_pdf=input_pdf, output_md=output_md, output_raw=output_raw)


if __name__ == "__main__":
    main()
