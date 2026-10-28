
from pathlib import Path
import csv
import json

ROOT = Path(__file__).resolve().parents[1]

BASE = ROOT / "data" / "processed" / "diarization" / "automatic"
ALIGNED_DIR = BASE / "aligned_transcripts"
TURNS_DIR = BASE / "speaker_turns"
REVIEW_DIR = BASE / "review"

MEETINGS = [
    "ES2002a", "ES2002b", "ES2002c", "ES2002d",
    "ES2003a", "ES2003b", "ES2003c", "ES2003d",
    "ES2004a", "ES2004b", "ES2004c", "ES2004d",
]

REVIEW_DIR.mkdir(parents=True, exist_ok=True)


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def number(row, key):
    try:
        value = float(row[key])
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    except (KeyError, TypeError, ValueError):
        return None


summary = []
issues = []

for meeting in MEETINGS:
    aligned_path = ALIGNED_DIR / f"{meeting}_speaker_aligned.csv"
    turns_path = TURNS_DIR / f"{meeting}_speaker_turns.csv"

    result = {
        "meeting_id": meeting,
        "aligned_file_exists": aligned_path.is_file(),
        "turns_file_exists": turns_path.is_file(),
        "aligned_segments": 0,
        "matched": 0,
        "needs_review": 0,
        "blank_text": 0,
        "invalid_aligned_timestamps": 0,
        "missing_speaker_on_matched": 0,
        "speaker_turns": 0,
        "invalid_turn_timestamps": 0,
        "missing_turn_speaker": 0,
        "turns_over_30_seconds": 0,
        "status": "OK",
    }

    if not aligned_path.is_file():
        result["status"] = "MISSING_ALIGNED_FILE"
        issues.append({
            "meeting_id": meeting,
            "file_type": "aligned_transcript",
            "issue": "Missing aligned transcript CSV",
            "row_number": "",
            "details": str(aligned_path),
        })
    else:
        aligned_rows = read_csv(aligned_path)
        result["aligned_segments"] = len(aligned_rows)

        for row_number, row in enumerate(aligned_rows, start=2):
            status = (row.get("alignment_status") or "").strip()
            speaker = (row.get("speaker_id") or "").strip()
            text = (row.get("text") or "").strip()
            start = number(row, "start")
            end = number(row, "end")

            if status == "matched_automatic_diarization":
                result["matched"] += 1
                if not speaker:
                    result["missing_speaker_on_matched"] += 1
                    issues.append({
                        "meeting_id": meeting,
                        "file_type": "aligned_transcript",
                        "issue": "Matched segment has no speaker ID",
                        "row_number": row_number,
                        "details": text[:160],
                    })
            else:
                result["needs_review"] += 1

            if not text:
                result["blank_text"] += 1
                issues.append({
                    "meeting_id": meeting,
                    "file_type": "aligned_transcript",
                    "issue": "Blank transcript text",
                    "row_number": row_number,
                    "details": "",
                })

            if start is None or end is None or start < 0 or end <= start:
                result["invalid_aligned_timestamps"] += 1
                issues.append({
                    "meeting_id": meeting,
                    "file_type": "aligned_transcript",
                    "issue": "Invalid or missing timestamps",
                    "row_number": row_number,
                    "details": f"start={row.get('start')}, end={row.get('end')}",
                })

    if not turns_path.is_file():
        result["status"] = "MISSING_TURN_FILE"
        issues.append({
            "meeting_id": meeting,
            "file_type": "speaker_turns",
            "issue": "Missing speaker-turn CSV",
            "row_number": "",
            "details": str(turns_path),
        })
    else:
        turn_rows = read_csv(turns_path)
        result["speaker_turns"] = len(turn_rows)

        for row_number, row in enumerate(turn_rows, start=2):
            speaker = (row.get("speaker_id") or "").strip()
            start = number(row, "start")
            end = number(row, "end")

            if not speaker:
                result["missing_turn_speaker"] += 1
                issues.append({
                    "meeting_id": meeting,
                    "file_type": "speaker_turns",
                    "issue": "Missing speaker ID",
                    "row_number": row_number,
                    "details": "",
                })

            if start is None or end is None or start < 0 or end <= start:
                result["invalid_turn_timestamps"] += 1
                issues.append({
                    "meeting_id": meeting,
                    "file_type": "speaker_turns",
                    "issue": "Invalid or missing timestamps",
                    "row_number": row_number,
                    "details": f"start={row.get('start')}, end={row.get('end')}",
                })
            elif end - start > 30:
                result["turns_over_30_seconds"] += 1
                issues.append({
                    "meeting_id": meeting,
                    "file_type": "speaker_turns",
                    "issue": "Turn longer than 30 seconds; inspect",
                    "row_number": row_number,
                    "details": f"{start:.3f}-{end:.3f} ({end-start:.3f}s), speaker={speaker}",
                })

    if result["status"] == "OK" and (
        result["invalid_aligned_timestamps"]
        or result["missing_speaker_on_matched"]
        or result["invalid_turn_timestamps"]
        or result["missing_turn_speaker"]
    ):
        result["status"] = "CHECK_REQUIRED"

    summary.append(result)

