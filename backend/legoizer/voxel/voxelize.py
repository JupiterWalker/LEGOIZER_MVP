# legoizer/voxel/voxelize.py
import numpy as np
import trimesh

# LEGO geometry
STUD_MM = 8.0
PLATE_MM = 3.2
BRICK_MM = 9.6

PARTS = {
    'plate_1x1': {'ldraw_id': 3024, 'height_mm': PLATE_MM, 'footprint': (1, 1)},
    'brick_1x1': {'ldraw_id': 3005, 'height_mm': BRICK_MM, 'footprint': (1, 1)},
}

def part_info(part_key: str):
    if part_key not in PARTS:
        raise ValueError(f"Unsupported part '{part_key}'. Supported: {list(PARTS.keys())}")
    return PARTS[part_key]

def mesh_to_voxels(mesh: trimesh.Trimesh, part_key: str):
    """
    将网格体素化为布尔栅格。每个体素的 XY footprint = 1×1 stud，Z 高 = 对应颗粒高度。
    返回:
      - grid: np.ndarray[bool]，形状 (nx, ny, nz)
      - index_to_mm_center: 4x4 仿射矩阵，满足 [i,j,k,1] -> 该体素中心的毫米坐标
    说明:
      - trimesh.voxelized(pitch) 的 transform 已是“索引 -> 体素中心（在当前坐标系）”
      - 我们先把网格在 Z 放缩到“各向同性”，pitch=STUD_MM，然后把中心点再映射回真实毫米坐标
    """
    info = part_info(part_key)
    h = info['height_mm']

    # 各向同性缩放，使 Z 的单位从 h(mm) 拉伸到 STUD_MM(mm)
    s = STUD_MM / h
    S = np.diag([1.0, 1.0, s, 1.0])      # 先将 mesh 缩放到 iso 空间
    Si = np.linalg.inv(S)                # 把 iso 空间坐标还原到真实 mm

    mesh_iso = mesh.copy()
    mesh_iso.apply_transform(S)   # 把原模型 变形

    vox = mesh_iso.voxelized(pitch=STUD_MM)  # iso 空间下的等边体素，单位 mm

    # 这行代码调用了 trimesh的体素对象vox的fill()
    # 方法，将体素网格中被包围的空洞填充，
    # 返回一个“实心”的体素网格（即所有被包围的体素都被标记为填充）。
    # 这样可以确保体素化结果内部没有空洞，适合后续的布尔体素处理。
    filled = vox.fill()

    grid = filled.matrix.astype(bool)
    # filled.transform: [i,j,k,1] -> iso 空间体素中心（单位 mm）
    # 回到真实 mm：Si @ (iso_center)
    index_to_mm_center = Si @ filled.transform

    return grid, index_to_mm_center

def grid_bounds_mm(grid: np.ndarray, index_to_mm_center: np.ndarray):
    """
    用体素中心的变换估算整体包围盒（毫米）。
    注意：中心到角落相差半个体素；此处只做近似边界用于报告。
    """
    nx, ny, nz = grid.shape
    corners_idx = np.array([
        [0,   0,   0,   1],
        [nx-1,0,   0,   1],
        [0,  ny-1, 0,   1],
        [0,   0,  nz-1, 1],
        [nx-1,ny-1,nz-1,1],
    ], dtype=float)
    pts = (index_to_mm_center @ corners_idx.T).T[:, :3]
    mins = pts.min(axis=0)
    maxs = pts.max(axis=0)
    return mins, maxs
