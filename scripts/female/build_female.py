"""Build the female Human Atlas package (public/models/female/) from shared BodyParts3D
structures, HRA female reference organs and generated schematic structures.

    python scripts/female/build_female.py --hra work/sources/hra/3d-vh-f-united.glb --blender PATH/TO/blender
    node scripts/optimize-anatomy.mjs female/atlas.json
    node scripts/compress-models.mjs

(`python scripts/build-anatomy.py --sex female` runs all three.) Every step is deterministic.
Inputs: the male package in public/models (BodyParts3D 4.0, already simplified), the HRA
united-female v1.5 GLB, scripts/female/config.json and scripts/female/ontology_xrefs.json.
Outputs: public/models/female/atlas.json plus unsimplified source chunks, and the build report
work/female/report.json (landmarks, scale factors, collision checks).
"""
import argparse
import json
import re
import subprocess
import tempfile
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import meshlib as ml  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
WORK = ROOT / 'work' / 'female'
OUT = ROOT / 'public' / 'models' / 'female'

SOURCES = {
    'bp3d': {'name': 'BodyParts3D 4.0', 'author': 'Database Center for Life Science (DBCLS)', 'license': 'CC BY 4.0',
             'url': 'https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html'},
    'hra': {'name': 'HRA 3D Reference Organ Set for Female v1.5', 'author': 'Kristen Browne, Heidi Schlehlein; Human Reference Atlas / HuBMAP',
            'license': 'CC BY 4.0', 'url': 'https://doi.org/10.48539/HBM352.BTSQ.586'},
    'generated': {'name': 'Generated for Human Atlas (schematic)', 'author': 'Human Atlas contributors', 'license': 'CC BY 4.0',
                  'url': 'https://github.com/ashemag/human-atlas/blob/main/DATA_SOURCES.md'},
}
ACCURACY_NOTES = {
    'source': 'Source geometry; uniformly scaled and/or rigidly placed.',
    'warped': 'Source geometry smoothly warped to fit the female pelvis or neighbouring female structures.',
    'schematic': 'Approximate / schematic, not scan-derived. Built from reference dimensions in anatomy texts.',
}


def log(*a):
    print(*a, flush=True)


# ============================================================== stage 1: shared male structures

def load_inputs(args, cfg):
    atlas, male = ml.load_package(ROOT / 'public' / 'models' / 'atlas.json')
    doc, hra_parts, _ = ml.read_glb(args.hra)
    names = {i: n.get('name', '') for i, n in enumerate(doc['nodes'])}
    for p in hra_parts:
        p['ancestor_names'] = [names[a] for a in p['ancestors']]
    hra = {p['name']: p for p in hra_parts}
    return atlas, male, doc, hra


def classify_male(atlas, cfg):
    pat = re.compile('|'.join(cfg['male_only_patterns']), re.I)
    removed = {}
    for p in atlas['parts']:
        if p['id'] in cfg['male_only']:
            removed[p['id']] = 'male-only: ' + cfg['male_only'][p['id']]
        elif pat.search(p['name']):
            removed[p['id']] = 'male-only (name match): ' + p['name']
        elif p['id'] in cfg['replaced']:
            removed[p['id']] = 'replaced: ' + cfg['replaced'][p['id']]['reason']
    return removed


# ============================================================== stage 2: pelvis morph

def morph_targets(lm, spec):
    t = {k: v.copy() for k, v in lm.items()}
    for key, v in lm.items():
        base = re.sub(r'_[LR]$', '', key)
        if base in spec['x_scale']:
            t[key][0] = v[0] * spec['x_scale'][base]
    for side in 'LR':
        h = lm['symphysis_top_' + side][1] - lm['symphysis_bottom_' + side][1]
        t['symphysis_bottom_' + side][1] += h * spec['symphysis_shortening']
        t['iliac_crest_' + side][1] -= (lm['iliac_crest_' + side][1] - lm['acetabulum_' + side][1]) * spec['crest_lowering']
    t['sacral_apex'] = lm['sacral_apex'] + (lm['sacral_base'] - lm['sacral_apex']) * spec['sacral_shortening']
    return t


def morph_pelvis(M, atlas, cfg, report):
    pb = cfg['pelvis_bones']
    head_l, r_l = ml.femoral_head_centre(M[pb['femur_L']]['pos'])
    head_r, r_r = ml.femoral_head_centre(M[pb['femur_R']]['pos'])
    lm = ml.pelvis_landmarks(M[pb['hip_L']]['pos'], M[pb['hip_R']]['pos'], M[pb['sacrum']]['pos'], head_l, head_r)
    target = morph_targets(lm, cfg['pelvis_morph'])
    male_hips = (M[pb['hip_L']]['pos'].copy(), M[pb['hip_R']]['pos'].copy())
    keys = sorted(lm)
    src = np.array([lm[k] for k in keys]); dst = np.array([target[k] for k in keys])
    # Identity anchors keep the warp local: lumbar spine above, femoral shafts below, a ring around.
    rng = np.random.default_rng(7)
    anchors = []
    for pid in ('FJ3162', 'FJ3165', pb['femur_L'], pb['femur_R']):
        pos = M[pid]['pos']
        if pid.startswith('FJ316'):
            sel = pos
        else:
            sel = pos[pos[:, 1] < head_l[1] - 0.12]
        anchors.append(sel[rng.choice(len(sel), min(24, len(sel)), replace=False)])
    centre = (src.min(0) + src.max(0)) / 2
    for y in (centre[1] - 0.2, centre[1] + 0.22):
        for a in np.linspace(0, 2 * np.pi, 12, endpoint=False):
            anchors.append(np.array([[centre[0] + 0.32 * np.cos(a), y, centre[2] + 0.25 * np.sin(a)]]))
    anchors = np.vstack(anchors)
    warp = ml.tps_warp(src, dst, anchors)
    lo = np.min([M[pb[k]]['pos'].min(0) for k in ('hip_L', 'hip_R', 'sacrum')], axis=0)
    hi = np.max([M[pb[k]]['pos'].max(0) for k in ('hip_L', 'hip_R', 'sacrum')], axis=0)
    rigid = re.compile('|'.join(cfg['rigid_patterns']), re.I)
    warped, maxdisp = [], 0.0
    bone_ids = {pb['hip_L'], pb['hip_R'], pb['sacrum']}
    for p in atlas['parts']:
        m = M.get(p['id'])
        if m is None:
            continue
        if p['id'] not in bone_ids and (p['system'] == 'skeletal' and rigid.search(p['name'])):
            continue
        pos = m['pos']
        w = np.ones(len(pos)) if p['id'] in bone_ids else ml.box_falloff(pos, lo, hi, 0.10)
        if w.max() < 1e-4:
            continue
        sel = w > 1e-4
        disp = np.zeros_like(pos)
        disp[sel] = warp(pos[sel]) * w[sel, None]
        d = np.linalg.norm(disp, axis=1).max()
        if d < 2e-4:
            continue
        m['pos'] = pos + disp
        m['warped'] = True
        warped.append(p['id']); maxdisp = max(maxdisp, d)
    after = ml.pelvis_landmarks(M[pb['hip_L']]['pos'], M[pb['hip_R']]['pos'], M[pb['sacrum']]['pos'], head_l, head_r)
    report['pelvis'] = {
        'femoral_head_radius_mm': [r_l * 1000, r_r * 1000],
        'male_measures_mm': ml.pelvis_measures(lm, *male_hips),
        'morphed_measures_mm': ml.pelvis_measures(after, M[pb['hip_L']]['pos'], M[pb['hip_R']]['pos']),
        'landmark_fit_error_mm': {k: float(np.linalg.norm(after[k] - target[k]) * 1000) for k in keys},
        'warped_parts': len(warped), 'max_soft_tissue_displacement_mm': maxdisp * 1000,
    }
    return after


# ============================================================== stage 3: HRA female organs

