"""Female body target (version 3): the MPFB2 average adult female posed into the male pose, and
everything that is fitted to it without any non-uniform warp.

* load_mpfb(): skin + rig joints from create_mpfb_body.py (cached in work/female/mpfb/).
* add_pudendal_cleft(): schematic cleft (vulva skin surface) on the parametric body.
* similarity fits (rotation + translation + one uniform scale) for the HRA pelvis/pelvic organs,
  the HRA lungs and each breast's glands - never a non-uniform warp.
* make_breast_fat(): the breast adipose body = the skin over the breast inset by 4 mm, closed
  against the chest wall; areola and nipple meshes on the skin surface.
* hand_foot_rigid(): every hand/foot bone mapped by its own rigid transform + uniform scale onto
  the matching MPFB rig bone; soft tissue follows by linear blend skinning.
* rig_correspondences(), midline_pins(): extra warp landmarks.
"""
import json
import re
import tempfile
from pathlib import Path

import numpy as np

import meshlib as ml

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'work' / 'female' / 'mpfb'
MPFB_FILES = ('mpfb_skin.obj', 'mpfb_female_flat.obj', 'mpfb_male.obj', 'mpfb_joints.json', 'mpfb_male_joints.json', 'mpfb_info.json',
              'mpfb_skin_restx.txt', 'mpfb_female_flat_restx.txt')


# ------------------------------------------------------------------ MPFB body

def load_mpfb(male_pose_path, blender=None, bmi=22.5, stature=1.63, force=False):
    import shutil
    import trimesh
    import blender_run
    CACHE.mkdir(parents=True, exist_ok=True)
    skin_obj, joints_json = CACHE / 'mpfb_skin.obj', CACHE / 'mpfb_joints.json'
    if force or not all((CACHE / n).exists() for n in MPFB_FILES):
        tmp = Path(tempfile.gettempdir()) / 'ha-female' / 'mpfb'
        tmp.mkdir(parents=True, exist_ok=True)
        shutil.copy(male_pose_path, tmp / 'male_pose.json')
        blender_run.run(Path(__file__).with_name('create_mpfb_body.py'), [tmp / 'male_pose.json', tmp, bmi, stature],
                        blender, extensions=True)
        for n in MPFB_FILES:
            shutil.copy(tmp / n, CACHE / n)
    skin = load_obj_mesh('mpfb_skin.obj')
    joints = {k: {kk: np.array(vv) for kk, vv in v.items()} for k, v in json.loads(joints_json.read_text()).items()}
    info = json.loads((CACHE / 'mpfb_info.json').read_text())
    return skin, joints, info


def add_pudendal_cleft(skin, joints, depth=0.007, half_width=0.006):
    """Indent a midline cleft from the mons to the perineum (schematic vulva surface).
    The parametric body has a smooth closed crotch; this gives the labia majora their cleft."""
    v = skin.vertices.copy()
    n = skin.vertex_normals
    hip = (joints['upperleg01.L']['head'] + joints['upperleg01.R']['head']) / 2
    crotch = v[(np.abs(v[:, 0]) < 5e-4)]      # symmetric base mesh: true mid-sagittal vertices only
    crotch = crotch[(crotch[:, 1] < hip[1]) & (crotch[:, 1] > hip[1] - 0.2)]
    y_bottom = crotch[:, 1].min()
    y_top = y_bottom + 0.085                              # cleft ~8.5 cm (labia majora 7-12 cm)
    z_back = crotch[np.argmin(crotch[:, 1]), 2] - 0.02    # stop before the perineum/anus region
    sel = (np.abs(v[:, 0]) < 0.03) & (v[:, 1] > y_bottom - 0.01) & (v[:, 1] < y_top) & (v[:, 2] > z_back)
    w = np.exp(-(v[sel, 0] / half_width) ** 2)
    t = np.clip((v[sel, 1] - y_bottom) / (y_top - y_bottom), 0, 1)
    taper = np.sin(np.pi * np.clip(t * 1.1, 0, 1)) ** 0.6
    v[sel] -= n[sel] * (depth * w * taper)[:, None]
    skin.vertices = v
    return {'cleft_length_m': float(y_top - y_bottom), 'depth_m': depth}


# ------------------------------------------------------------------ landmarks on skins

def skin_midline_point(skin, y, front=True, x0=0.0):
    v = skin.vertices
    band = v[(np.abs(v[:, 0] - x0) < 0.008) & (np.abs(v[:, 1] - y) < 0.006)]
    return band[np.argmax(band[:, 2])] if front else band[np.argmin(band[:, 2])]


