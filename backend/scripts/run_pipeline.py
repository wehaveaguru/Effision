"""
Step 2 check: "run one sample document through parse -> segregate,
verify output" — and the full pipeline runner for real use.

Usage:
    python scripts/run_pipeline.py data/sample_docs/camber_bolt_specsheet.txt --dry-run
    python scripts/run_pipeline.py data/sample_docs/camber_bolt_specsheet.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv(find_dotenv())

from app.pipeline.graph_model import write_segregation_result, write_source_document  # noqa: E402
from app.pipeline.ingestor import parse_document  # noqa: E402
from app.pipeline.segregate import segregate_document  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file_path", help="Source document to run through the pipeline")
    ap.add_argument(
        "--dry-run", action="store_true", help="Parse + segregate only; do not write to the DB"
    )
    args = ap.parse_args()

    print(f"[1/2] Parsing {args.file_path} ...")
    parsed = parse_document(args.file_path)
    print(f"      -> {len(parsed.raw_text)} chars extracted")

    print("[2/2] Segregating ...")
    result = segregate_document(parsed)
    print(f"      -> product: {result.product_label!r}, {len(result.fields)} fields extracted")
    print(json.dumps(result.model_dump(), indent=2))

    if args.dry_run:
        print("\n--dry-run set: nothing written to the DB.")
        return

    print("\nWriting to DB ...")
    doc_id = write_source_document(parsed)
    written = write_segregation_result(result, doc_id)
    print(
        f"Wrote 1 source document, 1 product node, {len(written['edges'])} proposed edges "
        f"(all status='proposed', pending human review)."
    )


if __name__ == "__main__":
    main()