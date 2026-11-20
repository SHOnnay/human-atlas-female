"""Generate the remaining female structures no open scan provides.

blender -b --factory-startup -P scripts/female/create_female_extras.py -- LANDMARKS.json OUT_DIR

GENERATED / SCHEMATIC — not scan-derived. References: Gray's Anatomy 42nd ed. (2020).
* Ovarian arteries: from the abdominal aorta just below the renal arteries, down over psoas,
  across the pelvic brim in the suspensory ligament of the ovary, to the ovary (~2-3 mm diameter).
* Ovarian veins: same course; right -> inferior vena cava, left -> left renal vein (~3-4 mm).
* Greater vestibular (Bartholin's) glands: pea-sized (~1 cm), posterolateral to the vaginal
  orifice, deep to the bulbospongiosus at about 4 and 8 o'clock.
* Paraurethral (Skene's) glands: small (few mm) glands either side of the external urethral orifice.
* Perineal body: fibromuscular node (~1-1.5 cm) between the vaginal orifice and the anus.
* Mons pubis: subcutaneous fat pad over the pubic symphysis.
* Prepuce of the clitoris: hood of the labia minora over the glans.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import blender_common as bc  # noqa: E402

lm, out = bc.args()
bc.reset()
ap, n, lr = bc.frame(lm)
V = bc.V
O, M, G = V(lm['introitus']), V(lm['meatus']), V(lm['glans_site'])

for side, s in (('left', 1), ('right', -1)):
    ov = V(lm['ovary_' + side])
    susp = V(lm['susp_top_' + side])
    ao = V(lm['aorta_origin'])
    mid = ao.lerp(susp, 0.5) + V((s * 0.025, 0, -0.005))
    art = bc.tube('a', bc.bezier([ao + V((s * 0.006, 0, 0.004)), mid, susp, ov], 10), lambda t: 0.0013, segments=10)
    bc.polish(art, voxel=0.0006, smooth=2, ratio=0.5)
    bc.write(art, out, f'ovarian_artery_{side}')
    drain = V(lm['ivc_point']) if side == 'right' else V(lm['left_renal_vein_point'])
    midv = drain.lerp(susp, 0.5) + V((s * 0.03, 0, -0.008))
    vein = bc.tube('v', bc.bezier([drain, midv, susp + V((s * 0.004, 0, -0.003)), ov + V((0, 0.003, -0.003))], 10),
                   lambda t: 0.0019, segments=10)
    bc.polish(vein, voxel=0.0007, smooth=2, ratio=0.5)
    bc.write(vein, out, f'ovarian_vein_{side}')

for side, s in (('left', 1), ('right', -1)):
    c = O - ap * 0.008 + lr * s * 0.013 - n * 0.012
    g = bc.ellipsoid('bartholin', c, (ap, lr, n), (0.0055, 0.004, 0.0035), subdiv=3)
    bc.polish(g, voxel=0.0006, smooth=2, ratio=0.5)
    bc.write(g, out, f'greater_vestibular_gland_{side}')
    k = M + lr * s * 0.004 - n * 0.006 + ap * 0.001
    sk = bc.ellipsoid('skene', k, (ap, lr, n), (0.0025, 0.0018, 0.0018), subdiv=2)
    bc.polish(sk, voxel=0.0005, smooth=1, ratio=0.6)
    bc.write(sk, out, f'paraurethral_gland_{side}')

pb = V(lm['perineal_body'])
body = bc.ellipsoid('pb', pb, (ap, lr, n), (0.008, 0.011, 0.008), subdiv=3)
bc.polish(body, voxel=0.0008, smooth=3, ratio=0.45)
bc.write(body, out, 'perineal_body')

mons = V(lm['mons_centre'])
pad = bc.ellipsoid('mons', mons, (V(lm['mons_up']), lr, V(lm['mons_normal'])), (0.032, 0.045, 0.008), subdiv=4)
bc.polish(pad, voxel=0.0012, smooth=4, ratio=0.35)
bc.write(pad, out, 'mons_pubis_fat_pad')

gl = G - n * 0.007
hood_path = bc.bezier([gl + ap * 0.011 - n * 0.001, gl + ap * 0.004 + n * 0.0015, gl - ap * 0.003 + n * 0.0015], 6)
hood = bc.tube('prepuce', hood_path, lambda t: 0.0058 - 0.001 * t, segments=16, arc=(-1.6, 1.6), ref_dir=n)
bc.polish(hood, voxel=0.0005, smooth=2, ratio=0.5, solidify=0.0011)
bc.write(hood, out, 'prepuce_of_clitoris')