def pelvic_similarity(hra_lm, hra_heads, hra_skin, mpfb_joints, mpfb_skin):
    """Similarity mapping the HRA pelvis into the MPFB hips: acetabula -> MPFB hip joints, and the
    front/back skin midline points at hip-joint height -> the MPFB ones (one uniform scale)."""
    hl, hr = hra_heads
    fl, fr = mpfb_joints['upperleg01.L']['head'], mpfb_joints['upperleg01.R']['head']
    src = [hl, hr, skin_midline_point(hra_skin, (hl[1] + hr[1]) / 2, True), skin_midline_point(hra_skin, (hl[1] + hr[1]) / 2 + 0.05, False)]
    dst = [fl, fr, skin_midline_point(mpfb_skin, (fl[1] + fr[1]) / 2, True), skin_midline_point(mpfb_skin, (fl[1] + fr[1]) / 2 + 0.05, False)]
    return ml.umeyama(np.array(src), np.array(dst), [3, 3, 1, 1])


def thorax_similarity(hra_skin, mpfb_skin, lm_h, lm_f):
    """Similarity for the lungs from torso contours between the axilla and the 45% torso level."""
    import body_warp as bw
    src, dst = [], []
    for f in np.linspace(0.55, 0.95, 6):
        yh = lm_h['crotch'] + f * (lm_h['axilla'] - lm_h['crotch'])
        yf = lm_f['crotch'] + f * (lm_f['axilla'] - lm_f['crotch'])
        a, b = bw.torso_loop(hra_skin, yh), bw.torso_loop(mpfb_skin, yf)
        if a is None or b is None:
            continue
        pa, _ = bw.rays(a, 16); pb, _ = bw.rays(b, 16)
        keep = (np.abs(pa[:, 0]) < 0.06) | (pa[:, 1] < np.median(pa[:, 1]))   # avoid the breasts
        src.append(bw.to3(pa[keep], yh)); dst.append(bw.to3(pb[keep], yf))
    return ml.umeyama(np.vstack(src), np.vstack(dst))


# ------------------------------------------------------------------ breasts

def nipples(skin, joints):
    """Nipple = most anterior skin point of each breast (chest band, lateral of the sternum)."""
    v = skin.vertices
    sh = (joints['upperarm01.L']['head'][1] + joints['upperarm01.R']['head'][1]) / 2
    out = {}
    for side, sign in (('L', 1), ('R', -1)):
        band = v[(v[:, 0] * sign > 0.04) & (v[:, 0] * sign < 0.16) & (v[:, 1] < sh - 0.06) & (v[:, 1] > sh - 0.3)]
        out[side] = band[np.argmax(band[:, 2])]
    return out


def make_breast_fat(skin, nipple, chest_wall, inset=0.004, radius=0.085):
    """Breast adipose body: skin over the breast (within `radius` of the nipple in the coronal plane,
    in front of the chest wall) inset by `inset`, closed by a smooth back surface lying on the chest
    wall (pectoralis). Returns (vertices, triangles)."""
    import trimesh
    from scipy.spatial import cKDTree
    c = skin.triangles_center
    d2 = np.linalg.norm((c - nipple)[:, :2], axis=1)
    wall = cKDTree(chest_wall[:, :2])
    _, j = wall.query(c[:, :2])
    in_front = c[:, 2] > chest_wall[j, 2] + 0.004
    sel = np.where((d2 < radius) & in_front)[0]
    front = skin.submesh([sel], append=True)
    comps = front.split(only_watertight=False)
    front = max(comps, key=lambda m: len(m.faces))
    fv = front.vertices - front.vertex_normals * inset
    # Back surface: each front vertex dropped onto the chest wall (+1.5 mm), smoothed.
    _, k = wall.query(fv[:, :2])
    back = fv.copy()
    back[:, 2] = chest_wall[k, 2] + 0.0015
    nv = len(fv)
    edges = trimesh.grouping.group_rows(front.edges_sorted, require_count=1)
    be = front.edges_sorted[edges]
    side = np.vstack([np.c_[be[:, 0], be[:, 1], be[:, 1] + nv], np.c_[be[:, 0], be[:, 1] + nv, be[:, 0] + nv]])
    V = np.vstack([fv, back])
    F = np.vstack([front.faces, front.faces[:, ::-1] + nv, side])
    m = trimesh.Trimesh(V, F, process=True)
    trimesh.smoothing.filter_taubin(m, iterations=10)
    return np.asarray(m.vertices), np.asarray(m.faces).reshape(-1)


