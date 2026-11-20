"""Gate A: body measurements of the packaged male and female models, same code for both.

    python scripts/female/measure.py      -> work/female/measurements.json (+ table on stdout)

All values come from the optimized packages in public/models (what the viewer shows).
Reference ranges and their sources are in REFERENCE below and in VERIFICATION.md.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import body_warp as bw  # noqa: E402
import meshlib as ml  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

# Adult female reference ranges (approximate; sources in VERIFICATION.md, "Reference ranges").
REFERENCE = {
    'height_cm': (150, 178, 'NHANES 2015-2018 adult women, ~5th-95th percentile (Fryar et al. 2021)'),
    'biacromial_cm': (32, 41, 'ANSUR II female biacromial breadth (over the acromia, on the skin), mean ~36.5 cm, ±2.5 SD (Gordon et al. 2014)'),
    'ribcage_width_cm': (22, 30, 'Skeletal thoracic width, adult women (Bellemare et al. 2003, Am J Respir Crit Care Med 168:305)'),
    'waist_circumference_cm': (62, 110, 'NHANES 2015-2018 adult women waist circumference, ~5th-95th percentile'),
    'bi_iliac_cm': (25, 32, 'Intercristal distance, female pelvimetry (~26-28 cm; Gray\'s Anatomy 42nd ed.; obstetric texts)'),
    'bitrochanteric_cm': (29, 37, 'Bitrochanteric breadth, adult women (obstetric/anthropometric texts, ~31-33 cm)'),
    'shoulder_hip_ratio': (0.85, 1.10, 'Biacromial / hip breadth (skin); ANSUR II female means ~36.5 / ~37 cm give ~1.0, male ~1.15-1.25 (Gordon et al. 2014)'),
    'inlet_transverse_cm': (11.5, 14.5, 'Pelvic inlet transverse diameter, female ~13-13.5 cm (Gray\'s; Williams Obstetrics)'),
    'inlet_ap_cm': (10.0, 12.5, 'True conjugate, female ~11 cm (Gray\'s; Williams Obstetrics)'),
    'subpubic_angle_deg': (80, 100, 'Female subpubic angle 80-90°+, male ~50-60° (Gray\'s Anatomy 42nd ed.)'),
    'q_angle_deg': (11, 21, 'Q-angle women 15.8 ± 4.5° (Horton & Hall 1989, Phys Ther 69:897)'),
}


def parts(atlas, meshes, pattern):
    pat = re.compile(pattern, re.I)
    sel = [p for p in atlas['parts'] if pat.search(p['name'])]
    return np.vstack([meshes[p['id']]['pos'] for p in sel]) if sel else None


def one(atlas, meshes, name):
    for p in atlas['parts']:
        if p['name'].lower() == name.lower():
            return meshes[p['id']]['pos']
    raise KeyError(name)


def subpubic_angle(hip_l, hip_r, lm):
    """Subpubic angle as on an AP pelvic radiograph: in the coronal projection, a line is fitted
    to the medial border of each inferior pubic ramus from 8 to 35 mm below the arch apex; the
    angle between the two lines is reported."""
    pts = np.vstack([hip_l, hip_r])
    cx = (lm['symphysis_bottom_L'][0] + lm['symphysis_bottom_R'][0]) / 2
    # Arch apex in projection: the lowest bone point on the midline (top of the gap).
    mid = pts[np.abs(pts[:, 0] - cx) < 0.003]
    apex = mid[np.argmin(mid[:, 1])].copy(); apex[0] = cx
    lines = []
    for sign in (1, -1):
        rows = []
        for depth in np.arange(0.008, 0.035, 0.002):
            sel = (np.abs(pts[:, 1] - (apex[1] - depth)) < 0.001) & (np.sign(pts[:, 0] - apex[0]) == sign)
            if sel.sum() >= 2:
                rows.append((depth, np.abs(pts[sel, 0] - apex[0]).min()))
        rows = np.array(rows)
        slope = np.polyfit(rows[:, 0], rows[:, 1], 1)[0]      # lateral spread per mm of depth
        lines.append(np.degrees(np.arctan(slope)))
    return float(sum(lines))


def promontory(sacrum):
    """Most anterior midline point of the upper sacrum (S1 body), not the spinous crest."""
    mid = sacrum[np.abs(sacrum[:, 0] - np.median(sacrum[:, 0])) < 0.01]
    top = mid[mid[:, 1] > mid[:, 1].max() - 0.04]
    return top[np.argmax(top[:, 2])]


def inlet(hip_l, hip_r, sacrum, lm):
    """Inlet transverse and AP (true conjugate). The brim plane passes through the promontory and
    the top of the symphysis; parallel planes from 15 mm below to 5 mm above are cut, and the
    narrowest ring's greatest width is the transverse diameter (above the brim the iliac fossae
    would widen it)."""
    prom = promontory(sacrum)
    sym_top = (lm['symphysis_top_L'] + lm['symphysis_top_R']) / 2
    hips = np.vstack([hip_l, hip_r])
    mid_sym = hips[(np.abs(hips[:, 0] - sym_top[0]) < 0.01) & (np.abs(hips[:, 1] - sym_top[1]) < 0.025)]
    ap = float(np.linalg.norm(mid_sym - prom, axis=1).min()) if len(mid_sym) else float(np.linalg.norm(sym_top - prom))
    a = sym_top - prom; a /= np.linalg.norm(a)
    n = np.cross(a, [1.0, 0, 0]); n /= np.linalg.norm(n)
    if n[1] < 0:
        n = -n
    L = np.linalg.norm(sym_top - prom)
    cx = (prom[0] + sym_top[0]) / 2
    widths = []
    for off in np.arange(-0.015, 0.0051, 0.0025):
        rel = hips - prom
        band = hips[np.abs(rel @ n - off) < 0.003]
        t = (band - prom) @ a
        w = 0.0
        for s in np.arange(0.2, 0.8, 0.02) * L:
            sl = band[np.abs(t - s) < 0.004]
            # Only bone that can belong to the true-pelvis ring (inlet half-width < 9 cm).
            lft = sl[(sl[:, 0] > cx + 0.01) & (sl[:, 0] < cx + 0.09)]
            rgt = sl[(sl[:, 0] < cx - 0.01) & (sl[:, 0] > cx - 0.09)]
            if len(lft) and len(rgt):
                w = max(w, lft[:, 0].min() - rgt[:, 0].max())
        if w > 0:
            widths.append(w)
    return float(min(widths)), ap


def q_angle(asis, patella, tuberosity):
    a = (patella - asis)[:2]; b = (tuberosity - patella)[:2]
    return float(np.degrees(np.arccos(a @ b / np.linalg.norm(a) / np.linalg.norm(b))))


def waist(skin, y_lo, y_hi):
    best = None
    for y in np.arange(y_lo, y_hi, 0.005):
        loop = bw.torso_loop(skin, y)
        if loop is None:
            continue
        per = float(np.linalg.norm(np.diff(np.vstack([loop, loop[:1]]), axis=0), axis=1).sum())
        if best is None or per < best[0]:
            best = (per, float(np.ptp(loop[:, 0])), float(y))
    return best


def measure(path, female):
    atlas, M = ml.load_package(path)
    skin = ml.to_trimesh(*[M[[p['id'] for p in atlas['parts'] if p['name'] == 'Skin'][0]][k] for k in ('pos', 'idx')])
    if female:
        hip_l = parts(atlas, M, r'^left (ilium|ischium|pubis)$'); hip_r = parts(atlas, M, r'^right (ilium|ischium|pubis)$')
        sac = parts(atlas, M, r'sacrum')
    else:
        hip_l, hip_r, sac = one(atlas, M, 'Left hip bone'), one(atlas, M, 'Right hip bone'), one(atlas, M, 'Sacrum')
    fl, fr = one(atlas, M, 'Left femur'), one(atlas, M, 'Right femur')
    hl, _ = ml.femoral_head_centre(fl); hr, _ = ml.femoral_head_centre(fr)
    lm = ml.pelvis_landmarks(hip_l, hip_r, sac, hl, hr)
    out = {}
    out['height_cm'] = float(np.ptp(skin.vertices[:, 1]) * 100)
    sl, sr = one(atlas, M, 'Left scapula'), one(atlas, M, 'Right scapula')
    # Anthropometric biacromial breadth: between the skin points over the two acromion tips.
    from scipy.spatial import cKDTree
    tree = cKDTree(skin.vertices)
    acr = [s[np.argmax(s[:, 0] * sign)] for s, sign in ((sl, 1), (sr, -1))]
    over = [skin.vertices[tree.query(p + np.array([0.015 * sign, 0.01, 0]))[1]] for p, sign in zip(acr, (1, -1))]
    out['biacromial_cm'] = float(np.linalg.norm(over[0] - over[1]) * 100)
    out['biacromial_skeletal_cm'] = float(np.linalg.norm(acr[0] - acr[1]) * 100)
    ribs = parts(atlas, M, r'^(left|right) \w+ rib$')
    out['ribcage_width_cm'] = float(np.ptp(ribs[:, 0]) * 100)
    lowest_rib = ribs[:, 1].min()
    w = waist(skin, lm['iliac_crest_L'][1] + 0.01, lowest_rib + 0.02)
    out['waist_circumference_cm'] = w[0] * 100
    out['waist_breadth_cm'] = w[1] * 100
    out['bi_iliac_cm'] = float(np.linalg.norm(lm['iliac_lateral_L'] - lm['iliac_lateral_R']) * 100)
    gt = lambda f, s: f[f[:, 1] > f[:, 1].max() - 0.1][np.argmax(f[f[:, 1] > f[:, 1].max() - 0.1][:, 0] * s)]
    out['bitrochanteric_cm'] = float(np.linalg.norm(gt(fl, 1) - gt(fr, -1)) * 100)
    # Hip breadth over the skin at the level of the greater trochanters (torso loop).
    yt = (gt(fl, 1)[1] + gt(fr, -1)[1]) / 2
    loop = None
    for dy in (0, 0.01, -0.01, 0.02):
        loop = bw.torso_loop(skin, yt + dy)
        if loop is not None:
            break
    out['hip_breadth_skin_cm'] = float(np.ptp(loop[:, 0]) * 100)
    out['shoulder_hip_ratio'] = out['biacromial_cm'] / out['hip_breadth_skin_cm']
    tw, ap = inlet(hip_l, hip_r, sac, lm)
    # Transverse inlet diameter: between the arcuate lines (most medial bone 3 cm above each
    # acetabular centre), the conventional landmark estimate; the plane-cut value is kept for reference.
    out['inlet_transverse_cm'] = float(np.linalg.norm(lm['inlet_lateral_L'] - lm['inlet_lateral_R']) * 100)
    out['inlet_transverse_planecut_cm'] = tw * 100
    out['inlet_ap_cm'] = ap * 100
    out['subpubic_angle_deg'] = subpubic_angle(hip_l, hip_r, lm)
    qs = []
    for side in ('Left', 'Right'):
        pat = one(atlas, M, f'{side} patella').mean(0)
        tib = one(atlas, M, f'{side} tibia')
        ytop = tib[:, 1].max()
        band = tib[(tib[:, 1] < ytop - 0.02) & (tib[:, 1] > ytop - 0.06)]   # tuberosity: 2-6 cm below the plateau
        tub = band[np.argmax(band[:, 2])]
        qs.append(q_angle(lm['asis_' + side[0]], pat, tub))
    out['q_angle_deg'] = float(np.mean(qs))
    out['q_angle_LR_deg'] = qs
    out['acetabular_width_cm'] = float(np.linalg.norm(hl - hr) * 100)
    # Femoral shaft obliquity: femoral head centre -> condylar centre, angle from vertical (coronal).
    obl = []
    for f, h in ((fl, hl), (fr, hr)):
        cond = f[f[:, 1] < f[:, 1].min() + 0.02].mean(0)
        d = (h - cond)[:2]
        obl.append(float(np.degrees(np.arctan2(abs(d[0]), d[1]))))
    out['femoral_obliquity_deg'] = float(np.mean(obl))
    out['knee_separation_cm'] = float(abs(fl[fl[:, 1] < fl[:, 1].min() + 0.02].mean(0)[0] - fr[fr[:, 1] < fr[:, 1].min() + 0.02].mean(0)[0]) * 100)
    return out


def main():
    male = measure(ROOT / 'public/models/atlas.json', False)
    female = measure(ROOT / 'public/models/female/atlas.json', True)
    rows = []
    for k, (lo, hi, src) in REFERENCE.items():
        f = female[k]
        rows.append({'measure': k, 'male': male[k], 'female': f, 'range': [lo, hi], 'in_range': lo <= f <= hi, 'source': src})
    res = {'male': male, 'female': female, 'rows': rows, 'all_in_range': all(r['in_range'] for r in rows)}
    (ROOT / 'work/female').mkdir(parents=True, exist_ok=True)
    (ROOT / 'work/female/measurements.json').write_text(json.dumps(res, indent=1))
    for r in rows:
        print(f"{r['measure']:24s} male {r['male']:7.1f}  female {r['female']:7.1f}  range {r['range']}  {'PASS' if r['in_range'] else 'FAIL'}")
    print('ALL IN RANGE' if res['all_in_range'] else 'SOME OUT OF RANGE')


if __name__ == '__main__':
    main()
