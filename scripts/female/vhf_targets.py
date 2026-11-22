"""Step 2 + 4: the VHF CT in the HRA VHF frame, and one target mesh per TotalSegmentator label.

    python scripts/female/vhf_targets.py         (TotalSegmentator venv)

1. Body outline of each CT volume (HU > -400, largest component) -> surface mesh.
2. DICOM patient frame (LPS, mm) -> atlas frame (x left, y up, z anterior; m): (x, z, -y) / 1000,
   then ONE rigid transform (ICP, no scale) of the CT body surface onto the HRA VHF skin (the HRA
   organs were made from the same donor, so the CT and HRA should differ by a rigid move).
   The two CT volumes (head->femur, femur->toes) are registered separately (the donor was
   repositioned between them) - each gets its own rigid transform.
3. Each TotalSegmentator "total" label (Apache-2.0 model) -> marching cubes, Taubin smoothing,
   decimation -> work/vhf/targets/<label>.npz (vertices in the atlas frame, faces).
4. Overlap report (Step 2 gate): mean / 95th-percentile distance CT body surface -> HRA skin, and
   CT hips -> HRA pelvis.
"""
import json
import sys
from pathlib import Path

import numpy as np
import SimpleITK as sitk

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work' / 'vhf'
sys.path.insert(0, str(Path(__file__).parent))
import meshlib as ml  # noqa: E402


def lps_to_atlas(p):
    p = np.asarray(p, float) / 1000.0
    return np.c_[p[:, 0], p[:, 2], -p[:, 1]]


def mask_mesh(mask, img, step=1, smooth=10, target_faces=None):
    """Binary mask (z,y,x numpy) -> triangle mesh in LPS mm."""
    import trimesh
    from skimage import measure
    if mask.sum() < 50:
        return None
    pad = np.pad(mask.astype(np.float32), 1)
    v, f, _, _ = measure.marching_cubes(pad, 0.5, step_size=step)
    v -= 1
    idx = v[:, ::-1]                                       # (x, y, z) voxel index
    sp, org = np.array(img.GetSpacing()), np.array(img.GetOrigin())
    D = np.array(img.GetDirection()).reshape(3, 3)
    pts = (D @ (idx * sp).T).T + org
    m = trimesh.Trimesh(pts, f[:, ::-1], process=True)
    trimesh.smoothing.filter_taubin(m, iterations=smooth)
    if target_faces and len(m.faces) > target_faces:
        try:
            m = m.simplify_quadric_decimation(face_count=target_faces)
        except Exception:
            pass
    return m


def body_surface(img):
    from scipy import ndimage
    a = sitk.GetArrayFromImage(img)
    m = a > -400
    lab, n = ndimage.label(m[::2, ::2, ::2])
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    keep = lab == (1 + int(np.argmax(sizes)))
    keep = ndimage.binary_fill_holes(keep)
    small = sitk.GetImageFromArray(keep.astype(np.uint8))
    small.SetSpacing(tuple(s * 2 for s in img.GetSpacing())); small.SetOrigin(img.GetOrigin()); small.SetDirection(img.GetDirection())
    return mask_mesh(keep, small, smooth=5, target_faces=120000)


def rigid_icp(src, dst_tree, dst_pts, iters=40, trim=85):
    """Rigid (no scale) ICP of point set src onto a target; returns R, t."""
    R, t = np.eye(3), dst_pts.mean(0) - src.mean(0)
    for _ in range(iters):
        X = src @ R.T + t
        d, j = dst_tree.query(X)
        ok = d < np.percentile(d, trim)
        A, B = X[ok], dst_pts[j[ok]]
        _, R2, _ = ml.umeyama(A, B)                   # rotation only; rigid translation below
        t2 = B.mean(0) - R2 @ A.mean(0)
        R, t = R2 @ R, R2 @ t + t2
    return R, t