def areola_and_nipple(skin, nipple, areola_r=0.019, nipple_r=0.005, nipple_h=0.006):
    """Areola: the skin disc around the nipple lifted 0.5 mm (a thin shell on the surface).
    Nipple: a rounded cylinder along the skin normal. Generated, on the skin surface."""
    import trimesh
    c = skin.triangles_center
    sel = np.where(np.linalg.norm(c - nipple, axis=1) < areola_r)[0]
    disc = skin.submesh([sel], append=True)
    disc = max(disc.split(only_watertight=False), key=lambda m: len(m.faces))
    top = disc.vertices + disc.vertex_normals * 0.0012
    bot = disc.vertices + disc.vertex_normals * 0.0002
    nv = len(top)
    edges = trimesh.grouping.group_rows(disc.edges_sorted, require_count=1)
    be = disc.edges_sorted[edges]
    side = np.vstack([np.c_[be[:, 0], be[:, 1], be[:, 1] + nv], np.c_[be[:, 0], be[:, 1] + nv, be[:, 0] + nv]])
    areola = (np.vstack([top, bot]), np.vstack([disc.faces, disc.faces[:, ::-1] + nv, side]).reshape(-1))
    _, i = trimesh.proximity.ProximityQuery(skin).vertex(nipple[None])
    n = skin.vertex_normals[i[0]]
    cyl = trimesh.creation.capsule(height=nipple_h, radius=nipple_r, count=[12, 12])
    z = np.array([0, 0, 1.0])
    v = np.cross(z, n); s = np.linalg.norm(v); cth = z @ n
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    R = np.eye(3) + vx + vx @ vx * ((1 - cth) / max(s * s, 1e-12))
    nip = (cyl.vertices @ R.T + nipple + n * (nipple_h / 2 - 0.001), np.asarray(cyl.faces).reshape(-1))
    return areola, nip


# ------------------------------------------------------------------ hands and feet

HAND_RIG = {}  # male bone name -> MPFB rig bone name (filled by hand_foot_map)


def hand_foot_map(pose):
    """Male bone -> MPFB rig bone for every metacarpal, phalanx, metatarsal and toe phalanx."""
    out = {}
    for name, b in pose['bones'].items():
        s = b['side']
        if 'finger' in b:
            k, j = b['finger'], b['index']
            if k == 1:
                out[name] = f'finger1-{j + 1}.{s}'
            elif j == 0:
                out[name] = f'metacarpal{k - 1}.{s}'
            else:
                out[name] = f'finger{k}-{j}.{s}'
        elif 'toe' in b:
            k, j = b['toe'], b['index']
            if j == 0:
                continue  # metatarsals follow the foot bone transform
            out[name] = f'toe{k}-{j}.{s}' if k != 1 else f'toe1-{min(j, 2)}.{s}'
    return out


def frame(axis, normal):
    a = axis / np.linalg.norm(axis)
    n = normal - a * (normal @ a); n /= np.linalg.norm(n)
    return np.c_[a, n, np.cross(a, n)]


def bone_transform(p0, p1, q0, q1, n_m, n_f, scale=None):
    """Rigid rotation + uniform scale taking male segment p0->p1 (with reference normal n_m) onto
    female segment q0->q1 (normal n_f). Returns f(points)."""
    Rm, Rf = frame(p1 - p0, n_m), frame(q1 - q0, n_f)
    R = Rf @ Rm.T
    s = scale if scale is not None else np.linalg.norm(q1 - q0) / max(np.linalg.norm(p1 - p0), 1e-9)
    return lambda x: (s * (R @ (x - p0).T)).T + q0, s


def palm_normal(mc2_0, mc2_1, mc5_0):
    return np.cross(mc2_1 - mc2_0, mc5_0 - mc2_0)


def seg_dist(x, a, b):
    d = b - a
    u = np.clip(((x - a) @ d) / max(d @ d, 1e-12), 0, 1)
    return np.linalg.norm(x - (a + u[:, None] * d), axis=1)


def _rot_frames(a_m, n_m, a_f, n_f):
    return frame(a_f, n_f) @ frame(a_m, n_m).T


