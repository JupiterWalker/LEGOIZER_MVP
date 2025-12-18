# legoizer/color/colorize.py
from typing import List, Tuple, Optional
import numpy as np
import trimesh

# 可选依赖（纹理采样需要 PIL；KDTree 回退需要 scipy）
try:
    from PIL import Image
except Exception:
    Image = None

try:
    from scipy.spatial import cKDTree
except Exception:
    cKDTree = None


# -------------------- 基础工具 --------------------

def _to_u8_rgb(arr: np.ndarray) -> np.ndarray:
    """确保返回 uint8 的 RGB（0..255）。"""
    arr = np.asarray(arr)
    if arr.ndim == 1:
        arr = arr[None, :]
    arr = arr[:, :3]
    if arr.dtype == np.uint8:
        return arr
    arr = arr.astype(np.float32)
    if np.nanmax(arr) <= 1.0:
        arr = arr * 255.0
    arr = np.clip(arr, 0.0, 255.0).astype(np.uint8)
    return arr

def _rgb_to_ldraw_direct(rgb_u8: np.ndarray) -> np.ndarray:
    """Nx3 uint8 RGB -> LDraw 直色 0x02RRGGBB（int）。"""
    rgb_u8 = rgb_u8.astype(np.uint32)
    return (0x02000000 | (rgb_u8[:,0] << 16) | (rgb_u8[:,1] << 8) | rgb_u8[:,2]).astype(np.uint32)

def _index_to_mm_points(index_to_mm_center: np.ndarray, ijk_list: List[Tuple[int,int,int]]) -> np.ndarray:
    """体素索引(i,j,k) -> 世界毫米坐标（4x4 矩阵）"""
    if len(ijk_list) == 0:
        return np.zeros((0,3), dtype=float)
    idx = np.array(ijk_list, dtype=float)
    ones = np.ones((idx.shape[0], 1), dtype=float)
    homo = np.hstack([idx, ones])
    pts = (index_to_mm_center @ homo.T).T[:, :3]
    return pts

def _is_surface_mask_from_grid(grid: np.ndarray, placements: List[Tuple[int,int,int]]) -> np.ndarray:
    """6 邻域触边/空则认为是表层体素。"""
    nx, ny, nz = grid.shape
    surf = []
    for (i,j,k) in placements:
        is_surface = False
        for di,dj,dk in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            ii, jj, kk = i+di, j+dj, k+dk
            if ii<0 or jj<0 or kk<0 or ii>=nx or jj>=ny or kk>=nz or not grid[ii,jj,kk]:
                is_surface = True
                break
        surf.append(is_surface)
    return np.array(surf, dtype=bool)


# -------------------- 材质颜色（非纹理） --------------------

def _pbr_material_color(mat) -> Optional[np.ndarray]:
    """
    从 PBRMaterial 提取 RGB：
      1) to_color()（常返回 uint8 RGBA）
      2) main_color
      3) baseColorFactor / base_color_factor
      4) diffuse / ambient / specular / color
    """
    if mat is None:
        return None

    try:
        if hasattr(mat, "to_color"):
            col = mat.to_color()
            if col is not None:
                col = np.asarray(col)
                if col.ndim == 1:
                    col = col[:3]
                else:
                    col = col[0, :3]
                return _to_u8_rgb(col)[0]
    except Exception:
        pass

    try:
        if hasattr(mat, "main_color"):
            col = getattr(mat, "main_color")
            if col is not None:
                return _to_u8_rgb(np.array(col))[0]
    except Exception:
        pass

    for attr in ("baseColorFactor", "base_color_factor"):
        if hasattr(mat, attr):
            col = getattr(mat, attr)
            if col is not None:
                return _to_u8_rgb(np.array(col))[0]

    for attr in ("diffuse", "ambient", "specular", "color"):
        if hasattr(mat, attr):
            col = getattr(mat, attr)
            if col is not None:
                return _to_u8_rgb(np.array(col))[0]

    return None

