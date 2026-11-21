"""Geometry helpers for the female atlas pipeline (scripts/female/build_female.py).

Only numpy/scipy/trimesh are required. python-fcl is used for collision checks.
"""
import json
import struct
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------- packages

def load_package(manifest_path):
    """Read an optimized atlas package (manifest + raw .bin chunks)."""
    manifest_path = Path(manifest_path)
    atlas = json.loads(manifest_path.read_text())
    base = manifest_path.parent
    buffers = [(base / c['url'].split('/')[-1]).read_bytes() for c in atlas['chunks']]
    meshes = {}
    for p in atlas['parts']:
        b = buffers[p['chunk']]
        pos = np.frombuffer(b, np.float32, p['vertexCount'] * 3, p['positions']).reshape(-1, 3).astype(np.float64)
        nrm = np.frombuffer(b, np.int16, p['vertexCount'] * 3, p['normals']).reshape(-1, 3).copy()
        idx = np.frombuffer(b, np.uint32, p['indexCount'], p['indices']).copy()
        meshes[p['id']] = {'pos': pos, 'nrm': nrm, 'idx': idx}
    return atlas, meshes


def read_glb(path):
    """Return (doc, parts) for a glTF binary with untransformed mesh nodes.

    parts: list of {node, name, extras, path, pos (N,3), nrm (N,3) float, idx (M,)}
    """
    data = Path(path).read_bytes()
    json_len = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + json_len])
    binary = memoryview(data)[20 + json_len + 8:]
    fmts = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}
    widths = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}

    def read(i):
        a = doc['accessors'][i]
        view = doc['bufferViews'][a['bufferView']]
        dtype = np.dtype(fmts[a['componentType']])
        width = widths[a['type']]
        offset = view.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = view.get('byteStride', width * dtype.itemsize)
        if stride == width * dtype.itemsize:
            arr = np.frombuffer(binary, dtype, a['count'] * width, offset)
        else:
            rows = [np.frombuffer(binary, dtype, width, offset + k * stride) for k in range(a['count'])]
            arr = np.concatenate(rows)
        return arr.reshape(-1, width) if width > 1 else arr

    parent = {}
    for i, n in enumerate(doc['nodes']):
        for c in n.get('children', []):
            parent[c] = i

    def ancestry(i):
        out = []
        while i in parent:
            i = parent[i]
            out.append(i)
        return out

    parts = []
    for ni, node in enumerate(doc['nodes']):
        if 'mesh' not in node:
            continue
        assert not any(k in node for k in ('matrix', 'translation', 'rotation', 'scale')), node['name']
        pos, nrm, idx = [], [], []
        base = 0
        for prim in doc['meshes'][node['mesh']]['primitives']:
            assert prim.get('mode', 4) == 4
            p = read(prim['attributes']['POSITION']).astype(np.float64)
            n = read(prim['attributes']['NORMAL']).astype(np.float64)
            k = read(prim['indices']).astype(np.int64)
            pos.append(p); nrm.append(n); idx.append(k + base); base += len(p)
        parts.append({'node': ni, 'name': node['name'], 'extras': node.get('extras', {}),
                      'ancestors': ancestry(ni), 'pos': np.concatenate(pos), 'nrm': np.concatenate(nrm),
                      'idx': np.concatenate(idx)})
    return doc, parts, parent

# ---------------------------------------------------------------- mesh ops

def weld(pos, nrm, idx):
    """Merge exactly coincident vertices, averaging normals (HRA exports split them)."""
    uniq, inverse = np.unique(pos, axis=0, return_inverse=True)
    inverse = inverse.reshape(-1)
    acc = np.zeros_like(uniq)
    np.add.at(acc, inverse, nrm)
    length = np.linalg.norm(acc, axis=1, keepdims=True)
    length[length == 0] = 1
    new_idx = inverse[idx]
    tri = new_idx.reshape(-1, 3)
    keep = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])
    return uniq, acc / length, tri[keep].reshape(-1)


