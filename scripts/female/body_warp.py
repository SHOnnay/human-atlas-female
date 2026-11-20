"""Landmark correspondences between the BodyParts3D male and the HRA female body, and the
thin-plate-spline warp that carries every male-derived structure into the female body.

Correspondences are computed identically on both bodies (same algorithm, same normalised
heights), so no landmark is hand-placed:
  * skeleton: 30 pelvic landmarks, femoral heads, greater trochanters, femoral condyles,
    epicondyles, patellae, tibial plateaus and plafonds, lateral malleoli (HRA has real bones);
  * thorax: ribs 5/8/10 lateral extremes (male) <-> HRA lung lateral extremes + rib thickness;
  * skin: torso contours (24 rays) at 12 heights between crotch and axilla, neck/head contours,
    leg contours (16 rays) at 9 heights per leg, arm axis + perimeter at 12 stations per arm,
    head extremes (vertex, nose, occiput, ears), feet (heel, toe, medial, lateral).
Breast-region torso samples are excluded on the female side so the chest wall follows the
ribs, not the breast surface; female gluteofemoral targets sit `fat_extra` m inside the skin.
"""
import numpy as np

import meshlib as ml


# ------------------------------------------------------------------ skin slicing

def loops_at(mesh, y):
    """Closed section loops of a mesh at height y, as (n,2) arrays of (x, z)."""
    sec = mesh.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    if sec is None:
        return []
    out = []
    for d in sec.discrete:
        if len(d) >= 8:
            out.append(np.asarray(d)[:, [0, 2]])
    return out


def area(loop):
    x, z = loop[:, 0], loop[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(z, 1)) - np.dot(z, np.roll(x, 1)))


def torso_loop(mesh, y):
    """Largest loop spanning the midline (x = 0)."""
    cands = [l for l in loops_at(mesh, y) if l[:, 0].min() < 0 < l[:, 0].max()]
    return max(cands, key=area) if cands else None


def side_loop(mesh, y, sign):
    cands = [l for l in loops_at(mesh, y) if np.sign(l[:, 0].mean()) == sign]
    return max(cands, key=area) if cands else None


def rays(loop, n, centre=None, start=0.0):
    """Contour points at n equal angles around `centre` (nearest-angle vertex, outermost)."""
    c = loop.mean(0) if centre is None else centre
    d = loop - c
    ang = np.arctan2(d[:, 1], d[:, 0])
    r = np.linalg.norm(d, axis=1)
    out = []
    for k in range(n):
        a = start + 2 * np.pi * k / n
        diff = np.abs((ang - a + np.pi) % (2 * np.pi) - np.pi)
        sel = diff < (np.pi / n)
        i = np.argmax(np.where(sel, r, -1)) if sel.any() else np.argmin(diff)
        out.append(loop[i])
    return np.array(out), c


def body_levels(mesh, step=0.004):
    """Key heights: crotch (legs join), axilla (arms join the torso), top of head."""
    lo, hi = mesh.bounds[0][1], mesh.bounds[1][1]
    stature = hi - lo
    crotch = None
    for y in np.arange(lo + 0.35 * stature, lo + 0.6 * stature, step):
        if torso_loop(mesh, y) is not None:
            crotch = y
            break
    axilla = None
    for y in np.arange(lo + 0.55 * stature, lo + 0.85 * stature, step):
        big = [l for l in loops_at(mesh, y) if area(l) > 2e-4]
        if len(big) >= 3:
            axilla = y
    return {'floor': lo, 'top': hi, 'crotch': crotch, 'axilla': axilla, 'stature': stature}


# ------------------------------------------------------------------ correspondences

class Correspondences:
    def __init__(self):
        self.src, self.dst, self.tags = [], [], []

    def add(self, a, b, tag):
        a, b = np.atleast_2d(a), np.atleast_2d(b)
        assert a.shape == b.shape
        self.src.append(a); self.dst.append(b); self.tags += [tag] * len(a)

    def arrays(self):
        return np.vstack(self.src), np.vstack(self.dst)


def to3(p2, y):
    return np.c_[p2[:, 0], np.full(len(p2), y), p2[:, 1]]


