import xml.etree.ElementTree as ET
import csv
import os

BASE = r"C:\Users\moush\Downloads\AI Meeting Intelligence\data\raw\ami"

MEETING = "ES2002d"
SPEAKER = "A"

words_file = os.path.join(
    BASE,
    "words",
    f"{MEETING}.{SPEAKER}.words.xml"
)

segments_file = os.path.join(
    BASE,
    "segments",
    f"{MEETING}.{SPEAKER}.segments.xml"
)

# Read words
words_tree = ET.parse(words_file)
words_root = words_tree.getroot()

words = {}

for w in words_root.iter("w"):
    word_id = w.attrib.get(
        "{http://nite.sourceforge.net/}id"
    )

    words[word_id] = w.text or ""

# Read segments
segments_tree = ET.parse(segments_file)
segments_root = segments_tree.getroot()

output = []

word_ids = list(words.keys())

for segment in segments_root.iter("segment"):

    start = segment.attrib.get("transcriber_start")
    end = segment.attrib.get("transcriber_end")

    child = segment.find(
        "{http://nite.sourceforge.net/}child"
    )

    if child is None:
        continue

    href = child.attrib.get("href", "")

    if "#id(" not in href:
        continue

    part = href.split("#id(")[1]

    first_id = part.split(")")[0]

    if "..id(" in part:
        second_id = part.split("..id(")[1].split(")")[0]
    else:
        second_id = first_id

    try:
        first_index = word_ids.index(first_id)
        second_index = word_ids.index(second_id)
    except ValueError:
        continue

    selected_words = word_ids[first_index:second_index + 1]

    text = " ".join(words[w] for w in selected_words)

    text = text.replace(" ,", ",")
    text = text.replace(" .", ".")
    text = text.replace(" ?", "?")
    text = text.replace(" !", "!")
    text = text.replace(" ;", ";")
    text = text.replace(" :", ":")

    output.append([
        MEETING,
        SPEAKER,
        start,
        end,
        text
    ])

output_file = os.path.join(
    BASE,
    "ES2002d_A_segments.csv"
)

with open(
    output_file,
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.writer(f)

    writer.writerow([
        "meeting_id",
        "speaker",
        "start_time",
        "end_time",
        "text"
    ])

    writer.writerows(output)

print("DONE!")
print("Created:", output_file)
print("Number of segments:", len(output))