import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "data" / "raw" / "ami"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

INPUT_CSV = PROCESSED_DIR / "ES2002d_clean.csv"
OUTPUT_CSV = PROCESSED_DIR / "ES2002d_enriched.csv"

DA_TYPES_FILE = RAW_DIR / "ontologies" / "da-types.xml"


# ============================================================
# AMI DIALOGUE-ACT LABELS
# ============================================================

def load_dialogue_labels():
    """
    Reads da-types.xml and creates a mapping such as:

    ami_da_4 -> Inform
    ami_da_5 -> Elicit-Inform
    ami_da_6 -> Suggest
    """

    tree = ET.parse(DA_TYPES_FILE)
    root = tree.getroot()

    labels = {}

    for element in root.iter():
        ami_id = element.attrib.get(
            "{http://nite.sourceforge.net/}id"
        )

        name = element.attrib.get("name")
        gloss = element.attrib.get("gloss")

        if ami_id and ami_id.startswith("ami_da_"):
            labels[ami_id] = gloss or name or ami_id

    return labels


# ============================================================
# EXTRACT WORD RANGE FROM NITE REFERENCE
# ============================================================

def extract_word_range(href):
    """
    Example:

    ES2002d.B.words.xml#id(ES2002d.B.words0)..id(ES2002d.B.words5)

    returns:

    speaker = B
    start_word = 0
    end_word = 5
    """

    pattern = (
        r"ES2002d\.([A-D])\.words\.xml"
        r"#id\(ES2002d\.\1\.words(\d+)\)"
        r"\.\.id\(ES2002d\.\1\.words(\d+)\)"
    )

    match = re.search(pattern, href)

    if match:
        speaker = match.group(1)
        start_word = int(match.group(2))
        end_word = int(match.group(3))

        return speaker, start_word, end_word

    # Handle single-word references if encountered
    pattern_single = (
        r"ES2002d\.([A-D])\.words\.xml"
        r"#id\(ES2002d\.\1\.words(\d+)\)"
    )

    match = re.search(pattern_single, href)

    if match:
        speaker = match.group(1)
        word_id = int(match.group(2))

        return speaker, word_id, word_id

    return None


# ============================================================
# LOAD DIALOGUE ACTS
# ============================================================

def load_dialogue_acts(labels):
    """
    Reads A/B/C/D dialogue-act XML files.

    Returns a list containing:

        speaker
        start_word
        end_word
        dialogue_act
    """

    dialogue_acts = []

    for speaker in ["A", "B", "C", "D"]:

        xml_file = (
            RAW_DIR
            / "dialogueActs"
            / f"ES2002d.{speaker}.dialog-act.xml"
        )

        if not xml_file.exists():
            print(f"WARNING: Missing {xml_file}")
            continue

        tree = ET.parse(xml_file)
        root = tree.getroot()

        for dact in root.iter():

            if not dact.tag.endswith("dact"):
                continue

            dialogue_label = ""

            # Find the da-aspect pointer
            for child in dact:
                if child.tag.endswith("pointer"):

                    href = child.attrib.get("href", "")

                    match = re.search(
                        r"#id\((ami_da_\d+)\)",
                        href
                    )

                    if match:
                        ami_id = match.group(1)
                        dialogue_label = labels.get(
                            ami_id,
                            ami_id
                        )

            # Find the word-range child
            for child in dact:
                if not child.tag.endswith("child"):
                    continue

                href = child.attrib.get("href", "")

                result = extract_word_range(href)

                if result:

                    ref_speaker, start_word, end_word = result

                    dialogue_acts.append({
                        "speaker": ref_speaker,
                        "start_word": start_word,
                        "end_word": end_word,
                        "dialogue_act": dialogue_label
                    })

    return dialogue_acts


# ============================================================
# LOAD SEGMENT WORD RANGES
# ============================================================

