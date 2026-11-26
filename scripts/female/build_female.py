"""Build the female Human Atlas package (public/models/female/).

    python scripts/build-anatomy.py --sex female          (runs everything below)
    python scripts/female/build_female.py [--hra GLB] [--resume] [--debug-obj]
    node scripts/optimize-anatomy.mjs female/atlas.json
    node scripts/compress-models.mjs female/atlas.json

Design (DECISIONS.md D21–D30):
  * Frame and body: the HRA united-female v1.5 assembly (Visible Human Female, CC BY 4.0) in its
    native scale, translated so the feet rest on y = 0. Its scan-derived skin is the body surface;
    its pelvis, sacrum, coccyx, uterus/adnexa/ligaments, vagina, bladder, uterine vessels and
    breasts (glands + adipose) keep their native positions.
  * Every other structure comes from the BodyParts3D male and is carried into that body by one
    thin-plate-spline warp computed from ~900 automatically extracted correspondences
    (scripts/female/body_warp.py). There is no uniform scaling.
  * Vulva, clitoris, vestibular bulbs, female urethra and superficial perineal muscles, and the
    extra gluteofemoral subcutaneous fat, are generated (Blender / Python) and labelled so.
Inputs: the male package (public/models), the HRA GLB, config.json, ontology_xrefs.json.
Outputs: public/models/female/atlas.json + source chunks, work/female/report.json.
"""
import argparse
import json
import pickle
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import body_target as bt  # noqa: E402
from hand_fit import articulated_hands  # noqa: E402
import body_warp as bw  # noqa: E402
import meshlib as ml  # noqa: E402

POSE = [None, None]   # (male pose json, MPFB rig joints) once retargeted
STATE = {}


MIDLINE = re.compile(r'vertebra|intervertebral|sternum|manubrium|xiphoid|body of sternum|sacrum|coccyx|axis|atlas', re.I)


def pin_midline(M, report, x0=0.0):
    """Remove any coronal bend: the lateral offset dx(y) of the vertebral bodies / sternum centroids
    from the mid-sagittal plane (x = x0; the MPFB body is symmetric about it) is interpolated along y
    and subtracted from every vertex, weighted by closeness to the midline (Gaussian, 7 cm) so the
    ribs, linea alba and paraspinal tissue follow without tearing."""
    pts = [(m['pos'][:, 1].mean(), m['pos'][:, 0].mean()) for m in M.values()
           if MIDLINE.search(m['name']) and not re.search(r'left|right', m['name'], re.I) and m['system'] == 'skeletal']
    pts = np.array(sorted(pts))
    if len(pts) < 4:
        return
    ys, dx = pts[:, 0], pts[:, 1] - x0
    # Smooth the offset profile (running mean over 5) so single bones do not create kinks.
    k = np.ones(5) / 5
    dxs = np.convolve(np.pad(dx, 2, mode='edge'), k, mode='valid')
    before = float(np.abs(dx).max() * 1000)
    for m in M.values():
        p = m['pos']
        if p[:, 1].max() < ys.min() - 0.05 or p[:, 1].min() > ys.max() + 0.05:
            continue
        off = np.interp(p[:, 1], ys, dxs)
        mid = MIDLINE.search(m['name']) and not re.search(r'left|right', m['name'], re.I)
        # Midline bones move by their own full offset (rigid); everything else by a smooth falloff.
        if mid and m['system'] == 'skeletal':
            off = np.full(len(p), p[:, 0].mean() - x0); w = np.ones(len(p))
        else:
            w = np.exp(-((p[:, 0] - x0) / 0.07) ** 2)
        m['pos'] = p - np.c_[off * w, np.zeros(len(p)), np.zeros(len(p))]
    after = [m['pos'][:, 0].mean() - x0 for m in M.values()
             if MIDLINE.search(m['name']) and not re.search(r'left|right', m['name'], re.I) and m['system'] == 'skeletal']
    report['midline'] = {'max_offset_before_mm': before, 'max_offset_after_mm': float(np.abs(after).max() * 1000), 'bones': int(len(pts))}
    log('midline', report['midline'])


def edge_ratios(src, dst, idx):
    t = idx.reshape(-1, 3)
    e = lambda p: np.stack([np.linalg.norm(p[t[:, a]] - p[t[:, b]], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))], 1)
    return e(dst) / np.maximum(e(src), 1e-7)


def relax_corrections(M, male, shell, report, limit=2.0, rounds=40):
    """Containment and make-room corrections are local pushes; where one stretched a triangle past
    `limit` x its source, diffuse that part's correction displacement (pos - warp-only pos) over the
    mesh until no triangle exceeds the limit (or the correction is spread out). Parts the warp itself
    already stretched are left for the report."""
    from scipy.sparse import coo_matrix
    fixed, left = 0, 0
    for pid, m in M.items():
        if 'warp_pos' not in m or m['system'] == 'skeletal' or pid in STATE.get('head_all', []):
            continue    # rigid parts (bones, the whole head) are never smoothed part by part
        src = male[pid]['pos']
        if not (edge_ratios(src, m['pos'], m['idx']) > limit).any():
            continue
        if (edge_ratios(src, m['warp_pos'], m['idx']) > limit).any():
            left += 1
            continue
        t = m['idx'].reshape(-1, 3)
        n = len(m['pos'])
        r = np.r_[t[:, 0], t[:, 1], t[:, 2], t[:, 1], t[:, 2], t[:, 0]]
        c = np.r_[t[:, 1], t[:, 2], t[:, 0], t[:, 0], t[:, 1], t[:, 2]]
        A = coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)).tocsr()
        A.data[:] = 1.0
        deg = np.asarray(A.sum(1)).ravel()
        D = m['pos'] - m['warp_pos']
        for _ in range(rounds):
            D = 0.5 * D + 0.5 * (A @ D) / np.maximum(deg, 1)[:, None]
            pos = m['warp_pos'] + D
            if not (edge_ratios(src, pos, m['idx']) > limit).any():
                break
        m['pos'] = pos
        fixed += 1
    report['stretch_relax'] = {'parts_relaxed': fixed, 'parts_stretched_by_warp': left}
    log('stretch relax', report['stretch_relax'])


def stretch_report(M, male, report, limit=2.0):
    """Gate: no warped triangle edge longer than `limit` x its source (BodyParts3D) length."""
    bad = {}
    total = 0
    by_warp = 0
    for pid, m in M.items():
        if m.get('scan_derived') or len(m['pos']) != len(male[pid]['pos']):
            continue            # real VHF geometry shown as-is: not a warped triangle
        r = edge_ratios(male[pid]['pos'], m['pos'], m['idx']).max(1)
        total += len(r)
        k = int((r > limit).sum())
        if k:
            w = int((edge_ratios(male[pid]['pos'], m['warp_pos'], m['idx']).max(1) > limit).sum()) if 'warp_pos' in m else -1
            by_warp += max(w, 0)
            bad[pid] = {'name': m['name'], 'triangles_over': k, 'max_ratio': float(r.max()), 'over_after_warp_only': w}
    touched = re.compile(r'gluteus (maximus|medius|minimus)|tensor fasciae latae|iliotibial', re.I)
    report['stretch_touched_m9'] = int(sum(b['triangles_over'] for b in bad.values() if touched.search(b['name'])))
    report['stretch'] = {'limit': limit, 'triangles': total, 'triangles_over': int(sum(b['triangles_over'] for b in bad.values())),
                         'triangles_over_after_warp_only': by_warp,
                         'parts': dict(sorted(bad.items(), key=lambda kv: -kv[1]['triangles_over'])[:40])}
    log('stretch', report['stretch']['triangles_over'], 'of', total, 'triangles over', limit, 'x;', len(bad), 'parts;',
        'gluteal region (m9 parts)', report['stretch_touched_m9'])


def female_shoulder_bulk(M, report, factor=0.75):
    """Phase 4: reduce deltoid bulk toward female averages - each deltoid is scaled radially toward
    the humeral axis near the shoulder (keeps its attachments on clavicle/acromion/humerus roughly in
    place) by `factor`; the later containment keeps a subcutaneous gap under the skin."""
    hum = {s: next((m['pos'] for m in M.values() if m['name'] == f'{w} humerus'), None) for s, w in (('L', 'Left'), ('R', 'Right'))}
    n = 0
    for m in M.values():
        if not re.search(r'deltoid', m['name'], re.I):
            continue
        s = 'L' if m['pos'][:, 0].mean() > 0 else 'R'
        h = hum[s]
        if h is None:
            continue
        top = h[h[:, 1] > h[:, 1].max() - 0.04].mean(0)
        shaft = h[(h[:, 1] < h[:, 1].max() - 0.08) & (h[:, 1] > h[:, 1].max() - 0.16)].mean(0)
        ax = (top - shaft) / np.linalg.norm(top - shaft)
        p = m['pos']
        foot = shaft + np.outer((p - shaft) @ ax, ax)
        m['pos'] = foot + (p - foot) * factor
        n += 1
    report['shoulder_bulk'] = {'deltoid_parts': n, 'radial_factor': factor}


def fit_head_skin(F, M, report, max_scale=1.10):
    """Phase 3: the skull is never deformed to fit the face. Instead the MPFB head skin is scaled up
    uniformly about the skull centre (blended to zero across the neck, between C5 and C3) until the
    rigid head group (bones, teeth, eyes, ears) is inside it with a 3 mm soft-tissue margin."""
    head = [i for i in STATE.get('head_parts', []) if i in M]
    if not head:
        return
    bones = np.vstack([M[i]['pos'] for i in head])
    c = bones.mean(0)
    J = POSE[1]
    y_lo, y_hi = J['neck02']['head'][1], J['neck03']['head'][1] + 0.02
    P0 = F['VH_F_skin']['pos'].copy()
    w = ml.smoothstep(y_lo, y_hi, P0[:, 1])
    k, scale = 1.0, 1.0
    for k in np.arange(1.0, max_scale + 1e-9, 0.01):
        P = P0 + (k - 1.0) * w[:, None] * (P0 - c)
        shell = ml.SkinShell(ml.to_trimesh(P, F['VH_F_skin']['idx']), pitch=0.002)
        frac = float(shell.outside(bones, 0.0).mean())   # bone actually outside the skin
        scale = k
        if frac <= 0.005:
            break
    F['VH_F_skin']['pos'] = P
    report['head_skin_fit'] = {'head_skin_scale': float(scale), 'skull_vertices_within_3mm_of_or_outside_skin': frac}
    log('head skin fit', report['head_skin_fit'])


def rigid_head(M, male, report):
    """The skull is rigid: everything above the neck gets ONE similarity (rotation + translation +
    uniform scale) fitted on the dense head/face skin pairs, blended into the body warp between the
    3rd cervical vertebra and 5 cm above it. The jaw keeps its male (closed) relation to the skull."""
    src, dst = STATE['dense']
    J = POSE[0]['joints']
    y0 = J['C3'][1]
    head = src[:, 1] > y0 + 0.05
    # Eye anchors (weight 40 each): male eyeball centres (sclera) -> MPFB eye joints, so the eyes sit
    # in the parametric face's palpebral openings rather than being pushed in by the skin.
    eyes_m = [male[pid]['pos'].mean(0) for pid, m in M.items() if m['name'] in ('Left sclera', 'Right sclera')]
    names_eye = [m['name'] for pid, m in M.items() if m['name'] in ('Left sclera', 'Right sclera')]
    if POSE[1] is None:                 # VHF body: no rig eye joints - fit on the head skin pairs only
        eyes_m, names_eye = [], []
    eyes_f = [POSE[1]['eye.L' if n.startswith('Left') else 'eye.R']['head'] for n in names_eye]
    S = np.vstack([src[head]] + [e[None] for e in eyes_m]) if eyes_m else src[head]
    D = np.vstack([dst[head]] + [np.asarray(e)[None] for e in eyes_f]) if eyes_f else dst[head]
    W = np.r_[np.ones(int(head.sum())), np.full(len(eyes_m), 40.0)]
    s, R, t = ml.umeyama(S, D, W)
    resid = np.linalg.norm(ml.apply_similarity(src[head], s, R, t) - dst[head], axis=1)
    # The mandible (and teeth, tongue, floor of mouth) sit low; any part whose centroid lies in the
    # box of the male cranium + mandible (+5 mm) belongs to the rigid head as well.
    skull = np.vstack([male[pid]['pos'] for pid, m in M.items()
                       if m['system'] == 'skeletal' and male[pid]['pos'][:, 1].mean() > y0 + 0.04] +
                      [male[pid]['pos'] for pid, m in M.items() if m['name'] == 'Mandible'])
    box_lo, box_hi = skull.min(0) - 0.005, skull.max(0) + 0.005
    STATE['head_parts'] = []
    STATE['head_all'] = []
    n = 0
    for pid, m in M.items():
        p = male[pid]['pos']
        c = p.mean(0)
        in_skull_box = bool(np.all(c > box_lo) and np.all(c < box_hi))
        if (p[:, 1].mean() > y0 + 0.04 or in_skull_box) and np.ptp(p[:, 1]) < 0.3:
            w = np.ones(len(p))              # a head part (skull, mandible, teeth, eye, ear): fully rigid
            STATE.setdefault('head_all', []).append(pid)
            if m['system'] in ('skeletal', 'sensory'):
                STATE.setdefault('head_parts', []).append(pid)
        else:
            # One weight per part (from its centroid): a structure crossing the blend band moves as a
            # whole and is never stretched internally.
            w = np.full(len(p), ml.smoothstep(y0, y0 + 0.05, p[:, 1].mean()))
        if w.max() < 1e-3:
            continue
        m['pos'] = m['pos'] * (1 - w[:, None]) + ml.apply_similarity(p, s, R, t) * w[:, None]
        n += 1
    report['rigid_head'] = {'scale': float(s), 'pairs': int(head.sum()), 'residual_mm_median': float(np.median(resid) * 1000), 'parts': n}
    log('rigid head', report['rigid_head'])

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
WORK = ROOT / 'work' / 'female'
OUT = ROOT / 'public' / 'models' / 'female'

SOURCES = {
    'bp3d': {'name': 'BodyParts3D 4.0', 'author': 'Database Center for Life Science (DBCLS)', 'license': 'CC BY 4.0',
             'url': 'https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html'},
    'hra': {'name': 'HRA 3D Reference Organ Set for Female v1.5', 'author': 'Kristen Browne, Heidi Schlehlein; Human Reference Atlas / HuBMAP',
            'license': 'CC BY 4.0', 'url': 'https://doi.org/10.48539/HBM352.BTSQ.586'},
    'mpfb': {'name': 'MPFB2 / MakeHuman (parametric body)', 'author': 'MakeHuman Community (Joel Palmius et al.)',
             'license': 'CC0 1.0 (MakeHuman assets); the GPL-3 MPFB2 add-on is used only as a tool',
             'url': 'https://static.makehumancommunity.org/mpfb.html'},
    'generated': {'name': 'Generated for Human Atlas (schematic)', 'author': 'Human Atlas contributors', 'license': 'CC BY 4.0',
                  'url': 'https://github.com/ashemag/human-atlas/blob/main/DATA_SOURCES.md'},
}
# Provenance label shown in the UI badge for every structure.
ACCURACY_NOTES = {
    'scan-derived': 'Scan-derived geometry (HRA / Visible Human Female), in its native position and scale.',
    'warped': 'Warped approximation: BodyParts3D male geometry carried into the female body by a landmark thin-plate-spline warp.',
    'generated': 'Generated / schematic, not scan-derived: built from reference dimensions in anatomy texts.',
}
HRA_SOFT = re.compile(r'ligament|mesosalpinx|mesovarium|uterine_(artery|vein)|uterovesical')
LEVATOR = re.compile(r'pubococcygeus|puborectalis|iliococcygeus|coccygeus|sphincter|perineal|levator', re.I)
HRA_PELVIS = {'hip_L': ['VH_F_ilium_compact_bone_L', 'VH_F_ischium_compact_bone_L', 'VH_F_pubis_compact_bone_L'],
              'hip_R': ['VH_F_ilium_compact_bone_R', 'VH_F_ischium_compact_bone_R', 'VH_F_pubis_compact_bone_R'],
              'sacrum': ['VH_F_sacrum']}
