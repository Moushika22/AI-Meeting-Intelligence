
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import time
import traceback
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from faster_whisper import WhisperModel
import soundfile as sf


# =========================================================
# PROJECT CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_DIR = PROJECT_ROOT / "data" / "processed" / "audio"
TRANSCRIPT_ROOT = PROJECT_ROOT / "data" / "processed" / "transcripts"
LOG_DIR = TRANSCRIPT_ROOT / "logs"
MODEL_CACHE_DIR = PROJECT_ROOT / "models" / "faster-whisper"

DEFAULT_MODEL = "small.en"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

# Conservative starting point for a laptop with 16 logical cores.
CPU_THREADS = 8
NUM_WORKERS = 1

EXPECTED_MEETINGS = 12

# Keep settings explicit for reproducibility.
BEAM_SIZE = 5
LANGUAGE = "en"
TASK = "transcribe"
WORD_TIMESTAMPS = True
VAD_FILTER = False
CONDITION_ON_PREVIOUS_TEXT = True


# =========================================================
# UTILITIES
# =========================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def package_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "unknown"


def atomic_write_text(path: Path, content: str) -> None:
    """Write to a temporary file first to avoid partial final files."""
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(content, encoding="utf-8")
    os.replace(temporary_path, path)


def atomic_write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")

    fieldnames = [
        "segment_id",
        "start_seconds",
        "end_seconds",
        "duration_seconds",
        "text",
        "avg_logprob",
        "no_speech_probability",
        "compression_ratio",
        "words_json",
    ]

    with temporary_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    os.replace(temporary_path, path)


def load_manifest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        return {
            row["meeting_id"]: row
            for row in reader
            if row.get("meeting_id")
        }


def save_manifest(path: Path, records: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "meeting_id",
        "source_file",
        "source_sha256",
        "model",
        "status",
        "language",
        "language_probability",
        "audio_duration_seconds",
        "segment_count",
        "elapsed_seconds",
        "started_at_utc",
        "completed_at_utc",
        "error",
    ]

    temporary_path = path.with_suffix(path.suffix + ".tmp")

    with temporary_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=fieldnames, extrasaction="ignore"
        )
        writer.writeheader()

        for meeting_id in sorted(records):
            writer.writerow(records[meeting_id])

    os.replace(temporary_path, path)


def completed_output(json_path: Path) -> bool:
    """Return True only if the existing JSON records successful completion."""
    if not json_path.exists():
        return False

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return data.get("metadata", {}).get("completed") is True
    except (OSError, json.JSONDecodeError):
        return False


# =========================================================
# TRANSCRIPTION
# =========================================================