def hra_selected(hra):
    """name → (system, group) for HRA structures used in the female atlas."""
    out = {}
    for name, p in hra.items():
        anc = p['ancestor_names']
        if 'VH_F_reproductive_system' in anc and 'VH_F_placenta' not in anc and name != 'VH_F_placenta':
            out[name] = ('reproductive', 'pelvic')
        elif 'VH_F_urinary_bladder' in anc:
            out[name] = ('urinary', 'pelvic')
        elif 'VH_F_blood_vasculature_of_uterus' in anc:
            out[name] = ('venous' if 'vein' in name else 'arterial', 'pelvic')
        elif name == 'VH_F_coccyx':
            out[name] = ('skeletal', 'coccyx')
        elif 'VH_F_mammary_gland' in anc:
            if any(k in name for k in ('nipple', 'areola')):
                system = 'integumentary'
            elif 'suspensory' in name:
                system = 'connective'
            elif 'fat' in name:
                system = 'integumentary'
            else:
                system = 'reproductive'
            out[name] = (system, 'breast_' + ('L' if name.endswith('_L') else 'R'))
    return out


def register_hra(hra, M, male_lm, cfg, report):
    pb = cfg['pelvis_bones']
    cat = lambda names: np.vstack([hra[n]['pos'] for n in names])
    hl, _ = ml.femoral_head_centre(hra['VH_F_femur_L']['pos'])
    hr, _ = ml.femoral_head_centre(hra['VH_F_femur_R']['pos'])
    hip_f = (cat(['VH_F_ilium_compact_bone_L', 'VH_F_ischium_compact_bone_L', 'VH_F_pubis_compact_bone_L']),
             cat(['VH_F_ilium_compact_bone_R', 'VH_F_ischium_compact_bone_R', 'VH_F_pubis_compact_bone_R']))
    lm_f = ml.pelvis_landmarks(hip_f[0], hip_f[1], hra['VH_F_sacrum']['pos'], hl, hr)
    keys = sorted(lm_f)
    inner = ('inlet_lateral', 'symphysis', 'sacral_promontory', 'sacral_base', 'sacral_apex', 'ischial', 'ramus')
    w = [2.0 if any(k.startswith(i) for i in inner) else 1.0 for k in keys]
    s, R, t = ml.umeyama([lm_f[k] for k in keys], [male_lm[k] for k in keys], w)
    res = {k: float(np.linalg.norm(ml.apply_similarity(lm_f[k][None], s, R, t)[0] - male_lm[k]) * 1000) for k in keys}
    report['hra_pelvic_registration'] = {'scale': s, 'rotation_deg': float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))),
                                         'translation_m': t.tolist(), 'landmark_residual_mm': res,
                                         'hra_female_measures_mm_native': ml.pelvis_measures(lm_f, *hip_f)}
    pelvic = (s, R, t)
    # Coccyx: same rotation/scale, translated so HRA's sacral apex lands on the morphed sacral apex.
    apex = ml.apply_similarity(lm_f['sacral_apex'][None], s, R, t)[0]
    coccyx = (s, R, t + (male_lm['sacral_apex'] - apex))
    # Breasts keep their native size: statures are matched, so HRA height above the floor maps
    # directly. Lateral position is scaled by thoracic width (BodyParts3D ribs vs HRA lungs + ribs).
    floor = -hra['VH_F_skin']['pos'][:, 1].min()
    nipple_y = hra['VH_F_nipple_L']['pos'][:, 1].mean() + floor
    ribs = np.vstack([M[i]['pos'] for i in M if re.search(r' rib$', M[i]['name']) and M[i]['system'] == 'skeletal'])
    band = ribs[np.abs(ribs[:, 1] - nipple_y) < 0.02]
    lung_f = np.vstack([p['pos'] for p in hra.values() if 'VH_F_lungs' in p['ancestor_names']])
    lung_band = lung_f[np.abs(lung_f[:, 1] + floor - nipple_y) < 0.02]
    rib_thickness = 0.012  # lung surface lies on the inner rib surface; see DECISIONS.md
    kx = np.ptp(band[:, 0]) / (np.ptp(lung_band[:, 0]) + 2 * rib_thickness)
    report['hra_breast_registration'] = {'scale': 1.0, 'floor_offset_m': float(floor), 'nipple_height_m': float(nipple_y),
                                         'lateral_ratio': float(kx), 'ribcage_width_mm': float(np.ptp(band[:, 0]) * 1000),
                                         'hra_lung_width_mm': float(np.ptp(lung_band[:, 0]) * 1000)}
    breast = (1.0, np.eye(3), np.array([0.0, floor, 0.0]), kx)
    return {'pelvic': pelvic, 'coccyx': coccyx, 'breast': breast}, lm_f


def place_hra(hra, selected, transforms):
    out = {}
    centroids = {}
    for side in 'LR':
        pts = np.vstack([hra[n]['pos'] for n, (_, g) in selected.items() if g == 'breast_' + side])
        centroids[side] = pts.mean(0)
    for name, (system, group) in selected.items():
        p = hra[name]
        pos, nrm, idx = ml.weld(p['pos'], p['nrm'], p['idx'])
        key = 'breast' if group.startswith('breast') else group
        s, R, t = transforms[key][:3]
        pos = ml.apply_similarity(pos, s, R, t)
        if key == 'breast':
            pos[:, 0] += centroids[group[-1]][0] * (transforms['breast'][3] - 1)
        nrm = (R @ nrm.T).T
        out[name] = {'pos': pos, 'nrm': nrm, 'idx': idx, 'system': system, 'group': group, 'hra': p}
    return out


def fit_breasts_to_chest(F, M, report):
    """Translate each breast forward/back so its deep surface rests 1.5 mm in front of the chest wall."""
    chest_ids = [i for i in M if re.search(r'pectoralis major|serratus anterior|^(right|left) [0-9a-z]+ rib|rib$', M[i]['name'], re.I)]
    chest = np.vstack([M[i]['pos'] for i in chest_ids])
    from scipy.spatial import cKDTree
    out = {}
    for side in 'LR':
        names = [n for n, f in F.items() if f['group'] == 'breast_' + side]
        pts = np.vstack([F[n]['pos'] for n in names])
        # For each chest point inside the breast footprint, compare with the breast's deepest point.
        lo, hi = pts.min(0), pts.max(0)
        foot = chest[(chest[:, 0] > lo[0]) & (chest[:, 0] < hi[0]) & (chest[:, 1] > lo[1]) & (chest[:, 1] < hi[1])]
        tree = cKDTree(pts[:, :2])
        # Required shift: the breast's deepest point above each chest point must clear it.
        gaps = [pts[js, 2].min() - c[2] for c, js in zip(foot, tree.query_ball_point(foot[:, :2], 0.006)) if js]
        gap = min(gaps) if gaps else 0.0
        dz = 0.0015 - gap
        for n in names:
            F[n]['pos'][:, 2] += dz
        out[side] = {'dz_mm': float(dz * 1000), 'chest_parts': len(chest_ids)}
    report['breast_chest_fit'] = out


# ============================================================== collisions

def overlaps(a_lo, a_hi, b_lo, b_hi, pad=0.0):
    return bool(np.all(a_lo - pad <= b_hi) and np.all(b_lo - pad <= a_hi))


def survey(movers, fixed, label):
    """Triangle-intersection survey: movers {name: (pos, idx)} vs fixed {name: (pos, idx)}."""
    hits = []
    fixed_mesh = {}
    for fn, (fp, fi) in fixed.items():
        fixed_mesh[fn] = (fp.min(0), fp.max(0), fp, fi)
    for mn, (mp, mi) in movers.items():
        lo, hi = mp.min(0), mp.max(0)
        a = None
        for fn, (flo, fhi, fp, fi) in fixed_mesh.items():
            if fn == mn or not overlaps(lo, hi, flo, fhi):
                continue
            a = a or ml.to_trimesh(mp, mi)
            if ml.collides(a, ml.to_trimesh(fp, fi)):
                hits.append((mn, fn))
    log(f'[{label}] {len(hits)} intersecting pairs')
    return hits