MALE_REPLACED = {  # BodyParts3D element -> HRA replacement (concept membership is transferred)
    'FJ3288': HRA_PELVIS['hip_L'], 'FJ3152': HRA_PELVIS['hip_R'], 'FJ3393': HRA_PELVIS['sacrum'],
    'FJ2810': ['female_skin'],
}
MALE_DROPPED = {'FJ2812': 'Eyebrow (male surface detail; the female body surface replaces the head surface)',
                'FJ2813': 'Hair of head (male hairstyle; not part of the female body surface)',
                'FJ2814': 'Lip (surface detail of the male skin; the female body surface has lips)'}


def log(*a):
    print(*a, flush=True)


# ============================================================== inputs

def load_inputs(args, cfg):
    atlas, male = ml.load_package(ROOT / 'public' / 'models' / 'atlas.json')
    doc, hra_parts, _ = ml.read_glb(args.hra)
    names = {i: n.get('name', '') for i, n in enumerate(doc['nodes'])}
    for p in hra_parts:
        p['ancestor_names'] = [names[a] for a in p['ancestors']]
    return atlas, male, {p['name']: p for p in hra_parts}


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
        elif p['id'] in MALE_REPLACED:
            removed[p['id']] = 'replaced by the real HRA female structure: ' + ', '.join(MALE_REPLACED[p['id']])
        elif p['id'] in MALE_DROPPED:
            removed[p['id']] = 'dropped: ' + MALE_DROPPED[p['id']]
        elif STATE.get('body') == 'hybrid' and (p['system'] == 'cardiac' or BP3D_REPLACED_HYBRID.search(p['name'])):
            removed[p['id']] = 'replaced by the real HRA Visible Human Female organ / bone (hybrid body)'
    return removed


def hra_selected(hra):
    """name -> (system, group) for every HRA structure used."""
    out = {}
    for name, p in hra.items():
        anc = p['ancestor_names']
        if STATE.get('body') == 'hybrid':
            hit = next((HRA_HYBRID[a] for a in [name] + anc if a in HRA_HYBRID), None)
            if hit:
                out[name] = hit
                continue
        if name == 'VH_F_skin':
            out[name] = ('integumentary', 'skin')
        elif 'VH_F_lungs' in anc:
            # BodyParts3D has bronchial trees but no lung tissue; the HRA bronchopulmonary
            # segments and hila (Visible Human Female) are real.
            out[name] = ('respiratory', 'thorax')
        elif 'VH_F_reproductive_system' in anc and 'VH_F_placenta' not in anc and name != 'VH_F_placenta':
            # Peritoneal pouches are serosa (connective), not organ: they must not hide the bladder.
            # Peritoneal pouches and the uterine/ovarian ligaments (broad, round, cardinal, uterosacral,
            # mesosalpinx/mesovarium) are fibrous/serous connective tissue; the broad ligament (14 x 12 cm)
            # otherwise hides the bladder and uterus in every front view.
            soft = re.search(r'pouch|ligament|mesosalpinx|mesovarium', name)
            out[name] = ('connective' if soft else 'reproductive', 'pelvic')
        elif 'VH_F_urinary_bladder' in anc:
            out[name] = ('urinary', 'pelvic')
        elif 'VH_F_blood_vasculature_of_uterus' in anc:
            out[name] = ('venous' if 'vein' in name else 'arterial', 'pelvic')
        elif name == 'VH_F_coccyx' or any(name in v for v in HRA_PELVIS.values()):
            out[name] = ('skeletal', 'pelvis')
        elif 'VH_F_mammary_gland' in anc:
            if any(k in name for k in ('nipple', 'areola')):
                system = 'integumentary'
            elif 'suspensory' in name or 'fat' in name:
                system = 'connective'          # Cooper's ligaments (the HRA fat itself is replaced)
            elif 'lactiferous' in name:
                system = 'lactiferous'         # ducts and sinuses: own colour
            else:
                system = 'mammary'             # glandular lobes: pinkish-white
            out[name] = (system, 'breast_' + ('L' if name.endswith('_L') else 'R'))
    return out


# ============================================================== frame and warp

def hra_frame(hra):
    """Translate HRA so the feet rest on y = 0 and the body is centred in z (no scaling)."""
    s = hra['VH_F_skin']['pos']
    return np.array([0.0, -s[:, 1].min(), -(s[:, 2].min() + s[:, 2].max()) / 2])


def build_warp(atlas, male, hra, shift, report):
    import trimesh
    by_name = {p['name']: p['id'] for p in atlas['parts']}
    mpos = lambda name: male[by_name[name]]['pos']
    hpos = lambda n: hra[n]['pos'] + shift
    m_skin = ml.to_trimesh(male['FJ2810']['pos'], male['FJ2810']['idx'])
    pos, nrm, idx = ml.weld(hra['VH_F_skin']['pos'] + shift, hra['VH_F_skin']['nrm'], hra['VH_F_skin']['idx'])
    f_skin = trimesh.Trimesh(pos, idx.reshape(-1, 3), process=False)
    C = bw.Correspondences()
    # Skeleton: pelvis (real female) and lower limbs (real female bones).
    m_hl, _ = ml.femoral_head_centre(mpos('Left femur')); m_hr, _ = ml.femoral_head_centre(mpos('Right femur'))
    f_hl, _ = ml.femoral_head_centre(hpos('VH_F_femur_L')); f_hr, _ = ml.femoral_head_centre(hpos('VH_F_femur_R'))
    lm_pm = ml.pelvis_landmarks(mpos('Left hip bone'), mpos('Right hip bone'), mpos('Sacrum'), m_hl, m_hr)
    fh = {k: np.vstack([hpos(n) for n in v]) for k, v in HRA_PELVIS.items()}
    lm_pf = ml.pelvis_landmarks(fh['hip_L'], fh['hip_R'], fh['sacrum'], f_hl, f_hr)
    keys = sorted(set(lm_pm) & set(lm_pf))
    C.add(np.array([lm_pm[k] for k in keys]), np.array([lm_pf[k] for k in keys]), 'pelvis')
    names_m = {s: {'femur': f'{w} femur', 'tibia': f'{w} tibia', 'fibula': f'{w} fibula', 'patella': f'{w} patella'}
               for s, w in (('L', 'Left'), ('R', 'Right'))}
    names_f = {s: {'femur': f'VH_F_femur_{s}', 'tibia': f'VH_F_tibia_{s}', 'fibula': f'VH_F_fibula_{s}', 'patella': f'VH_F_patella_{s}'}
               for s in 'LR'}
    bm = bw.bone_points(mpos, names_m['L'], names_m['R'])
    bf = bw.bone_points(hpos, names_f['L'], names_f['R'])
    # v3: dense surface pairs through the MPFB male / flat-female pair (identical topology) and the
    # rig joints (both bodies already posed like the male, so no large rotation is left to the spline).
    ds, dd, dtags, dinfo = bt.dense_correspondences(m_skin, POSE[0])
    dtags = np.array(dtags)
    for t in ('skin-dense', 'rig-joints'):
        C.add(ds[dtags == t], dd[dtags == t], t)
    report['dense'] = dinfo
    STATE['dense'] = (ds[dtags == 'skin-dense'], dd[dtags == 'skin-dense'])
    # Body levels.
    lm_m, lm_f = bw.body_levels(m_skin), bw.body_levels(f_skin)
    lm_m['ankle'] = (bm['tib_bottom_L'][1] + bm['tib_bottom_R'][1]) / 2
    lm_f['ankle'] = (POSE[1]['foot.L']['head'][1] + POSE[1]['foot.R']['head'][1]) / 2
    # Thorax: ribs 5/8/10 lateral extremes <-> HRA lung lateral extremes + rib thickness (12 mm).
    lungs = np.vstack([hpos(n) for n, p in hra.items() if 'VH_F_lungs' in p['ancestor_names']])
    for word in ('fifth', 'eighth', 'tenth'):
        for side, sign in (('Left', 1), ('Right', -1)):
            rib = mpos(f'{side} {word} rib')
            pm = rib[np.argmax(rib[:, 0] * sign)]
            frac = (pm[1] - lm_m['crotch']) / (lm_m['axilla'] - lm_m['crotch'])
            yf = lm_f['crotch'] + frac * (lm_f['axilla'] - lm_f['crotch'])
            band = lungs[(np.abs(lungs[:, 1] - yf) < 0.01) & (np.sign(lungs[:, 0]) == sign)]
            if len(band) < 10:
                continue
            pf = band[np.argmax(band[:, 0] * sign)].copy()
            pf[0] += 0.012 * sign
            # v3: not added - with dense skin pairs these rib->lung pairs fought the skin on the
            # lateral chest wall and stretched the intercostals (stretch gate).
    src, dst = C.arrays()
    # Remove near-duplicate sources (would make the spline ill-conditioned).
    _, uniq = np.unique(np.round(src, 4), axis=0, return_index=True)
    uniq = np.sort(uniq)
    src, dst = src[uniq], dst[uniq]
    tags = np.array(C.tags)[uniq]
    warp = bw.tps(src, dst, smoothing=1e-3)  # v3: regularised
    resid = np.linalg.norm(warp(src) - dst, axis=1) * 1000
    report['warp'] = {'correspondences': int(len(src)), 'by_group': {t: int((tags == t).sum()) for t in sorted(set(tags))},
                      'residual_mm_mean': float(resid.mean()), 'residual_mm_max': float(resid.max()),
                      'levels_male': {k: float(v) for k, v in lm_m.items() if np.isscalar(v)},
                      'levels_female': {k: float(v) for k, v in lm_f.items() if np.isscalar(v)}}
    log('warp', json.dumps(report['warp']))
    np.savez(WORK / 'correspondences.npz', src=src, dst=dst, tags=tags)
    return warp, f_skin, lm_pf, (m_hl, m_hr, f_hl, f_hr), bm, bf, lm_m, lm_f


