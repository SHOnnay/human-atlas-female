"""Milestone 10 (hybrid): abdominal wall at her real depth, and one continuous subcutaneous fat layer.

abdominal_wall     - CT band (work/vhf/abdominal_band.npz, from vhf_abdominal_band.py) placed with ONE local
                     rigid refinement on her pelvis and lower ribs. The BodyParts3D external oblique and
                     linea alba are moved radially onto it (their own thickness kept; over the rectus the
                     external oblique is its aponeurosis, 1 mm). Rectus abdominis, internal oblique and
                     transversus abdominis do not exist in BodyParts3D / HRA: they are GENERATED from her CT
                     band (approximate). The lateral band under the external oblique is split internal
                     oblique : transversus = 5.95 : 3.4 (mean resting thickness in 81 women, Tahan et al.
                     2016, J Physiol Anthropol 35:17). Tendinous intersections and inguinal ligaments are
                     generated from standard anatomy (approximate).
subcutaneous_fat   - one closed layer: the packaged skin (simplified exactly as the packager will, see
                     simplify_like_package.mjs) offset inward by 1 mm (outer surface) and by 1 mm + t (inner
                     surface), t = distance to the deep envelope (all deep parts; superficial veins and
                     cutaneous nerves excluded). Two nested surfaces of the same closed skin: no boundary edge.
Courtesy of the U.S. National Library of Medicine (VHF data).
"""
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

import meshlib as ml
import glute_fit as gf

ROOT = Path(__file__).resolve().parents[2]
LOCAL = {}
# Tahan N et al. Measurement of superficial and deep abdominal muscle thickness: an ultrasonography study.
# J Physiol Anthropol 2016;35:17 (81 women; resting, anterior axillary line): EO 4.8, IO 6.1 / 5.8, TrA 3.5 / 3.3 mm.
IO_SHARE = 5.95 / (5.95 + 3.4)
EO_SHARE = 4.8 / (4.8 + 5.95 + 3.4)
APPROX = 'approximate'
NOTE_CT = ('Generated · approximate: built from her CT abdominal wall band (VHF, raw HU); the band under the external '
           'oblique is split internal oblique : transversus abdominis by typical thickness ratios (Tahan et al. 2016, '
           'J Physiol Anthropol 35:17, 81 women). Not present in BodyParts3D or HRA.')
NOTE_STD = 'Generated · approximate: placed from standard anatomical descriptions on her bones and CT abdominal wall.'


# ----------------------------------------------------------------------------------------- utilities
def package_like(pos, idx):
    """The mesh exactly as scripts/optimize-anatomy.mjs will simplify it (same call, same bound)."""
    tmp = Path(tempfile.mkdtemp())
    a = np.ascontiguousarray(pos, np.float32); i = np.ascontiguousarray(idx, np.uint32).ravel()
    (tmp / 'in.bin').write_bytes(np.array([len(a), len(i)], np.uint32).tobytes() + a.tobytes() + i.tobytes())
    subprocess.run(['node', str(Path(__file__).parent / 'simplify_like_package.mjs'), str(tmp / 'in.bin'), str(tmp / 'out.bin')],
                   check=True, cwd=ROOT)
    b = (tmp / 'out.bin').read_bytes()
    vc, ic = (int(x) for x in np.frombuffer(b[:8], np.uint32))
    P = np.frombuffer(b[8:8 + vc * 12], np.float32).reshape(-1, 3).astype(np.float64)
    I = np.frombuffer(b[8 + vc * 12:8 + vc * 12 + ic * 4], np.uint32).astype(np.int64)
    return P, I


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def nanfill(A, sigma=(2, 2), rounds=4):
    """Fill NaNs by normalized Gaussian convolution, then smooth."""
    from scipy import ndimage
    A = A.copy()
    for _ in range(rounds):
        m = np.isfinite(A)
        if m.all():
            break
        num = ndimage.gaussian_filter(np.where(m, A, 0), sigma)
        den = ndimage.gaussian_filter(m.astype(float), sigma)
        f = num / np.maximum(den, 1e-9)
        A[~m & (den > 0.05)] = f[~m & (den > 0.05)]
        sigma = (sigma[0] * 2, sigma[1] * 2)
    m = np.isfinite(A)
    if not m.all():
        A[~m] = np.nanmedian(A)
    return A


def slab(O, I):
    """Closed mesh from an outer and an inner (nu, nv, 3) grid: two surfaces + four side strips."""
    nu, nv = O.shape[:2]
    V = np.vstack([O.reshape(-1, 3), I.reshape(-1, 3)])
    n = nu * nv
    g = lambda u, v: u * nv + v
    F = []
    for u in range(nu - 1):
        for v in range(nv - 1):
            a, b, c, d = g(u, v), g(u + 1, v), g(u + 1, v + 1), g(u, v + 1)
            F += [[a, b, c], [a, c, d], [a + n, c + n, b + n], [a + n, d + n, c + n]]
    ring = [g(u, 0) for u in range(nu)] + [g(nu - 1, v) for v in range(1, nv)] + \
           [g(u, nv - 1) for u in range(nu - 2, -1, -1)] + [g(0, v) for v in range(nv - 2, 0, -1)]
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        F += [[a, b + n, b], [a, a + n, b + n]]
    import trimesh
    m = trimesh.Trimesh(V, np.array(F), process=True)
    trimesh.repair.fix_normals(m)
    return np.asarray(m.vertices), np.asarray(m.faces).reshape(-1)