def min_rotation(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = a @ b; s = np.linalg.norm(v)
    if s < 1e-9:
        return np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * ((1 - c) / s ** 2)


def rigid_legs(M, male, pose, joints, acetabula, report):
    """Long bones of the lower limb without any spline: femur + patella get one rotation + uniform
    scale (male hip->knee onto the real HRA acetabulum -> female rig knee), tibia + fibula another
    (knee->ankle onto rig knee->ankle). Minimal rotations keep the male bones' axial roll, so the
    patella faces forward and the tibial tuberosity stays below it; the femur converges on the knee
    from the wider female hip (valgus)."""
    J = {k: np.array(v) for k, v in pose['joints'].items()}
    names = {p['name']: pid for pid, p in M.items()}
    out = {}
    for s, word in (('L', 'Left'), ('R', 'Right')):
        hip_m, knee_m, ankle_m = J[f'hip.{s}'], J[f'knee.{s}'], J[f'ankle.{s}']
        hip_f, knee_f, ankle_f = acetabula[s], joints[f'lowerleg01.{s}']['head'], joints[f'foot.{s}']['head']
        sh_m, el_m, wr_m = J[f'shoulder.{s}'], J[f'elbow.{s}'], J[f'wrist.{s}']
        sh_f, el_f, wr_f = (joints[f'{b}.{s}']['head'] for b in ('upperarm01', 'lowerarm01', 'wrist'))
        for bones, (a_m, b_m, a_f, b_f) in (((f'{word} femur', f'{word} patella'), (hip_m, knee_m, hip_f, knee_f)),
                                            ((f'{word} tibia', f'{word} fibula'), (knee_m, ankle_m, knee_f, ankle_f)),
                                            ((f'{word} humerus',), (sh_m, el_m, sh_f, el_f)),
                                            ((f'{word} radius', f'{word} ulna'), (el_m, wr_m, el_f, wr_f))):
            R = min_rotation(b_m - a_m, b_f - a_f)
            sc = np.linalg.norm(b_f - a_f) / np.linalg.norm(b_m - a_m)
            for b in bones:
                pid = names.get(b)
                if pid:
                    M[pid]['pos'] = (sc * (R @ (male[pid]['pos'] - a_m).T)).T + a_f
            out[f'{bones[0]}'] = {'scale': float(sc), 'rotation_deg': float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))}
    report['rigid_legs'] = out
    print('rigid legs', out, flush=True)