HRA_SOFT = re.compile(r'ligament|mesosalpinx|mesovarium|uterine_(artery|vein)|uterovesical|fat_[LR]')
LEVATOR = re.compile(r'pubococcygeus|puborectalis|iliococcygeus|coccygeus|sphincter|perineal|levator', re.I)


def union_mesh(items):
    import trimesh
    meshes = [ml.to_trimesh(p, i) for p, i in items]
    return trimesh.util.concatenate(meshes)


def inside_count(points, bones):
    """Vertices of `points` lying inside any bone (2 mm filled voxel grids, see fit_pelvic_block)."""
    total = 0
    for grid in bones:
        total += int(grid.is_filled(points).sum())
    return total


def fit_pelvic_block(F, M, cfg, report):
    """Small rigid translation of the HRA pelvic organs that minimises their overlap with bone."""
    pb = cfg['pelvis_bones']
    meshes = [ml.to_trimesh(M[pb[k]]['pos'], M[pb[k]]['idx']) for k in ('hip_L', 'hip_R', 'sacrum')]
    bones = [m.voxelized(pitch=0.002).fill() for m in meshes]
    solid = [n for n, f in F.items() if f['group'] == 'pelvic' and not HRA_SOFT.search(n)]
    pts = np.vstack([F[n]['pos'] for n in solid])
    pts = pts[np.random.default_rng(1).choice(len(pts), min(6000, len(pts)), replace=False)]
    best = (inside_count(pts, bones), 0.0, 0.0)
    start = best[0]
    # Coarse-to-fine search over vertical/anteroposterior shifts (±20 mm); ties prefer small shifts.
    for step, span in ((0.005, 0.02), (0.00125, 0.005)):
        cy, cz = best[1], best[2]
        for dy in np.arange(cy - span, cy + span + 1e-9, step):
            for dz in np.arange(cz - span, cz + span + 1e-9, step):
                score = inside_count(pts + [0, dy, dz], bones)
                if (score, abs(dy) + abs(dz)) < (best[0], abs(best[1]) + abs(best[2])):
                    best = (score, dy, dz)
    for n, f in F.items():
        if f['group'] == 'pelvic':
            f['pos'] = f['pos'] + [0, best[1], best[2]]
    report['pelvic_block_fit'] = {'inside_bone_vertices_before': start, 'after': best[0], 'shift_mm': [0, best[1] * 1000, best[2] * 1000],
                                  'sampled_vertices': len(pts), 'bone_watertight': [bool(m.is_watertight) for m in meshes]}
    log('pelvic block fit', report['pelvic_block_fit'])


def orient_coccyx(F, M, cfg, report):
    """Align the HRA coccyx with the end of the morphed sacrum and attach its base to the apex."""
    sac = M[cfg['pelvis_bones']['sacrum']]['pos']
    mid = sac[np.abs(sac[:, 0]) < 0.012]
    apex = mid[np.argmin(mid[:, 1])]
    upper = mid[(mid[:, 1] > apex[1] + 0.015) & (mid[:, 1] < apex[1] + 0.03)].mean(0)
    sacral_dir = (apex - upper) / np.linalg.norm(apex - upper)
    c = F['VH_F_coccyx']
    top = c['pos'][c['pos'][:, 1] > c['pos'][:, 1].max() - 0.004].mean(0)
    tip = c['pos'][np.argmin(c['pos'][:, 1])]
    coc_dir = (tip - top) / np.linalg.norm(tip - top)
    # The coccyx continues the sacral curve, angled ~15° further anteriorly (rotation about x).
    ang = np.radians(15)
    curve = np.array([[1, 0, 0], [0, np.cos(ang), -np.sin(ang)], [0, np.sin(ang), np.cos(ang)]])
    target = curve @ sacral_dir
    if target[2] < sacral_dir[2]:
        curve = curve.T; target = curve @ sacral_dir
    v = np.cross(coc_dir, target); s = np.linalg.norm(v); cth = coc_dir @ target
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    R = np.eye(3) + vx + vx @ vx * ((1 - cth) / max(s * s, 1e-12))
    c['pos'] = (R @ (c['pos'] - top).T).T + apex + sacral_dir * 0.002
    c['nrm'] = (R @ c['nrm'].T).T
    report['coccyx'] = {'rotation_deg': float(np.degrees(np.arccos(np.clip(cth, -1, 1)))), 'apex': apex.tolist()}


def connect_ureters(F, M, report):
    """Bend the distal ureters so they end at the HRA bladder's ureteral orifices."""
    out = {}
    for side, uid in (('L', 'FJ3144'), ('R', 'FJ3146')):
        if uid not in M:
            continue
        u = M[uid]['pos']
        end = u[np.argmin(u[:, 1])]
        orifice = F['VH_F_ureteral_orifice_' + side]['pos'].mean(0)
        # Ureters enter the bladder obliquely from posterolateral; aim 6 mm outside the orifice.
        bladder = F['VH_F_fundus_of_urinary_bladder_base']['pos']
        outward = orifice - bladder.mean(0); outward[1] = 0; outward /= np.linalg.norm(outward)
        goal = orifice + outward * 0.006
        delta = goal - end
        w = 1 - ml.smoothstep(0, 0.07, u[:, 1] - end[1])
        M[uid]['pos'] = u + w[:, None] * delta
        M[uid]['warped'] = True
        out[side] = {'gap_before_mm': float(np.linalg.norm(delta) * 1000)}
    report['ureter_connection'] = out


def away(pos, centre, radius=0.06):
    """Direction from `centre` to the part of `pos` lying within `radius` of it."""
    near_pts = pos[np.linalg.norm(pos - centre, axis=1) < radius]
    d = (near_pts.mean(0) if len(near_pts) else pos.mean(0)) - centre
    return d if np.linalg.norm(d) > 1e-6 else np.array([0, 1.0, 0])


