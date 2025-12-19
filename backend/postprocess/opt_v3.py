from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


STUD_PITCH_LDU = 20.0
MERGE_TOLERANCE = 1e-3

# family, studs_x, studs_y -> part number
PART_LIBRARY: Dict[Tuple[str, int, int], str] = {
    ("plate", 1, 1): "3024.dat",
    ("plate", 2, 1): "3023.dat",
    ("plate", 1, 2): "3023.dat",
    ("plate", 3, 1): "3623.dat",
    ("plate", 1, 3): "3623.dat",
    ("plate", 4, 1): "3710.dat",
    ("plate", 1, 4): "3710.dat",
    ("plate", 2, 2): "3022.dat",
    ("plate", 2, 3): "3021.dat",
    ("plate", 3, 2): "3021.dat",
    ("plate", 2, 4): "3020.dat",
    ("plate", 4, 2): "3020.dat",
    ("plate", 4, 4): "3031.dat",
    ("brick", 1, 1): "3005.dat",
    ("brick", 2, 1): "3004.dat",
    ("brick", 1, 2): "3004.dat",
    ("brick", 3, 1): "3622.dat",
    ("brick", 1, 3): "3622.dat",
    ("brick", 4, 1): "3010.dat",
    ("brick", 1, 4): "3010.dat",
    ("brick", 2, 2): "3003.dat",
    ("brick", 2, 4): "3001.dat",
    ("brick", 4, 2): "3001.dat",
}

ALIAS_PATTERN = re.compile(r"(plate|brick)_(\d+)x(\d+)$")
NUMBER_TO_DESCRIPTOR: Dict[str, Tuple[str, int, int]] = {}
for descriptor, part_no in PART_LIBRARY.items():
    NUMBER_TO_DESCRIPTOR[part_no.lower()] = descriptor
    NUMBER_TO_DESCRIPTOR[part_no.lower().rstrip(".dat")] = descriptor


def _normalize_token(token: str) -> str:
    value = token.strip().lower()
    value = value.replace("\\", "/")
    if "/" in value:
        value = value.rsplit("/", 1)[-1]
    return value


def _resolve_descriptor(part_type: str) -> Optional[Tuple[str, int, int]]:
    token = _normalize_token(part_type)
    if not token:
        return None
    if token in NUMBER_TO_DESCRIPTOR:
        return NUMBER_TO_DESCRIPTOR[token]
    match = ALIAS_PATTERN.match(token)
    if match:
        descriptor = (match.group(1), int(match.group(2)), int(match.group(3)))
        if descriptor in PART_LIBRARY:
            return descriptor
    if token.endswith(".dat") and token[:-4] in NUMBER_TO_DESCRIPTOR:
        return NUMBER_TO_DESCRIPTOR[token[:-4]]
    return None


def _lookup_part_number(family: str, studs_x: int, studs_y: int) -> Optional[str]:
    return PART_LIBRARY.get((family, studs_x, studs_y))


def format_type1_line(color: str, position: Tuple[float, float, float], rotation: Tuple[float, ...], part_type: str) -> str:
    rot = " ".join(f"{v:g}" for v in rotation)
    return (
        f"1 {color} {position[0]:.3f} {position[1]:.3f} {position[2]:.3f} "
        f"{rot} {part_type}"
    )


def parse_mpd_line(line: str) -> Optional[Dict[str, object]]:
    if not line.startswith("1 "):
        return None
    tokens = line.split()
    if len(tokens) < 14:
        return None
    color = tokens[1]
    try:
        x, y, z = float(tokens[2]), float(tokens[3]), float(tokens[4])
        rotation = tuple(float(value) for value in tokens[5:14])
    except ValueError:
        return None
    part_type = tokens[14]
    return {
        "color": color,
        "position": (x, y, z),
        "rotation": rotation,
        "part_type": part_type,
        "original_line": line,
    }


def part_to_ldraw(part_type: str) -> Optional[str]:
    descriptor = _resolve_descriptor(part_type)
    if not descriptor:
        return None
    return _lookup_part_number(*descriptor)


def get_part_size_from_name(part_type: str) -> Tuple[int, int]:
    descriptor = _resolve_descriptor(part_type)
    if descriptor:
        return descriptor[1], descriptor[2]
    return 1, 1


def group_by_color_and_position(components: Iterable[Dict[str, object]], axis: int = 0) -> Dict[Tuple[str, float, float], List[Dict[str, object]]]:
    grouped: Dict[Tuple[str, float, float], List[Dict[str, object]]] = defaultdict(list)
    other_axis = 1 if axis == 0 else 0
    for comp in components:
        position = comp["position"]
        color = comp["color"]
        key = (
            color,
            round(position[2], 3),
            round(position[other_axis], 3),
        )
        grouped[key].append(comp)
    for key in grouped:
        grouped[key].sort(key=lambda item: item["position"][axis])
    return grouped


