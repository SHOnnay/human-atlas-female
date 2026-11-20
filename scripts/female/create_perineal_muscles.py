"""Generate schematic female superficial perineal muscles: ischiocavernosus and bulbospongiosus.

blender -b --factory-startup -P scripts/female/create_perineal_muscles.py -- LANDMARKS.json OUT_DIR

APPROXIMATE / SCHEMATIC — not scan-derived. Per Gray's Anatomy (42nd ed., 2020): in females,
ischiocavernosus covers each crus of the clitoris along the ischiopubic ramus, and
bulbospongiosus covers the vestibular bulbs on either side of the vaginal orifice, from the
perineal body to the clitoris. Sheets ~2 mm thick wrap the generated crura/bulb paths.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import blender_common as bc  # noqa: E402

lm, out = bc.args()
bc.reset()
ap, n, lr = bc.frame(lm)
root = bc.V(lm['clitoral_root'])
O = bc.V(lm['introitus'])
body = bc.V(lm['perineal_body'])

for side in ('left', 'right'):
    pts = [root.lerp(bc.V(lm['crus_' + side][0]), 0.35)] + [bc.V(p) for p in lm['crus_' + side]]
    path = bc.bezier(pts, 6)
    sheet = bc.tube('ic', path, lambda t: 0.0068 - 0.0035 * t ** 1.2, segments=16, arc=(-2.0, 2.0), ref_dir=-n)
    bc.polish(sheet, voxel=0.0008, smooth=3, ratio=0.4, solidify=0.0018)
    bc.write(sheet, out, f'ischiocavernosus_{side}')

for side, s in (('left', 1), ('right', -1)):
    a = root + lr * s * 0.008 - n * 0.001
    b = O + ap * 0.010 + lr * s * 0.0165 - n * 0.009
    c = O - ap * 0.012 + lr * s * 0.016 - n * 0.008
    d = body + lr * s * 0.004
    path = bc.bezier([a, b, c, d], 8)
    sheet = bc.tube('bs', path, lambda t: 0.0035 + 0.0045 * math.sin(math.pi * min(1, t ** 0.8)), segments=16,
                    arc=(-1.7, 1.7), ref_dir=lr * s - n * 0.6)
    bc.polish(sheet, voxel=0.0008, smooth=3, ratio=0.4, solidify=0.0018)
    bc.write(sheet, out, f'bulbospongiosus_{side}')