def resolve_collisions(F, M, cfg, report):
    """Deform soft structures out of the structures they must not cross. See DECISIONS.md."""
    cfg_ids = cfg['pelvis_bones']
    stats = {}
    pelvic_lo = np.min([f['pos'].min(0) for f in F.values() if f['group'] in ('pelvic', 'coccyx')], axis=0) - 0.02
    pelvic_hi = np.max([f['pos'].max(0) for f in F.values() if f['group'] in ('pelvic', 'coccyx')], axis=0) + 0.02
    near = lambda m: overlaps(m['pos'].min(0), m['pos'].max(0), pelvic_lo, pelvic_hi)
    # 1. Thin HRA ligaments and uterine vessels stay in front of the sacrum/coccyx and medial to the
    #    hip bones (height-field clamps; the HRA meshes are open, so normal-based tests are unreliable).
    sac = np.vstack([M[cfg_ids['sacrum']]['pos'], F['VH_F_coccyx']['pos']])
    hip_l, hip_r = M[cfg_ids['hip_L']]['pos'], M[cfg_ids['hip_R']]['pos']
    for n, f in F.items():
        if f['group'] != 'pelvic' or not HRA_SOFT.search(n):
            continue
        p, d0 = ml.clamp_heightfield(f['pos'], sac, axis=2, sign=1, reach=0.08)
        d1 = d2 = 0.0
        if 'round_ligament' not in n:
            left, right = p[:, 0] > 0, p[:, 0] <= 0
            pl, d1 = ml.clamp_heightfield(p[left], hip_l, axis=0, sign=-1, reach=0.05)
            pr, d2 = ml.clamp_heightfield(p[right], hip_r, axis=0, sign=1, reach=0.05)
            p[left], p[right] = pl, pr
        if max(d0, d1, d2) > 0:
            f['pos'] = p; f['warped'] = True
            stats[n] = max(d0, d1, d2) * 1000
    # 2. BodyParts3D viscera, vessels, nerves, ureters and pelvic floor muscles give way to the
    #    solid female organs, represented by closed convex hulls (exact inside test).
    hull_groups = {
        'uterus': lambda n: re.search(r'uterus|cornua|cervi|uterine_segment|cervical_os', n) and not HRA_SOFT.search(n),
        'vagina': lambda n: 'vagina' in n,
        'bladder': lambda n: 'bladder' in n or 'trigone' in n or 'ureteral_orifice' in n,
        'adnexa_L': lambda n: n.endswith('_L') and re.search(r'ovary|tube|fibria|infundibulum|ampulla|isthmus|mesosalpinx|mesovarium|ovarian', n),
        'adnexa_R': lambda n: n.endswith('_R') and re.search(r'ovary|tube|fibria|infundibulum|ampulla|isthmus|mesosalpinx|mesovarium|ovarian', n),
        'coccyx': lambda n: n == 'VH_F_coccyx',
    }
    import trimesh
    hulls = []
    for g, test in hull_groups.items():
        pts = [f['pos'] for n, f in F.items() if f['group'] in ('pelvic', 'coccyx') and test(n) or (g.startswith('adnexa') and n == ('VH_F_left_ovary' if g.endswith('L') else 'VH_F_right_ovary'))]
        if pts:
            hulls.append(trimesh.convex.convex_hull(np.vstack(pts)))
    residual = {}
    for i, m in M.items():
        if not near(m):
            continue
        movable = m['system'] in ('digestive', 'urinary', 'lymphatic', 'venous', 'arterial', 'nervous') or LEVATOR.search(m['name'])
        if not movable:
            continue
        pos, d, left_inside = ml.push_out_convex(m['pos'], hulls, margin=0.0015, radius=0.014)
        if d > 1e-5:
            m['pos'] = pos; m['warped'] = True
            stats[i] = d * 1000
            if left_inside:
                residual[i] = left_inside
    report['viscera_residual_inside_vertices'] = residual
    # 2b. Whole-loop moves: where a bowel loop still crosses an organ (e.g. the BodyParts3D sigmoid
    #     colon hangs where the uterus sits, with the uterus inside its loop), shift that part of the
    #     loop away from the organ; slings around the vagina (levator ani, pudendal veins) open radially.
    vag = F['VH_F_vagina']['pos']; vc = vag.mean(0)
    _, _, vt = np.linalg.svd(vag - vc, full_matrices=False)
    names = list(hull_groups)
    room = {}
    for i, m in M.items():
        if not near(m):
            continue
        sling = LEVATOR.search(m['name']) or (m['system'] in ('venous', 'arterial', 'nervous'))
        if not (sling or m['system'] in ('digestive', 'urinary', 'lymphatic')):
            continue
        for g, hull in zip(names, hulls):
            if g == 'coccyx' and m['system'] != 'digestive' and not LEVATOR.search(m['name']):
                continue
            a = ml.to_trimesh(m['pos'], m['idx'])
            if not overlaps(a.bounds[0], a.bounds[1], hull.bounds[0], hull.bounds[1]) or not ml.collides(a, hull):
                continue
            cap = 0.04 if m['system'] == 'digestive' else 0.02
            if sling and g == 'vagina':
                pos, amp, ok = ml.make_room(m['pos'], m['idx'], hull, axis_point=vc, axis_dir=vt[0], sigma=0.02, max_amp=cap)
            else:
                pos, amp, ok = ml.make_room(m['pos'], m['idx'], hull, direction=away(m['pos'], hull.centroid), sigma=0.035, max_amp=cap)
            if ok and amp > 0:
                m['pos'] = pos; m['warped'] = True
                stats[i] = max(stats.get(i, 0), amp * 1000)
            room[f'{i} vs {g}'] = {'amplitude_mm': amp * 1000, 'clean': ok}
    # 2c'. Bowel also clears the thin peritoneal sheets and uterine vessels lying over the organs.
    sheets = {n: ml.to_trimesh(f['pos'], f['idx']) for n, f in F.items()
              if f['group'] == 'pelvic' and re.search(r'broad|uterovesical|round_ligament|uterine_(artery|vein)|cardinal|mesosalpinx', n)}
    for i, m in M.items():
        if m['system'] != 'digestive' or not near(m):
            continue
        for n, sheet in sheets.items():
            a = ml.to_trimesh(m['pos'], m['idx'])
            if not overlaps(a.bounds[0], a.bounds[1], sheet.bounds[0], sheet.bounds[1]) or not ml.collides(a, sheet):
                continue
            pos, amp, ok = ml.make_room(m['pos'], m['idx'], sheet, direction=away(m['pos'], sheet.vertices.mean(0)), sigma=0.03, max_amp=0.03)
            if ok and amp > 0:
                m['pos'] = pos; m['warped'] = True
                stats[i] = max(stats.get(i, 0), amp * 1000)
            room[f'{i} vs {n}'] = {'amplitude_mm': amp * 1000, 'clean': ok}
    report['make_room'] = room
    # 2c. Round ligaments run from the uterine cornua through the inguinal canal to the labia majora;
    #     keep their distal part from straying lateral to the pubic tubercles into the thigh.
    for n in ('VH_F_left_round_ligament_of_uterus', 'VH_F_right_round_ligament_of_uterus'):
        p = F[n]['pos'].copy()
        side = 'L' if p[:, 0].mean() > 0 else 'R'
        hip = M[cfg_ids['hip_' + side]]['pos']
        tub = hip[hip[:, 1] < np.median(hip[:, 1])]
        tub = tub[np.argmax(tub[:, 2])]
        below = p[:, 1] < tub[1] + 0.01
        t = ml.smoothstep(0, 0.03, tub[1] + 0.01 - p[below, 1])
        p[below, 0] = p[below, 0] * (1 - t) + np.sign(tub[0]) * np.minimum(np.abs(p[below, 0]), abs(tub[0]) * 0.8) * t
        p[below, 2] = np.maximum(p[below, 2], tub[2] * t + p[below, 2] * (1 - t))
        if below.any():
            F[n]['pos'] = p; F[n]['warped'] = True
    # 3. Breast fat gives way to the chest wall muscles.
    chest = union_mesh([(m['pos'], m['idx']) for m in M.values() if m['system'] in ('muscular', 'skeletal') and 1.0 < m['pos'][:, 1].mean() < 1.5])
    for n, f in F.items():
        if f['group'].startswith('breast'):
            a = ml.to_trimesh(f['pos'], f['idx'])
            if ml.collides(a, chest):
                f['pos'], d = ml.push_out(f['pos'], chest, margin=0.001, radius=0.02)
                stats[n] = d * 1000
    report['collision_resolution_max_displacement_mm'] = stats
    log('resolved', len(stats), 'structures; max displacement mm', round(max(stats.values(), default=0), 1))


# ============================================================== stage 4: skin

# Skin within these distances of the (removed) penis and testes/epididymides is penile/scrotal
# skin. Only skin within 4 cm of the midline is cut, so the medial thigh skin is kept.
EXTERNAL_MALE = {'FJ3132': 0.009, 'FJ3133': 0.009, 'FJ3134': 0.009, 'FJ3136': 0.014, 'FJ3138': 0.014, 'FJ3141': 0.014, 'FJ3142': 0.014}
CUT_HALF_WIDTH = 0.04


def boundary_loops(faces):
    """Ordered boundary vertex loops of a triangle mesh."""
    from collections import defaultdict
    count = defaultdict(int)
    directed = {}
    for a, b, c in faces:
        for u, v in ((a, b), (b, c), (c, a)):
            key = (min(u, v), max(u, v))
            count[key] += 1
            directed[key] = (u, v)
    nxt = {}
    for key, k in count.items():
        if k == 1:
            u, v = directed[key]
            nxt[v] = u  # walk opposite to the face winding so new faces wind consistently
    loops, seen = [], set()
    for start in list(nxt):
        if start in seen:
            continue
        loop, v = [], start
        while v not in seen and v in nxt:
            seen.add(v); loop.append(v); v = nxt[v]
        if len(loop) > 2:
            loops.append(loop)
    return loops