def _min_rotation(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = a @ b; s = np.linalg.norm(v)
    if s < 1e-9:
        return np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * ((1 - c) / s ** 2)


HAND_BONE_RE = re.compile(r'carp|metacarp|phalan.*(finger|thumb)|(finger|thumb).*phalan|scaphoid|lunate|triquetr|pisiform|trapezi|capitate|hamate|sesamoid.*hand', re.I)


def articulated_arms(M, male, atlas, hra, shift, report):
    """Arms change pose (male hanging -> female A-pose), which a smooth warp shears. Upper arm,
    forearm and hand are therefore moved as rigid segments about the male shoulder, elbow and wrist
    (from the humerus and radius), mapped to the same arc-length positions on the female arm axis
    (skin sections), blended over ±2 cm at each joint and into the body warp at the shoulder."""
    import trimesh
    by_name = {p['name']: p['id'] for p in atlas['parts']}
    m_skin = ml.to_trimesh(male['FJ2810']['pos'], male['FJ2810']['idx'])
    p, _, i = ml.weld(hra['VH_F_skin']['pos'] + shift, hra['VH_F_skin']['nrm'], hra['VH_F_skin']['idx'])
    f_skin = trimesh.Trimesh(p, i.reshape(-1, 3), process=False)
    lm_m, lm_f = bw.body_levels(m_skin), bw.body_levels(f_skin)
    out = {}
    fshell = [None]; hand_fit = []

    def arc(poly):
        return np.r_[0, np.cumsum(np.linalg.norm(np.diff(poly, axis=0), axis=1))]

    def at(poly, s):
        t = arc(poly)
        return np.array([np.interp(s, t, poly[:, k]) for k in range(3)])

    def param(poly, q):
        """Arc-length of the point of `poly` nearest to q, and the distance."""
        best = (np.inf, 0.0)
        t = arc(poly)
        for k in range(len(poly) - 1):
            a, b = poly[k], poly[k + 1]
            d = b - a; L = np.linalg.norm(d)
            u = np.clip((q - a) @ d / (L * L), 0, 1)
            dist = np.linalg.norm(a + u * d - q)
            if dist < best[0]:
                best = (dist, t[k] + u * L)
        return best[1], best[0]

    def param_many(poly, q):
        """Vectorised arc-length parameter of the nearest polyline point for many points."""
        t = arc(poly)
        a, b = poly[:-1], poly[1:]
        d = b - a; L2 = (d * d).sum(1)
        u = np.clip(((q[:, None, :] - a[None]) * d[None]).sum(2) / L2[None], 0, 1)
        proj = a[None] + u[..., None] * d[None]
        dist = np.linalg.norm(proj - q[:, None, :], axis=2)
        k = dist.argmin(1)
        return t[k] + u[np.arange(len(q)), k] * np.sqrt(L2[k])

    for sign, side, word in ((1, 'L', 'Left'), (-1, 'R', 'Right')):
        sm, sf = bw.arm_stations(m_skin, lm_m, sign), bw.arm_stations(f_skin, lm_f, sign)
        cm, cf = sm[::5], sf[::5]                 # station centroids = arm axis polylines
        hum = male[by_name[f'{word} humerus']]['pos']
        rad = male[by_name[f'{word} radius']]['pos']
        shoulder, _ = ml.femoral_head_centre(hum)  # sphere fit of the top of the humerus
        elbow = hum[np.argsort(np.linalg.norm(hum - shoulder, axis=1))[-200:]].mean(0)
        far = np.argsort(np.linalg.norm(rad - elbow, axis=1))[-150:]
        wrist = rad[far].mean(0)
        tip = cm[-1]
        # Joint arc-length fractions on the male axis -> same fractions on the female axis.
        Lm, Lf = arc(cm)[-1], arc(cf)[-1]
        sE, _ = param(cm, elbow); sW, _ = param(cm, wrist)
        E_f, W_f, T_f = at(cf, sE / Lm * Lf), at(cf, sW / Lm * Lf), cf[-1]
        S_m = cm[0]; S_f = cf[0]
        joints_m = [S_m, at(cm, sE), at(cm, sW), tip]
        joints_f = [S_f, E_f, W_f, T_f]
        Rs, ts = [], []
        chain = STATE.get('body') == 'hybrid'
        sc = Lf / Lm if chain else 1.0
        P = joints_f[0]
        seg_scale = []
        for k in range(3):
            R = _min_rotation(joints_m[k + 1] - joints_m[k], joints_f[k + 1] - joints_f[k])
            if chain and k == 2:
                # Milestone 7: the hand is CHAINED to the forearm at the bone wrist (distal radius), so
                # the carpals stay on the radius (no radius/ulna-carpal gap). Upper arm and forearm keep
                # their own segment transforms (chaining from the skin-estimated elbow displaced them).
                # Rotation about the wrist (roll, flexion, deviation) searched so the male hand bones lie
                # inside her real skin hand as far as a rigid hand can.
                from scipy.spatial.transform import Rotation as Rot
                if fshell[0] is None:
                    fshell[0] = ml.SkinShell(f_skin)
                hb = np.vstack([male[q]['pos'] for q, mm in M.items() if mm['system'] == 'skeletal'
                                and HAND_BONE_RE.search(mm['name']) and np.sign(male[q]['pos'][:, 0].mean()) == sign])[::3]
                Wf = Rs[1] @ wrist + ts[1]
                ax = (joints_f[3] - joints_f[2]); ax /= np.linalg.norm(ax)
                best = (np.inf, R)
                for roll in range(-90, 91, 15):
                    for flex in range(-30, 31, 10):
                        for dev in range(-30, 31, 10):
                            Rx = Rot.from_rotvec(ax * np.radians(roll)).as_matrix() @ Rot.from_euler('xz', [flex, dev], degrees=True).as_matrix()
                            Rc = Rx @ R
                            q = (Rc @ (hb - wrist).T).T + Wf
                            o = int(fshell[0].outside(q, 0.002).sum())
                            if o < best[0]:
                                best = (o, Rc)
                R = best[1]
                hand_fit.append(best[0])
                ts.append(Wf - R @ wrist); Rs.append(R)
            else:
                ts.append(joints_f[k] - R @ joints_m[k]); Rs.append(R)
            seg_scale.append(1.0)
        bounds = [0.0, sE, sW, Lm]
        moved = 0; checked = 0; straps = []
        for pid, m in M.items():
            src = male[pid]['pos']
            c = src.mean(0)
            if np.sign(c[0]) != sign:
                continue
            s_c, d_c = param(cm, c)
            hand_bone = chain and m['system'] == 'skeletal' and HAND_BONE_RE.search(m['name'])
            if (d_c > 0.06 or s_c <= 0.0) and not hand_bone:
                continue                              # not an arm part (torso, thigh)
            s_v = param_many(cm, src)
            if chain and m['system'] == 'skeletal' and (s_c > 0.08 or hand_bone):
                # a bone is never split between segments: the whole bone follows the segment of its centroid
                k = 2 if hand_bone else min(max(int(np.searchsorted(bounds, s_c) - 1), 0), 2)
                m['pos'] = (Rs[k] @ src.T).T + ts[k]
                m['arm_segment'] = k
                moved += 1
                continue
            new = np.zeros_like(src); wsum = np.zeros(len(src))
            for k in range(3):
                lo, hi = bounds[k], bounds[k + 1]
                w = ml.smoothstep(lo - 0.02, lo + 0.02, s_v) * (1 - ml.smoothstep(hi - 0.02, hi + 0.02, s_v))
                if k == 0:
                    w = 1 - ml.smoothstep(hi - 0.02, hi + 0.02, s_v)
                if k == 2:
                    w = ml.smoothstep(lo - 0.02, lo + 0.02, s_v)
                new += w[:, None] * ((Rs[k] @ src.T).T + ts[k]); wsum += w
            new /= np.maximum(wsum, 1e-9)[:, None]
            near_shoulder = 1 - ml.smoothstep(0.02, 0.08, s_v)   # blend into the body warp proximally
            m['pos'] = m['pos'] * near_shoulder[:, None] + new * (1 - near_shoulder)[:, None]
            if chain and m['system'] == 'muscular' and s_c > sE - 0.03:
                # forearm / hand muscle: length (principal extent) must stay within 10 % of male x arm scale
                ax = np.linalg.svd(src - src.mean(0), full_matrices=False)[2][0]
                k0 = min(max(int(np.searchsorted(bounds, s_c) - 1), 0), 2)
                L0 = np.ptp(src @ ax) * seg_scale[k0]
                L1 = np.ptp(m['pos'] @ np.linalg.svd(m['pos'] - m['pos'].mean(0), full_matrices=False)[2][0])
                if abs(L1 / max(L0, 1e-9) - 1) > 0.10:
                    k = int(np.searchsorted(bounds, s_c) - 1); k = min(max(k, 0), 2)
                    m['pos'] = (Rs[k] @ src.T).T + ts[k]      # re-fit: carried whole by its segment
                    straps.append(m['name'])
                checked += 1
            moved += 1
        out[side] = {'parts': moved, 'hand_bone_samples_outside_after_search': hand_fit[-1] if hand_fit else None, 'forearm_hand_muscles_checked': checked,
                     'straps_refit': straps, 'joint_fractions': [float(sE / Lm), float(sW / Lm)],
                     'female_joints': [j.tolist() for j in joints_f]}
    report['articulated_arms'] = out
    log('articulated arms', {k: v['parts'] for k, v in out.items()})


def rigid_hands(M, male, hra, shift, report):
    """Hands are carried rigidly (rotation + translation, Umeyama on the distal arm stations) and
    blended into the thin-plate warp across the wrist, so the small hand bones are not crumpled
    by the change from the male's hanging pose to the female's abducted A-pose."""
    import trimesh
    m_skin = ml.to_trimesh(male['FJ2810']['pos'], male['FJ2810']['idx'])
    p, n_, i = ml.weld(hra['VH_F_skin']['pos'] + shift, hra['VH_F_skin']['nrm'], hra['VH_F_skin']['idx'])
    f_skin = trimesh.Trimesh(p, i.reshape(-1, 3), process=False)
    lm_m, lm_f = bw.body_levels(m_skin), bw.body_levels(f_skin)
    out = {}
    for sign, side in ((1, 'L'), (-1, 'R')):
        sm, sf = bw.arm_stations(m_skin, lm_m, sign), bw.arm_stations(f_skin, lm_f, sign)
        k = 4 * 5                       # last 4 stations x (centroid + 4 rays)
        s, R, _ = ml.umeyama(sm[-k:], sf[-k:])
        # Rigid (native hand size): rotation from the fit, translation matching the centroids.
        t = sf[-k:].mean(0) - R @ sm[-k:].mean(0)
        wrist_m = sm[-k]
        hand_c = sm[-k:].mean(0)
        # Also exclude anything closer to the thigh skin axis than to the hand (thigh vertices).
        axis = sm[-5] - sm[-k]; axis /= np.linalg.norm(axis)
        moved = 0
        for pid, m in M.items():
            src = male[pid]['pos']
            u = (src - wrist_m) @ axis
            # Only the hand itself: past the wrist AND within 12 cm of the male hand centroid
            # (the hanging male hand lies beside the thigh, which must not move with it).
            near_hand = 1 - ml.smoothstep(0.10, 0.13, np.linalg.norm(src - hand_c, axis=1))
            w = ml.smoothstep(-0.03, 0.01, u) * near_hand * (np.sign(src[:, 0]) == sign)
            if w.max() < 1e-3:
                continue
            rig = ml.apply_similarity(src, 1.0, R, t)
            m['pos'] = m['pos'] * (1 - w[:, None]) + rig * w[:, None]
            moved += 1
        out[side] = {'parts_blended': moved, 'fit_scale_ignored': float(s)}
    report['rigid_hands'] = out
    log('rigid hands', out)


# ============================================================== HRA placement

def place_hra(hra, selected, shift):
    out = {}
    for name, (system, group) in selected.items():
        p = hra[name]
        pos, nrm, idx = ml.weld(p['pos'], p['nrm'], p['idx'])
        out[name] = {'pos': pos + shift, 'nrm': nrm, 'idx': idx, 'system': system, 'group': group, 'hra': p}
    return out


def seal_uterus(F, report, tol=0.0025):
    """Close cracks between uterine pieces: vertices of a piece lying within `tol` of a
    neighbouring piece are projected onto it, so body, segment and cervix meet without gaps."""
    import trimesh
    names = [n for n in F if re.search(r'body_of_uterus|fundus_of_uterus|lower_uterine_segment|cervix$|cornua|wall_of_uterus', n)]
    moved = {}
    for a in names:
        pa = F[a]['pos']
        for b in names:
            if a == b:
                continue
            tb = ml.to_trimesh(F[b]['pos'], F[b]['idx'])
            lo, hi = tb.bounds
            sel = np.where(np.all((pa > lo - tol) & (pa < hi + tol), axis=1))[0]
            if not len(sel):
                continue
            c, d, _ = trimesh.proximity.closest_point(tb, pa[sel])
            near = (d > 1e-6) & (d < tol)
            if near.any():
                pa[sel[near]] = c[near]
                moved[f'{a}->{b}'] = int(near.sum())
        F[a]['pos'] = pa
    for n in names:
        F[n]['seal'] = True
    report['uterus_seal'] = moved


# ============================================================== collisions

def overlaps(a_lo, a_hi, b_lo, b_hi, pad=0.0):
    return bool(np.all(a_lo - pad <= b_hi) and np.all(b_lo - pad <= a_hi))


def survey(movers, fixed, label):
    hits = []
    for mn, (mp, mi) in movers.items():
        lo, hi = mp.min(0), mp.max(0)
        a = None
        for fn, (fp, fi) in fixed.items():
            if fn == mn or not overlaps(lo, hi, fp.min(0), fp.max(0)):
                continue
            a = a or ml.to_trimesh(mp, mi)
            if ml.collides(a, ml.to_trimesh(fp, fi)):
                hits.append((mn, fn))
    log(f'[{label}] {len(hits)} intersecting pairs')
    return hits


def union_mesh(items):
    import trimesh
    return trimesh.util.concatenate([ml.to_trimesh(p, i) for p, i in items])


def away(pos, centre, radius=0.06):
    near_pts = pos[np.linalg.norm(pos - centre, axis=1) < radius]
    d = (near_pts.mean(0) if len(near_pts) else pos.mean(0)) - centre
    return d if np.linalg.norm(d) > 1e-6 else np.array([0, 1.0, 0])


def connect_ureters(F, M, report):
    out = {}
    for side, uid in (('L', 'FJ3144'), ('R', 'FJ3146')):
        u = M[uid]['pos']
        word, sign = ('Left', 1) if side == 'L' else ('Right', -1)
        orifice = F['VH_F_ureteral_orifice_' + side]['pos'].mean(0)
        bladder = F['VH_F_fundus_of_urinary_bladder_base']['pos']
        outward = orifice - bladder.mean(0); outward[1] = 0; outward /= np.linalg.norm(outward)
        target = orifice + outward * 0.006
        # Pelvic course (Gray's): the ureter crosses ANTERIOR to the common iliac bifurcation at the
        # pelvic brim, runs down the lateral pelvic wall in front of the internal iliac vessels, then
        # turns medially to the bladder. It never approaches the midline.
        cia = next(m['pos'] for m in M.values() if m['name'] == f'{word} common iliac artery')
        bif = cia[np.argmin(cia[:, 1])]
        brim = bif + np.array([0, 0.004, 0.009])
        brim[0] = sign * max(abs(brim[0]), 0.045)
        hip = np.vstack([F[n]['pos'] for n in HRA_PELVIS['hip_' + side]])
        ym = (brim[1] + target[1]) / 2
        band = hip[(np.abs(hip[:, 1] - ym) < 0.012) & (hip[:, 0] * sign > 0.03)]
        wall_x = sign * (np.abs(band[:, 0]).min() - 0.012) if len(band) else brim[0]
        wall = np.array([wall_x, ym, min(brim[2], target[2]) - 0.008])
        ctrl = np.array([brim, wall, target])
        # Centreline of the warped ureter by height; vertices below the brim follow the new curve.
        ys = np.linspace(u[:, 1].min(), u[:, 1].max(), 60)
        cen = np.array([u[np.abs(u[:, 1] - y) < 0.006].mean(0) if (np.abs(u[:, 1] - y) < 0.006).any() else [np.nan] * 3 for y in ys])
        ok = ~np.isnan(cen[:, 0])
        cx = lambda y: np.c_[np.interp(y, ys[ok], cen[ok, 0]), y, np.interp(y, ys[ok], cen[ok, 2])]
        below = u[:, 1] < brim[1] + 0.03
        y_top = brim[1] + 0.03; y_end = u[:, 1].min()
        t = np.clip((y_top - u[:, 1]) / (y_top - y_end), 0, 1)
        # Catmull-like quadratic path: top (on the old centreline) -> brim -> wall -> target.
        top = cx(np.array([y_top]))[0]
        knots = np.array([top, brim, wall, target])
        seg = np.linspace(0, 1, len(knots))
        path = np.stack([np.interp(t, seg, knots[:, k]) for k in range(3)], 1)
        offset = u - cx(u[:, 1])
        new = path + offset
        blend = ml.smoothstep(0.0, 0.25, t)[:, None]
        u2 = u.copy()
        u2[below] = (u * (1 - blend) + new * blend)[below]
        # Smooth the polyline corners a little (Laplacian on vertex positions by height order).
        M[uid]['pos'] = u2
        out[side] = {'brim': brim.tolist(), 'lateral_wall': wall.tolist(), 'end_gap_mm': float(np.linalg.norm(u2[np.argmin(u2[:, 1])] - target) * 1000),
                     'min_abs_x_mm': float(np.abs(u2[:, 0]).min() * 1000)}
    report['ureter_connection'] = out


def resolve_collisions(F, M, report):
    """Make room for the real female organs: bowel, ureters, vessels, nerves and the levator ani
    give way to convex hulls of the uterus, vagina, bladder and adnexa (exact inside test);
    thin HRA sheets stay in front of the sacrum and medial to the hip bones."""
    import trimesh
    stats, room = {}, {}
    pel = [f for f in F.values() if f['group'] in ('pelvic', 'pelvis')]
    lo = np.min([f['pos'].min(0) for f in pel], 0) - 0.02
    hi = np.max([f['pos'].max(0) for f in pel], 0) + 0.02
    near = lambda m: overlaps(m['pos'].min(0), m['pos'].max(0), lo, hi)
    sac = np.vstack([F[n]['pos'] for n in HRA_PELVIS['sacrum'] + ['VH_F_coccyx']])
    hip_l = np.vstack([F[n]['pos'] for n in HRA_PELVIS['hip_L']])
    hip_r = np.vstack([F[n]['pos'] for n in HRA_PELVIS['hip_R']])
    for n, f in F.items():
        if f['group'] != 'pelvic' or not HRA_SOFT.search(n):
            continue
        p, d0 = ml.clamp_heightfield(f['pos'], sac, axis=2, sign=1, reach=0.04)
        d1 = d2 = 0.0
        if 'round_ligament' not in n:
            left, right = p[:, 0] > 0, p[:, 0] <= 0
            p[left], d1 = ml.clamp_heightfield(p[left], hip_l, axis=0, sign=-1, reach=0.03)
            p[right], d2 = ml.clamp_heightfield(p[right], hip_r, axis=0, sign=1, reach=0.03)
        if max(d0, d1, d2) > 0:
            f['pos'] = p
            stats[n] = max(d0, d1, d2) * 1000
    groups = {
        'uterus': lambda n: re.search(r'uterus|cornua|cervi|uterine_segment|cervical_os', n) and not HRA_SOFT.search(n),
        'vagina': lambda n: 'vagina' in n,
        'bladder': lambda n: 'bladder' in n or 'trigone' in n or 'ureteral_orifice' in n,
        'adnexa_L': lambda n: (n.endswith('_L') and re.search(r'tube|fibria|infundibulum|ampulla|isthmus|mesosalpinx|mesovarium|ovarian', n)) or n == 'VH_F_left_ovary',
        'adnexa_R': lambda n: (n.endswith('_R') and re.search(r'tube|fibria|infundibulum|ampulla|isthmus|mesosalpinx|mesovarium|ovarian', n)) or n == 'VH_F_right_ovary',
        'coccyx': lambda n: n == 'VH_F_coccyx',
    }
    hulls = {g: trimesh.convex.convex_hull(np.vstack([f['pos'] for n, f in F.items() if test(n)])) for g, test in groups.items()}
    vag = F['VH_F_vagina']['pos']; vc = vag.mean(0)
    _, _, vt = np.linalg.svd(vag - vc, full_matrices=False)
    for i, m in M.items():
        if not near(m):
            continue
        sling = bool(LEVATOR.search(m['name'])) or m['system'] in ('venous', 'arterial', 'nervous')
        if not (sling or m['system'] in ('digestive', 'urinary', 'lymphatic')):
            continue
        pos, d, _ = ml.push_out_convex(m['pos'], [h for g, h in hulls.items() if g != 'coccyx' or m['system'] == 'digestive'],
                                       margin=0.0015, radius=0.014)
        if d > 1e-5:
            m['pos'] = pos; stats[i] = d * 1000
        for g, hull in hulls.items():
            a = ml.to_trimesh(m['pos'], m['idx'])
            if not overlaps(a.bounds[0], a.bounds[1], hull.bounds[0], hull.bounds[1]) or not ml.collides(a, hull):
                continue
            cap = 0.04 if m['system'] == 'digestive' else 0.025
            if sling and g == 'vagina':
                pos, amp, ok = ml.make_room(m['pos'], m['idx'], hull, axis_point=vc, axis_dir=vt[0], sigma=0.02, max_amp=cap)
            else:
                pos, amp, ok = ml.make_room(m['pos'], m['idx'], hull, direction=away(m['pos'], hull.centroid), sigma=0.035, max_amp=cap)
            if ok and amp > 0:
                m['pos'] = pos; stats[i] = max(stats.get(i, 0), amp * 1000)
            room[f'{i} vs {g}'] = {'amplitude_mm': amp * 1000, 'clean': ok}
    report['make_room'] = room
    report['collision_resolution_max_displacement_mm'] = stats
    log('resolved', len(stats), 'structures')


def soft_tissue_off_pelvis(F, M, report):
    """Warped male muscles, vessels and nerves that attach to or pass the pelvis are pushed onto
    the surface of the real HRA pelvic bones instead of cutting into them."""
    out = {}
    bones = {n: ml.to_trimesh(F[n]['pos'], F[n]['idx']) for v in HRA_PELVIS.values() for n in v}
    bones['VH_F_coccyx'] = ml.to_trimesh(F['VH_F_coccyx']['pos'], F['VH_F_coccyx']['idx'])
    for i, m in M.items():
        if m['system'] == 'skeletal':
            continue
        for n, b in bones.items():
            if not overlaps(m['pos'].min(0), m['pos'].max(0), b.bounds[0], b.bounds[1]):
                continue
            a = ml.to_trimesh(m['pos'], m['idx'])
            if not ml.collides(a, b):
                continue
            m['pos'], d = ml.push_out(m['pos'], b, margin=0.0008, radius=0.008, iterations=5)
            out[f'{i} vs {n}'] = d * 1000
    report['soft_tissue_off_pelvis_mm'] = out
    log('soft tissue off pelvis', len(out))


def chest_and_breasts(F, M, report):
    """Glands and adipose sit on pectoralis major: push the warped chest wall muscles out of each
    breast's adipose body, posteriorly; whatever chest-wall structure still intersects the breast
    (ribs, costal cartilages, vessels, liver at the costal margin) moves the breast body forward."""
    import trimesh
    out = {}
    for side in 'LR':
        names = [n for n, f in F.items() if f['group'] == 'breast_' + side]
        box_lo = np.min([F[n]['pos'].min(0) for n in names], 0); box_hi = np.max([F[n]['pos'].max(0) for n in names], 0)
        wall = [ml.to_trimesh(m['pos'], m['idx']) for m in M.values()
                if overlaps(m['pos'].min(0), m['pos'].max(0), box_lo, box_hi) and not re.search(r'pectoralis|serratus|external oblique', m['name'], re.I)]
        if not wall:
            continue
        wall = trimesh.util.concatenate(wall)
        fat = [n for n in names if 'fat' in n][0]
        pos, amp, ok = ml.make_room(F[fat]['pos'], F[fat]['idx'], wall, direction=[0, 0, 1], sigma=0.06, step=0.0015, max_amp=0.02)
        if ok and amp > 0:
            # Move the whole breast (glands, ducts, ligaments, nipple) with the adipose body.
            delta = pos - F[fat]['pos']
            shift = np.array([0, 0, float(np.percentile(delta[:, 2], 90))])
            F[fat]['pos'] = pos
            for n in names:
                if n != fat:
                    F[n]['pos'] = F[n]['pos'] + shift
        out[f'breast_{side} forward'] = {'amplitude_mm': amp * 1000, 'clean': ok}
    for side in 'LR':
        fat = [f for n, f in F.items() if f['group'] == 'breast_' + side and 'fat' in n][0]
        hull = trimesh.convex.convex_hull(fat['pos'])
        for i, m in M.items():
            if m['system'] != 'muscular' or not re.search(r'pectoralis|serratus|external oblique|intercostal', m['name'], re.I):
                continue
            a = ml.to_trimesh(m['pos'], m['idx'])
            if not overlaps(a.bounds[0], a.bounds[1], hull.bounds[0], hull.bounds[1]) or not ml.collides(a, ml.to_trimesh(fat['pos'], fat['idx'])):
                continue
            pos, amp, ok = ml.make_room(m['pos'], m['idx'], ml.to_trimesh(fat['pos'], fat['idx']), direction=[0, 0, -1], sigma=0.03, step=0.002, max_amp=0.03)
            if ok and amp > 0:
                m['pos'] = pos
            out[f'{i} vs breast_{side}'] = {'amplitude_mm': amp * 1000, 'clean': ok}
    report['breast_chest'] = out


def mpfb_breasts(F, M, skin, report):
    """v3 breasts: adipose body generated from the MPFB skin (inset 4 mm, closed on pectoralis major);
    areola + nipple generated on the skin at the breast apex; the HRA glands, ducts and suspensory
    ligaments carried rigidly (+ one uniform scale) so their nipple meets the new nipple and they
    fit inside the fat. Returns extra parts [(meta, pos, idx)]."""
    extra, out = [], {}
    from scipy.spatial import cKDTree
    skin = bt.load_obj_mesh('mpfb_skin.obj')
    flat = bt.load_obj_mesh('mpfb_female_flat.obj')
    # Nipple at the 4th intercostal space: midway between the warped 4th and 5th ribs where they
    # pass the nipple's parasagittal plane; the whole mound moves along the chest wall to get there.
    nip0 = bt.nipples(skin, POSE[1])['L']
    rib = lambda w: next(m['pos'] for m in M.values() if m['name'] == f'Left {w} rib')
    def front_y(r, x):
        b = r[np.abs(r[:, 0] - x) < 0.015]
        return float(b[b[:, 2] > np.percentile(b[:, 2], 60), 1].mean())
    target = (front_y(rib('fourth'), nip0[0]) + front_y(rib('fifth'), nip0[0])) / 2
    dy = float(np.clip(target - nip0[1], -0.06, 0.06))
    P0 = np.asarray(skin.vertices).copy()
    lifted, flat_lifted = bt.raise_breasts(skin, flat, dy)
    skin.vertices = lifted
    flat.vertices = flat_lifted
    # Carry the raised breasts into the packaged skin (welded order may differ: match by position).
    d, j = cKDTree(P0).query(F['VH_F_skin']['pos'])
    F['VH_F_skin']['pos'] = np.where((d < 1e-7)[:, None], np.asarray(skin.vertices)[j], F['VH_F_skin']['pos'])
    report['breast_raise'] = {'nipple_before_y': float(nip0[1]), 'target_y': target, 'dy_m': dy}
    log('breast raise', report['breast_raise'])
    nip1 = bt.nipples(skin, POSE[1])['L']
    y_range = (front_y(rib('sixth'), nip1[0]) - 0.003, front_y(rib('second'), nip1[0]) + 0.01)
    report['breast_raise']['footprint_y_range'] = list(y_range)
    import trimesh
    wall = trimesh.util.concatenate([ml.to_trimesh(m['pos'], m['idx']) for m in M.values()
                                     if re.search(r'pectoralis|serratus anterior|intercostal|\brib\b|costal cartilage|sternum', m['name'], re.I)
                                     and 1.0 < m['pos'][:, 1].mean() < 1.45])
    fats = bt.breast_fat_from_pair(skin, flat, y_range=y_range, chest_wall=wall)
    nips = bt.nipples(skin, POSE[1])
    for side, word in (('L', 'Left'), ('R', 'Right')):
        nip = nips[side]
        fv, fi = np.asarray(fats[side].vertices), np.asarray(fats[side].faces).reshape(-1)
        names = [n for n, f in F.items() if f['group'] == 'breast_' + side]
        import trimesh
        drop = r'fat|nipple|areola|tubercle'
        hra_nip = [n for n in names if 'nipple' in n]
        keep = [n for n in names if not re.search(drop, n)]       # real HRA lobes, ducts, sinuses, Cooper's ligaments
        src_nip = np.vstack([F[n]['pos'] for n in hra_nip]).mean(0)
        hra_fat = np.vstack([F[n]['pos'] for n in names if 'fat' in n])
        # ONE rigid transform + uniform scale for the whole real HRA breast interior: the HRA nipple goes
        # 4 mm under the new nipple, the nipple->fat-centroid axis is aligned, and the scale is the cube
        # root of the volume ratio of the new adipose body to the real HRA one (x0.95, so it fits inside).
        s = 0.8 * (trimesh.convex.convex_hull(fv).volume / trimesh.convex.convex_hull(hra_fat).volume) ** (1 / 3)
        R = bt.min_rotation(hra_fat.mean(0) - src_nip, fv.mean(0) - nip)
        anchor = nip - skin.vertex_normals[np.argmin(np.linalg.norm(skin.vertices - nip, axis=1))] * 0.004
        for n in keep:
            F[n]['pos'] = s * (F[n]['pos'] - src_nip) @ R.T + anchor
            F[n]['nrm'] = F[n]['nrm'] @ R.T
        fat_shell = ml.SkinShell(ml.to_trimesh(fv, fi), pitch=0.0015)
        for n in keep:
            F[n]['pos'], _, _ = fat_shell.keep_inside(F[n]['pos'], margin=0.0008, radius=0.004)
        for n in names:
            if re.search(drop, n):
                F.pop(n)
        (av, ai), (nv, ni) = bt.areola_and_nipple(skin, nip)
        w = word.lower()
        extra += [({'id': f'GEN_breast_adipose_{w}', 'name': f'{word} breast adipose tissue', 'conceptId': f'GEN:breast-adipose-{w}',
                    'system': 'adipose', 'source': 'generated', 'accuracy': 'generated',
                    'note': 'Generated: the space between the chest wall (pectoralis fascia + retromammary fat) and the '
                            'breast skin inset 2.5 mm; thickness tapers to zero at the border. Matches the visible breast exactly.'}, fv, fi),
                  ({'id': f'GEN_areola_{w}', 'name': f'{word} areola', 'conceptId': f'GEN:areola-{w}', 'system': 'integumentary',
                    'source': 'generated', 'accuracy': 'generated',
                    'note': 'Generated from the skin surface: 19 mm radius raised disc with Montgomery-tubercle texture.'}, av, ai),
                  ({'id': f'GEN_nipple_{w}', 'name': f'{word} nipple', 'conceptId': f'GEN:nipple-{w}', 'system': 'integumentary',
                    'source': 'generated', 'accuracy': 'generated',
                    'note': 'Generated from the skin surface: a 5 mm radius, 6 mm high rise blending into the areola.'}, nv, ni)]
        out[side] = {'nipple': nip.tolist(), 'gland_scale': float(s), 'fat_vertices': int(len(fv)), 'hra_parts_kept': keep}
    report['breasts_v3'] = out
    return extra


def rigid_inside(shell, pos, margin=0.0015, tolerance=0.0, min_scale=0.8):
    """Translate a rigid part (or group) inside the skin; if translation alone cannot, shrink it
    uniformly about its centroid (aspect ratios unchanged). `tolerance` = fraction of vertices allowed
    to stay outside. Returns (pos, description)."""
    p = pos.copy()
    moved = np.zeros(3)
    ok = lambda q: shell.outside(q, margin).mean() <= tolerance
    for _ in range(6):
        if ok(p):
            break
        q, _, _ = shell.keep_inside(p, margin=margin, radius=0.001, iterations=3)
        d = q - p
        out = shell.outside(p, margin)
        step = d[out].mean(0) if out.any() else d[np.argmax(np.linalg.norm(d, axis=1))]
        p = p + step; moved += step
    scale = 1.0
    c = p.mean(0)
    base = p - c
    while not ok(p) and scale > min_scale:
        scale *= 0.99
        p = c + base * scale
    return p, {'translate_mm': float(np.linalg.norm(moved) * 1000), 'scale': scale}


def keep_inside_skin(shell, M, F, report, names=None):
    """Nothing male-derived or relocated may protrude through the skin."""
    out = {}
    # The skull, teeth, eyes and ears move as ONE rigid group (shared translation, then shared
    # uniform shrink about the group centroid), so the face is never taken apart bone by bone.
    head = [i for i in STATE.get('head_parts', []) if i in M]
    if head:
        cat = np.vstack([M[i]['pos'] for i in head])
        if shell.outside(cat, 0.0005).sum():
            new, how = rigid_inside(shell, cat, margin=0.001, tolerance=0.002, min_scale=0.95)
            # The same translation + uniform scale goes to EVERY rigid head part (brain, muscles,
            # glands too), fitted on the bones and sense organs, so nothing slips out of the skull.
            s_, R_, t_ = ml.umeyama(cat, new)
            for i in STATE.get('head_all', head):
                if i in M:
                    M[i]['pos'] = ml.apply_similarity(M[i]['pos'], s_, R_, t_)
            out['head_group'] = {'parts': len(head), **how, 'left_outside': int(shell.outside(new, 0.0005).sum())}
    # Milestone 7: forearm + hand bones of each side move as ONE rigid group (like the skull), so the
    # wrist and finger joints are never taken apart bone by bone.
    limb = set()
    for sgn, side in ((1, 'L'), (-1, 'R')):
        g = [i for i, m in M.items() if m.get('arm_segment') in (1, 2) and np.sign(m['pos'][:, 0].mean()) == sgn]
        if not g:
            continue
        limb.update(g)
        cat = np.vstack([M[i]['pos'] for i in g])
        if shell.outside(cat, 0.0005).sum():
            new, how = rigid_inside(shell, cat, margin=0.001, tolerance=0.002, min_scale=0.95)
            s_, R_, t_ = ml.umeyama(cat, new)
            for i in g:
                M[i]['pos'] = ml.apply_similarity(M[i]['pos'], s_, R_, t_)
            out['forearm_hand_group_' + side] = {'parts': len(g), **how, 'left_outside': int(shell.outside(new, 0.0005).sum())}
    for i, m in M.items():
        if i in limb:
            continue
        # 3 mm detection margin: absorbs the later 0.2 % simplification error, so the packaged
        # (simplified) meshes stay inside the skin too.
        bad = shell.outside(m['pos'], 0.003).sum()
        if i in STATE.get('head_all', []) or i in head:
            # The head is ONE rigid unit: never move a head part on its own. Any residual protrusion
            # after the group fit (lips / nose tip) is reported, not "fixed" by breaking the skull.
            if bad:
                out[i] = {'vertices_outside': int(bad), 'left_outside': int(shell.outside(m['pos'], 0.0005).sum()), 'head_rigid': True}
            continue
        if bad > 2000:
            log('  far outside skin:', i, m['name'], int(bad), 'of', len(m['pos']))
        if bad and (m['system'] in ('skeletal', 'sensory') or np.linalg.norm(np.ptp(m['pos'], 0)) < 0.06):
            # Bones and sense organs are rigid: translate (then, only if needed, uniformly shrink about
            # the centroid) - never squash them vertex by vertex, which would change their shape.
            m['pos'], how = rigid_inside(shell, m['pos'], margin=0.003)
            out[i] = {'vertices_outside': int(bad), 'rigid': how, 'left_outside': int(shell.outside(m['pos'], 0.0005).sum())}
            continue
        if bad:
            m['pos'], d, left = shell.keep_inside(m['pos'], margin=0.003, radius=0.012)
            out[i] = {'vertices_outside': int(bad), 'moved_mm': d * 1000, 'left_outside': left}
    for n, f in F.items():
        if f['group'] in ('skin',) or n in ('VH_F_nipple_L', 'VH_F_nipple_R'):
            continue
        bad = shell.outside(f['pos'], 0.003).sum()
        if not bad:
            continue
        # HRA ducts, lung segments and any other HRA soft organ touching the (smaller) MPFB body
        # are kept 3 mm inside the skin with a smooth local push.
        f['pos'], d, left = shell.keep_inside(f['pos'], margin=0.003, radius=0.008)
        out[n] = {'vertices_outside': int(bad), 'moved_mm': d * 1000, 'left_outside': left}
    report['skin_protrusion_fix'] = out
    log('inside skin: fixed', len(out), 'parts')


# ============================================================== generated structures

GENERATED = {
    'labium_majus_left': ('Left labium majus (fat pad)', 'reproductive', 'left labium majus', ['vulva']),
    'labium_majus_right': ('Right labium majus (fat pad)', 'reproductive', 'right labium majus', ['vulva']),
    'labium_minus_left': ('Left labium minus', 'reproductive', 'left labium minus', ['vulva']),
    'labium_minus_right': ('Right labium minus', 'reproductive', 'right labium minus', ['vulva']),
    'vestibule_of_vagina': ('Vestibule of vagina', 'reproductive', 'vestibule of vagina', ['vulva']),
    'glans_of_clitoris': ('Glans of clitoris', 'erectile', 'glans of clitoris', ['vulva', 'clitoris']),
    'body_of_clitoris': ('Body of clitoris', 'erectile', 'body of clitoris', ['vulva', 'clitoris']),
    'crus_of_clitoris_left': ('Left crus of clitoris', 'erectile', 'left crus of clitoris', ['vulva', 'clitoris']),
    'crus_of_clitoris_right': ('Right crus of clitoris', 'erectile', 'right crus of clitoris', ['vulva', 'clitoris']),
    'bulb_of_vestibule_left': ('Left bulb of vestibule', 'erectile', 'left bulb of vestibule', ['vulva']),
    'bulb_of_vestibule_right': ('Right bulb of vestibule', 'erectile', 'right bulb of vestibule', ['vulva']),
    'female_urethra': ('Female urethra', 'urinary', 'female urethra', []),
    'ischiocavernosus_left': ('Left ischiocavernosus', 'muscular', 'left ischiocavernosus', ['female perineal muscles']),
    'ischiocavernosus_right': ('Right ischiocavernosus', 'muscular', 'right ischiocavernosus', ['female perineal muscles']),
    'bulbospongiosus_left': ('Left bulbospongiosus', 'muscular', 'left bulbospongiosus', ['female perineal muscles']),
    'bulbospongiosus_right': ('Right bulbospongiosus', 'muscular', 'right bulbospongiosus', ['female perineal muscles']),
    'ovarian_artery_left': ('Left ovarian artery', 'arterial', 'left ovarian artery', ['ovarian vessels']),
    'ovarian_artery_right': ('Right ovarian artery', 'arterial', 'right ovarian artery', ['ovarian vessels']),
    'ovarian_vein_left': ('Left ovarian vein', 'venous', 'left ovarian vein', ['ovarian vessels']),
    'ovarian_vein_right': ('Right ovarian vein', 'venous', 'right ovarian vein', ['ovarian vessels']),
    'greater_vestibular_gland_left': ("Left greater vestibular (Bartholin's) gland", 'reproductive', 'left greater vestibular gland', ['vulva']),
    'greater_vestibular_gland_right': ("Right greater vestibular (Bartholin's) gland", 'reproductive', 'right greater vestibular gland', ['vulva']),
    'paraurethral_gland_left': ("Left paraurethral (Skene's) gland", 'reproductive', 'left paraurethral gland', ['vulva']),
    'paraurethral_gland_right': ("Right paraurethral (Skene's) gland", 'reproductive', 'right paraurethral gland', ['vulva']),
    'perineal_body': ('Perineal body', 'connective', 'perineal body', []),
    'mons_pubis_fat_pad': ('Mons pubis (fat pad)', 'reproductive', 'mons pubis', ['vulva']),
    'prepuce_of_clitoris': ('Prepuce of clitoris', 'reproductive', 'prepuce of clitoris', ['vulva', 'clitoris']),
}
CREATE_SCRIPTS = ['create_vulva.py', 'create_clitoris.py', 'create_female_urethra.py', 'create_perineal_muscles.py', 'create_female_extras.py']


def vulva_landmarks(F, M, skin, lm, tmp):
    import trimesh
    vag = F['VH_F_vagina']['pos']
    c = vag.mean(0)
    _, _, vt = np.linalg.svd(vag - c, full_matrices=False)
    axis = vt[0] if vt[0][1] < 0 else -vt[0]
    proj = (vag - c) @ axis
    inner = vag[proj > proj.max() - 0.003].mean(0)
    # The real HRA pelvis is not centred on x = 0: use its pubic symphysis as the midline.
    S = (lm['symphysis_bottom_L'] + lm['symphysis_bottom_R']) / 2
    x0 = 0.0   # v3: MPFB body is symmetric about x = 0
    inner[0] = x0
    sv = skin.vertices
    # Vaginal orifice: where the vaginal axis meets the skin (midline band), below the symphysis.
    band = sv[(np.abs(sv[:, 0] - x0) < 6e-4) & (sv[:, 1] < S[1]) & (sv[:, 1] > inner[1] - 0.06)]
    d = band - inner
    along = d @ axis
    off = np.linalg.norm(d - np.outer(along, axis), axis=1)
    cand = band[(along > -0.005)]
    introitus = cand[np.argmin(off[along > -0.005])].copy() if len(cand) else band[np.argmin(np.linalg.norm(d, axis=1))].copy()
    introitus[0] = x0
    _, _, tri = trimesh.proximity.closest_point(skin, [introitus])
    normal = skin.face_normals[tri[0]].copy(); normal[0] = 0.0; normal /= np.linalg.norm(normal)
    ap = S - introitus; ap -= normal * (ap @ normal); ap[0] = 0; ap /= np.linalg.norm(ap)
    midline = sv[(np.abs(sv[:, 0] - x0) < 6e-4) & (sv[:, 1] < S[1] + 0.04) & (sv[:, 1] > introitus[1] - 0.06)]

    def snap(p):
        q = midline[np.argmin(np.linalg.norm(midline - p, axis=1))].copy(); q[0] = x0
        return q
    glans = snap(introitus + ap * 0.030)
    meatus = snap(introitus + ap * 0.013)
    out = {'introitus': introitus, 'vulva_normal': normal, 'glans_site': glans, 'meatus': meatus,
           'meatus_inner': meatus - normal * 0.006, 'anterior_commissure': snap(introitus + ap * 0.058),
           'posterior_commissure': snap(introitus - ap * 0.022), 'vagina_axis': axis, 'symphysis_bottom': S,
           'vagina_inner': inner}
    sph = np.vstack([M[i]['pos'] for i in M if 'anal sphincter' in M[i]['name'].lower()])
    out['perineal_body'] = (introitus + sph.mean(0)) / 2 - normal * 0.012
    out['clitoral_root'] = S + (glans - S) * 0.35 - normal * 0.004
    centre = (S + introitus) / 2
    for side, key in (('left', 'L'), ('right', 'R')):
        hip = np.vstack([F[n]['pos'] for n in HRA_PELVIS['hip_' + key]])
        a, b = lm['symphysis_bottom_' + key], lm['ischial_tuberosity_' + key]
        pts = []
        for t in (0.15, 0.45, 0.7, 0.95):   # along the ischiopubic ramus
            q = a + (b - a) * t
            bone = hip[np.argmin(np.linalg.norm(hip - q, axis=1))]
            dd = centre - bone; dd[1] *= 0.3; dd /= np.linalg.norm(dd)
            pts.append(bone + dd * 0.0065)
        out['crus_' + side] = [p.tolist() for p in pts]
    neck = F['VH_F_urinary_bladder_neck_smooth_muscle']['pos'].mean(0)
    out['bladder_neck'] = neck + (meatus - neck) / np.linalg.norm(meatus - neck) * 0.002
    mid = (out['bladder_neck'] + meatus) / 2
    vb = vag[(np.abs(vag[:, 0] - x0) < 0.01) & (np.abs(vag[:, 1] - mid[1]) < 0.006)]
    hip = np.vstack([F[n]['pos'] for n in HRA_PELVIS['hip_L'] + HRA_PELVIS['hip_R']])
    sym = hip[(np.abs(hip[:, 0] - x0) < 0.02) & (np.abs(hip[:, 1] - mid[1]) < 0.006)]
    z = (vb[:, 2].max() if len(vb) else mid[2]) + 0.0045
    if len(sym):
        z = min(z, sym[:, 2].min() - 0.0045)
    out['urethra_mid'] = np.array([x0, mid[1], z])
    # Ovarian vessels: origins on the warped aorta / IVC / left renal vein, course over the
    # suspensory ligament of the ovary to the HRA ovary.
    by = lambda pat: np.vstack([M[i]['pos'] for i in M if re.fullmatch(pat, M[i]['name'])])
    aorta = by('Abdominal aorta'); renal = by('(Left|Right) renal artery')
    yr = renal[:, 1].mean() - 0.025
    band = aorta[np.abs(aorta[:, 1] - yr) < 0.008]
    out['aorta_origin'] = band.mean(0) if len(band) else aorta[np.argmin(np.abs(aorta[:, 1] - yr))]
    ivc = by('Inferior vena cava'); band = ivc[np.abs(ivc[:, 1] - yr) < 0.01]
    out['ivc_point'] = band.mean(0) if len(band) else ivc[np.argmin(ivc[:, 1])]
    lrv = by('Left renal vein'); out['left_renal_vein_point'] = lrv[np.argmax(lrv[:, 0])] * 0.5 + lrv.mean(0) * 0.5
    for side, key in (('left', 'L'), ('right', 'R')):
        out['ovary_' + side] = F[f'VH_F_{side}_ovary']['pos'].mean(0)
        sl = F['VH_F_suspensory_ligament_of_ovary_' + key]['pos']
        out['susp_top_' + side] = sl[np.argmax(sl[:, 1])]
    # Mons pubis: under the skin in front of the pubic symphysis.
    top = (lm['symphysis_top_L'] + lm['symphysis_top_R']) / 2
    ahead = sv[(np.abs(sv[:, 0] - x0) < 0.01) & (np.abs(sv[:, 1] - top[1]) < 0.01) & (sv[:, 2] > top[2])]
    front = ahead[np.argmax(ahead[:, 2])] if len(ahead) else top + [0, 0, 0.03]
    mn = front - top; mn[0] = 0; mn /= np.linalg.norm(mn)
    out['mons_normal'] = mn
    out['mons_up'] = np.cross([1.0, 0, 0], mn)
    out['mons_centre'] = front - mn * 0.012
    sel = np.linalg.norm(skin.triangles_center - introitus, axis=1) < 0.09
    patch = skin.submesh([np.where(sel)[0]], append=True)
    ml.write_obj(tmp / 'skin_patch.obj', patch.vertices, patch.faces.reshape(-1))
    out['skin_patch'] = str(tmp / 'skin_patch.obj')
    return {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in out.items()}


def generate(F, M, skin, lm, report, blender):
    import blender_run
    tmp = Path(tempfile.gettempdir()) / 'ha-female' / 'generated'
    tmp.mkdir(parents=True, exist_ok=True)
    for f in tmp.glob('*'):
        f.unlink()
    landmarks = vulva_landmarks(F, M, skin, lm, tmp)
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


def check_generated(G, F, M, shell, report, rounds=6):
    """Push generated structures out of bone, thigh muscles and organs and keep them inside the
    skin; Taubin-smooth; re-check. Then make room in BodyParts3D soft tissue."""
    import trimesh
    bones = [ml.to_trimesh(F[n]['pos'], F[n]['idx']) for v in HRA_PELVIS.values() for n in v] + \
            [ml.to_trimesh(F['VH_F_coccyx']['pos'], F['VH_F_coccyx']['idx'])]
    organs = {n: ml.to_trimesh(f['pos'], f['idx']) for n, f in F.items() if f['group'] == 'pelvic' and not HRA_SOFT.search(n)}
    per = np.vstack([g['pos'] for g in G.values()])
    plo, phi = per.min(0) - 0.01, per.max(0) + 0.01
    thigh = [ml.to_trimesh(m['pos'], m['idx']) for m in M.values()
             if m['system'] == 'muscular' and re.search(r'gracilis|adductor|obturator externus|pectineus', m['name'], re.I)
             and overlaps(m['pos'].min(0), m['pos'].max(0), plo, phi)]

    retro = {}
    for i, m in M.items():
        if re.search(r'psoas|kidney|colon|ureter|renal vein|vena cava|abdominal aorta|common iliac|external iliac', m['name'], re.I):
            retro[i] = (m['name'], ml.to_trimesh(m['pos'], m['idx']))

    def obstacles(stem):
        if stem.startswith('ovarian'):
            # Retroperitoneal course: clear psoas, kidneys, colon, ureters and the great vessels,
            # except the vessel each one arises from / drains into.
            own = 'abdominal aorta' if 'artery' in stem else ('vena cava' if stem.endswith('right') else 'left renal vein')
            g = G[stem]
            lo, hi = g['pos'].min(0) - 0.01, g['pos'].max(0) + 0.01
            obs = [t for n, t in retro.values() if own not in n.lower() and overlaps(t.bounds[0], t.bounds[1], lo, hi)]
            return trimesh.util.concatenate(obs) if obs else trimesh.Trimesh()
        obs = list(bones) + thigh
        for n, t in organs.items():
            if stem == 'female_urethra' and ('bladder' in n or 'trigone' in n):
                continue
            if stem == 'vestibule_of_vagina' and 'vagina' in n:
                continue
            obs.append(t)
        return trimesh.util.concatenate(obs)
    history = {}
    for stem, g in G.items():
        obs = obstacles(stem)
        if stem.startswith(('ischiocavernosus', 'bulbospongiosus')):
            cov = ('crus_of_clitoris_' if stem.startswith('ischio') else 'bulb_of_vestibule_') + stem.split('_')[-1]
            obs = trimesh.util.concatenate([obs, ml.to_trimesh(G[cov]['pos'], G[cov]['idx'])])
        steps = []
        for _ in range(rounds):
            hit = ml.collides(ml.to_trimesh(g['pos'], g['idx']), obs)
            outside = int(shell.outside(g['pos'], 0.0008).sum())
            steps.append({'collides': bool(hit), 'outside_skin': outside})
            if not hit and not outside:
                break
            if hit:
                g['pos'], _ = ml.push_out(g['pos'], obs, margin=0.0008, radius=0.006, iterations=4)
            g['pos'], _, _ = shell.keep_inside(g['pos'], margin=0.0015, radius=0.006)
            t = ml.to_trimesh(g['pos'], g['idx'])
            trimesh.smoothing.filter_taubin(t, lamb=0.5, nu=-0.53, iterations=6)
            g['pos'] = np.asarray(t.vertices)
        last = steps[-1]
        history[stem] = {'rounds': steps, 'clean': not last['collides'] and not last['outside_skin']}
    gen = trimesh.util.concatenate([ml.to_trimesh(g['pos'], g['idx']) for s, g in G.items()
                                    if not s.startswith(('labium_majus', 'ovarian', 'mons'))])
    moved = {}
    for i, m in M.items():
        movable = m['system'] in ('venous', 'arterial', 'nervous', 'digestive', 'lymphatic') or LEVATOR.search(m['name'])
        if not movable or not overlaps(m['pos'].min(0), m['pos'].max(0), gen.bounds[0], gen.bounds[1]):
            continue
        if not ml.collides(ml.to_trimesh(m['pos'], m['idx']), gen):
            continue
        pos, amp, ok = ml.make_room(m['pos'], m['idx'], gen, direction=away(m['pos'], gen.centroid, 0.08), sigma=0.015, step=0.0015, max_amp=0.03)
        if ok and amp > 0:
            m['pos'] = pos
        moved[i] = {'amplitude_mm': amp * 1000, 'clean': ok}
    report['generated_collision_loop'] = {'generated': history, 'bp3d_soft_tissue': moved}
    log('generated collision loop', {k: v['clean'] for k, v in history.items()})


def gluteofemoral_fat(skin, lm_f, lm_pf, fat_extra=0.008):
    """Generated subcutaneous fat shell over hips, buttocks and thighs: the band of skin between
    the gluteofemoral levels, offset inward by 1–(1+fat_extra/1mm) mm and closed into a shell."""
    import trimesh
    y_lo, y_hi = lm_f['crotch'] - 0.30, lm_pf['iliac_crest_L'][1] + 0.02
    c = skin.triangles_center
    sel = (c[:, 1] > y_lo) & (c[:, 1] < y_hi) & ~((np.abs(c[:, 0]) < 0.03) & (c[:, 1] > lm_f['crotch'] - 0.04) & (c[:, 1] < lm_f['crotch'] + 0.06))
    band = skin.submesh([np.where(sel)[0]], append=True)
    n = band.vertex_normals
    y = band.vertices[:, 1]
    taper = ml.smoothstep(y_lo, y_lo + 0.08, y) * (1 - ml.smoothstep(y_hi - 0.05, y_hi, y))
    outer = band.vertices - n * 0.001
    inner = band.vertices - n * (0.001 + fat_extra * np.maximum(taper, 0.15))[:, None]
    V = np.vstack([outer, inner])
    nv = len(outer)
    Fo = band.faces
    Fi = band.faces[:, ::-1] + nv
    edges = trimesh.grouping.group_rows(band.edges_sorted, require_count=1)
    be = band.edges_sorted[edges]
    side = np.vstack([np.c_[be[:, 0], be[:, 1], be[:, 1] + nv], np.c_[be[:, 0], be[:, 1] + nv, be[:, 0] + nv]])
    return V, np.vstack([Fo, Fi, side]).reshape(-1)


# ============================================================== manifest

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
    'VH_F_fundus_of_urinary_bladder_base': 'fundus of urinary bladder', 'VH_F_pelvis': 'female pelvis',
    'VH_F_ilium': 'ilium', 'VH_F_ischium': 'ischium', 'VH_F_pubis': 'pubis',
}
GROUP_NAMES = {'vulva': 'Vulva (external genitalia)', 'clitoris': 'Clitoris', 'female perineal muscles': 'Superficial perineal muscles (female)'}
SKIP_GROUPS = ('VH_F', 'VH_F_integumentary_system', 'VH_F_circulatory_system', 'VH_F_blood_vasculature', 'VH_F_skeletal_system',
               'VH_F_urinary_system', 'VH_F_ilium_compact_bone', 'VH_F_ischium_compact_bone', 'VH_F_pubis_compact_bone')


