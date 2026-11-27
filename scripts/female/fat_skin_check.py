"""Fat gates on the PACKAGED female model (gate_checks exempts subcutaneous fat):
  - every fat part (system adipose or subcutaneous): vertices outside her skin (signed distance)
  - the subcutaneous fat layer (milestone 10): boundary (open) edges, i.e. cut edges, must be 0

    python scripts/female/fat_skin_check.py      -> prints per part, exit 1 on any failure
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
    pq = trimesh.proximity.ProximityQuery(skin)
    bad = 0
    for p in atlas['parts']:
        if p['system'] not in ('adipose', 'subcutaneous'):
            continue
        P = M[p['id']]['pos']
        w = pq.signed_distance(P)            # > 0 inside the skin
        n = int((w < 0).sum())
        line = f"{p['name']}: {len(P)} vertices, {n} outside the skin, min inset {w.min() * 1000:.2f} mm"
        if p['system'] == 'subcutaneous':
            m = trimesh.Trimesh(P, M[p['id']]['idx'].reshape(-1, 3), process=False)
            be = len(trimesh.grouping.group_rows(m.edges_sorted, require_count=1))
            line += f', boundary edges {be}'
            bad += be
        print(line)
        bad += n
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
