from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.loader import Loader
from src.pipeline.markdown_cleaner import MarkdownCleaner


def run(
    input_pdf: Path,
    output_md: Path,
    output_raw: Path | None,
    output_pages_md: Path,
    output_page15_md: Path,
    output_nodes_jsonl: Path,
) -> None:
    if not input_pdf.exists():
        raise FileNotFoundError(f"Input file not found: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise ValueError("This test script expects a PDF input.")

    loader = Loader()
    cleaner = MarkdownCleaner()

    print("[STEP 1] Loading PDF...")
    nodes = loader.load_nodes(input_pdf, debug=True)
    raw_text = "\n\n".join(str(n["text"]) for n in nodes)
    print(f"  raw_text_length={len(raw_text)}")
    print(f"  node_count={len(nodes)}")

    output_nodes_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_nodes_jsonl.open("w", encoding="utf-8") as f:
        for node in nodes:
            import json

            f.write(json.dumps(node, ensure_ascii=False) + "\n")
    print(f"  wrote_nodes_jsonl={output_nodes_jsonl}")

    if output_raw is not None:
        output_raw.parent.mkdir(parents=True, exist_ok=True)
        output_raw.write_text(raw_text, encoding="utf-8")
        print(f"  wrote_raw_text={output_raw}")

    print("[STEP 1.1] Rendering page-level markdown previews...")
    by_page: dict[str, str] = {}
    for node in nodes:
        metadata = node.get("metadata", {}) if isinstance(node, dict) else {}
        page = str(metadata.get("page_label", "unknown"))
        text = str(node.get("text", "")).strip()
        if not text:
            continue
        by_page[page] = (by_page.get(page, "") + "\n\n" + text).strip()

    first5_blocks = []
    for page in ["1", "2", "3", "4", "5"]:
        if page in by_page:
            first5_blocks.append(f"# Page {page}\n\n{by_page[page]}")
    output_pages_md.parent.mkdir(parents=True, exist_ok=True)
    output_pages_md.write_text("\n\n---\n\n".join(first5_blocks), encoding="utf-8")
    print(f"  wrote_first5_pages_md={output_pages_md}")

    page15_text = by_page.get("15", "")
    output_page15_md.parent.mkdir(parents=True, exist_ok=True)
    output_page15_md.write_text(page15_text, encoding="utf-8")
    print(f"  wrote_page15_md={output_page15_md}")
    page15_has_pipe = "|" in page15_text
    print(f"  page15_has_pipe={page15_has_pipe}")
    if not page15_has_pipe:
        print("[STOP] Page 15 has no '|' separator. Skip cleaning and focus on loader parsing quality.")
        return

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
        default="output/debug_table.md",
        help="Path to full cleaned markdown output",
    )
    parser.add_argument(
        "--output-raw",
        default="output/converted.raw.txt",
        help="Optional path to raw text output (set empty string to disable)",
    )
    parser.add_argument(
        "--output-pages-md",
        default="output/debug_first5_pages.md",
        help="Path to first 5 pages markdown preview",
    )
    parser.add_argument(
        "--output-page15-md",
        default="output/debug_page15.md",
        help="Path to page 15 markdown for table inspection",
    )
    parser.add_argument(
        "--output-nodes-jsonl",
        default="output/debug_nodes.jsonl",
        help="Path to node-level metadata dump",
    )
    args = parser.parse_args()

    input_pdf = Path(args.input)
    output_md = Path(args.output_md)
    output_raw = Path(args.output_raw) if str(args.output_raw).strip() else None
    output_pages_md = Path(args.output_pages_md)
    output_page15_md = Path(args.output_page15_md)
    output_nodes_jsonl = Path(args.output_nodes_jsonl)
    run(
        input_pdf=input_pdf,
        output_md=output_md,
        output_raw=output_raw,
        output_pages_md=output_pages_md,
        output_page15_md=output_page15_md,
        output_nodes_jsonl=output_nodes_jsonl,
    )


if __name__ == "__main__":
    main()
