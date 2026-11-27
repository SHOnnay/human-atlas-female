"""Milestone 9 (hybrid): the gluteal region from her real body.

1. pelvis_delta      - the VHF CT (already rigidly registered on hips + sacrum + femurs, vhf_targets.py)
                       is refined with ONE rigid move fitted on the pelvic bones only: TotalSegmentator
                       hip_left / hip_right / sacrum -> HRA ilium / ischium / pubis / sacrum.
2. fit_gluteals      - BodyParts3D gluteus maximus / medius / minimus fitted (similarity, then smooth
                       symmetric non-rigid ICP) to her CT masks (largest connected component, so a
                       mislabelled blob is dropped). Where the fitted muscle meets her real bones
                       (within 6 mm) it is seated on the bone surface: origins and insertions are on
                       her bones. Gate: mean surface distance <= 3 mm.
3. it_shell          - the iliotibial tract becomes a thin shell on the OUTER surface of tensor fasciae
                       latae / gluteus maximus / gluteus medius / vastus lateralis (first hit of a ray
                       cast inward along the sheet normal), 0.75 mm off the muscle.
4. gluteofemoral_fat - new structure: the volume between her skin (inset 2 mm) and the outer surface of
                       the gluteal and lateral thigh muscles (and the IT tract), from the iliac crest to
                       mid-thigh, posterior and lateral, including the gluteal fold; thickness tapers
                       smoothly to zero at the border.
The CT donor lay supine: the CT gives the muscles' volume and attachments, the fat layer takes up the
rest of her (wider) skin shape.
"""
import re

import numpy as np
from scipy.spatial import cKDTree

import meshlib as ml

TARGETS = None
GLUT = re.compile(r'^(Left|Right) gluteus (maximus|medius|minimus)$')
UNDER_TRACT = re.compile(r'tensor fasciae latae|gluteus (maximus|medius)|vastus lateralis', re.I)
FAT_WALL = re.compile(r'gluteus (maximus|medius)|tensor fasciae latae|vastus lateralis|biceps femoris|semitendinosus|'
                      r'semimembranosus|adductor magnus|iliotibial|rectus femoris|sartorius|gracilis|vastus medialis', re.I)
DELTA = {}


def _target(label):
    import trimesh
    d = np.load(ml_root() / 'work' / 'vhf' / 'targets' / f'{label}__head_to_femur.npz')
    m = trimesh.Trimesh(d['v'], d['f'], process=False)
    parts = m.split(only_watertight=False)
    big = max(parts, key=lambda c: len(c.faces))
    return big, len(parts), float(len(big.faces) / max(len(m.faces), 1))


def ml_root():
    from pathlib import Path
    return Path(__file__).resolve().parents[2]


def edge_ratio(src, X, idx):
    t = idx.reshape(-1, 3)
    r = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        l0 = np.linalg.norm(src[t[:, a]] - src[t[:, b]], axis=1)
        l1 = np.linalg.norm(X[t[:, a]] - X[t[:, b]], axis=1)
        r.append(l1 / np.maximum(l0, 1e-9))
    return np.max(r, axis=0)