def fill_loop(pos, faces, loop, rings=6, iterations=400):
    """Close a hole with concentric rings relaxed to a smooth membrane (boundary fixed)."""
    pos = list(map(np.asarray, pos))
    base = len(pos)
    ring_prev = loop
    centre = np.mean([pos[i] for i in loop], axis=0)
    new_faces = []
    all_new = []
    m = len(loop)
    for r in range(1, rings + 1):
        t = r / (rings + 1)
        ring = []
        for i in loop:
            pos.append(pos[i] * (1 - t) + centre * t)
            ring.append(len(pos) - 1)
        all_new += ring
        for k in range(m):
            a, b = ring_prev[k], ring_prev[(k + 1) % m]
            c, d = ring[(k + 1) % m], ring[k]
            new_faces += [(a, b, c), (a, c, d)]
        ring_prev = ring
    pos.append(centre); cidx = len(pos) - 1; all_new.append(cidx)
    for k in range(m):
        new_faces.append((ring_prev[k], ring_prev[(k + 1) % m], cidx))
    pos = np.array(pos)
    # Laplacian relaxation of the new vertices only.
    from collections import defaultdict
    nb = defaultdict(set)
    for a, b, c in new_faces:
        nb[a] |= {b, c}; nb[b] |= {a, c}; nb[c] |= {a, b}
    movable = np.array(all_new)
    neigh = [np.array(sorted(nb[v])) for v in movable]
    for _ in range(iterations):
        pos[movable] = np.array([pos[n].mean(0) for n in neigh])
    return pos, np.vstack([faces, np.array(new_faces)])


def adapt_skin(M, male, stature, F, cfg, report):
    from scipy.spatial import cKDTree
    sid = cfg['skin']
    skin = M[sid]
    pos, faces = skin['pos'], skin['idx'].reshape(-1, 3)
    near = np.zeros(len(pos), bool)
    wide = np.zeros(len(pos), bool)
    for pid, thr in EXTERNAL_MALE.items():
        g = male[pid]['pos'] * stature
        d, _ = cKDTree(g).query(pos, distance_upper_bound=0.05)
        near |= d < thr
        wide |= np.isfinite(d)
    near &= np.abs(pos[:, 0]) < CUT_HALF_WIDTH
    drop = near[faces].all(1)
    kept = faces[~drop]
    # Remove islands orphaned by the cut (all of their vertices lie within 5 cm of the removed
    # genitalia); every other skin component is kept.
    import trimesh
    tm = trimesh.Trimesh(pos, kept, process=False)
    comps = trimesh.graph.connected_components(tm.face_adjacency, min_len=1)
    keep_faces = [c for c in comps if not wide[kept[c]].all()]
    kept = kept[np.sort(np.concatenate(keep_faces))]
    # Fill only the openings created by the cut, not the skin's own openings (eyes, mouth, nostrils).
    cut_edge = np.zeros(len(pos), bool)
    cut_edge[np.unique(faces[drop])] = True
    loops = [l for l in boundary_loops(kept) if len(l) >= 8 and cut_edge[l].mean() > 0.5]
    for loop in loops:
        pos, kept = fill_loop(pos, kept, loop)
    used = np.unique(kept)
    remap = -np.ones(len(pos), int); remap[used] = np.arange(len(used))
    pos = pos[used]; kept = remap[kept]
    # Chest: wrap the skin around each breast (convex hull of all HRA breast structures + 2 mm).
    for side in 'LR':
        pts = np.vstack([f['pos'] for f in F.values() if f['group'] == 'breast_' + side])
        hull = trimesh.convex.convex_hull(pts)
        pos, d = ml.push_out(pos, hull, margin=0.0025, radius=0.03, iterations=10)
        report.setdefault('skin', {})['breast_' + side + '_max_mm'] = d * 1000
    skin['pos'], skin['idx'] = pos, kept.reshape(-1)
    skin['warped'] = True
    skin['nrm'] = None
    report.setdefault('skin', {}).update({'removed_faces': int(drop.sum()), 'holes_closed': len(loops),
                                          'hole_sizes': [len(l) for l in loops]})
    log('skin', report['skin'])


# ============================================================== stage 5: generated structures

def vulva_landmarks(F, M, cfg, lm, tmp):
    import trimesh
    pb = cfg['pelvis_bones']
    skin = ml.to_trimesh(M[cfg['skin']]['pos'], M[cfg['skin']]['idx'])
    vag = F['VH_F_vagina']['pos']
    c = vag.mean(0)
    _, _, vt = np.linalg.svd(vag - c, full_matrices=False)
    axis = vt[0] if vt[0][1] < 0 else -vt[0]                      # outward = downward
    proj = (vag - c) @ axis
    inner = vag[proj > proj.max() - 0.003].mean(0)
    inner[0] = 0.0
    # Vaginal orifice: the midline skin point nearest the vagina's outer end.
    sv = skin.vertices
    band = sv[(np.abs(sv[:, 0]) < 0.008) & (sv[:, 1] < inner[1] + 0.01)]
    introitus = band[np.argmin(np.linalg.norm(band - inner, axis=1))].copy()
    introitus[0] = 0.0
    _, _, tri = trimesh.proximity.closest_point(skin, [introitus])
    normal = skin.face_normals[tri[0]].copy()
    normal[0] = 0.0
    normal /= np.linalg.norm(normal)
    if normal @ (introitus - inner) < 0:
        normal = -normal
    S = (lm['symphysis_bottom_L'] + lm['symphysis_bottom_R']) / 2; S[0] = 0
    ap = S - introitus; ap -= normal * (ap @ normal); ap[0] = 0; ap /= np.linalg.norm(ap)

    midline = sv[(np.abs(sv[:, 0]) < 0.008) & (sv[:, 1] < S[1] + 0.03) & (sv[:, 1] > introitus[1] - 0.06)]

    def snap(p):
        """Nearest skin point to p within the perineal midline band (x forced to 0)."""
        q = midline[np.argmin(np.linalg.norm(midline - p, axis=1))].copy()
        q[0] = 0.0
        return q
    glans = snap(introitus + ap * 0.032)
    meatus = snap(introitus + ap * 0.013)
    out = {'introitus': introitus, 'vulva_normal': normal, 'glans_site': glans, 'meatus': meatus,
           'meatus_inner': meatus - normal * 0.0015,
           'anterior_commissure': snap(introitus + ap * 0.058), 'posterior_commissure': snap(introitus - ap * 0.022),
           'vagina_axis': axis, 'symphysis_bottom': S}
    sph = np.vstack([M[i]['pos'] for i in M if 'anal sphincter' in M[i]['name'].lower()])
    out['perineal_body'] = (introitus + sph.mean(0)) / 2 - normal * 0.01
    out['clitoral_root'] = S + (glans - S) * 0.3 - normal * 0.004
    centre = (S + introitus) / 2
    for side, key in (('left', 'L'), ('right', 'R')):
        hip = M[pb['hip_' + key]]['pos']
        a, b = lm['symphysis_bottom_' + key], lm['ischial_tuberosity_' + key]
        pts = []
        for t in (0.18, 0.38, 0.58, 0.75):
            q = a + (b - a) * t
            bone = hip[np.argmin(np.linalg.norm(hip - q, axis=1))]
            d = centre - bone; d[1] *= 0.3; d /= np.linalg.norm(d)
            pts.append(bone + d * 0.0065)
        out['crus_' + side] = [p.tolist() for p in pts]
    neck = F['VH_F_urinary_bladder_neck_smooth_muscle']['pos'].mean(0)
    out['bladder_neck'] = neck + (meatus - neck) / np.linalg.norm(meatus - neck) * 0.002
    mid = (out['bladder_neck'] + meatus) / 2
    band = vag[(np.abs(vag[:, 0]) < 0.01) & (np.abs(vag[:, 1] - mid[1]) < 0.006)]
    hip = np.vstack([M[pb['hip_L']]['pos'], M[pb['hip_R']]['pos']])
    sym = hip[(np.abs(hip[:, 0]) < 0.02) & (np.abs(hip[:, 1] - mid[1]) < 0.006)]
    z_v = band[:, 2].max() if len(band) else mid[2]
    z = z_v + 0.0045
    if len(sym):
        z = min(z, sym[:, 2].min() - 0.0045)
    out['urethra_mid'] = np.array([0.0, mid[1], z])
    # Perineal skin patch for projecting surface structures inside Blender.
    sel = np.linalg.norm(skin.triangles_center - introitus, axis=1) < 0.09
    patch = skin.submesh([np.where(sel)[0]], append=True)
    ml.write_obj(tmp / 'skin_patch.obj', patch.vertices, patch.faces.reshape(-1))
    out['skin_patch'] = str(tmp / 'skin_patch.obj')
    return {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in out.items()}