def main():
    import trimesh
    from scipy.spatial import cKDTree
    _, hra, _ = ml.read_glb(ROOT / 'work/sources/hra/3d-vh-f-united.glb')
    H = {p['name']: p for p in hra}
    skin = H['VH_F_skin']['pos']
    shift = np.array([0.0, -skin[:, 1].min(), -(skin[:, 2].min() + skin[:, 2].max()) / 2])   # same frame as the build
    skin = skin + shift
    tree = cKDTree(skin)
    out = {'frame_shift_m': shift.tolist(), 'volumes': {}}
    (WORK / 'targets').mkdir(parents=True, exist_ok=True)
    # The VHF cadaver was CT-scanned frozen inside a gelatin block, so the CT "body outline" is the
    # block, not the skin. Registration is therefore done on BONE, which HRA and the CT share:
    #   head->femur: TotalSegmentator hips + sacrum + femurs  vs  HRA ilium/ischium/pubis + sacrum + femurs
    #   femur->toes: CT bone (HU > 250)                        vs  HRA femurs, patellae, tibiae, fibulae
    from totalsegmentator.map_to_binary import class_map
    labels = class_map['total']
    hra_bone = lambda pat: np.vstack([p['pos'] + shift for n, p in H.items() if __import__('re').search(pat, n)])
    targets = {'head_to_femur': hra_bone(r'^VH_F_(ilium|ischium|pubis)_compact_bone_[LR]$|^VH_F_sacrum$|^VH_F_femur_[LR]$'),
               'femur_to_toes': hra_bone(r'^VH_F_(femur|patella|tibia|fibula)_[LR]$')}
    for name in ('head_to_femur', 'femur_to_toes'):
        img = sitk.ReadImage(str(WORK / f'ct_{name}.nii.gz'))
        seg_path = WORK / f'seg_{name}.nii'
        seg = sitk.ReadImage(str(seg_path))
        arr = sitk.GetArrayFromImage(seg)
        if name == 'head_to_femur':
            ids = [k for k, l in labels.items() if l in ('hip_left', 'hip_right', 'sacrum', 'femur_left', 'femur_right')]
            zyx = np.argwhere(np.isin(arr, ids))
        else:
            ct = sitk.GetArrayFromImage(img)
            zyx = np.argwhere(ct > 250)
        zyx = zyx[:: max(1, len(zyx) // 60000)]
        sp, org = np.array(seg.GetSpacing()), np.array(seg.GetOrigin())
        pts = lps_to_atlas(zyx[:, ::-1] * sp + org)
        T = targets[name]
        ttree = cKDTree(T)
        # Initial guess: try both vertical orientations (the series may be stored feet-first) and
        # several heights; keep the best ICP.
        best = None
        for flip in (False, True):
            P = pts.copy()
            if flip:
                P[:, 1] *= -1; P[:, 0] *= -1
            for dy in np.linspace(-0.3, 0.3, 7):
                t0 = T.mean(0) - P.mean(0) + [0, dy, 0]
                R, t = rigid_icp(P + t0, ttree, T, iters=30)
                X = (P + t0) @ R.T + t
                d, _ = ttree.query(X)
                score = np.percentile(d, 50)
                if best is None or score < best[0]:
                    F = np.diag([-1.0, -1.0, 1.0]) if flip else np.eye(3)
                    best = (score, R @ F, R @ t0 + t, d)
        score, R, t, d = best
        out['volumes'][name] = {'R': R.tolist(), 't': t.tolist(), 'bone_to_hra_bone_mm_median': float(score * 1000),
                                'bone_to_hra_bone_mm_p90': float(np.percentile(d, 90) * 1000)}
        print(name, json.dumps(out['volumes'][name]), flush=True)
        for k, lab in labels.items():
            mask = arr == k
            if mask.sum() < 200:
                continue
            m = mask_mesh(mask, seg, smooth=10, target_faces=20000)
            if m is None:
                continue
            V = lps_to_atlas(m.vertices) @ R.T + t
            dst = WORK / 'targets' / f'{lab}__{name}.npz'
            np.savez_compressed(dst, v=V, f=np.asarray(m.faces), voxels=int(mask.sum()),
                                voxel_mm3=float(np.prod(seg.GetSpacing())))
        print(name, 'labels meshed', flush=True)
    (WORK / 'registration.json').write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