def _get_face_colors(mesh: trimesh.Trimesh) -> Optional[np.ndarray]:
    """
    推导逐面 RGB：
      1) visual.face_colors
      2) face_materials + materials[*]
      3) vertex_colors -> 面均值
      4) TextureVisuals.material（PBR）→单色广播
    返回 (F,3) uint8 或 None。
    """
    vis = getattr(mesh, 'visual', None)
    F = len(getattr(mesh, 'faces', []))
    if vis is None or F == 0:
        return None

    fc = getattr(vis, 'face_colors', None)
    if isinstance(fc, np.ndarray) and fc.shape[0] == F:
        return _to_u8_rgb(fc)

    fm = getattr(vis, 'face_materials', None)
    mats = getattr(vis, 'materials', None)
    if fm is not None and mats is not None and len(mats) > 0:
        mat_rgbs = []
        for m in mats:
            rgb = _pbr_material_color(m)
            if rgb is None:
                rgb = np.array([204, 204, 204], dtype=np.uint8)
            mat_rgbs.append(rgb)
        mat_rgbs = np.vstack(mat_rgbs).astype(np.uint8)
        idx = np.asarray(fm, dtype=int)
        idx = np.where((idx >= 0) & (idx < len(mat_rgbs)), idx, 0)
        return mat_rgbs[idx]

    vc = getattr(vis, 'vertex_colors', None)
    if isinstance(vc, np.ndarray) and vc.shape[0] == len(getattr(mesh, 'vertices', [])):
        vc_u8 = _to_u8_rgb(vc)
        f = mesh.faces.astype(int)
        per_face = vc_u8[f][:, :, :3].astype(np.float32).mean(axis=1)
        return per_face.astype(np.uint8)

    if hasattr(vis, "material"):
        rgb = _pbr_material_color(getattr(vis, "material", None))
        if rgb is not None:
            return np.tile(rgb[None, :], (F, 1))

    return None

def _get_global_color(mesh: trimesh.Trimesh) -> Optional[np.ndarray]:
    """整网单材质时返回一个 RGB。"""
    vis = getattr(mesh, 'visual', None)
    if vis is None:
        return None
    if hasattr(vis, "material"):
        rgb = _pbr_material_color(getattr(vis, "material", None))
        if rgb is not None:
            return rgb
    mats = getattr(vis, 'materials', None)
    if mats and len(mats) == 1:
        rgb = _pbr_material_color(mats[0])
        if rgb is not None:
            return rgb
    return None


# -------------------- 最近三角形（rtree 缺失回退） --------------------

def _nearest_triangle_indices(mesh: trimesh.Trimesh, pts: np.ndarray) -> np.ndarray:
    """
    返回每个点最近的三角形索引。
    优先用 trimesh.proximity.closest_point（需要 rtree）；
    否则回退到 KDTree（三角形中心近似）。
    """
    # 优先精确方法
    try:
        import rtree  # noqa: F401
        closest = trimesh.proximity.closest_point(mesh, pts)
        tri_idx = closest[2].astype(np.int64)
        tri_idx = np.clip(tri_idx, 0, len(mesh.faces)-1)
        return tri_idx
    except Exception:
        pass

    # 回退：KDTree 最近三角形中心
    if cKDTree is None:
        raise RuntimeError(
            "最近三角形查询需要安装 rtree 或 scipy。请安装其中之一：\n"
            "  pip install rtree\n"
            "或 pip install scipy"
        )
    centers = mesh.triangles_center
    tree = cKDTree(centers)
    _, tri_idx = tree.query(pts, k=1)
    return tri_idx.astype(np.int64)


# -------------------- 纹理采样 --------------------

def _get_basecolor_image_from_visual(vis) -> Optional[np.ndarray]:
    """
    从 TextureVisuals 的 PBRMaterial.baseColorTexture 解析纹理图像。
    返回 numpy uint8 的 (H, W, 3)；如果无法解析则返回 None。
    """
    if vis is None or getattr(vis, "kind", None) != "texture":
        return None
    mat = getattr(vis, "material", None)
    if mat is None:
        return None

    # 直接拿到 image（trimesh 内部常用）
    tex = getattr(mat, "baseColorTexture", None)
    img = None
    if tex is not None:
        if isinstance(tex, np.ndarray):
            img = tex
        elif Image is not None and hasattr(tex, "mode") and hasattr(tex, "size"):
            # tex may already be a PIL Image when loaded from GLB
            try:
                img = np.array(tex.convert("RGBA"))
            except Exception:
                img = None
        else:
        # 1) 直接 image / images
            for key in ("image", "images"):
                if hasattr(tex, key):
                    v = getattr(tex, key)
                    if v is None:
                        continue
                    if isinstance(v, (list, tuple)) and len(v) > 0:
                        v = v[0]
                    try:
                        if Image is not None and hasattr(v, "mode"):
                            img = np.array(v.convert("RGBA"), dtype=np.uint8)
                        else:
                            arr = np.asarray(v)
                            if arr.ndim >= 2:
                                img = arr
                    except Exception:
                        pass
                    if img is not None:
                        break
            # 2) 路径（少见）
            if img is None:
                for key in ("image_path", "source", "path"):
                    if hasattr(tex, key):
                        p = getattr(tex, key)
                        if p:
                            if Image is None:
                                raise RuntimeError("需要 Pillow 才能从纹理路径读取图像：pip install pillow")
                            try:
                                img = np.array(Image.open(p).convert("RGBA"))
                                break
                            except Exception:
                                pass

    if img is None:
        return None

    # 去掉 alpha（先不做与背景颜色混合）
    if img.shape[-1] == 4:
        img = img[:, :, :3]
    elif img.shape[-1] > 3:
        img = img[:, :, :3]
    return img.astype(np.uint8)


