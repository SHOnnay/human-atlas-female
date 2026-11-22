"""Step 4: register BodyParts3D male structures onto the real VHF shapes.

    python scripts/female/vhf_register.py      -> work/vhf/registered.pkl, work/vhf/register_report.json

Targets (all in the HRA VHF frame, feet at y = 0):
  * TotalSegmentator "total" meshes of the VHF CT (work/vhf/targets, from vhf_targets.py);
  * the HRA VHF femurs, patellae, tibiae, fibulae (scan-derived, same donor).

Per structure (single):  similarity ICP, then smooth non-rigid ICP (body_target.fit_to_surface)
                         -> BodyParts3D topology/IDs with the real VHF shape.
Per group (skull, heart, liver, brain): ONE similarity for all its parts (rigid units / many small
                         parts) fitted on the group's union surface.
Gate per structure:      mean surface distance <= 2 mm and 95th-percentile symmetric Hausdorff
                         <= 5 mm to the VHF surface. A structure that fails is flagged; the build
                         then shows the VHF mesh itself (scan-derived) for it.
"""
import json
import pickle
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import body_target as bt  # noqa: E402
import meshlib as ml  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / 'work' / 'vhf' / 'targets'
ORD = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth', 'eleventh', 'twelfth']


def single_map():
    m = {}
    for i, w in enumerate(ORD[:12]):
        for side, sw in (('left', 'Left'), ('right', 'Right')):
            m[f'{sw} {w} rib'] = [f'rib_{side}_{i + 1}']
    for i, w in enumerate(ORD[:12]):
        m[f'{w.capitalize()} thoracic vertebra'] = [f'vertebrae_T{i + 1}']
    for i, w in enumerate(ORD[:5]):
        m[f'{w.capitalize()} lumbar vertebra'] = [f'vertebrae_L{i + 1}']
    for i, w in enumerate(ORD[:7]):
        m[f'{w.capitalize()} cervical vertebra'] = [f'vertebrae_C{i + 1}']
    m['Atlas'] = ['vertebrae_C1']; m['Axis'] = ['vertebrae_C2']
    for sw, s in (('Left', 'left'), ('Right', 'right')):
        m.update({f'{sw} clavicle': [f'clavicula_{s}'], f'{sw} scapula': [f'scapula_{s}'], f'{sw} humerus': [f'humerus_{s}'],
                  f'{sw} kidney': [f'kidney_{s}'], f'{sw} gluteus maximus': [f'gluteus_maximus_{s}'],
                  f'{sw} gluteus medius': [f'gluteus_medius_{s}'], f'{sw} gluteus minimus': [f'gluteus_minimus_{s}']})
    m.update({'Spleen': ['spleen'], 'Stomach': ['stomach'], 'Pancreas': ['pancreas'], 'Esophagus': ['esophagus'],
              'Trachea': ['trachea'], 'Gallbladder': ['gallbladder'], 'Inferior vena cava': ['inferior_vena_cava'],
              'Superior vena cava': ['superior_vena_cava']})
    return m


GROUPS = {   # group name -> (BodyParts3D name regex, target labels)
    'skull': (r'^(frontal|occipital|sphenoid|ethmoid|vomer|mandible|maxilla|left|right) ?(bone|parietal bone|temporal bone|zygomatic bone|nasal bone|lacrimal bone|palatine bone|inferior nasal concha|maxilla)?$|^Mandible$|^Frontal bone$|^Occipital bone$|^Sphenoid bone$|^Ethmoid$|^Vomer$|parietal bone$|temporal bone$|zygomatic bone$|nasal bone$|lacrimal bone$|palatine bone$|nasal concha$|^(Left|Right) maxilla$', ['skull']),
    'sternum': (r'^(Manubrium|Body of sternum|Xiphoid process)$', ['sternum']),
    'costal_cartilages': (r'costal cartilage$', ['costal_cartilages']),
    'aorta': (r'^(Ascending aorta|Arch of aorta|Descending thoracic aorta|Abdominal aorta|Descending aorta)$', ['aorta']),
    'iliopsoas_left': (r'^Left (psoas major|iliacus)$', ['iliopsoas_left']),
    'iliopsoas_right': (r'^Right (psoas major|iliacus)$', ['iliopsoas_right']),
}
SIM_GROUPS = {'heart': (r'(ventricle|atrium|auricle|heart|cardiac|myocardium|mitral|tricuspid|aortic valve|pulmonary valve)', ['heart']),
              'liver': (r'liver', ['liver']), 'brain': (r'(gyrus|lobe of cerebrum|cerebell|midbrain|pons|medulla oblongata|brain|thalamus|ventricle of brain)', ['brain'])}
