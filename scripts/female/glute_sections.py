"""Milestone 9: gluteal sections of the female model against her CT.

    python scripts/female/glute_sections.py     (TotalSegmentator venv)  -> work/vhf/glute_sections.json,
                                                                            docs/screenshots/sections/glute_*.png

At S1, the pubic symphysis and mid-thigh (levels from vhf_sections.levels) the model's gluteal muscles
(maximus + medius + minimus, per side) are sliced and compared with the TotalSegmentator "total" gluteal
labels of her CT on the same plane. The CT plane is sampled through the CT->HRA rigid registration
(vhf_targets.py) and the milestone 9 pelvis-only refinement (report.json m9_pelvis_registration), so the
two are aligned on her pelvis / femur; no further alignment is applied. Dice per side and level.
Fat thickness: along 5 rays per side (posterolateral +-60 deg) from the gluteal / femoral centre, the
outermost run of the model's gluteofemoral fat vs the outermost run of CT fat (HU -190 .. -30; the donor
was CT-scanned in a gelatin block, which is ~0 HU, so the outermost fat run is the subcutaneous fat).
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

OUT = ROOT / 'docs' / 'screenshots' / 'sections'
LEVELS = ('S1', 'pubic symphysis', 'mid-thigh')


def plane_points(y):
    xs = np.arange(vs.EXT[0], vs.EXT[1], vs.G); zs = np.arange(vs.EXT[3], vs.EXT[2], -vs.G)
    X, Z = np.meshgrid(xs, zs)
    return np.c_[X.ravel(), np.full(X.size, y), Z.ravel()], X.shape


def sample(name, A, reg, delta, seg=False):
    import SimpleITK as sitk
    key = (name, seg)
    if key not in vs.CACHE:
        f = ROOT / (f'work/vhf/seg_{name}.nii' if seg else f'work/vhf/ct_{name}.nii.gz')
        img = sitk.ReadImage(str(f))
        vs.CACHE[key] = (img, sitk.GetArrayFromImage(img))
    img, arr = vs.CACHE[key]
    if delta is not None:                      # undo the pelvis refinement (applied after the CT registration)
        A = (A - delta[1]) @ delta[0]
    R, t = np.array(reg['R']), np.array(reg['t'])
    B = (A - t) @ R
    lps = np.c_[B[:, 0], -B[:, 2], B[:, 1]] * 1000.0
    D = np.array(img.GetDirection()).reshape(3, 3)
    i = np.round(((lps - np.array(img.GetOrigin())) @ D) / np.array(img.GetSpacing())).astype(int)
    ok = (i[:, 0] >= 0) & (i[:, 0] < arr.shape[2]) & (i[:, 1] >= 0) & (i[:, 1] < arr.shape[1]) & (i[:, 2] >= 0) & (i[:, 2] < arr.shape[0])
    v = np.full(len(i), 0 if seg else -1000.0)
    v[ok] = arr[i[ok, 2], i[ok, 1], i[ok, 0]]
    return v, bool(ok.any())


def section_any(meshes, y, tol=0.008):
    """Plane section that also works on the packaged (simplified, not watertight) meshes: the cut
    segments are chained end to end (gaps up to `tol` bridged) and each chain is closed."""
    import trimesh
    from scipy.spatial import cKDTree
    polys = []
    for m in meshes:
        if m.bounds[0][1] > y or m.bounds[1][1] < y:
            continue
        seg = trimesh.intersections.mesh_plane(m, [0, 1, 0], [0, y, 0])
        if not len(seg):
            continue
        seg = seg[:, :, [0, 2]]
        used = np.zeros(len(seg), bool)
        ends = cKDTree(seg.reshape(-1, 2))
        for s0 in range(len(seg)):
            if used[s0]:
                continue
            used[s0] = True
            chain = [seg[s0, 0], seg[s0, 1]]
            while True:
                cand = [j // 2 for j in ends.query_ball_point(chain[-1], tol) if not used[j // 2]]
                if not cand:
                    break
                j = cand[0]; used[j] = True
                a, b = seg[j]
                chain.append(b if np.linalg.norm(a - chain[-1]) <= np.linalg.norm(b - chain[-1]) else a)
            if len(chain) >= 4:
                polys.append(np.array(chain))
    return polys


def section_mask(meshes, y):
    """Filled cross-section of (possibly not watertight) meshes: every cut segment is drawn as a line,
    gaps up to 5 mm are closed, and the enclosed area is filled."""
    import trimesh
    from PIL import Image, ImageDraw
    from scipy import ndimage
    ext, g = vs.EXT, vs.G
    w, h = int((ext[1] - ext[0]) / g), int((ext[3] - ext[2]) / g)
    out = np.zeros((h, w), bool)
    for m in meshes:
        if m.bounds[0][1] > y or m.bounds[1][1] < y:
            continue
        seg = trimesh.intersections.mesh_plane(m, [0, 1, 0], [0, y, 0])
        if not len(seg):
            continue
        img = Image.new('L', (w, h), 0); d = ImageDraw.Draw(img)
        for a, b in seg:
            d.line([((a[0] - ext[0]) / g, (ext[3] - a[2]) / g), ((b[0] - ext[0]) / g, (ext[3] - b[2]) / g)], fill=255, width=3)
        line = np.array(img) > 0
        out |= ndimage.binary_fill_holes(ndimage.binary_closing(line, iterations=5))
    return out


def winding_mask(meshes, y):
    """Filled cross-section by the generalized winding number (> 0.5 = inside), which tolerates the
    small holes of open meshes; evaluated only on the grid points inside each mesh's x/z bounds."""
    ext, g = vs.EXT, vs.G
    w, h = int((ext[1] - ext[0]) / g), int((ext[3] - ext[2]) / g)
    out = np.zeros((h, w), bool)
    for m in meshes:
        if m.bounds[0][1] > y or m.bounds[1][1] < y:
            continue
        (x0, _, z0), (x1, _, z1) = m.bounds
        c0, c1 = int((x0 - ext[0]) / g), int((x1 - ext[0]) / g) + 1
        r0, r1 = int((ext[3] - z1) / g), int((ext[3] - z0) / g) + 1
        rr, cc = np.mgrid[max(r0, 0):min(r1, h), max(c0, 0):min(c1, w)]
        P = np.c_[ext[0] + cc.ravel() * g, np.full(cc.size, y), ext[3] - rr.ravel() * g]
        T = np.asarray(m.triangles)
        wn = np.zeros(len(P))
        for k in range(0, len(P), 400):
            a = T[None, :, 0] - P[k:k + 400, None]; b = T[None, :, 1] - P[k:k + 400, None]; c = T[None, :, 2] - P[k:k + 400, None]
            la, lb, lc = (np.linalg.norm(v, axis=2) for v in (a, b, c))
            num = np.einsum('ijk,ijk->ij', a, np.cross(b, c))
            den = la * lb * lc + np.einsum('ijk,ijk->ij', a, b) * lc + np.einsum('ijk,ijk->ij', b, c) * la + np.einsum('ijk,ijk->ij', c, a) * lb
            wn[k:k + 400] = np.arctan2(num, den).sum(1) / (2 * np.pi)
        inside = np.abs(wn) > 0.5
        out[rr.ravel()[inside], cc.ravel()[inside]] = True
    return out