def skin_correspondences(male, female, lm_m, lm_f, C, breast_box, fat_extra, fat_band, normals_f):
    """Skin-surface correspondences (male skin → female skin, minus extra female fat)."""
    from scipy.spatial import cKDTree
    ftree = cKDTree(female.vertices)

    def inset(p, y_lo, y_hi):
        """Female target moved inward by the extra female subcutaneous fat in the band."""
        _, i = ftree.query(p)
        n = normals_f[i]
        depth = np.where((p[:, 1] > y_lo) & (p[:, 1] < y_hi), fat_extra, 0.002)
        return p - n * depth[:, None]

    def lev(lm, f):
        return lm['crotch'] + f * (lm['axilla'] - lm['crotch'])

    # Torso: 12 levels between crotch and axilla, 24 rays each.
    for f in np.linspace(0.05, 0.95, 12):
        ym, yf = lev(lm_m, f), lev(lm_f, f)
        lm_loop, lf_loop = torso_loop(male, ym), torso_loop(female, yf)
        if lm_loop is None or lf_loop is None:
            continue
        pm, _ = rays(lm_loop, 24)
        pf, _ = rays(lf_loop, 24)
        pm3, pf3 = to3(pm, ym), to3(pf, yf)
        keep = np.ones(len(pf3), bool)
        for lo, hi in breast_box:
            keep &= ~np.all((pf3 > lo) & (pf3 < hi), axis=1)
        C.add(pm3[keep], inset(pf3[keep], *fat_band)[0:keep.sum()], 'torso')
    # Neck and head: fractions of the axilla→top span; whole loop around the midline.
    for f in (0.25, 0.4, 0.55, 0.7, 0.85):
        ym = lm_m['axilla'] + f * (lm_m['top'] - lm_m['axilla'])
        yf = lm_f['axilla'] + f * (lm_f['top'] - lm_f['axilla'])
        a, b = torso_loop(male, ym), torso_loop(female, yf)
        if a is None or b is None:
            continue
        n = 12 if f < 0.35 else 16
        pm, _ = rays(a, n); pf, _ = rays(b, n)
        C.add(to3(pm, ym), inset(to3(pf, yf), *fat_band), 'head')
    for mesh, lm, out in ((male, lm_m, []), (female, lm_f, [])):
        v = mesh.vertices
        head = v[v[:, 1] > lm['top'] - 0.25 * (lm['top'] - lm['axilla'])]
        mid = head[np.abs(head[:, 0]) < 0.015]
        out += [head[np.argmax(head[:, 1])], mid[np.argmax(mid[:, 2])], mid[np.argmin(mid[:, 2])]]
        lm['head_pts'] = np.array(out)
    C.add(lm_m['head_pts'], lm_f['head_pts'], 'head-extremes')
    # Legs: 9 levels between ankle and crotch per side, 16 rays.
    for sign in (1, -1):
        for f in np.linspace(0.08, 0.92, 9):
            ym = lm_m['ankle'] + f * (lm_m['crotch'] - lm_m['ankle'])
            yf = lm_f['ankle'] + f * (lm_f['crotch'] - lm_f['ankle'])
            a, b = side_loop(male, ym, sign), side_loop(female, yf, sign)
            if a is None or b is None:
                continue
            pm, _ = rays(a, 16); pf, _ = rays(b, 16)
            C.add(to3(pm, ym), inset(to3(pf, yf), *fat_band), 'leg')
        # Feet: heel, toe, medial and lateral sole points.
        for mesh, lm in ((male, lm_m), (female, lm_f)):
            v = mesh.vertices
            foot = v[(v[:, 1] < lm['floor'] + 0.06) & (np.sign(v[:, 0]) == sign)]
            low = foot[foot[:, 1] < lm['floor'] + 0.02]
            lm['foot_%d' % sign] = np.array([foot[np.argmin(foot[:, 2])], foot[np.argmax(foot[:, 2])],
                                             low[np.argmin(np.abs(low[:, 0]))], low[np.argmax(np.abs(low[:, 0]))]])
        C.add(lm_m['foot_%d' % sign], lm_f['foot_%d' % sign], 'foot')
    # Arms: axis + perimeter at 12 stations from the shoulder to the fingertips.
    for sign in (1, -1):
        sm, sf = arm_stations(male, lm_m, sign), arm_stations(female, lm_f, sign)
        C.add(sm, sf, 'arm')


