#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json

from common import (
    parse_mapping_file,
    mapping_to_nomenclature,
    scan_samples,
    filter_kits,
    print_listing,
    parse_midi_note_list,
)


def to_jsonable(obj):
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]
    return obj


def main():
    p = argparse.ArgumentParser(description="Create listing of NI/Maschine kits")

    p.add_argument("samples_folder")
    p.add_argument("--mapping", default="mapping.txt")

    p.add_argument("--min-total", type=int, default=0)
    p.add_argument("--exclude-only-other", action="store_true")
    p.add_argument("--exclude-mixed-other", action="store_true")

    p.add_argument(
        "--overflow-policy",
        choices=["reject", "truncate", "trash", "ignore"],
        default="reject"
    )

    p.add_argument(
        "--trash-notes",
        help="MIDI trash notes (e.g. 82-127). Default: 82-127"
    )

    p.add_argument("--export-valid")
    p.add_argument("--export-rejected")

    args = p.parse_args()

    mapping = parse_mapping_file(args.mapping)
    nomenclature = mapping_to_nomenclature(mapping)

    kits = scan_samples(args.samples_folder, nomenclature)

    if args.overflow_policy == "trash":
        if args.trash_notes:
            trash_notes = parse_midi_note_list(args.trash_notes)
        else:
            trash_notes = list(range(82, 128))
    else:
        trash_notes = []

    valid, rejected = filter_kits(
        kits,
        min_total_samples=args.min_total,
        exclude_only_other=args.exclude_only_other,
        exclude_mixed_other=args.exclude_mixed_other,
        mapping=mapping,
        overflow_policy=args.overflow_policy,
        trash_notes=trash_notes,
    )

    print(f"\nVALID KITS : {len(valid)}")
    #print_listing(valid)

    print(f"\nREJECTED KITS : {len(rejected)}")

    if args.export_valid:
        with open(args.export_valid, "w", encoding="utf-8") as f:
            json.dump(to_jsonable(valid), f, indent=2, ensure_ascii=False)
        print(f"\nValid exported to {args.export_valid}")

    if args.export_rejected:
        with open(args.export_rejected, "w", encoding="utf-8") as f:
            json.dump(to_jsonable(rejected), f, indent=2, ensure_ascii=False)
        print(f"\nRejected exported to {args.export_rejected}")


if __name__ == "__main__":
    main()
