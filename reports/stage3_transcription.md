# Stage 3 — Speech-to-Text Transcription

## Objective
Convert AMI meeting audio into timestamped text transcripts for downstream speaker diarization, meeting analysis, and action-item extraction.

## Model and configuration
- Model: `faster-whisper` — `small.en`
- Device: CPU
- Compute type: `int8`
- Language: English
- Beam size: 5
- Input audio: preprocessed mono, 16 kHz WAV files
- Word timestamps: enabled
- Voice activity detection filter: disabled

## Pipeline outputs
- JSON: transcript segments, timing, metadata, and word timestamps
- CSV: structured transcript segments
- TXT: readable timestamped transcripts
- Manifest: per-meeting status, duration, segment count, and runtime

## Quality assurance
- Tested the pipeline on a 180-second excerpt from ES2002a.
- The test completed in 44.2 seconds and generated 35 segments.
- Full-batch results must be validated against the run manifest.
- Transcription accuracy will be evaluated against a compatible AMI reference transcript using Word Error Rate (WER).

## Limitations
- Automatic speech recognition may misrecognize words, names, and overlapping speech.
- Whisper transcription does not identify the AMI speaker labels A, B, C, and D by itself.
- Word timestamps and recognized language do not establish transcription accuracy.
- Evaluation on a single meeting should not be treated as a dataset-wide performance estimate.

## Outputs
- `data/processed/transcripts/full/small.en/json/`
- `data/processed/transcripts/full/small.en/segments_csv/`
- `data/processed/transcripts/full/small.en/text/`
- `data/processed/transcripts/logs/full_small.en_manifest.csv`