summary_path = REVIEW_DIR / "stage4_quality_summary.csv"
issues_path = REVIEW_DIR / "stage4_quality_issues.csv"
report_path = REVIEW_DIR / "stage4_quality_report.md"

with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=summary[0].keys())
    writer.writeheader()
    writer.writerows(summary)

issue_fields = [
    "meeting_id", "file_type", "issue", "row_number", "details"
]
with issues_path.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=issue_fields)
    writer.writeheader()
    writer.writerows(issues)

total_segments = sum(r["aligned_segments"] for r in summary)
total_matched = sum(r["matched"] for r in summary)
total_review = sum(r["needs_review"] for r in summary)
total_turns = sum(r["speaker_turns"] for r in summary)

report = [
    "# Stage 4 — Automatic Diarization Quality Report",
    "",
    "## Scope",
    "",
    f"- Meetings checked: {len(summary)}",
    f"- Aligned transcript segments: {total_segments}",
    f"- Matched segments: {total_matched}",
    f"- Segments requiring alignment review: {total_review}",
    f"- Automatic speaker turns: {total_turns}",
    (
        f"- Alignment coverage: "
        f"{100 * total_matched / total_segments:.2f}%"
        if total_segments else "- Alignment coverage: N/A"
    ),
    "",
    "## Validation",
    "",
    f"- Blank transcript rows: {sum(r['blank_text'] for r in summary)}",
    f"- Invalid aligned timestamps: {sum(r['invalid_aligned_timestamps'] for r in summary)}",
    f"- Matched rows missing speaker ID: {sum(r['missing_speaker_on_matched'] for r in summary)}",
    f"- Invalid speaker-turn timestamps: {sum(r['invalid_turn_timestamps'] for r in summary)}",
    f"- Speaker turns missing speaker ID: {sum(r['missing_turn_speaker'] for r in summary)}",
    f"- Turns longer than 30 seconds for inspection: {sum(r['turns_over_30_seconds'] for r in summary)}",
    "",
    "## Per-meeting results",
    "",
    "| Meeting | Segments | Matched | Review | Turns | Status |",
    "|---|---:|---:|---:|---:|---|",
]

for r in summary:
    report.append(
        f"| {r['meeting_id']} | {r['aligned_segments']} | "
        f"{r['matched']} | {r['needs_review']} | "
        f"{r['speaker_turns']} | {r['status']} |"
    )

report += [
    "",
    "## Interpretation and limitations",
    "",
    "- Alignment coverage measures transcript-segment alignment, not diarization accuracy.",
    "- Long turns are flagged for inspection and are not automatically errors.",
    "- This report does not calculate Diarization Error Rate (DER).",
    "- Formal speaker accuracy evaluation requires suitable, verified reference annotations and a defined evaluation protocol.",
    "- Non-matched segments are review candidates; they are not automatically incorrect.",
    "",
    "## Output files",
    "",
    "- `stage4_quality_summary.csv`: per-meeting checks.",
    "- `stage4_quality_issues.csv`: rows flagged for inspection.",
    "- `all_meetings_alignment_review.csv`: non-matched aligned transcript segments.",
]

report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

print("STAGE 4 QUALITY CHECK COMPLETE")
print(f"Meetings checked: {len(summary)}")
print(f"Aligned segments: {total_segments}")
print(f"Matched: {total_matched}")
print(f"Needs review: {total_review}")
print(f"Automatic speaker turns: {total_turns}")
print(f"Quality issues recorded: {len(issues)}")
print()
print(f"Summary: {summary_path}")
print(f"Issues:  {issues_path}")
print(f"Report:  {report_path}")