def tube(C, radius, seg=10):
    """Closed tube along polyline C (n, 3)."""
    n = len(C)
    T = np.gradient(C, axis=0); T /= np.linalg.norm(T, axis=1)[:, None]
    a = np.cross(T, [0, 1.0, 0]); a[np.linalg.norm(a, axis=1) < 1e-6] = [1, 0, 0]
    a /= np.linalg.norm(a, axis=1)[:, None]; b = np.cross(T, a)
    ang = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    R = radius * np.ones(n); R[0] = R[-1] = radius * 0.5
    V = (C[:, None] + R[:, None, None] * (np.cos(ang)[None, :, None] * a[:, None] + np.sin(ang)[None, :, None] * b[:, None])).reshape(-1, 3)
    F = []
    for i in range(n - 1):
        for j in range(seg):
            p, q = i * seg + j, i * seg + (j + 1) % seg
            F += [[p, q, q + seg], [p, q + seg, p + seg]]
    c0, c1 = len(V), len(V) + 1
    V = np.vstack([V, C[0], C[-1]])
    for j in range(seg):
        F += [[c0, (j + 1) % seg, j], [c1, (n - 1) * seg + j, (n - 1) * seg + (j + 1) % seg]]
    import trimesh
    m = trimesh.Trimesh(V, np.array(F), process=True)
    trimesh.repair.fix_normals(m)
    return np.asarray(m.vertices), np.asarray(m.faces).reshape(-1)


def diffuse(D, idx, fixed, rounds=10):
    import trimesh
    nb = trimesh.Trimesh(np.zeros((len(D), 3)) + np.arange(len(D))[:, None] * 1e-6, idx.reshape(-1, 3), process=False).vertex_neighbors
    return gf._diffuse(D, nb, fixed, rounds)


# ---------------------------------------------------------------------------------- registration
def local_delta(F, M, report):
    """ONE rigid refinement of the CT on her pelvis and lower ribs (7-12), for the abdominal wall only."""
    import trimesh  # noqa: F401
    ribs_m = [m['pos'] for m in M.values() if re.fullmatch(r'(Left|Right) (seventh|eighth|ninth|tenth|eleventh|twelfth) rib', m['name'])]
    pel = [f['pos'] for n, f in F.items() if re.search(r'^VH_F_((ilium|ischium|pubis)_compact_bone_[LR]|sacrum)$', n)]
    model = np.vstack(pel + ribs_m)
    labels = ['hip_left', 'hip_right', 'sacrum'] + [f'rib_{s}_{k}' for s in ('left', 'right') for k in range(7, 13)]
    ct = np.vstack([np.asarray(gf._target(l)[0].vertices) for l in labels])
    ct = ct[:: max(1, len(ct) // 50000)]
    tree = cKDTree(model)
    d0 = tree.query(ct)[0]
    R, t = np.eye(3), np.zeros(3)
    X = ct.copy()
    for _ in range(40):
        d, j = tree.query(X)
        ok = d < np.percentile(d, 90)
        r, tt = gf._rigid(X[ok], model[j[ok]])
        X = X @ r.T + tt
        R, t = r @ R, r @ t + tt
    d1 = tree.query(X)[0]
    LOCAL.update(R=R, t=t)
    report['m10_local_registration'] = {
        'bones': 'CT hip_left, hip_right, sacrum, ribs 7-12 -> HRA pelvis + her ribs 7-12',
        'rotation_deg': float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))), 'translation_mm': (t * 1000).tolist(),
        'median_mm_before': float(np.median(d0) * 1000), 'median_mm_after': float(np.median(d1) * 1000),
        'R': R.tolist(), 't': t.tolist()}
    print('m10 local registration', {k: v for k, v in report['m10_local_registration'].items() if k not in ('R', 't')}, flush=True)


def to_ct(X):
    return (X - LOCAL['t']) @ LOCAL['R']


def from_ct(X):
    return X @ LOCAL['R'].T + LOCAL['t']