def title(s):
    return s[:1].upper() + s[1:]


def hra_name(name, f, fixes):
    if name == 'VH_F_skin':
        return 'Skin'
    m = re.match(r'VH_F_(ilium|ischium|pubis)_compact_bone_([LR])', name)
    if m:
        return f"{'Left' if m.group(2) == 'L' else 'Right'} {m.group(1)}"
    label = str(f['hra']['extras'].get('label') or '').strip()
    if label in ('', '-', 'None', 'NA'):
        label = name.replace('VH_F_', '').replace('_', ' ').strip()
    # Readable vertebra names (the HRA labels are Uberon "Mammalian cervical vertebra 5" etc.).
    mv = re.match(r'(?i)^(?:mammalian )?(cervical|thoracic|lumbar) vertebra (\d+)$', label)
    if mv:
        k = {'cervical': 'C', 'thoracic': 'T', 'lumbar': 'L'}[mv.group(1).lower()]
        label = f"{mv.group(1).capitalize()} vertebra {mv.group(2)} ({k}{mv.group(2)})"
    low = label.lower()
    x = f['pos'][:, 0].mean()
    side = 'left' if x > 0.004 else 'right' if x < -0.004 else None
    if side and ('left' in low or 'right' in low):
        if ('left' in low and side == 'right') or ('right' in low and side == 'left'):
            fixed = re.sub(r'(?i)\b(left|right)\b', lambda mm: {'left': 'right', 'right': 'left'}[mm.group(1).lower()], label)
            fixes[name] = {'source_label': label, 'corrected': fixed, 'centroid_x_m': float(x)}
            label = fixed
    elif side and re.search(r'_[LR]$|_[LR]_', name):
        label = f'{side} {low}'
    return title(label)


