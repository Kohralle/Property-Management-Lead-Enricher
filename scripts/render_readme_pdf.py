#!/usr/bin/env python3
"""
Pre-render Mermaid diagrams in README.md, then convert the whole thing to PDF.
Outputs submission/README.pdf.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
README = ROOT / "README.md"
OUT_PDF = ROOT / "submission" / "README.pdf"
IMGS = ROOT / "submission" / "_diagrams"

MERMAID_BLOCK = re.compile(
    r"```mermaid\n(.*?)```", re.DOTALL
)


def render_diagram(source: str, index: int) -> Path:
    IMGS.mkdir(parents=True, exist_ok=True)
    src_file = IMGS / f"diagram_{index}.mmd"
    out_file = IMGS / f"diagram_{index}.png"
    src_file.write_text(source)
    result = subprocess.run(
        ["mmdc", "-i", str(src_file), "-o", str(out_file),
         "-b", "white", "--scale", "2"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"mmdc failed for diagram {index}:\n{result.stderr}", file=sys.stderr)
        return None
    return out_file


def main():
    text = README.read_text()
    counter = 0

    def replace(match: re.Match) -> str:
        nonlocal counter
        source = match.group(1)
        img_path = render_diagram(source, counter)
        counter += 1
        if img_path is None:
            return match.group(0)
        rel = img_path.relative_to(ROOT)
        return f"![]({rel})"

    processed = MERMAID_BLOCK.sub(replace, text)

    with tempfile.NamedTemporaryFile(
        suffix=".md", dir=ROOT, mode="w", delete=False, prefix="_readme_render_"
    ) as tmp:
        tmp.write(processed)
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            ["md-to-pdf", str(tmp_path)],
            capture_output=True, text=True, cwd=ROOT,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            sys.exit(1)
        generated = tmp_path.with_suffix(".pdf")
        generated.rename(OUT_PDF)
        print(f"PDF written to {OUT_PDF}")
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
