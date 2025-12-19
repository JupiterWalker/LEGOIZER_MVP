from __future__ import annotations
import re
import math
import itertools
import pathlib
from typing import List, Tuple, Dict, Set, Optional, Callable, Iterable
from collections import defaultdict, deque

# ======================
# 类型与常量
# ======================

V2 = Tuple[int, int]
V3 = Tuple[int, int, int]
BrickKey = Tuple[int, V2, int]  # (z, (x, y), color)
Rect = Tuple[int, int, int, int]  # (x0, y0, x1, y1) 闭区间
PartLib = Dict[V2, str]  # {(w, h): "part_no", ...}
NewBrick = Tuple[Rect, int, str]  # (rect, color, part_no)

EPS = 1e-6
LDRAW_HEADER = [
    "0",
    "0 Name: merged_model.mpd",
    "0 Author: LDraw Merge Plugin",
    "0 !LDRAW_ORG Unofficial_Model",
]
EMPTY_LINE = "0 // empty"

# ======================
# 工具函数
# ======================

def normalize_part_number(part_no: str) -> str:
    token = part_no.strip()
    if token.lower().endswith(".dat"):
        token = token[:-4]
    return token.upper()


def ensure_part_extension(part_no: str) -> str:
    token = part_no.strip()
    if not token.lower().endswith(".dat"):
        token = f"{token}.dat"
    return token

def round_int(v: float) -> int:
    return int(round(v))

def quantize(v: float, eps: float = EPS) -> int:
    r = round(v)
    return r if abs(r - v) < eps else int(math.floor(v + 0.5))

def bbox2rect(b: Tuple[float, float, float, float]) -> Rect:
    x0, y0, x1, y1 = b
    return (quantize(x0), quantize(y0), quantize(x1), quantize(y1))

def rect_area(r: Rect) -> int:
    return max(0, r[2] - r[0] + 1) * max(0, r[3] - r[1] + 1)

def rect_intersect(a: Rect, b: Rect) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])

def rect_cover(a: Rect, b: Rect) -> bool:
    return a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]

def rect_inside(a: Rect, b: Rect) -> bool:
    return b[0] <= a[0] and b[1] <= a[1] and b[2] >= a[2] and b[3] >= a[3]

def cells_in_rect(r: Rect) -> Set[V2]:
    xs = range(r[0], r[2] + 1)
    ys = range(r[1], r[3] + 1)
    return {(x, y) for x in xs for y in ys}

def dilate_rect(r: Rect, d: int) -> Rect:
    return (r[0] - d, r[1] - d, r[2] + d, r[3] + d)

def bfs_connected_components(grid: Dict[V2, int], connectivity: int = 6) -> List[Set[V2]]:
    """
    6-connectivity: 上下左右前后（这里仅用 4 连通于 XY）
    26-connectivity: 含对角
    """
    visited: Set[V2] = set()
    components: List[Set[V2]] = []
    dirs4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    dirs8 = dirs4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    dirs = dirs8 if connectivity == 26 else dirs4

    for start in grid:
        if start in visited:
            continue
        comp = set()
        q = deque([start])
        visited.add(start)
        while q:
            cx, cy = q.popleft()
            comp.add((cx, cy))
            for dx, dy in dirs:
                nb = (cx + dx, cy + dy)
                if nb in grid and nb not in visited:
                    visited.add(nb)
                    q.append(nb)
        components.append(comp)
    return components

def snap_to_grid_xy(verts: List[Tuple[float, float, float]], tol: float = EPS) -> List[V2]:
    """将 3D 顶点投影到 XY 并量化到整数网格"""
    pts = []
    for x, y, z in verts:
        if abs(z) > tol:
            continue
        pts.append((quantize(x), quantize(y)))
    return pts

def polygon_bbox(pts: Iterable[V2]) -> Rect:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))

# ======================
# MPD 解析与写入
# ======================

class LDrawMPDParser:
    def __init__(self, mpd_path: pathlib.Path):
        self.mpd_path = mpd_path
        self.files: Dict[str, List[str]] = {}
        self._parse()

    def _parse(self):
        current_file = None
        with self.mpd_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\r\n")
                if not line or line.startswith("0 //"):
                    continue
                if line.startswith("0 FILE "):
                    m = re.match(r"0\s+FILE\s+(.+)", line)
                    if m:
                        current_file = m.group(1).strip()
                        self.files[current_file] = []
                elif current_file:
                    self.files[current_file].append(line)

    def save(self, out_path: pathlib.Path):
        with out_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(LDRAW_HEADER) + "\n\n")
            for fname, lines in self.files.items():
                f.write(f"0 FILE {fname}\n")
                f.write("\n".join(lines))
                f.write("\n\n")