def rigid_hands_feet(M, male, pose, joints, report):
    """Hands and feet without any RBF: one similarity per hand/foot (wrist/ankle + rig joints) for
    carpals/tarsals/metatarsals; every metacarpal and phalanx gets its own rotation onto its MPFB rig
    bone with that one uniform scale (aspect ratios exactly preserved). Soft tissue of the hand/foot
    follows the bones by linear blend skinning (inverse-distance weights to the male bone axes)."""
    J = joints
    bones = pose['bones']
    bmap = hand_foot_map(pose)
    out = {}

    def setup(limb, s, word):
        if True:
            if limb == 'hand':
                names = [n for n, b in bones.items() if b['side'] == s and 'finger' in b]
                mc = {k: bones[f'{word} {w} metacarpal bone'] for k, w in ((2, 'second'), (5, 'fifth'))}
                root_m = np.array(pose['joints'][f'wrist.{s}'])
                src = [root_m] + [np.array(bones[n]['p1']) for n in names if bones[n]['index'] == 0]
                dst = [J[f'wrist.{s}']['head']] + [J[bmap[n]]['tail'] for n in names if bones[n]['index'] == 0]
                n_m = palm_normal(np.array(mc[2]['p0']), np.array(mc[2]['p1']), np.array(mc[5]['p0']))
                n_f = palm_normal(J[f'metacarpal1.{s}']['head'], J[f'metacarpal1.{s}']['tail'], J[f'metacarpal4.{s}']['head'])
                axis_m = np.array(mc[2]['p1']) - root_m
            else:
                names = [n for n, b in bones.items() if b['side'] == s and 'toe' in b]
                root_m = np.array(pose['joints'][f'ankle.{s}'])
                prox = [n for n in names if bones[n]['index'] == 1 and n in bmap]
                src = [root_m] + [np.array(bones[n]['p0']) for n in prox]
                dst = [J[f'foot.{s}']['head']] + [J[bmap[n]]['head'] for n in prox]
                t1 = [n for n in prox if bones[n]['toe'] == 1]; t5 = [n for n in prox if bones[n]['toe'] == 5]
                n_m = np.cross(np.array(bones[t1[0]]['p0']) - root_m, np.array(bones[t5[0]]['p0']) - root_m)
                n_f = np.cross(J[bmap[t1[0]]]['head'] - J[f'foot.{s}']['head'], J[bmap[t5[0]]]['head'] - J[f'foot.{s}']['head'])
                axis_m = np.array(bones[t1[0]]['p0']) - root_m
        return names, np.array(src), np.array(dst), n_m, n_f, root_m, axis_m

    # One uniform scale per limb type (mean of left and right) keeps the two sides symmetric.
    limb_scale = {limb: float(np.mean([ml.umeyama(*setup(limb, s, w)[1:3])[0] for s, w in (('L', 'left'), ('R', 'right'))]))
                  for limb in ('hand', 'foot')}
    for limb in ('hand', 'foot'):
        for s, word in (('L', 'left'), ('R', 'right')):
            names, src, dst, n_m, n_f, root_m, axis_m = setup(limb, s, word)
            _, R, _ = ml.umeyama(src, dst)
            sc = limb_scale[limb]
            t = dst.mean(0) - sc * R @ src.mean(0)
            H = lambda x, sc=sc, R=R, t=t: ml.apply_similarity(x, sc, R, t)
            # Per-bone transforms.
            T = {}
            for n in names:
                b = bones[n]
                p0, p1 = np.array(b['p0']), np.array(b['p1'])
                if n in bmap:
                    # Joint-anchored: the bone's proximal end sits on the rig joint (head), its axis
                    # along the rig bone, one uniform scale = rig bone length / bone length, so
                    # consecutive phalanges meet at the joints (no gaps) and aspect ratios are exact.
                    q0, q1 = J[bmap[n]]['head'], J[bmap[n]]['tail']
                    Rb = _rot_frames(p1 - p0, n_m, q1 - q0, n_f)
                    sb = float(np.clip(np.linalg.norm(q1 - q0) / max(np.linalg.norm(p1 - p0), 1e-6), 0.6, 1.3))
                    T[n] = (lambda x, Rb=Rb, p0=p0, q0=q0, sb=sb: (sb * (Rb @ (x - p0).T)).T + q0, p0, p1)
                else:
                    T[n] = (H, p0, p1)
            # Apply to the bones; LBS for everything else past the wrist/ankle.
            seg_list = list(T.values())
            ids = {bones[n]['id']: n for n in names}
            ax = axis_m / np.linalg.norm(axis_m)
            moved = 0
            for pid, m in M.items():
                src_pos = male[pid]['pos']
                if pid in ids:
                    m['pos'] = T[ids[pid]][0](src_pos)
                    moved += 1
                    continue
                u = (src_pos - root_m) @ ax
                near = np.min([seg_dist(src_pos, a, b) for _, a, b in seg_list], axis=0)
                w_in = ml.smoothstep(-0.025, 0.005, u) * (1 - ml.smoothstep(0.02, 0.035, near))
                w_in *= (np.sign(src_pos[:, 0]) == (1 if s == 'L' else -1))
                if w_in.max() < 1e-3:
                    continue
                D = np.stack([seg_dist(src_pos, a, b) for _, a, b in seg_list] + [np.linalg.norm(src_pos - root_m, axis=1) + 0.01])
                W = 1.0 / (D + 0.004) ** 4
                W /= W.sum(0)
                new = sum(W[k][:, None] * f(src_pos) for k, (f, _, _) in enumerate(seg_list))
                new += W[-1][:, None] * H(src_pos)
                m['pos'] = m['pos'] * (1 - w_in[:, None]) + new * w_in[:, None]
                moved += 1
            out[f'{limb}.{s}'] = {'scale': float(sc), 'bones': len(names), 'parts_moved': moved}
    report['rigid_hands_feet'] = out
    print('rigid hands/feet', out, flush=True)


# ------------------------------------------------------------------ dense correspondences

def flatten_thigh_contact(P, restx, gap=0.0008):
    """Where the posed thighs press together, flatten each side onto its own side of the midline
    (as soft tissue does) instead of letting the two legs interpenetrate. Leg side = sign of the
    vertex's rest-pose x. Only below the crotch (lowest exact mid-sagittal vertex)."""
    P = P.copy()
    mid = np.abs(restx) < 5e-4
    crotch = P[mid & (P[:, 1] < 1.0), 1].min()
    side = np.sign(restx)
    leg = (P[:, 1] < crotch) & (np.abs(restx) > 1e-3)
    bad = leg & (P[:, 0] * side < gap)
    P[bad, 0] = side[bad] * gap
    return P, int(bad.sum())


def load_obj_mesh(name):
    import trimesh
    p, i = ml.read_obj(CACHE / name)
    rx = CACHE / name.replace('.obj', '_restx.txt')
    if rx.exists() and 'male.obj' not in name:
        p, _ = flatten_thigh_contact(p, np.loadtxt(rx))
    return trimesh.Trimesh(p, i.reshape(-1, 3), process=False)


