# legoizer/planner/tiler.py
import numpy as np
from typing import List, Tuple, Dict

def tile_single_part_1x1(grid: np.ndarray) -> List[Tuple[int,int,int]]:
    """
    返回所有需要放置 1×1 颗粒的体素索引 (i,j,k)，一一对应 True 单元。
    """
    xs, ys, zs = np.where(grid)
    return list(zip(xs.tolist(), ys.tolist(), zs.tolist()))

def compute_stats_1x1(placements) -> Dict[str, int]:
    return {
        'count': len(placements)
    }