def relax_on_surface(X, src, idx, project, limit=1.9, rounds=60, pin=None):
    """Tangential relaxation: vertices of triangles stretched past `limit` x their source length are
    moved toward their neighbours' mean and projected back onto the target surface, so the mesh is
    redistributed along the surface (no stretch, still on the surface). `pin`: vertices never moved."""
    from scipy.sparse import coo_matrix
    t = idx.reshape(-1, 3); n = len(X)
    rr = np.r_[t[:, 0], t[:, 1], t[:, 2], t[:, 1], t[:, 2], t[:, 0]]
    cc = np.r_[t[:, 1], t[:, 2], t[:, 0], t[:, 0], t[:, 1], t[:, 2]]
    A = coo_matrix((np.ones(len(rr)), (rr, cc)), shape=(n, n)).tocsr(); A.data[:] = 1.0
    deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
    X = X.copy()
    for k in range(rounds):
        r = edge_ratio(src, X, idx)
        bad = r > limit
        if not bad.any():
            break
        v = np.zeros(n, bool); v[t[bad].ravel()] = True
        v = v | (A @ v.astype(float) > 0)          # and their ring
        if pin is not None:
            v &= ~pin
        mean = (A @ X) / deg[:, None]
        X[v] = 0.4 * X[v] + 0.6 * mean[v]
        # the stretched triangles and their ring are NOT projected back (projecting restores the stretch
        # across a thickened rim); the wider neighbourhood is, so the surface stays on the target
        core = np.zeros(n, bool); core[t[bad].ravel()] = True
        core = core | (A @ core.astype(float) > 0)
        w = v & ~core
        if w.any():
            X[w] = project(X[w])
    return X, int((edge_ratio(src, X, idx) > 2.0).sum())


def edge_clamp(X, src, idx, pull, pin, limit=1.8, iters=500, every=5, w=0.3):
    """Position-based edge-length constraint: every edge longer than `limit` x its source (male BP3D)
    length is shortened, both ends moving toward each other (pinned vertices never move); every
    `every` steps the free vertices are pulled a fraction `w` toward the target surface (`pull`).
    The mesh is actually redistributed (no subdivision, no vertex added)."""
    t = idx.reshape(-1, 3)
    e = np.unique(np.sort(np.r_[t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]], axis=1), axis=0)
    l0 = np.linalg.norm(src[e[:, 0]] - src[e[:, 1]], axis=1)
    inv = (~pin).astype(float)
    X = X.copy()
    for k in range(iters):
        d = X[e[:, 1]] - X[e[:, 0]]
        L = np.linalg.norm(d, axis=1)
        over = L > limit * l0
        if not over.any():
            break
        a, b = e[over, 0], e[over, 1]
        wa, wb = inv[a], inv[b]
        ws = np.maximum(wa + wb, 1e-9)
        c = d[over] * ((L[over] - limit * l0[over]) / L[over])[:, None]
        mv = np.zeros_like(X); cnt = np.zeros(len(X))
        np.add.at(mv, a, c * (wa / ws)[:, None]); np.add.at(mv, b, -c * (wb / ws)[:, None])
        np.add.at(cnt, a, 1); np.add.at(cnt, b, 1)
        X += mv / np.maximum(cnt, 1)[:, None]
        if pull is not None and k % every == every - 1:
            free = ~pin
            X[free] = X[free] + w * (pull(X[free]) - X[free])
    return X


