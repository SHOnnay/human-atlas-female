"""Gate C: male vs female composites from identical cameras.

    python scripts/female/compare_renders.py   -> docs/screenshots/compare/<category>_<view>.png

Exports each category from both packaged models (merged per display system), renders both with
Blender Workbench from the same camera (framed on the union of the two bodies' geometry for that
category), and places male (left) and female (right) side by side.
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import blender_run  # noqa: E402
import meshlib as ml  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs' / 'screenshots' / 'compare'
TMP = Path(tempfile.gettempdir()) / 'ha-compare'
VISIBLE = {'cardiac', 'sensory', 'skeletal', 'muscular', 'arterial', 'venous', 'nervous', 'respiratory', 'digestive', 'urinary',
           'lymphatic', 'endocrine', 'reproductive', 'connective', 'adipose', 'erectile', 'mammary', 'lactiferous'}


def categories(p, c):
    """Category membership for part p with centroid c (atlas frame, feet at y=0)."""
    s, n = p['system'], p['name'].lower()
    out = []
    if s in VISIBLE:
        out.append('all-systems')
    if s in VISIBLE or n == 'skin':
        out.append('all-systems-skin')
    if n == 'skin':
        out.append('skin-only')
    if s == 'skeletal':
        out.append('skeleton-only')
    if s in ('skeletal', 'reproductive', 'urinary') and 0.5 < c[1] < 1.08 and abs(c[0]) < 0.2 and p['name'] != 'Skin':
        out.append('pelvis-closeup')
    if (s in ('reproductive', 'urinary', 'skeletal') or re.search(r'levator|pubococc|puborect|iliococc|sphincter|perine|bulbospong|ischiocav', n)) \
            and 0.55 < c[1] < 0.98 and abs(c[0]) < 0.2:
        out.append('perineum-closeup')
    if 1.0 < c[1] < 1.45 and abs(c[0]) < 0.22 and (s in ('reproductive', 'connective', 'skeletal', 'adipose', 'mammary', 'lactiferous') or re.search(r'pectoralis|serratus|intercostal', n)):
        out.append('breast-closeup')
    # v3 close-ups. Milestone 7: hands found from each body's own hand bones (pose-independent).
    for side, box in HANDS.items():
        if s not in ('integumentary',) and np.all(c > box[0]) and np.all(c < box[1]):
            out.append('hand-' + side)
    if 0.40 < c[1] < 0.85 and abs(c[0]) < 0.25 and s in ('skeletal', 'muscular', 'connective'):
        out.append('thigh-closeup')
        if s == 'skeletal':
            out.append('thigh-skeleton')
    if c[1] > 1.30 and s in ('skeletal', 'sensory') and n != 'skin':
        out.append('head-skeleton')
    in_breast = 1.0 < c[1] < 1.36 and abs(c[0]) < 0.24
    if in_breast and (s in ('mammary', 'lactiferous', 'adipose', 'skeletal') or 'suspensory' in n or re.search(r'pectoralis|serratus|intercostal|nipple|areola', n)):
        out.append('breast-fat-on')
        if s != 'adipose':
            out.append('breast-fat-off')
    if 0.6 < c[1] < 1.0 and abs(c[0]) < 0.15 and (s in ('reproductive', 'urinary', 'erectile') or n == 'skin'
                                                   or re.search(r'hip bone|ilium|ischium|pubis|bulbospong|ischiocav|perine|sacrum', n)):
        out.append('vulva-closeup')
    if re.search(r'uter|cervix|fallopian|tube|ovary', n) and s == 'reproductive' and 'ligament' not in n and 'pouch' not in n:
        out.append('uterus-isolated')
    return out


JOB_VIEWS = {'perineum-closeup': ['front', 'side', 'back', 'oblique', 'below'], 'hand-left': ['palm', 'dorsum', 'front', 'back'], 'hand-right': ['palm_r', 'dorsum_r', 'front', 'back'], 'head-skeleton': ['front', 'side'], 'thigh-closeup': ['front', 'side', 'back'], 'thigh-skeleton': ['front', 'side', 'back'],
             'breast-fat-on': ['front', 'side', 'oblique'], 'breast-fat-off': ['front', 'side', 'oblique'], 'vulva-closeup': ['front', 'below', 'oblique'],
             'uterus-isolated': ['front', 'side', 'oblique']}
JOB_ALPHA = {'vulva-closeup': {'integumentary': 0.4}, 'breast-fat-on': {'adipose': 0.35}, 'all-systems': {'adipose': 0.35},
             'all-systems-skin': {'integumentary': 0.2}}
NO_FRAME = {'vulva-closeup': {'integumentary'}}   # systems that do not set the camera framing


HANDS = {}
HAND_TIGHT = {}
HAND_PTS = {}
HAND_PTS_BY = {}
HAND_BONE = re.compile(r'carp|phalanx of .*(finger|thumb)|scaphoid|lunate|triquetr|pisiform|trapezi|capitate|hamate', re.I)


DIRS_B = {'front': (0, -1, 0), 'back': (0, 1, 0), 'side': (1, 0, 0), 'oblique': (0.75, -1, 0.15), 'below': (0, -0.35, -1),
          'palm': (-1, -0.25, 0), 'dorsum': (1, 0.25, 0), 'palm_r': (1, -0.25, 0), 'dorsum_r': (-1, 0.25, 0)}


def view_frame(P, v, fill=0.70, aspect=700 / 900):
    """Round 2 review: frame one hand view on the hand bones AS SEEN from that camera (projected
    extents), centred, the hand filling ~70 % of the portrait frame. Returns [atlas centre, size]
    where both renderers show size * 1.08 vertically."""
    b = DIRS_B[v]
    d = np.array([b[0], b[2], -b[1]], float); d /= np.linalg.norm(d)
    up = np.array([0, 1.0, 0]); up = up - (up @ d) * d; up /= np.linalg.norm(up)
    r = np.cross(d, up)
    u, w = P @ r, P @ up
    um, wm = (u.min() + u.max()) / 2, (w.min() + w.max()) / 2
    c = r * um + up * wm + d * float((P @ d).mean())
    scale = max(np.ptp(w), np.ptp(u) / aspect) / fill
    return [c.tolist(), float(scale / 1.08)]


def export(body, path):
    atlas, M = ml.load_package(path)
    set_hands(atlas, M)
    bounds = _export(body, atlas, M)
    HAND_PTS_BY[body] = dict(HAND_PTS)
    # Milestone 8: hand views frame the hand only (carpus to fingertips), centred, the hand bones
    # filling about 70 % of the frame (the camera shows size * 1.08 of the frame's largest extent).
    for side, (lo, hi) in HAND_TIGHT.items():
        c, half = (lo + hi) / 2, float(np.max(hi - lo)) / 2 / (0.62 * 1.08)   # round 1: 0.70 clipped the female hands
        if f'hand-{side}' in bounds:
            bounds[f'hand-{side}'] = (c - half, c + half)
    return bounds


def set_hands(atlas, M):
    HANDS.clear(); HAND_TIGHT.clear(); HAND_PTS.clear()
    for side, sgn in (('left', 1), ('right', -1)):
        hb = [M[p['id']]['pos'] for p in atlas['parts'] if p['system'] == 'skeletal' and HAND_BONE.search(p['name'])
              and np.sign(M[p['id']]['pos'][:, 0].mean()) == sgn]
        if hb:
            V = np.vstack(hb)
            HANDS[side] = (V.min(0) - 0.02, V.max(0) + 0.02)
            HAND_TIGHT[side] = (V.min(0), V.max(0))
            HAND_PTS[side] = V[::max(1, len(V) // 4000)]


def _export(body, atlas, M):
    groups = {}
    for p in atlas['parts']:
        pos = M[p['id']]['pos']
        c = pos.mean(0)
        for cat in categories(p, c):
            groups.setdefault((cat, p['system']), []).append((pos, M[p['id']]['idx']))
    bounds = {}
    for (cat, system), items in groups.items():
        d = TMP / body / cat
        d.mkdir(parents=True, exist_ok=True)
        V, F, off = [], [], 0
        for pos, idx in items:
            V.append(pos); F.append(idx.reshape(-1, 3) + off); off += len(pos)
        V = np.vstack(V); F = np.vstack(F)
        ml.write_obj(d / f'{system}.obj', V, F.reshape(-1))
        if system in NO_FRAME.get(cat, ()):
            continue
        lo, hi = bounds.get(cat, (V.min(0), V.max(0)))
        bounds[cat] = (np.minimum(lo, V.min(0)), np.maximum(hi, V.max(0)))
    return bounds


def main():
    import shutil
    from PIL import Image, ImageDraw
    if TMP.exists():
        shutil.rmtree(TMP)
    bm = export('male', ROOT / 'public/models/atlas.json')
    bf = export('female', ROOT / 'public/models/female/atlas.json')
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = []
    for cat in sorted(bf):          # female-only categories (uterus) render a blank male panel
        mb = bm.get(cat, bf[cat])
        lo = np.minimum(mb[0], bf[cat][0]); hi = np.maximum(mb[1], bf[cat][1])
        views = JOB_VIEWS.get(cat, ['front', 'side', 'back', 'oblique'])
        frames = {'female': [bf[cat][0].tolist(), bf[cat][1].tolist()]}
        if cat in bm:
            frames['male'] = [bm[cat][0].tolist(), bm[cat][1].tolist()]
        job = {'cat': cat, 'lo': lo.tolist(), 'hi': hi.tolist(), 'views': views, 'alpha': JOB_ALPHA.get(cat, {}),
               'frames': frames}
        if cat.startswith('hand-'):
            job['view_frames'] = {b: {v: view_frame(HAND_PTS_BY[b][cat[5:]], v) for v in views}
                                  for b in ('male', 'female') if cat[5:] in HAND_PTS_BY.get(b, {})}
        jobs.append(job)
    (TMP / 'jobs.json').write_text(json.dumps(jobs))
    blender_run.run(Path(__file__).with_name('render_compare_blender.py'), [TMP / 'jobs.json', TMP], quiet=True)
    made = []
    for job in jobs:
        for v in job['views']:
            a = Image.open(TMP / f"male_{job['cat']}_{v}.png").convert('RGB')
            b = Image.open(TMP / f"female_{job['cat']}_{v}.png").convert('RGB')
            img = Image.new('RGB', (a.width + b.width, a.height + 36), (245, 246, 247))
            img.paste(a, (0, 36)); img.paste(b, (a.width, 36))
            d = ImageDraw.Draw(img)
            d.text((12, 10), f"MALE  ·  {job['cat']}  ·  {v}", fill=(40, 50, 60))
            d.text((a.width + 12, 10), f"FEMALE  ·  {job['cat']}  ·  {v}", fill=(40, 50, 60))
            name = f"{job['cat']}_{v}.png"
            img.save(OUT / name)
            made.append(name)
    print('\n'.join(made))


if __name__ == '__main__':
    main()