def _sample_texture_rgb(img: np.ndarray, uv: np.ndarray) -> np.ndarray:
    """
    最近邻采样纹理：img(H,W,3)；uv(N,2) in [0,1].
    注意：V 轴翻转（v = 1 - v）。
    """
    if img is None:
        raise ValueError("纹理图像为空")
    H, W = img.shape[:2]
    u = np.clip(uv[:, 0], 0.0, 1.0)
    v = 1.0 - np.clip(uv[:, 1], 0.0, 1.0)  # flip V
    x = np.clip((u * (W - 1)).round().astype(int), 0, W - 1)
    y = np.clip((v * (H - 1)).round().astype(int), 0, H - 1)
    rgb = img[y, x, :3]
    return rgb.astype(np.uint8)


# -------------------- 主流程 --------------------

def colorize_voxels(mesh: trimesh.Trimesh,
                    placements: List[Tuple[int,int,int]],
                    index_to_mm_center: np.ndarray,
                    grid: np.ndarray,
                    mode: str = 'mtl_surface_only',
                    surface_thickness_mm: Optional[float] = None,
                    default_color: int = 71) -> List[int]:
    """
    返回与 placements 对齐的 LDraw 直色列表。
    支持模式：
      - 'mtl_surface_only'：仅表层按纯色材质上色，内部默认色
      - 'mtl_nearest'：所有体素按纯色材质上色
      - 'mtl_texture_surface_only'：仅表层按纹理采样上色，内部默认色
      - 'mtl_texture'：所有体素按纹理采样上色
      - 'none'：返回空列表
    """
    if mode == 'none' or len(placements) == 0:
        return []

    vis = getattr(mesh, 'visual', None)
    want_texture = mode in ('mtl_texture_surface_only', 'mtl_texture')

    # 纹理路径
    if want_texture:
        if Image is None:
            raise RuntimeError("需要安装 Pillow 才能进行纹理采样：pip install pillow")
        tex_img = _get_basecolor_image_from_visual(vis)
    else:
        tex_img = None

    # 决定哪些体素需要上色
    if mode in ('mtl_surface_only', 'mtl_texture_surface_only'):
        surface_mask = _is_surface_mask_from_grid(grid, placements)
    else:
        surface_mask = np.ones(len(placements), dtype=bool)

    colors_out = np.full(len(placements), default_color, dtype=np.uint32)
    sel_indices = np.nonzero(surface_mask)[0]
    if sel_indices.size == 0:
        return colors_out.tolist()

    batch = 50000

    if want_texture and tex_img is not None and hasattr(vis, "uv") and vis.uv is not None:
        # ---------- 纹理采样路径 ----------
        faces = mesh.faces.astype(int)
        uv_all = np.asarray(vis.uv)  # (V,2)
        tris = mesh.triangles  # (F,3,3)

        for s in range(0, sel_indices.size, batch):
            e = min(s + batch, sel_indices.size)
            idx_batch = sel_indices[s:e]

            pts = _index_to_mm_points(index_to_mm_center, [placements[i] for i in idx_batch])
            tri_idx = _nearest_triangle_indices(mesh, pts)

            # 重心坐标 -> UV 插值
            tris_sel = tris[tri_idx]                         # (N,3,3)
            bary = trimesh.triangles.points_to_barycentric(tris_sel, pts)  # (N,3)
            uv_face = uv_all[faces[tri_idx]]                # (N,3,2)
            uv = (bary[..., None] * uv_face).sum(axis=1)    # (N,2)

            rgb = _sample_texture_rgb(tex_img, uv)          # (N,3)
            colors = _rgb_to_ldraw_direct(rgb)
            colors_out[idx_batch] = colors

        return colors_out.tolist()

    # ---------- 非纹理：纯色材质路径 ----------
    face_colors = _get_face_colors(mesh)
    if face_colors is None:
        g = _get_global_color(mesh)
        if g is not None:
            gl = int(0x02000000 | (int(g[0]) << 16) | (int(g[1]) << 8) | int(g[2]))
            colors_out[sel_indices] = gl
            return colors_out.tolist()
        return colors_out.tolist()

    for s in range(0, sel_indices.size, batch):
        e = min(s + batch, sel_indices.size)
        idx_batch = sel_indices[s:e]
        pts = _index_to_mm_points(index_to_mm_center, [placements[i] for i in idx_batch])
        tri_idx = _nearest_triangle_indices(mesh, pts)
        rgb = face_colors[tri_idx]
        colors = _rgb_to_ldraw_direct(rgb)
        colors_out[idx_batch] = colors

    return colors_out.tolist()
