
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf


# ---------------------------------------------------------
# PROJECT CONFIGURATION
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_DIR = PROJECT_ROOT / "data" / "raw" / "ami" / "audio"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "audio"
REPORT_DIR = PROJECT_ROOT / "data" / "interim" / "audio_quality"

CSV_REPORT = REPORT_DIR / "preprocessing_manifest.csv"
JSON_REPORT = REPORT_DIR / "preprocessing_manifest.json"

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
TARGET_SUBTYPE = "PCM_16"

# Signal-quality screening thresholds.
# These are review flags, not automatic rejection rules.
NEAR_SILENCE_DBFS = -50.0
NEAR_SILENCE_BLOCK_SECONDS = 1.0
CLIPPING_THRESHOLD = 0.999


# ---------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------

def sha256_file(path: Path) -> str:
    """Calculate a file checksum without loading the full file."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def run_ffmpeg(source: Path, destination: Path) -> None:
    """Convert audio to mono, 16 kHz, signed 16-bit PCM."""
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i", str(source),
        "-map", "0:a:0",
        "-map_metadata", "-1",
        "-vn",
        "-ac", str(TARGET_CHANNELS),
        "-ar", str(TARGET_SAMPLE_RATE),
        "-c:a", "pcm_s16le",
        str(destination),
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "FFmpeg conversion failed: "
            + completed.stderr[-2000:]
        )


def inspect_signal(path: Path) -> dict:
    """
    Inspect WAV metadata and estimate signal-quality indicators.

    Reads audio in blocks to avoid loading an entire meeting
    into memory.
    """
    info = sf.info(str(path))

    if info.frames <= 0 or info.samplerate <= 0:
        raise ValueError("Audio has no valid frames or sample rate.")

    if info.channels <= 0:
        raise ValueError("Audio has an invalid channel count.")

    if not info.format or info.format.upper() != "WAV":
        raise ValueError(f"Expected WAV format, got {info.format!r}.")

    duration_seconds = info.frames / info.samplerate

    peak = 0.0
    sum_squares = 0.0
    sample_count = 0
    clipped_samples = 0
    near_silent_blocks = 0
    total_blocks = 0

    block_size = max(
        1,
        int(info.samplerate * NEAR_SILENCE_BLOCK_SECONDS)
    )

    for block in sf.blocks(
        str(path),
        blocksize=block_size,
        dtype="float32",
        always_2d=True,
    ):
        if block.size == 0:
            continue

        if not np.isfinite(block).all():
            raise ValueError("Audio contains non-finite sample values.")

        block_peak = float(np.max(np.abs(block)))
        peak = max(peak, block_peak)

        sum_squares += float(np.sum(block.astype(np.float64) ** 2))
        sample_count += int(block.size)

        clipped_samples += int(
            np.count_nonzero(np.abs(block) >= CLIPPING_THRESHOLD)
        )

        block_rms = float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))
        block_dbfs = (
            20.0 * np.log10(block_rms)
            if block_rms > 0
            else -120.0
        )

        if block_dbfs < NEAR_SILENCE_DBFS:
            near_silent_blocks += 1

        total_blocks += 1

    if sample_count == 0:
        raise ValueError("No audio samples could be read.")

    rms = float(np.sqrt(sum_squares / sample_count))
    rms_dbfs = 20.0 * np.log10(rms) if rms > 0 else -120.0
    peak_dbfs = 20.0 * np.log10(peak) if peak > 0 else -120.0

    clipping_ratio = clipped_samples / sample_count
    near_silence_ratio = (
        near_silent_blocks / total_blocks if total_blocks else 0.0
    )

    flags = []

    if duration_seconds < 60:
        flags.append("SHORT_RECORDING_REVIEW")

    if peak >= CLIPPING_THRESHOLD:
        flags.append("POSSIBLE_CLIPPING")

    if rms_dbfs < -50:
        flags.append("VERY_LOW_OVERALL_LEVEL")

    if near_silence_ratio > 0.50:
        flags.append("HIGH_NEAR_SILENCE_BLOCK_RATIO")

    if info.channels > 2:
        flags.append("MULTICHANNEL_REVIEW")

    return {
        "duration_seconds": round(duration_seconds, 3),
        "duration_minutes": round(duration_seconds / 60, 3),
        "sample_rate_hz": info.samplerate,
        "channels": info.channels,
        "subtype": info.subtype,
        "format": info.format,
        "frames": info.frames,
        "file_size_mb": round(path.stat().st_size / (1024 ** 2), 3),
        "peak_dbfs": round(peak_dbfs, 3),
        "rms_dbfs": round(rms_dbfs, 3),
        "clipped_sample_ratio": round(clipping_ratio, 8),
        "near_silence_block_ratio": round(near_silence_ratio, 4),
        "quality_flags": ";".join(flags) if flags else "NONE",
    }


def is_target_format(metadata: dict) -> bool:
    return (
        metadata["sample_rate_hz"] == TARGET_SAMPLE_RATE
        and metadata["channels"] == TARGET_CHANNELS
        and metadata["subtype"] == TARGET_SUBTYPE
    )


# ---------------------------------------------------------
# PROCESS EACH RECORDING
# ---------------------------------------------------------

def process_file(source: Path) -> dict:
    relative_path = source.relative_to(INPUT_DIR)
    destination = OUTPUT_DIR / relative_path

    result = {
        "source_file": source.name,
        "source_path": str(source.relative_to(PROJECT_ROOT)),
        "output_path": str(destination.relative_to(PROJECT_ROOT)),
        "source_sha256": "",
        "output_sha256": "",
        "processing_status": "FAILED",
        "error": "",
    }

    try:
        result["source_sha256"] = sha256_file(source)

        source_metadata = inspect_signal(source)
        result["source_metadata"] = source_metadata

        destination.parent.mkdir(parents=True, exist_ok=True)

        if is_target_format(source_metadata):
            # Preserve the exact source bytes when no conversion is needed.
            shutil.copy2(source, destination)
            result["processing_status"] = "COPIED_ALREADY_STANDARD"

        else:
            if shutil.which("ffmpeg") is None:
                raise RuntimeError(
                    "FFmpeg is required to standardise this recording."
                )

            run_ffmpeg(source, destination)
            result["processing_status"] = "CONVERTED"

        # Re-open and verify the actual output.
        output_metadata = inspect_signal(destination)
        result["output_metadata"] = output_metadata

        if not is_target_format(output_metadata):
            raise ValueError(
                "Output does not meet the target audio specification."
            )

        if output_metadata["frames"] <= 0:
            raise ValueError("Output contains no audio frames.")

        result["output_sha256"] = sha256_file(destination)

        if (
            result["processing_status"] == "COPIED_ALREADY_STANDARD"
            and result["source_sha256"] != result["output_sha256"]
        ):
            raise ValueError(
                "Checksum mismatch after copying an unchanged source."
            )

    except Exception as error:
        result["processing_status"] = "FAILED"
        result["error"] = f"{type(error).__name__}: {error}"

        # Do not leave a partial output looking like a valid result.
        if destination.exists():
            destination.unlink()

    return result


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    files = sorted(
        path for path in INPUT_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() == ".wav"
    )

    if not files:
        raise FileNotFoundError(f"No WAV files found in {INPUT_DIR}")

    results = []

    print(f"Input recordings: {len(files)}")
    print(f"Output directory: {OUTPUT_DIR}")

    for index, source in enumerate(files, start=1):
        print(f"\n[{index}/{len(files)}] {source.name}")

        result = process_file(source)
        results.append(result)

        print("Status:", result["processing_status"])

        if result.get("output_metadata"):
            metadata = result["output_metadata"]
            print(
                f"Duration: {metadata['duration_minutes']} min | "
                f"Rate: {metadata['sample_rate_hz']} Hz | "
                f"Channels: {metadata['channels']} | "
                f"RMS: {metadata['rms_dbfs']} dBFS"
            )
            print("Quality flags:", metadata["quality_flags"])

        if result["error"]:
            print("ERROR:", result["error"])

    # Flatten nested metadata for a convenient CSV manifest.
    csv_rows = []

    for item in results:
        row = {
            key: value
            for key, value in item.items()
            if key not in {"source_metadata", "output_metadata"}
        }

        for prefix in ("source_metadata", "output_metadata"):
            for key, value in item.get(prefix, {}).items():
                row[f"{prefix}_{key}"] = value

        csv_rows.append(row)

    fieldnames = sorted({
        key for row in csv_rows for key in row.keys()
    })

    with CSV_REPORT.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "input_directory": str(INPUT_DIR),
        "output_directory": str(OUTPUT_DIR),
        "target_specification": {
            "format": "WAV",
            "sample_rate_hz": TARGET_SAMPLE_RATE,
            "channels": TARGET_CHANNELS,
            "subtype": TARGET_SUBTYPE,
        },
        "total_files": len(results),
        "successful_files": sum(
            item["processing_status"] in {
                "CONVERTED", "COPIED_ALREADY_STANDARD"
            }
            for item in results
        ),
        "failed_files": sum(
            item["processing_status"] == "FAILED"
            for item in results
        ),
        "files": results,
    }

    JSON_REPORT.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 55)
    print("AUDIO PREPROCESSING SUMMARY")
    print("=" * 55)
    print("Files discovered:", summary["total_files"])
    print("Successful:", summary["successful_files"])
    print("Failed:", summary["failed_files"])
    print("CSV manifest:", CSV_REPORT)
    print("JSON report:", JSON_REPORT)

    if summary["failed_files"]:
        print("\nResolve failed files before continuing to transcription.")


if __name__ == "__main__":
    main()