def fit_to_surface(P, neighbors, target, iters=25, reject=0.04, smooth=6):
    """Fit the MPFB male mesh to the BodyParts3D male skin: similarity ICP, then a smooth non-rigid
    ICP (closest-point displacements, outliers > 4 cm rejected, averaged over the mesh neighbourhood
    `smooth` times, half step per iteration). Returns (fitted vertices, info)."""
    from scipy.spatial import cKDTree
    T = np.asarray(target.vertices)
    tree = cKDTree(T)
    X = P.copy()
    for _ in range(15):
        d, j = tree.query(X)
        ok = d < np.percentile(d, 90)
        s, R, t = ml.umeyama(X[ok], T[j[ok]])
        X = ml.apply_similarity(X, s, R, t)
    rigid_gap = float(np.median(tree.query(X)[0]) * 1000)
    sim = ml.umeyama(P, X)                  # cumulative similarity (for the rig joints)
    nb = [np.asarray(n) for n in neighbors]
    deg = np.array([len(n) for n in nb])
    flat_idx = np.concatenate(nb); owner = np.repeat(np.arange(len(nb)), deg)

    def average(D):
        acc = np.zeros_like(D)
        np.add.at(acc, owner, D[flat_idx])
        return (D + acc) / (1 + deg)[:, None]

    for _ in range(iters):
        d, j = tree.query(X)
        D = T[j] - X
        w = (d < reject).astype(float)
        D *= w[:, None]
        W = w[:, None]
        for _ in range(smooth):
            D, W = average(D), average(W)
        X = X + 0.5 * D / np.maximum(W, 1e-6)
    gap = tree.query(X)[0]
    return X, {'sim': sim, 'similarity_median_gap_mm': rigid_gap, 'nonrigid_median_gap_mm': float(np.median(gap) * 1000),
               'nonrigid_p95_gap_mm': float(np.percentile(gap, 95) * 1000)}


def dense_correspondences(m_skin, pose, spacing=0.025, max_gap=0.025):
    """Male surface -> female surface pairs through the MPFB male / flat-female pair (identical
    topology): src = closest point of the BodyParts3D male skin to MPFB-male vertex i, dst = flat
    female vertex i. Hands (past the wrist) are excluded - they get per-bone rigid transforms.
    Plus interior joints: BodyParts3D joint -> female rig joint + the joint's offset from the MPFB male
    rig joint (scaled by the stature ratio). Returns (src, dst, tags)."""
    import trimesh
    male_m, flat = load_obj_mesh('mpfb_male.obj'), load_obj_mesh('mpfb_female_flat.obj')
    Jm = {k: {kk: np.array(vv) for kk, vv in v.items()} for k, v in json.loads((CACHE / 'mpfb_male_joints.json').read_text()).items()}
    Jf = {k: {kk: np.array(vv) for kk, vv in v.items()} for k, v in json.loads((CACHE / 'mpfb_joints.json').read_text()).items()}
    Pm, Pf = np.asarray(male_m.vertices), np.asarray(flat.vertices)
    assert len(Pm) == len(Pf), 'MPFB male and female meshes must share topology'
    Pm, fit_info = fit_to_surface(Pm, male_m.vertex_neighbors, m_skin)
    s_, R_, t_ = fit_info.pop('sim')
    for k in Jm:
        for e in ('head', 'tail'):
            Jm[k][e] = ml.apply_similarity(Jm[k][e][None], s_, R_, t_)[0]
    keep = np.ones(len(Pm), bool)
    for s in 'LR':                                     # drop the hands
        w, e = Jm[f'wrist.{s}']['head'], Jm[f'lowerarm01.{s}']['head']
        ax = (w - e) / np.linalg.norm(w - e)
        keep &= ~(((Pm - w) @ ax > -0.01) & (np.linalg.norm(Pm - w, axis=1) < 0.25))
    # Even subsample (voxel grid).
    key = np.floor(Pm / spacing).astype(int)
    _, first = np.unique(key[keep], axis=0, return_index=True)
    ids = np.where(keep)[0][first]
    closest, dist, _ = trimesh.proximity.closest_point(m_skin, Pm[ids])
    ok = dist < max_gap
    src, dst = [closest[ok]], [Pf[ids][ok]]
    tags = ['skin-dense'] * int(ok.sum())
    ratio = np.ptp(Pf[:, 1]) / np.ptp(Pm[:, 1])
    J = {k: np.array(v) for k, v in pose['joints'].items()}
    for s in 'LR':
        for mk, b in (('shoulder', 'upperarm01'), ('elbow', 'lowerarm01'), ('wrist', 'wrist'), ('knee', 'lowerleg01'), ('ankle', 'foot')):
            if f'{mk}.{s}' in J:
                src.append(J[f'{mk}.{s}'][None])
                dst.append((Jf[f'{b}.{s}']['head'] + (J[f'{mk}.{s}'] - Jm[f'{b}.{s}']['head']) * ratio)[None])
                tags.append('rig-joints')
    for k, b in (('C7', 'neck01'), ('C5', 'neck02'), ('C3', 'neck03')):
        if k in J:
            src.append(J[k][None]); dst.append((Jf[b]['head'] + (J[k] - Jm[b]['head']) * ratio)[None]); tags.append('rig-joints')
    return np.vstack(src), np.vstack(dst), tags, {'pairs': int(ok.sum()), 'dropped_gap': int((~ok).sum()),
                                                   'gap_mm_median': float(np.median(dist) * 1000), **fit_info}


