# legoizer/cli.py
import argparse
from pathlib import Path

from legoizer.pipeline import generate_mpd_report

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
    result = generate_mpd_report(
        Path(args.input),
        Path(args.out),
        unit=args.unit,
        part=args.part,
        max_dim_limit=float(args.max_dim_limit),
        mtl_path=Path(args.mtl) if args.mtl else None,
        default_color=args.default_color,
        color_mode="none",
        surface_thickness_mm=args.surface_thickness_mm,
    )

    print(f"Wrote {result['mpd_path']} and {result['report_path']}")

if __name__ == '__main__':
    main()