def _are_adjacent(prev_comp: Dict[str, object], next_comp: Dict[str, object], axis: int, axis_studs: int) -> bool:
    prev_pos = prev_comp["position"]
    next_pos = next_comp["position"]
    delta = abs(next_pos[axis] - prev_pos[axis])
    expected = axis_studs * STUD_PITCH_LDU
    if abs(delta - expected) > MERGE_TOLERANCE:
        return False
    for idx in range(3):
        if idx == axis:
            continue
        if abs(prev_pos[idx] - next_pos[idx]) > MERGE_TOLERANCE:
            return False
    return prev_comp["color"] == next_comp["color"] and prev_comp["part_type"] == next_comp["part_type"]


def combine_group(group: List[Dict[str, object]], axis: int, part_type: str) -> List[Dict[str, object]]:
    if len(group) <= 1:
        return group
    descriptor = _resolve_descriptor(part_type)
    if not descriptor:
        return group
    family, studs_x, studs_y = descriptor
    axis_studs = studs_x if axis == 0 else studs_y
    other_axis_studs = studs_y if axis == 0 else studs_x
    new_axis_studs = axis_studs * len(group)
    if axis == 0:
        target_width, target_depth = new_axis_studs, other_axis_studs
    elif axis == 1:
        target_width, target_depth = other_axis_studs, new_axis_studs
    else:
        return group
    new_part = _lookup_part_number(family, target_width, target_depth)
    if not new_part:
        return group
    first = group[0]
    last = group[-1]
    position = list(first["position"])
    position[axis] = (first["position"][axis] + last["position"][axis]) / 2.0
    new_line = format_type1_line(
        first["color"],
        (position[0], position[1], position[2]),
        first["rotation"],
        new_part,
    )
    return [
        {
            "color": first["color"],
            "position": (position[0], position[1], position[2]),
            "rotation": first["rotation"],
            "part_type": new_part,
            "original_line": new_line,
        }
    ]


def merge_in_line(components: List[Dict[str, object]], axis: int, part_type: str) -> List[Dict[str, object]]:
    descriptor = _resolve_descriptor(part_type)
    if not descriptor:
        raise ValueError(f"Unsupported part type: {part_type}")
    family, studs_x, studs_y = descriptor
    axis_studs = studs_x if axis == 0 else studs_y
    if axis not in (0, 1):
        raise ValueError("Only X and Y axes are supported for merging")
    merged: List[Dict[str, object]] = []
    if not components:
        return merged
    current_group: List[Dict[str, object]] = [components[0]]
    for comp in components[1:]:
        if _are_adjacent(current_group[-1], comp, axis, axis_studs):
            current_group.append(comp)
        else:
            merged.extend(combine_group(current_group, axis, part_type))
            current_group = [comp]
    merged.extend(combine_group(current_group, axis, part_type))
    return merged


def optimize_mpd_file(file_path: Path | str, part_type: str, axis: int = 0) -> None:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)
    target_part = part_to_ldraw(part_type)
    if target_part is None:
        raise ValueError(f"Unsupported part type: {part_type}")
    with path.open("r", encoding="utf-8") as handle:
        original_lines = handle.readlines()
    components: List[Dict[str, object]] = []
    target_indexes = set()
    for index, line in enumerate(original_lines):
        parsed = parse_mpd_line(line.strip())
        if parsed and parsed["part_type"].lower() == target_part.lower():
            parsed["line_index"] = index
            components.append(parsed)
            target_indexes.add(index)
    if not components:
        return
    grouped = group_by_color_and_position(components, axis=axis)
    optimized: List[Dict[str, object]] = []
    for group in grouped.values():
        optimized.extend(merge_in_line(group, axis, part_type))
    made_changes = any(
        "line_index" not in comp or comp["part_type"].lower() != target_part.lower()
        for comp in optimized
    )
    if not made_changes:
        return
    new_lines: List[str] = []
    for idx, line in enumerate(original_lines):
        if idx not in target_indexes:
            new_lines.append(line)
    if optimized:
        new_lines.append("0 // --- Optimized components ---\n")
        for comp in optimized:
            new_lines.append(comp["original_line"].rstrip("\n") + "\n")
    with path.open("w", encoding="utf-8") as handle:
        handle.writelines(new_lines)


if __name__ == "__main__":
    pass



