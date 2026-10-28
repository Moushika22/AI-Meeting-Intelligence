# Stage 2: Audio Acquisition and Preprocessing

## 1. Objective

The objective of Stage 2 was to acquire meeting audio recordings from the AMI Meeting Corpus, inspect their technical properties and audio quality, and prepare standardized audio files for the transcription stage.

## 2. Dataset Source

- **Dataset:** AMI Meeting Corpus
- **Source:** [AMI Corpus Mirror](https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/)
- **Audio type:** Headset-mixed meeting recordings
- **Format:** WAV
- **Target sample rate:** 16,000 Hz
- **Target channels:** Mono
- **Target sample format:** 16-bit PCM

The selected recordings represent multiple meetings and provide conversational audio for subsequent speech transcription and meeting-information extraction.

## 3. Meeting Selection

The planned dataset consists of the following 12 recordings:

- ES2002a
- ES2002b
- ES2002c
- ES2002d
- ES2003a
- ES2003b
- ES2003c
- ES2003d
- ES2004a
- ES2004b
- ES2004c
- ES2004d

The completeness of the dataset was checked by comparing the downloaded and processed WAV files against the planned meeting list.

**Final dataset count:** Update this field after confirming that all 12 recordings are downloaded and processed successfully.

## 4. Audio Acquisition

The selected audio files were downloaded from the AMI Corpus Mirror and stored locally in the project directory.

**Raw audio directory:**

`data/raw/ami/audio/`

The original recordings were retained separately from the processed audio to preserve the source data and allow reproducibility.

## 5. Audio Inspection

The audio inspection script was used to generate a manifest containing technical metadata and preliminary audio-quality indicators.

**Script:** `scripts/inspect_audio.py`

**Output directory:** `data/interim/audio_quality/`

**Generated files:**
- `audio_manifest.csv`
- `audio_manifest.json`

The inspection included:

- Recording duration
- Sample rate
- Number of audio channels
- Audio subtype
- Peak amplitude
- Root mean square (RMS) level
- Clipping ratio
- Near-silence-block ratio
- Quality flags
- SHA-256 file hash

These measurements were used to identify recordings that might require further investigation before transcription.

## 6. Audio Preprocessing

**Script:** `scripts/preprocess_audio.py`

The preprocessing script prepared the recordings for consistent downstream processing.

**Input directory:** `data/raw/ami/audio/`

**Output directory:** `data/processed/audio/`

The target audio format was:

- Sample rate: 16 kHz
- Channels: Mono
- Sample format: 16-bit PCM WAV

The script converted recordings when necessary and retained compatible recordings without unnecessary conversion. A preprocessing manifest was generated to record the processing results.

**Generated manifest files:**
- `data/interim/audio_quality/preprocessing_manifest.csv`
- `data/interim/audio_quality/preprocessing_manifest.json`

The preprocessing stage standardized the technical audio format. It did not automatically perform denoising, silence removal, or loudness normalization.

## 7. Audio Quality Observations

Preliminary quality checks identified recordings with low overall RMS levels and high near-silence-block ratios.

For example, earlier inspection flagged ES2002c and ES2002d for elevated near-silence-block ratios, with ES2002d also flagged for a very low overall level.

These flags are screening indicators rather than proof that the recordings are unusable. The recordings should be reviewed further if transcription quality is poor.

**Important:** Update these observations using the final manifests after all planned recordings have been processed.

## 8. Validation

The following checks were used to validate Stage 2:

1. Confirm that the expected raw WAV recordings exist.
2. Confirm that the processed WAV files were generated.
3. Verify that processing completed without failures.
4. Check that processed audio meets the target format.
5. Review the manifests for errors and audio-quality flags.
6. Investigate missing recordings before starting full-dataset transcription.

The stage is considered complete only after the final file counts and processing results have been verified.

## 9. Limitations

- Audio-quality metrics provide preliminary indicators and do not guarantee speech intelligibility.
- Low RMS levels and near-silent sections may affect transcription performance.
- No automatic denoising, silence removal, or loudness normalization was performed during this stage.
- The dataset contains a limited selection of meetings from the AMI Meeting Corpus and should not be treated as representative of every meeting environment.

## 10. Outcome

Stage 2 establishes a reproducible audio preparation pipeline for the AI Meeting Intelligence project. The raw recordings, processed WAV files, inspection manifests, and preprocessing manifests provide the inputs and audit trail required for Stage 3: speech transcription using Whisper.

**Status:** Update to complete after verifying all 12 planned recordings and reviewing the final preprocessing manifest.