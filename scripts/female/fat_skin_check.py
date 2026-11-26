"""Milestone 9: gate_checks exempts subcutaneous fat, so the gluteofemoral fat is checked here on the
PACKAGED female model: number of fat vertices outside her skin (winding number, skin mesh).

    python scripts/female/fat_skin_check.py      -> prints per side, exit 1 if any vertex is outside
"""
import sys
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import meshlib as ml  # noqa: E402


def main():
    atlas, M = ml.load_package(ROOT / 'public/models/female/atlas.json')
    by = {p['name']: M[p['id']] for p in atlas['parts']}
    skin = ml.to_trimesh(by['Skin']['pos'], by['Skin']['idx'])
    bad = 0
    for side in ('Left', 'Right'):
        f = by.get(f'{side} gluteofemoral subcutaneous fat')
        if f is None:
            print(side, 'missing'); bad += 1
            continue
        P = f['pos']
        w = trimesh.proximity.ProximityQuery(skin).signed_distance(P)   # > 0 inside the skin
        n = int((w < 0).sum())
        print(f'{side} gluteofemoral fat: {len(P)} vertices, {n} outside the skin, min inset {w.min() * 1000:.2f} mm')
        bad += n
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
