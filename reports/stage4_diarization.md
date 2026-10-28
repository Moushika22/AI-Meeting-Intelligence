# Stage 4: Automatic Speaker Diarization and Quality Validation

## 1. Objective

The objective of Stage 4 was to identify speaker turns in the AMI Meeting Corpus recordings, align the detected speakers with the existing Whisper transcripts, and validate the generated outputs for completeness and consistency.

## 2. Methodology

Automatic speaker diarization was performed using the `pyannote/speaker-diarization-community-1` pipeline. The processing workflow included:

1. Loading the meeting audio and running automatic speaker diarization.
2. Generating speaker-turn timestamps and speaker labels.
3. Aligning transcript segments with the automatically detected speaker turns.
4. Recording alignment status, speaker coverage, and candidate speakers.
5. Validating timestamps, transcript completeness, and speaker-label availability.
6. Generating a consolidated review queue and a quality-validation report.

The pipeline was executed for 12 meetings: ES2002a–ES2002d, ES2003a–ES2003d, and ES2004a–ES2004d.

## 3. Results

| Metric | Result |
|---|---:|
| Meetings processed | 12 |
| Aligned transcript segments | 6,740 |
| Segments matched to automatic diarization | 6,547 |
| Segments requiring alignment review | 193 |
| Alignment coverage | 97.14% |
| Blank transcript-text entries | 0 |
| Automatic speaker turns | 5,513 |
| Quality issues recorded | 127 |

Alignment coverage was calculated as the number of matched transcript segments divided by the total number of aligned transcript segments. The resulting coverage was 97.14%.

This metric measures the proportion of transcript segments successfully matched to the automatic diarization output. It must not be interpreted as speaker-identification accuracy.

## 4. Quality Validation

The quality-check script evaluated the existence of aligned transcript and speaker-turn files, alignment statuses, blank transcript text, timestamp validity, speaker-label availability, and unusually long speaker turns.

The generated report recorded 127 quality issues for inspection. These are rule-based flags and should not automatically be interpreted as 127 confirmed errors. Long speaker turns, for example, may be valid when a participant speaks continuously.

A consolidated review queue containing 193 non-matched transcript segments was generated for further investigation.

## 5. Output Files

The principal output directory is:

`data/processed/diarization/automatic/`

The generated artifacts include:

- `speaker_turns/` — automatically detected speaker turns.
- `aligned_transcripts/` — transcripts aligned with automatic speaker labels.
- `diarization_manifest.csv` — batch-processing status.
- `review/all_meetings_alignment_review.csv` — consolidated alignment review queue.
- `review/stage4_quality_summary.csv` — per-meeting quality-check summary.
- `review/stage4_quality_issues.csv` — detailed quality flags.
- `review/stage4_quality_report.md` — generated quality-validation report.

## 6. Limitations

Although all 12 meetings were processed and the expected aligned transcript and speaker-turn files were present, further validation is necessary before declaring diarization accuracy fully established.

The 193 non-matched transcript segments require review. The 127 quality flags also require interpretation to distinguish genuine errors from valid but unusual speech patterns.

The available ES2002d reference transcript contains long segments and overlapping annotations. Its suitability for formal diarization evaluation must therefore be established before reporting a reliable Diarization Error Rate (DER). No formal DER or speaker-identification accuracy score is claimed in this report.

## 7. Conclusion

Stage 4 automatic diarization and initial quality validation were completed for all 12 selected AMI meetings. A total of 5,513 automatic speaker turns and 6,740 aligned transcript segments were recorded, with 6,547 segments successfully matched, corresponding to 97.14% alignment coverage.

The processing outputs and review artifacts have been generated. The remaining work is to inspect flagged segments, investigate the recorded quality issues, and perform reference-based evaluation where suitable annotations are available.

**Final status:** Automatic processing and initial quality checks completed; detailed review and formal accuracy validation remain pending.