class Band:
    """Her CT abdominal wall in polar form (CT frame): r_out / r_in / r_skin over (y, theta)."""

    def __init__(self, skin=None):
        from scipy.interpolate import RegularGridInterpolator as RGI
        d = np.load(ROOT / 'work/vhf/abdominal_band.npz')
        self.y, self.th = d['y'], d['theta']
        cen = d['centre']
        ok = np.isfinite(cen[:, 0])
        self.cx = np.interp(self.y, self.y[ok], cen[ok, 0]); self.cz = np.interp(self.y, self.y[ok], cen[ok, 1])
        from scipy.ndimage import median_filter
        self.valid = np.isfinite(d['r_out']) & np.isfinite(d['r_in'])
        self.r_model_skin = None
        if skin is not None:
            # her arms lie against the trunk in the CT: a CT reading outside her own torso skin (model, first
            # hit from the slice centre) + 25 mm is an arm, not her abdominal wall
            import trimesh
            sk = trimesh.Trimesh(to_ct(np.asarray(skin.vertices)), skin.faces, process=False)
            yy, tt = np.meshgrid(self.y[::2], self.th[::2], indexing='ij')
            O = self.point(tt.ravel(), yy.ravel(), np.zeros(tt.size))
            Dn = self.point(tt.ravel(), yy.ravel(), np.ones(tt.size)) - O
            rs = gf._ray_first(sk, O, Dn, 0.4).reshape(yy.shape)
            rs[~np.isfinite(rs)] = np.nan
            from scipy.ndimage import zoom
            rs = nanfill(rs, (1, 1))
            R = zoom(rs, (len(self.y) / rs.shape[0], len(self.th) / rs.shape[1]), order=1)[:len(self.y), :len(self.th)]
            self.r_model_skin = R
            arm = (d['r_skin'] > R + 0.025) | (d['r_out'] > R)
            self.valid &= ~arm
            self.arm_cells = float(arm.mean())
        out = {}
        for k in ('r_out', 'r_in', 'r_skin'):
            A = d[k].copy()
            A[~self.valid] = np.nan
            A = nanfill(A)
            A = median_filter(A, size=(3, 3), mode='nearest')
            from scipy.ndimage import gaussian_filter
            out[k] = gaussian_filter(A, (1.0, 1.0), mode='nearest')
        out['r_in'] = np.minimum(out['r_in'], out['r_out'] - 0.0015)
        self.A = out
        # raw (unsmoothed, valid cells only) for the fit gate: not the smoothed band the parts are built on
        # (3 x 3 median of the valid readings, so one spiking ray does not count as her wall)
        from scipy.ndimage import generic_filter
        raw = {k: generic_filter(np.where(self.valid, d[k], np.nan), np.nanmedian, size=3, mode='nearest') for k in ('r_out', 'r_in', 'r_skin')}
        if self.r_model_skin is not None:
            # round 2, posture: the CT was supine (the belly wall sags back), her organs and skin are standing.
            # The wall keeps her CT fat depth and wall thickness, measured from her (standing) skin.
            shift = self.r_model_skin - out['r_skin']
            for k in ('r_out', 'r_in'):
                out[k] = out[k] + shift
                raw[k] = raw[k] + (self.r_model_skin - raw['r_skin'])
            self.posture_shift_mm = np.round(np.percentile(shift[self.valid], [10, 50, 90]) * 1000, 1).tolist()
        self.raw = {k: RGI((self.y, self.th), raw[k], method='nearest', bounds_error=False, fill_value=np.nan) for k in ('r_out', 'r_in')}
        self.f = {k: RGI((self.y, self.th), v, bounds_error=False, fill_value=None) for k, v in out.items()}

    def clear_organs(self, pts_ct, margin=0.003):
        """Round 2: her organs (real HRA viscera) must lie BEHIND the wall. Where an organ reaches further out
        than the CT wall's inner surface (the CT was supine, the organs are in her standing body), the wall's
        inner and outer surfaces move out to clear it by `margin`, keeping the CT wall thickness."""
        from scipy.interpolate import RegularGridInterpolator as RGI
        from scipy.ndimage import maximum_filter, gaussian_filter
        th, y, r = self.polar(pts_ct)
        ok = self.inside(th, y)
        iy = np.clip(np.round((y[ok] - self.y[0]) / (self.y[1] - self.y[0])).astype(int), 0, len(self.y) - 1)
        it = np.clip(np.round((th[ok] - self.th[0]) / (self.th[1] - self.th[0])).astype(int), 0, len(self.th) - 1)
        R = np.zeros((len(self.y), len(self.th)))
        np.fmax.at(R, (iy, it), r[ok])
        R = gaussian_filter(maximum_filter(R, size=(7, 7)), 1.5)
        need = R + margin
        thick = self.A['r_out'] - self.A['r_in']
        push = np.maximum(need - self.A['r_in'], 0)
        self.A['r_in'] = self.A['r_in'] + push
        self.A['r_out'] = self.A['r_in'] + thick
        self.f.update({k: RGI((self.y, self.th), self.A[k], bounds_error=False, fill_value=None) for k in ('r_in', 'r_out')})
        return {'cells_pushed': int((push > 0.0005).sum()), 'cells': int(push.size), 'max_push_mm': float(push.max() * 1000),
                'mean_push_mm_where_pushed': float(push[push > 0.0005].mean() * 1000) if (push > 0.0005).any() else 0.0}

    def centre(self, y):
        return np.interp(y, self.y, self.cx), np.interp(y, self.y, self.cz)

    def polar(self, Xct):
        cx, cz = self.centre(Xct[:, 1])
        dx, dz = Xct[:, 0] - cx, Xct[:, 2] - cz
        return np.arctan2(dx, dz), Xct[:, 1], np.hypot(dx, dz)

    def point(self, th, y, r):
        cx, cz = self.centre(y)
        return np.c_[cx + r * np.sin(th), y, cz + r * np.cos(th)]

    def __call__(self, k, th, y):
        y = np.clip(y, self.y[0], self.y[-1]); th = np.clip(th, self.th[0], self.th[-1])
        return self.f[k](np.c_[y, th])

    def inside(self, th, y):
        return (y >= self.y[0]) & (y <= self.y[-1]) & (np.abs(th) <= self.th[-1])


def band_distance(B, X):
    """Radial distance (m) of model points to her RAW CT abdominal wall band (0 inside it); NaN where the CT
    reading at that (y, theta) was invalid (organ against the wall, arm, outside the scanned range)."""
    th, y, r = B.polar(to_ct(X))
    q = np.c_[y, th]
    ro, ri = B.raw['r_out'](q), B.raw['r_in'](q)
    return np.maximum.reduce([r - ro, ri - r, np.zeros(len(r))])


# ---------------------------------------------------------------------------------- abdominal wall
L3_NAME = re.compile(r'.*(third lumbar vertebra|lumbar vertebra 3\b|lumbar_vertebra_3\b|_L3\b).*', re.I)


def find_l3(F, M):
    """Her third lumbar vertebra: BodyParts3D name, or the real HRA vertebra (hybrid body)."""
    for m in M.values():
        if L3_NAME.fullmatch(m['name']):
            return m['pos']
    for n, f in F.items():
        nm = str(f.get('name') or (f.get('hra') or {}).get('name') or n)
        if L3_NAME.fullmatch(nm) or L3_NAME.fullmatch(n):
            return f['pos']
    return None