# 简易 LDraw 行构造（仅覆盖常用子集）
def ldraw_comment(text: str) -> str:
    return f"0 // {text}"

def ldraw_subfile(part_no: str, color: int, x: float, y: float, z: float, transform: str = "") -> str:
    # transform 预留（缩放/旋转/镜像），当前仅位置
    # 注意：LDraw 中旋转/镜像会改变朝向，这里不处理，仅做平移
    # 若需要旋转，请在此处扩展
    matrix = transform.strip() or "1 0 0 0 1 0 0 0 1"
    part_token = ensure_part_extension(part_no)
    return f"1 {color} {x:.6f} {y:.6f} {z:.6f} {matrix} {part_token}"

def ldraw_meta_step() -> str:
    return "0 STEP"

# ======================
# 砖/板库与候选尺寸
# ======================

def get_part_library() -> PartLib:
    """
    返回可用的砖/板零件库：键为 (w, h)，值为零件编号（字符串）。
    你可以按自己的库返回，如：
      - 板：1×n、2×2、2×4、4×4 ...
      - 砖：1×n、2×2、2×4、4×4 ...
    注意：高度固定为 1 个 LDRAW 单位（板）或 3 个 LDRAW 单位（砖），本插件只合并 XY。
    """
    base = {
        # 板（厚度 1）
        (1, 1): "3024",  # Plate 1x1
        (1, 2): "3023",  # Plate 1x2
        (1, 3): "3623",  # Plate 1x3
        (1, 4): "3710",  # Plate 1x4
        (2, 2): "3022",  # Plate 2x2
        (2, 3): "3021",  # Plate 2x3
        (2, 4): "3020",  # Plate 2x4
        (4, 4): "3031",  # Plate 4x4
    }
    lib: PartLib = dict(base)
    for (w, h), part_no in base.items():
        if w != h and (h, w) not in lib:
            lib[(h, w)] = part_no
    return lib

def candidate_sizes(max_wh: int = 8) -> List[V2]:
    sizes: List[V2] = []
    for w in range(1, max_wh + 1):
        for h in range(1, max_wh + 1):
            sizes.append((w, h))
    # 按面积降序，其次更“方正”优先
    sizes.sort(key=lambda s: (-s[0] * s[1], abs(s[0] - s[1])))
    return sizes

# ======================
# 几何与网格化
# ======================

def extract_bricks_from_mpd(mpd: LDrawMPDParser) -> Dict[BrickKey, Tuple[Rect, List[Tuple[float, float, float]]]]:
    """
    从 MPD 中提取所有 1×1 plate/brick 的占据格子与几何轮廓（用于后续合并与校验）。
    简化：仅识别 1×1 砖/板（类型 1，引用 3024/3005 等），并读取其顶点以得到精确包围盒。
    返回：{brick_key: (rect, verts_xy)}
    """
    bricks: Dict[BrickKey, Tuple[Rect, List[Tuple[float, float, float]]]] = {}
    part_lib = get_part_library()
    one_by_one_ids = {normalize_part_number(v) for k, v in part_lib.items() if k == (1, 1)}

    for fname, lines in mpd.files.items():
        transform_stack = []  # 简化：仅支持平移（x,y,z）
        for line in lines:
            if line.startswith("0 ROTSTEP"):
                continue
            if line.startswith("1 "):
                tokens = line.split()
                if len(tokens) < 15:
                    continue
                try:
                    color = int(tokens[1])
                    x, y, z = float(tokens[2]), float(tokens[3]), float(tokens[4])
                    part_no = normalize_part_number(tokens[14])
                except Exception:
                    continue
                # 仅处理 1×1
                if part_no not in one_by_one_ids:
                    continue
                # 简化：忽略变换矩阵，仅用平移
                # 读取顶点（类型 3/4 在 1×1 中通常不存在，若有需扩展）
                # 这里假设 1×1 的包围盒就是 [x-0.5, x+0.5] × [y-0.5, y+0.5]
                verts_xy = [
                    (x - 0.5, y - 0.5, z),
                    (x + 0.5, y - 0.5, z),
                    (x + 0.5, y + 0.5, z),
                    (x - 0.5, y + 0.5, z),
                ]
                ix, iy, iz = round_int(x), round_int(y), round_int(z)
                r = (ix, iy, ix, iy)
                key = (iz, (ix, iy), color)
                bricks[key] = (r, verts_xy)
            elif line.startswith("0 STEP"):
                continue
    return bricks

