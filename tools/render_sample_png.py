#!/usr/bin/env python
"""Render the Summary sheet of the generated workbook to sample_output.png.

Optional developer tool, not part of the pipeline: it exists so the image in
the README can be regenerated from the real .xlsx instead of being mocked up by
hand. It shells out to LibreOffice (xlsx -> pdf), poppler (pdf -> png) and
ImageMagick (crop), none of which are Python dependencies -- if they are not
installed, the committed sample_output.png is still perfectly valid.

    python tools/render_sample_png.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = PROJECT_ROOT / "output" / "daily_sales_consolidated.xlsx"
TARGET = PROJECT_ROOT / "sample_output.png"
REQUIRED = ("soffice", "pdftoppm", "convert")


def main() -> int:
    missing = [tool for tool in REQUIRED if shutil.which(tool) is None]
    if missing:
        print(f"Cannot render: missing {', '.join(missing)}.", file=sys.stderr)
        print("Install libreoffice, poppler-utils and imagemagick, or keep the "
              "committed sample_output.png.", file=sys.stderr)
        return 1

    if not WORKBOOK.is_file():
        print(f"No workbook at {WORKBOOK} - run `make demo` first.", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(work), str(WORKBOOK)])
        pdf = work / f"{WORKBOOK.stem}.pdf"
        # Page 1 of the PDF is the Summary sheet; the workbook is set to print
        # it on a single landscape page, which is what makes this crop reliable.
        run(["pdftoppm", "-png", "-r", "160", "-f", "1", "-l", "1", str(pdf), str(work / "page")])
        run(["convert", str(work / "page-1.png"), "-trim", "+repage",
             "-bordercolor", "white", "-border", "28", str(TARGET)])

    print(f"Wrote {TARGET.relative_to(PROJECT_ROOT)}")
    return 0


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    raise SystemExit(main())
