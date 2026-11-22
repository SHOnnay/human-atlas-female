"""Step 8A: cross-section check of the female model against the real body.

    python scripts/female/vhf_sections.py     (TotalSegmentator venv: SimpleITK, pydicom, PIL, trimesh)

At 14 levels the model's body outline (skin) and bones are sliced and compared with
  * the VHF colour cryosection photo (body = not blue gelatin, not background) -> body Dice, and
  * the VHF CT plane at the same height (bone = HU > 200), sampled through the CT->HRA rigid
    registration of vhf_targets.py -> bone Dice.
Levels come from the model itself (registered vertebrae, joints). The cryosection z for a level is
found by searching +-40 mm (10 mm steps) around y*1000 + z_feet for the best body Dice, and its
in-plane placement is fitted per slice (translation + flips only, no scale): the reported body
Dice therefore measures SHAPE agreement, not absolute height. Overlays: docs/screenshots/sections/.
Courtesy of the U.S. National Library of Medicine (VHF data).
"""
import io
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import meshlib as ml  # noqa: E402

OUT = ROOT / 'docs' / 'screenshots' / 'sections'
CACHE = {}
G = 0.001          # raster grid 1 mm
EXT = (-0.30, 0.30, -0.20, 0.20)   # x0, x1, z0, z1 (m)


def raster(polys, ext=EXT, g=G):
    from PIL import Image, ImageDraw
    w, h = int((ext[1] - ext[0]) / g), int((ext[3] - ext[2]) / g)
    img = Image.new('L', (w, h), 0); d = ImageDraw.Draw(img)
    for poly in polys:
        pts = [((x - ext[0]) / g, (ext[3] - z) / g) for x, z in poly]
        if len(pts) > 2:
            d.polygon(pts, fill=255)
    return np.array(img) > 0


def section_polys(meshes, y):
    import trimesh
    polys = []
    for m in meshes:
        if m.bounds[0][1] > y or m.bounds[1][1] < y:
            continue
        s = m.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
        if s is None:
            continue
        for ent in s.discrete:
            polys.append(ent[:, [0, 2]])
    return polys


def dice(a, b):
    s = a.sum() + b.sum()
    return float(2 * (a & b).sum() / s) if s else float('nan')


def levels(atlas, M):
    by = {p['name']: M[p['id']]['pos'] for p in atlas['parts']}
    import re

    def c(*pats):           # BodyParts3D name or the real HRA vertebra label
        for n, v in by.items():
            if any(re.fullmatch(p, n, re.I) for p in pats):
                return v.mean(0)[1]
        raise KeyError(pats)
    skin = by['Skin']
    out = {'C5': c('Fifth cervical vertebra', r'(mammalian )?cervical vertebra 5( \(C5\))?'),
           'T4 (nipple level)': c('Fourth thoracic vertebra', r'thoracic vertebra 4( \(T4\))?'),
           'T10': c('Tenth thoracic vertebra', r'thoracic vertebra 10( \(T10\))?'),
           'L3': c('Third lumbar vertebra', r'lumbar vertebra 3( \(L3\))?'), 'S1': np.vstack([v for n, v in by.items() if n.lower() == 'sacrum' or 'sacrum' in n.lower()])[:, 1].max() - 0.02,
           'pubic symphysis': np.vstack([v for n, v in by.items() if n.lower().endswith('pubis')]).mean(0)[1]}
    out['perineum'] = out['pubic symphysis'] - 0.045
    fem = by['Left femur']; tib = by['Left tibia']
    out['mid-thigh'] = (fem[:, 1].max() + fem[:, 1].min()) / 2
    out['knee'] = fem[:, 1].min() + 0.01
    out['mid-calf'] = (tib[:, 1].max() + tib[:, 1].min()) / 2
    hum, rad = by['Left humerus'], by.get('Left radius')
    out['mid-upper-arm'] = (hum[:, 1].max() + hum[:, 1].min()) / 2
    if rad is not None:
        out['mid-forearm'] = (rad[:, 1].max() + rad[:, 1].min()) / 2
        out['wrist'] = rad[:, 1].min() + 0.005
    mc = [v for n, v in by.items() if 'metacarpal' in n.lower() and n.lower().startswith('left')]
    if mc:
        out['mid-hand'] = np.vstack(mc)[:, 1].mean()
    return {k: float(v) for k, v in out.items()}


REGION = {   # level -> x-window (m) of the local bone used for the regional alignment / bone Dice
    'C5': (-0.05, 0.05), 'T4 (nipple level)': (-0.05, 0.05), 'T10': (-0.05, 0.05), 'L3': (-0.05, 0.05),
    'S1': (-0.2, 0.2), 'pubic symphysis': (-0.2, 0.2), 'perineum': (-0.2, 0.2),
    'mid-thigh': (0.0, 0.2), 'knee': (0.0, 0.2), 'mid-calf': (0.0, 0.2),
    'mid-upper-arm': (0.12, 0.3), 'mid-forearm': (0.12, 0.3), 'wrist': (0.12, 0.3), 'mid-hand': (0.12, 0.3)}


