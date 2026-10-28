# Stage 4 — Automatic Diarization Quality Report

## Scope

- Meetings checked: 12
- Aligned transcript segments: 6740
- Matched segments: 6547
- Segments requiring alignment review: 193
- Automatic speaker turns: 5513
- Alignment coverage: 97.14%

## Validation

- Blank transcript rows: 0
- Invalid aligned timestamps: 0
- Matched rows missing speaker ID: 0
- Invalid speaker-turn timestamps: 0
- Speaker turns missing speaker ID: 0
- Turns longer than 30 seconds for inspection: 127

## Per-meeting results

| Meeting | Segments | Matched | Review | Turns | Status |
|---|---:|---:|---:|---:|---|
| ES2002a | 227 | 211 | 16 | 355 | OK |
| ES2002b | 741 | 725 | 16 | 532 | OK |
| ES2002c | 853 | 842 | 11 | 535 | OK |
| ES2002d | 869 | 843 | 26 | 887 | OK |
| ES2003a | 186 | 170 | 16 | 121 | OK |
| ES2003b | 575 | 564 | 11 | 291 | OK |
| ES2003c | 344 | 335 | 9 | 274 | OK |
| ES2003d | 799 | 774 | 25 | 537 | OK |
| ES2004a | 306 | 291 | 15 | 298 | OK |
| ES2004b | 645 | 628 | 17 | 484 | OK |
| ES2004c | 585 | 577 | 8 | 530 | OK |
| ES2004d | 610 | 587 | 23 | 669 | OK |

## Interpretation and limitations

- Alignment coverage measures transcript-segment alignment, not diarization accuracy.
- Long turns are flagged for inspection and are not automatically errors.
- This report does not calculate Diarization Error Rate (DER).
- Formal speaker accuracy evaluation requires suitable, verified reference annotations and a defined evaluation protocol.
- Non-matched segments are review candidates; they are not automatically incorrect.

## Output files

- `stage4_quality_summary.csv`: per-meeting checks.
- `stage4_quality_issues.csv`: rows flagged for inspection.
- `all_meetings_alignment_review.csv`: non-matched aligned transcript segments.
