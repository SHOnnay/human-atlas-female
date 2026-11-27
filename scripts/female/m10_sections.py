"""Milestone 10: sections at T10, L3, S1, the pubic level and mid-thigh, and CT fat thickness.

    python scripts/female/m10_sections.py     (TotalSegmentator venv) -> work/vhf/m10_sections.json,
                                                                        docs/screenshots/sections/m10_*.png
Overlay on her CT (grey): white = model skin, green = subcutaneous fat layer, cyan = abdominal wall muscles,
yellow = model gluteals, red = CT gluteal labels (TotalSegmentator `total`). The CT plane is sampled through
the CT -> HRA registration plus the milestone 10 local refinement (pelvis + lower ribs) at T10 / L3, the
milestone 9 pelvis refinement at S1 / pubic level, and the leg volume's own registration at mid-thigh.
Gluteal Dice per side (winding-number fill, see glute_sections.py).
CT subcutaneous fat thickness is measured in the CT alone: rays from the bone (or body) centre outward, the
outermost fat run (HU -190..-30, >= 3 mm) is the subcutaneous fat. Posterior values are supine-distorted.
Courtesy of the U.S. National Library of Medicine (VHF data).
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import meshlib as ml  # noqa: E402
import vhf_sections as vs  # noqa: E402
import glute_sections as gs  # noqa: E402

OUT = ROOT / 'docs' / 'screenshots' / 'sections'
LEVELS = ('T10', 'L3', 'S1', 'pubic symphysis', 'mid-thigh')
ABD = re.compile(r'(Left|Right) (external oblique|internal oblique|transversus abdominis|rectus abdominis)$|Linea alba')


def seg_lines(meshes, y):
    import trimesh
    out = []
    for m in meshes:
        if m.bounds[0][1] > y or m.bounds[1][1] < y:
            continue
        s = trimesh.intersections.mesh_plane(m, [0, 1, 0], [0, y, 0])
        if len(s):
            out.append(s[:, :, [0, 2]])
    return np.vstack(out) if out else np.zeros((0, 2, 2))


def draw(img, segs, col):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for a, b in segs:
        d.line([((a[0] - vs.EXT[0]) / vs.G, (vs.EXT[3] - a[1]) / vs.G), ((b[0] - vs.EXT[0]) / vs.G, (vs.EXT[3] - b[1]) / vs.G)], fill=col, width=1)


def ct_fat(hu_fn, cx, cz, y, angles, rmax=0.20):
    """Outermost subcutaneous fat run (mm) along rays from (cx, cz) at height y, CT only."""
    s = np.arange(0, rmax, 0.0005)
    res = []
    for a in angles:
        P = np.c_[cx + np.sin(a) * s, np.full(len(s), y), cz + np.cos(a) * s]
        h = hu_fn(P)
        fat = (h > -190) & (h < -30)
        d = np.diff(np.r_[0, fat.astype(np.int8), 0])
        st, en = np.where(d == 1)[0], np.where(d == -1)[0]
        runs = [(a_, b_) for a_, b_ in zip(st, en) if b_ - a_ >= 6]
        res.append((runs[-1][1] - runs[-1][0]) * 0.5 if runs else np.nan)
    return res


def main():
    import trimesh
    from PIL import Image
    from totalsegmentator.map_to_binary import class_map
    labels = class_map['total']
    OUT.mkdir(parents=True, exist_ok=True)
    atlas, M = ml.load_package(ROOT / 'public/models/female/atlas.json')
    rep = json.loads((ROOT / 'work/female/report.json').read_text())
    vols = json.loads((ROOT / 'work/vhf/registration.json').read_text())['volumes']
    pr = rep.get('m9_pelvis_registration', {}); lr = rep.get('m10_local_registration', {})
    d_pel = (np.array(pr['R']), np.array(pr['t'])) if 'R' in pr else None
    d_loc = (np.array(lr['R']), np.array(lr['t'])) if 'R' in lr else None
    lev = vs.levels(atlas, M)
    by = {p['name']: p for p in atlas['parts']}
    mesh = lambda p: ml.to_trimesh(M[p['id']]['pos'], M[p['id']]['idx'])
    skin = [mesh(by['Skin'])]
    fat = [mesh(p) for p in atlas['parts'] if p['system'] == 'subcutaneous']
    abd = [mesh(p) for p in atlas['parts'] if ABD.fullmatch(p['name'])]
    res = {}
    for lv in LEVELS:
        y = lev[lv]
        A, shape = gs.plane_points(y)
        if lv == 'mid-thigh':
            vol, delta = 'femur_to_toes', None
        else:
            vol, delta = 'head_to_femur', (d_loc if lv in ('T10', 'L3') else d_pel)
        hu, inside = gs.sample(vol, A, vols[vol], delta)
        hu2 = hu.reshape(shape)
        img = Image.fromarray(np.stack([np.clip((hu2 + 200) / 1400 * 255, 0, 255).astype(np.uint8)] * 3, -1))
        draw(img, seg_lines(skin, y), (255, 255, 255))
        draw(img, seg_lines(fat, y), (60, 230, 90))
        draw(img, seg_lines(abd, y), (60, 220, 255))
        row = {'y_m': y, 'ct_volume': vol}
        if lv in ('S1', 'pubic symphysis'):
            sg, _ = gs.sample(vol, A, vols[vol], delta, seg=True)
            sg = sg.reshape(shape)
            arr = np.array(img)
            for side in ('Left', 'Right'):
                mus = [mesh(by[f'{side} gluteus {m}']) for m in ('maximus', 'medius', 'minimus')]
                model = gs.winding_mask(mus, y)
                ids = [k for k, l in labels.items() if re.fullmatch(f'gluteus_(maximus|medius|minimus)_{side.lower()}', l)]
                ct = np.isin(sg, ids)
                row[f'{side} gluteal Dice'] = vs.dice(model, ct) if (model.any() or ct.any()) else None
                e = lambda m: m ^ __import__('scipy').ndimage.binary_erosion(m)
                arr[e(ct)] = (255, 60, 60); arr[e(model)] = (255, 220, 0)
            img = Image.fromarray(arr)
        from PIL import ImageDraw
        ImageDraw.Draw(img).text((8, 6), f'{lv}  CT grey | white skin | green subcutaneous fat | cyan abdominal wall | yellow model gluteals | red CT gluteals',
                                 fill=(255, 255, 255))
        img.save(OUT / f"m10_{lv.replace(' ', '-')}.png")
        res[lv] = row
        print(lv, row, flush=True)
    # ---- CT subcutaneous fat thickness at the requested sites (CT only)
    hf = lambda d: (lambda P: gs.sample('head_to_femur', P, vols['head_to_femur'], d)[0])
    ft = lambda P: gs.sample('femur_to_toes', P, vols['femur_to_toes'], None)[0]
    ct = {}
    band = np.load(ROOT / 'work/vhf/abdominal_band.npz')
    yl3 = lev['L3']
    if d_loc is not None:
        yl3 = float(((np.array([[0, lev['L3'], 0.08]]) - d_loc[1]) @ d_loc[0])[0, 1])
    iy = np.argmin(np.abs(band['y'] - yl3)); th = np.degrees(band['theta'])
    sel = np.abs(th) < 15
    v = (band['r_skin'][iy, sel] - band['r_out'][iy, sel]) * 1000
    ct['abdomen L3 anterior'] = float(np.nanmedian(v))

    def bone_centre(name, y):
        P = M[by[name]['id']]['pos']
        s = P[np.abs(P[:, 1] - y) < 0.01]
        return s[:, 0].mean(), s[:, 2].mean()
    for side, sgn in (('Left', 1), ('Right', -1)):
        fm = M[by[f'{side} femur']['id']]['pos']
        yt = fm[:, 1].max() - 0.25 * np.ptp(fm[:, 1])
        cx, cz = bone_centre(f'{side} femur', yt)
        ct[f'upper thigh ({side})'] = float(np.nanmedian(ct_fat(hf(d_pel), cx, cz, yt, np.radians(np.arange(0, 360, 30)))))
        ym = lev['mid-thigh']
        cx, cz = bone_centre(f'{side} femur', ym)
        ct[f'mid-thigh ({side})'] = float(np.nanmedian(ct_fat(ft, cx, cz, ym, np.radians(np.arange(0, 360, 30)))))
        top = fm[fm[:, 1] > fm[:, 1].max() - 0.06]
        gt = top[np.argmax(top[:, 0] * sgn)]
        cx, cz = bone_centre(f'{side} femur', gt[1])
        ct[f'lateral hip at trochanter ({side})'] = float(np.nanmedian(ct_fat(hf(d_pel), cx, cz, gt[1], np.radians(sgn * np.arange(70, 111, 10)))))
        hm = M[by[f'{side} humerus']['id']]['pos']
        yh = (hm[:, 1].min() + hm[:, 1].max()) / 2
        cx, cz = bone_centre(f'{side} humerus', yh)
        ct[f'upper arm ({side})'] = float(np.nanmedian(ct_fat(hf(None), cx, cz, yh, np.radians(np.arange(0, 360, 30)), rmax=0.08)))
    s1 = lev['S1']
    sk = M[by['Skin']['id']]['pos']; sl = sk[(np.abs(sk[:, 1] - s1) < 0.005) & (np.abs(sk[:, 0]) < 0.2)]
    ct['buttock S1 posterior (supine-distorted)'] = float(np.nanmedian(ct_fat(hf(d_pel), 0.0, (sl[:, 2].min() + sl[:, 2].max()) / 2, s1,
                                                                             np.radians(np.r_[150, 160, 170, 190, 200, 210]), rmax=0.25)))
    res['ct_fat_thickness_mm'] = ct
    print('CT fat thickness (mm)', ct, flush=True)
    (ROOT / 'work/vhf/m10_sections.json').write_text(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