GENERATED = {
    # file stem: (display name, system, FMA label for lookup, group concepts)
    'labium_majus_left': ('Left labium majus', 'reproductive', 'left labium majus', ['vulva']),
    'labium_majus_right': ('Right labium majus', 'reproductive', 'right labium majus', ['vulva']),
    'labium_minus_left': ('Left labium minus', 'reproductive', 'left labium minus', ['vulva']),
    'labium_minus_right': ('Right labium minus', 'reproductive', 'right labium minus', ['vulva']),
    'vestibule_of_vagina': ('Vestibule of vagina', 'reproductive', 'vestibule of vagina', ['vulva']),
    'glans_of_clitoris': ('Glans of clitoris', 'reproductive', 'glans of clitoris', ['vulva', 'clitoris']),
    'body_of_clitoris': ('Body of clitoris', 'reproductive', 'body of clitoris', ['vulva', 'clitoris']),
    'crus_of_clitoris_left': ('Left crus of clitoris', 'reproductive', 'left crus of clitoris', ['vulva', 'clitoris']),
    'crus_of_clitoris_right': ('Right crus of clitoris', 'reproductive', 'right crus of clitoris', ['vulva', 'clitoris']),
    'bulb_of_vestibule_left': ('Left bulb of vestibule', 'reproductive', 'left bulb of vestibule', ['vulva']),
    'bulb_of_vestibule_right': ('Right bulb of vestibule', 'reproductive', 'right bulb of vestibule', ['vulva']),
    'female_urethra': ('Female urethra', 'urinary', 'female urethra', []),
    'ischiocavernosus_left': ('Left ischiocavernosus', 'muscular', 'left ischiocavernosus', ['female perineal muscles']),
    'ischiocavernosus_right': ('Right ischiocavernosus', 'muscular', 'right ischiocavernosus', ['female perineal muscles']),
    'bulbospongiosus_left': ('Left bulbospongiosus', 'muscular', 'left bulbospongiosus', ['female perineal muscles']),
    'bulbospongiosus_right': ('Right bulbospongiosus', 'muscular', 'right bulbospongiosus', ['female perineal muscles']),
}
CREATE_SCRIPTS = ['create_vulva.py', 'create_clitoris.py', 'create_female_urethra.py', 'create_perineal_muscles.py']


def generate(F, M, cfg, lm, report, blender):
    import blender_run
    tmp = Path(tempfile.gettempdir()) / 'ha-female' / 'generated'
    if tmp.exists():
        for f in tmp.glob('*'):
            f.unlink()
    tmp.mkdir(parents=True, exist_ok=True)
    landmarks = vulva_landmarks(F, M, cfg, lm, tmp)
    (tmp / 'landmarks.json').write_text(json.dumps(landmarks, indent=1))
    (WORK / 'landmarks.json').write_text(json.dumps(landmarks, indent=1))
    logs = {}
    for script in CREATE_SCRIPTS:
        stdout = blender_run.run(HERE / script, [tmp / 'landmarks.json', tmp], blender)
        logs[script] = [l for l in stdout.splitlines() if l.startswith(('wrote', 'URETHRA'))]
        log(script, 'ok')
    G = {}
    for stem, (name, system, label, groups) in GENERATED.items():
        pos, idx = ml.read_obj(tmp / f'{stem}.obj')
        G[stem] = {'pos': pos, 'idx': idx, 'name': name, 'system': system, 'label': label, 'groups': groups}
    report['generated'] = {'blender_output': logs, 'landmarks': 'work/female/landmarks.json'}
    return G


def check_generated(G, F, M, cfg, report, rounds=6):
    """Collision fix loop for generated structures: push them out of bone and HRA organs, push
    BodyParts3D soft tissue out of them, then re-check until clean (or report what remains)."""
    import trimesh
    pb = cfg['pelvis_bones']
    bones = [ml.to_trimesh(M[pb[k]]['pos'], M[pb[k]]['idx']) for k in ('hip_L', 'hip_R', 'sacrum')]
    bones.append(ml.to_trimesh(F['VH_F_coccyx']['pos'], F['VH_F_coccyx']['idx']))
    organs = {n: ml.to_trimesh(f['pos'], f['idx']) for n, f in F.items() if f['group'] == 'pelvic' and not HRA_SOFT.search(n)}
    # Thigh muscles bordering the perineum (rigid here: they are not perineal structures).
    perineum = np.vstack([g['pos'] for g in G.values()])
    plo, phi = perineum.min(0) - 0.01, perineum.max(0) + 0.01
    thigh = [ml.to_trimesh(m['pos'], m['idx']) for m in M.values()
             if m['system'] == 'muscular' and re.search(r'gracilis|adductor|obturator externus|pectineus', m['name'], re.I)
             and overlaps(m['pos'].min(0), m['pos'].max(0), plo, phi)]
    # Which obstacles each generated structure must clear (the urethra may touch the bladder neck).
    def obstacles(stem):
        obs = list(bones) + thigh
        for n, t in organs.items():
            if stem == 'female_urethra' and ('bladder' in n or 'trigone' in n):
                continue
            obs.append(t)
        return trimesh.util.concatenate(obs)
    order = ['female_urethra', 'crus_of_clitoris_left', 'crus_of_clitoris_right', 'body_of_clitoris', 'glans_of_clitoris',
             'bulb_of_vestibule_left', 'bulb_of_vestibule_right', 'vestibule_of_vagina', 'labium_minus_left', 'labium_minus_right',
             'labium_majus_left', 'labium_majus_right', 'ischiocavernosus_left', 'ischiocavernosus_right',
             'bulbospongiosus_left', 'bulbospongiosus_right']
    history = {}
    for stem in order:
        g = G[stem]
        obs = obstacles(stem)
        # Muscles additionally clear the erectile tissue they cover.
        if stem.startswith(('ischiocavernosus', 'bulbospongiosus')):
            covered = 'crus_of_clitoris_' if stem.startswith('ischio') else 'bulb_of_vestibule_'
            side = stem.split('_')[-1]
            obs = trimesh.util.concatenate([obs, ml.to_trimesh(G[covered + side]['pos'], G[covered + side]['idx'])])
        steps = []
        for r in range(rounds):
            a = ml.to_trimesh(g['pos'], g['idx'])
            hit = ml.collides(a, obs)
            steps.append(bool(hit))
            if not hit:
                break
            g['pos'], d = ml.push_out(g['pos'], obs, margin=0.0008, radius=0.006, iterations=4)
            # Taubin smoothing removes push artefacts without shrinking the part; re-checked next round.
            t = ml.to_trimesh(g['pos'], g['idx'])
            trimesh.smoothing.filter_taubin(t, lamb=0.5, nu=-0.53, iterations=8)
            g['pos'] = np.asarray(t.vertices)
        history[stem] = {'collision_by_round': steps, 'clean': not steps[-1] if steps else True}
    # BodyParts3D soft tissue (pelvic floor, vessels, nerves) gives way to the generated structures.
    gen = trimesh.util.concatenate([ml.to_trimesh(g['pos'], g['idx']) for s, g in G.items() if s != 'labium_majus_left' and s != 'labium_majus_right'])
    moved = {}
    for i, m in M.items():
        movable = m['system'] in ('venous', 'arterial', 'nervous', 'digestive', 'lymphatic') or LEVATOR.search(m['name'])
        if not movable or not overlaps(m['pos'].min(0), m['pos'].max(0), gen.bounds[0], gen.bounds[1]):
            continue
        if not ml.collides(ml.to_trimesh(m['pos'], m['idx']), gen):
            continue
        pos, amp, ok = ml.make_room(m['pos'], m['idx'], gen, direction=away(m['pos'], gen.centroid, 0.08), sigma=0.015, step=0.0015, max_amp=0.02)
        if ok and amp > 0:
            m['pos'] = pos; m['warped'] = True
        moved[i] = {'amplitude_mm': amp * 1000, 'clean': ok}
    report['generated_collision_loop'] = {'generated': history, 'bp3d_soft_tissue_rounds': moved}
    log('generated collision loop', {k: v['clean'] for k, v in history.items()})


