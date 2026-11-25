"""Milestone 8: articulated (jointed) hand fit on the real VHF skin.

Every carpal, metacarpal and phalanx stays rigid (shape unchanged). The hand is fitted as a chain:

* Wrist: the carpus (8 carpals + metacarpals II-V, which barely move at their CMC joints) is one unit,
  rotated about the radiocarpal joint centre (flexion / deviation / a little roll) and translated by at
  most 2 mm, keeping the radius-to-proximal-carpal gap within 1-3 mm.
* Fingers and thumb: each bone is rotated about its proximal joint (thumb CMC, MCP, PIP, DIP) within a
  physiological range of the TOTAL joint angle, so that it follows the centreline of her skin finger.
  The centrelines come from skeletonizing her skin: the Euclidean distance transform of the filled
  skin voxels has its ridge on the medial axis of each finger; a bone is centred by maximising the
  distance-to-skin of its samples (and never leaving the skin).
* Soft tissue (tendons, small hand muscles, vessels, nerves, retinacula) follows the bones by
  bone-attached linear blend skinning (inverse-distance weights to the nearest bones; radius and ulna
  are fixed anchors so the forearm does not move), then is kept 1.5 mm inside the skin.
"""
import re

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot

import meshlib as ml

CARPAL = re.compile(r'scaphoid|lunate|triquetr|pisiform|trapezium|trapezoid|capitate|hamate', re.I)
HAND_ANY = re.compile(r'carp|metacarp|phalan.*(finger|thumb)|scaphoid|lunate|triquetr|pisiform|trapezi|capitate|hamate|sesamoid.*hand', re.I)
MC = {'thumb': 'first', 'index': 'second', 'middle': 'third', 'ring': 'fourth', 'little': 'fifth'}
# Physiological ranges of the TOTAL joint angle (degrees; + = flexion toward the palm).
RANGE = {'mcp': (-20, 90), 'pip': (0, 100), 'dip': (0, 80), 'cmc1': (-30, 30), 'mcp1': (-10, 60), 'ip1': (-10, 80)}
# Bones are kept >= 2 mm inside the skin: packaging simplifies skin and bones by up to 2 mm.
CLR = 0.0025   # EDT is in 2 mm voxel steps: this needs more than one voxel of clearance
ABD = {'mcp': 20, 'pip': 0, 'dip': 0, 'cmc1': 35, 'mcp1': 10, 'ip1': 0}


def _unit(v):
    return v / max(np.linalg.norm(v), 1e-12)


class Field:
    """Distance (m) from a point to the outside of the filled skin; 0 outside. Same 2 mm voxel grid as
    the through-skin gate, so `value > 0` is exactly the gate's inside test."""

    def __init__(self, shell, lo, hi):
        g = shell.grid
        self.g = g
        a = np.clip(g.points_to_indices(lo[None])[0] - 2, 0, None)
        b = np.minimum(g.points_to_indices(hi[None])[0] + 3, np.array(g.matrix.shape))
        self.a = a
        self.edt = ndimage.distance_transform_edt(g.matrix[a[0]:b[0], a[1]:b[1], a[2]:b[2]]) * float(g.pitch[0] if np.ndim(g.pitch) else g.pitch)

    def __call__(self, pts):
        ix = self.g.points_to_indices(pts) - self.a
        ok = np.all((ix >= 0) & (ix < np.array(self.edt.shape)), axis=1)
        # beyond the cropped box: inside/outside from the full grid (distance unknown -> 1 voxel)
        out = np.where(self.g.is_filled(pts), float(self.edt.max() > 0) * 0.002, 0.0)
        out[ok] = self.edt[ix[ok, 0], ix[ok, 1], ix[ok, 2]]
        return out