def load_segment_ranges():
    """
    Reads the official AMI segment XML files.

    Each segment is associated with a range of word IDs.
    """

    segments = []

    for speaker in ["A", "B", "C", "D"]:

        xml_file = (
            RAW_DIR
            / "segments"
            / f"ES2002d.{speaker}.segments.xml"
        )

        if not xml_file.exists():
            print(f"WARNING: Missing {xml_file}")
            continue

        tree = ET.parse(xml_file)
        root = tree.getroot()

        for segment in root.iter():

            if not segment.tag.endswith("segment"):
                continue

            segment_id = segment.attrib.get(
                "{http://nite.sourceforge.net/}id",
                ""
            )

            start_time = segment.attrib.get(
                "transcriber_start",
                ""
            )

            end_time = segment.attrib.get(
                "transcriber_end",
                ""
            )

            start_word = None
            end_word = None

            for child in segment:

                if not child.tag.endswith("child"):
                    continue

                href = child.attrib.get("href", "")

                result = extract_word_range(href)

                if result:

                    _, start_word, end_word = result
                    break

            if start_word is not None:

                segments.append({
                    "speaker": speaker,
                    "segment_id": segment_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "start_word": start_word,
                    "end_word": end_word
                })

    return segments


# ============================================================
# FIND DIALOGUE ACTS FOR A SEGMENT
# ============================================================

def get_segment_dialogue_acts(
    speaker,
    start_word,
    end_word,
    dialogue_acts
):

    labels = []

    for act in dialogue_acts:

        if act["speaker"] != speaker:
            continue

        # Check whether the dialogue-act word range
        # overlaps with the segment word range.

        overlap = (
            act["start_word"] <= end_word
            and
            act["end_word"] >= start_word
        )

        if overlap:

            label = act["dialogue_act"]

            if label and label not in labels:
                labels.append(label)

    return "; ".join(labels)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("AMI ANNOTATION ENRICHMENT")
    print("-------------------------")

    # --------------------------------------------------------
    # 1. Load dialogue-act labels
    # --------------------------------------------------------

    labels = load_dialogue_labels()

    print(
        f"Dialogue-act labels loaded: {len(labels)}"
    )

    # --------------------------------------------------------
    # 2. Load official dialogue acts
    # --------------------------------------------------------

    dialogue_acts = load_dialogue_acts(labels)

    print(
        f"Dialogue acts loaded: {len(dialogue_acts)}"
    )

    # --------------------------------------------------------
    # 3. Load official segment word ranges
    # --------------------------------------------------------

    segment_ranges = load_segment_ranges()

    print(
        f"AMI segment ranges loaded: {len(segment_ranges)}"
    )

    # Create quick lookup structure

    range_lookup = {}

    for segment in segment_ranges:

        key = (
            segment["speaker"],
            segment["start_time"],
            segment["end_time"]
        )

        range_lookup[key] = segment

    # --------------------------------------------------------
    # 4. Read our cleaned CSV
    # --------------------------------------------------------

    with open(
        INPUT_CSV,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        rows = list(reader)

    print(
        f"Clean transcript rows: {len(rows)}"
    )

    # --------------------------------------------------------
    # 5. Add dialogue-act information
    # --------------------------------------------------------

    for row in rows:

        speaker = row["speaker"]
        start_time = row["start_time"]
        end_time = row["end_time"]

        key = (
            speaker,
            start_time,
            end_time
        )

        segment_info = range_lookup.get(key)

        if segment_info:

            dialogue_act = get_segment_dialogue_acts(
                speaker,
                segment_info["start_word"],
                segment_info["end_word"],
                dialogue_acts
            )

            row["dialogue_act"] = dialogue_act

        else:

            row["dialogue_act"] = ""

    # --------------------------------------------------------
    # 6. Save enriched dataset
    # --------------------------------------------------------

    fieldnames = list(rows[0].keys())

    if "dialogue_act" not in fieldnames:
        fieldnames.append("dialogue_act")

    with open(
        OUTPUT_CSV,
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(rows)

    # --------------------------------------------------------
    # 7. Statistics
    # --------------------------------------------------------

    labelled = sum(
        1
        for row in rows
        if row.get("dialogue_act", "").strip()
    )

    print()
    print("ENRICHMENT COMPLETE")
    print("-------------------")
    print(
        f"Total segments : {len(rows)}"
    )
    print(
        f"With dialogue acts : {labelled}"
    )
    print(
        f"Without dialogue acts : {len(rows) - labelled}"
    )
    print()
    print(
        f"Created: {OUTPUT_CSV}"
    )


if __name__ == "__main__":
    main()