def runs(mask_line):
    """Outermost run of True along a ray (index 0 = centre)."""
    idx = np.where(mask_line)[0]
    if not len(idx):
        return 0
    end = idx[-1]; start = end
    while start - 1 >= 0 and mask_line[start - 1]:
        start -= 1
    return end - start + 1


def main():
    from PIL import Image, ImageDraw
    from scipy import ndimage
    from totalsegmentator.map_to_binary import class_map
    labels = class_map['total']
    OUT.mkdir(parents=True, exist_ok=True)
    atlas, M = ml.load_package(ROOT / 'public/models/female/atlas.json')
    pre = __import__('os').environ.get('HA_DUMP')
    if pre:
        # The packaged gluteals are simplified (<= 2 mm) and no longer closed, so their sections leak.
        # With HA_DUMP (the build's pre-packaging dump, build_female.py) the gluteals are sliced as
        # fitted: dumped positions on the BodyParts3D topology.
        import pickle
        dump = pickle.loads(Path(pre).read_bytes())
        _, male = ml.load_package(ROOT / 'public/models/atlas.json')
        for p in atlas['parts']:
            if re.fullmatch(r'(Left|Right) gluteus (maximus|medius|minimus)', p['name']) and p['id'] in dump:
                M[p['id']] = {'pos': dump[p['id']], 'idx': male[p['id']]['idx']}
    rep = json.loads((ROOT / 'work/female/report.json').read_text())
    pr = rep.get('m9_pelvis_registration', {})
    delta = (np.array(pr['R']), np.array(pr['t'])) if 'R' in pr else None
    vols = json.loads((ROOT / 'work/vhf/registration.json').read_text())['volumes']
    lev = vs.levels(atlas, M)
    res = {}
    for lv in LEVELS:
        y = lev[lv]
        A, shape = plane_points(y)
        hu, inside = sample('head_to_femur', A, vols['head_to_femur'], delta)
        sg, _ = sample('head_to_femur', A, vols['head_to_femur'], delta, seg=True)
        vol = 'head_to_femur'
        if not inside or not (hu > 200).any():
            hu, inside = sample('femur_to_toes', A, vols['femur_to_toes'], None)
            sg = np.zeros(len(A)); vol = 'femur_to_toes (no gluteal labels)'
        hu = hu.reshape(shape); sg = sg.reshape(shape)
        row = {'y_m': y, 'ct_volume': vol}
        skin = [ml.to_trimesh(M[p['id']]['pos'], M[p['id']]['idx']) for p in atlas['parts'] if p['name'] == 'Skin']
        body = ndimage.binary_dilation(vs.raster(vs.section_polys(skin, y)), iterations=3)
        img = np.stack([np.clip((hu + 200) / 1400 * 255, 0, 255).astype(np.uint8)] * 3, -1)
        edge = lambda m: m ^ ndimage.binary_erosion(m, iterations=1)
        for side, sgn in (('Left', 1), ('Right', -1)):
            mus = [ml.to_trimesh(M[p['id']]['pos'], M[p['id']]['idx']) for p in atlas['parts']
                   if re.fullmatch(f'{side} gluteus (maximus|medius|minimus)', p['name'])]
            model = winding_mask(mus, y)
            ids = [k for k, l in labels.items() if re.fullmatch(f'gluteus_(maximus|medius|minimus)_{side.lower()}', l)]
            ct = np.isin(sg, ids)
            d = vs.dice(model, ct) if (model.any() or ct.any()) else None
            row[f'{side} gluteal Dice'] = None if (d is None or np.isnan(d)) else d
            row[f'{side} model area cm2'] = float(model.sum() * vs.G ** 2 * 1e4)
            row[f'{side} CT area cm2'] = float(ct.sum() * vs.G ** 2 * 1e4)
            img[edge(ct)] = (255, 60, 60); img[edge(model)] = (255, 220, 0)
            # fat thickness
            fat = [ml.to_trimesh(M[p['id']]['pos'], M[p['id']]['idx']) for p in atlas['parts'] if p['name'] == f'{side} gluteofemoral subcutaneous fat']
            fm = section_mask(fat, y) if fat else np.zeros(shape, bool)
            img[edge(fm)] = (0, 255, 120)
            if model.any():
                cy, cx = ndimage.center_of_mass(model)
            else:
                fem = [M[p['id']]['pos'] for p in atlas['parts'] if p['name'] == f'{side} femur'][0]
                sl = fem[np.abs(fem[:, 1] - y) < 0.01]
                cx = (sl[:, 0].mean() - vs.EXT[0]) / vs.G; cy = (vs.EXT[3] - sl[:, 2].mean()) / vs.G
            ctfat = (hu > -190) & (hu < -30)
            mt, cth = [], []
            g = np.array([sgn * 0.45, -0.89]); g /= np.linalg.norm(g)
            for a in np.radians([-60, -30, 0, 30, 60]):
                ca, sa = np.cos(a), np.sin(a)
                dx, dz = g[0] * ca - g[1] * sa, g[0] * sa + g[1] * ca
                s = np.arange(0, 250)
                px = np.round(cx + dx * s).astype(int); py = np.round(cy - dz * s).astype(int)
                ok = (px >= 0) & (px < shape[1]) & (py >= 0) & (py < shape[0])
                px, py = px[ok], py[ok]
                inb = body[py, px]                 # stop at her skin (+3 mm): never reach the hanging arm
                stop = np.argmax(~inb) if (~inb).any() else len(inb)
                px, py = px[:stop], py[:stop]
                mt.append(runs(fm[py, px])); cth.append(runs(ctfat[py, px]))
                img[py, px] = (90, 160, 255)
            row[f'{side} fat thickness model mm (5 rays)'] = mt
            row[f'{side} fat thickness CT mm (5 rays)'] = cth
            row[f'{side} fat thickness median model / CT mm'] = [float(np.median(mt)), float(np.median(cth))]
        res[lv] = row
        im = Image.fromarray(img); dr = ImageDraw.Draw(im)
        dr.text((8, 6), f"{lv}  CT (grey)  red = CT gluteal muscles  yellow = model gluteal muscles  green = model gluteofemoral fat  blue = thickness rays", fill=(255, 255, 255))
        im.save(OUT / f"glute_{lv.replace(' ', '-')}.png")
        print(lv, json.dumps(row, default=float), flush=True)
    (ROOT / 'work/vhf/glute_sections.json').write_text(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
