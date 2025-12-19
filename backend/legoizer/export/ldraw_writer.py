# legoizer/export/ldraw_writer.py
from typing import List, Tuple
import numpy as np
import os

# LDraw color: Light Bluish Gray = 71
DEFAULT_COLOR = 71

# LDraw unit: 1 LDU = 0.4 mm
MM_PER_LDU = 0.4

PLATE_MM = 3.2
BRICK_MM = 9.6

PARTS = {
    'plate_1x1': {'ldraw_id': 3024, 'height_mm': PLATE_MM, 'footprint': (1, 1)},
    'brick_1x1': {'ldraw_id': 3005, 'height_mm': BRICK_MM, 'footprint': (1, 1)},
}

def _mm_to_ldu_xyz(xyz_mm):
    """
    我们的几何是 Z 向上；LDraw 以 Y 向上。
    因此映射为：LDraw(X,Y,Z) = (mm_x, mm_z, mm_y) / 0.4
    """
    x, y, z = xyz_mm
    return np.array([x, z, y]) / MM_PER_LDU

def _format_ldraw_color(value, fallback: int) -> str:
    """Render LDraw colour code, respecting true-colour encoding."""
    if value is None:
        return str(fallback)
    if isinstance(value, str):
        return value
    try:
        ival = int(value)
    except (TypeError, ValueError):
        return str(fallback)
    if 0x02000000 <= ival <= 0x02FFFFFF:
        direct_rgb = ival & 0x00FFFFFF
        return f"0x2{direct_rgb:06X}"
    return str(ival)


def write_mpd(out_path: str,
              part_key: str,
              placements: List[Tuple[int,int,int]],
              index_to_mm_center: np.ndarray,
              colors: list = None,
              default_color: int = DEFAULT_COLOR):
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    info = PARTS[part_key]
    ldraw_id = info['ldraw_id']

    lines = []
    # 主模型（唯一 FILE 段）
    lines.append('0 FILE model.ldr')
    lines.append('0 Name: model.ldr')
    lines.append('0 Author: legoizer-mvp')
    lines.append('0 !LDRAW_ORG Unofficial_Model')
    lines.append('0 ROTATION CENTER 0 0 0 1 "Custom"')
    lines.append('0 ROTATION CONFIG 0 0')

    # 逐颗零件（位置为体素中心；旋转为单位阵）
    for idx, (i, j, k) in enumerate(placements):
        #这一行代码的作用是： 将体素索引 ([i, j, k]) 转换为以毫米为单位的三维空间坐标。  
        # 具体过程如下：  np.array([i, j, k, 1.0]) 构造一个齐次坐标（4维向量）。
        # index_to_mm_center @ ... 
        # 用 4x4 变换矩阵 index_to_mm_center 对索引进行仿射变换，
        # 得到实际的空间坐标（单位为毫米）。[:3] 取前三个分量，
        # 得到 (x, y, z) 三维坐标。
        # 简言之，这一步是把体素的索引位置变换为实际的三维空间中心点坐标
        center_mm = (index_to_mm_center @ np.array([i, j, k, 1.0]))[:3]  
        pos_ldu = _mm_to_ldu_xyz(center_mm)

        # LDraw line type 1: 1 COLOR x y z a b c d e f g h i part.dat
        a,b,c,d,e,f,g,h,i_m = 1,0,0, 0,1,0, 0,0,1
        colour_code = None
        if colors is not None and idx < len(colors):
            colour_code = colors[idx]
        lines.append(
            f"1 {_format_ldraw_color(colour_code, default_color)} "
            f"{pos_ldu[0]:.3f} {pos_ldu[1]:.3f} {pos_ldu[2]:.3f} "
            f"{a} {b} {c} {d} {e} {f} {g} {h} {i_m} "
            f"{ldraw_id}.dat"
        )

    lines.append('0 NOFILE')

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))