def write_package(M, F, G, extra, atlas, removed, report):
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
        nrm = ml.quantize_normals(ml.vertex_normals(pos.astype(np.float64), idx)) if nrm is None else ml.quantize_normals(nrm)
        idx = np.asarray(idx, np.uint32)
        entry.update({'chunk': len(chunks), 'positions': append(pos), 'normals': append(nrm), 'indices': append(idx),
                      'vertexCount': len(pos), 'indexCount': len(idx), 'bounds': ml.bounds(pos.astype(np.float64))})
        total += len(idx) // 3
        parts.append(entry)

    for p in atlas['parts']:
        if p['id'] not in M:
            continue
        m = M[p['id']]
        note = 'Warped approximation: BodyParts3D male geometry carried into the HRA female body by a landmark thin-plate-spline warp.'
        if re.search(r'thyroid cartilage|mandible|frontal bone|larynx', p['name'], re.I):
            note += ' Brow, jaw and laryngeal prominence follow the female head and neck surface (warped approximation).'
        if m.get('scan_derived'):
            add({'id': p['id'], 'name': p['name'], 'conceptId': p['conceptId'], 'system': p['system'], 'source': 'hra',
                 'accuracy': 'scan-derived', 'note': f"Scan-derived: the real Visible Human Female bone ({m['scan_derived']}), "
                 'shown in place of the BodyParts3D shape (same ID, name and system).'}, m['pos'], None, m['idx'])
            continue
        add({'id': p['id'], 'name': p['name'], 'conceptId': p['conceptId'], 'system': m.get('system', p['system']), 'source': 'bp3d',
             'accuracy': 'warped', 'note': note}, m['pos'], None, m['idx'])
    xref = xrefs['uberon']
    fixes = {}
    for n, f in F.items():
        u = str(f['hra']['extras'].get('ontologyid') or '')
        if not u.startswith(('UBERON', 'FMA', 'CL', 'ILX')):
            u = ''
        fma = (xref.get(u) or {}).get('fma')
        if u.startswith('FMA'):
            fma, u = u.replace(':', ''), ''
        cid = fma or u or 'HRA:' + n
        if n == 'VH_F_skin':
            cid = 'FMA7163'
        e = {'id': n, 'name': hra_name(n, f, fixes), 'conceptId': cid, 'uberon': u, 'system': f['system'], 'source': 'hra',
             'accuracy': 'scan-derived'}
        if f.get('seal'):
            e['seal'] = True
        if n == 'VH_F_skin' and STATE.get('body') in ('vhf', 'hybrid'):
            e.update(id='female_skin', note='Scan-derived body surface of the Visible Human Female (HRA), the one real donor '
                     'of this model. Courtesy of the U.S. National Library of Medicine.')
        elif n == 'VH_F_skin':
            e.update(id='female_skin', source='mpfb', accuracy='generated', uberon='',
                     note='Generated body surface: MPFB2 (MakeHuman, CC0) parametric average adult female (1.63 m, BMI 22.5), '
                          'posed by its rig into the reference pose; schematic pudendal cleft. Not scan-derived.')
        add(e, f['pos'], f['nrm'], f['idx'])
    for stem, g in G.items():
        add({'id': 'GEN_' + stem, 'name': g['name'], 'conceptId': by_label.get(g['label']) or 'GEN:' + stem, 'system': g['system'],
             'source': 'generated', 'accuracy': 'generated',
             'note': 'Generated / schematic, not scan-derived. Built in Blender from reference dimensions (see DATA_SOURCES.md).'},
            g['pos'], None, g['idx'])
    for e, pos, idx in extra:
        add(e, pos, None, idx)
    flush()
    ids = {p['id'] for p in parts}
    replaced = {pid: [] for pid in removed}
    replaced.update(MALE_REPLACED)
    replaced['FJ3149'] = [n for n, f in F.items() if f['system'] == 'urinary']
    concepts, seen = [], {}

    def add_concept(cid, name, elements):
        elements = [e for e in dict.fromkeys(elements) if e in ids]
        if not elements:
            return
        if cid in seen:
            seen[cid]['elements'] = list(dict.fromkeys(seen[cid]['elements'] + elements))
            return
        c = {'id': cid, 'name': name, 'elements': elements}
        seen[cid] = c; concepts.append(c)
    for c in atlas['concepts']:
        els = []
        for e in c['elements']:
            els += replaced.get(e, []) if e in removed else [e]
        add_concept(c['id'], c['name'], els)
    groups = {}
    for n, f in F.items():
        if n == 'VH_F_skin':
            continue
        for anc in f['hra']['ancestor_names']:
            groups.setdefault(anc, []).append(n)
    add_concept('FMA7163', 'Skin', ['female_skin'])
    for g, members in groups.items():
        if g in SKIP_GROUPS:
            continue
        label = HRA_GROUP_LABELS.get(g, g.replace('VH_F_', '').replace('_', ' '))
        add_concept(by_label.get(label) or 'HRA:' + g, title(label), members)
    for p in parts:
        if p['source'] == 'hra':
            cid = p['conceptId'] if sum(q['conceptId'] == p['conceptId'] for q in parts) == 1 else p['id']
            add_concept(cid, p['name'], [p['id']])
    for stem, g in G.items():
        add_concept(by_label.get(g['label']) or 'GEN:' + stem, g['name'], ['GEN_' + stem])
        for grp in g['groups']:
            add_concept(by_label.get(grp) or 'GEN:' + grp.replace(' ', '-'), GROUP_NAMES.get(grp, title(grp)), ['GEN_' + stem])
    for e, _, _ in extra:
        add_concept(e['conceptId'], e['name'], [e['id']])
    add_concept('FMA16586', 'Right hip bone', HRA_PELVIS['hip_R'])
    add_concept('FMA16587', 'Left hip bone', HRA_PELVIS['hip_L'])
    add_concept('HRA:VH_F_pelvis', 'Female pelvis', HRA_PELVIS['hip_L'] + HRA_PELVIS['hip_R'] + HRA_PELVIS['sacrum'] + ['VH_F_coccyx'])
    add_concept('GEN:breasts', 'Breasts', [n for n, f in F.items() if f['group'].startswith('breast')])
    vhf = STATE.get('body') in ('vhf', 'hybrid')
    manifest = {
        'version': 'Human Atlas female 5.0 (one real body: Visible Human Female)' if vhf else 'Human Atlas female 3.0 (MPFB2 average female body + HRA pelvis/organs + warped BodyParts3D + generated)',
        'sex': 'female', 'source': ('Visible Human Female (U.S. National Library of Medicine): HRA 3D Reference Organ Set for Female v1.5 '
                                   '(skin, pelvis, organs, breasts, lungs) and VHF CT (TotalSegmentator targets); BodyParts3D 4.0 registered/warped; generated structures') if vhf else
                                  'MPFB2/MakeHuman CC0 (body surface); HRA 3D Reference Organ Set for Female v1.5 (pelvis, pelvic organs, lungs, breast glands); BodyParts3D 4.0 (warped); generated structures',
        'scope': ('Female body based on one real donor: Visible Human Female (age 59), U.S. National Library of Medicine.') if vhf else
                 'Adult female reference assembly: average adult female body (MPFB2, BMI 22.5) with the scan-derived Visible Human Female pelvis and organs (HRA).',
        'sources': SOURCES, 'accuracyNotes': ACCURACY_NOTES, 'parts': parts, 'concepts': concepts, 'chunks': chunks,
        'triangles': total, 'build': {'removedMaleParts': sorted(removed), 'labelCorrections': fixes, 'report': 'work/female/report.json'},
    }
    (OUT / 'atlas.json').write_text(json.dumps(manifest, separators=(',', ':')))
    report['package'] = {'parts': len(parts), 'concepts': len(concepts), 'triangles_before_simplification': total,
                         'by_source': {s: sum(p['source'] == s for p in parts) for s in SOURCES},
                         'by_accuracy': {a: sum(p['accuracy'] == a for p in parts) for a in ACCURACY_NOTES}, 'label_corrections': fixes}
    log('package', json.dumps(report['package']))


