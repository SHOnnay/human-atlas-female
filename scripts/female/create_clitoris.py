"""Generate a schematic clitoral complex: glans, body, left/right crura, left/right vestibular bulbs.

blender -b --factory-startup -P scripts/female/create_clitoris.py -- LANDMARKS.json OUT_DIR

APPROXIMATE / SCHEMATIC — not scan-derived. Layout follows O'Connell et al. (J Urol 1998;
159:1892-1897 and 2005;174:1189-1195): the glans continues as a body that bends posteriorly
toward the pubic symphysis and divides into two crura along the ischiopubic rami; the
vestibular bulbs lie deep to the labia either side of the vestibule. Sizes used: glans width
7 mm (published 3-10 mm, Lloyd et al. 2005), body ~25 mm, crura ~50 mm, bulbs ~35 mm.
Crura follow polylines offset from the pelvis bone, supplied by build_female.py.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import blender_common as bc  # noqa: E402

lm, out = bc.args()
bc.reset()
ap, n, lr = bc.frame(lm)
G = bc.V(lm['glans_site']) - n * 0.007  # under the prepuce, ~7 mm beneath the skin surface
root = bc.V(lm['clitoral_root'])
O = bc.V(lm['introitus'])

glans = bc.ellipsoid('glans', G, (ap, lr, n), (0.0042, 0.0035, 0.0032))
bc.polish(glans, voxel=0.0006, smooth=2, ratio=0.5)
bc.write(glans, out, 'glans_of_clitoris')

knee = G.lerp(root, 0.45) - n * 0.004 + ap * 0.004
body = bc.tube('body', bc.bezier([G, knee, root], 8), lambda t: 0.0036 + 0.0008 * t, segments=14)
bc.polish(body, voxel=0.0007, smooth=4, ratio=0.45)
bc.write(body, out, 'body_of_clitoris')

for side in ('left', 'right'):
    pts = [root] + [bc.V(p) for p in lm['crus_' + side]]
    path = bc.bezier(pts, 6)
    crus = bc.tube('crus', path, lambda t: 0.0042 - 0.0027 * t ** 1.3, segments=14)
    bc.polish(crus, voxel=0.0008, smooth=4, ratio=0.4)
    bc.write(crus, out, f'crus_of_clitoris_{side}')

for side, s in (('left', 1), ('right', -1)):
    a = root + lr * s * 0.007 - n * 0.002
    b = O + ap * 0.010 + lr * s * 0.0165 - n * 0.009
    c = O - ap * 0.012 + lr * s * 0.016 - n * 0.008
    path = bc.bezier([a, b, c], 8)
    bulb = bc.tube('bulb', path, lambda t: 0.0018 + 0.0034 * math.sin(math.pi * min(1, t ** 0.75)), segments=14,
                   scale_lr=0.7, lr_axis=lr)
    bc.polish(bulb, voxel=0.0008, smooth=4, ratio=0.4)
    bc.write(bulb, out, f'bulb_of_vestibule_{side}')
