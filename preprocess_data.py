import csv
import re
import os

INPUT_FILE = r"C:\Users\moush\Downloads\AI Meeting Intelligence\data\processed\ES2002d_all_segments.csv"

OUTPUT_FILE = r"C:\Users\moush\Downloads\AI Meeting Intelligence\data\processed\ES2002d_clean.csv"


def clean_text(text):
    if not text:
        return ""

    # Remove leading/trailing spaces
    text = text.strip()

    # Normalize multiple spaces
    text = re.sub(r"\s+", " ", text)

    # Normalize common AMI transcription markers
    text = text.replace("_", "")

    return text


# Read original processed segments
with open(INPUT_FILE, "r", encoding="utf-8") as file:
    rows = list(csv.DictReader(file))


cleaned_rows = []
seen = set()

for row in rows:

    meeting_id = row["meeting_id"].strip()
    speaker = row["speaker"].strip()
    text = clean_text(row["text"])

    try:
        start_time = float(row["start_time"])
        end_time = float(row["end_time"])
    except ValueError:
        continue

    # Remove empty segments
    if not text:
        continue

    # Remove invalid timestamps
    if start_time < 0 or end_time < start_time:
        continue

    # Remove exact duplicates
    key = (meeting_id, speaker, start_time, end_time, text)

    if key in seen:
        continue

    seen.add(key)

    cleaned_rows.append({
        "meeting_id": meeting_id,
        "speaker": speaker,
        "start_time": start_time,
        "end_time": end_time,
        "duration": round(end_time - start_time, 2),
        "text": text
    })


# Sort chronologically
cleaned_rows.sort(key=lambda x: x["start_time"])


# Save cleaned dataset
fields = [
    "meeting_id",
    "speaker",
    "start_time",
    "end_time",
    "duration",
    "text"
]

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:

    writer = csv.DictWriter(file, fieldnames=fields)

    writer.writeheader()
    writer.writerows(cleaned_rows)


print("PREPROCESSING COMPLETE")
print("----------------------")
print("Original segments :", len(rows))
print("Clean segments    :", len(cleaned_rows))
print("Removed segments  :", len(rows) - len(cleaned_rows))
print("Output file       :", OUTPUT_FILE)