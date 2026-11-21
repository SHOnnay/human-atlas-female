"""Joint centres and bone axes of the BodyParts3D male (atlas frame: metres, Y up, +z anterior).

Used to pose the MPFB2 female into the same pose (create_mpfb_body.py) and to map every hand and
foot bone rigidly (build_female.py). Joints are derived from the bones themselves:
  * long bones / phalanges / metacarpals / metatarsals: principal axis (PCA) endpoints; the proximal
    end is the one nearer the parent joint;
  * shoulder: sphere fit of the humeral head; elbow: distal humerus; wrist: distal radius+ulna;
  * hip: femoral head sphere fit; knee: femoral condyles; ankle: distal tibia;
  * neck: cervical vertebral bodies; head: skull (frontal + parietal + occipital) centroid and top.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import meshlib as ml  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FINGERS = {'thumb': 1, 'index finger': 2, 'middle finger': 3, 'ring finger': 4, 'little finger': 5}
TOES = {'big toe': 1, 'second toe': 2, 'third toe': 3, 'fourth toe': 4, 'little toe': 5}
ORD = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5}


def axis_ends(v, parent):
    c = v.mean(0)
    _, _, vt = np.linalg.svd(v - c, full_matrices=False)
    a = vt[0]
    t = (v - c) @ a
    p0, p1 = c + a * np.percentile(t, 2), c + a * np.percentile(t, 98)
    return (p0, p1) if np.linalg.norm(p0 - parent) <= np.linalg.norm(p1 - parent) else (p1, p0)


def male_pose(atlas, M):
    names = {p['name'].lower(): p['id'] for p in atlas['parts']}
    get = lambda n: M[names[n.lower()]]['pos']
    out = {'bones': {}, 'joints': {}}
    for side, word in (('L', 'left'), ('R', 'right')):
        hum, rad, uln = get(f'{word} humerus'), get(f'{word} radius'), get(f'{word} ulna')
        sh, _ = ml.femoral_head_centre(hum)
        elbow = hum[np.argsort(np.linalg.norm(hum - sh, axis=1))[-200:]].mean(0)
        fa = np.vstack([rad, uln])
        wrist = fa[np.argsort(np.linalg.norm(fa - elbow, axis=1))[-200:]].mean(0)
        out['joints'][f'shoulder.{side}'] = sh; out['joints'][f'elbow.{side}'] = elbow; out['joints'][f'wrist.{side}'] = wrist
        # Hand: metacarpals and phalanges (axis ends, proximal = nearer the wrist / previous joint).
        for fname, k in FINGERS.items():
            prev = wrist
            seq = []
            if k == 1:
                seq = [f'{word} first metacarpal bone', f'proximal phalanx of {word} thumb', f'distal phalanx of {word} thumb']
            else:
                mc = {2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth'}[k]
                seq = [f'{word} {mc} metacarpal bone', f'proximal phalanx of {word} {fname}',
                       f'middle phalanx of {word} {fname}', f'distal phalanx of {word} {fname}']
            for j, n in enumerate(seq):
                if n.lower() not in names:
                    continue
                p0, p1 = axis_ends(get(n), prev)
                out['bones'][n] = {'id': names[n.lower()], 'p0': p0, 'p1': p1, 'finger': k, 'index': j, 'side': side}
                prev = p1
        # Leg.
        fem, tib = get(f'{word} femur'), get(f'{word} tibia')
        hip, _ = ml.femoral_head_centre(fem)
        knee = fem[fem[:, 1] < fem[:, 1].min() + 0.02].mean(0)
        ankle = tib[tib[:, 1] < tib[:, 1].min() + 0.02].mean(0)
        out['joints'][f'hip.{side}'] = hip; out['joints'][f'knee.{side}'] = knee; out['joints'][f'ankle.{side}'] = ankle
        # Foot: metatarsals and toe phalanges.
        for tname, k in TOES.items():
            prev = ankle
            mt = {1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth'}[k]
            seq = [f'{word} {mt} metatarsal bone', f'proximal phalanx of {word} {tname}']
            if k != 1:
                seq.append(f'middle phalanx of {word} {tname}')
            seq.append(f'distal phalanx of {word} {tname}')
            for j, n in enumerate(seq):
                if n.lower() not in names:
                    continue
                p0, p1 = axis_ends(get(n), prev)
                out['bones'][n] = {'id': names[n.lower()], 'p0': p0, 'p1': p1, 'toe': k, 'index': j, 'side': side}
                prev = p1
    cerv = [n for n in names if re.fullmatch(r'(first|second|third|fourth|fifth|sixth|seventh) cervical vertebra', n)]
    order = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh']
    cerv.sort(key=lambda n: order.index(n.split()[0]))
    for n in cerv:
        v = get(n)
        out['joints'][f'C{order.index(n.split()[0]) + 1}'] = v.mean(0)
    skull = np.vstack([get(n) for n in ('frontal bone', 'occipital bone', 'left parietal bone', 'right parietal bone') if n in names])
    out['joints']['skull_centre'] = skull.mean(0)
    out['joints']['vertex'] = skull[np.argmax(skull[:, 1])]
    return out


def male_fit(skin):
    """Targets for fitting the MPFB male to the BodyParts3D male skin: stature, and mid-sagittal
    torso depths (|x| < 2 cm) at chest/waist/hip and thigh depths (|x| = 9 cm) - arms excluded."""
    st = float(np.ptp(skin[:, 1]))
    levels = []
    for kind, f in (('torso', 0.74), ('torso', 0.68), ('torso', 0.62), ('torso', 0.53), ('thigh', 0.40), ('thigh', 0.34)):
        y = skin[:, 1].min() + f * st
        if kind == 'torso':
            band = skin[(np.abs(skin[:, 0]) < 0.02) & (np.abs(skin[:, 1] - y) < 0.01)]
        else:
            band = skin[(np.abs(np.abs(skin[:, 0]) - 0.09) < 0.02) & (np.abs(skin[:, 1] - y) < 0.01)]
        levels.append([kind, float(y), float(np.ptp(band[:, 2]))])
    return {'stature': st, 'levels': levels}


def main():
    atlas, M = ml.load_package(ROOT / 'public/models/atlas.json')
    pose = male_pose(atlas, M)
    conv = lambda o: o.tolist() if isinstance(o, np.ndarray) else o
    data = {'joints': {k: conv(v) for k, v in pose['joints'].items()},
            'bones': {k: {kk: conv(vv) for kk, vv in v.items()} for k, v in pose['bones'].items()},
            'male_fit': male_fit(M['FJ2810']['pos'])}
    out = ROOT / 'work/female/male_pose.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1))
    print('joints', len(data['joints']), 'bones', len(data['bones']))


if __name__ == '__main__':
    main()