def _bones(M, word):
    """Hand bones of one side, by name."""
    w = word.lower()
    ids = {pid: m['name'].lower() for pid, m in M.items() if m['system'] == 'skeletal' and HAND_ANY.search(m['name'])
           and re.search(r'\b%s\b' % w, m['name'].lower())}
    find = lambda pat: next((pid for pid, n in ids.items() if re.search(pat, n)), None)
    chains = {}
    carpus = [pid for pid, n in ids.items() if CARPAL.search(n)]
    carpus += [find(r'%s metacarpal' % MC[f]) for f in ('index', 'middle', 'ring', 'little')]
    carpus = [c for c in carpus if c]
    chains['thumb'] = [find(r'first metacarpal'), find(r'proximal phalanx of %s thumb' % w), find(r'distal phalanx of %s thumb' % w)]
    for f in ('index', 'middle', 'ring', 'little'):
        chains[f] = [find(r'%s metacarpal' % MC[f]), find(r'proximal phalanx of %s %s' % (w, f)),
                     find(r'middle phalanx of %s %s' % (w, f)), find(r'distal phalanx of %s %s' % (w, f))]
    used = set(carpus) | {b for c in chains.values() for b in c if b}
    rest = [pid for pid in ids if pid not in used]          # sesamoids etc.: carried by the nearest bone
    return carpus, chains, rest


def _joint(P, C):
    """Joint centre between a parent and a child bone: mean midpoint of their 30 closest vertex pairs."""
    d, j = cKDTree(P).query(C)
    k = np.argsort(d)[:30]
    return ((C[k] + P[j[k]]) / 2).mean(0)


def _far_dir(J, V):
    d = np.linalg.norm(V - J, axis=1)
    return _unit(V[d >= np.quantile(d, 0.95)].mean(0) - J)


def pull_to_bone(P, is_out, bone_pts, idx=None):
    """Round 2 review: soft tissue that ends up outside her (shorter, thinner) fingers is pulled
    straight back toward its nearest bone, so it folds onto the finger instead of being shoved
    sideways into spikes and sheets. is_out(points) -> bool mask."""
    P = P.copy(); P0 = P.copy()
    bad = np.where(is_out(P))[0]
    if not len(bad):
        return P, 0
    q = bone_pts[cKDTree(bone_pts).query(P[bad])[1]]
    done = np.zeros(len(bad), bool)
    for a in np.arange(0.9, 0.0, -0.1):
        sel = np.where(~done)[0]
        if not len(sel):
            break
        X = q[sel] + (P[bad[sel]] - q[sel]) * a
        ok = ~is_out(X)
        P[bad[sel[ok]]] = X[ok]
        done[sel[ok]] = True
    rest = np.where(~done)[0]
    P[bad[rest]] = q[rest] + (P[bad[rest]] - q[rest]) * 0.05
    if idx is not None:
        # spread the pull over the part's own mesh (a fold, not a pinch), then re-pull what is still out
        from scipy.sparse import coo_matrix
        t3 = idx.reshape(-1, 3); n_ = len(P)
        rr = np.r_[t3[:, 0], t3[:, 1], t3[:, 2], t3[:, 1], t3[:, 2], t3[:, 0]]
        cc = np.r_[t3[:, 1], t3[:, 2], t3[:, 0], t3[:, 0], t3[:, 1], t3[:, 2]]
        A = coo_matrix((np.ones(len(rr)), (rr, cc)), shape=(n_, n_)).tocsr(); A.data[:] = 1.0
        deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
        D = P - P0
        for _ in range(25):
            D = 0.5 * D + 0.5 * (A @ D) / deg[:, None]
            D[bad] = (P - P0)[bad]          # pulled vertices keep their pull; neighbours follow
        P = P0 + D
        P = pull_to_bone(P, is_out, bone_pts)[0]
    return P, len(bad)