def regional_dice(ct_bone, model_bone, xwin):
    """Bone Dice after REGIONAL alignment: both masks are restricted to the level's x-window, the CT
    mask is translated so its bone centroid matches the model's (no rotation, no scale)."""
    from scipy import ndimage
    H, W = model_bone.shape
    c0, c1 = int((xwin[0] - EXT[0]) / G), int((xwin[1] - EXT[0]) / G)
    win = np.zeros_like(model_bone); win[:, max(0, c0):min(W, c1)] = True
    a, b = ct_bone & win, model_bone & win
    if not a.any() or not b.any():
        return None, a
    off = np.round(np.array(ndimage.center_of_mass(b)) - np.array(ndimage.center_of_mass(a))).astype(int)
    a2 = np.roll(np.roll(a, off[0], 0), off[1], 1)
    return dice(a2 & win, b), a2


def ct_plane(y, reg, name='head_to_femur'):
    """Resample a VHF CT volume on the atlas plane at height y (grid EXT, 1 mm) -> HU image."""
    import SimpleITK as sitk
    if name not in CACHE:
        img = sitk.ReadImage(str(ROOT / f'work/vhf/ct_{name}.nii.gz'))
        CACHE[name] = (img, sitk.GetArrayFromImage(img))
    img, arr = CACHE[name]
    R, t = np.array(reg['R']), np.array(reg['t'])
    xs = np.arange(EXT[0], EXT[1], G); zs = np.arange(EXT[3], EXT[2], -G)
    X, Z = np.meshgrid(xs, zs)
    A = np.c_[X.ravel(), np.full(X.size, y), Z.ravel()]
    B = (A - t) @ R                     # undo the rigid registration (R orthonormal)
    lps = np.c_[B[:, 0], -B[:, 2], B[:, 1]] * 1000.0
    # physical (LPS) -> voxel index (axis-aligned direction matrix): (p - origin) / spacing
    D = np.array(img.GetDirection()).reshape(3, 3)
    idx = ((lps - np.array(img.GetOrigin())) @ D) / np.array(img.GetSpacing())
    i = np.round(idx).astype(int)
    ok = (i[:, 0] >= 0) & (i[:, 0] < arr.shape[2]) & (i[:, 1] >= 0) & (i[:, 1] < arr.shape[1]) & (i[:, 2] >= 0) & (i[:, 2] < arr.shape[0])
    hu = np.full(len(i), -1000.0)
    hu[ok] = arr[i[ok, 2], i[ok, 1], i[ok, 0]]
    return hu.reshape(X.shape), bool(ok.any())


def cryo_slice(z):
    import pydicom
    from PIL import Image
    rows = json.loads((ROOT / 'work/vhf/xc_index.json').read_text())
    r = min(rows, key=lambda q: abs(q['z'] - z))
    cache = ROOT / 'work/vhf/xc' / f"{r['z']:.2f}.png"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        u = r['url'].replace('s3://idc-open-data/', 'https://idc-open-data.s3.amazonaws.com/')
        with urllib.request.urlopen(u, timeout=300) as f:
            ds = pydicom.dcmread(io.BytesIO(f.read()), force=True)
        Image.fromarray(ds.pixel_array).save(cache)
    return np.array(Image.open(cache).convert('RGB')), r['z']


def cryo_body(rgb):
    from scipy import ndimage
    r, g, b = (rgb[..., k].astype(int) for k in range(3))
    blue = (b > r + 15) & (b > g)            # blue gelatin
    dark = (r + g + b) < 60                  # background
    body = ~(blue | dark)
    lab, n = ndimage.label(ndimage.binary_opening(body, iterations=3))
    if n == 0:
        return body
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    keep = np.isin(lab, 1 + np.where(sizes > 0.02 * sizes.max())[0])
    return ndimage.binary_fill_holes(keep)


def fit_cryo(body_px, model_mask):
    """Place the cryo body mask (0.333 mm px) on the model grid (1 mm): 3x downsample, try the 4 axis
    flips, align centroids, keep the best Dice. Returns (aligned mask, dice, flip)."""
    from scipy import ndimage
    small = body_px[::3, ::3]
    best = (None, -1, None)
    H, W = model_mask.shape
    mc = np.array(ndimage.center_of_mass(model_mask)) if model_mask.any() else np.array([H / 2, W / 2])
    for fy in (False, True):
        for fx in (False, True):
            s = small[::-1 if fy else 1, ::-1 if fx else 1]
            canvas = np.zeros_like(model_mask)
            sc = np.array(ndimage.center_of_mass(s))
            off = np.round(mc - sc).astype(int)
            ys, xs = np.nonzero(s)
            ys, xs = ys + off[0], xs + off[1]
            ok = (ys >= 0) & (ys < H) & (xs >= 0) & (xs < W)
            canvas[ys[ok], xs[ok]] = True
            d = dice(canvas, model_mask)
            if d > best[1]:
                best = (canvas, d, (fy, fx))
    return best