# ============================================================== driver

# ============================================================== hybrid body (milestone 6)

# Real HRA VH_F organs used as-is (same donor, same space) in the hybrid body; BodyParts3D
# equivalents are removed. ancestor group -> (system, group)
HRA_HYBRID = {
    'VH_F_vertebrae': ('skeletal', 'spine'), 'VH_F_spinal_cord': ('nervous', 'spine'),
    'VH_F_liver': ('digestive', 'organ'), 'VH_F_right_lobe_of_liver': ('digestive', 'organ'),
    'VH_F_liver_left_lateral_lobe': ('digestive', 'organ'), 'VH_F_liver_left_medial_lobe': ('digestive', 'organ'),
    'VH_F_left_inferomedial_segment': ('digestive', 'organ'), 'VH_F_gallbladder_': ('digestive', 'organ'),
    'VH_F_ducts_of_liver': ('digestive', 'organ'), 'VH_F_ducts_of_gallbladder': ('digestive', 'organ'),
    'VH_F_pancreas': ('digestive', 'organ'), 'VH_F_ducts_of_pancreas': ('digestive', 'organ'),
    'VH_F_spleen': ('lymphatic', 'organ'), 'VH_F_colon': ('digestive', 'organ'), 'VH_F_small_intestine': ('digestive', 'organ'),
    'VH_F_ileum': ('digestive', 'organ'), 'VH_F_duodenum': ('digestive', 'organ'), 'VH_F_duodenum_superior': ('digestive', 'organ'),
    'VH_F_left_kidney': ('urinary', 'organ'), 'VH_F_right_kidney': ('urinary', 'organ'),
    'VH_F_cortex_of_kidney_L': ('urinary', 'organ'), 'VH_F_cortex_of_kidney_R': ('urinary', 'organ'),
    'VH_F_renal_pyramid_L': ('urinary', 'organ'), 'VH_F_renal_pyramid_R': ('urinary', 'organ'),
    'VH_F_renal_papilla_L': ('urinary', 'organ'), 'VH_F_renal_papilla_R': ('urinary', 'organ'),
    'VH_F_major_calyx_L': ('urinary', 'organ'), 'VH_F_major_calyx_R': ('urinary', 'organ'),
    'VH_F_minor_calyx_L': ('urinary', 'organ'), 'VH_F_minor_calyx_R': ('urinary', 'organ'),
    'VH_F_cardiac_chamber': ('cardiac', 'organ'), 'VH_F_valve': ('cardiac', 'organ'), 'VH_F_papillary_muscle_of_heart': ('cardiac', 'organ'),
    'VH_F_trachea': ('respiratory', 'organ'), 'VH_F_main_bronchi': ('respiratory', 'organ'), 'VH_F_thymus': ('lymphatic', 'organ'),
}
# BodyParts3D structures replaced by those real organs (hybrid only).
BP3D_REPLACED_HYBRID = re.compile(
    r'vertebra$|^Atlas$|^Axis$|^Sacrum$|spinal cord|intervertebral dis[ck]|^Coccyx|liver|gallbladder|pancrea|^Spleen$|splenic (?!artery|vein)|colon|caecum|cecum|'
    r'appendix|jejunum|ileum$|duodenum|small intestine|kidney|renal (pyramid|papilla|cortex|medulla|column)|calyx|^Trachea$|'
    r'(left|right) main bronchus|thymus', re.I)


def rigidify_bones(M, male, report):
    """Milestone 6: every BodyParts3D bone moves by ONE similarity (rotation + translation + uniform
    scale): the best similarity from its male shape to wherever the warp / arm segments took it.
    The result is identical to the source up to scale (max error after a similarity fit = 0)."""
    worst, n = 0.0, 0
    for pid, m in M.items():
        if m['system'] != 'skeletal' or m.get('scan_derived') or len(m['pos']) != len(male[pid]['pos']):
            continue
        s, R, t = ml.umeyama(male[pid]['pos'], m['pos'])
        m['pos'] = ml.apply_similarity(male[pid]['pos'], s, R, t)
        s2, R2, t2 = ml.umeyama(male[pid]['pos'], m['pos'])
        worst = max(worst, float(np.abs(ml.apply_similarity(male[pid]['pos'], s2, R2, t2) - m['pos']).max()))
        n += 1
    report['rigid_bones'] = {'bones': n, 'max_vertex_error_after_similarity_mm': worst * 1000}
    log('rigid bones', report['rigid_bones'])


def ribs_on_lungs(M, F, report, gap=(0.002, 0.005)):
    """Each rib is translated (rigidly) so its inner surface keeps a 2-5 mm pleural gap outside the
    real HRA lungs: out of the lung if it cuts into it, in toward it if the gap is larger than 5 mm."""
    from scipy.spatial import cKDTree
    lungs = np.vstack([f['pos'] for f in F.values() if f['system'] == 'respiratory' and f['group'] == 'thorax'])
    lc = lungs.mean(0)
    tree = cKDTree(lungs)
    import trimesh
    shells = {}
    for side, sgn in (('L', 1), ('R', -1)):
        pts = [f for f in F.values() if f['system'] == 'respiratory' and f['group'] == 'thorax' and np.sign(f['pos'][:, 0].mean()) == sgn]
        if pts:
            shells[side] = ml.SkinShell(trimesh.util.concatenate([ml.to_trimesh(f['pos'], f['idx']) for f in pts]), pitch=0.003)
    moved = {}
    for pid, m in M.items():
        if not re.search(r'\b(rib)$', m['name'], re.I):
            continue
        side = 'L' if m['pos'][:, 0].mean() > 0 else 'R'
        sh = shells.get(side)
        if sh is None:
            continue
        c = m['pos'].mean(0)
        out = c - lc; out[1] = 0; out /= max(np.linalg.norm(out), 1e-9)
        total = 0.0
        for _ in range(30):
            inside = ~sh.outside(m['pos'], 0.0)
            d, _ = tree.query(m['pos'])
            if inside.any() or d.min() < gap[0]:
                step = 0.0015
            elif d.min() > gap[1]:
                step = -0.0015
            else:
                break
            m['pos'] = m['pos'] + out * step; total += step
        if total:
            moved[m['name']] = round(total * 1000, 1)
    report['ribs_on_lungs'] = {'ribs_moved': len(moved), 'moves_mm': moved}
    log('ribs on lungs', len(moved), 'ribs moved')


def cover_iliac_crests(M, F, report, margin=0.003):
    """Gluteals, tensor fasciae latae and abdominal wall muscles must cover the real iliac crests: any
    such muscle vertex that lies inside the real HRA hip bone is pushed out along the bone surface
    normal (+3 mm), smoothly - the bone never shows through the muscle layer."""
    import trimesh
    hip = trimesh.util.concatenate([ml.to_trimesh(f['pos'], f['idx']) for n, f in F.items() if re.search(r'ilium|ischium|pubis', n)])
    sh = ml.SkinShell(hip, pitch=0.002)
    n = 0
    for m in M.values():
        if not re.search(r'gluteus|tensor fasciae latae|oblique|transversus abdominis|quadratus lumborum|iliacus', m['name'], re.I):
            continue
        if sh.outside(m['pos'], margin).all():
            continue
        m['pos'], _ = ml.push_out(m['pos'], hip, margin=margin, radius=0.02)
        n += 1
    report['iliac_cover'] = {'muscles_adjusted': n}
    log('iliac cover', n)


