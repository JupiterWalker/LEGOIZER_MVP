from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Dict

from .utils import StageTimer

from .legoizer.export.ldraw_writer import write_mpd
from .legoizer.io.obj_loader import load_obj
from .legoizer.io.gltf_loader import load_gltf
from .legoizer.planner.colorize import colorize_voxels
from .legoizer.planner.tiler import tile_single_part_1x1, compute_stats_1x1
from .legoizer.reporting.summary import Report
from .legoizer.voxel.voxelize import mesh_to_voxels, grid_bounds_mm


def generate_mpd_report(
    input_path: Path,
    output_path: Path,
    *,
    unit: str = "mm",
    part: str = "plate_1x1",
    max_dim_limit: float = 100.0,
    mtl_path: Optional[Path] = None,
    default_color: int = 71,
    color_mode: str = "auto",
    surface_thickness_mm: Optional[float] = None,
) -> Dict[str, object]:
    """Run the legacy CLI pipeline and return metadata about the generated artefacts."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with StageTimer("load mesh"):
        mesh = _load_mesh(input_path, unit, max_dim_limit, mtl_path)

    with StageTimer("mesh to voxels"):
        grid, index_to_mm_center = mesh_to_voxels(mesh, part_key=part)
    
    with StageTimer("tile single part 1x1"):
        placements = tile_single_part_1x1(grid)

    stats = compute_stats_1x1(placements)
    report_payload = Report(part=part, count=stats["count"]).to_dict()

    colors = None
    effective_mode = (color_mode or "none").lower()
    if effective_mode == "auto":
        vis = getattr(mesh, "visual", None)
        has_texture = bool(getattr(vis, "kind", None) == "texture" and getattr(vis, "uv", None) is not None)
        has_material = False
        if vis is not None:
            mats = getattr(vis, "materials", None)
            if mats:
                has_material = True
            elif getattr(vis, "material", None) is not None:
                has_material = True
            elif getattr(vis, "vertex_colors", None) is not None:
                has_material = True
        effective_mode = "mtl_texture_surface_only" if has_texture else ("mtl_surface_only" if has_material else "none")

    if effective_mode != "none":
        colors = colorize_voxels(
            mesh,
            placements,
            index_to_mm_center,
            grid,
            mode=effective_mode,
            surface_thickness_mm=surface_thickness_mm,
            default_color=default_color,
        )

    with StageTimer("write mpd"):
        write_mpd(
            str(output_path),
            part,
            placements,
            index_to_mm_center,
            report_payload,
            colors=colors,
            default_color=default_color,
        )

    return {
        "mpd_path": str(output_path),
    }


def _load_mesh(input_path: Path,
               unit: str,
               max_dim_limit: float,
               mtl_path: Optional[Path]) -> "trimesh.Trimesh":
    """Pick the appropriate loader based on file extension."""
    suffix = input_path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        return load_gltf(str(input_path), unit=unit, max_dim_limit=max_dim_limit)
    return load_obj(str(input_path), unit=unit, max_dim_limit=max_dim_limit, mtl=str(mtl_path) if mtl_path else None)