def transcribe_meeting(
    model: WhisperModel,
    source: Path,
    meeting_id: str,
    model_name: str,
    mode: str,
    test_seconds: float | None,
    force: bool,
) -> dict:
    model_output_dir = TRANSCRIPT_ROOT / mode / model_name

    json_dir = model_output_dir / "json"
    csv_dir = model_output_dir / "segments_csv"
    text_dir = model_output_dir / "text"

    json_path = json_dir / f"{meeting_id}.json"
    csv_path = csv_dir / f"{meeting_id}.csv"
    text_path = text_dir / f"{meeting_id}.txt"

    if (
        not force
        and test_seconds is None
        and completed_output(json_path)
    ):
        print(f"Already completed; skipping {meeting_id}")
        return {
            "meeting_id": meeting_id,
            "source_file": source.name,
            "model": model_name,
            "status": "SKIPPED_ALREADY_COMPLETED",
            "error": "",
        }

    if test_seconds is not None and test_seconds <= 0:
        raise ValueError("--test-seconds must be greater than zero.")

    audio_info = sf.info(str(source))
    audio_duration = audio_info.frames / audio_info.samplerate

    if test_seconds is not None:
        clip_end = min(test_seconds, audio_duration)
        clip_timestamps = [0.0, clip_end]
    else:
        clip_end = audio_duration
        clip_timestamps = None

    started_at = utc_now()
    start_time = time.perf_counter()

    print(f"\nTranscribing {meeting_id}")
    print(f"Audio duration: {audio_duration / 60:.2f} minutes")
    print(f"Mode: {mode}")
    if test_seconds is not None:
        print(f"Test excerpt: {clip_end:.1f} seconds")

    try:
        transcribe_kwargs = {
            "language": LANGUAGE,
            "task": TASK,
            "beam_size": BEAM_SIZE,
            "word_timestamps": WORD_TIMESTAMPS,
            "vad_filter": VAD_FILTER,
            "condition_on_previous_text": CONDITION_ON_PREVIOUS_TEXT,
            "temperature": 0.0,
            "compression_ratio_threshold": 2.4,
            "log_prob_threshold": -1.0,
            "no_speech_threshold": 0.6,
        }

        if clip_timestamps is not None:
            transcribe_kwargs["clip_timestamps"] = clip_timestamps

        segment_generator, info = model.transcribe(
            str(source),
            **transcribe_kwargs,
        )

        segments = []
        csv_rows = []
        text_lines = []

        # IMPORTANT: faster-whisper performs inference as the generator
        # is consumed. Iterating here completes the transcription.
        for segment in segment_generator:
            words = []

            if segment.words:
                for word in segment.words:
                    words.append({
                        "start": word.start,
                        "end": word.end,
                        "word": word.word,
                        "probability": word.probability,
                    })

            segment_record = {
                "segment_id": len(segments),
                "start": segment.start,
                "end": segment.end,
                "duration": round(segment.end - segment.start, 3),
                "text": segment.text.strip(),
                "avg_logprob": segment.avg_logprob,
                "no_speech_probability": segment.no_speech_prob,
                "compression_ratio": segment.compression_ratio,
                "words": words,
            }
            segments.append(segment_record)

            csv_rows.append({
                "segment_id": segment_record["segment_id"],
                "start_seconds": segment.start,
                "end_seconds": segment.end,
                "duration_seconds": segment_record["duration"],
                "text": segment_record["text"],
                "avg_logprob": segment.avg_logprob,
                "no_speech_probability": segment.no_speech_prob,
                "compression_ratio": segment.compression_ratio,
                "words_json": json.dumps(
                    words, ensure_ascii=False
                ),
            })

            text_lines.append(
                f"[{segment.start:.2f} - {segment.end:.2f}] "
                f"{segment.text.strip()}"
            )

        elapsed_seconds = round(time.perf_counter() - start_time, 2)

        metadata = {
            "completed": True,
            "meeting_id": meeting_id,
            "source_file": source.name,
            "source_relative_path": str(
                source.relative_to(PROJECT_ROOT)
            ),
            "source_sha256": sha256_file(source),
            "mode": mode,
            "model": model_name,
            "engine": "faster-whisper",
            "faster_whisper_version": package_version(
                "faster-whisper"
            ),
            "ctranslate2_version": package_version("ctranslate2"),
            "python_version": sys.version,
            "platform": platform.platform(),
            "device": DEVICE,
            "compute_type": COMPUTE_TYPE,
            "cpu_threads": CPU_THREADS,
            "num_workers": NUM_WORKERS,
            "language_requested": LANGUAGE,
            "language_detected": info.language,
            "language_probability": info.language_probability,
            "task": TASK,
            "beam_size": BEAM_SIZE,
            "word_timestamps": WORD_TIMESTAMPS,
            "vad_filter": VAD_FILTER,
            "condition_on_previous_text": CONDITION_ON_PREVIOUS_TEXT,
            "test_excerpt_seconds": (
                clip_end if test_seconds is not None else None
            ),
            "source_duration_seconds": round(audio_duration, 3),
            "transcribed_clip_end_seconds": round(clip_end, 3),
            "segment_count": len(segments),
            "transcription_elapsed_seconds": elapsed_seconds,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
        }

        output = {
            "metadata": metadata,
            "segments": segments,
            "full_text": " ".join(
                segment["text"] for segment in segments
            ).strip(),
        }

        # Write all output files only after transcription completes.
        json_content = json.dumps(
            output, indent=2, ensure_ascii=False
        )
        atomic_write_text(json_path, json_content)
        atomic_write_csv(csv_path, csv_rows)
        atomic_write_text(
            text_path,
            "\n".join(text_lines) + ("\n" if text_lines else ""),
        )

        status = (
            "COMPLETED"
            if segments
            else "COMPLETED_NO_SEGMENTS_REVIEW"
        )

        print(f"Status: {status}")
        print(f"Segments: {len(segments)}")
        print(f"Detected language: {info.language}")
        print(
            f"Language probability: "
            f"{info.language_probability:.3f}"
        )
        print(f"Elapsed: {elapsed_seconds:.1f} seconds")
        print("JSON:", json_path)
        print("CSV:", csv_path)
        print("TXT:", text_path)

        return {
            "meeting_id": meeting_id,
            "source_file": source.name,
            "source_sha256": metadata["source_sha256"],
            "model": model_name,
            "status": status,
            "language": info.language,
            "language_probability": round(
                info.language_probability, 5
            ),
            "audio_duration_seconds": round(audio_duration, 3),
            "segment_count": len(segments),
            "elapsed_seconds": elapsed_seconds,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "error": "",
        }

    except Exception as error:
        elapsed_seconds = round(time.perf_counter() - start_time, 2)

        error_text = (
            f"{type(error).__name__}: {error}\n"
            f"{traceback.format_exc()}"
        )

        error_path = LOG_DIR / f"{mode}_{model_name}_{meeting_id}.error.txt"
        atomic_write_text(error_path, error_text)

        print(f"FAILED: {error}")
        print("Error log:", error_path)

        return {
            "meeting_id": meeting_id,
            "source_file": source.name,
            "model": model_name,
            "status": "FAILED",
            "elapsed_seconds": elapsed_seconds,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "error": f"{type(error).__name__}: {error}",
        }


