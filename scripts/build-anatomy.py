"""Rebuild a packaged anatomy model end to end.

  python scripts/build-anatomy.py --sex male   OBJ_DIR CONCEPT_MAP SYSTEM_MAP
      BodyParts3D 4.0 → public/models/atlas.json + body-N.bin(.gz)
      (convert-anatomy.py → optimize-anatomy.mjs → compress-models.mjs atlas.json)

  python scripts/build-anatomy.py --sex female [--hra GLB] [--blender PATH]
      male package + MPFB2 average female (Blender + MPFB2 extension; generated once into
      work/female/mpfb/) + HRA female v1.5 + Blender-generated structures
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
    ap.add_argument('--body', choices=['vhf', 'mpfb'], default='vhf', help='female body: vhf (one real donor) or mpfb (v4)')
    ap.add_argument('--ts-python', default=os.environ.get('TS_PYTHON', 'python'),
                    help='Python of an environment with TotalSegmentator, idc-index, SimpleITK (VHF CT steps)')
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
        if a.body == 'vhf':
            # One real body: VHF CT (IDC, NLM) -> TotalSegmentator "total" (Apache-2.0) -> VHF targets in the
            # HRA frame -> BodyParts3D registration. The first three need the TotalSegmentator environment
            # (--ts-python); their outputs are cached under work/vhf/.
            if not (ROOT / 'work/vhf/targets').exists():
                run(a.ts_python, 'scripts/female/vhf_ct.py')
                ct = ROOT / 'work/vhf'
                for n in ('head_to_femur', 'femur_to_toes'):
                    run(Path(a.ts_python).with_name('TotalSegmentator'), '-i', ct / f'ct_{n}.nii.gz', '-o', ct / f'seg_{n}',
                        '--task', 'total', '--ml')
                run(a.ts_python, 'scripts/female/vhf_targets.py')
            if not (ROOT / 'work/vhf/registered.pkl').exists():
                run(sys.executable, 'scripts/female/vhf_register.py')
        run(sys.executable, '-I', 'scripts/female/build_female.py', '--hra', a.hra, '--body', a.body)
        run('node', 'scripts/optimize-anatomy.mjs', 'female/atlas.json')
        run('node', 'scripts/compress-models.mjs', 'female/atlas.json')
        run('node', 'scripts/validate-atlas.mjs', 'female/atlas.json')
        run(sys.executable, '-I', 'scripts/female/measure.py')        # gate A -> work/female/measurements.json
        run(sys.executable, '-I', 'scripts/female/gate_checks.py')    # gate B -> work/female/gate_b.json


if __name__ == '__main__':
    main()
