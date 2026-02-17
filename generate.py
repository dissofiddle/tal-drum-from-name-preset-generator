#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import math
import os
import re
import random
import xml.etree.ElementTree as ET

from common import (
    parse_mapping_file,
    parse_midi_note_list,
    LAYER_LIMIT_PER_PAD,
)

TALDRUM_VERSION = "13"
DEFAULT_VOLUME = "0.75"
DEFAULT_PANELMODE = "0"

DEFAULT_PAD_COUNT = 64
DEFAULT_PAD_BASE_MIDI = 36  # C2


# ------------------------------------------------------------
# Utils
# ------------------------------------------------------------

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[\\/:\*\?\"<>\|]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "UNTITLED"


def load_listing_json(listing_path: str) -> dict:
    with open(listing_path, "r", encoding="utf-8") as f:
        return json.load(f)


def float_str(n: int) -> str:
    return f"{float(n):.1f}"


# ------------------------------------------------------------
# 🎨 TRUE TAL COLOUR (ARGB signed 32-bit)
# ------------------------------------------------------------

def random_pad_colour() -> str:
    """
    TAL Drum 'colour' is stored as a signed 32-bit integer.
    It corresponds to ARGB (0xAARRGGBB).

    We generate vivid colors (avoid gray-ish).
    Alpha is fixed to 255.
    """
    while True:
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)

        # Avoid near-gray colors
        if max(r, g, b) - min(r, g, b) < 80:
            continue

        argb = (255 << 24) | (r << 16) | (g << 8) | b

        # Convert to signed 32-bit int
        if argb >= 2**31:
            argb -= 2**32

        return str(argb)


# ------------------------------------------------------------
# Velocity
# ------------------------------------------------------------

def velocity_ranges(n_layers: int):
    if n_layers <= 0:
        return []

    ranges = []
    for i in range(n_layers):
        start = math.floor(i * 127 / n_layers) + 1
        end = math.floor((i + 1) * 127 / n_layers)
        if i == n_layers - 1:
            end = 127
        ranges.append((start, end))

    # Ensure contiguous
    for i in range(1, len(ranges)):
        prev_end = ranges[i - 1][1]
        cur_start, cur_end = ranges[i]
        if cur_start != prev_end + 1:
            ranges[i] = (prev_end + 1, cur_end)

    return ranges


# ------------------------------------------------------------
# Path handling
# ------------------------------------------------------------

def wav_to_pathrelative(wav_path: str, global_base: str) -> str:
    wav_abs = os.path.abspath(wav_path)
    base_abs = os.path.abspath(global_base)

    rel = os.path.relpath(wav_abs, base_abs)

    if rel.startswith(".."):
        raise ValueError(
            f"Sample outside global base path:\n"
            f"{wav_abs}\nbase={base_abs}"
        )

    return rel.replace("\\", "/")


def wav_to_path_foldback(wav_path: str, preset_dir: str) -> str:
    wav_abs = os.path.abspath(wav_path)
    preset_dir_abs = os.path.abspath(preset_dir)
    rel = os.path.relpath(wav_abs, preset_dir_abs)
    return rel.replace("\\", "/")


# ------------------------------------------------------------
# TAL Drum XML building
# ------------------------------------------------------------

def make_empty_taldrum_root(preset_path_abs: str, kit_name: str) -> ET.Element:
    root = ET.Element(
        "taldrum",
        {
            "version": TALDRUM_VERSION,
            "path": preset_path_abs.replace("\\", "/"),
            "name": kit_name,
            "volume": DEFAULT_VOLUME,
            "panelmode": DEFAULT_PANELMODE,
        },
    )
    ET.SubElement(root, "pads")
    return root


def make_pad(pads_el: ET.Element, pad_index: int, midi_note: int) -> ET.Element:
    pad_el = ET.SubElement(
        pads_el,
        "pad",
        {
            "version": TALDRUM_VERSION,
            "activemappings": "0",
            "colour": "0",
            "name": f"Pad {pad_index+1}",
            "midikey": float_str(midi_note),
        },
    )

    maps_el = ET.SubElement(pad_el, "mappings")
    for _ in range(LAYER_LIMIT_PER_PAD):
        ET.SubElement(maps_el, "mapping", {"path": "", "pathrelative": ""})

    return pad_el


def build_base_pads(root: ET.Element, base_midi: int, pad_count: int):
    pads_el = root.find("pads")
    midi_to_pad = {}

    for i in range(pad_count):
        note = base_midi + i
        pad_el = make_pad(pads_el, i, note)
        midi_to_pad[note] = pad_el

    return midi_to_pad