def build_voxel_grid(
    bricks: Dict[BrickKey, Tuple[Rect, List[Tuple[float, float, float]]]],
    connectivity: int = 6
) -> Dict[int, Dict[V2, int]]:
    """
    按 Z 分层构建占据网格：grid_by_z[z][(x,y)] = color
    """
    grid_by_z: Dict[int, Dict[V2, int]] = defaultdict(dict)
    for (z, _, color), (rect, _) in bricks.items():
        for cx, cy in cells_in_rect(rect):
            grid_by_z[z][(cx, cy)] = color
    return grid_by_z

# ======================
# 合并策略与校验钩子
# ======================

def propose_rects_from_component(
    comp: Set[V2], grid_by_z: Dict[int, Dict[V2, int]], z: int, color: int, candidates: List[V2]
) -> List[Rect]:
    """
    给定一个连通域，枚举所有能被候选砖/板完全覆盖的矩形（轴对齐）。
    """
    cells = list(comp)
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    candidates_in_bounds = []
    for w, h in candidates:
        if w <= (maxx - minx + 1) and h <= (maxy - miny + 1):
            candidates_in_bounds.append((w, h))
    rects = []
    for w, h in candidates_in_bounds:
        for gx in range(minx, maxx - w + 2):
            for gy in range(miny, maxy - h + 2):
                cand_rect = (gx, gy, gx + w - 1, gy + h - 1)
                cover = cells_in_rect(cand_rect)
                # 必须完全覆盖 comp 且不多占
                if cover.issubset(comp):
                    rects.append(cand_rect)
    # 去重并按面积降序
    seen = set()
    uniq = []
    for r in rects:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    uniq.sort(key=rect_area, reverse=True)
    return uniq

def can_place_rect(
    rect: Rect,
    z: int,
    color: int,
    grid_by_z: Dict[int, Dict[V2, int]],
    bricks: Dict[BrickKey, Tuple[Rect, List[Tuple[float, float, float]]]],
    allow_cover_others: bool = False,
) -> bool:
    """
    检查矩形放置是否合法：不越界、不覆盖异色、不与已合并砖干涉（简化：仅检查网格占用）
    """
    # 边界检查（简化：不检查模型边界，只检查与现有 1×1 的冲突）
    for cx, cy in cells_in_rect(rect):
        occ = grid_by_z.get(z, {}).get((cx, cy))
        if occ is not None and occ != color:
            return False
    # 可选：与已合并砖干涉检查（若 bricks 包含合并结果，需要传入）
    return True

def stability_check(
    rect: Rect, z: int, color: int, grid_by_z: Dict[int, Dict[V2, int]]
) -> bool:
    """
    稳定性钩子：检查下方是否有支撑（简化：仅检查 z-1 层同位置是否有占据）
    返回 True 表示通过
    """
    below = grid_by_z.get(z - 1, {})
    for cx, cy in cells_in_rect(rect):
        if (cx, cy) not in below:
            return False
    return True

def post_merge_hook(
    rect: Rect, z: int, color: int, part_no: str, grid_by_z: Dict[int, Dict[V2, int]]
) -> bool:
    """
    合并后钩子：可用于更新辅助索引、记录日志、进一步约束
    返回 True 表示接受
    """
    return True

# ======================
# 合并核心
# ======================

