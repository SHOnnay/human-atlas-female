"""Generate a schematic female urethra from the bladder neck to the external urethral orifice.

blender -b --factory-startup -P scripts/female/create_female_urethra.py -- LANDMARKS.json OUT_DIR

APPROXIMATE / SCHEMATIC — not scan-derived. Gray's Anatomy (42nd ed., 2020) describes the female
urethra as about 4 cm long and 6 mm in diameter, running anteroinferiorly behind the pubic
symphysis, embedded in the anterior vaginal wall. Path: HRA bladder neck → a control point
between the symphysis and the anterior vaginal wall (from build_female.py) → meatus.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import blender_common as bc  # noqa: E402

lm, out = bc.args()
bc.reset()
path = bc.bezier([bc.V(lm['bladder_neck']), bc.V(lm['urethra_mid']), bc.V(lm['meatus_inner'])], 12)
length = sum((b - a).length for a, b in zip(path, path[1:]))
urethra = bc.tube('urethra', path, lambda t: 0.003 - 0.0006 * t, segments=14)
bc.polish(urethra, voxel=0.0007, smooth=3, ratio=0.45)
bc.write(urethra, out, 'female_urethra')
print('URETHRA_LENGTH_MM', round(length * 1000, 1))