def arm_stations(mesh, lm, sign, n=14):
    """Arm axis and perimeter from horizontal sections: at each height below the axilla the arm
    is the most lateral loop on that side (never the torso, which spans the midline, and never
    the thigh, which is medial to the hand). Stations are equal arc-length steps along the
    centroid curve from the axilla to the fingertips; each gives the centroid + 4 rays."""
    v = mesh.vertices
    hip = torso_loop(mesh, lm['crotch'] + 0.01)
    thr = (hip[:, 0].max() if sign > 0 else -hip[:, 0].min()) + 0.015
    tips = v[sign * v[:, 0] > thr]
    y_end = tips[:, 1].min() + 0.006
    curve = []
    for y in np.arange(lm['axilla'] - 0.012, y_end, -0.006):
        cands = [l for l in loops_at(mesh, y) if np.sign(l[:, 0].mean()) == sign and not (l[:, 0].min() < 0 < l[:, 0].max())
                 and area(l) > 1.5e-5]
        if not cands:
            continue
        loop = max(cands, key=lambda l: sign * l[:, 0].mean())
        if y < lm['crotch'] + 0.02 and sign * loop[:, 0].mean() < thr:
            continue  # only the thigh is present at this height
        curve.append((y, loop))
    cent = np.array([to3(l.mean(0)[None], y)[0] for y, l in curve])
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(cent, axis=0), axis=1))]
    pts = []
    for k in range(n):
        i = int(np.argmin(np.abs(seg - seg[-1] * k / (n - 1))))
        y, loop = curve[i]
        pts.append(cent[i])
        ring, _ = rays(loop, 4)
        pts.extend(to3(ring, y))
    return np.array(pts)


def bone_points(get, prefix_l, prefix_r):
    """Lower-limb bone landmarks. get(name) -> vertices; names via prefix dicts."""
    out = {}
    for side, names in (('L', prefix_l), ('R', prefix_r)):
        sign = 1 if side == 'L' else -1
        fem = get(names['femur'])
        top = fem[fem[:, 1] > fem[:, 1].max() - 0.1]
        out['gtroch_' + side] = top[np.argmax(top[:, 0] * sign)]
        head, _ = ml.femoral_head_centre(fem)
        out['fhead_' + side] = head
        dist = fem[fem[:, 1] < fem[:, 1].min() + 0.05]
        out['condyles_' + side] = fem[fem[:, 1] < fem[:, 1].min() + 0.02].mean(0)
        out['epi_med_' + side] = dist[np.argmin(dist[:, 0] * sign)]
        out['epi_lat_' + side] = dist[np.argmax(dist[:, 0] * sign)]
        tib = get(names['tibia'])
        out['tib_top_' + side] = tib[tib[:, 1] > tib[:, 1].max() - 0.02].mean(0)
        out['tib_bottom_' + side] = tib[tib[:, 1] < tib[:, 1].min() + 0.02].mean(0)
        out['tib_tuberosity_' + side] = tib[tib[:, 1] > tib[:, 1].max() - 0.07][np.argmax(tib[tib[:, 1] > tib[:, 1].max() - 0.07][:, 2])]
        fib = get(names['fibula'])
        out['lat_malleolus_' + side] = fib[np.argmin(fib[:, 1])]
        out['patella_' + side] = get(names['patella']).mean(0)
    return out


def tps(src, dst, smoothing=1e-5):
    from scipy.interpolate import RBFInterpolator
    rbf = RBFInterpolator(src, dst - src, kernel='thin_plate_spline', smoothing=smoothing)

    def warp(p, chunk=40000):
        out = np.empty_like(p)
        for i in range(0, len(p), chunk):
            out[i:i + chunk] = p[i:i + chunk] + rbf(p[i:i + chunk])
        return out
    return warp
