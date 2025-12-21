# legoizer/io/obj_loader.py
import os
import io
import re
import numpy as np
import trimesh
from trimesh import repair

from utils import StageTimer

UNIT_SCALE_MM = {
    "m": 1000.0,
    "cm": 10.0,
    "mm": 1.0,
}

LDU_SIZE = 0.4 # mm

def _drop_nan_inf_inplace(mesh: trimesh.Trimesh) -> None:
    """移除包含 NaN/Inf 顶点的三角面，并清理悬空顶点。"""
    v = mesh.vertices
    if len(v) == 0:
        return
    good_v = np.isfinite(v).all(axis=1)
    if good_v.all():
        return
    good_idx = np.nonzero(good_v)[0]
    keep_face = np.isin(mesh.faces, good_idx).all(axis=1)
    if not keep_face.all():
        mesh.update_faces(keep_face)
        mesh.remove_unreferenced_vertices()

def load_obj(path: str, unit: str = "mm", max_dim_limit: float = 0, mtl: str = None) -> trimesh.Trimesh:
    if unit not in UNIT_SCALE_MM:
        raise ValueError(f"Unsupported unit '{unit}'. Choose from m/cm/mm.")

    # 优先用 resolver 让 trimesh 能找到指定的 .mtl
    with StageTimer("load obj"):
        if mtl and os.path.exists(mtl):
            pass
            # try:
            #     from trimesh.resolvers import FilePathResolver
            #     resolver = FilePathResolver(os.path.dirname(mtl))
            #     mesh = trimesh.load(file_obj=open(path, "rb"), file_type="obj", force="mesh", resolver=resolver)
            # except Exception:
            #     mesh = trimesh.load(path, force="mesh")
        else:
            mesh = trimesh.load(path, force="mesh")

    with StageTimer("process mesh"):
        # 坐标系调整（与项目其余部分一致）：交换 Y/Z，并翻转 Z
        mesh.vertices = mesh.vertices[:, [0, 2, 1]]
        mesh.vertices[:, 2] *= -1

        # 等比缩放到最长边
        if max_dim_limit:
            bbox = mesh.bounding_box.extents
            max_dim = bbox.max()
            if max_dim > 0:
                scale_factor = max_dim_limit / max_dim
                mesh.apply_scale(scale_factor)

        # if scale:
        #     mesh.apply_scale(scale)

        # 如果读到的是 Scene，合并为单一 Trimesh
        if not isinstance(mesh, trimesh.Trimesh):
            mesh = trimesh.util.concatenate(mesh.dump())

        # 统一到毫米
        mesh.apply_scale(UNIT_SCALE_MM[unit])

    with StageTimer("repair mesh"):
        # # 清理 NaN/Inf
        # _drop_nan_inf_inplace(mesh)

        # # 基础几何清理
        # try: mesh.remove_duplicate_faces()
        # except Exception: pass
        # try: mesh.remove_degenerate_faces()
        # except Exception: pass
        # try: mesh.remove_unreferenced_vertices()
        # except Exception: pass

        # # 修复
        # try: repair.fix_normals(mesh)
        # except Exception: pass
        # try: repair.fill_holes(mesh)
        # except Exception: pass
        # try: repair.fix_winding(mesh)
        # except Exception: pass
        # try: repair.fix_inversion(mesh)
        # except Exception: pass

        # try: mesh.process(validate=True)
        # except Exception: pass

        return mesh

# -------- Collada (.dae) --------

def _sanitize_dae_xml(text: str) -> str:
    """
    去除未绑定命名空间的厂商扩展标签（例如 <RoundingEdgeNormal:enable> ... </...> 或自闭合）。
    仅移除带前缀的元素，不触碰标准 Collada 标签。
    """
    # <prefix:name ...>...</prefix:name>
    text = re.sub(r'<([A-Za-z_][\w\-.]*):([A-Za-z_][\w\-.]*)\b[^>]*>.*?</\1:\2\s*>', '', text, flags=re.DOTALL)
    # <prefix:name .../>
    text = re.sub(r'<([A-Za-z_][\w\-.]*):([A-Za-z_][\w\-.]*)\b[^>]*/\s*>', '', text)
    return text