# =========================================================
# ENTRY POINT
# =========================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resumable AMI meeting transcription pipeline."
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Whisper model, e.g. small.en or medium.en.",
    )
    parser.add_argument(
        "--meeting",
        default=None,
        help="Process one meeting ID, e.g. ES2002a.",
    )
    parser.add_argument(
        "--test-seconds",
        type=float,
        default=None,
        help="Transcribe only the first N seconds. Outputs go to test/.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing completed transcription outputs.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Allow a full batch even when fewer than 12 recordings exist.",
    )
    args = parser.parse_args()

    if not INPUT_DIR.exists():
        raise FileNotFoundError(
            f"Processed audio directory not found: {INPUT_DIR}"
        )

    files = sorted(
        path for path in INPUT_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() == ".wav"
    )

    if not files:
        raise FileNotFoundError(
            f"No processed WAV files found in {INPUT_DIR}"
        )

    if args.meeting:
        files = [
            path for path in files
            if path.name.startswith(args.meeting)
        ]

        if not files:
            raise FileNotFoundError(
                f"No processed WAV found for meeting ID {args.meeting}"
            )

    # Protect the full-batch run from silently processing an incomplete set.
    if (
        args.test_seconds is None
        and len(files) != EXPECTED_MEETINGS
        and not args.allow_incomplete
    ):
        raise SystemExit(
            f"Expected {EXPECTED_MEETINGS} recordings, found {len(files)}. "
            "Recover missing files, or use --allow-incomplete only if "
            "you intentionally want to process a smaller batch."
        )

    mode = "test" if args.test_seconds is not None else "full"

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    manifest_path = LOG_DIR / f"{mode}_{args.model}_manifest.csv"
    records = load_manifest(manifest_path)

    print("=" * 65)
    print("AI MEETING INTELLIGENCE — TRANSCRIPTION PIPELINE")
    print("=" * 65)
    print("Mode:", mode)
    print("Model:", args.model)
    print("Device:", DEVICE)
    print("Compute type:", COMPUTE_TYPE)
    print("CPU threads:", CPU_THREADS)
    print("Files selected:", len(files))
    print("Input:", INPUT_DIR)
    print("Manifest:", manifest_path)

    print("\nLoading model; the first run may download model files...")

    model = WhisperModel(
        args.model,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        cpu_threads=CPU_THREADS,
        num_workers=NUM_WORKERS,
        download_root=str(MODEL_CACHE_DIR),
    )

    for index, source in enumerate(files, start=1):
        meeting_id = source.name.replace(".Mix-Headset.wav", "")
        if meeting_id == source.name:
            meeting_id = source.stem

        print(f"\n[{index}/{len(files)}]")

        result = transcribe_meeting(
            model=model,
            source=source,
            meeting_id=meeting_id,
            model_name=args.model,
            mode=mode,
            test_seconds=args.test_seconds,
            force=args.force,
        )

        # Preserve earlier manifest entries and update the current meeting.
        if result.get("status") != "SKIPPED_ALREADY_COMPLETED":
            records[meeting_id] = {
                "meeting_id": meeting_id,
                "source_file": source.name,
                "source_sha256": result.get("source_sha256", ""),
                "model": args.model,
                "status": result.get("status", "FAILED"),
                "language": result.get("language", ""),
                "language_probability": result.get(
                    "language_probability", ""
                ),
                "audio_duration_seconds": result.get(
                    "audio_duration_seconds", ""
                ),
                "segment_count": result.get("segment_count", ""),
                "elapsed_seconds": result.get("elapsed_seconds", ""),
                "started_at_utc": result.get("started_at_utc", ""),
                "completed_at_utc": result.get("completed_at_utc", ""),
                "error": result.get("error", ""),
            }

        save_manifest(manifest_path, records)

    print("\n" + "=" * 65)
    print("TRANSCRIPTION RUN FINISHED")
    print("=" * 65)
    print("Manifest:", manifest_path)
    print("Review FAILED or COMPLETED_NO_SEGMENTS_REVIEW entries.")


if __name__ == "__main__":
    main()