def raise_breasts(skin, flat, dy):
    """Lift each breast mound `dy` m cranially (a smooth translation, as in a mastopexy): weight 1 on
    the mound (where the breast adds > 6 mm over the flat chest), falling to 0 over the surrounding
    skin by mesh diffusion, so the mound keeps its shape and the transition stays smooth.
    Returns (lifted skin vertices, lifted flat-chest vertices) - the latter is the chest wall under
    the lifted mound, used for the back surface of the fat."""
    P, Q = np.asarray(skin.vertices), np.asarray(flat.vertices)
    B = np.linalg.norm(P - Q, axis=1)
    w = np.clip(B / 0.006, 0, 1)
    nb = [np.asarray(n) for n in skin.vertex_neighbors]
    deg = np.array([len(n) for n in nb]); idx = np.concatenate(nb); owner = np.repeat(np.arange(len(nb)), deg)
    for _ in range(25):                     # diffuse: smooth falloff a few cm beyond the mound
        acc = np.zeros(len(P)); np.add.at(acc, owner, w[idx])
        w = np.maximum(w, 0.5 * (w + acc / np.maximum(deg, 1))) * (np.abs(P[:, 0]) > 0.004)
    w = np.where(B > 0.006, 1.0, np.minimum(w, 1.0))
    lift = np.c_[np.zeros(len(P)), dy * w, np.zeros(len(P))]
    return P + lift, Q + lift


def breast_fat_from_pair(skin, flat, inset=0.004, back=0.008, thresh=0.002, y_range=None):
    """Breast adipose body from the female skin vs the same body with a flat chest (same topology):
    front = skin inset 4 mm, back = flat chest 8 mm deep (on pectoralis), region = where the breast
    adds > 2 mm, grown by two rings. One component per side."""
    import trimesh
    P, Q = np.asarray(skin.vertices), np.asarray(flat.vertices)
    d = np.linalg.norm(P - Q, axis=1)
    sel = d > thresh
    sel &= (P[:, 1] > np.percentile(P[sel, 1], 1) - 0.02) if sel.any() else sel
    adj = skin.vertex_neighbors
    for _ in range(2):
        grow = sel.copy()
        for i in np.where(sel)[0]:
            grow[adj[i]] = True
        sel = grow
    out = {}
    for side, sign in (('L', 1), ('R', -1)):
        ss = sel & (P[:, 0] * sign > 0.03)           # lateral to the sternal edge, never over the sternum
        if y_range is not None:                      # footprint: between the 2nd and 6th ribs
            # Inframammary fold: lowest (6th rib) under the breast's centre, curving up medially and
            # laterally (+3 cm at 7 cm from the centre) - a natural U, never a straight cut.
            xc = np.average(P[ss, 0], weights=np.linalg.norm(P - Q, axis=1)[ss] + 1e-9) if ss.any() else 0.1 * sign
            fold = y_range[0] + 6.0 * (P[:, 0] - xc) ** 2
            ss &= (P[:, 1] >= fold) & (P[:, 1] <= y_range[1])
        faces = skin.faces[ss[skin.faces].all(1)]
        comps = trimesh.Trimesh(P, faces, process=False).split(only_watertight=False)
        comp = max(comps, key=lambda c: len(c.faces))
        # map comp vertices back to global indices
        _, gi = trimesh.proximity.ProximityQuery(skin).vertex(comp.vertices)
        n = skin.vertex_normals[gi]
        nf = flat.vertex_normals[gi]
        front = P[gi] - n * inset
        backv = Q[gi] - nf * back
        nv = len(gi)
        be = comp.edges_sorted[trimesh.grouping.group_rows(comp.edges_sorted, require_count=1)]
        side_f = np.vstack([np.c_[be[:, 0], be[:, 1], be[:, 1] + nv], np.c_[be[:, 0], be[:, 1] + nv, be[:, 0] + nv]])
        m = trimesh.Trimesh(np.vstack([front, backv]), np.vstack([comp.faces, comp.faces[:, ::-1] + nv, side_f]), process=True)
        trimesh.repair.fix_normals(m)
        trimesh.smoothing.filter_taubin(m, iterations=8)
        out[side] = m
    return out


# ------------------------------------------------------------------ retarget the HRA data

