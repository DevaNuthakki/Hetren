#!/usr/bin/env bash
# Build docs/TECHNICAL_REPORT.md into a PDF with pandoc and Typst, in a container pinned by digest (Milestone 4,
# step 8). Used by CI's report job and by the operator; nothing is downloaded but the image, and the container
# runs without a network.
#
#   scripts/build_report_pdf.sh <output folder>      writes TECHNICAL_REPORT.pdf and TECHNICAL_REPORT.pdf.sha256
#
# Typst handles the report's Unicode (−, ≥, ½, A₁) without a LaTeX installation. The image is pandoc 3.11.0.0
# with Typst (Alpine, 86 MB). scripts/report-pdf.typ sets the layout: ragged right, headings kept with the
# text that follows, and a smaller font in tables.
#
# Reproducible: the PDF's timestamp is the report's date (REPORT_DATE_EPOCH, passed as SOURCE_DATE_EPOCH), so the same
# report, layout file and image always give the same bytes. The sha256 recorded in docs/RELEASE_NOTES.md can be
# checked by rebuilding from the tagged commit. Change REPORT_DATE_EPOCH when the report is revised for a release.
set -euo pipefail

IMAGE="pandoc/typst:3.11.0.0@sha256:ae9dfa3c58cae72d363484442993b761ff4bc30202ec12823bc1e59fa952c892"
REPORT_DATE_EPOCH=1794355200  # 2026-11-11T00:00:00Z, the v1.0.0 report's date
out="${1:?usage: build_report_pdf.sh <output folder>}"
root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$out"
out="$(cd "$out" && pwd)"

docker run --rm --platform linux/amd64 --network none --user "$(id -u):$(id -g)" -e SOURCE_DATE_EPOCH="$REPORT_DATE_EPOCH" \
  -v "$root/docs":/data:ro -v "$root/scripts/report-pdf.typ":/style/report-pdf.typ:ro -v "$out":/out -w /out "$IMAGE" \
  -f markdown+lists_without_preceding_blankline /data/TECHNICAL_REPORT.md --include-before-body=/style/report-pdf.typ \
  --pdf-engine=typst -V papersize=a4 -V margin.x=2cm -V margin.y=2.2cm -o /out/TECHNICAL_REPORT.pdf

test -s "$out/TECHNICAL_REPORT.pdf"
(cd "$out" && { sha256sum TECHNICAL_REPORT.pdf 2>/dev/null || shasum -a 256 TECHNICAL_REPORT.pdf; } > TECHNICAL_REPORT.pdf.sha256)
echo "built $out/TECHNICAL_REPORT.pdf ($(wc -c < "$out/TECHNICAL_REPORT.pdf" | tr -d ' ') bytes): $(cut -d' ' -f1 "$out/TECHNICAL_REPORT.pdf.sha256")"
