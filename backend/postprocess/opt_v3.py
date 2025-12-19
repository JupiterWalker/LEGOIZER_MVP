from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from backend.postprocess.color_table import COMMON_LDRAW_COLORS, LEGO_COLORS


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

import math

AXIS_SWITCH_UNIT = 48.0  # LDU multiplier for deciding merge axis by layer height


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """将十六进制颜色代码转换为RGB元组"""
    hex_color = hex_color.lstrip('#').lstrip('0x')
    
    # 处理乐高特有的7位颜色代码
    if len(hex_color) == 7:
        hex_color = hex_color[1:]  # 移除第一位字符
    
    # 确保是6位十六进制
    if len(hex_color) < 6:
        hex_color = hex_color.zfill(6)
    elif len(hex_color) > 6:
        hex_color = hex_color[-6:]  # 取最后6位
    
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except ValueError:
        # 解析失败时返回黑色
        return (0, 0, 0)

def color_distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    """计算两个RGB颜色之间的欧几里得距离"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))

def match_lego_color(rgb: Tuple[int, int, int]) -> str:
    """将RGB颜色匹配到最接近的标准乐高颜色"""
    return min(LEGO_COLORS.items(), key=lambda item: color_distance(rgb, item[1]))[0]


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
    rgb = hex_to_rgb(color)
    lego_color = match_lego_color(rgb)
    elements = line.split(" ")
    line_el = f"{elements[0]} {lego_color} {' '.join(elements[2:])}"
    return {
        "color": lego_color,
        "position": (x, y, z),
        "rotation": rotation,
        "part_type": part_type,
        "original_line": line_el,
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
    other_axis = 2 if axis == 0 else 0
    for comp in components:
        position = comp["position"]
        color = comp["color"]
        key = (
            color,  # 同颜色
            round(position[1], 3),  # 同高度
            round(position[other_axis], 3),  # 同另一轴位置
        )
        grouped[key].append(comp)
    for key in grouped:
        grouped[key].sort(key=lambda item: item["position"][axis])
    return grouped


def _axis_for_layer(layer_height: float) -> int:
    """Determine merge axis per layer height.

    Even multiples of AXIS_SWITCH_UNIT merge along X; odd multiples along Y; other heights default to Y.
    """
    return 0 if layer_height % AXIS_SWITCH_UNIT == 0 else 2


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


def _available_lengths_for_axis(
    family: str,
    other_axis_studs: int,
    axis: int,
) -> List[int]:
    lengths = set()
    for (fam, studs_x, studs_y), _ in PART_LIBRARY.items():
        if fam != family:
            continue
        if axis == 0 and studs_y == other_axis_studs:
            lengths.add(studs_x)
        elif axis == 2 and studs_x == other_axis_studs:
            lengths.add(studs_y)
    return sorted(lengths, reverse=True)


def _build_combined_component(
    segment: List[Dict[str, object]],
    axis: int,
    part_no: str,
) -> Dict[str, object]:
    first = segment[0]
    last = segment[-1]
    position = list(first["position"])
    position[axis] = (first["position"][axis] + last["position"][axis]) / 2.0
    if axis == 2:
        rotation = (0.0, 0.0, 1.0, 0.0, 1.0, 0.0, -1.0, 0.0, 0.0)
    else:
        rotation = first["rotation"]
    new_line = format_type1_line(
        first["color"],
        (position[0], position[1], position[2]),
        rotation,
        part_no,
    )
    return {
        "color": first["color"],
        "position": (position[0], position[1], position[2]),
        "rotation": rotation,
        "part_type": part_no,
        "original_line": new_line,
    }


def combine_group(group: List[Dict[str, object]], axis: int, part_type: str) -> List[Dict[str, object]]:
    if len(group) <= 1:
        return group
    descriptor = _resolve_descriptor(part_type)
    if not descriptor:
        return group
    family, studs_x, studs_y = descriptor
    axis_studs = studs_x if axis == 0 else studs_y
    other_axis_studs = studs_y if axis == 0 else studs_x
    if axis_studs <= 0 or other_axis_studs <= 0:
        return group

    available_lengths = _available_lengths_for_axis(family, other_axis_studs, axis)
    if not available_lengths:
        return group

    result: List[Dict[str, object]] = []
    idx = 0
    while idx < len(group):
        remaining = len(group) - idx
        chosen_length = None
        components_needed = 1
        for length in available_lengths:
            if length % axis_studs != 0:
                continue
            needed = length // axis_studs
            if needed <= 0 or needed > remaining:
                continue
            chosen_length = length
            components_needed = needed
            break
        if chosen_length is None or components_needed <= 1:
            # 无法合并更大的零件，保留原件
            result.append(group[idx])
            idx += 1
            continue

        segment = group[idx : idx + components_needed]
        if axis == 0:
            width, depth = chosen_length, other_axis_studs
        else:
            width, depth = other_axis_studs, chosen_length
        part_no = _lookup_part_number(family, width, depth)
        if not part_no:
            # 理论上不会发生，但为安全起见退化
            result.append(group[idx])
            idx += 1
            continue
        result.append(_build_combined_component(segment, axis, part_no))
        idx += components_needed

    return result


def merge_in_line(components: List[Dict[str, object]], axis: int, part_type: str) -> List[Dict[str, object]]:
    descriptor = _resolve_descriptor(part_type)
    if not descriptor:
        raise ValueError(f"Unsupported part type: {part_type}")
    family, studs_x, studs_y = descriptor
    axis_studs = studs_x if axis == 0 else studs_y
    if axis not in (0, 2):
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


def optimize_mpd_file(file_path: Path | str, part_type: str, axis: int | None = None) -> None:
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
    layers: Dict[float, List[Dict[str, object]]] = defaultdict(list)
    for index, line in enumerate(original_lines):
        parsed = parse_mpd_line(line.strip())
        if parsed and parsed["part_type"].lower() == target_part.lower():
            parsed["line_index"] = index
            components.append(parsed)
            target_indexes.add(index)
            layer_height = round(parsed["position"][1], 3)
            parsed["layer_height"] = layer_height
            layers[layer_height].append(parsed)
        else:
            print(f"Skipping line {index}: not target part")
    if not components:
        return
    optimized: List[Dict[str, object]] = []
    for layer_height, layer_components in layers.items():
        current_axis = axis if axis in (0, 2) else _axis_for_layer(layer_height)
        # current_axis = _axis_for_layer(layer_height)
        grouped = group_by_color_and_position(layer_components, axis=current_axis)
        for group in grouped.values():
            optimized.extend(merge_in_line(group, current_axis, part_type))
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



