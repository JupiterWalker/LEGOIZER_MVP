# legoizer/cli.py
import argparse
import os
from legoizer.io.obj_loader import load_obj, load_collada
from legoizer.voxel.voxelize import mesh_to_voxels, part_info, grid_bounds_mm
from legoizer.planner.tiler import tile_single_part_1x1, compute_stats_1x1
from legoizer.export.ldraw_writer import write_mpd
from legoizer.planner.colorize import colorize_voxels
from legoizer.reporting.summary import Report

def parse_args():
    """
    解析命令行参数，指定输入文件（.obj 或 .dae）、单位、零件类型和输出路径。
    """
    p = argparse.ArgumentParser(description='OBJ/DAE -> LDraw MPD with coloring options')
    p.add_argument('--input', required=True, help='Path to OBJ (.obj) or Collada (.dae) file')
    p.add_argument('--unit', default='mm', choices=['m','cm','mm'], help='Unit of the source model')
    p.add_argument('--max_dim_limit', default=100, help='Brick max unit(mm) of the longest direction')
    p.add_argument('--scale', default=1, help='scale from original 3D model')
    p.add_argument('--part', required=True, choices=['plate_1x1','brick_1x1'], help='Single part to use')
    p.add_argument('--out', required=True, help='Output MPD path')
    # 上色相关
    p.add_argument('--mtl', default=None, help='Path to MTL file (for OBJ; ignored for DAE)')
    p.add_argument('--default_color', type=int, default=71,
                   help='Default LDraw color for missing/inside voxels')

    p.add_argument('--surface_thickness_mm', type=float, default=None,
                   help='(Reserved) Surface thickness in mm; not required for current surface detection')
    return p.parse_args()

def main():
    args = parse_args()

    # 1) 载入网格
    mesh = load_obj(args.input, unit=args.unit,
                        max_dim_limit=float(args.max_dim_limit),
                        scale=int(args.scale), mtl=args.mtl)

    # 2) 体素化
    grid, index_to_mm_center = mesh_to_voxels(mesh, part_key=args.part)

    # 3) 铺砖
    placements = tile_single_part_1x1(grid)

    # 4) 统计
    stats = compute_stats_1x1(placements)
    report = Report(part=args.part, count=stats['count']).to_dict()

    # 5) 上色（默认只表层上色）

    # 6) 导出 MPD + 报告
    report_path = write_mpd(args.out, args.part, placements, index_to_mm_center,
                            report, colors=None, default_color=args.default_color)

    # 7) 计算毫米包围盒尺寸并补写报告
    mins, maxs = grid_bounds_mm(grid, index_to_mm_center)
    dims = (maxs - mins).tolist()

    import json
    with open(report_path, 'r') as f:
        data = json.load(f)
    data['dims_mm_xyz'] = [round(x,3) for x in dims]
    data['voxels'] = int(grid.sum())
    with open(report_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {args.out} and {report_path}")

if __name__ == '__main__':
    main()