# ============================================================== stage 6: manifest

HRA_GROUP_LABELS = {
    'VH_F_reproductive_system': 'female reproductive system', 'VH_F_uterus': 'uterus', 'VH_F_ovary': 'ovary',
    'VH_F_fallopian_tube': 'uterine tube', 'VH_F_fallopian_tube_L': 'left uterine tube', 'VH_F_fallopian_tube_R': 'right uterine tube',
    'VH_F_ligaments_of_uterus_and_ovaries': 'ligaments of uterus and ovaries', 'VH_F_broad_ligament': 'broad ligament of uterus',
    'VH_F_round_ligament_of_uterus': 'round ligament of uterus', 'VH_F_ovarian_ligament': 'ovarian ligament',
    'VH_F_uterosacral_ligament': 'uterosacral ligament', 'VH_F_cardinal_ligament_of_uterus': 'cardinal ligament',
    'VH_F_suspensory_ligament_of_ovary': 'suspensory ligament of ovary', 'VH_F_mesosalpinx': 'mesosalpinx', 'VH_F_mesovarium': 'mesovarium',
    'VH_F_urinary_bladder': 'urinary bladder', 'VH_F_mammary_gland': 'mammary gland', 'VH_F_mammary_gland_L': 'left mammary gland',
    'VH_F_mammary_gland_R': 'right mammary gland', 'VH_F_blood_vasculature_of_uterus': 'blood vessels of uterus',
    'VH_F_uterine_artery': 'uterine artery', 'VH_F_uterine_vein': 'uterine vein', 'VH_F_ureteral_orifice': 'ureteral orifice',
    'VH_F_fundus_of_urinary_bladder_base': 'fundus of urinary bladder',
}
GROUP_NAMES = {'vulva': 'Vulva (external genitalia)', 'clitoris': 'Clitoris', 'female perineal muscles': 'Superficial perineal muscles (female)'}


def title(s):
    return s[:1].upper() + s[1:]


def side_of(x):
    return 'left' if x > 0.004 else 'right' if x < -0.004 else None


def hra_name(name, f, fixes):
    label = str(f['hra']['extras'].get('label') or '').strip()
    if label in ('', '-', 'None', 'NA'):
        label = name.replace('VH_F_', '').replace('_', ' ').strip()
    low = label.lower()
    x = f['pos'][:, 0].mean()
    side = side_of(x)
    if side and ('left' in low or 'right' in low):
        wrong = ('left' in low and side == 'right') or ('right' in low and side == 'left')
        if wrong:
            fixed = re.sub(r'(?i)\b(left|right)\b', lambda m: {'left': 'right', 'right': 'left'}[m.group(1).lower()], label)
            fixes[name] = {'source_label': label, 'corrected': fixed, 'centroid_x_m': float(x)}
            label = fixed
    elif side and re.search(r'_[LR]$|_[LR]_|left|right', name, re.I):
        label = f'{side} {low}'
    return title(label)


def write_package(M, F, G, atlas, cfg, removed, report):
    xrefs = json.loads((HERE / 'ontology_xrefs.json').read_text())
    by_label = xrefs['labels']
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob('*'):
        old.unlink()
    parts, chunks, blob = [], [], bytearray()
    total = 0

    def flush():
        nonlocal blob
        if blob:
            url = f'/models/female/source-female-{len(chunks)}.bin'
            (OUT / url.split('/')[-1]).write_bytes(blob)
            chunks.append({'url': url, 'bytes': len(blob)})
            blob = bytearray()

    def append(arr):
        while len(blob) % 4:
            blob.append(0)
        off = len(blob); blob.extend(arr.tobytes()); return off

    def add(entry, pos, nrm, idx):
        nonlocal total
        if len(blob) > 7_000_000:
            flush()
        pos = np.asarray(pos, np.float32)
        nrm = ml.quantize_normals(ml.vertex_normals(pos.astype(np.float64), idx)) if nrm is None else np.asarray(nrm)
        if nrm.dtype != np.int16:
            nrm = ml.quantize_normals(nrm)
        idx = np.asarray(idx, np.uint32)
        entry.update({'chunk': len(chunks), 'positions': append(pos), 'normals': append(nrm), 'indices': append(idx),
                      'vertexCount': len(pos), 'indexCount': len(idx), 'bounds': ml.bounds(pos.astype(np.float64))})
        total += len(idx) // 3
        parts.append(entry)

    notes = cfg.get('notes', {})
    pelvis_ids = {cfg['pelvis_bones'][k] for k in ('hip_L', 'hip_R', 'sacrum')}
    for p in atlas['parts']:
        if p['id'] not in M:
            continue
        m = M[p['id']]
        e = {'id': p['id'], 'name': p['name'], 'conceptId': p['conceptId'], 'system': p['system'], 'source': 'bp3d', 'preoptimized': True}
        if p['id'] in pelvis_ids:
            e['accuracy'] = 'schematic'
            e['note'] = 'Male BodyParts3D bone morphed toward published female pelvic proportions (approximate).'
        elif p['id'] == cfg['skin']:
            e['accuracy'] = 'schematic'
            e['note'] = 'BodyParts3D skin with the external male genitalia removed, the opening closed schematically, and the chest reshaped over the HRA breasts.'
        elif m.get('warped'):
            e['accuracy'] = 'warped'
        else:
            e['accuracy'] = 'source'
        nrm = None if (m.get('warped') or m['nrm'] is None) else m['nrm']
        add(e, m['pos'], nrm, m['idx'])
    xref = xrefs['uberon']
    fixes = {}
    hra_part_ids = {}
    for n, f in F.items():
        u = str(f['hra']['extras'].get('ontologyid') or '')
        if not u.startswith(('UBERON', 'FMA', 'CL', 'ILX')):
            u = ''  # source placeholder such as '-'
        fma = (xref.get(u) or {}).get('fma')
        e = {'id': n, 'name': hra_name(n, f, fixes), 'conceptId': fma or u or 'HRA:' + n, 'uberon': u, 'system': f['system'],
             'source': 'hra', 'accuracy': 'warped' if f.get('warped') else 'source'}
        if n == 'VH_F_coccyx':
            e['note'] = 'HRA coccyx re-oriented to continue the morphed sacrum.'
        hra_part_ids[n] = n
        add(e, f['pos'], f['nrm'], f['idx'])
    for stem, g in G.items():
        e = {'id': 'GEN_' + stem, 'name': g['name'], 'conceptId': by_label.get(g['label']) or 'GEN:' + stem, 'system': g['system'],
             'source': 'generated', 'accuracy': 'schematic',
             'note': 'Approximate / schematic, not scan-derived. Generated in Blender from reference dimensions (see DATA_SOURCES.md).'}
        add(e, g['pos'], None, g['idx'])
    flush()
    ids = {p['id'] for p in parts}
    # ---- concepts
    replaced = {pid: [] for pid in removed}
    replaced['FJ3149'] = [n for n, f in F.items() if f['system'] == 'urinary']
    concepts, seen = [], {}

    def add_concept(cid, name, elements):
        elements = [e for e in dict.fromkeys(elements) if e in ids]
        if not elements:
            return
        if cid in seen:
            c = seen[cid]
            c['elements'] = list(dict.fromkeys(c['elements'] + elements))
            return
        c = {'id': cid, 'name': name, 'elements': elements}
        seen[cid] = c; concepts.append(c)
    for c in atlas['concepts']:
        els = []
        for e in c['elements']:
            els += replaced.get(e, [e]) if e in removed else [e]
        add_concept(c['id'], c['name'], els)
    # HRA group concepts follow the GLB hierarchy.
    groups = {}
    for n, f in F.items():
        for anc_name in f['hra']['ancestor_names']:
            groups.setdefault(anc_name, []).append(n)
    for g, members in groups.items():
        if g in ('VH_F', 'VH_F_integumentary_system', 'VH_F_circulatory_system', 'VH_F_blood_vasculature', 'VH_F_skeletal_system', 'VH_F_urinary_system'):
            continue
        label = HRA_GROUP_LABELS.get(g, g.replace('VH_F_', '').replace('_', ' '))
        add_concept(by_label.get(label) or 'HRA:' + g, title(label), members)
    for p in parts:
        if p['source'] == 'hra':
            cid = p['conceptId'] if sum(q['conceptId'] == p['conceptId'] for q in parts) == 1 else p['id']
            add_concept(cid, p['name'], [p['id']])
    for stem, g in G.items():
        cid = by_label.get(g['label']) or 'GEN:' + stem
        add_concept(cid, g['name'], ['GEN_' + stem])
        for grp in g['groups']:
            gid = by_label.get(grp) or 'GEN:' + grp.replace(' ', '-')
            add_concept(gid, GROUP_NAMES.get(grp, title(grp)), ['GEN_' + stem])
    add_concept(by_label.get('female pelvis') or 'GEN:female-pelvis', 'Female pelvis (morphed, approximate)',
                [cfg['pelvis_bones'][k] for k in ('hip_L', 'hip_R', 'sacrum')] + ['VH_F_coccyx'])
    add_concept(by_label.get('breast') or 'GEN:breasts', 'Breasts', [n for n, f in F.items() if f['group'].startswith('breast')])
    manifest = {
        'version': 'Human Atlas female 1.0 (BodyParts3D 4.0 + HRA united-female v1.5 + generated)',
        'sex': 'female', 'source': 'BodyParts3D 4.0, HRA 3D Reference Organ Set for Female v1.5, generated schematic structures',
        'scope': 'Adult female reference assembly. Shared structures from the BodyParts3D male reference, scaled; female-specific structures from HRA or generated (marked approximate).',
        'sources': SOURCES, 'accuracyNotes': ACCURACY_NOTES, 'parts': parts, 'concepts': concepts, 'chunks': chunks,
        'triangles': total, 'build': {'statureScale': report['stature_scale'], 'removedMaleParts': sorted(removed),
                                      'labelCorrections': fixes, 'report': 'work/female/report.json'},
    }
    (OUT / 'atlas.json').write_text(json.dumps(manifest, separators=(',', ':')))
    report['package'] = {'parts': len(parts), 'concepts': len(concepts), 'triangles_before_simplification': total,
                         'by_source': {s: sum(p['source'] == s for p in parts) for s in SOURCES},
                         'by_accuracy': {a: sum(p['accuracy'] == a for p in parts) for a in ACCURACY_NOTES}, 'label_corrections': fixes}
    log('package', json.dumps(report['package']))


