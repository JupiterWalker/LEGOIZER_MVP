import numpy as np
import trimesh

from backend.utils import StageTimer
from .obj_loader import UNIT_SCALE_MM


def _ensure_trimesh(mesh: trimesh.base.Trimesh | trimesh.Scene) -> trimesh.Trimesh:
    """Convert trimesh Scene collections into a single Trimesh mesh."""
    if isinstance(mesh, trimesh.Trimesh):
        return mesh
    if isinstance(mesh, trimesh.Scene):
        dumped = mesh.dump(concatenate=True)
        if isinstance(dumped, trimesh.Trimesh):
            return dumped
        mesh = dumped
    if hasattr(mesh, "dump"):
        meshes = mesh.dump()
        if isinstance(meshes, (list, tuple)):
            return trimesh.util.concatenate(meshes)
    raise TypeError("Unsupported mesh type returned from trimesh.load")


def _axis_align(mesh: trimesh.Trimesh) -> None:
    """Reorient mesh to match legacy OBJ pipeline expectations."""
    v = mesh.vertices
    if v.shape[1] < 3:
        raise ValueError("Mesh vertices must be 3D")
    mesh.vertices = v[:, [0, 2, 1]]
    mesh.vertices[:, 2] *= -1.0


def load_gltf(path: str,
              *,
              unit: str = "mm",
              max_dim_limit: float = 0.0) -> trimesh.Trimesh:
    if unit not in UNIT_SCALE_MM:
        raise ValueError(f"Unsupported unit '{unit}'. Choose from m/cm/mm.")

    with StageTimer("load gltf"):
        mesh = trimesh.load(path, force="mesh")

    with StageTimer("process mesh"):
        mesh = _ensure_trimesh(mesh)

        # Align coordinate system to match downstream assumptions.
        _axis_align(mesh)

        if max_dim_limit:
            bbox = mesh.bounding_box.extents
            max_dim = float(np.max(bbox)) if bbox.size else 0.0
            if max_dim > 0.0:
                mesh.apply_scale(max_dim_limit / max_dim)

        mesh.apply_scale(UNIT_SCALE_MM[unit])

    return mesh
