#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

AUDIO_EXTS = {".wav", ".aif", ".aiff", ".flac"}
LAYER_LIMIT_PER_PAD = 8


# ============================================================
# Data model
# ============================================================

@dataclass(frozen=True)
class MappingEntry:
    canonical: str
    synonyms: List[str]
    midi_notes: Optional[List[int]] = None


# ============================================================
# Parsing mapping file
# ============================================================

def parse_mapping_file(file_path: str) -> Dict[str, MappingEntry]:
    mapping: Dict[str, MappingEntry] = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            if ":" in line:
                left, right = line.split(":", 1)
                left = left.strip().lower()
                right = right.strip()
            else:
                left = line.strip().lower()
                right = None

            synonyms = [x.strip() for x in left.split("/") if x.strip()]
            canonical = synonyms[0]

            midi_notes = None
            if right is not None:
                if right == "":
                    midi_notes = []
                else:
                    midi_notes = [int(x.strip()) for x in right.split(",") if x.strip()]

            mapping[canonical] = MappingEntry(
                canonical=canonical,
                synonyms=synonyms,
                midi_notes=midi_notes,
            )

    return mapping


def mapping_to_nomenclature(mapping: Dict[str, MappingEntry]) -> Dict[str, List[str]]:
    return {k: v.synonyms for k, v in mapping.items()}


# ============================================================
# Detection helpers
# ============================================================

def detect_category(filename: str, nomenclature: Dict[str, List[str]]) -> str:
    name = filename.lower()
    for canonical, synonyms in nomenclature.items():
        for word in synonyms:
            if re.search(rf"\b{re.escape(word)}\b", name):
                return canonical
    return "other"


def extract_trailing_index(stem: str) -> Optional[int]:
    m = re.search(r"\s(\d+)$", stem)
    if not m:
        return None
    return int(m.group(1))


def extract_kit_name(filename: str, category: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(rf"^{re.escape(category)}\s*", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\s*\d+$", "", stem)
    return stem.strip() or "UNKNOWN"


# ============================================================
# Scan
# ============================================================

def scan_samples(root_folder: str, nomenclature: Dict[str, List[str]]):
    kits = defaultdict(lambda: defaultdict(list))

    for root, _, files in os.walk(root_folder):
        for file in files:
            if Path(file).suffix.lower() not in AUDIO_EXTS:
                continue

            category = detect_category(file, nomenclature)
            kit_name = extract_kit_name(file, category)

            kits[kit_name][category].append(os.path.join(root, file))

    return kits


# ============================================================
# Sorting
# ============================================================

def sort_samples_by_trailing_number(paths: List[str]) -> List[str]:
    def key(p):
        stem = Path(p).stem
        idx = extract_trailing_index(stem)
        return (0, idx) if idx is not None else (1, stem.lower())
    return sorted(paths, key=key)


# ============================================================
# Stats
# ============================================================

def kit_stats(elements):
    total = sum(len(v) for v in elements.values())
    only_other = ("other" in elements and len(elements) == 1)
    mixed_other = ("other" in elements and len(elements) > 1)
    return {
        "total": total,
        "only_other": only_other,
        "mixed_other": mixed_other,
    }


# ============================================================
# MIDI helpers
# ============================================================

def parse_midi_note_list(spec: str) -> List[int]:
    notes = set()
    parts = [x.strip() for x in spec.split(",") if x.strip()]
    for part in parts:
        if "-" in part:
            start, end = part.split("-", 1)
            for n in range(int(start), int(end) + 1):
                notes.add(n)
        else:
            notes.add(int(part))
    return sorted(notes)


def category_capacity(mapping, category):
    entry = mapping.get(category)
    if not entry or entry.midi_notes is None:
        return None
    return len(entry.midi_notes) * LAYER_LIMIT_PER_PAD


# ============================================================
# Filtering with overflow + trash
# ============================================================

def filter_kits(
    kits,
    *,
    min_total_samples=0,
    exclude_only_other=False,
    exclude_mixed_other=False,
    mapping=None,
    overflow_policy="reject",
    trash_notes=None,
):
    valid = {}
    rejected = {}

    for kit_name, elements in kits.items():
        stats = kit_stats(elements)

        reason = None
        details = {}

        if stats["total"] < min_total_samples:
            reason = "too_few_samples"

        elif exclude_only_other and stats["only_other"]:
            reason = "only_other"

        elif exclude_mixed_other and stats["mixed_other"]:
            reason = "mixed_other"

        overflow_info = []
        other_count = len(elements.get("other", []))

        if mapping:
            for cat, files in elements.items():
                if cat == "other":
                    continue

                cap = category_capacity(mapping, cat)
                if cap is not None and len(files) > cap:
                    overflow_info.append({
                        "category": cat,
                        "count": len(files),
                        "capacity": cap
                    })

        if overflow_info or other_count:

            total_trash_needed = 0

            for info in overflow_info:
                total_trash_needed += info["count"] - info["capacity"]

            total_trash_needed += other_count

            if overflow_policy == "reject":
                reason = "overflow_or_other"

            elif overflow_policy == "trash":
                trash_capacity = len(trash_notes) * LAYER_LIMIT_PER_PAD if trash_notes else 0
                if total_trash_needed > trash_capacity:
                    reason = "trash_zone_insufficient"
                    details["trash_needed"] = total_trash_needed
                    details["trash_capacity"] = trash_capacity

            details["overflow"] = overflow_info
            details["other_count"] = other_count

        if reason:
            rejected[kit_name] = {
                "reason": reason,
                "details": details,
                "elements": elements
            }
        else:
            sorted_elements = {
                cat: sort_samples_by_trailing_number(files)
                for cat, files in elements.items()
            }
            valid[kit_name] = sorted_elements

    return valid, rejected


# ============================================================
# Display
# ============================================================

def print_listing(kits):
    print(f"\nTOTAL KITS : {len(kits)}")
    for kit_name, elements in kits.items():
        stats = kit_stats(elements)
        print(f"\n=== KIT : {kit_name} ===")
        print(f"  Total samples : {stats['total']}")
        for category, files in elements.items():
            print(f"  {category} ({len(files)})")
            for f in files:
                print(f"    - {Path(f).name}")
