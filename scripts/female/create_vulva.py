"""Generate schematic vulva structures: labia majora, labia minora and the vestibule.

blender -b --factory-startup -P scripts/female/create_vulva.py -- LANDMARKS.json OUT_DIR

APPROXIMATE / SCHEMATIC — not scan-derived. Shapes follow the perineal skin of the atlas body
(projected onto it) and use mid-range values of published measurements (Lloyd et al. 2005,
BJOG 112:643-646): labia majora length 70-120 mm (used 85), labia minora length 20-100 mm
(used 45) and width 7-50 mm (used ~11), clitoris-to-urethra distance 16-45 mm (used ~22).
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import blender_common as bc  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

lm, out = bc.args()
bc.reset()
skin = bc.skin_bvh(lm)
ap, n, lr = bc.frame(lm)
O = bc.V(lm['introitus'])
A = bc.V(lm['anterior_commissure'])
P = bc.V(lm['posterior_commissure'])


def skin_path(start, end, lateral, depth, count=9, bow=0.0):
    pts = []
    for k in range(count):
        t = k / (count - 1)
        p = start.lerp(end, t) + lr * lateral * (1 + bow * math.sin(math.pi * t))
        pts.append(bc.on_skin(skin, p, n, depth))
    return pts


# Labia majora: rounded fat-filled folds either side of the pudendal cleft (A → P).
for side, s in (('left', 1), ('right', -1)):
    path = bc.bezier(skin_path(A, P, s * 0.016, 0.0035, bow=0.25), 6)
    r = lambda t: 0.0035 + 0.0062 * math.sin(math.pi * min(1, max(0, t))) ** 0.55
    obj = bc.tube(f'labium_majus_{side}', path, r, segments=18, scale_lr=0.62, lr_axis=lr)
    bc.polish(obj, voxel=0.0011, smooth=6, ratio=0.4)
    bc.write(obj, out, f'labium_majus_{side}')

# Labia minora: thin folds bordering the vestibule, from the clitoral prepuce to the fourchette.
G = bc.V(lm['glans_site'])
for side, s in (('left', 1), ('right', -1)):
    start = G - ap * 0.004 + lr * s * 0.004
    end = O - ap * 0.013 + lr * s * 0.006
    path = bc.bezier(skin_path(start, end, s * 0.0045, 0.0018, count=7, bow=0.6), 6)
    r = lambda t: 0.0012 + 0.0042 * math.sin(math.pi * min(1, max(0, t))) ** 0.7
    obj = bc.tube(f'labium_minus_{side}', path, r, segments=14, scale_lr=0.38, lr_axis=lr)
    bc.polish(obj, voxel=0.0008, smooth=4, ratio=0.45)
    bc.write(obj, out, f'labium_minus_{side}')

# Vestibule: the recessed area between the labia minora, with urethral and vaginal openings.
M = bc.V(lm['meatus'])
centre = (G - ap * 0.006).lerp(O - ap * 0.011, 0.5)
half_len = ((G - ap * 0.006) - (O - ap * 0.011)).length / 2
bm = bmesh.new()
rings, R, S = [], 10, 40
for i in range(R + 1):
    ring = []
    for k in range(S):
        a = 2 * math.pi * k / S
        u, v = math.cos(a) * half_len * i / R, math.sin(a) * 0.0075 * i / R
        ring.append(bm.verts.new(centre + ap * u + lr * v))
    rings.append(ring)
holes = [(M, 0.0022), (O, 0.0085)]
for i in range(R):
    for k in range(S):
        quad = (rings[i][k], rings[i][(k + 1) % S], rings[i + 1][(k + 1) % S], rings[i + 1][k])
        c = sum((q.co for q in quad), Vector()) / 4
        if any(((c - h) - n * (c - h).dot(n)).length < r for h, r in holes):
            continue
        if i == 0:
            if k % 2 == 0:
                continue
        bm.faces.new(quad if i else quad)
for v in bm.verts:
    v.co = bc.on_skin(skin, v.co, n, -0.0012)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
loose = [v for v in bm.verts if not v.link_faces]
bmesh.ops.delete(bm, geom=loose, context='VERTS')
obj = bc.finish('vestibule', bm)
bc.polish(obj, voxel=0.0007, smooth=2, ratio=0.5, solidify=0.0012)
bc.write(obj, out, 'vestibule_of_vagina')