def merge_components_for_layer(
    grid_by_z: Dict[int, Dict[V2, int]],
    z: int,
    color: int,
    candidates: List[V2],
    strategy: str = "greedy_area",
    stability: bool = False,
    allow_cover_others: bool = False,
) -> Tuple[Set[V2], List[NewBrick]]:
    """
    对某一层、某一颜色的连通域执行合并，返回：
      - 仍保留的 1×1 单元集合（未被更大砖覆盖）
      - 合并后新增的砖/板列表：[(rect, part_no), ...]
    """
    layer = grid_by_z.get(z, {})
    if not layer:
        return set(), []

    # 1) 连通域分解
    comps = bfs_connected_components(layer, connectivity=4)  # 仅用 4 连通于 XY
    kept: Set[V2] = set()
    new_bricks: List[NewBrick] = []

    # 2) 候选砖/板尺寸按面积降序
    lib = get_part_library()
    # 过滤：仅保留当前库中存在的尺寸；优先砖(厚度3)再板(厚度1)
    avail = []
    for w, h in candidates:
        if (w, h) in lib:
            # 简单启发：面积大优先；若面积相同，砖优先（更稳）
            prio = (w * h, 1 if lib[(w, h)].startswith("300") else 0)
            avail.append((prio, w, h, lib[(w, h)]))
    avail.sort(key=lambda x: (-x[0][0], -x[0][1]))

    used = [[False] * 10000 for _ in range(10000)]  # 简化占用标记；实际可用位图/set优化

    def in_range(x, y):
        return 0 <= x < 10000 and 0 <= y < 10000

    for comp in comps:
        if not comp:
            continue
        # 计算外接矩形
        xs = [c[0] for c in comp]
        ys = [c[1] for c in comp]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        comp_rect = (minx, miny, maxx, maxy)
        comp_cells = cells_in_rect(comp_rect)

        placed = False
        # 3) 枚举候选砖/板
        for _, w, h, part_no in avail:
            if w > (maxx - minx + 1) or h > (maxy - miny + 1):
                continue
            # 枚举放置位置
            for gx in range(minx, maxx - w + 2):
                for gy in range(miny, maxy - h + 2):
                    cand_rect = (gx, gy, gx + w - 1, gy + h - 1)
                    cover = cells_in_rect(cand_rect)
                    # 必须完全覆盖 comp 且不多占
                    if not cover.issubset(comp):
                        continue
                    # 边界与占用检查
                    ok = True
                    for cx, cy in cover:
                        if not in_range(cx, cy) or used[cx][cy]:
                            ok = False
                            break
                        occ = layer.get((cx, cy))
                        if occ is not None and occ != color:
                            ok = False
                            break
                    if not ok:
                        continue
                    # 稳定性检查（可选）
                    if stability:
                        for cx, cy in cover:
                            if (cx, cy) not in grid_by_z.get(z - 1, {}):
                                ok = False
                                break
                    if not ok:
                        continue
                    # 通过校验：占用、写出
                    for cx, cy in cover:
                        used[cx][cy] = True
                    new_bricks.append((cand_rect, color, normalize_part_number(part_no)))
                    placed = True
                    break
                if placed:
                    break
            if placed:
                break
        if not placed:
            # 保留未合并的 1×1
            kept.update(comp)

    return kept, new_bricks


def build_merged_mpd(
    mpd: LDrawMPDParser,
    layer_results: Dict[int, Tuple[Set[V2], List[NewBrick]]],
    strategy: str = "greedy_area",
    stability: bool = False,
) -> LDrawMPDParser:
    """
    基于原 MPD 与每层合并结果，生成新的 MPD（仅替换 1×1 为更大砖/板）
    注意：本实现仅处理“类型 1 的 1×1 砖/板”，其它行（类型 3/4、引用、子模型引用）原样保留。
    """
    out_mpd = LDrawMPDParser.__new__(LDrawMPDParser)
    out_mpd.files = {k: list(v) for k, v in mpd.files.items()}
    lib = get_part_library()
    lib_by_part = {normalize_part_number(part): size for size, part in lib.items()}

    # 建立“保留集合”：哪些 (z, x, y) 仍是 1×1
    kept_global: Set[Tuple[int, int, int]] = set()
    for z, (kept, _) in layer_results.items():
        for x, y in kept:
            kept_global.add((z, x, y))

    # 逐文件、逐行扫描，替换类型 1 的 1×1
    for fname, lines in out_mpd.files.items():
        new_lines = []
        for line in lines:
            if not line.startswith("1 "):
                new_lines.append(line)
                continue
            tokens = line.split()
            if len(tokens) < 15:
                new_lines.append(line)
                continue
            try:
                color = int(tokens[1])
                x = float(tokens[2])
                y = float(tokens[3])
                z = float(tokens[4])
                part_no = normalize_part_number(tokens[14])
            except Exception:
                new_lines.append(line)
                continue
            # 仅处理 1×1 砖/板
            if part_no not in lib_by_part or lib_by_part[part_no] != (1, 1):
                new_lines.append(line)
                continue
            ix, iy = round_int(x), round_int(y)
            iz = round_int(z)
            if (iz, ix, iy) in kept_global:
                # 保留 1×1
                new_lines.append(line)
            else:
                # 已被合并：不写该行（由新增砖行替代）
                pass
        out_mpd.files[fname] = new_lines

    # 追加新增砖/板行（按层、按文件分组，简单落到 (0,0,0) 原点；如需保持原位置，请扩展：记录每个 rect 的 ref_xy）
    # 这里演示：把所有新增砖/板集中写到第一个子模型的末尾
    if not out_mpd.files:
        return out_mpd
    first_file = next(iter(out_mpd.files.keys()))
    target_lines = out_mpd.files[first_file]
    target_lines.append("")
    target_lines.append(ldraw_comment("--- Merged larger bricks/plates ---"))
    for z, (_, bricks) in sorted(layer_results.items()):
        for rect, brick_color, part_no in bricks:
            x0, y0, _, _ = rect
            target_lines.append(ldraw_subfile(part_no, brick_color, float(x0), float(y0), float(z)))
        target_lines.append("")

    return out_mpd