def articulated_hands(M, skin, report, male=None):
    shell = ml.SkinShell(skin)
    out = {}
    touched = set()
    for word in ('Left', 'Right'):
        carpus, chains, rest = _bones(M, word)
        if not carpus:
            continue
        rad = next(pid for pid, m in M.items() if m['name'].lower() == f'{word.lower()} radius')
        uln = next(pid for pid, m in M.items() if m['name'].lower() == f'{word.lower()} ulna')
        allb = list(dict.fromkeys(carpus + [b for c in chains.values() for b in c if b] + rest))   # MC II-V are in both lists: once only
        V0 = np.vstack([M[b]['pos'] for b in allb])
        lo_e, hi_e = V0.min(0) - 0.15, V0.max(0) + 0.15
        entry = {pid: m['pos'].copy() for pid, m in M.items() if m['system'] != 'skeletal'
                 and np.all(m['pos'].max(0) > lo_e) and np.all(m['pos'].min(0) < hi_e)}
        entry_w = {pid: M[pid]['warp_pos'].copy() for pid in entry if 'warp_pos' in M[pid]}
        field = Field(shell, V0.min(0) - 0.05, V0.max(0) + 0.05)
        # ---- PRE-FIT. forearm + hand: a small rigid rotation about the elbow (<= 6 deg) so the radius, ulna and
        # hand bones lie inside her skin; soft tissue follows, fading to zero 2-6 cm below the elbow.
        hum = next(pid for pid, m in M.items() if m['name'].lower() == f'{word.lower()} humerus')
        E = _joint(M[hum]['pos'], M[uln]['pos'])
        fb = [rad, uln] + allb
        fit_set = [rad, uln] + carpus
        S = np.vstack([M[b]['pos'][::max(1, len(M[b]['pos']) // 300)] for b in fit_set])
        ax_f = _unit(M[rad]['pos'].mean(0) - E)
        u1 = _unit(np.cross(ax_f, [0, 0, 1.0])); u2 = np.cross(ax_f, u1)
        # A uniform scale (similarity: shape unchanged, as rigidify_bones allows for every bone) of at most
        # -12 % is allowed: her wrist and hand are narrower than the male's. The largest scale reaching
        # the fewest outside samples wins.
        best = (int((field(S) < CLR).sum()), np.eye(3), 1.0)
        for sc in np.arange(1.0, 0.879, -0.01):
            for a1 in np.arange(-6, 6.1, 1.5):
                for a2 in np.arange(-6, 6.1, 1.5):
                    R = sc * Rot.from_rotvec(np.radians(a1) * u1 + np.radians(a2) * u2).as_matrix()
                    o = int((field((R @ (S - E).T).T + E) < CLR).sum())
                    if o < best[0]:
                        best = (o, R, sc)
            if best[0] == 0:
                break
        Re = best[1]; scale_fa = best[2]
        nudge = float(np.degrees(np.arccos(np.clip((np.trace(Re / scale_fa) - 1) / 2, -1, 1))))
        if nudge > 0 or scale_fa < 1:
            for b in fb:
                M[b]['pos'] = (Re @ (M[b]['pos'] - E).T).T + E
            near = cKDTree(S)
            for pid, m in M.items():
                if m['system'] == 'skeletal' or np.sign(m['pos'][:, 0].mean()) != (1 if word == 'Left' else -1):
                    continue
                P = m['pos']
                if near.query(P, distance_upper_bound=0.03)[0].min() == np.inf:
                    continue
                w = ml.smoothstep(0.02, 0.06, (P - E) @ ax_f) * (near.query(P)[0] < 0.05)
                if w.max() <= 0:
                    continue
                m['pos'] = P + w[:, None] * ((Re @ (P - E).T).T + E - P)
                m['pos'] = shell.keep_inside(m['pos'], margin=0.0015, radius=0.006, iterations=12)[0]
        src = {b: M[b]['pos'].copy() for b in allb}
        D = {b: (np.eye(3), np.zeros(3)) for b in allb}
        cur = lambda b: (D[b][0] @ src[b].T).T + D[b][1]
        samp = {b: src[b][::max(1, len(src[b]) // 300)] for b in allb}
        cs = lambda b: (D[b][0] @ samp[b].T).T + D[b][1]
        V = np.vstack([src[b] for b in allb])
        # carriers for sesamoids etc.
        main_b = [b for b in allb if b not in rest]
        cent = {b: src[b].mean(0) for b in main_b}
        carry = {r: min(main_b, key=lambda b: np.linalg.norm(cent[b] - src[r].mean(0))) for r in rest}
        # subtree of each bone
        child = {}
        for f, c in chains.items():
            seq = [b for b in c if b]
            for i, b in enumerate(seq):
                child[b] = seq[i + 1:]
        for r, b in carry.items():
            for k in list(child):
                if b == k or b in child[k]:
                    child[k] = child[k] + [r]
        whole = allb

        def apply(bones, R, J, t=np.zeros(3)):
            for b in bones:
                R0, t0 = D[b]
                D[b] = (R @ R0, R @ (t0 - J) + J + t)

        def cost(bones, R, J, t=np.zeros(3), others=None):
            P = np.vstack([(R @ (cs(b) - J).T).T + J + t for b in bones])
            e = field(P)
            c = float((e < CLR).sum()) + 0.5 * float(np.clip(0.002 - e, 0, None).mean() / 0.002) - 0.3 * float(np.minimum(e, 0.008).mean() / 0.008)
            if others is not None:
                c += float((others.query(P, distance_upper_bound=0.0015)[0] < np.inf).sum()) * 0.5
            return c, int((e < CLR).sum())

        # ---- hand frame (palmar normal p, long axis L, radial axis r)
        carp_c = np.vstack([src[b] for b in carpus if CARPAL.search(M[b]['name'])]).mean(0)
        mc3 = chains['middle'][0]
        L = _unit(src[mc3].mean(0) - carp_c)
        r = src[chains['index'][0]].mean(0) - src[chains['little'][0]].mean(0)
        r = _unit(r - (r @ L) * L)
        p = _unit(np.cross(L, r))
        pis = next((b for b in carpus if re.search('pisiform', M[b]['name'], re.I)), None)
        ret = next((m['pos'].mean(0) for m in M.values() if re.search(r'flexor retinaculum of %s' % word.lower(), m['name'], re.I)), None)
        ref = ret if ret is not None else (src[pis].mean(0) if pis else None)
        if ref is not None and (ref - carp_c) @ p < 0:
            p = -p
        # ---- wrist: carpus unit about the radiocarpal joint
        prox = [b for b in carpus if re.search('scaphoid|lunate', M[b]['name'], re.I)]
        Wj = _joint(M[rad]['pos'], np.vstack([src[b] for b in prox]))
        rtree, utree = cKDTree(M[rad]['pos']), cKDTree(M[uln]['pos'])
        proxs = np.vstack([samp[b] for b in prox])

        def wrist_cost(R, t):
            # First seat the carpus 2 mm from the radius along the joint normal (gap 1-3 mm by construction).
            for _ in range(4):
                q = (R @ (proxs - Wj).T).T + Wj + t
                d, j = rtree.query(q)
                k = np.argsort(d)[:20]
                nrm = _unit((q[k] - M[rad]['pos'][j[k]]).mean(0))
                t = t + nrm * (0.002 - d.min())
            c, o = cost(whole, R, Wj, t)
            q = (R @ (proxs - Wj).T).T + Wj + t
            gap = rtree.query(q)[0].min() * 1000
            c += 1e5 * (max(0, 1.0 - gap) + max(0, gap - 3.0))
            c += 0.5 * float((utree.query(q)[0] < 0.0005).sum())
            return c, o, gap, t
        rad_axis = _unit(np.cross(L, p))           # flexion axis of the wrist
        best = (np.inf, np.eye(3), np.zeros(3), 0, 0)
        for fl in range(-45, 46, 15):
            for dv in range(-20, 31, 10):
                for rl in range(-20, 21, 10):
                    R = Rot.from_rotvec(rad_axis * np.radians(fl)).as_matrix() @ Rot.from_rotvec(p * np.radians(dv)).as_matrix() @ Rot.from_rotvec(L * np.radians(rl)).as_matrix()
                    c, o, g, t = wrist_cost(R, np.zeros(3))
                    if c < best[0]:
                        best = (c, R, t, o, g)
        R0, t0 = best[1], best[2]
        for dx in (-0.002, 0, 0.002):
            for dy in (-0.002, 0, 0.002):
                for dz in (-0.002, 0, 0.002):
                    c, o, g, t = wrist_cost(R0, t0 + np.array([dx, dy, dz]))
                    if c < best[0]:
                        best = (c, R0, t, o, g)
        apply(whole, best[1], Wj, best[2])
        wrist_rep = {'gap_radius_carpus_mm': round(best[4], 2), 'carpus_samples_outside': best[3]}
        L = best[1] @ L; p = best[1] @ p; r = best[1] @ r

        # ---- fingers and thumb, proximal to distal, two passes
        angles = {}
        for _pass in range(2):
            for f, c in chains.items():
                seq = [b for b in c if b]
                joints = ['cmc1', 'mcp1', 'ip1'] if f == 'thumb' else ['mcp', 'pip', 'dip']
                start = 0 if f == 'thumb' else 1
                for i in range(start, len(seq)):
                    b = seq[i]
                    kind = joints[i - start] if f == 'thumb' else joints[i - 1]
                    parent = seq[i - 1] if i > 0 else None
                    pv = cur(parent) if parent else np.vstack([cur(x) for x in carpus if re.search('trapezium', M[x]['name'], re.I)] or [cur(carpus[0])])
                    J = _joint(pv, cur(b))
                    d_par = _far_dir(J, pv) * -1 if parent else L
                    d_ch = _far_dir(J, cur(b))
                    a_fl = _unit(np.cross(d_par, p))
                    rest_ang = np.degrees(np.arctan2(np.cross(d_par, d_ch) @ a_fl, d_par @ d_ch))
                    lo, hi = RANGE[kind]
                    sub = [b] + child.get(b, [])
                    others = cKDTree(np.vstack([cs(x) for x in allb if x not in sub and x != parent]))
                    best = (np.inf, np.eye(3), 0.0, 0.0, 0)
                    A = ABD[kind]
                    for step, span in ((10.0, None), (2.5, 7.5)):
                        if span is None:
                            fl_set = np.arange(lo - rest_ang, hi - rest_ang + 1e-6, step)
                            ab_set = np.arange(-A, A + 1e-6, step) if A else [0.0]
                        else:
                            fl_set = np.clip(np.arange(best[2] - span, best[2] + span + 1e-6, step), lo - rest_ang, hi - rest_ang)
                            ab_set = np.clip(np.arange(best[3] - span, best[3] + span + 1e-6, step), -A, A) if A else [0.0]
                        for fl in np.unique(fl_set):
                            for ab in np.unique(ab_set):
                                R = Rot.from_rotvec(a_fl * np.radians(fl)).as_matrix() @ Rot.from_rotvec(p * np.radians(ab)).as_matrix()
                                cc, o = cost(sub, R, J, others=others)
                                if cc < best[0]:
                                    best = (cc, R, fl, ab, o)
                    apply(sub, best[1], J)
                    angles[f'{f}_{kind}'] = {'total_flexion_deg': round(float(rest_ang + best[2]), 1), 'abduction_delta_deg': round(float(best[3]), 1),
                                             'samples_outside': best[4]}
        # ---- rescue: a bone still (partly) outside her skin slides by at most 5 mm (with the bones
        # distal to it), proximal to distal; joint gaps change by at most that much.
        rescued = {}
        order = list(dict.fromkeys(b for c in chains.values() for b in c if b))
        for b in order:
            o0 = int((field(np.vstack([cur(x) for x in [b] + child.get(b, [])])) < CLR).sum())
            if not o0:
                continue
            sub = [b] + child.get(b, [])
            P0 = np.vstack([cs(x) for x in sub])
            bt = (int((field(P0) < CLR).sum()), np.zeros(3))
            g = np.arange(-0.005, 0.00501, 0.001)
            for dx in g:
                for dy in g:
                    for dz in g:
                        t = np.array([dx, dy, dz])
                        o = int((field(P0 + t) < CLR).sum())
                        if o < bt[0] or (o == bt[0] and np.linalg.norm(t) < np.linalg.norm(bt[1])):
                            bt = (o, t)
            if np.any(bt[1]):
                apply(sub, np.eye(3), np.zeros(3), bt[1])
                rescued[M[b]['name']] = [round(float(v) * 1000, 1) for v in bt[1]]
        # ---- write bones
        for b in allb:
            M[b]['pos'] = cur(b)
        bone_out = {M[b]['name']: int((field(M[b]['pos']) < CLR).sum()) for b in allb}
        # ---- soft tissue: bone-attached skinning
        anchors = [rad, uln]
        lab_pts, lab = [], []
        for i, b in enumerate(allb + anchors):
            s = src[b] if b in src else M[b]['pos']
            s = s[::max(1, len(s) // 400)]
            lab_pts.append(s); lab.append(np.full(len(s), i))
        lab_pts = np.vstack(lab_pts); lab = np.concatenate(lab)
        tree = cKDTree(lab_pts)
        Rs = [D[b][0] for b in allb] + [np.eye(3)] * 2
        ts = [D[b][1] for b in allb] + [np.zeros(3)] * 2
        lo_b, hi_b = V.min(0) - 0.03, V.max(0) + 0.03
        hand_tree = cKDTree(np.vstack([samp[b] for b in allb]))
        skinned = []
        st_skin, st_clamp = [0], [0]
        for pid, m in M.items():
            if m['system'] == 'skeletal' or pid in src:
                continue
            P = m['pos']
            if not (np.all(P.max(0) > lo_b) and np.all(P.min(0) < hi_b)):
                continue
            if np.sign(P[:, 0].mean()) != (1 if word == 'Left' else -1):
                continue
            dh = hand_tree.query(P)[0]
            if dh.min() > 0.03:
                continue
            # Round 1 review: blending 16 bones pulled tissue between fingers into sheets. Now each vertex
            # follows essentially its nearest bone; neighbours only share weight at a joint (within ~3 mm).
            d, j = tree.query(P, k=8)
            w = np.exp(-((d - d[:, :1]) / 0.003) ** 2)
            new = np.zeros_like(P); ws = np.zeros(len(P))
            for k in range(8):
                L_ = lab[j[:, k]]
                for li in np.unique(L_):
                    sel = L_ == li
                    new[sel] += w[sel, k, None] * ((Rs[li] @ P[sel].T).T + ts[li])
                    ws[sel] += w[sel, k]
            new /= ws[:, None]
            # Diffuse the skinning displacement over the part's own mesh until no triangle edge is
            # stretched past 1.8x (tendons crossing a bent joint then bend over a span, not a crease).
            t3 = m['idx'].reshape(-1, 3)
            from scipy.sparse import coo_matrix
            rr = np.r_[t3[:, 0], t3[:, 1], t3[:, 2], t3[:, 1], t3[:, 2], t3[:, 0]]
            cc_ = np.r_[t3[:, 1], t3[:, 2], t3[:, 0], t3[:, 0], t3[:, 1], t3[:, 2]]
            A = coo_matrix((np.ones(len(rr)), (rr, cc_)), shape=(len(P), len(P))).tocsr(); A.data[:] = 1.0
            deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
            ref = male[pid]['pos'] if male is not None and pid in male and len(male[pid]['pos']) == len(P) else P
            el0 = np.maximum(np.linalg.norm(ref[t3] - ref[np.roll(t3, 1, 1)], axis=2), 1e-9)
            Dp = new - P
            base = int((np.linalg.norm(P[t3] - P[np.roll(t3, 1, 1)], axis=2) / el0 > 2).any(1).sum())
            for _ in range(300):    # no more triangles past 1.9x the male source than before the fit
                if int((np.linalg.norm((P + Dp)[t3] - (P + Dp)[np.roll(t3, 1, 1)], axis=2) / el0 > 1.9).any(1).sum()) <= base:
                    break
                Dp = 0.5 * Dp + 0.5 * (A @ Dp) / deg[:, None]
            new = P + Dp
            fade = 1 - ml.smoothstep(0.03, 0.05, dh)         # far up the forearm: unchanged
            P2 = P * (1 - fade[:, None]) + new * fade[:, None]
            m['warp_pos'] = P2.copy()           # the skinned pose is this part's baseline for the stretch relax
            P2 = shell.keep_inside(P2, margin=0.0015, radius=0.006, iterations=12)[0]
            t3 = m['idx'].reshape(-1, 3)
            el = lambda X: np.linalg.norm(X[t3] - X[np.roll(t3, 1, 1)], axis=2)
            e0 = np.maximum(el(P), 1e-9)
            st_skin[0] += int((el(m['warp_pos']) / e0 > 2).any(1).sum())
            st_clamp[0] += int((el(P2) / e0 > 2).any(1).sum())
            m['pos'] = P2
            skinned.append(pid)
        bone_out = {M[b]['name']: int((field(M[b]['pos']) < CLR).sum()) for b in fb}
        # ---- round 2: soft tissue skinned FROM THE MALE REST POSE. Earlier stages (arm posing, warp)
        # had already sheared some hand parts (e.g. a palmar vein / thumb artery standing ~4 cm off the
        # bones); skinning from that pose kept the shear. Each bone's exact male->final similarity is
        # known (Umeyama on its own vertices); each soft vertex takes its nearest bones' transforms,
        # weighted by MALE-pose distance (blending only within ~3 mm of a joint), faded into the existing
        # pose 2-4 cm from the male hand bones.
        if male is not None:
            sk_b = [b for b in allb + [rad, uln] if b in male and len(male[b]['pos']) == len(M[b]['pos'])]
            T = {}
            for b in sk_b:
                s_, R_, t_ = ml.umeyama(male[b]['pos'], M[b]['pos'])
                T[b] = (s_ * R_, t_)
            mp, ml_ = [], []
            for i, b in enumerate(sk_b):
                q = male[b]['pos'][::max(1, len(male[b]['pos']) // 400)]
                mp.append(q); ml_.append(np.full(len(q), i))
            mp = np.vstack(mp); ml_ = np.concatenate(ml_)
            mtree = cKDTree(mp)
            hand_idx = np.array([b in allb for b in sk_b])
            mhand = cKDTree(mp[hand_idx[ml_]])
            remale = 0
            bone_cloud = np.vstack([M[b]['pos'] for b in allb])      # hand bones only
            near_hand = cKDTree(bone_cloud)
            for pid in list(entry):
                m = M[pid]
                if pid not in male or len(male[pid]['pos']) != len(m['pos']):
                    continue
                S0 = male[pid]['pos']
                dh = mhand.query(S0)[0]
                if dh.min() > 0.04:
                    continue
                d, j = mtree.query(S0, k=6)
                w = np.exp(-((d - d[:, :1]) / 0.003) ** 2)
                new = np.zeros_like(S0); ws = np.zeros(len(S0))
                for k in range(6):
                    L_ = ml_[j[:, k]]
                    for li in np.unique(L_):
                        sel = L_ == li
                        A_, t_ = T[sk_b[li]]
                        new[sel] += w[sel, k, None] * ((A_ @ S0[sel].T).T + t_)
                        ws[sel] += w[sel, k]
                new /= ws[:, None]
                fade = 1 - ml.smoothstep(0.02, 0.04, dh)
                P2 = m['pos'] * (1 - fade[:, None]) + new * fade[:, None]
                # pull to bone only in the hand (superficial forearm veins lie just under the skin)
                m['pos'] = pull_to_bone(P2, lambda X: (field(X) < 0.0025) & (near_hand.query(X)[0] < 0.03), bone_cloud, m['idx'])[0]
                if (field(m['pos']) <= 0).any():
                    m['pos'] = shell.keep_inside(m['pos'], margin=0.0025, radius=0.006, iterations=20)[0]
                remale += 1
            out_rm = remale
        else:
            out_rm = 0
        # ---- stretch guard: no part touched here ends with more triangles past 2x its male source
        # than it had on entry; the extra is removed by diffusing this step's displacement over the part.
        guard = {'parts': 0, 'excess_before': 0, 'excess_after': 0}
        if male is not None:
            from scipy.sparse import coo_matrix
            for pid, P_in in entry.items():
                m = M[pid]
                if pid not in male or len(male[pid]['pos']) != len(P_in) or np.array_equal(m['pos'], P_in):
                    continue
                t3 = m['idx'].reshape(-1, 3)
                e = lambda X: np.linalg.norm(X[t3] - X[np.roll(t3, 1, 1)], axis=2)
                e0 = np.maximum(e(male[pid]['pos']), 1e-9)
                cnt = lambda X: int((e(X) / e0 > 2).any(1).sum())
                base, now = cnt(P_in), cnt(m['pos'])
                if pid in entry_w:          # the level the later stretch relax would have reached
                    base = min(base, cnt(entry_w[pid]))
                if now <= base:
                    continue
                guard['parts'] += 1; guard['excess_before'] += now - base
                n_ = len(P_in)
                rr = np.r_[t3[:, 0], t3[:, 1], t3[:, 2], t3[:, 1], t3[:, 2], t3[:, 0]]
                cc_ = np.r_[t3[:, 1], t3[:, 2], t3[:, 0], t3[:, 0], t3[:, 1], t3[:, 2]]
                A = coo_matrix((np.ones(len(rr)), (rr, cc_)), shape=(n_, n_)).tocsr(); A.data[:] = 1.0
                deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
                Dd = m['pos'] - P_in
                for _ in range(400):
                    Dd = 0.5 * Dd + 0.5 * (A @ Dd) / deg[:, None]
                    if cnt(P_in + Dd) <= base:
                        break
                X = P_in + Dd
                if (field(X) <= 0).any():
                    X = shell.keep_inside(X, margin=0.0015, radius=0.004, iterations=8)[0]
                m['pos'] = X
                guard['excess_after'] += max(cnt(X) - base, 0)
            for pid, w0 in entry_w.items():   # the warp-only baseline stays the warp (as in milestone 7)
                M[pid]['warp_pos'] = w0
        touched.update(pid for pid, P_in in entry.items() if not np.array_equal(M[pid]['pos'], P_in))
        soft_out = {}
        for pid, m in M.items():
            if pid in skinned:
                o = int((field(m['pos']) <= 0).sum())
                if o:
                    soft_out[m['name']] = o
        out[word] = {'skinned_from_male_pose': out_rm, 'stretch_guard': guard, 'rescued_mm': rescued, 'forearm_nudge_deg': round(nudge, 1), 'forearm_hand_scale': round(float(scale_fa), 2), 'wrist': wrist_rep, 'joints': angles, 'bones_outside': {k: v for k, v in bone_out.items() if v},
                     'soft_parts_skinned': len(skinned), 'soft_outside': soft_out}
        ml_log = f"{word}: wrist {wrist_rep}, bones outside {sum(bone_out.values())}, soft skinned {len(skinned)}, soft outside {sum(soft_out.values())}, guard {guard}, tris>2x skinning {st_skin[0]} after clamp {st_clamp[0]}, top {sorted(soft_out.items(), key=lambda kv: -kv[1])[:6]}"
        print('articulated hands', ml_log, flush=True)
    report['articulated_hands'] = out
    TOUCHED.clear(); TOUCHED.update(touched)


TOUCHED = set()
BONES = [None]


def final_containment(M, shell, report):
    """After the global stretch relax: hand / forearm soft parts touched by the hand fit are kept inside
    the skin by moving only the vertices that are outside (plus a 4 mm neighbourhood), 1.5 mm inward."""
    n = {}
    BONES[0] = np.vstack([m['pos'] for m in M.values() if m['system'] == 'skeletal' and HAND_ANY.search(m['name'])])
    near = cKDTree(BONES[0])
    for pid in TOUCHED:
        m = M[pid]
        o = shell.outside(m["pos"], 0.002)   # packaging may move a vertex up to 2 mm
        if not o.any():
            continue
        # In the hand (within 3 cm of hand bones): pull toward the bone (folds, no spikes). Elsewhere
        # (superficial forearm veins lie just under the skin): only a gentle local push inward.
        in_hand = lambda X: near.query(X)[0] < 0.03
        pos = pull_to_bone(m['pos'], lambda X: shell.outside(X, 0.002) & in_hand(X), BONES[0], m['idx'])[0]
        if shell.outside(pos, 0.002).any():
            pos = shell.keep_inside(pos, margin=0.0025, radius=0.006, iterations=20)[0]
        bad = np.where(shell.outside(pos, 0.003))[0]   # margin: packaging moves vertices (and the skin) up to 2 mm each
        if len(bad):
            _, i = shell.tree.query(pos[bad])
            pos[bad] = shell.skin.vertices[i] - shell.normals[i] * 0.004
        m['pos'] = pos
        n[m['name']] = int(o.sum())
    report['hand_final_containment'] = n
    print('hand final containment', len(n), 'parts', sum(n.values()), 'vertices', flush=True)