def set_pad_layers(pad_el, wav_paths, preset_dir, global_base):
    maps_el = pad_el.find("mappings")
    mappings = list(maps_el)

    n = min(len(wav_paths), LAYER_LIMIT_PER_PAD)
    ranges = velocity_ranges(n)

    # Clear mappings
    for m in mappings:
        m.attrib.clear()
        m.set("path", "")
        m.set("pathrelative", "")

    for i in range(n):
        wav = wav_paths[i]
        m = mappings[i]

        m.set("pathrelative", wav_to_pathrelative(wav, global_base))
        m.set("path", wav_to_path_foldback(wav, preset_dir))

        vstart, vend = ranges[i]

        if n == 1:
            pass
        elif i == 0:
            m.set("velocityend", float_str(vend))
        elif i == n - 1:
            m.set("velocitystart", float_str(vstart))
        else:
            m.set("velocitystart", float_str(vstart))
            m.set("velocityend", float_str(vend))

    pad_el.set("activemappings", str(n))


def pretty_xml(elem):
    def indent(e, level=0):
        i = "\n" + level * "  "
        if len(e):
            if not e.text or not e.text.strip():
                e.text = i + "  "
            for child in e:
                indent(child, level + 1)
            if not e.tail or not e.tail.strip():
                e.tail = i
        else:
            if level and (not e.tail or not e.tail.strip()):
                e.tail = i

    indent(elem)
    return ET.tostring(elem, encoding="utf-8", xml_declaration=True).decode("utf-8")


# ------------------------------------------------------------
# Assignment logic
# ------------------------------------------------------------

def assign_samples_to_notes(kit_elements, mapping, overflow_policy, trash_notes):
    note_to_samples = {}
    warnings = []

    mapped_notes = set()
    for entry in mapping.values():
        if entry.midi_notes:
            mapped_notes.update(entry.midi_notes)

    trash_pool = [n for n in trash_notes if n not in mapped_notes]

    def push(note, samples):
        note_to_samples.setdefault(note, []).extend(samples)

    def push_trash(samples):
        nonlocal trash_pool
        idx = 0
        while idx < len(samples) and trash_pool:
            note = trash_pool[0]
            cur = note_to_samples.get(note, [])
            space = LAYER_LIMIT_PER_PAD - len(cur)

            if space <= 0:
                trash_pool.pop(0)
                continue

            take = samples[idx: idx + space]
            push(note, take)
            idx += len(take)

            if len(note_to_samples[note]) >= LAYER_LIMIT_PER_PAD:
                trash_pool.pop(0)

        if idx < len(samples):
            warnings.append(f"Dropped {len(samples)-idx} samples (trash full)")

    for category, files in kit_elements.items():
        if category == "other":
            if overflow_policy in ("trash", "ignore"):
                push_trash(files)
            continue

        entry = mapping.get(category)
        notes = entry.midi_notes if entry and entry.midi_notes else []

        idx = 0
        for note in notes:
            chunk = files[idx: idx + LAYER_LIMIT_PER_PAD]
            if not chunk:
                break
            push(note, chunk)
            idx += len(chunk)

        overflow = files[idx:]
        if overflow:
            if overflow_policy == "truncate":
                warnings.append(f"Overflow in {category}, truncated {len(overflow)}")
            elif overflow_policy in ("trash", "ignore"):
                push_trash(overflow)

    return note_to_samples, warnings


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Generate TAL Drum kits")

    p.add_argument("listing_json")
    p.add_argument("--mapping", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--global-sample-base", required=True)

    p.add_argument("--overflow-policy",
                   choices=["reject", "truncate", "trash", "ignore"],
                   default="trash")

    p.add_argument("--trash-notes", default="82-127")
    p.add_argument("--pad-base-midi", type=int, default=DEFAULT_PAD_BASE_MIDI)
    p.add_argument("--pad-count", type=int, default=DEFAULT_PAD_COUNT)

    args = p.parse_args()

    listing = load_listing_json(args.listing_json)
    mapping = parse_mapping_file(args.mapping)

    ensure_dir(args.output_dir)
    out_dir = os.path.abspath(args.output_dir)

    trash_notes = parse_midi_note_list(args.trash_notes)

    for kit_name, kit_elements in listing.items():
        kit_safe = sanitize_filename(kit_name)
        preset_path = os.path.join(out_dir, f"{kit_safe}.taldrum")
        preset_path_abs = os.path.abspath(preset_path)

        root = make_empty_taldrum_root(preset_path_abs, kit_safe)
        midi_to_pad = build_base_pads(root, args.pad_base_midi, args.pad_count)

        note_to_samples, warns = assign_samples_to_notes(
            kit_elements, mapping, args.overflow_policy, trash_notes
        )

        for note, files in note_to_samples.items():
            pad_el = midi_to_pad.get(note)
            if pad_el is None:  # ✅ no more DeprecationWarning
                continue

            set_pad_layers(
                pad_el,
                files[:LAYER_LIMIT_PER_PAD],
                os.path.dirname(preset_path_abs),
                args.global_sample_base
            )

            # 🎨 Apply visible random colour
            pad_el.set("colour", random_pad_colour())

        xml_text = pretty_xml(root)

        with open(preset_path_abs, "w", encoding="utf-8") as f:
            f.write(xml_text)

    print(f"Generation complete → {out_dir}")


if __name__ == "__main__":
    main()