# ======================
# 主入口函数
# ======================

def merge_1x1_to_larger(
    mpd_path: str,
    out_path: Optional[str] = None,
    max_wh: int = 8,
    connectivity: int = 4,
    strategy: str = "greedy_area",
    stability: bool = False,
    allow_cover_others: bool = False,
) -> None:
    """
    将 MPD 中相邻同色的 1×1 plate/brick 合并为更大的砖/板。

    参数：
      - mpd_path: 输入 .mpd 路径
      - out_path: 输出 .mpd 路径；若为 None，则自动生成同目录 _merged.mpd
      - max_wh: 允许的最大砖/板尺寸（宽/高）
      - connectivity: 连通性（4 或 8）
      - strategy: 合并策略（目前仅实现 greedy_area）
      - stability: 是否启用“下方支撑”稳定性检查
      - allow_cover_others: 是否允许覆盖已被合并区域之外的单元（建议 False）
    """
    in_path = pathlib.Path(mpd_path)
    if not in_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {in_path}")
    if out_path is None:
        out_path = in_path.with_name(f"{in_path.stem}_merged.mpd")

    # 1) 解析
    mpd = LDrawMPDParser(in_path)

    # 2) 提取 1×1 砖/板并建立体素网格
    bricks = extract_bricks_from_mpd(mpd)
    grid_by_z = build_voxel_grid(bricks, connectivity=connectivity)

    # 3) 候选尺寸
    candidates = candidate_sizes(max_wh=max_wh)

    # 4) 按层、按颜色合并
    kept_by_layer: Dict[int, Set[V2]] = defaultdict(set)
    bricks_by_layer: Dict[int, List[NewBrick]] = defaultdict(list)
    for z in sorted(grid_by_z.keys()):
        layer = grid_by_z[z]
        if not layer:
            continue
        colors = {layer[c] for c in layer}
        for color in colors:
            comp_cells = {c for c, col in layer.items() if col == color}
            kept, new_bricks = merge_components_for_layer(
                grid_by_z,
                z,
                color,
                candidates,
                strategy=strategy,
                stability=stability,
                allow_cover_others=allow_cover_others,
            )
            kept_by_layer[z].update(kept)
            bricks_by_layer[z].extend(new_bricks)

    all_layers = set(kept_by_layer.keys()) | set(bricks_by_layer.keys())
    layer_results: Dict[int, Tuple[Set[V2], List[NewBrick]]] = {}
    for z in all_layers:
        layer_results[z] = (
            kept_by_layer.get(z, set()),
            bricks_by_layer.get(z, []),
        )

    # 5) 生成新 MPD
    merged_mpd = build_merged_mpd(mpd, layer_results, strategy=strategy, stability=stability)

    # 6) 写出
    merged_mpd.save(pathlib.Path(out_path))
    print(f"[OK] 已生成合并结果: {out_path}")


# ======================
# 命令行入口（可选）
# ======================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="将 MPD 中相邻同色的 1×1 plate/brick 合并为更大的砖/板")
    parser.add_argument("mpd", help="输入 .mpd 文件路径")
    parser.add_argument("-o", "--out", help="输出 .mpd 文件路径（默认：同名 _merged.mpd）")
    parser.add_argument("--max-wh", type=int, default=8, help="允许的最大砖/板尺寸（宽/高）")
    parser.add_argument("--connectivity", type=int, choices=[4, 8], default=4, help="连通性（4 或 8）")
    parser.add_argument("--stability", action="store_true", help="启用下方支撑稳定性检查")
    args = parser.parse_args()

    merge_1x1_to_larger(
        mpd_path=args.mpd,
        out_path=args.out,
        max_wh=args.max_wh,
        connectivity=args.connectivity,
        stability=args.stability,
    )
