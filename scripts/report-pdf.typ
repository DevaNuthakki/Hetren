// Layout for the technical report's PDF (scripts/build_report_pdf.sh): pandoc includes this at the start of the
// body, after its template's own settings, so these rules win. Layout only; the text is the Markdown's.
#set par(justify: false)                  // ragged right: no stretched gaps around long code spans
#show heading: set block(sticky: true)    // a heading stays on the page of the text that follows it
#show table: set text(size: 9pt)          // tables a little smaller than the body text
#show table: set par(justify: false)
#set table(inset: (x: 4pt, y: 5pt))