def _landmarks(F, M):
    by = {m['name']: m for m in M.values()}
    L = {}
    st = [m['pos'] for m in M.values() if re.search(r'xiphoid|body of sternum', m['name'], re.I) and m['system'] == 'skeletal']
    L['xiphoid'] = float(min(s[:, 1].min() for s in st))
    l3 = find_l3(F, M)
    L['umbilicus'] = float(l3[:, 1].min()) if l3 is not None else L['xiphoid'] - 0.17
    for side, sgn, tag in (('Left', 1, 'L'), ('Right', -1, 'R')):
        il = np.vstack([f['pos'] for n, f in F.items() if re.fullmatch(f'VH_F_ilium_compact_bone_{tag}', n)])
        pb = np.vstack([f['pos'] for n, f in F.items() if re.fullmatch(f'VH_F_pubis_compact_bone_{tag}', n)])
        top = il[il[:, 1] > il[:, 1].max() - 0.07]
        L['asis_' + tag] = top[np.argmax(top[:, 2])]
        L['crest_' + tag] = float(il[:, 1].max())
        q = pb[(np.abs(pb[:, 0]) > 0.012) & (np.abs(pb[:, 0]) < 0.035)]
        L['tubercle_' + tag] = q[np.argmax(q[:, 1] + 0.3 * q[:, 2])]
        L['pubic_crest'] = float(max(L.get('pubic_crest', -1), pb[np.abs(pb[:, 0]) < 0.03, 1].max()))
    return L