HRA_BONES = {f'{sw} {b}': f'VH_F_{b}_{s}' for sw, s in (('Left', 'L'), ('Right', 'R')) for b in ('femur', 'patella', 'tibia', 'fibula')}


def load_target(labels):
    import trimesh
    ms = []
    for l in labels:
        f = T / f'{l}__head_to_femur.npz'
        if f.exists():
            d = np.load(f)
            ms.append(trimesh.Trimesh(d['v'], d['f'], process=False))
    return trimesh.util.concatenate(ms) if ms else None


def surf_metrics(P, faces, target):
    import trimesh
    from scipy.spatial import cKDTree
    _, d1, _ = trimesh.proximity.closest_point(target, P[:: max(1, len(P) // 4000)])
    Q = np.asarray(target.vertices)[:: max(1, len(target.vertices) // 4000)]
    d2, _ = cKDTree(P).query(Q)
    return float(d1.mean() * 1000), float(np.percentile(np.r_[d1, d2], 95) * 1000)


def symmetric_fit(P, neighbors, target, iters=60, smooth=5, sim_iters=25):
    """Similarity ICP, then SYMMETRIC smooth non-rigid ICP: each model vertex is pulled to its
    closest target point AND each target point pulls its closest model vertex, so the registered
    BodyParts3D mesh covers the whole VHF surface (not only the part nearest to it). Displacements
    are averaged over the mesh neighbourhood `smooth` times per step (keeps the surface detail)."""
    from scipy.spatial import cKDTree
    Tv = np.asarray(target.vertices)
    Tv = Tv[:: max(1, len(Tv) // 20000)]
    ttree = cKDTree(Tv)
    X = P + (Tv.mean(0) - P.mean(0))
    for _ in range(sim_iters):
        d, j = ttree.query(X)
        ok = d < np.percentile(d, 90)
        s, R, t = ml.umeyama(X[ok], Tv[j[ok]])
        X = ml.apply_similarity(X, s, R, t)
    nb = [np.asarray(n) for n in neighbors]
    deg = np.array([len(n) for n in nb]); fl = np.concatenate(nb); own = np.repeat(np.arange(len(nb)), deg)

    def avg(D):
        acc = np.zeros_like(D); np.add.at(acc, own, D[fl])
        return (D + acc) / (1 + deg)[:, None]
    for it in range(iters):
        d, j = ttree.query(X)
        D = Tv[j] - X
        W = np.ones((len(X), 1))
        # reverse term: target point -> nearest model vertex
        d2, i2 = cKDTree(X).query(Tv)
        acc = np.zeros_like(X); cnt = np.zeros(len(X))
        np.add.at(acc, i2, Tv - X[i2]); np.add.at(cnt, i2, 1)
        D = D + acc
        W = W + cnt[:, None]
        for _ in range(smooth):
            D, W = avg(D), avg(W)
        X = X + 0.5 * D / np.maximum(W, 1e-9)
    return X


def register_single(P, idx, target, nonrigid=True):
    import trimesh
    m = trimesh.Trimesh(P, idx.reshape(-1, 3), process=False)
    return symmetric_fit(P, m.vertex_neighbors, target)


def main():
    import trimesh
    atlas, male = ml.load_package(ROOT / 'public/models/atlas.json')
    _, hra, _ = ml.read_glb(ROOT / 'work/sources/hra/3d-vh-f-united.glb')
    H = {p['name']: p for p in hra}
    reg = json.loads((ROOT / 'work/vhf/registration.json').read_text())
    shift = np.array(reg['frame_shift_m'])
    by = {}
    for p in atlas['parts']:
        by.setdefault(p['name'], []).append(p['id'])
    out, rep = {}, {}
    # 1. singles
    for name, labels in {**single_map(), **{k: None for k in HRA_BONES}}.items():
        if name not in by:
            continue
        if labels is None:
            hp = H[HRA_BONES[name]]
            tgt = trimesh.Trimesh(hp['pos'] + shift, hp['idx'].reshape(-1, 3), process=True)
            src_name = 'HRA ' + HRA_BONES[name]
        else:
            tgt = load_target(labels)
            src_name = 'CT ' + '+'.join(labels)
        if tgt is None:
            rep[name] = {'status': 'no target'}; continue
        for pid in by[name]:
            P, idx = male[pid]['pos'], male[pid]['idx']
            X = register_single(P, idx, tgt)
            mean, h95 = surf_metrics(X, idx, tgt)
            ratio = np.ptp(X, 0).max() / max(np.ptp(P, 0).max(), 1e-6)
            ok = mean <= 2.0 and h95 <= 5.0 and 0.6 <= ratio <= 1.6     # also: never stretched across a neighbour
            out[pid] = {'pos': X, 'gate': ok}
            rep[name] = {'target': src_name, 'mean_mm': mean, 'hausdorff95_mm': h95, 'pass': ok}
        print(f"{name:36s} {rep[name].get('mean_mm', 0):6.2f} {rep[name].get('hausdorff95_mm', 0):6.2f} {'PASS' if rep[name].get('pass') else 'FAIL'}", flush=True)
    # 2. groups registered as one surface (non-rigid on the union, per-part results)
    for g, (pat, labels) in {**GROUPS}.items():
        tgt = load_target(labels)
        pids = [pid for n, ids in by.items() if re.search(pat, n, re.I) for pid in ids]
        if tgt is None or not pids:
            continue
        P = np.vstack([male[p]['pos'] for p in pids])
        off = np.cumsum([0] + [len(male[p]['pos']) for p in pids])
        I = np.concatenate([male[p]['idx'] + off[k] for k, p in enumerate(pids)])
        rigid_unit = g in ('skull', 'sternum')
        if rigid_unit:
            # rigid units: similarity only (never deform a skull non-uniformly)
            from scipy.spatial import cKDTree
            tree = cKDTree(tgt.vertices); X = P + (np.asarray(tgt.vertices).mean(0) - P.mean(0))
            for _ in range(30):
                d, j = tree.query(X); ok = d < np.percentile(d, 85)
                s, R, t = ml.umeyama(X[ok], np.asarray(tgt.vertices)[j[ok]]); X = ml.apply_similarity(X, s, R, t)
        else:
            X = register_single(P, I, tgt)
        mean, h95 = surf_metrics(X, I, tgt)
        ok = mean <= 2.0 and h95 <= 5.0
        for k, p in enumerate(pids):
            out[p] = {'pos': X[off[k]:off[k + 1]], 'gate': ok, 'group': g}
        rep['group:' + g] = {'parts': len(pids), 'mean_mm': mean, 'hausdorff95_mm': h95, 'pass': ok, 'rigid_unit': rigid_unit}
        print(f"group {g:30s} {mean:6.2f} {h95:6.2f} {'PASS' if ok else 'FAIL'} ({len(pids)} parts)", flush=True)
    # 3. similarity groups (heart, liver, brain): one similarity to the VHF organ
    from scipy.spatial import cKDTree
    for g, (pat, labels) in SIM_GROUPS.items():
        tgt = load_target(labels)
        sysof = {q['id']: q['system'] for q in atlas['parts']}
        pids = [i for n, ids in by.items() if re.search(pat, n, re.I) for i in ids
                if i not in out and (g == 'brain' or sysof[i] not in ('arterial', 'venous', 'nervous'))]
        if tgt is None or not pids:
            continue
        P = np.vstack([male[p]['pos'] for p in pids])
        tree = cKDTree(tgt.vertices); X = P + (np.asarray(tgt.vertices).mean(0) - P.mean(0))
        for _ in range(30):
            d, j = tree.query(X); ok = d < np.percentile(d, 85)
            s, R, t = ml.umeyama(X[ok], np.asarray(tgt.vertices)[j[ok]]); X = ml.apply_similarity(X, s, R, t)
        s, R, t = ml.umeyama(P, X)
        for p in pids:
            out[p] = {'pos': ml.apply_similarity(male[p]['pos'], s, R, t), 'gate': None, 'group': g}
        rep['simgroup:' + g] = {'parts': len(pids), 'scale': float(s)}
        print('simgroup', g, len(pids), 'scale', round(float(s), 3), flush=True)
    (ROOT / 'work/vhf/registered.pkl').write_bytes(pickle.dumps(out))
    summary = {'structures': len([k for k in rep if not k.startswith(('group', 'simgroup'))]),
               'pass': sum(1 for v in rep.values() if v.get('pass')), 'fail': sum(1 for v in rep.values() if v.get('pass') is False)}
    (ROOT / 'work/vhf/register_report.json').write_text(json.dumps({'summary': summary, 'items': rep}, indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o)))
    print('summary', summary)


if __name__ == '__main__':
    main()
