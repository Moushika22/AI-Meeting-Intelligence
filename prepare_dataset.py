import csv
import os

BASE = r"C:\Users\moush\Downloads\AI Meeting Intelligence"

CLEAN_FILE = os.path.join(
    BASE, "data", "processed", "ES2002d_clean.csv"
)

ANNOTATION_FILE = os.path.join(
    BASE, "data", "annotations", "ami_annotations_completed.csv"
)

TRANSCRIPT_FILE = os.path.join(
    BASE, "data", "processed", "ES2002d_transcript.txt"
)

ALIGNED_FILE = os.path.join(
    BASE, "data", "processed", "ES2002d_annotation_aligned.csv"
)


# --------------------------------------------------
# 1. Read cleaned segments
# --------------------------------------------------

with open(CLEAN_FILE, "r", encoding="utf-8") as file:
    segments = list(csv.DictReader(file))


# --------------------------------------------------
# 2. Create speaker-aware transcript
# --------------------------------------------------

with open(TRANSCRIPT_FILE, "w", encoding="utf-8") as file:

    current_speaker = None

    for row in segments:

        speaker = row["speaker"]

        if speaker != current_speaker:
            file.write(f"\nSpeaker {speaker}:\n")
            current_speaker = speaker

        file.write(row["text"] + " ")


print("Created:", TRANSCRIPT_FILE)


# --------------------------------------------------
# 3. Load annotations
# --------------------------------------------------

with open(ANNOTATION_FILE, "r", encoding="utf-8") as file:
    annotations = list(csv.DictReader(file))


# --------------------------------------------------
# 4. Match annotations with clean segments
# --------------------------------------------------

aligned = []

for annotation in annotations:

    matched = False

    for segment in segments:

        same_speaker = (
            annotation["speaker"] == segment["speaker"]
        )

        same_start = abs(
            float(annotation["start_time"])
            - float(segment["start_time"])
        ) < 0.01

        same_end = abs(
            float(annotation["end_time"])
            - float(segment["end_time"])
        ) < 0.01

        if same_speaker and same_start and same_end:

            row = dict(segment)

            row["action_item"] = annotation["action_item"]
            row["task"] = annotation["task"]
            row["owner"] = annotation["owner"]
            row["deadline"] = annotation["deadline"]
            row["priority"] = annotation["priority"]
            row["dependency"] = annotation["dependency"]
            row["decision"] = annotation["decision"]
            row["decision_text"] = annotation["decision_text"]

            aligned.append(row)

            matched = True
            break

    if not matched:
        print(
            "Warning: annotation not matched:",
            annotation["speaker"],
            annotation["start_time"]
        )


# --------------------------------------------------
# 5. Save aligned dataset
# --------------------------------------------------

fields = [
    "meeting_id",
    "speaker",
    "start_time",
    "end_time",
    "duration",
    "text",
    "action_item",
    "task",
    "owner",
    "deadline",
    "priority",
    "dependency",
    "decision",
    "decision_text"
]

with open(ALIGNED_FILE, "w", newline="", encoding="utf-8") as file:

    writer = csv.DictWriter(
        file,
        fieldnames=fields
    )

    writer.writeheader()
    writer.writerows(aligned)


print("Created:", ALIGNED_FILE)
print("Aligned annotations:", len(aligned))
print("\nDATA PREPARATION COMPLETE")