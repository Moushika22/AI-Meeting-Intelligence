"""
Stage 4: Automatic speaker diarization and Whisper transcript alignment.

Run from the project root:
    python scripts\stage4_automatic_diarization.py

Required environment variable:
    HF_TOKEN = Hugging Face read token, after accepting the model conditions.

Inputs:
    data/processed/audio/*.wav
    data/processed/transcripts/full/small.en/json/*.json

Outputs:
    data/processed/diarization/automatic/
        speaker_turns/
        exclusive_turns/
        aligned_transcripts/
        rttm/
        diarization_manifest.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIO_DIR = ROOT / "data" / "processed" / "audio"
TRANSCRIPT_DIR = ROOT / "data" / "processed" / "transcripts" / "full" / "small.en" / "json"
OUTPUT_DIR = ROOT / "data" / "processed" / "diarization" / "automatic"

TURN_DIR = OUTPUT_DIR / "speaker_turns"
EXCLUSIVE_DIR = OUTPUT_DIR / "exclusive_turns"
ALIGNED_DIR = OUTPUT_DIR / "aligned_transcripts"
RTTM_DIR = OUTPUT_DIR / "rttm"
MANIFEST_PATH = OUTPUT_DIR / "diarization_manifest.csv"

MODEL_ID = "pyannote/speaker-diarization-community-1"
# A segment is assigned a speaker only when one exclusive speaker turn covers
# at least this fraction of the Whisper segment's duration.
MIN_SEGMENT_COVERAGE = 0.50


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def annotation_to_rows(annotation: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        rows.append(
            {
                "start": round(float(turn.start), 3),
                "end": round(float(turn.end), 3),
                "duration": round(float(turn.end - turn.start), 3),
                "speaker_id": str(speaker),
            }
        )
    rows.sort(key=lambda row: (row["start"], row["end"], row["speaker_id"]))
    return rows


def align_segments(segments: list[dict[str, Any]], exclusive_rows: list[dict[str, Any]],
                   meeting_id: str) -> list[dict[str, Any]]:
    aligned: list[dict[str, Any]] = []

    for index, segment in enumerate(segments):
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start))
        duration = max(0.0, end - start)

        overlap_by_speaker: dict[str, float] = {}
        for turn in exclusive_rows:
            overlap = max(
                0.0,
                min(end, float(turn["end"])) - max(start, float(turn["start"]))
            )
            if overlap > 0:
                sid = str(turn["speaker_id"])
                overlap_by_speaker[sid] = overlap_by_speaker.get(sid, 0.0) + overlap

        ranked = sorted(overlap_by_speaker.items(), key=lambda item: item[1], reverse=True)
        best_speaker = ranked[0][0] if ranked else ""
        best_overlap = ranked[0][1] if ranked else 0.0
        coverage = best_overlap / duration if duration > 0 else 0.0

        if not ranked:
            speaker_id = "UNCERTAIN"
            status = "no_speaker_overlap"
        elif coverage >= MIN_SEGMENT_COVERAGE:
            speaker_id = best_speaker
            status = "matched_automatic_diarization"
        else:
            speaker_id = "UNCERTAIN"
            status = "low_or_mixed_speaker_overlap"

        candidates = [
            {"speaker_id": sid, "overlap_seconds": round(seconds, 3)}
            for sid, seconds in ranked
        ]
        aligned.append(
            {
                "meeting_id": meeting_id,
                "segment_id": segment.get("segment_id", index),
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(duration, 3),
                "speaker_id": speaker_id,
                "alignment_status": status,
                "speaker_coverage": round(min(coverage, 1.0), 4),
                "speaker_candidates": json.dumps(candidates, ensure_ascii=False),
                "text": str(segment.get("text", "")).strip(),
            }
        )
    return aligned


def process_meeting(pipeline: Any, audio_path: Path, transcript_path: Path) -> dict[str, Any]:
    meeting_id = transcript_path.stem
    result: dict[str, Any] = {
        "meeting_id": meeting_id,
        "status": "started",
        "audio_file": str(audio_path.relative_to(ROOT)) if audio_path.exists() else "",
        "transcript_file": str(transcript_path.relative_to(ROOT)),
        "model": MODEL_ID,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "whisper_segments": 0,
        "speaker_turns": 0,
        "exclusive_turns": 0,
        "aligned_segments": 0,
        "uncertain_segments": 0,
        "speaker_count": 0,
        "error": "",
    }

    try:
        if not audio_path.exists():
            result["status"] = "missing_audio"
            result["error"] = f"Audio file not found: {audio_path}"
            return result

        with transcript_path.open("r", encoding="utf-8") as f:
            transcript_data = json.load(f)
        segments = transcript_data.get("segments", [])
        result["whisper_segments"] = len(segments)

        # Do not force a speaker count: the model estimates it automatically.
        output = pipeline(str(audio_path))
        diarization = output.speaker_diarization
        exclusive = output.exclusive_speaker_diarization

        speaker_rows = annotation_to_rows(diarization)
        exclusive_rows = annotation_to_rows(exclusive)
        aligned_rows = align_segments(segments, exclusive_rows, meeting_id)

        speaker_ids = sorted({row["speaker_id"] for row in speaker_rows})
        result["speaker_count"] = len(speaker_ids)
        result["speaker_turns"] = len(speaker_rows)
        result["exclusive_turns"] = len(exclusive_rows)
        result["aligned_segments"] = len(aligned_rows)
        result["uncertain_segments"] = sum(
            row["speaker_id"] == "UNCERTAIN" for row in aligned_rows
        )

        write_csv(
            TURN_DIR / f"{meeting_id}_speaker_turns.csv",
            speaker_rows,
            ["start", "end", "duration", "speaker_id"],
        )
        write_csv(
            EXCLUSIVE_DIR / f"{meeting_id}_exclusive_turns.csv",
            exclusive_rows,
            ["start", "end", "duration", "speaker_id"],
        )
        write_csv(
            ALIGNED_DIR / f"{meeting_id}_speaker_aligned.csv",
            aligned_rows,
            [
                "meeting_id", "segment_id", "start", "end", "duration",
                "speaker_id", "alignment_status", "speaker_coverage",
                "speaker_candidates", "text",
            ],
        )

        aligned_json = {
            "meeting_id": meeting_id,
            "model": MODEL_ID,
            "alignment_method": "maximum temporal overlap with exclusive automatic diarization",
            "minimum_speaker_coverage": MIN_SEGMENT_COVERAGE,
            "speaker_count": len(speaker_ids),
            "speaker_ids": speaker_ids,
            "segments": aligned_rows,
        }
        (ALIGNED_DIR / f"{meeting_id}_speaker_aligned.json").write_text(
            json.dumps(aligned_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        rttm_path = RTTM_DIR / f"{meeting_id}.rttm"
        rttm_path.parent.mkdir(parents=True, exist_ok=True)
        with rttm_path.open("w", encoding="utf-8") as f:
            diarization.write_rttm(f)

        result["status"] = "success"
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
    finally:
        result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    return result


def main() -> int:
    for directory in (TURN_DIR, EXCLUSIVE_DIR, ALIGNED_DIR, RTTM_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        print(
            "ERROR: HF_TOKEN is not set in this terminal.\n"
            "Set it in PowerShell, then rerun this script.",
            file=sys.stderr,
        )
        return 2

    if not TRANSCRIPT_DIR.exists():
        print(f"ERROR: Transcript directory not found: {TRANSCRIPT_DIR}", file=sys.stderr)
        return 2
    if not AUDIO_DIR.exists():
        print(f"ERROR: Audio directory not found: {AUDIO_DIR}", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(description="Run automatic speaker diarization and transcript alignment.")
    parser.add_argument(
        "--meeting",
        help="Process one meeting only, e.g. ES2002d. Omit this option to process every meeting."
    )
    args = parser.parse_args()

    transcript_files = sorted(TRANSCRIPT_DIR.glob("*.json"))
    if args.meeting:
        transcript_files = [p for p in transcript_files if p.stem.lower() == args.meeting.lower()]
        if not transcript_files:
            print(f"ERROR: No transcript JSON found for meeting {args.meeting}", file=sys.stderr)
            return 2
    if not transcript_files:
        print(f"ERROR: No Whisper JSON files found in {TRANSCRIPT_DIR}", file=sys.stderr)
        return 2

    print(f"Project root: {ROOT}")
    print(f"Whisper JSON files found: {len(transcript_files)}")
    print(f"Audio directory: {AUDIO_DIR}")
    print(f"Model: {MODEL_ID}")
    print("Loading pyannote pipeline. First run may download model files...")

    try:
        from pyannote.audio import Pipeline
        pipeline = Pipeline.from_pretrained(MODEL_ID, token=token)
        if pipeline is None:
            raise RuntimeError(
                "Pipeline.from_pretrained returned None. Check model access and token."
            )
    except Exception as exc:
        print(f"ERROR loading model: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "Check that you accepted the model conditions on Hugging Face, "
            "the token is valid, and required audio dependencies are installed.",
            file=sys.stderr,
        )
        return 3

    manifest: list[dict[str, Any]] = []
    for number, transcript_path in enumerate(transcript_files, start=1):
        meeting_id = transcript_path.stem
        candidates = [
            AUDIO_DIR / f"{meeting_id}.Mix-Headset.wav",
            AUDIO_DIR / f"{meeting_id}.wav",
        ]
        audio_path = next((p for p in candidates if p.exists()), None)
        if audio_path is None:
            matches = sorted(AUDIO_DIR.glob(f"{meeting_id}*.wav"))
            audio_path = matches[0] if matches else AUDIO_DIR / candidates[0].name

        print(f"\n[{number}/{len(transcript_files)}] Processing {meeting_id} ...")
        row = process_meeting(pipeline, audio_path, transcript_path)
        manifest.append(row)
        print(
            f"Status: {row['status']} | speakers: {row.get('speaker_count', 0)} | "
            f"turns: {row.get('speaker_turns', 0)} | "
            f"aligned segments: {row.get('aligned_segments', 0)} | "
            f"uncertain: {row.get('uncertain_segments', 0)}"
        )
        if row.get("error"):
            print(f"Details: {row['error']}")

        write_csv(
            MANIFEST_PATH,
            manifest,
            [
                "meeting_id", "status", "audio_file", "transcript_file", "model",
                "started_at_utc", "finished_at_utc", "whisper_segments",
                "speaker_turns", "exclusive_turns", "aligned_segments",
                "uncertain_segments", "speaker_count", "error",
            ],
        )

    successful = sum(row["status"] == "success" for row in manifest)
    failed = len(manifest) - successful
    print("\nStage 4 automatic diarization run finished.")
    print(f"Successful meetings: {successful}/{len(manifest)}")
    print(f"Meetings needing attention: {failed}")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Outputs: {OUTPUT_DIR}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
