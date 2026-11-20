"""Developer aid: render OBJs from work/female/debug (or another folder) with Blender Workbench.

blender -b -P scripts/female/render_debug.py -- IN_DIR OUT_PREFIX [include-regex] [exclude-regex] [views]
Files named <prefix>_<system>_<id>.obj are coloured by system. views: front,side,top,below,oblique
"""
import math
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
src, out = Path(argv[0]), argv[1]
pattern = argv[2] if len(argv) > 2 else ''
if pattern.startswith('@'):
    pattern = Path(pattern[1:]).read_text().strip()
inc = re.compile(pattern) if pattern else None
exc = re.compile(argv[3]) if len(argv) > 3 and argv[3] else None
views = (argv[4] if len(argv) > 4 else 'front,side,oblique').split(',')
COLORS = {'skeletal': (0.89, 0.85, 0.73), 'muscular': (0.66, 0.36, 0.31), 'reproductive': (0.86, 0.45, 0.62),
          'urinary': (0.95, 0.75, 0.2), 'digestive': (0.62, 0.5, 0.36), 'integumentary': (0.75, 0.6, 0.5),
          'connective': (0.55, 0.75, 0.7), 'arterial': (0.8, 0.2, 0.2), 'venous': (0.25, 0.4, 0.75),
          'generated': (0.2, 0.75, 0.95), 'nervous': (0.85, 0.7, 0.3)}
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
objs = []
for f in sorted(src.glob('*.obj')):
    if (inc and not inc.search(f.name)) or (exc and exc.search(f.name)):
        continue
    bpy.ops.wm.obj_import(filepath=str(f))
    o = bpy.context.selected_objects[0]
    system = f.stem.split('_')[1]
    if f.stem.startswith('g_'):
        system = 'generated'
    mat = bpy.data.materials.new(f.stem)
    c = COLORS.get(system, (0.7, 0.7, 0.7))
    mat.diffuse_color = (*c, 0.25 if system == 'integumentary' else 1.0)
    o.data.materials.append(mat)
    objs.append(o)
bpy.context.view_layer.update()
corners = [o.matrix_world @ Vector(v) for o in objs for v in o.bound_box]
lo = Vector((min(c[i] for c in corners) for i in range(3)))
hi = Vector((max(c[i] for c in corners) for i in range(3)))
world = bpy.data.worlds.new('w'); world.color = (0.55, 0.57, 0.6); scene.world = world
scene.display.shading.background_type = 'WORLD'
centre, size = (lo + hi) / 2, max(hi - lo)
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_xray = False
scene.render.resolution_x = scene.render.resolution_y = 900
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.type = 'ORTHO'
cam.data.ortho_scale = size * 1.1
# Blender is Z-up after OBJ import: atlas +z (anterior) → Blender -y, atlas +y (up) → Blender +z.
dirs = {'front': Vector((0, -1, 0)), 'back': Vector((0, 1, 0)), 'side': Vector((1, 0, 0)), 'top': Vector((0, 0, 1)),
        'below': Vector((0, -0.25, -1)), 'oblique': Vector((0.7, -1, 0.35))}
for v in views:
    d = dirs[v].normalized()
    cam.location = centre + d * size * 3
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y' if v not in ('top', 'below') else 'Y').to_euler()
    cam.data.clip_end = size * 10
    scene.render.filepath = f'{out}_{v}.png'
    bpy.ops.render.render(write_still=True)
print('rendered', len(objs), 'objects')