def main():
    import trimesh
    from PIL import Image, ImageDraw
    OUT.mkdir(parents=True, exist_ok=True)
    atlas, M = ml.load_package(ROOT / 'public/models/female/atlas.json')
    vols = json.loads((ROOT / 'work/vhf/registration.json').read_text())['volumes']
    reg, reg_legs = vols['head_to_femur'], vols['femur_to_toes']
    rows_idx = json.loads((ROOT / 'work/vhf/xc_index.json').read_text())
    z_feet = min(r['z'] for r in rows_idx) + 30.0      # first body slice ~3 cm above the block bottom (refined by search)
    skin = [ml.to_trimesh(M[p['id']]['pos'], M[p['id']]['idx']) for p in atlas['parts'] if p['name'] == 'Skin']
    bones = [ml.to_trimesh(M[p['id']]['pos'], M[p['id']]['idx']) for p in atlas['parts'] if p['system'] == 'skeletal']
    res = {}
    for name, y in levels(atlas, M).items():
        body_m = raster(section_polys(skin, y))
        bone_m = raster(section_polys(bones, y))
        # cryosection: search the height (+-40 mm) for the best shape agreement
        best = None
        for dz in range(-30, 31, 15):
            rgb, zc = cryo_slice(z_feet + y * 1000 + dz)
            aligned, d, flip = fit_cryo(cryo_body(rgb), body_m)
            if best is None or d > best[0]:
                best = (d, zc, rgb, aligned, flip)
        d_body, zc, rgb, aligned, flip = best
        hu, inside = ct_plane(y, reg)
        if not inside or not (hu > 200).any():
            hu, inside = ct_plane(y, reg_legs, 'femur_to_toes')     # leg levels: the femur->toes volume
        ct_bone = hu > 200
        d_bone, ct_aligned = regional_dice(ct_bone, bone_m, REGION.get(name, (-0.3, 0.3))) if inside and ct_bone.any() else (None, ct_bone)
        res[name] = {'y_m': y, 'cryo_z_mm': zc, 'body_dice': d_body, 'bone_dice': d_bone, 'ct_in_fov': inside}
        print(f"{name:20s} y={y:.3f} body Dice {d_body:.3f}  bone Dice {('%.3f' % d_bone) if d_bone is not None else 'n/a (outside CT)'}", flush=True)
        # overlay images: cryo (aligned to the model grid) + model outlines; CT plane + model bone outline
        H, W = body_m.shape
        small = rgb[::3, ::3][::-1 if flip[0] else 1, ::-1 if flip[1] else 1]
        from scipy import ndimage
        canvas = np.full((H, W, 3), 245, np.uint8)
        sc = np.array(ndimage.center_of_mass(cryo_body(rgb)[::3, ::3][::-1 if flip[0] else 1, ::-1 if flip[1] else 1]))
        mc = np.array(ndimage.center_of_mass(body_m)) if body_m.any() else sc
        off = np.round(mc - sc).astype(int)
        y0, x0 = max(0, off[0]), max(0, off[1])
        sy0, sx0 = max(0, -off[0]), max(0, -off[1])
        hh, ww = min(H - y0, small.shape[0] - sy0), min(W - x0, small.shape[1] - sx0)
        if hh > 0 and ww > 0:
            canvas[y0:y0 + hh, x0:x0 + ww] = small[sy0:sy0 + hh, sx0:sx0 + ww]
        edge = lambda m: m ^ ndimage.binary_erosion(m, iterations=1)
        canvas[edge(body_m)] = (0, 255, 120); canvas[edge(bone_m)] = (255, 220, 0)
        ct_img = np.clip((hu + 200) / 1400 * 255, 0, 255).astype(np.uint8)
        ct_rgb = np.stack([ct_img] * 3, -1)
        ct_rgb[edge(ct_aligned)] = (255, 60, 60)            # regionally aligned CT bone (red)
        ct_rgb[edge(bone_m)] = (255, 220, 0); ct_rgb[edge(body_m)] = (0, 255, 120)
        both = np.concatenate([canvas, ct_rgb], 1)
        im = Image.fromarray(both); dr = ImageDraw.Draw(im)
        dr.text((8, 6), f"{name}  cryosection (left) / CT (right)  green = model skin, yellow = model bones  "
                         f"body Dice {d_body:.2f}  bone Dice {d_bone if d_bone is None else round(d_bone, 2)}", fill=(0, 0, 0))
        im.save(OUT / f"{name.split(' ')[0].replace('/', '-')}_{name.replace(' ', '-').replace('(', '').replace(')', '')}.png")
    body = [r['body_dice'] for r in res.values()]
    bone = [r['bone_dice'] for r in res.values() if r['bone_dice'] is not None]
    summary = {'levels': len(res), 'body_dice_min': min(body), 'body_dice_mean': float(np.mean(body)),
               'bone_dice_min': min(bone) if bone else None, 'bone_dice_mean': float(np.mean(bone)) if bone else None,
               'body_gate_0.95': all(b >= 0.95 for b in body), 'bone_gate_0.85': bool(bone) and all(b >= 0.85 for b in bone)}
    (ROOT / 'work/vhf/sections.json').write_text(json.dumps({'summary': summary, 'levels': res}, indent=1))
    print('summary', json.dumps(summary))


if __name__ == '__main__':
    main()
