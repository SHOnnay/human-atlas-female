"""Gate B on the packaged models: skin protrusion and floating parts.

    python scripts/female/gate_checks.py   -> work/female/gate_b.json

* Protrusion: vertices of every part (except the skin and surface structures that are part of it:
  nipples, areolae, areolar tubercles, the subcutaneous fat shell) lying outside the closed skin,
  tested against a filled 2 mm voxel grid of the skin.
* Floating: a part is attached when some other part lies within 5 mm of it.
The male model is measured with the same code as a baseline.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).parent))
import meshlib as ml  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SURFACE = re.compile(r'^skin$|nipple|areola|subcutaneous fat|hair|eyebrow|^lip$', re.I)


def check(path):
    atlas, M = ml.load_package(path)
    skin_id = [p['id'] for p in atlas['parts'] if p['name'] == 'Skin'][0]
    shell = ml.SkinShell(ml.to_trimesh(M[skin_id]['pos'], M[skin_id]['idx']))
    protruding = []
    for p in atlas['parts']:
        if SURFACE.search(p['name']):
            continue
        out = int((~shell.grid.is_filled(M[p['id']]['pos'])).sum())
        if out:
            protruding.append({'id': p['id'], 'name': p['name'], 'source': p.get('source', 'bp3d'), 'vertices_outside': out,
                               'fraction': out / len(M[p['id']]['pos'])})
    # Floating parts.
    allv, lab = [], []
    for i, p in enumerate(atlas['parts']):
        v = M[p['id']]['pos']
        allv.append(v); lab.append(np.full(len(v), i))
    allv = np.vstack(allv); lab = np.concatenate(lab)
    tree = cKDTree(allv)
    floating = []
    rng = np.random.default_rng(0)
    for i, p in enumerate(atlas['parts']):
        v = M[p['id']]['pos']
        s = v if len(v) <= 400 else v[rng.choice(len(v), 400, replace=False)]
        hit = False
        for js in tree.query_ball_point(s, 0.005):
            if np.any(lab[js] != i):
                hit = True
                break
        if not hit:
            d, j = tree.query(s, k=min(64, len(allv)))
            other = np.where(lab[j] != i, d, np.inf).min()
            floating.append({'id': p['id'], 'name': p['name'], 'source': p.get('source', 'bp3d'), 'nearest_other_mm': float(other * 1000)})
    by = lambda rows, key: {s: sum(r['source'] == s for r in rows) for s in sorted({r['source'] for r in rows})}
    return {'parts': len(atlas['parts']), 'protruding': protruding, 'protruding_by_source': by(protruding, 'source'),
            'floating': floating, 'floating_by_source': by(floating, 'source')}


def main():
    res = {'male': check(ROOT / 'public/models/atlas.json'), 'female': check(ROOT / 'public/models/female/atlas.json')}
    (ROOT / 'work/female').mkdir(parents=True, exist_ok=True)
    (ROOT / 'work/female/gate_b.json').write_text(json.dumps(res, indent=1))
    for body in ('male', 'female'):
        r = res[body]
        print(body, 'protruding parts', len(r['protruding']), r['protruding_by_source'], '| floating parts', len(r['floating']), r['floating_by_source'])
    for row in sorted(res['female']['protruding'], key=lambda r: -r['vertices_outside'])[:25]:
        print('  OUT', row['source'], row['vertices_outside'], row['name'])
    for row in res['female']['floating'][:25]:
        print('  FLOAT', row['source'], round(row['nearest_other_mm'], 1), row['name'])


if __name__ == '__main__':
    main()