# ============================================================== VHF body (milestone 5)

def build_warp_vhf(atlas, male, hra, shift, report, registered, every=6):
    """Warp onto the ONE real body (Visible Human Female): the Version 2 correspondences on the real
    HRA VHF skin and pelvis/leg bones, PLUS dense pairs from every BodyParts3D structure that was
    registered onto its VHF CT / HRA shape and passed the gate (every `every`-th vertex)."""
    import trimesh
    by_name = {p['name']: p['id'] for p in atlas['parts']}
    mpos = lambda name: male[by_name[name]]['pos']
    hpos = lambda n: hra[n]['pos'] + shift
    m_skin = ml.to_trimesh(male['FJ2810']['pos'], male['FJ2810']['idx'])
    pos, nrm, idx = ml.weld(hra['VH_F_skin']['pos'] + shift, hra['VH_F_skin']['nrm'], hra['VH_F_skin']['idx'])
    f_skin = trimesh.Trimesh(pos, idx.reshape(-1, 3), process=False)
    C = bw.Correspondences()
    m_hl, _ = ml.femoral_head_centre(mpos('Left femur')); m_hr, _ = ml.femoral_head_centre(mpos('Right femur'))
    f_hl, _ = ml.femoral_head_centre(hpos('VH_F_femur_L')); f_hr, _ = ml.femoral_head_centre(hpos('VH_F_femur_R'))
    lm_pm = ml.pelvis_landmarks(mpos('Left hip bone'), mpos('Right hip bone'), mpos('Sacrum'), m_hl, m_hr)
    fh = {k: np.vstack([hpos(n) for n in v]) for k, v in HRA_PELVIS.items()}
    lm_pf = ml.pelvis_landmarks(fh['hip_L'], fh['hip_R'], fh['sacrum'], f_hl, f_hr)
    keys = sorted(set(lm_pm) & set(lm_pf))
    C.add(np.array([lm_pm[k] for k in keys]), np.array([lm_pf[k] for k in keys]), 'pelvis')
    names_m = {s: {'femur': f'{w} femur', 'tibia': f'{w} tibia', 'fibula': f'{w} fibula', 'patella': f'{w} patella'} for s, w in (('L', 'Left'), ('R', 'Right'))}
    names_f = {s: {'femur': f'VH_F_femur_{s}', 'tibia': f'VH_F_tibia_{s}', 'fibula': f'VH_F_fibula_{s}', 'patella': f'VH_F_patella_{s}'} for s in 'LR'}
    bm = bw.bone_points(mpos, names_m['L'], names_m['R'])
    bf = bw.bone_points(hpos, names_f['L'], names_f['R'])
    bk = sorted(bm)
    C.add(np.array([bm[k] for k in bk]), np.array([bf[k] for k in bk]), 'leg-bones')
    lm_m, lm_f = bw.body_levels(m_skin), bw.body_levels(f_skin)
    lm_m['ankle'] = (bm['tib_bottom_L'][1] + bm['tib_bottom_R'][1]) / 2
    lm_f['ankle'] = (bf['tib_bottom_L'][1] + bf['tib_bottom_R'][1]) / 2
    # Dense pairs from the registered VHF structures (bones, organs, gluteals, iliopsoas, autochthon...).
    n_reg = 0
    for pid, r in registered.items():
        if not r.get('gate') or pid not in male:
            continue
        C.add(male[pid]['pos'][::every], r['pos'][::every], 'vhf-registered')
        n_reg += 1
    boxes = []
    for side in 'LR':
        pts = np.vstack([hpos(n) for n, (s, g) in hra_selected(hra).items() if g == 'breast_' + side])
        boxes.append((pts.min(0) - [0.01, 0.01, 0.0], pts.max(0) + 0.01))
    fat_band = (lm_f['crotch'] - 0.30, lm_pf['iliac_crest_L'][1] + 0.05)
    bw.skin_correspondences(m_skin, f_skin, lm_m, lm_f, C, boxes, 0.008, fat_band, f_skin.vertex_normals)
    src, dst = C.arrays()
    _, uniq = np.unique(np.round(src, 4), axis=0, return_index=True)
    uniq = np.sort(uniq)
    src, dst = src[uniq], dst[uniq]
    tags = np.array(C.tags)[uniq]
    warp = bw.tps(src, dst, smoothing=1e-3)
    resid = np.linalg.norm(warp(src) - dst, axis=1) * 1000
    report['warp'] = {'body': 'vhf', 'correspondences': int(len(src)), 'registered_structures_used': n_reg,
                      'by_group': {t: int((tags == t).sum()) for t in sorted(set(tags))},
                      'residual_mm_mean': float(resid.mean()), 'residual_mm_max': float(resid.max())}
    log('warp', json.dumps(report['warp']))
    STATE['skin_pairs'] = (src[tags == 'skin'], dst[tags == 'skin']) if (tags == 'skin').any() else None
    return warp, f_skin, lm_pf, (m_hl, m_hr, f_hl, f_hr), bm, bf, lm_m, lm_f


def apply_registered(M, registered, hra, shift, report):
    """Structures that passed the gate take their registered (real VHF) shape exactly. Long leg bones
    that failed the gate are shown as the real HRA VHF bone itself (scan-derived), keeping the
    BodyParts3D ID, name and system."""
    used, scan = 0, []
    hra_bones = {f'{sw} {b}': f'VH_F_{b}_{s}' for sw, s in (('Left', 'L'), ('Right', 'R')) for b in ('femur', 'patella', 'tibia', 'fibula')}
    for pid, r in registered.items():
        if pid not in M:
            continue
        if r.get('gate'):
            M[pid]['pos'] = r['pos']; used += 1
        elif M[pid]['name'] in hra_bones:
            h = hra[hra_bones[M[pid]['name']]]
            p, n, i = ml.weld(h['pos'] + shift, h['nrm'], h['idx'])
            M[pid].update(pos=p, idx=i, scan_derived='HRA ' + hra_bones[M[pid]['name']])
            scan.append(M[pid]['name'])
    report['vhf_registered_applied'] = {'gate_pass_applied': used, 'shown_as_scan': scan}
    log('vhf registered applied', used, 'scan-derived bones', len(scan))


FASCIA = re.compile(r'^(?!.*tensor).*(fascia|aponeuros|iliotibial|tract$|retinaculum)', re.I)   # TFL is a muscle


THIGH_SHEET = re.compile(r'iliotibial|fascia lata|fascia of (the )?thigh|crural fascia', re.I)


HIP_MUSCLE = re.compile(r'tensor fasciae latae|gluteus (maximus|medius)', re.I)


def bind_sheets(M, male, report, pattern, offset=0.0008):
    """Milestone 8 round 2: a thigh sheet (IT tract) is bound in the MALE source to the muscles under
    it: each sheet vertex -> nearest triangle of the male muscles (barycentric coordinates + offset along
    the face normal). The binding is evaluated on the same triangles of her warped muscles (same mesh
    topology), so the sheet lies on her muscle surface and stretches only as the muscle does. Its top
    therefore follows TFL / gluteus medius up to the iliac crest instead of standing off."""
    import trimesh
    out = {}
    for pid, m in M.items():
        if not pattern.search(m['name']) or pid not in male:
            continue
        side = 'left' if 'left' in m['name'].lower() else 'right'
        S = male[pid]['pos']
        lo, hi = S.min(0) - 0.04, S.max(0) + 0.04
        tg = [q for q, mm in M.items() if q != pid and q in male and len(male[q]['pos']) == len(mm['pos'])
              and (mm['system'] == 'muscular' or HIP_MUSCLE.search(mm['name'])) and not FASCIA.search(mm['name'])
              and side in mm['name'].lower()
              and np.all(male[q]['pos'].max(0) > lo) and np.all(male[q]['pos'].min(0) < hi)]
        if not tg:
            continue
        Vm, Vf, Fc, off = [], [], [], 0
        for q in tg:
            Vm.append(male[q]['pos']); Vf.append(M[q]['pos']); Fc.append(M[q]['idx'].reshape(-1, 3) + off); off += len(male[q]['pos'])
        Vm, Vf, Fc = np.vstack(Vm), np.vstack(Vf), np.vstack(Fc)
        Um = trimesh.Trimesh(Vm, Fc, process=False)
        cp, d, tri = trimesh.proximity.closest_point(Um, S)
        bc = trimesh.triangles.points_to_barycentric(Vm[Fc[tri]], cp)
        Uf = trimesh.Trimesh(Vf, Fc, process=False)
        base = (Vf[Fc[tri]] * bc[:, :, None]).sum(1)
        nf = Uf.face_normals[tri]
        sgn = np.sign(((S - cp) * Um.face_normals[tri]).sum(1)); sgn[sgn == 0] = 1
        m['pos'] = base + nf * (sgn * offset)[:, None]
        out[m['name']] = {'targets': len(tg), 'male_bind_dist_p95_mm': float(np.quantile(d, 0.95) * 1000)}
    report['sheet_binding'] = out
    log('sheet binding', {k: v['targets'] for k, v in out.items()})


def refit_fasciae(M, report, offset=0.0008, pattern=None, full=False, key='fascia_refit', extra_targets=None, male=None):
    """Fasciae / aponeuroses are never warped freely: each is re-fitted as a thin shell on the outer
    surface of the muscles it covers (closest muscle surface point + 0.8 mm along that face's normal).
    full=True (milestone 7 thigh sheets): every vertex is snapped, so nothing stands off the muscle.
    extra_targets (milestone 8): parts that are muscle but not stored as 'muscular' (the tensor fasciae
    latae is in the connective system), so the upper IT tract lies on TFL and the glutei, not off them."""
    import trimesh
    muscles = [m for m in M.values() if (m['system'] == 'muscular' and not FASCIA.search(m['name']))
               or (extra_targets is not None and extra_targets.search(m['name']))]
    n = 0
    for m in M.values():
        if not FASCIA.search(m['name']) or (pattern is not None and not pattern.search(m['name'])):
            continue
        lo, hi = m['pos'].min(0) - 0.03, m['pos'].max(0) + 0.03
        near = [q for q in muscles if np.all(q['pos'].max(0) > lo) and np.all(q['pos'].min(0) < hi)]
        if not near:
            continue
        U = trimesh.util.concatenate([ml.to_trimesh(q['pos'], q['idx']) for q in near])
        cp, d, tri = trimesh.proximity.closest_point(U, m['pos'])
        out = m['pos'] - cp
        nrm = U.face_normals[tri]
        sgn = np.sign((out * nrm).sum(1)); sgn[sgn == 0] = 1
        new = cp + nrm * sgn[:, None] * offset
        # only snap vertices that are near a muscle (within 2 cm); others keep the warp
        w = np.ones((len(d), 1)) if full else (1 - ml.smoothstep(0.01, 0.02, d))[:, None]
        snapped = m['pos'] * (1 - w) + new * w
        pid = next((k for k, v in M.items() if v is m), None)
        if full and male is not None and pid in male and len(male[pid]['pos']) == len(m['pos']):
            # milestone 8: the snap may not stretch a triangle past 1.9x its source: diffuse the snap
            # displacement over the sheet where it would (the shell then follows the muscle smoothly).
            from scipy.sparse import coo_matrix
            t3 = m['idx'].reshape(-1, 3); n_ = len(m['pos'])
            rr = np.r_[t3[:, 0], t3[:, 1], t3[:, 2], t3[:, 1], t3[:, 2], t3[:, 0]]
            cc = np.r_[t3[:, 1], t3[:, 2], t3[:, 0], t3[:, 0], t3[:, 1], t3[:, 2]]
            A = coo_matrix((np.ones(len(rr)), (rr, cc)), shape=(n_, n_)).tocsr(); A.data[:] = 1.0
            deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
            Dd = snapped - m['pos']
            before = int((edge_ratios(male[pid]['pos'], m['pos'], m['idx']) > 2).any(1).sum())
            for _ in range(200):
                bad_t = (edge_ratios(male[pid]['pos'], m['pos'] + Dd, m['idx']) > 1.9).any(1)
                if int(bad_t.sum()) <= before + 120:   # up to 120 extra per sheet: the top lies on the muscle
                    break
                Dd = 0.5 * Dd + 0.5 * (A @ Dd) / deg[:, None]
            snapped = m['pos'] + Dd
        m['pos'] = snapped
        n += 1
    report[key] = {'parts': n}
    log(key, n)


def vhf_breast_fat(F, M, skin, report, inset=0.0025):
    """Breast fat on the ONE real body: the volume between the real HRA VHF breast skin (inset 2.5 mm)
    and the real chest wall (ray-cast onto pectoralis / serratus / intercostals / ribs, + 3 mm
    retromammary fat). Region = skin over the real HRA breast (within 1.5 cm of its glandular / fat
    parts); thickness tapers smoothly to zero toward the border (no planar faces, no hard edge)."""
    import trimesh
    from scipy.spatial import cKDTree
    wall = trimesh.util.concatenate([ml.to_trimesh(m['pos'], m['idx']) for m in M.values()
                                     if re.search(r'pectoralis|serratus anterior|intercostal|\brib\b|costal cartilage', m['name'], re.I)])
    P = np.asarray(skin.vertices); N = np.asarray(skin.vertex_normals)
    st = [m['pos'] for m in M.values() if re.search(r'sternum|manubrium|xiphoid', m['name'], re.I)]
    sternal_edge = float(np.abs(np.vstack(st)[:, 0]).max()) + 0.004 if st else 0.025
    report['breast_sternal_edge_m'] = sternal_edge
    extra = []
    bshell = [None]; fat_check = {}
    for side, word in (('L', 'Left'), ('R', 'Right')):
        pts = np.vstack([f['pos'] for n, f in F.items() if f['group'] == 'breast_' + side])
        d, _ = cKDTree(pts).query(P)
        # Milestone 8: the footprint is the positive part of ONE smooth field (soft minimum of: nearness
        # to the real breast tissue, distance past the sternal edge, height above the inframammary fold),
        # so its border is a smooth curve (no straight cuts) and the thickness tapers to zero along it.
        sgn = 1 if side == 'L' else -1
        a = (0.012 - d) / 0.012
        # medial border curves laterally above and below the breast centre (a parabola, not a vertical cut)
        yc = float(np.median(pts[:, 1]))
        edge_y = sternal_edge + 0.035 * ((P[:, 1] - yc) / 0.07) ** 2
        b = ((P[:, 0] * sgn) - edge_y) / 0.020
        c = (P[:, 1] - (pts[:, 1].min() - 0.004)) / 0.020
        kk = 6.0
        field = -np.log(np.exp(-kk * a) + np.exp(-kk * b) + np.exp(-kk * c)) / kk
        region = field > 0
        if region.sum() < 50:
            continue
        faces = skin.faces[region[skin.faces].all(1)]
        comp = max(trimesh.Trimesh(P, faces, process=False).split(only_watertight=False), key=lambda c: len(c.faces))
        _, gi = cKDTree(P).query(comp.vertices)
        n = N[gi]
        front = P[gi] - n * inset
        depth = np.full(len(front), np.nan)
        for k in range(0, len(front), 400):          # batched: bounded memory
            loc, ri, _ = wall.ray.intersects_location(front[k:k + 400], -n[k:k + 400], multiple_hits=False)
            depth[k + ri] = np.maximum(np.linalg.norm(loc - front[k + ri], axis=1) - 0.003, 0.0005)
        depth = np.minimum(depth, 0.16)              # this donor's breast reaches > 8 cm from the chest wall
        # rays that missed the wall (grazing angles at the border): use the nearest hit depth
        miss = ~np.isfinite(depth)
        if miss.any() and (~miss).any():
            _, jj = cKDTree(front[~miss]).query(front[miss])
            depth[miss] = depth[~miss][jj]
        depth = np.nan_to_num(depth, nan=0.01)
        # taper: graph distance from the region border (in rings), smooth
        be = np.unique(comp.edges_sorted[trimesh.grouping.group_rows(comp.edges_sorted, require_count=1)])
        ring = np.full(len(gi), 99.0); ring[be] = 0
        nb = comp.vertex_neighbors
        for k in range(1, 22):
            cur = np.where(ring == k - 1)[0]
            for i in cur:
                for j in nb[i]:
                    if ring[j] > k:
                        ring[j] = k
        # Round 1 review: still straight rims. Milestone 8 taper: over 18 rings from the border, over the
        # whole positive range of the footprint field, and toward the sternum over 4 cm, so the thickness
        # reaches zero along a smooth curve with no cut face.
        med = ml.smoothstep(0.0, 0.04, P[gi, 0] * sgn - edge_y[gi])
        t = ml.smoothstep(0, 18, ring) * ml.smoothstep(0.0, 1.0, field[gi]) * med
        thick = 0.0004 + t * depth
        # The deep surface never reaches within 1.2 cm of the midline (the inward normal near the
        # sternum points medially): shorten the depth there.
        nx = -n[:, 0] * sgn
        lim = np.where(nx < -1e-6, (front[:, 0] * sgn - 0.020) / np.maximum(-nx, 1e-6), np.inf)
        thick = np.clip(np.minimum(thick, lim), 0.0002, None)
        back = front - n * thick[:, None]
        nv = len(gi)
        bedges = comp.edges_sorted[trimesh.grouping.group_rows(comp.edges_sorted, require_count=1)]
        sidef = np.vstack([np.c_[bedges[:, 0], bedges[:, 1], bedges[:, 1] + nv], np.c_[bedges[:, 0], bedges[:, 1] + nv, bedges[:, 0] + nv]])
        m = trimesh.Trimesh(np.vstack([front, back]), np.vstack([comp.faces, comp.faces[:, ::-1] + nv, sidef]), process=True)
        trimesh.repair.fix_normals(m)
        trimesh.smoothing.filter_taubin(m, iterations=30)   # round 2: straight rim seen edge-on at the chest wall
        # Milestone 8: nothing outside the skin and nothing within 1 cm of the midline.
        V = np.asarray(m.vertices).copy()
        if bshell[0] is None:
            bshell[0] = ml.SkinShell(skin)
        V = bshell[0].keep_inside(V, margin=0.001)[0]
        bad = np.where(bshell[0].outside(V))[0]
        if len(bad):                       # hard fallback: nearest skin point, 1.5 mm inward
            _, i = bshell[0].tree.query(V[bad])
            V[bad] = bshell[0].skin.vertices[i] - bshell[0].normals[i] * 0.0015
        V[:, 0] = sgn * np.maximum(V[:, 0] * sgn, 0.0105)   # safety only
        m = trimesh.Trimesh(V, m.faces, process=False)
        fat_check[side] = {'outside_skin': int(bshell[0].outside(V).sum()), 'min_abs_x_m': float(np.abs(V[:, 0]).min())}
        w = word.lower()
        extra.append(({'id': f'GEN_breast_adipose_{w}', 'name': f'{word} breast adipose tissue', 'conceptId': f'GEN:breast-adipose-{w}',
                       'system': 'adipose', 'source': 'generated', 'accuracy': 'generated',
                       'note': 'Generated on the real VHF body: the volume between the real breast skin (inset 2.5 mm) and the '
                               'real chest wall (+3 mm retromammary fat), tapering smoothly to the border.'},
                      np.asarray(m.vertices), np.asarray(m.faces).reshape(-1)))
    # The real HRA interlobar fat is replaced by this volume (the brief's breast fat definition).
    for n in [n for n, f in F.items() if f['group'].startswith('breast') and re.search(r'_fat_', n)]:
        F.pop(n)
    report['vhf_breast_fat'] = {'parts': len(extra), 'check': fat_check}
    log('breast fat', fat_check)
    return extra


