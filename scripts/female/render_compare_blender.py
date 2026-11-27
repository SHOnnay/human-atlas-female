"""Blender side of compare_renders.py: identical orthographic cameras for male and female."""
import json
import sys
from pathlib import Path

import bmesh  # noqa: F401
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
jobs = json.loads(Path(argv[0]).read_text())
root = Path(argv[1])
COLORS = {'skeletal': (0.89, 0.85, 0.73), 'muscular': (0.66, 0.36, 0.31), 'reproductive': (0.86, 0.45, 0.62),
          'urinary': (0.95, 0.75, 0.2), 'digestive': (0.72, 0.57, 0.42), 'integumentary': (0.86, 0.72, 0.62),
          'connective': (0.93, 0.83, 0.62), 'arterial': (0.8, 0.25, 0.22), 'venous': (0.32, 0.47, 0.67),
          'nervous': (0.85, 0.7, 0.4), 'cardiac': (0.73, 0.4, 0.38), 'respiratory': (0.73, 0.54, 0.57),
          'lymphatic': (0.53, 0.62, 0.49), 'endocrine': (0.77, 0.63, 0.6), 'sensory': (0.69, 0.78, 0.81),
          'adipose': (1.0, 0.94, 0.62), 'subcutaneous': (0.94, 0.85, 0.56), 'erectile': (0.43, 0.18, 0.42),
          'mammary': (0.96, 0.85, 0.84), 'lactiferous': (0.72, 0.16, 0.36)}
ALPHA = {}
# Atlas (x, y-up, z-anterior) -> Blender (x, -z, y): Blender is Z-up, anterior = -Y.
def B(p):
    return Vector((p[0], -p[2], p[1]))


DIRS = {'front': Vector((0, -1, 0)), 'back': Vector((0, 1, 0)), 'side': Vector((1, 0, 0)),
        'oblique': Vector((0.75, -1, 0.15)).normalized(), 'below': Vector((0, -0.35, -1)).normalized(),
        'palm': Vector((-1, -0.25, 0)).normalized(), 'dorsum': Vector((1, 0.25, 0)).normalized()}


def load_obj(path):
    verts, faces = [], []
    with open(path) as f:
        for line in f:
            if line.startswith('v '):
                verts.append(tuple(B([float(x) for x in line.split()[1:4]])))
            elif line.startswith('f '):
                faces.append(tuple(int(s) - 1 for s in line.split()[1:4]))
    mesh = bpy.data.meshes.new(path.stem)
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new(path.stem, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.new(path.stem)
    mat.diffuse_color = (*COLORS.get(path.stem, (0.7, 0.7, 0.7)), ALPHA.get(path.stem, 1.0))
    mesh.materials.append(mat)
    return obj


DIRS['palm_r'] = Vector((1, -0.25, 0)).normalized(); DIRS['dorsum_r'] = Vector((-1, 0.25, 0)).normalized()


def frame(lo_, hi_):
    a, b = B(lo_), B(hi_)
    lo = Vector((min(a[i], b[i]) for i in range(3))); hi = Vector((max(a[i], b[i]) for i in range(3)))
    return (lo + hi) / 2, max(hi - lo)


for job in jobs:
    for body in ('male', 'female'):
        # milestone 7: each body framed on its OWN geometry, so both fill their half equally
        fr = job.get('frames', {}).get(body)
        centre, size = frame(*fr) if fr else frame(job['lo'], job['hi'])
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        ALPHA.clear(); ALPHA.update({'adipose': 0.35, 'subcutaneous': 0.35}); ALPHA.update(job.get('alpha', {}))   # female fat 35 % in every view (male has no fat parts)
        d = root / body / job['cat']
        for f in (sorted(d.glob('*.obj')) if d.exists() else []):
            load_obj(f)
        world = bpy.data.worlds.new('w'); world.color = (0.93, 0.94, 0.95); scene.world = world
        scene.render.engine = 'BLENDER_WORKBENCH'
        scene.display.shading.light = 'STUDIO'
        scene.display.shading.color_type = 'MATERIAL'
        scene.display.shading.background_type = 'WORLD'
        scene.display.shading.show_cavity = True
        scene.render.resolution_x, scene.render.resolution_y = 700, 900
        cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
        scene.collection.objects.link(cam); scene.camera = cam
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = size * 1.08
        cam.data.clip_end = size * 20
        for v in job['views']:
            d = DIRS[v]
            vf = job.get('view_frames', {}).get(body, {}).get(v)
            if vf:                      # per-view hand framing (projected hand bones)
                centre = Vector(B(vf[0])); size = vf[1]
                cam.data.ortho_scale = size * 1.08; cam.data.clip_end = size * 20
            cam.location = centre + d * size * 4
            cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = str(root / f"{body}_{job['cat']}_{v}.png")
            bpy.ops.render.render(write_still=True)
print('done')
