"""Shared helpers for scripts/female/create_*.py (run inside Blender 4.2: blender -b -P).

Every create script is called as:
    blender -b --factory-startup -P scripts/female/create_X.py -- LANDMARKS.json OUT_DIR
LANDMARKS.json is written by build_female.py and holds points in atlas space (metres, Y-up,
+x = body left, +z = anterior), plus `skin_patch` (path to an OBJ of the perineal skin).
Geometry is built directly in atlas coordinates with bmesh, smoothed, remeshed, decimated,
and written as plain OBJ (no axis conversion). Dimensions and their literature sources are
listed in DATA_SOURCES.md ("Generated structures").
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def args():
    argv = sys.argv[sys.argv.index('--') + 1:]
    lm = json.loads(Path(argv[0]).read_text())
    out = Path(argv[1]); out.mkdir(parents=True, exist_ok=True)
    return {k: (Vector(v) if isinstance(v, list) and len(v) == 3 and not isinstance(v[0], list) else v) for k, v in lm.items()}, out


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def V(p):
    return Vector(p)


def frame(lm):
    """Local vulva frame: ap (toward the clitoris), n (outward skin normal), lr (body left)."""
    ap = (V(lm['glans_site']) - V(lm['introitus'])).normalized()
    n = V(lm['vulva_normal']).normalized()
    n = (n - ap * n.dot(ap)).normalized()
    lr = ap.cross(n).normalized()
    if lr.x < 0:
        lr = -lr
    return ap, n, lr


def bezier(points, samples=24):
    """Catmull-Rom through points → list of Vectors."""
    pts = [V(p) for p in points]
    pts = [pts[0] + (pts[0] - pts[1])] + pts + [pts[-1] + (pts[-1] - pts[-2])]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for k in range(samples):
            t = k / samples
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-2])
    return out


def tube(name, path, radii, segments=16, scale_lr=1.0, lr_axis=None, arc=None, ref_dir=None):
    """Swept tube along `path` with per-sample radius (list or callable t→r), closed with caps.

    `arc` = (start, end) radians builds an open partial sleeve instead (for muscles over bulbs);
    angle 0 points along `ref_dir` (projected perpendicular to the path).
    """
    bm = bmesh.new()
    rings = []
    n = len(path)
    prev_normal = None
    for i, p in enumerate(path):
        t = i / (n - 1)
        tangent = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        default = V(ref_dir) if ref_dir is not None else (Vector((0, 1, 0)) if abs(tangent.y) < 0.9 else Vector((1, 0, 0)))
        ref = prev_normal if prev_normal is not None else default
        normal = (ref - tangent * ref.dot(tangent)).normalized()
        prev_normal = normal
        binormal = tangent.cross(normal)
        r = radii(t) if callable(radii) else radii[i]
        ring = []
        steps = segments if arc is None else segments + 1
        for k in range(steps):
            a = (2 * math.pi * k / segments) if arc is None else arc[0] + (arc[1] - arc[0]) * k / segments
            off = normal * math.cos(a) + binormal * math.sin(a)
            if lr_axis is not None:
                off = off + V(lr_axis) * off.dot(V(lr_axis)) * (scale_lr - 1)
            ring.append(bm.verts.new(p + off * max(r, 1e-4)))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        m = len(a)
        for k in range(m if arc is None else m - 1):
            bm.faces.new((a[k], a[(k + 1) % m], b[(k + 1) % m], b[k]))
    if arc is None:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    return finish(name, bm)


def ellipsoid(name, centre, axes, radii, subdiv=3):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    ax = [V(a).normalized() for a in axes]
    for v in bm.verts:
        c = v.co.copy()
        v.co = V(centre) + ax[0] * c.x * radii[0] + ax[1] * c.y * radii[1] + ax[2] * c.z * radii[2]
    return finish(name, bm)


def finish(name, bm):
    mesh = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def polish(obj, voxel=0.0012, smooth=4, ratio=None, solidify=None):
    """Remesh → smooth → decimate, matching the atlas's density (~1 vertex / 1.5 mm)."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    if solidify:
        m = obj.modifiers.new('solid', 'SOLIDIFY'); m.thickness = solidify; m.offset = 0
        bpy.ops.object.modifier_apply(modifier=m.name)
    m = obj.modifiers.new('remesh', 'REMESH'); m.mode = 'VOXEL'; m.voxel_size = voxel
    bpy.ops.object.modifier_apply(modifier=m.name)
    if smooth:
        m = obj.modifiers.new('smooth', 'CORRECTIVE_SMOOTH'); m.iterations = smooth; m.smooth_type = 'LENGTH_WEIGHTED'
        m.use_only_smooth = True
        bpy.ops.object.modifier_apply(modifier=m.name)
    m = obj.modifiers.new('dec', 'DECIMATE'); m.ratio = ratio or 0.35
    bpy.ops.object.modifier_apply(modifier=m.name)
    obj.select_set(False)
    return obj


def skin_bvh(lm):
    """BVH of the perineal skin patch (OBJ written by build_female.py, atlas coordinates)."""
    verts, faces = [], []
    for line in Path(lm['skin_patch']).read_text().splitlines():
        if line.startswith('v '):
            verts.append(Vector([float(x) for x in line.split()[1:4]]))
        elif line.startswith('f '):
            faces.append([int(s.split('/')[0]) - 1 for s in line.split()[1:]])
    return BVHTree.FromPolygons(verts, faces)


def on_skin(bvh, p, n, depth=0.0):
    """Project p onto the skin along ±n; return the skin point offset by `depth` along n."""
    for d in (-n, n):
        hit = bvh.ray_cast(p + n * 0.05 * (1 if d == -n else -1), d, 0.12)
        if hit[0] is not None:
            return hit[0] + n * depth
    loc, *_ = bvh.find_nearest(p)
    return (loc if loc is not None else p) + n * depth


def write(obj, out, name):
    """Write evaluated mesh triangles as OBJ in atlas coordinates."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    mesh = ev.to_mesh()
    mesh.calc_loop_triangles()
    path = Path(out) / f'{name}.obj'
    with path.open('w') as f:
        f.write(f'# {name}: generated schematic structure (Human Atlas). Not scan-derived.\n')
        for v in mesh.vertices:
            co = obj.matrix_world @ v.co
            f.write(f'v {co.x:.6f} {co.y:.6f} {co.z:.6f}\n')
        for t in mesh.loop_triangles:
            a, b, c = t.vertices
            f.write(f'f {a + 1} {b + 1} {c + 1}\n')
    count = len(mesh.vertices)
    ev.to_mesh_clear()
    print('wrote', path, count)