def vertex_normals(pos, idx):
    tri = idx.reshape(-1, 3)
    fn = np.cross(pos[tri[:, 1]] - pos[tri[:, 0]], pos[tri[:, 2]] - pos[tri[:, 0]])
    acc = np.zeros_like(pos)
    for k in range(3):
        np.add.at(acc, tri[:, k], fn)
    length = np.linalg.norm(acc, axis=1, keepdims=True)
    length[length == 0] = 1
    return acc / length


def quantize_normals(n):
    n = np.asarray(n, np.float64)
    length = np.linalg.norm(n, axis=1, keepdims=True)
    length[length == 0] = 1
    return np.clip(np.round(n / length * 32767), -32767, 32767).astype(np.int16)


def bounds(pos):
    return [pos.min(0).tolist(), pos.max(0).tolist()]


def fit_sphere(points):
    """Algebraic least-squares sphere fit → (centre, radius)."""
    A = np.c_[2 * points, np.ones(len(points))]
    b = (points ** 2).sum(1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = sol[:3]
    return c, float(np.sqrt(sol[3] + c @ c))


def femoral_head_centre(femur_pos):
    """Sphere-fit the femoral head: the top 4.5 cm of the femur, medial half."""
    top = femur_pos[:, 1].max()
    region = femur_pos[femur_pos[:, 1] > top - 0.045]
    medial = region[np.abs(region[:, 0]) < np.median(np.abs(region[:, 0]))]
    centre, radius = fit_sphere(medial)
    # Refine: keep points within 25% of the first radius estimate.
    d = np.linalg.norm(region - centre, axis=1)
    centre, radius = fit_sphere(region[np.abs(d - radius) < radius * 0.25])
    return centre, radius


def umeyama(src, dst, weights=None):
    """Least-squares similarity transform dst ≈ s R src + t."""
    src = np.asarray(src, float); dst = np.asarray(dst, float)
    w = np.ones(len(src)) if weights is None else np.asarray(weights, float)
    w = w / w.sum()
    ms, md = w @ src, w @ dst
    xs, xd = src - ms, dst - md
    cov = (xd * w[:, None]).T @ xs
    U, S, Vt = np.linalg.svd(cov)
    D = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        D[2, 2] = -1
    R = U @ D @ Vt
    var = (w * (xs ** 2).sum(1)).sum()
    s = np.trace(np.diag(S) @ D) / var
    t = md - s * R @ ms
    return s, R, t


def apply_similarity(pos, s, R, t):
    return (s * (R @ pos.T)).T + t


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def box_falloff(pos, lo, hi, margin):
    """1 inside [lo,hi], smoothly 0 at `margin` outside it."""
    d = np.maximum(np.maximum(lo - pos, pos - hi), 0)
    dist = np.linalg.norm(d, axis=1)
    return 1 - smoothstep(0, margin, dist)

# ---------------------------------------------------------------- pelvis landmarks

def pelvis_landmarks(hip_l, hip_r, sacrum, head_l, head_r):
    """Corresponding bony landmarks computed identically on any pelvis.

    hip_*: (N,3) vertices of one hip bone; sacrum: (N,3); head_*: femoral head centres
    (= acetabular centres). +x is the body's left, +y up, +z anterior.
    """
    out = {}
    for side, hip, head in (('L', hip_l, head_l), ('R', hip_r, head_r)):
        sign = 1 if side == 'L' else -1
        upper = hip[hip[:, 1] > head[1] + 0.03]
        lower = hip[hip[:, 1] < head[1]]
        out['acetabulum_' + side] = head
        out['iliac_crest_' + side] = hip[np.argmax(hip[:, 1])]
        out['iliac_lateral_' + side] = upper[np.argmax(upper[:, 0] * sign)]
        out['asis_' + side] = upper[np.argmax(upper[:, 2])]
        out['psis_' + side] = upper[np.argmin(upper[:, 2])]
        out['ischial_tuberosity_' + side] = hip[np.argmin(hip[:, 1])]
        # Symphyseal surface: the most medial 6 mm of the pubis.
        medial_low = lower[np.abs(lower[:, 0]) < np.abs(lower[:, 0]).min() + 0.006]
        out['pubic_tubercle_' + side] = lower[np.argmax(lower[:, 2])]
        out['symphysis_top_' + side] = medial_low[np.argmax(medial_low[:, 1])]
        out['symphysis_bottom_' + side] = medial_low[np.argmin(medial_low[:, 1])]
        # Pelvic brim: the most medial bone at ~3 cm above the acetabular centre (arcuate line).
        brim = hip[(np.abs(hip[:, 1] - (head[1] + 0.03)) < 0.006) & (np.abs(hip[:, 2] - head[2]) < 0.035)]
        out['inlet_lateral_' + side] = brim[np.argmin(np.abs(brim[:, 0]))]
    for side, hip in (('L', hip_l), ('R', hip_r)):
        mid_point = (out['symphysis_bottom_' + side] + out['ischial_tuberosity_' + side]) / 2
        out['ramus_mid_' + side] = hip[np.argmin(np.linalg.norm(hip - mid_point, axis=1))]
    mid = sacrum[np.abs(sacrum[:, 0]) < 0.012]
    top = mid[mid[:, 1] > mid[:, 1].max() - 0.008]
    out['sacral_base'] = top.mean(0)
    out['sacral_promontory'] = top[np.argmax(top[:, 2])]
    out['sacral_apex'] = mid[np.argmin(mid[:, 1])]
    upper_sacrum = sacrum[sacrum[:, 1] > sacrum[:, 1].max() - 0.03]
    out['sacral_ala_L'] = upper_sacrum[np.argmax(upper_sacrum[:, 0])]
    out['sacral_ala_R'] = upper_sacrum[np.argmin(upper_sacrum[:, 0])]
    return {k: np.asarray(v, float) for k, v in out.items()}


def subpubic_angle(hip_l, hip_r, lm, offset=0.025):
    """Pubic arch angle: apex at the inferior symphysis, arms to the lower border of each
    ischiopubic ramus `offset` metres lateral to the apex (coronal projection)."""
    apex = (lm['symphysis_bottom_L'] + lm['symphysis_bottom_R']) / 2
    arms = []
    for hip, sign in ((hip_l, 1), (hip_r, -1)):
        dx = (hip[:, 0] - apex[0]) * sign
        band = hip[(dx > offset - 0.003) & (dx < offset + 0.003) & (np.abs(hip[:, 2] - apex[2]) < 0.03) & (hip[:, 1] < apex[1] + 0.02)]
        arms.append(band[np.argmin(band[:, 1])][:2] - apex[:2])
    u, v = arms
    return float(np.degrees(np.arccos(u @ v / np.linalg.norm(u) / np.linalg.norm(v))))


def pelvis_measures(lm, hip_l=None, hip_r=None):
    """Sex-dimorphic measures (mm, degrees) used to document the morph."""
    d = lambda a, b: float(np.linalg.norm(lm[a] - lm[b]) * 1000)
    angle = subpubic_angle(hip_l, hip_r, lm) if hip_l is not None else None
    return {'acetabular_width': d('acetabulum_L', 'acetabulum_R'), 'interspinous_asis': d('asis_L', 'asis_R'),
            'intercristal': d('iliac_lateral_L', 'iliac_lateral_R'), 'inlet_transverse': d('inlet_lateral_L', 'inlet_lateral_R'),
            'intertuberous': d('ischial_tuberosity_L', 'ischial_tuberosity_R'), 'subpubic_angle_deg': angle,
            'sacral_width': d('sacral_ala_L', 'sacral_ala_R'), 'sacral_length': d('sacral_base', 'sacral_apex'),
            'symphysis_height': float((lm['symphysis_top_L'][1] + lm['symphysis_top_R'][1] - lm['symphysis_bottom_L'][1] - lm['symphysis_bottom_R'][1]) / 2 * 1000)}


def tps_warp(src, dst, anchors, smoothing=1e-6):
    """Return f(points) → displaced points, a thin-plate spline through src→dst.

    `anchors` are extra points mapped to themselves so the warp decays away from the pelvis.
    """
    from scipy.interpolate import RBFInterpolator
    s = np.vstack([src, anchors])
    d = np.vstack([dst - src, np.zeros_like(anchors)])
    rbf = RBFInterpolator(s, d, kernel='thin_plate_spline', smoothing=smoothing)
    return lambda pts: rbf(pts)

# ---------------------------------------------------------------- collision

def to_trimesh(pos, idx):
    import trimesh
    return trimesh.Trimesh(vertices=pos, faces=np.asarray(idx).reshape(-1, 3), process=False)


def collides(mesh_a, mesh_b):
    """True when any triangles of the two meshes intersect (python-fcl)."""
    import trimesh
    manager = trimesh.collision.CollisionManager()
    manager.add_object('b', mesh_b)
    return manager.in_collision_single(mesh_a)


def penetration(mesh_a, mesh_b, samples=4000):
    """Fraction of mesh_a's vertices that lie inside closed mesh_b, and max depth (m)."""
    import trimesh
    pts = mesh_a.vertices
    if len(pts) > samples:
        pts = pts[np.random.default_rng(0).choice(len(pts), samples, replace=False)]
    inside = mesh_b.contains(pts) if mesh_b.is_watertight else _inside_by_normal(mesh_b, pts)
    if not inside.any():
        return 0.0, 0.0
    _, dist, _ = trimesh.proximity.closest_point(mesh_b, pts[inside])
    return float(inside.mean()), float(dist.max())


def _inside_by_normal(mesh, pts):
    import trimesh
    closest, dist, tri = trimesh.proximity.closest_point(mesh, pts)
    normal = mesh.face_normals[tri]
    return ((pts - closest) * normal).sum(1) < -1e-5


def push_out(pos, fixed, margin=0.0015, radius=0.015, iterations=6, direction=None):
    """Deform soft tissue (`pos`) so no vertex lies inside or within `margin` of `fixed`.

    Penetrating vertices are moved to the fixed surface along its normal (or along a
    fixed `direction`). The displacement is spread with a Gaussian of `radius` so the tissue
    bulges smoothly instead of tearing. Returns (new_pos, max_displacement_m).
    """
    import trimesh
    from scipy.spatial import cKDTree
    pos = pos.copy()
    lo, hi = fixed.bounds[0] - margin * 2, fixed.bounds[1] + margin * 2
    total = np.zeros_like(pos)
    for _ in range(iterations):
        near = np.where(np.all((pos > lo) & (pos < hi), axis=1))[0]
        if not len(near):
            break
        closest, dist, tri = trimesh.proximity.closest_point(fixed, pos[near])
        normal = fixed.face_normals[tri]
        signed = ((pos[near] - closest) * normal).sum(1)
        bad = signed < margin
        if not bad.any():
            break
        ids = near[bad]
        if direction is None:
            disp = normal[bad] * (margin - signed[bad])[:, None]
        else:
            dirv = np.asarray(direction, float) / np.linalg.norm(direction)
            depth = (margin - signed[bad]) / np.maximum((normal[bad] @ dirv), 0.25)
            disp = dirv[None] * depth[:, None]
        from scipy.sparse import coo_matrix
        sdm = cKDTree(pos).sparse_distance_matrix(cKDTree(pos[ids]), radius * 2.5, output_type='coo_matrix')
        w = coo_matrix((np.exp(-sdm.data ** 2 / radius ** 2), (sdm.row, sdm.col)), shape=sdm.shape).tocsr()
        wsum = np.maximum(1.0, np.asarray(w.sum(1)).ravel())
        step = (w @ disp) / wsum[:, None]
        step[ids] = np.where(np.linalg.norm(step[ids], axis=1, keepdims=True) < np.linalg.norm(disp, axis=1, keepdims=True), disp, step[ids])
        pos += step
        total += step
    return pos, float(np.linalg.norm(total, axis=1).max()) if len(total) else 0.0


def _spread(pos, ids, disp, radius):
    from scipy.sparse import coo_matrix
    from scipy.spatial import cKDTree
    tree = cKDTree(pos)
    num = np.zeros_like(pos); den = np.zeros(len(pos))
    ids = np.asarray(ids)
    for k in range(0, len(ids), 2000):   # chunked: bounded memory for large protrusions
        sub = ids[k:k + 2000]
        sdm = tree.sparse_distance_matrix(cKDTree(pos[sub]), radius * 2.5, output_type='coo_matrix')
        w = coo_matrix((np.exp(-sdm.data ** 2 / radius ** 2), (sdm.row, sdm.col)), shape=sdm.shape).tocsr()
        num += w @ disp[k:k + 2000]; den += np.asarray(w.sum(1)).ravel()
    step = num / np.maximum(1.0, den)[:, None]
    step[ids] = disp  # penetrating vertices move fully
    return step


def push_out_convex(pos, hulls, margin=0.0015, radius=0.015, iterations=12):
    """Move soft tissue out of convex hulls (exact inside test via face planes), smoothly.

    Returns (new_pos, max_displacement_m, still_inside_count)."""
    pos = pos.copy()
    planes = [(h.face_normals, (h.face_normals * h.triangles[:, 0]).sum(1), h.bounds) for h in hulls]
    total = np.zeros_like(pos)
    bad_count = 0
    for _ in range(iterations):
        disp = np.zeros_like(pos)
        hit = np.zeros(len(pos), bool)
        for n, d, (lo, hi) in planes:
            near = np.where(np.all((pos > lo - margin) & (pos < hi + margin), axis=1))[0]
            if not len(near):
                continue
            sd = pos[near] @ n.T - d                      # (k, faces), >0 outside that face
            worst = sd.max(1)
            inside = worst < margin
            if not inside.any():
                continue
            k = near[inside]
            face = sd[inside].argmax(1)
            push = n[face] * (margin - worst[inside])[:, None]
            better = np.linalg.norm(push, axis=1) > np.linalg.norm(disp[k], axis=1)
            disp[k[better]] = push[better]
            hit[k] = True
        ids = np.where(hit)[0]
        bad_count = len(ids)
        if not bad_count:
            break
        step = _spread(pos, ids, disp[ids], radius)
        pos += step
        total += step
    return pos, float(np.linalg.norm(total, axis=1).max()), bad_count


def make_room(pos, idx, obstacle, direction=None, axis_point=None, axis_dir=None, sigma=0.03, step=0.003, max_amp=0.06):
    """Displace soft tissue away from a closed obstacle until their surfaces no longer intersect.

    The displacement is A·w(v)·dir(v) with w = exp(-(d/sigma)^2), d = distance from v to the
    obstacle, and A increased in `step`s until python-fcl reports no intersection. dir is either
    one fixed `direction` (moving a bowel loop off an organ) or radial from an axis
    (`axis_point`, `axis_dir`: opening a muscular sling around the vagina).
    Returns (new_pos, amplitude_m, clean)."""
    from scipy.spatial import cKDTree
    dist, _ = cKDTree(obstacle.vertices).query(pos)  # vertex distance is enough for a smooth falloff
    w = np.exp(-(dist / sigma) ** 2)
    if direction is not None:
        dirs = np.repeat(np.asarray(direction, float)[None] / np.linalg.norm(direction), len(pos), 0)
    else:
        a = np.asarray(axis_dir, float) / np.linalg.norm(axis_dir)
        rel = pos - axis_point
        rel -= np.outer(rel @ a, a)
        dirs = rel / np.maximum(np.linalg.norm(rel, axis=1, keepdims=True), 1e-9)
    amp = 0.0
    new = pos
    while amp <= max_amp + 1e-9:
        if not collides(to_trimesh(new, idx), obstacle):
            return new, amp, True
        amp += step
        new = pos + dirs * (amp * w)[:, None]
    # Could not clear within max_amp: leave the tissue where it was (reported as a residual contact).
    return pos, 0.0, False


class SkinShell:
    """Inside/outside tests against a closed skin surface (filled voxel grid + nearest surface)."""

    def __init__(self, skin, pitch=0.002):
        from scipy.spatial import cKDTree
        self.skin = skin
        self.grid = skin.voxelized(pitch=pitch).fill()
        self.tree = cKDTree(skin.vertices)
        self.normals = skin.vertex_normals

    def outside(self, pts, margin=0.0):
        """True where a point is outside the skin or within `margin` of its surface."""
        out = ~self.grid.is_filled(pts)
        if margin > 0:
            d, _ = self.tree.query(pts, distance_upper_bound=margin)
            out |= np.isfinite(d)
        return out

    def keep_inside(self, pos, margin=0.0015, radius=0.01, iterations=6):
        """Move protruding vertices to `margin` inside the skin along the inward normal, smoothly."""
        pos = pos.copy()
        total = 0.0
        for _ in range(iterations):
            bad = np.where(self.outside(pos, margin))[0]
            if not len(bad):
                break
            _, i = self.tree.query(pos[bad])
            n = self.normals[i]
            depth = ((pos[bad] - self.skin.vertices[i]) * n).sum(1) + margin
            disp = -n * np.maximum(depth, margin * 0.5)[:, None]
            step = _spread(pos, bad, disp, radius)
            pos += step
            total = max(total, float(np.linalg.norm(disp, axis=1).max()))
        return pos, total, int(self.outside(pos).sum())


def clamp_heightfield(pos, obstacle, axis, sign, margin=0.0015, window=0.008, reach=0.06):
    """Keep `pos` on the `sign` side of an obstacle surface along `axis` (e.g. in front of the
    sacrum: axis=2, sign=+1). For each vertex, the obstacle's extreme coordinate among obstacle
    points within `window` in the other two axes is the boundary; vertices behind it (by at most
    `reach`) are moved to boundary + margin."""
    from scipy.spatial import cKDTree
    other = [a for a in range(3) if a != axis]
    tree = cKDTree(obstacle[:, other])
    pos = pos.copy()
    moved = 0.0
    for v, js in enumerate(tree.query_ball_point(pos[:, other], window)):
        if not js:
            continue
        boundary = (obstacle[js, axis] * sign).max()
        cur = pos[v, axis] * sign
        if boundary - reach < cur < boundary + margin:
            moved = max(moved, boundary + margin - cur)
            pos[v, axis] = (boundary + margin) * sign
    return pos, moved


def write_obj(path, pos, idx):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as f:
        for v in pos:
            f.write(f'v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n')
        for t in np.asarray(idx).reshape(-1, 3) + 1:
            f.write(f'f {t[0]} {t[1]} {t[2]}\n')


def read_obj(path):
    pos, faces = [], []
    for line in Path(path).read_text().splitlines():
        if line.startswith('v '):
            pos.append([float(x) for x in line.split()[1:4]])
        elif line.startswith('f '):
            f = [int(s.split('/')[0]) - 1 for s in line.split()[1:]]
            for j in range(1, len(f) - 1):
                faces.extend([f[0], f[j], f[j + 1]])
    return np.array(pos, float), np.array(faces, np.int64)
