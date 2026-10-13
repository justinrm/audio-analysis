# Audio Reference Studio — MVP Planning Package

This package is a **specification and code review**, not a completed web app.

## Start here

1. `01_TECHNICAL_MVP_SPEC.md` — product behavior, frontend/backend architecture, data model, API, both output modes, reliability, phased acceptance and tests.
2. `02_SCRIPT_REVIEW.md` — source-grounded review of the four scripts inside the provided `Four_Song_Audit_Evidence.zip`, including reuse opportunities and 16-bit pitfalls.
3. `03_CURSOR_AGENT_FIRST_SESSION.md` — bounded implementation instructions for Cursor Agent to build the **real working frontend/backend skeleton**.
4. `04_TECHNICAL_CHART_REQUIREMENTS.md` — first-class technical dashboard chart catalog, shared contracts, technical ZIP content and validation gates.

## Source evidence reviewed

`Four_Song_Audit_Evidence.zip` contained 37 entries. Reviewed four `.py` scripts (~641 source lines), four archived metrics records, pairwise comparison JSON, NPZ feature files and report/PNGs. The code was statically inspected and all four Python modules passed syntax parsing. End-to-end execution is not verified because the source WAVs are not packaged.

The original four-song audit and `Little Mouse` technical charts define the diagnostic side of the application. The uploaded five `Praise Kink` charts and `Praise_Kink_Lyricist_Reference.md` define the complementary lyricist output and evidence vocabulary. Their chart-generating scripts are not included.

## Proposed operating philosophy

Local first. Audio remains local. **Technical Analysis for WAV-only is a co-equal core product with the five-chart Lyricist Inspiration package; Album QC compares several tracks.** Measured and estimated observations are separated. User controls interpretation. Export `technical`, `lyricist`, or `combined` with no cloud or NIM requirement. Real frontend now, public access later only if justified.

**Next decision:** Approve this plan or request changes, then supply Cursor with the first-session handoff and original evidence ZIP.
