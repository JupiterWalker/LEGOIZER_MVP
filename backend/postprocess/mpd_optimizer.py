from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

# LDraw spacing: 1 stud width equals 20 LDraw units (8 mm / 0.4 mm per LDU)
STUD_SPACING_LDU = 20.0
TOLERANCE = 1e-3

# Supported replacement variants per base part key.
PART_VARIANTS: Dict[str, Dict[int, str]] = {
    "plate_1x1": {
        1: "3024",
        2: "3023",
        3: "3623",
        4: "3710",
    },
    "brick_1x1": {
        1: "3005",
        2: "3004",
        3: "3622",
        4: "3010",
    },
}

IDENTITY_ORIENTATION = ("1", "0", "0", "0", "1", "0", "0", "0", "1")


def _format_orientation(matrix: Sequence[str]) -> str:
    return " ".join(matrix)


def _make_line(color: str, position: Tuple[float, float, float], orientation: Tuple[str, ...], part_id: str) -> str:
    x, y, z = position
    orient = _format_orientation(orientation)
    return (
        f"1 {color} "
        f"{x:.3f} {y:.3f} {z:.3f} "
        f"{orient} "
        f"{part_id}.dat"
    )


def _group_candidates(candidates: Iterable[Dict[str, object]]) -> Dict[Tuple[str, float, float, Tuple[str, ...]], List[Dict[str, object]]]:
    buckets: Dict[Tuple[str, float, float, Tuple[str, ...]], List[Dict[str, object]]] = defaultdict(list)
    for entry in candidates:
        key = (
            entry["color"],
            round(entry["y"], 3),
            round(entry["z"], 3),
            entry["orientation"],
        )
        buckets[key].append(entry)
    return buckets


def _split_runs(entries: List[Dict[str, object]]) -> List[List[Dict[str, object]]]:
    if not entries:
        return []
    runs: List[List[Dict[str, object]]] = []
    current = [entries[0]]
    for prev, this in zip(entries, entries[1:]):
        step = this["x"] - prev["x"]
        if abs(step - STUD_SPACING_LDU) <= TOLERANCE:
            current.append(this)
        else:
            runs.append(current)
            current = [this]
    runs.append(current)
    return runs


def _segment_run(run: List[Dict[str, object]], variants: Dict[int, str]) -> List[List[Dict[str, object]]]:
    order = [length for length in sorted(variants.keys(), reverse=True) if length > 1]
    order.append(1)

    segments: List[List[Dict[str, object]]] = []
    idx = 0
    while idx < len(run):
        remaining = len(run) - idx
        selected = 1
        for length in order:
            if length <= remaining:
                selected = length
                break
        segments.append(run[idx : idx + selected])
        idx += selected
    return segments


def _build_replacements(groups: Dict[Tuple[str, float, float, Tuple[str, ...]], List[Dict[str, object]]], variants: Dict[int, str]) -> List[str]:
    replacements: List[str] = []
    ordered_keys = sorted(groups.keys(), key=lambda k: (k[1], k[2], k[0]))
    for key in ordered_keys:
        entries = groups[key]
        entries.sort(key=lambda item: item["x"])
        runs = _split_runs(entries)
        for run in runs:
            segments = _segment_run(run, variants)
            for segment in segments:
                length = len(segment)
                part_id = variants.get(length, variants[1])
                start_x = segment[0]["x"]
                center_x = start_x + STUD_SPACING_LDU * (length - 1) / 2.0
                y = segment[0]["y"]
                z = segment[0]["z"]
                color = segment[0]["color"]
                orientation = segment[0]["orientation"]
                replacements.append(
                    _make_line(color, (center_x, y, z), orientation, part_id)
                )
    return replacements


def optimize_mpd_file(mpd_path: Path | str, base_part: str) -> None:
    """Rewrite the MPD so adjacent same-colour 1x1 parts become longer variants."""
    variants = PART_VARIANTS.get(base_part)
    if not variants or 1 not in variants:
        return

    mpd_path = Path(mpd_path)
    if not mpd_path.exists():
        return

    lines = mpd_path.read_text().splitlines()
    if not lines:
        return

    base_filename = f"{variants[1]}.dat"

    kept_lines: List[str] = []
    candidates: List[Dict[str, object]] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("1 "):
            parts = stripped.split()
            if parts[-1].lower() == base_filename.lower() and tuple(parts[5:14]) == IDENTITY_ORIENTATION:
                try:
                    x = float(parts[2])
                    y = float(parts[3])
                    z = float(parts[4])
                except ValueError:
                    kept_lines.append(line)
                    continue
                candidates.append(
                    {
                        "color": parts[1],
                        "x": x,
                        "y": y,
                        "z": z,
                        "orientation": IDENTITY_ORIENTATION,
                    }
                )
                continue
        kept_lines.append(line)

    if not candidates:
        return

    groups = _group_candidates(candidates)
    replacements = _build_replacements(groups, variants)

    if not replacements:
        return

    tail = None
    if kept_lines and kept_lines[-1].strip().upper() == "0 NOFILE":
        tail = kept_lines.pop()

    kept_lines.extend(replacements)

    if tail is not None:
        kept_lines.append(tail)

    mpd_path.write_text("\n".join(kept_lines))