def abdominal_wall(F, M, male, report):
    """Returns the generated extra parts [(meta, V, idx)]; moves the BodyParts3D external oblique and linea alba."""
    import trimesh
    B = Band(ml.to_trimesh(F['VH_F_skin']['pos'], F['VH_F_skin']['idx']))
    L = _landmarks(F, M)
    res = {'landmarks': {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in L.items()}}
    VISC = re.compile(r'liver|stomach|colon|caecum|cecum|intestin|jejun|ileum|duoden|bladder|uter|spleen|gall|pancrea|appendix|rectum|sigmoid', re.I)
    organs = [f['pos'] for n, f in F.items() if VISC.search(n) and f.get('system') in ('digestive', 'urinary', 'reproductive', 'lymphatic')] + \
             [m['pos'] for m in M.values() if VISC.search(m['name']) and m['system'] in ('digestive', 'urinary')]
    res['organ_parts'] = len(organs)
    res['posture_shift_mm_p10_50_90'] = getattr(B, 'posture_shift_mm', None)
    res['organ_clearance'] = B.clear_organs(to_ct(np.vstack(organs)))
    print('m10 organ clearance', res['organ_clearance'], flush=True)
    extra = []
    Lct = {k: (to_ct(v[None])[0] if isinstance(v, np.ndarray) else v) for k, v in L.items()}
    # the model's landmark heights in the CT frame (the local refinement is a small rigid move)
    y_x, y_u, y_pc = (to_ct(np.array([[0, L[k], 0.08]]))[0, 1] for k in ('xiphoid', 'umbilicus', 'pubic_crest'))
    inters = [y_u + 0.012, (y_u + 0.012 + y_x - 0.02) / 2, y_x - 0.02]

    def half_width(y):       # rectus arc width (m) from the linea alba: 3 cm at the pubis, 7 cm at the umbilicus, 8 cm at the top
        return np.interp(y, [y_pc, y_u, y_x + 0.04], [0.03, 0.07, 0.08])

    LA = 0.004               # linea alba half width

    def th_of_arc(s, y, sgn):
        r = B('r_out', np.zeros_like(y), y)
        th = sgn * s / r
        r = B('r_out', th, y)
        return sgn * s / r

    def groove(y):
        return sum(np.exp(-0.5 * ((y - yi) / 0.003) ** 2) for yi in inters)

    def rect_outer(th, y):
        # round 2: each strap is convex across its width and the intersections are 2.2 mm grooves, so the
        # straps read through the aponeurosis that covers them (the external oblique follows this surface)
        r0 = B('r_out', th, y)
        u = np.clip((np.abs(th) * r0 - LA) / half_width(y), 0, 1)
        return r0 - 0.0013 + 0.0018 * np.sin(np.pi * u) - 0.0022 * groove(y) * np.sin(np.pi * u) ** 0.5

    def rect_inner(th, y):
        o = B('r_out', th, y) - 0.0013
        return np.minimum(B('r_in', th, y) + 0.0003, o - 0.0015)

    # ---- generated rectus abdominis (two straps) + tendinous intersections
    for side, sgn in (('Left', 1), ('Right', -1)):
        nu, dy = 14, 0.003
        vs_ = np.arange(0, 1.0001, 1 / max(2, int((y_x + 0.04 - y_pc) / dy)))
        U = np.linspace(0, 1, nu)
        O = np.zeros((nu, len(vs_), 3)); I = np.zeros_like(O)
        for iu, u in enumerate(U):
            ytop = y_x + 0.04 * u            # higher laterally (costal cartilages 5-7)
            y = y_pc + vs_ * (ytop - y_pc)
            s = LA + u * half_width(y)
            th = th_of_arc(s, y, sgn)
            ro = rect_outer(th, y) + 0.00015 * np.sin(2 * np.pi * s / 0.004)       # vertical fibre relief
            O[iu] = from_ct(B.point(th, y, ro)); I[iu] = from_ct(B.point(th, y, rect_inner(th, y)))
        V, idx = slab(O, I)
        extra.append(({'id': f'GEN_rectus_abdominis_{side.lower()}', 'name': f'{side} rectus abdominis', 'conceptId': f'GEN:rectus-abdominis-{side.lower()}',
                       'system': 'muscular', 'source': 'generated', 'accuracy': APPROX, 'note': NOTE_CT}, V, idx))
        parts = []
        for yi in inters:
            nu2 = 10; yy = np.array([yi - 0.0015, yi + 0.0015])
            O2 = np.zeros((nu2, 2, 3)); I2 = np.zeros_like(O2)
            for iu, u in enumerate(np.linspace(0.02, 0.98, nu2)):
                s = LA + u * half_width(yy)
                th = th_of_arc(s, yy, sgn)
                O2[iu] = from_ct(B.point(th, yy, rect_outer(th, yy) + 0.0004))
                I2[iu] = from_ct(B.point(th, yy, rect_inner(th, yy) + 0.0002))
            parts.append(slab(O2, I2))
        Vi = np.vstack([p[0] for p in parts]); off = np.cumsum([0] + [len(p[0]) for p in parts[:-1]])
        Ii = np.concatenate([p[1] + o for p, o in zip(parts, off)])
        extra.append(({'id': f'GEN_tendinous_intersections_{side.lower()}', 'name': f'Tendinous intersections of {side.lower()} rectus abdominis',
                       'conceptId': f'GEN:tendinous-intersections-{side.lower()}', 'system': 'connective', 'source': 'generated',
                       'accuracy': APPROX, 'note': NOTE_STD + ' Three intersections above the umbilicus.'}, Vi, Ii))

    # ---- BodyParts3D external oblique + linea alba: radial move onto her CT wall, own thickness kept
    th_rb = lambda y, sgn: th_of_arc(LA + half_width(y), y, sgn)
    moved = {}
    for pid, m in M.items():
        if not re.fullmatch(r'(Left|Right) external oblique|Linea alba', m['name']):
            continue
        X = m['pos']; Xc = to_ct(X)
        th, y, r = B.polar(Xc)
        # the part's own outer / inner radius per (y, theta) bin
        yb = np.clip(((y - B.y[0]) / 0.006).astype(int), 0, None); tb = np.clip(((th - B.th[0]) / np.radians(3)).astype(int), 0, None)
        ny, nt = yb.max() + 1, tb.max() + 1
        rmax = np.full((ny, nt), np.nan); rmin = np.full((ny, nt), np.nan)
        np.fmax.at(rmax, (yb, tb), r); np.fmin.at(rmin, (yb, tb), r)
        from scipy.ndimage import gaussian_filter as _gf             # round 2: smoother bins (no crumpling)
        rmax, rmin = _gf(nanfill(rmax, (1, 1)), 1.2, mode='nearest'), _gf(nanfill(rmin, (1, 1)), 1.2, mode='nearest')
        eo_out, eo_in = rmax[yb, tb], rmin[yb, tb]
        thick = np.maximum(eo_out - eo_in, 0.0005)
        # lateral wall: the external oblique takes its share of HER CT wall (4.8 of 4.8 + 5.95 + 3.4 mm, Tahan
        # et al. 2016); the BodyParts3D (male) sheet is thicker than her whole wall at the flank
        bo, bi = B('r_out', th, y), B('r_in', th, y)
        eo_band = np.maximum(EO_SHARE * (bo - bi), 0.0015)
        keep = bo - np.clip((eo_out - r) / thick, 0, 1) * np.minimum(thick, eo_band)
        sgn = np.where(th >= 0, 1, -1)
        if 'oblique' in m['name']:
            apo = rect_outer(th, y) + 0.0003 + np.clip((r - eo_in) / thick, 0, 1) * 0.0010   # aponeurosis over the rectus
            rb = th_rb(y, sgn)
            wr = smoothstep(np.abs(rb) + 0.015 / B('r_out', th, y), np.abs(rb) - 0.01 / B('r_out', th, y), np.abs(th))
            new = wr * apo + (1 - wr) * keep
        else:                    # linea alba: an aponeurosis, it fills her wall band between the straps
            bo, bi = B('r_out', th, y) - 0.0002, B('r_in', th, y) + 0.0002
            new = bi + np.clip((r - eo_in) / thick, 0, 1) * np.maximum(bo - bi, 0.001)
        dr = new - r
        inside = B.inside(th, y)
        w = smoothstep(0, 0.03, np.minimum.reduce([y - B.y[0], B.y[-1] - y, (B.th[-1] - np.abs(th)) * 0.15])) * inside
        dr = dr * w
        Y = B.point(th, y, r + dr)
        D = from_ct(Y) - X
        D = diffuse(D, m['idx'], np.zeros(len(X), bool), rounds=30)      # round 2: no crumpling, no loose flaps
        X2 = X + D
        src = male[pid]['pos']
        if len(src) == len(X2):
            X2 = gf.edge_clamp(X2, src, m['idx'], None, np.zeros(len(X2), bool), iters=200)
        m['pos'] = X2; m['warp_pos'] = X2.copy(); m['preoptimized'] = True
        moved[pid] = m['name']
    # ---- inguinal ligaments (ASIS -> pubic tubercle) and the external oblique's lower border on them
    for side, tag in (('Left', 'L'), ('Right', 'R')):
        A, T = L['asis_' + tag], L['tubercle_' + tag]
        s = np.linspace(0, 1, 30)[:, None]
        C = A + s * (T - A) + np.sin(np.pi * s) * np.array([0, -0.006, 0.003])
        V, idx = tube(C, 0.003)
        extra.append(({'id': f'GEN_inguinal_ligament_{side.lower()}', 'name': f'{side} inguinal ligament', 'conceptId': f'GEN:inguinal-ligament-{side.lower()}',
                       'system': 'connective', 'source': 'generated', 'accuracy': APPROX,
                       'note': NOTE_STD + ' The lower border of the external oblique aponeurosis, ASIS to pubic tubercle.'}, V, idx))
        eo = [m for m in M.values() if m['name'] == f'{side} external oblique']
        if eo:
            m = eo[0]; X = m['pos']
            tree = cKDTree(C)
            d, j = tree.query(X)
            cp = C[j]
            below = X[:, 1] < cp[:, 1] + 0.02
            wgt = smoothstep(0.028, 0.008, d) * below
            D = (cp + np.array([0, 0.0015, 0]) - X) * wgt[:, None]
            D = diffuse(D, m['idx'], wgt > 0.95, rounds=4)
            m['pos'] = X + D; m['warp_pos'] = m['pos'].copy()
            res[f'{side} inguinal ligament'] = {'asis': A.tolist(), 'pubic_tubercle': T.tolist(), 'eo_vertices_on_ligament': int((wgt > 0.95).sum())}
    # ---- generated internal oblique and transversus abdominis (lateral band under the external oblique)
    eo_all = np.vstack([to_ct(m['pos']) for m in M.values() if re.fullmatch(r'(Left|Right) external oblique', m['name'])])
    eth, ey, er = B.polar(eo_all)
    yb = np.clip(((ey - B.y[0]) / 0.006).astype(int), 0, len(B.y) // 2); tb = np.clip(((eth - B.th[0]) / np.radians(3)).astype(int), 0, None)
    EOin = np.full((yb.max() + 1, tb.max() + 1), np.nan); np.fmin.at(EOin, (yb, tb), er)
    EOin = nanfill(EOin, (1, 1))

    def eo_inner(th, y):
        i = np.clip(((y - B.y[0]) / 0.006).astype(int), 0, EOin.shape[0] - 1); j = np.clip(((th - B.th[0]) / np.radians(3)).astype(int), 0, EOin.shape[1] - 1)
        return np.minimum(EOin[i, j], B('r_out', th, y) - 0.0015)

    def polar_pts(P):
        return B.polar(to_ct(P))
    ribs = np.vstack([m['pos'] for m in M.values() if re.fullmatch(r'(Left|Right) (seventh|eighth|ninth|tenth|eleventh|twelfth) rib', m['name'])
                      or re.search(r'costal cartilage', m['name'], re.I)])
    rth, ry, rr_ = polar_pts(ribs)
    ilium = np.vstack([f['pos'] for n, f in F.items() if re.search(r'^VH_F_ilium_compact_bone', n)])
    ith, iy, _ = polar_pts(ilium)
    TH = np.radians(np.arange(0, 121, 3))
    for side, sgn, tag in (('Left', 1, 'L'), ('Right', -1, 'R')):
        def border(thv):
            """lower (inguinal ligament / iliac crest) and upper (costal margin) heights at |theta|."""
            lo = np.full(len(thv), np.nan); up = np.full(len(thv), np.nan)
            for k, t in enumerate(thv):
                sel = np.abs(ith - sgn * t) < np.radians(4)
                if sel.any():
                    lo[k] = iy[sel].max()
                sel = np.abs(rth - sgn * t) < np.radians(4)
                if sel.any():
                    up[k] = ry[sel].min()
            a_th, a_y, _ = polar_pts(L['asis_' + tag][None]); t_th, t_y, _ = polar_pts(L['tubercle_' + tag][None])
            ant = np.abs(thv) < abs(a_th[0])
            lo[ant] = np.interp(np.abs(thv[ant]), [abs(t_th[0]), abs(a_th[0])], [t_y[0], a_y[0]])
            lo = np.interp(thv, thv[np.isfinite(lo)], lo[np.isfinite(lo)])
            up = np.interp(thv, thv[np.isfinite(up)], up[np.isfinite(up)])
            return lo + 0.004, np.maximum(up, lo + 0.05)
        lo, up = border(TH)
        for name, frac, fib, extra_up in (('internal oblique', (0.0, IO_SHARE), (1.0, 1.0), 0.0), ('transversus abdominis', (IO_SHARE, 1.0), (0.0, 1.0), 0.015)):
            nv = 120; nu = 40
            O = np.zeros((nu, nv, 3)); I = np.zeros_like(O)
            # Coons patch in (|theta|, y) from four border curves (no fold): lower = inguinal ligament then
            # iliac crest, upper = costal margin, medial = the rectus lateral border, posterior = 115 deg
            t_post = np.radians(115)
            t_bot = abs(polar_pts(L['tubercle_' + tag][None])[0][0])
            y_tm = 1.15
            for _ in range(3):
                t_top = float(np.abs(th_rb(np.array([y_tm]), sgn))[0]); y_tm = float(np.interp(t_top, TH, up)) + extra_up
            uu = np.linspace(0, 1, nu); vv = np.linspace(0, 1, nv)
            c0t = t_bot + uu * (t_post - t_bot); C0 = np.c_[c0t, np.interp(c0t, TH, lo)]
            c1t = t_top + uu * (t_post - t_top); C1 = np.c_[c1t, np.interp(c1t, TH, up) + extra_up]
            d0y = C0[0, 1] + vv * (C1[0, 1] - C0[0, 1])
            d0t = np.abs(th_rb(d0y, sgn)); d0t = d0t + (1 - vv) * (C0[0, 0] - d0t[0]) + vv * (C1[0, 0] - d0t[-1])
            D0 = np.c_[d0t, d0y]
            D1 = np.c_[np.full(nv, t_post), C0[-1, 1] + vv * (C1[-1, 1] - C0[-1, 1])]
            for iv, v in enumerate(vv):
                S = ((1 - v) * C0 + v * C1 + (1 - uu)[:, None] * D0[iv] + uu[:, None] * D1[iv]
                     - ((1 - uu) * (1 - v))[:, None] * C0[0] - (uu * (1 - v))[:, None] * C0[-1]
                     - ((1 - uu) * v)[:, None] * C1[0] - (uu * v)[:, None] * C1[-1])
                thv, y = S[:, 0], S[:, 1]
                th = sgn * thv
                bo_, bi_ = B('r_out', th, y), B('r_in', th, y)
                top = bo_ - np.maximum(EO_SHARE * (bo_ - bi_), 0.0015) - 0.0004     # under the external oblique as placed
                bot = B('r_in', th, y) + 0.0002
                span = np.maximum(top - bot, 0.0023)
                bot = top - span
                ro = top - frac[0] * span - (0.00015 if frac[0] > 0 else 0)
                ri = top - frac[1] * span + (0.00015 if frac[1] < 1 else 0)
                ri = np.minimum(ri, ro - 0.001)
                # fibre relief: internal oblique up and medially, transversus horizontal
                arc = thv * B('r_out', th, y)
                phase = (arc * fib[0] - y * fib[1]) if fib[0] else y
                ro = ro + 0.00015 * np.sin(2 * np.pi * phase / 0.004)
                O[:, iv] = from_ct(B.point(th, y, ro)); I[:, iv] = from_ct(B.point(th, y, ri))
            V, idx = slab(O, I)
            extra.append(({'id': f"GEN_{name.replace(' ', '_')}_{side.lower()}", 'name': f'{side} {name}',
                           'conceptId': f"GEN:{name.replace(' ', '-')}-{side.lower()}", 'system': 'muscular', 'source': 'generated',
                           'accuracy': APPROX, 'note': NOTE_CT}, V, idx))
    # ---- fit numbers: every abdominal wall muscle vs her CT band
    fit = {}

    def gate(V):
        d = band_distance(B, V)
        ok = np.isfinite(d)
        return {'mean_mm': float(d[ok].mean() * 1000) if ok.any() else None, 'p95_mm': float(np.percentile(d[ok], 95) * 1000) if ok.any() else None,
                'vertices_with_valid_ct': int(ok.sum()), 'vertices': len(V)}
    for pid, name in moved.items():
        fit[name] = gate(M[pid]['pos'])
    for meta, V, idx in extra:
        if meta['system'] == 'muscular':
            fit[meta['name']] = gate(V)
        m = trimesh.Trimesh(V, idx.reshape(-1, 3), process=False)
        fit.setdefault(meta['name'], {})['watertight'] = bool(m.is_watertight)
    res['fit_to_ct'] = fit
    res['intersections_y_ct'] = inters
    report['m10_abdominal_wall'] = res
    for k, v in fit.items():
        print('m10 abdominal', k, v, flush=True)
    return extra


# ------------------------------------------------------------------------------- subcutaneous fat
SUPERFICIAL = re.compile(r'saphenous|cephalic|basilic|superficial|cutaneous|median cubital|dorsal venous|perforat|'
                         r'subcutaneous|gluteofemoral|breast adipose|skin', re.I)


def subcutaneous_fat(F, M, G, extra, report, inset=0.001, gap=0.0005, tmin=0.0003, tmax=0.10):
    """One closed subcutaneous fat layer between her (packaged) skin and the deep envelope."""
    import trimesh
    skin = F['VH_F_skin']
    P, I = package_like(skin['pos'], skin['idx'])
    sk = trimesh.Trimesh(P, I.reshape(-1, 3), process=False)
    N = np.asarray(sk.vertex_normals).copy()
    nb = sk.vertex_neighbors
    for _ in range(6):                                           # smooth the offset direction
        N = 0.5 * N + 0.5 * np.array([N[n].mean(0) if len(n) else N[i] for i, n in enumerate(nb)])
        N /= np.maximum(np.linalg.norm(N, axis=1), 1e-9)[:, None]
    deep = []
    for m in M.values():
        if m['system'] in ('integumentary', 'adipose') or SUPERFICIAL.search(m['name']):
            continue
        deep.append(m['pos'])
    for n, f in F.items():
        if n == 'VH_F_skin' or f['system'] in ('integumentary',):
            continue
        deep.append(f['pos'])
    for g in G.values():
        deep.append(g['pos'])
    for meta, V, _ in extra:
        if SUPERFICIAL.search(meta['name']) and 'breast adipose' not in meta['name']:
            continue
        deep.append(V)
    Q = np.vstack(deep)
    tree = cKDTree(Q)
    k = 48
    d, j = tree.query(P, k=k, distance_upper_bound=tmax)
    t0 = np.full(len(P), tmax)
    for c in range(k):
        ok = np.isfinite(d[:, c])
        if not ok.any():
            break
        jj = np.where(ok, j[:, c], 0)
        v = Q[jj] - P
        cone = (np.einsum('ij,ij->i', v, -N) > 0.5 * d[:, c]) & ok
        t0 = np.where(cone & (d[:, c] < t0), d[:, c], t0)
    bound = np.clip(t0 - inset - gap, tmin, tmax)
    # do not cross the medial axis (thin parts: fingers, ears, nose, between the thighs)
    stree = cKDTree(P)
    t = bound.copy()
    for _ in range(4):
        x = P - N * (inset + t)[:, None]
        s = stree.query(x)[0]
        over = s < 0.95 * (inset + t)
        t[over] = np.maximum(tmin, 0.9 * s[over] - inset)
    bound = np.minimum(bound, t)
    # natural openings: thin to tmin (eyes, mouth, nostrils, vulva, anus)
    centres = []
    for m in list(M.values()) + [{'name': n, 'pos': f['pos']} for n, f in F.items()] + [{'name': s, 'pos': g['pos']} for s, g in G.items()]:
        if re.search(r'eyeball|^(left|right) eye$|lip|orbicularis oris|nostril|naris|nasal vestibule|vestibul|vaginal orifice|external anal sphincter|anal canal', m['name'], re.I):
            centres.append(m['pos'].mean(0))
    f_open = np.ones(len(P))
    if centres:
        dc = cKDTree(np.array(centres)).query(P)[0]
        f_open = smoothstep(0.012, 0.035, dc)
    t = np.maximum(tmin, bound * f_open)
    for _ in range(20):                                          # smooth, never past the bound
        t = 0.5 * t + 0.5 * np.array([t[n].mean() if len(n) else t[i] for i, n in enumerate(nb)])
        t = np.minimum(t, np.maximum(bound * f_open, tmin))
    outer = P - N * inset
    # inner surface folded over (its normal against the skin normal = self-intersection): thin the layer there
    folded0 = None
    for _ in range(8):
        inner = P - N * (inset + t)[:, None]
        inner_n = trimesh.Trimesh(inner, I.reshape(-1, 3), process=False).vertex_normals
        fold = np.einsum('ij,ij->i', inner_n, N) < 0.2
        if folded0 is None:
            folded0 = int(fold.sum())
        if not fold.any():
            break
        grow = fold.copy()
        for _ in range(3):
            grow = grow | np.array([grow[n].any() if len(n) else False for n in nb])
        t[grow] = np.maximum(tmin, t[grow] * 0.6)
        for _ in range(3):
            t2 = 0.5 * t + 0.5 * np.array([t[n].mean() if len(n) else t[i] for i, n in enumerate(nb)])
            t[grow] = np.minimum(t2[grow], t[grow])
    inner = P - N * (inset + t)[:, None]
    inner_n = trimesh.Trimesh(inner, I.reshape(-1, 3), process=False).vertex_normals
    folded = int((np.einsum('ij,ij->i', inner_n, N) < 0).sum())
    shell = ml.SkinShell(sk)
    # sharp concave skin (smoothed offset direction): the few vertices that end up outside go back inside
    outer = shell.keep_inside(outer, margin=0.0005, radius=0.003, iterations=10)[0]
    inner = shell.keep_inside(inner, margin=0.0008, radius=0.003, iterations=10)[0]
    V = np.vstack([outer, inner]); nv = len(P)
    Fc = np.vstack([I.reshape(-1, 3), I.reshape(-1, 3)[:, ::-1] + nv])
    fm = trimesh.Trimesh(V, Fc, process=False)
    edges = fm.edges_sorted
    boundary = len(trimesh.grouping.group_rows(edges, require_count=1))
    outside = int(shell.outside(V).sum())
    report['m10_subcutaneous_fat'] = {'vertices': len(V), 'faces': len(Fc), 'boundary_edges': boundary, 'inner_vertices_folded': folded, 'folded_before_fix': folded0,
                                      'outside_packaged_skin': outside, 'inset_mm': inset * 1000,
                                      'thickness_mm_p10_50_90': np.round(np.percentile(t, [10, 50, 90]) * 1000, 1).tolist()}
    print('m10 subcutaneous fat', report['m10_subcutaneous_fat'], flush=True)
    meta = {'id': 'GEN_subcutaneous_fat', 'name': 'Subcutaneous fat', 'conceptId': 'GEN:subcutaneous-fat', 'system': 'subcutaneous',
            'source': 'generated', 'accuracy': 'generated', 'preoptimized': True,
            'note': 'Generated from her real (VHF) skin: one closed adipose layer between the skin (inset 1 mm) and the outer surface of '
                    'the muscles, bones and other deep structures. Hidden by default; shown with the "Subcutaneous fat" toggle.'}
    return (meta, V, Fc.reshape(-1)), (P, I, N, t)


def fat_thickness_sites(M, F, fatinfo, report):
    """Median layer thickness at the requested sites (model)."""
    P, I, N, t = fatinfo
    by = {m['name']: m['pos'] for m in M.values()}
    out = {}
    l3 = find_l3(F, M)
    s1 = np.vstack([f['pos'] for n, f in F.items() if n == 'VH_F_sacrum'])
    bones = {k: v for k, v in by.items() if re.fullmatch(r'(Left|Right) (femur|humerus)', k)}
    arm = np.vstack([v for k, v in by.items() if re.fullmatch(r'(Left|Right) (humerus|radius|ulna)', k)])
    leg = np.vstack([v for k, v in by.items() if re.fullmatch(r'(Left|Right) (femur|tibia)', k)] + [s1])
    near_leg = cKDTree(leg).query(P)[0] < cKDTree(arm).query(P)[0]

    def med(sel):
        return float(np.median(t[sel]) * 1000) if sel.sum() > 5 else None
    if l3 is not None:
        y = (l3[:, 1].min() + l3[:, 1].max()) / 2
        out['abdomen L3 anterior'] = med((np.abs(P[:, 1] - y) < 0.01) & (np.abs(P[:, 0]) < 0.06) & (N[:, 2] > 0.7))
    ys1 = s1[:, 1].max() - 0.01
    out['buttock S1 posterior (supine-distorted in CT)'] = med((np.abs(P[:, 1] - ys1) < 0.01) & (np.abs(P[:, 0]) > 0.03) & (np.abs(P[:, 0]) < 0.13) & (N[:, 2] < -0.7))
    for side, sgn in (('Left', 1), ('Right', -1)):
        fm = bones[f'{side} femur']
        top = fm[fm[:, 1] > fm[:, 1].max() - 0.06]
        gt = top[np.argmax(top[:, 0] * sgn)]
        out[f'lateral hip at trochanter ({side})'] = med((np.abs(P[:, 1] - gt[1]) < 0.015) & (N[:, 0] * sgn > 0.7) & near_leg & (P[:, 0] * sgn > 0))
        yt = fm[:, 1].max() - 0.25 * np.ptp(fm[:, 1])
        out[f'upper thigh ({side})'] = med((np.abs(P[:, 1] - yt) < 0.01) & near_leg & (P[:, 0] * sgn > 0.02))
        hm = bones[f'{side} humerus']
        yh = (hm[:, 1].min() + hm[:, 1].max()) / 2
        out[f'upper arm ({side})'] = med((np.abs(P[:, 1] - yh) < 0.01) & ~near_leg & (P[:, 0] * sgn > 0) & (cKDTree(hm).query(P)[0] < 0.08))
    report['m10_fat_thickness_model_mm'] = out
    print('m10 fat thickness (model, mm)', out, flush=True)
