import trimesh
from pathlib import Path

glb_f = Path(__file__).with_name('base_basic_pbr.glb')
# glb_f = Path(__file__).with_name('base_basic_shaded.glb')
scene_or_mesh = trimesh.load(glb_f)

# 若是场景，可合并为单一网格（按需）
if isinstance(scene_or_mesh, trimesh.Scene):
    mesh = scene_or_mesh.dump(concatenate=True)
else:
    mesh = scene_or_mesh

print('顶点数:', len(mesh.vertices))
print('面数:', len(mesh.faces))

# 快速可视化
mesh.show()