# ============================================================== driver

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--hra', default=str(ROOT / 'work/sources/hra/3d-vh-f-united.glb'))
    ap.add_argument('--blender', default='blender')
    ap.add_argument('--debug-obj', action='store_true', help='also export pelvic/chest OBJs to work/female/debug')
    ap.add_argument('--until', default='all')
    ap.add_argument('--resume', action='store_true', help='developer aid: restart after collision resolution from work/female/stage3.pkl')
    args = ap.parse_args()
    cfg = json.loads((HERE / 'config.json').read_text())
    WORK.mkdir(parents=True, exist_ok=True)
    if args.resume:
        return resume(args, cfg)
    report = {}
    atlas, male, doc, hra = load_inputs(args, cfg)
    removed = classify_male(atlas, cfg)
    skin_m = male[cfg['skin']]['pos']; skin_f = hra['VH_F_skin']['pos']
    stature = float(np.ptp(skin_f[:, 1]) / np.ptp(skin_m[:, 1]))
    report['stature_scale'] = stature
    M = {}
    for p in atlas['parts']:
        if p['id'] in removed:
            continue
        m = male[p['id']]
        M[p['id']] = {'pos': m['pos'] * stature, 'nrm': m['nrm'], 'idx': m['idx'], 'name': p['name'], 'system': p['system'], 'meta': p}
    report['removed_male_parts'] = removed
    log('stature scale', stature, 'kept', len(M), 'removed', len(removed))
    lm = morph_pelvis(M, atlas, cfg, report)
    log(json.dumps(report['pelvis'], indent=1))
    transforms, lm_f = register_hra(hra, M, lm, cfg, report)
    log(json.dumps(report['hra_pelvic_registration'], indent=1)[:3000])
    F = place_hra(hra, hra_selected(hra), transforms)
    fit_breasts_to_chest(F, M, report)
    log(json.dumps(report['breast_chest_fit']))
    fit_pelvic_block(F, M, cfg, report)
    orient_coccyx(F, M, cfg, report)
    connect_ureters(F, M, report)
    resolve_collisions(F, M, cfg, report)
    import pickle
    (WORK / 'stage3.pkl').write_bytes(pickle.dumps((M, F, lm, report, removed, stature)))
    G = {}
    return finish(args, cfg, atlas, male, M, F, lm, report, removed, stature)


def resume(args, cfg):
    import pickle
    atlas, male, doc, hra = load_inputs(args, cfg)
    M, F, lm, report, removed, stature = pickle.loads((WORK / 'stage3.pkl').read_bytes())
    return finish(args, cfg, atlas, male, M, F, lm, report, removed, stature)


def finish(args, cfg, atlas, male, M, F, lm, report, removed, stature):
    G = {}
    if args.until != 'survey':
        adapt_skin(M, male, stature, F, cfg, report)
        G = generate(F, M, cfg, lm, report, args.blender if args.blender != 'blender' else None)
        check_generated(G, F, M, cfg, report)
    # Final survey (documented in VERIFICATION.md): every remaining triangle intersection.
    fixed = {i: (m['pos'], m['idx']) for i, m in M.items() if m['system'] != 'integumentary'}
    final = {}
    for label, movers in (('hra-pelvic', {n: (f['pos'], f['idx']) for n, f in F.items() if f['group'] in ('pelvic', 'coccyx')}),
                          ('hra-breast', {n: (f['pos'], f['idx']) for n, f in F.items() if f['group'].startswith('breast')}),
                          ('generated', {'GEN_' + s: (g['pos'], g['idx']) for s, g in G.items()})):
        hits = survey(movers, fixed, label)
        final[label] = [[a, b, M[b]['name'], M[b]['system']] for a, b in hits]
        for h in final[label]:
            log('  ', *h)
    if G:
        organ = {n: (f['pos'], f['idx']) for n, f in F.items() if f['group'] in ('pelvic', 'coccyx') and not HRA_SOFT.search(n)}
        hits = survey({'GEN_' + s: (g['pos'], g['idx']) for s, g in G.items()}, organ, 'generated-vs-hra')
        final['generated-vs-hra'] = hits
    report['final_intersections'] = final
    if args.debug_obj:
        dbg = Path(tempfile.gettempdir()) / 'ha-female' / 'debug'
        dbg.mkdir(parents=True, exist_ok=True)
        for f in dbg.glob('*.obj'):
            f.unlink()
        for pid, m in M.items():
            c = m['pos'].mean(0)
            if 0.55 < c[1] < 1.45 and m['system'] in ('skeletal', 'muscular', 'digestive', 'urinary', 'integumentary', 'connective'):
                ml.write_obj(dbg / f"m_{m['system']}_{pid}.obj", m['pos'], m['idx'])
        for n, f in F.items():
            ml.write_obj(dbg / f"f_{f['system']}_{n}.obj", f['pos'], f['idx'])
        for s, g in G.items():
            ml.write_obj(dbg / f"g_{g['system']}_{s}.obj", g['pos'], g['idx'])
    if args.until == 'all':
        write_package(M, F, G, atlas, cfg, removed, report)
    (WORK / 'report.json').write_text(json.dumps(report, indent=1, default=float))


if __name__ == '__main__':
    main()