def vhf_rigid_head(M, male, hra_skin, report):
    """The CT head segmentation is unusable (frozen in a gelatin block). The head is fitted as ONE
    rigid unit (+ uniform scale) to the real VHF head skin: symmetric non-rigid fit of the male head
    skin onto the VHF head skin gives dense pairs; rigid_head() fits one similarity to them."""
    import vhf_register as vr
    J = json.loads((WORK / 'male_pose.json').read_text())['joints']
    ms = male['FJ2810']
    y0 = J['C3'][1] + 0.05
    full = ml.to_trimesh(ms['pos'], ms['idx'])
    keep = ms['pos'][:, 1] > y0
    m_head = full.submesh([np.where(keep[full.faces].all(1))[0]], append=True)
    sel = np.ones(len(m_head.vertices), bool)
    ms = {'pos': np.asarray(m_head.vertices)}
    fv = np.asarray(hra_skin.vertices)
    top = fv[:, 1].max()
    hmask = fv[:, 1] > top - (ms['pos'][:, 1].max() - y0) * 0.97
    tgt = ml.to_trimesh(fv, hra_skin.faces[hmask[hra_skin.faces].all(1)].reshape(-1))
    tgt.remove_unreferenced_vertices()
    X = vr.symmetric_fit(ms['pos'], m_head.vertex_neighbors, tgt, iters=40)
    STATE['dense'] = (ms['pos'][sel], X[sel])
    POSE[0] = {'joints': J}
    rigid_head(M, male, report)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--hra', default=str(ROOT / 'work/sources/hra/3d-vh-f-united.glb'))
    ap.add_argument('--blender', default=None)
    ap.add_argument('--debug-obj', action='store_true')
    ap.add_argument('--resume', action='store_true', help='developer aid: restart after the warp from work/female/stage.pkl')
    ap.add_argument('--body', choices=['hybrid', 'vhf', 'mpfb'], default='hybrid',
                    help='vhf: one real body (Visible Human Female; milestone 5). mpfb: the v4 parametric body.')
    args = ap.parse_args()
    STATE['body'] = args.body
    cfg = json.loads((HERE / 'config.json').read_text())
    WORK.mkdir(parents=True, exist_ok=True)
    atlas, male, hra = load_inputs(args, cfg)
    if args.resume:
        M, F, report, removed, ctx = pickle.loads((WORK / 'stage.pkl').read_bytes())
        POSE[:] = ctx['pose']
    elif args.body in ('vhf', 'hybrid'):
        hybrid = args.body == 'hybrid'
        report = {'body': args.body}
        removed = classify_male(atlas, cfg)
        shift = hra_frame(hra)
        report['frame_shift_m'] = shift.tolist()
        if not (WORK / 'male_pose.json').exists():
            import subprocess
            subprocess.run([sys.executable, str(HERE / 'male_pose.py')], check=True)
        registered = pickle.loads((ROOT / 'work/vhf/registered.pkl').read_bytes())
        if hybrid:
            # Hybrid: NO BodyParts3D structure keeps a non-rigid CT fit (that shredded ribs and spine).
            # Only the real HRA leg bones are taken over (via the failed-gate fallback in apply_registered).
            registered = {k: dict(v, gate=False) for k, v in registered.items()}
        warp, f_skin, lm_pf, heads, bm, bf, lm_m, lm_f = build_warp_vhf(atlas, male, hra, shift, report, registered)
        M = {}
        for p in atlas['parts']:
            if p['id'] in removed:
                continue
            M[p['id']] = {'pos': warp(male[p['id']]['pos']), 'idx': male[p['id']]['idx'], 'name': p['name'], 'system': p['system']}
        log('warped', len(M), 'male parts (%s body)' % args.body)
        if hybrid:
            for m in M.values():               # milestone 7: the IT tract is fascia, not bone
                if re.search(r'iliotibial', m['name'], re.I):
                    m['system'] = 'connective'
                if re.search(r'tensor fasciae latae', m['name'], re.I):
                    m['system'] = 'muscular'   # milestone 8: TFL is a muscle (atlas filed it as connective, so it rendered as a pale plate)
        apply_registered(M, registered, hra, shift, report)
        articulated_arms(M, male, atlas, hra, shift, report)      # arms: rigid segments on the real VHF arm axes
        if hybrid:
            rigidify_bones(M, male, report)                         # every bone: one similarity, never deformed
        vhf_rigid_head(M, male, f_skin, report)
        pin_midline(M, report)
        refit_fasciae(M, report)
        for m in M.values():
            m['warp_pos'] = m['pos'].copy()
        F = place_hra(hra, hra_selected(hra), shift)               # same donor: NO transform
        if hybrid:
            ribs_on_lungs(M, F, report)
            cover_iliac_crests(M, F, report)
        female_shoulder_bulk(M, report, factor=0.9)
        ctx = {'lm_pf': lm_pf, 'heads': heads, 'bm': bm, 'bf': bf, 'lm_m': lm_m, 'lm_f': lm_f, 'pose': [None, None]}
        (WORK / 'stage.pkl').write_bytes(pickle.dumps((M, F, report, removed, ctx)))
    else:
        report = {}
        removed = classify_male(atlas, cfg)
        shift = hra_frame(hra)
        report['frame_shift_m'] = shift.tolist()
        pose_path = WORK / 'male_pose.json'
        if not pose_path.exists():
            import subprocess
            subprocess.run([sys.executable, str(HERE / 'male_pose.py')], check=True)
        _, joints, _ = bt.retarget_hra(hra, shift, pose_path, report, args.blender)
        POSE[:] = [json.loads(pose_path.read_text()), joints]
        shift = np.zeros(3)
        warp, f_skin, lm_pf, heads, bm, bf, lm_m, lm_f = build_warp(atlas, male, hra, shift, report)
        M = {}
        for p in atlas['parts']:
            if p['id'] in removed:
                continue
            m = male[p['id']]
            M[p['id']] = {'pos': warp(m['pos']), 'idx': m['idx'], 'name': p['name'], 'system': p['system']}
        log('warped', len(M), 'male parts')
        bt.SEGS.clear()
        bt.rigid_legs(M, male, POSE[0], POSE[1], {s: lm_pf["acetabulum_" + s] for s in "LR"}, report)
        bt.limb_skinning(M, male, report)          # limb soft tissue follows its rigid bones
        bt.rigid_hands_feet(M, male, POSE[0], POSE[1], report)
        rigid_head(M, male, report)
        pin_midline(M, report)
        for m in M.values():
            m['warp_pos'] = m['pos'].copy()      # for the stretch gate: warp vs later corrections
        F = place_hra(hra, hra_selected(hra), shift)
        fit_head_skin(F, M, report)
        female_shoulder_bulk(M, report)
        ctx = {'lm_pf': lm_pf, 'heads': heads, 'bm': bm, 'bf': bf, 'lm_m': lm_m, 'lm_f': lm_f, 'pose': list(POSE)}
        (WORK / 'stage.pkl').write_bytes(pickle.dumps((M, F, report, removed, ctx)))
    import trimesh
    skin = ml.to_trimesh(F['VH_F_skin']['pos'], F['VH_F_skin']['idx'])
    shell = ml.SkinShell(skin)
    # Femoral heads must sit in the real acetabula.
    fh = {}
    for side, fid in (('L', 'FJ3259'), ('R', 'FJ3365')):
        c, _ = ml.femoral_head_centre(M[fid]['pos'])
        fh[side] = {'warped_head': c.tolist(), 'acetabulum': ctx['lm_pf']['acetabulum_' + side].tolist(),
                    'offset_mm': float(np.linalg.norm(c - ctx['lm_pf']['acetabulum_' + side]) * 1000)}
    report['femoral_heads'] = fh
    seal_uterus(F, report)
    connect_ureters(F, M, report)
    resolve_collisions(F, M, report)
    soft_tissue_off_pelvis(F, M, report)
    if args.body in ('vhf', 'hybrid'):
        breast_extra = vhf_breast_fat(F, M, skin, report)     # real HRA breast set untouched
    else:
        breast_extra = mpfb_breasts(F, M, skin, report)
    # The breasts moved: rebuild the skin shell used by every later containment step.
    skin = ml.to_trimesh(F['VH_F_skin']['pos'], F['VH_F_skin']['idx'])
    shell = ml.SkinShell(skin)
    keep_inside_skin(shell, M, F, report)
    if args.body == 'hybrid':      # milestone 7: thigh sheets as a 0.8 mm shell on the final muscles
        import glute_fit           # milestone 9: her real gluteal muscles (CT), registered on the pelvis only
        M9 = not __import__('os').environ.get('HA_M9_OFF')     # developer aid: build without milestone 9
        if M9:
            glute_fit.pelvis_delta(F, report)
            glute_fit.fit_gluteals(M, F, shell, report, male)
        refit_fasciae(M, report, pattern=THIGH_SHEET, full=True, key='thigh_sheet_refit', extra_targets=HIP_MUSCLE, male=male)
        bind_sheets(M, male, report, re.compile(r'iliotibial', re.I))   # round 2: the IT tract rides on her muscles
        if M9:
            glute_fit.it_shell(M, report, male)                # milestone 9: IT tract on the OUTER muscle surface
            breast_extra = breast_extra + glute_fit.gluteofemoral_fat(F, M, skin, shell, report)
        articulated_hands(M, skin, report, male=male)    # milestone 8: jointed hand fit + bone skinning
    G = generate(F, M, skin, ctx['lm_pf'], report, args.blender)
    check_generated(G, F, M, shell, report)
    # Phase 4: every generated vulval / perineal part stays >= 2 mm inside the body surface.
    gin = {}
    for stem, g in G.items():
        bad = int(shell.outside(g['pos'], 0.002).sum())
        if bad:
            g['pos'], _, left = shell.keep_inside(g['pos'], margin=0.002, radius=0.006)
            gin[stem] = {'vertices_outside': bad, 'left_outside': left}
    report['generated_inside'] = gin
    keep_inside_skin(shell, M, F, report)
    if args.body in ('vhf', 'hybrid'):
        extra = list(breast_extra)        # breast fat (+ hybrid milestone 9: gluteofemoral fat)
    else:
        fv, fi = gluteofemoral_fat(skin, ctx['lm_f'], ctx['lm_pf'])
        extra = [({'id': 'GEN_subcutaneous_fat_gluteofemoral', 'name': 'Subcutaneous fat of hips, buttocks and thighs (female distribution)',
                   'conceptId': 'GEN:subcutaneous-fat-gluteofemoral', 'system': 'integumentary', 'source': 'generated', 'accuracy': 'generated',
                   'note': 'Generated / schematic: the extra gluteofemoral subcutaneous fat (8 mm) between the warped male soft tissue and the scan-derived female skin.'},
                  fv, fi)] + breast_extra
    # Final surveys for VERIFICATION.md.
    fixed = {i: (m['pos'], m['idx']) for i, m in M.items()}
    final = {}
    for label, movers in (('hra-pelvic', {n: (f['pos'], f['idx']) for n, f in F.items() if f['group'] in ('pelvic', 'pelvis')}),
                          ('hra-breast', {n: (f['pos'], f['idx']) for n, f in F.items() if f['group'].startswith('breast')}),
                          ('generated', {'GEN_' + s: (g['pos'], g['idx']) for s, g in G.items()})):
        final[label] = [[a, b, M[b]['name'], M[b]['system']] for a, b in survey(movers, fixed, label)]
    report['final_intersections'] = final
    report['context'] = {k: (v if not isinstance(v, dict) else {kk: (vv.tolist() if isinstance(vv, np.ndarray) else vv) for kk, vv in v.items()})
                         for k, v in ctx.items() if k in ('lm_m', 'lm_f')}
    if args.debug_obj:
        dbg = Path(tempfile.gettempdir()) / 'ha-female' / 'debug'
        dbg.mkdir(parents=True, exist_ok=True)
        for f in dbg.glob('*.obj'):
            f.unlink()
        for pid, m in M.items():
            ml.write_obj(dbg / f"m_{m['system']}_{pid}.obj", m['pos'], m['idx'])
        for n, f in F.items():
            ml.write_obj(dbg / f"f_{f['system']}_{n}.obj", f['pos'], f['idx'])
        for s, g in G.items():
            ml.write_obj(dbg / f"g_{g['system']}_{s}.obj", g['pos'], g['idx'])
    relax_corrections(M, male, shell, report)
    if args.body == 'hybrid':
        import hand_fit
        hand_fit.final_containment(M, shell, report)     # milestone 8: hand soft tissue stays inside
    stretch_report(M, male, report)
    if __import__('os').environ.get('HA_DUMP'):                # developer aid: positions before packaging
        Path(__import__('os').environ['HA_DUMP']).write_bytes(pickle.dumps({k: m['pos'] for k, m in M.items()}))
    write_package(M, F, G, extra, atlas, removed, report)
    (WORK / 'report.json').write_text(json.dumps(report, indent=1, default=float))


if __name__ == '__main__':
    main()