def retarget_hra(hra, shift, male_pose_path, report, blender=None):
    """Move the whole HRA data set (feet on y=0) into the MPFB body: pelvis and pelvic organs by
    one similarity (acetabula -> MPFB hip joints), lungs by a thorax similarity, then replace the
    HRA skin by the MPFB skin. Shift is applied in place. Returns (mpfb skin, joints, info)."""
    import body_warp as bw
    for p in hra.values():
        p['pos'] = p['pos'] + shift
    skin, joints, info = load_mpfb(male_pose_path, blender)
    report['mpfb_cleft'] = add_pudendal_cleft(skin, joints)
    hl, _ = ml.femoral_head_centre(hra['VH_F_femur_L']['pos'])
    hr, _ = ml.femoral_head_centre(hra['VH_F_femur_R']['pos'])
    wp, _, wi = ml.weld(hra['VH_F_skin']['pos'], hra['VH_F_skin']['nrm'], hra['VH_F_skin']['idx'])
    hra_skin = ml.to_trimesh(wp, wi)
    s, R, t = pelvic_similarity(None, (hl, hr), hra_skin, joints, skin)
    lung_names = [n for n, p in hra.items() if 'VH_F_lungs' in p['ancestor_names'] or n == 'VH_F_lungs']
    # Pelvic soft organs (uterus, adnexa, vagina, bladder, uterine vessels) move as ONE rigid block
    # (rotation + translation, NO scale): the block centroid goes where the similarity puts it, so the
    # real HRA uterus and bladder keep their scanned size. The bony pelvis takes the similarity.
    organ = [n for n, p in hra.items() if any(a in p['ancestor_names'] for a in
             ('VH_F_reproductive_system', 'VH_F_urinary_bladder', 'VH_F_blood_vasculature_of_uterus')) and 'mammary' not in n]
    oc = np.vstack([hra[n]['pos'] for n in organ]).mean(0) if organ else np.zeros(3)
    oc_new = ml.apply_similarity(oc[None], s, R, t)[0]
    for n, p in hra.items():
        if n == 'VH_F_skin' or n in lung_names:
            continue
        if n in organ:
            p['pos'] = (R @ (p['pos'] - oc).T).T + oc_new
        else:
            p['pos'] = ml.apply_similarity(p['pos'], s, R, t)
        p['nrm'] = (R @ p['nrm'].T).T
    hra_skin.vertices = ml.apply_similarity(np.asarray(hra_skin.vertices), s, R, t)
    lm_h, lm_f = bw.body_levels(hra_skin), bw.body_levels(skin)
    s2, R2, t2 = thorax_similarity(hra_skin, skin, lm_h, lm_f)
    for n in lung_names:
        p = hra[n]
        p['pos'] = ml.apply_similarity(ml.apply_similarity(p['pos'], s, R, t), s2, R2, t2)
        p['nrm'] = (R2 @ R @ p['nrm'].T).T
    hra['VH_F_skin'] = dict(hra['VH_F_skin'], pos=np.asarray(skin.vertices, float), nrm=np.asarray(skin.vertex_normals, float),
                            idx=np.asarray(skin.faces, np.uint32).reshape(-1))
    report['retarget'] = {'pelvic_similarity_scale': float(s), 'thorax_similarity_scale': float(s2 * s),
                          'mpfb': info, 'hips_mpfb': [joints['upperleg01.L']['head'].tolist(), joints['upperleg01.R']['head'].tolist()]}
    return skin, joints, info


def rig_correspondences(pose, joints, skin):
    """Male joint -> MPFB rig joint (same pose, so these are small displacements)."""
    J = {k: np.array(v) for k, v in pose['joints'].items()}
    src, dst = [], []
    for s in 'LR':
        for mk, (fb, end) in (('shoulder', ('upperarm01', 'head')), ('elbow', ('lowerarm01', 'head')), ('wrist', ('wrist', 'head')),
                              ('hip', ('upperleg01', 'head')), ('knee', ('lowerleg01', 'head')), ('ankle', ('foot', 'head'))):
            if f'{mk}.{s}' in J:
                src.append(J[f'{mk}.{s}']); dst.append(joints[f'{fb}.{s}'][end])
    neck = [joints['neck01']['head'], joints['neck02']['head'], joints['neck03']['head']]
    for k, q in (('C7', neck[0]), ('C5', neck[1]), ('C4', (neck[1] + neck[2]) / 2), ('C3', neck[2])):
        if k in J:
            src.append(J[k]); dst.append(q)
    v = np.asarray(skin.vertices)
    top = v[np.argmax(v[:, 1])]
    if 'vertex' in J:
        src.append(J['vertex']); dst.append(top)
    return np.array(src), np.array(dst)
