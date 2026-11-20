"""Rebuild a packaged anatomy model end to end.

  python scripts/build-anatomy.py --sex male   OBJ_DIR CONCEPT_MAP SYSTEM_MAP
      BodyParts3D 4.0 → public/models/atlas.json + body-N.bin(.gz)
      (convert-anatomy.py → optimize-anatomy.mjs → compress-models.mjs atlas.json)

  python scripts/build-anatomy.py --sex female [--hra GLB] [--blender PATH]
      male package + HRA female v1.5 + Blender-generated structures
      → public/models/female/atlas.json + female-N.bin(.gz)
      (female/build_female.py → optimize-anatomy.mjs female/atlas.json → compress-models.mjs female/atlas.json)

The female build reads the packaged male model, so build male first when rebuilding both.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*cmd):
    print('$', ' '.join(map(str, cmd)), flush=True)
    subprocess.run(list(map(str, cmd)), check=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sex', choices=['male', 'female'], required=True)
    ap.add_argument('--hra', default=str(ROOT / 'work/sources/hra/3d-vh-f-united.glb'))
    ap.add_argument('--blender', help='Blender 4.2 executable (default: $BLENDER, work/tools, PATH)')
    ap.add_argument('male_inputs', nargs='*', help='male only: OBJ_DIR CONCEPT_MAP SYSTEM_MAP')
    a = ap.parse_args()
    if a.sex == 'male':
        if len(a.male_inputs) < 2:
            ap.error('male build needs OBJ_DIR CONCEPT_MAP [SYSTEM_MAP] (see README "Rebuilding geometry")')
        run(sys.executable, 'scripts/convert-anatomy.py', *a.male_inputs)
        run('node', 'scripts/optimize-anatomy.mjs', 'atlas.json')
        run('node', 'scripts/compress-models.mjs', 'atlas.json')
    else:
        if a.blender:
            os.environ['BLENDER'] = a.blender
        run(sys.executable, '-I', 'scripts/female/build_female.py', '--hra', a.hra)
        run('node', 'scripts/optimize-anatomy.mjs', 'female/atlas.json')
        run('node', 'scripts/compress-models.mjs', 'female/atlas.json')
        run('node', 'scripts/validate-atlas.mjs', 'female/atlas.json')
        run(sys.executable, '-I', 'scripts/female/measure.py')        # gate A -> work/female/measurements.json
        run(sys.executable, '-I', 'scripts/female/gate_checks.py')    # gate B -> work/female/gate_b.json


if __name__ == '__main__':
    main()
