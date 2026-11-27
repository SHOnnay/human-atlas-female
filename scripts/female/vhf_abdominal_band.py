"""Milestone 10: her anterior / lateral abdominal wall from the VHF CT (raw HU only).

    python scripts/female/vhf_abdominal_band.py      (TotalSegmentator venv: SimpleITK)
        -> work/vhf/abdominal_band.npz

For every height y (3 mm steps, pubis to above the xiphoid, build frame = the CT -> HRA registration of
vhf_targets.py) and every angle theta (1.5 deg steps, 0 = anterior, +- 130 deg), a ray is cast from the
CT body centre of that slice. Walking inward from outside:
  - the outermost fat run (HU -190..-30, >= 4 mm, gaps <= 1 mm bridged) is the subcutaneous fat; its
    outer end is her skin (r_skin);
  - the first soft-tissue run inside it (HU -10..150) starts the musculo-aponeurotic wall (r_out);
  - the wall ends at gas, bone, or fat > 4 mm (thinner fat planes between the layers are crossed when >= 1.5 mm
    of muscle follows) (r_in). Walls thicker than 30 mm (an organ
    lying against the wall, e.g. the liver) are marked invalid and filled from their neighbours.
No TotalSegmentator label is used (the `total` task has no abdominal wall muscles).
Courtesy of the U.S. National Library of Medicine (VHF data).
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import glute_sections as gs  # noqa: E402

STEP = 0.0005
RMAX = 0.30


def runs(mask):
    """(start, end) index pairs of True runs."""
    d = np.diff(np.r_[0, mask.astype(np.int8), 0])
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def bridge(mask, gap):
    m = mask.copy()
    rr = runs(~mask)
    for a, b in rr:
        if a > 0 and b < len(mask) and b - a <= gap:
            m[a:b] = True
    return m


def wall(h):
    """h: HU from the centre outward (STEP spacing). Returns r_skin, r_out, r_in (m) or nan."""
    fat = bridge((h > -190) & (h < -30), 2)
    soft = (h > -10) & (h < 150)
    gas = h < -400
    bone = h > 250
    fr = [(a, b) for a, b in runs(fat) if b - a >= 8]
    if not fr:
        return np.nan, np.nan, np.nan
    a, b = fr[-1]                                  # outermost subcutaneous fat run
    r_skin = b * STEP + 0.0015
    i = a - 1
    while i > 0 and not soft[i]:                   # thin fascia / partial volume between fat and muscle
        if a - i > 6:
            return r_skin, np.nan, np.nan
        i -= 1
    r_out = (i + 1) * STEP
    k = i
    while k > 0:
        if bone[k]:
            break
        if gas[k]:
            break
        if fat[k]:
            j = k
            while j > 0 and fat[j]:
                j -= 1
            # the fat planes between external oblique, internal oblique and transversus are thin: up to 4 mm
            # of fat is crossed when at least 1.5 mm of muscle follows; otherwise the wall ends here
            nxt = j
            while nxt > 0 and soft[nxt]:
                nxt -= 1
            if k - j > 8 or j - nxt < 3:
                break
            k = j
            continue
        k -= 1
    r_in = (k + 1) * STEP
    if r_out - r_in > 0.030 or r_out - r_in < 0.0008:
        return r_skin, np.nan, np.nan
    return r_skin, r_out, r_in


def main():
    from scipy import ndimage
    vols = json.loads((ROOT / 'work/vhf/registration.json').read_text())['volumes']
    reg = vols['head_to_femur']
    ys = np.arange(0.76, 1.34, 0.003)
    th = np.radians(np.arange(-130, 130.01, 1.5))
    s = np.arange(0, RMAX, STEP)
    out = {k: np.full((len(ys), len(th)), np.nan) for k in ('r_skin', 'r_out', 'r_in')}
    cen = np.full((len(ys), 2), np.nan)
    for iy, y in enumerate(ys):
        A, shape = gs.plane_points(y)
        hu, inside = gs.sample('head_to_femur', A, reg, None)
        if not inside:
            continue
        tissue = ((hu > -190) & (hu < 300)).reshape(shape)
        # torso only: a 10 mm opening cuts the arms (lying beside her in the CT) off the trunk
        lab, n = ndimage.label(ndimage.binary_opening(ndimage.binary_fill_holes(tissue), iterations=10))
        if not n:
            continue
        big = lab == (np.argmax(np.bincount(lab.ravel())[1:]) + 1)
        torso = ndimage.binary_dilation(big, iterations=12) & ndimage.binary_fill_holes(tissue)
        lab2, _ = ndimage.label(torso)
        torso = lab2 == lab2[big][0] if big.any() else torso
        rr, cc = np.nonzero(big)
        cx = gs.vs.EXT[0] + cc.mean() * gs.vs.G; cz = gs.vs.EXT[3] - rr.mean() * gs.vs.G
        cen[iy] = (cx, cz)
        for it, t in enumerate(th):
            P = np.c_[cx + np.sin(t) * s, np.full(len(s), y), cz + np.cos(t) * s]
            h, _ = gs.sample('head_to_femur', P, reg, None)
            ci = np.round((P[:, 0] - gs.vs.EXT[0]) / gs.vs.G).astype(int); ri = np.round((gs.vs.EXT[3] - P[:, 2]) / gs.vs.G).astype(int)
            ok = (ci >= 0) & (ci < shape[1]) & (ri >= 0) & (ri < shape[0])
            inT = np.zeros(len(s), bool); inT[ok] = torso[ri[ok], ci[ok]]
            if inT.any():
                last = np.where(inT)[0][-1]
                h = h.copy(); h[last + 6:] = -1000          # nothing beyond her torso surface (no arm)
            out['r_skin'][iy, it], out['r_out'][iy, it], out['r_in'][iy, it] = wall(h)
        if iy % 20 == 0:
            ok = np.isfinite(out['r_out'][iy]).mean()
            print('y %.3f valid %.2f' % (y, ok), flush=True)
    np.savez(ROOT / 'work/vhf/abdominal_band.npz', y=ys, theta=th, centre=cen, **out)
    print('saved', {k: float(np.isfinite(v).mean()) for k, v in out.items()})


if __name__ == '__main__':
    main()