def two_way(P, idx, tgt):
    """Mean surface distance both ways (model -> CT, CT -> model), their mean, and the 95th percentile."""
    import trimesh
    a = trimesh.proximity.closest_point(tgt, P[::max(1, len(P) // 4000)])[1]
    Q = np.asarray(tgt.vertices)[::max(1, len(tgt.vertices) // 4000)]
    b = trimesh.proximity.closest_point(trimesh.Trimesh(P, idx.reshape(-1, 3), process=False), Q)[1]
    return float(a.mean() * 1000), float(b.mean() * 1000), float((a.mean() + b.mean()) * 500), float(np.percentile(np.r_[a, b], 95) * 1000)


def _rigid(A, B):
    ca, cb = A.mean(0), B.mean(0)
    U, _, Vt = np.linalg.svd((A - ca).T @ (B - cb))
    D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ D @ U.T
    return R, cb - R @ ca


def pelvis_delta(F, report):
    """ONE rigid refinement of the CT on her pelvic bones only (no femurs)."""
    hra = np.vstack([f['pos'] for n, f in F.items() if re.search(r'^VH_F_((ilium|ischium|pubis)_compact_bone_[LR]|sacrum)$', n)])
    ct = np.vstack([np.asarray(_target(l)[0].vertices) for l in ('hip_left', 'hip_right', 'sacrum')])
    ct = ct[:: max(1, len(ct) // 40000)]
    tree = cKDTree(hra)
    d0 = tree.query(ct)[0]
    R, t = np.eye(3), np.zeros(3)
    X = ct.copy()
    for _ in range(40):
        d, j = tree.query(X)
        ok = d < np.percentile(d, 90)
        r, tt = _rigid(X[ok], hra[j[ok]])
        X = X @ r.T + tt
        R, t = r @ R, r @ t + tt
    d1 = tree.query(X)[0]
    ang = float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))
    DELTA.update(R=R, t=t)
    report['m9_pelvis_registration'] = {'bones': 'CT hip_left, hip_right, sacrum -> HRA ilium, ischium, pubis, sacrum',
                                        'rotation_deg': ang, 'translation_mm': (t * 1000).tolist(),
                                        'median_mm_before': float(np.median(d0) * 1000), 'median_mm_after': float(np.median(d1) * 1000),
                                        'p90_mm_after': float(np.percentile(d1, 90) * 1000), 'R': R.tolist(), 't': t.tolist()}
    print('m9 pelvis registration', report['m9_pelvis_registration'], flush=True)


def _apply_delta(V):
    return V @ DELTA['R'].T + DELTA['t']


REQUIRED = {'maximus': ('sacrum', 'coccyx', 'ilium', 'femur'), 'medius': ('ilium', 'femur'), 'minimus': ('ilium', 'femur')}


def _diffuse(D, nb, fixed, rounds=6):
    for _ in range(rounds):
        D2 = np.array([D[n].mean(0) if len(n) else D[i] for i, n in enumerate(nb)])
        D2[fixed] = D[fixed]
        D = D2
    return D


M10 = True


def bare_ilium(side, bones, M, medius_pos=None, medius_idx=None):
    """Outer (gluteal) surface of her ilium between the crest (-6 mm) and 12 cm below it with no gluteal muscle
    (maximus / medius / minimus / TFL) within 4 mm or along its outward normal within 30 mm."""
    import trimesh
    il = bones[('ilium', side)]
    sgn = 1 if side == 'Left' else -1
    V = np.asarray(il.vertices); N = np.asarray(il.vertex_normals)
    crest = V[:, 1].max()
    # round 2: the outer AND anterolateral faces of the wing (side and oblique views)
    outer = ((N[:, 0] * sgn > 0.3) | (N[:, 0] * sgn + 0.6 * N[:, 2] > 0.45)) & (V[:, 1] < crest - 0.006) & (V[:, 1] > crest - 0.12)
    ms = []
    for m in M.values():
        if re.fullmatch(f'{side} (gluteus (maximus|medius|minimus)|tensor fasciae latae)', m['name']):
            if medius_pos is not None and m['name'] == f'{side} gluteus medius':
                ms.append(ml.to_trimesh(medius_pos, medius_idx))
            else:
                ms.append(ml.to_trimesh(m['pos'], m['idx']))
    mus = trimesh.util.concatenate(ms)
    O = V[outer] + N[outer] * 0.0005
    hit = np.isfinite(_ray_first(mus, O, N[outer], 0.03))
    near = trimesh.proximity.ProximityQuery(mus).on_surface(O)[1] < 0.004
    bare = ~(hit | near)
    return O[bare], N[outer][bare], int(outer.sum())


def cover_ilium(X, idx, src, side, bones, M, pin, tgt, nb):
    """Gluteus medius covers the outer ilium between the crest and gluteus maximus: the bare ilium surface
    (offset 5 mm outward, mid-muscle) is added to her CT medius as a fit target; symmetric fit (no similarity
    step), the attachments kept, then the edge clamp."""
    import trimesh
    import vhf_register as vr
    P, N, n_outer = bare_ilium(side, bones, M, X, idx)
    before = len(P)
    if before < 10:
        return X, {'outer_ilium_points': n_outer, 'bare_before': before, 'bare_after': before}
    cloud = trimesh.Trimesh(np.vstack([P + N * 0.003, P + N * 0.007]), process=False)
    pts = np.vstack([np.asarray(tgt.vertices), np.asarray(cloud.vertices)])
    pc = trimesh.points.PointCloud(pts)
    # point targets: the CT medius surface plus the bare ilium band; symmetric pull via nearest points
    tree = cKDTree(pts)
    Y = X.copy()
    for it in range(120):
        d, j = tree.query(Y)
        D = pts[j] - Y                                   # model -> target
        tr = cKDTree(Y)
        d2, k = tr.query(np.asarray(cloud.vertices))
        D2 = np.zeros_like(Y); c2 = np.zeros(len(Y))
        np.add.at(D2, k, np.asarray(cloud.vertices) - Y[k]); np.add.at(c2, k, 1)
        D = 0.15 * D + 0.85 * np.where(c2[:, None] > 0, D2 / np.maximum(c2, 1)[:, None], D)   # cover the bare ilium first
        D = _diffuse(D, nb, pin, rounds=8)
        D[pin] = 0
        Y = Y + 0.6 * D
    Y = edge_clamp(Y, src, idx, None, pin, iters=300)
    after = len(bare_ilium(side, bones, M, Y, idx)[0])
    del pc
    return Y, {'outer_ilium_points': n_outer, 'bare_before': before, 'bare_after': after}


def fit_gluteals(M, F, shell, report, male):
    import trimesh
    import vhf_register as vr
    side_of = lambda pos: 'Left' if pos[:, 0].mean() > 0 else 'Right'
    bones = {}
    for n, f in F.items():
        for key, pat in (('sacrum', r'^VH_F_sacrum$'), ('coccyx', r'^VH_F_coccyx$'), ('ilium', r'^VH_F_ilium'), ('ischium', r'^VH_F_ischium')):
            if re.search(pat, n):
                s = 'mid' if key in ('sacrum', 'coccyx') else side_of(f['pos'])
                bones.setdefault((key, s), []).append(ml.to_trimesh(f['pos'], f['idx']))
    for m in M.values():
        g = re.match(r'^(Left|Right) femur$', m['name'])
        if g:
            bones[('femur', g.group(1))] = [ml.to_trimesh(m['pos'], m['idx'])]
    bones = {k: trimesh.util.concatenate(v) for k, v in bones.items()}
    out = {}
    for pid, m in M.items():
        g = GLUT.match(m['name'])
        if not g:
            continue
        side, mus = g.group(1), g.group(2)
        tgt, ncomp, frac = _target(f'gluteus_{mus}_{side.lower()}')
        tgt = trimesh.Trimesh(_apply_delta(np.asarray(tgt.vertices)), tgt.faces, process=False)
        pq = trimesh.proximity.ProximityQuery(tgt)
        src = male[pid]['pos']; idx = m['idx']
        tm = trimesh.Trimesh(m['pos'], idx.reshape(-1, 3), process=False)
        nb = tm.vertex_neighbors
        X0 = vr.symmetric_fit(m['pos'].copy(), nb, tgt, iters=60, smooth=15)
        # Attachments: on every bone this muscle must attach to, the muscle vertices nearest that bone
        # (within 4 mm of the closest one) are seated on the bone surface (+0.5 mm); the move is spread
        # smoothly over the mesh, and the seated vertices are pinned through the stretch relax.
        pin = np.zeros(len(X0), bool); D = np.zeros_like(X0); att = {}
        for bn in REQUIRED[mus]:
            key = (bn, 'mid' if bn in ('sacrum', 'coccyx') else side)
            if key not in bones:
                continue
            bm = bones[key]
            cp, d, tri = trimesh.proximity.ProximityQuery(bm).on_surface(X0)
            sel = (d < d.min() + 0.004) & ~pin
            D[sel] = cp[sel] + bm.face_normals[tri[sel]] * 0.0005 - X0[sel]
            pin |= sel
            att[bn] = {'closest_before_mm': float(d.min() * 1000), 'seated_vertices': int(sel.sum())}
        D = _diffuse(D, nb, pin)
        X1 = X0 + D
        # stretch: edge-length clamp (1.8 x source) with a pull back onto her CT surface; attachments pinned
        X = edge_clamp(X1, src, idx, lambda Z: pq.on_surface(Z)[0], pin)
        # smooth the free border (the CT mask edge is ragged), then clamp again without the pull
        tmx = trimesh.Trimesh(X, idx.reshape(-1, 3), process=False)
        Xs = np.asarray(trimesh.smoothing.filter_taubin(tmx.copy(), iterations=10).vertices)
        X = np.where(pin[:, None], X, Xs)
        X = edge_clamp(X, src, idx, None, pin, iters=200)
        rounds = 'edge clamp + taubin 10'
        if M10 and mus == 'maximus':
            # milestone 10: the upper border (top 4 cm) follows the ragged CT mask edge: smooth it harder
            top = X[:, 1] > X[:, 1].max() - 0.04
            tmx = trimesh.Trimesh(X, idx.reshape(-1, 3), process=False)
            Xs = np.asarray(trimesh.smoothing.filter_taubin(tmx.copy(), iterations=40).vertices)
            X = np.where((top & ~pin)[:, None], Xs, X)
            X = edge_clamp(X, src, idx, None, pin, iters=200)
            rounds += ' + upper border taubin 40'
        if M10 and mus == 'medius':
            X, cov = cover_ilium(X, idx, src, side, bones, M, pin, tgt, nb)
            out.setdefault('_ilium_cover', {})[m['name']] = cov
            rounds += ' + ilium cover'
        if M10:
            m['preoptimized'] = True             # packaged as built (no second simplification of the male-simplified mesh)
        if shell.outside(X, 0.003).any():
            X = shell.keep_inside(X, margin=0.003, radius=0.008, iterations=20)[0]
        m2c, c2m, mean_mm, h95 = two_way(X, idx, tgt)
        for bn in att:
            key = (bn, 'mid' if bn in ('sacrum', 'coccyx') else side)
            att[bn]['closest_after_mm'] = float(trimesh.proximity.ProximityQuery(bones[key]).on_surface(X)[1].min() * 1000)
        m['pos'] = X
        m['warp_pos'] = X.copy()
        out[m['name']] = {'mean_surface_mm': mean_mm, 'model_to_ct_mm': m2c, 'ct_to_model_mm': c2m,
                          'hausdorff95_mm': h95, 'gate_3mm': max(m2c, c2m) <= 3.0,
                          'stretch_tris_over_2x': int((edge_ratio(src, X, idx) > 2).sum()), 'relax_rounds': rounds,
                          'ct_components': ncomp, 'largest_component_face_fraction': frac, 'attachments': att,
                          'volume_cm3': float(abs(trimesh.Trimesh(X, idx.reshape(-1, 3), process=False).volume) * 1e6),
                          'ct_volume_cm3': float(abs(tgt.volume) * 1e6)}
    cov = out.pop('_ilium_cover', {})
    report['m9_gluteals'] = out
    if cov:
        report['m10_ilium_cover'] = cov
        print('m10 ilium cover', cov, flush=True)
    for k, v in out.items():
        print('m9 gluteal', k, 'model->CT %.2f CT->model %.2f mm h95 %.1f mm stretch %d' % (v['model_to_ct_mm'], v['ct_to_model_mm'], v['hausdorff95_mm'], v['stretch_tris_over_2x']),
              {b: round(a['closest_after_mm'], 1) for b, a in v['attachments'].items()}, flush=True)


def _ray_first(mesh, O, Dn, maxd):
    """First hit distance of rays O + s*Dn on mesh (inf where none within maxd)."""
    out = np.full(len(O), np.inf)
    for k in range(0, len(O), 500):
        loc, ri, _ = mesh.ray.intersects_location(O[k:k + 500], Dn[k:k + 500], multiple_hits=True)
        if len(ri):
            dd = np.einsum('ij,ij->i', loc - O[k + ri], Dn[k + ri])
            ok = dd > 0
            for i, v in zip(ri[ok], dd[ok]):
                if v < out[k + i]:
                    out[k + i] = v
    out[out > maxd] = np.inf
    return out


def it_shell(M, report, male, gap=0.0012, cap=0.012):
    """The IT tract (already bound to her muscles by bind_sheets) is laid on the muscle surface under it
    (tensor fasciae latae, gluteus maximus / medius, vastus lateralis): each vertex moves to the nearest
    muscle surface point + 1.2 mm along its normal (no z-fighting after packaging), at most 12 mm per vertex (the rest follows by
    diffusion over the sheet), then a tangential stretch relax on that surface."""
    import trimesh
    res = {}
    for side in ('Left', 'Right'):
        sh = [pid for pid, m in M.items() if m['name'] == f'{side} iliotibial tract']
        if not sh:
            continue
        pid = sh[0]; m = M[pid]; idx = m['idx']; src = male[pid]['pos']
        mus = trimesh.util.concatenate([ml.to_trimesh(q['pos'], q['idx']) for q in M.values()
                                        if q['name'].startswith(side) and UNDER_TRACT.search(q['name']) and 'iliotibial' not in q['name']])
        pq = trimesh.proximity.ProximityQuery(mus)

        def onto(Z):
            cp, _, tri = pq.on_surface(Z)
            return cp + mus.face_normals[tri] * gap
        X0 = m['pos'].copy()
        d0 = pq.on_surface(X0)[1]
        pre = {'max_off_muscle_mm': float(d0.max() * 1000), 'p95_off_muscle_mm': float(np.percentile(d0, 95) * 1000),
               'stretch_tris_over_2x': int((edge_ratio(src, X0, idx) > 2).sum())}
        D = onto(X0) - X0
        L = np.linalg.norm(D, axis=1)
        big = L > cap
        D[big] *= (cap / L[big])[:, None]
        tm = trimesh.Trimesh(X0, idx.reshape(-1, 3), process=False)
        D = _diffuse(D, tm.vertex_neighbors, ~big, rounds=4)
        X = X0 + D
        X = edge_clamp(X, src, idx, onto, np.zeros(len(X), bool), w=1.0, every=3, iters=1500)
        if M10:
            # milestone 10: the upper third (over the hip) was crumpled: smooth it, then back on the muscle
            up = X[:, 1] > X[:, 1].max() - 0.15
            Xs = np.asarray(trimesh.smoothing.filter_taubin(trimesh.Trimesh(X, idx.reshape(-1, 3), process=False), iterations=20).vertices)
            X = np.where(up[:, None], Xs, X)
            X = edge_clamp(X, src, idx, onto, np.zeros(len(X), bool), w=0.5, every=3, iters=300)
            m['preoptimized'] = True
        d = pq.on_surface(X)[1]
        far = d > 0.0019                         # the 2 mm gate: last vertices placed exactly
        if far.any():
            X[far] = onto(X[far])
        d = pq.on_surface(X)[1]
        m['pos'] = X
        m['warp_pos'] = X.copy()
        res[m['name']] = {'bind_sheets_only': pre, 'moved_more_than_cap': int(big.sum()),
                          'max_off_muscle_mm': float(d.max() * 1000), 'over_2mm': int((d > 0.002).sum()),
                          'stretch_tris_over_2x': int((edge_ratio(src, X, idx) > 2).sum()),
                          'top_y_m': float(X[:, 1].max()), 'bottom_y_m': float(X[:, 1].min())}
    report['m9_it_tract'] = res
    print('m9 IT tract', res, flush=True)


def gluteofemoral_fat(F, M, skin, shell, report, inset=0.002):
    """Gluteofemoral subcutaneous fat (generated): skin (inset 2 mm) down to the outer muscle surface."""
    import trimesh
    P = np.asarray(skin.vertices); N = np.asarray(skin.vertex_normals)
    il = np.vstack([f['pos'] for n, f in F.items() if re.search(r'^VH_F_ilium', n)])
    y_crest = float(il[:, 1].max())
    fem = {s: next(m['pos'] for m in M.values() if m['name'] == f'{w} femur') for s, w in (('L', 'Left'), ('R', 'Right'))}
    extra, check = [], {}
    for side, word, sgn in (('L', 'Left', 1), ('R', 'Right', -1)):
        fv = fem[side]
        y_mid = float((fv[:, 1].min() + fv[:, 1].max()) / 2)
        wall = trimesh.util.concatenate([ml.to_trimesh(q['pos'], q['idx']) for q in M.values()
                                         if q['name'].startswith(word) and FAT_WALL.search(q['name'])])
        # thigh / hip axis at each height: femur shaft below the trochanter, the femoral head line above
        top = fv[fv[:, 1] > np.percentile(fv[:, 1], 92)]
        cx0, cz0 = float(top[:, 0].mean()), float(top[:, 2].mean())
        shaft = fv[(fv[:, 1] > y_mid - 0.03) & (fv[:, 1] < y_mid + 0.03)]
        cx1, cz1 = float(shaft[:, 0].mean()), float(shaft[:, 2].mean())
        a = np.clip((P[:, 1] - y_mid) / max(top[:, 1].mean() - y_mid, 1e-3), 0, 1)
        cx, cz = cx1 + (cx0 - cx1) * a, cz1 + (cz0 - cz1) * a
        u = np.c_[P[:, 0] - cx, P[:, 2] - cz]
        u /= np.maximum(np.linalg.norm(u, axis=1), 1e-9)[:, None]
        g = np.array([sgn * 0.45, -0.89])                  # posterolateral
        ang = (u @ g - np.cos(np.radians(80))) / 0.35     # posterior + lateral only (no flank panels in front)
        # curved borders (no flat horizontal cut): the lower border rises medially like the gluteal fold,
        # the upper border dips toward the sacrum below the iliac crest
        med = np.clip(1 - (P[:, 0] * sgn - 0.012) / 0.14, 0, 1)
        f_lo = (P[:, 1] - (y_mid - 0.01 + 0.09 * med ** 1.5)) / 0.06
        f_hi = (y_crest - 0.01 - 0.06 * med ** 2 - P[:, 1]) / 0.05
        f_mid = (P[:, 0] * sgn - 0.012) / 0.015            # not across the gluteal cleft
        kk = 6.0
        field = -np.log(np.exp(-kk * f_lo) + np.exp(-kk * f_hi) + np.exp(-kk * ang) + np.exp(-kk * f_mid)) / kk
        # the hanging arm and hand lie beside the hip: keep only skin nearer her pelvis / femur than her arm bones
        trunk = np.vstack([fv] + [f['pos'] for nm, f in F.items() if re.search(r'^VH_F_((ilium|ischium|pubis)_compact_bone_[LR]|sacrum)$', nm)])
        arm = np.vstack([q['pos'] for q in M.values() if q['system'] == 'skeletal' and q['name'].startswith(word) and
                         re.search(r'humerus|radius|ulna|metacarp|phalanx|scaphoid|lunate|capitate|hamate|trapez|triquetr|pisiform', q['name'], re.I)])
        cand = np.where((field > 0) & (P[:, 0] * sgn > 0))[0]
        region = np.zeros(len(P), bool)
        region[cand] = cKDTree(trunk).query(P[cand])[0] < cKDTree(arm).query(P[cand])[0]
        faces = skin.faces[region[skin.faces].all(1)]
        if len(faces) < 50:
            continue
        comp = max(trimesh.Trimesh(P, faces, process=False).split(only_watertight=False), key=lambda c: len(c.faces))
        _, gi = cKDTree(P).query(comp.vertices)
        n = N[gi]
        front = P[gi] - n * inset
        depth = _ray_first(wall, front, -n, 0.15)
        miss = ~np.isfinite(depth)
        print('m9 fat rays', side, 'n', len(depth), 'hit', int((~miss).sum()), 'depth mm p10/50/90',
              np.round(np.percentile(depth[~miss], [10, 50, 90]) * 1000, 1) if (~miss).any() else None, flush=True)
        if miss.any() and (~miss).any():
            _, jj = cKDTree(front[~miss]).query(front[miss])
            depth[miss] = depth[~miss][jj]
        depth = np.nan_to_num(np.maximum(depth - 0.001, 0.0004), nan=0.01, posinf=0.01)
        be = np.unique(comp.edges_sorted[trimesh.grouping.group_rows(comp.edges_sorted, require_count=1)])
        ring = np.full(len(gi), 99.0); ring[be] = 0
        nbs = comp.vertex_neighbors
        for k in range(1, 36):
            for i in np.where(ring == k - 1)[0]:
                for j in nbs[i]:
                    if ring[j] > k:
                        ring[j] = k
        t = ml.smoothstep(0, 30, ring) * ml.smoothstep(0.0, 2.5, field[gi])      # long taper: thickness -> 0 at the border
        # smooth the depth over the surface (no step where a ray grazes a different muscle)
        for _ in range(8):
            depth = 0.5 * depth + 0.5 * np.array([depth[nn].mean() if len(nn) else depth[i] for i, nn in enumerate(nbs)])
        thick = np.clip(0.0004 + t * depth, 0.0002, None)
        back = front - n * thick[:, None]
        nv = len(gi)
        bedges = comp.edges_sorted[trimesh.grouping.group_rows(comp.edges_sorted, require_count=1)]
        sidef = np.vstack([np.c_[bedges[:, 0], bedges[:, 1], bedges[:, 1] + nv], np.c_[bedges[:, 0], bedges[:, 1] + nv, bedges[:, 0] + nv]])
        fm = trimesh.Trimesh(np.vstack([front, back]), np.vstack([comp.faces, comp.faces[:, ::-1] + nv, sidef]), process=True)
        trimesh.repair.fix_normals(fm)
        trimesh.smoothing.filter_taubin(fm, iterations=30)
        V = np.asarray(fm.vertices).copy()
        V = shell.keep_inside(V, margin=0.003)[0]          # packaging may move a vertex up to 2 mm
        bad = np.where(shell.outside(V, 0.0025))[0]
        if len(bad):
            _, i = shell.tree.query(V[bad])
            V[bad] = shell.skin.vertices[i] - shell.normals[i] * 0.004
        fm = trimesh.Trimesh(V, fm.faces, process=False)
        check[side] = {'outside_skin': int(shell.outside(V).sum()), 'max_thickness_mm': float(thick.max() * 1000),
                       'median_thickness_mm_interior': float(np.median(thick[t > 0.5]) * 1000) if (t > 0.5).any() else None,
                       'y_range_m': [float(V[:, 1].min()), float(V[:, 1].max())], 'iliac_crest_y': y_crest, 'mid_thigh_y': y_mid}
        w = word.lower()
        extra.append(({'id': f'GEN_gluteofemoral_fat_{w}', 'name': f'{word} gluteofemoral subcutaneous fat',
                       'conceptId': f'GEN:gluteofemoral-fat-{w}', 'system': 'adipose', 'source': 'generated', 'accuracy': 'generated',
                       'note': 'Generated on the real VHF body: the volume between her skin (inset 2 mm) and the outer surface of the '
                               'gluteal and lateral thigh muscles, iliac crest to mid-thigh, tapering smoothly to the border.'},
                      np.asarray(fm.vertices), np.asarray(fm.faces).reshape(-1)))
    report['m9_gluteofemoral_fat'] = check
    print('m9 gluteofemoral fat', check, flush=True)
    return extra
