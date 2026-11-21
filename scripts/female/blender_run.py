"""Run a Blender Python script headless: python scripts/female/blender_run.py SCRIPT [args...]

Blender is located from $BLENDER, then work/tools/blender-*/blender(.exe), then PATH.
"""
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def find_blender():
    if os.environ.get('BLENDER'):
        return os.environ['BLENDER']
    local = sorted(glob.glob(str(ROOT / 'work' / 'tools' / 'blender-*' / ('blender.exe' if os.name == 'nt' else 'blender'))))
    if local:
        return local[-1]
    found = shutil.which('blender')
    if not found:
        raise SystemExit('Blender not found. Install Blender 4.2 LTS and set $BLENDER (see README).')
    return found


def run(script, args, blender=None, quiet=True, extensions=False):
    """extensions=True keeps the user's installed extensions (needed for MPFB2)."""
    base = [blender or find_blender(), '--background'] + ([] if extensions else ['--factory-startup'])
    cmd = base + ['--python', str(script), '--', *map(str, args)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or 'Traceback' in res.stdout + res.stderr:
        sys.stderr.write(res.stdout[-4000:] + res.stderr[-4000:])
        raise SystemExit(f'Blender script failed: {script}')
    if not quiet:
        print(res.stdout[-2000:])
    return res.stdout


if __name__ == '__main__':
    print(run(sys.argv[1], sys.argv[2:], quiet=False)[-1500:])
