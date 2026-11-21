"""MPFB2 (MakeHuman; CC0 assets) bodies posed into the BodyParts3D male pose - three meshes with
IDENTICAL topology, which give the female warp a dense vertex-to-vertex correspondence:

  mpfb_male.obj         male (gender 1) fitted to the BodyParts3D male: stature, then weight and
                        muscle so its mid-sagittal torso depths and thigh depths match; arms, hands,
                        neck, head AND legs posed like the BodyParts3D male.
  mpfb_skin.obj         average adult female (gender 0, age 25, proportions 0.5, cup/firmness 0.5),
                        stature 1.63 m, BMI 22.5 kg/m^2 (mass = volume x 1010 kg/m^3); arms, hands,
                        neck and head posed like the male; legs keep the female stance.
  mpfb_female_flat.obj  the same female with cup size 0 (flat chest): target of the internal warp,
                        so the male chest wall is not pulled into the breasts.

blender -b -P scripts/female/create_mpfb_body.py -- MALE_POSE.json OUT_DIR [BMI] [STATURE_M]
(needs the MPFB2 extension, i.e. without --factory-startup.)

Outputs (atlas frame: x, y up, z anterior; metres): the three OBJs, mpfb_joints.json (female rig),
mpfb_male_joints.json, mpfb_info.json.
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

argv = sys.argv[sys.argv.index('--') + 1:]
pose = json.loads(Path(argv[0]).read_text())
out = Path(argv[1]); out.mkdir(parents=True, exist_ok=True)
TARGET_BMI = float(argv[2]) if len(argv) > 2 else 22.5
STATURE = float(argv[3]) if len(argv) > 3 else 1.63
KNEE_X, ANKLE_X = 0.055, 0.045      # female stance (half-distances, m)
FIRMNESS = 1.0                      # breast firmness: nipple at the 4th intercostal space

from bl_ext.user_default.mpfb.services.humanservice import HumanService  # noqa: E402


def B(p):  # atlas -> Blender
    return Vector((p[0], -p[2], p[1]))


def A(v):  # Blender -> atlas
    return [v.x, v.z, -v.y]


def make(macro):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    m = {'gender': 0.0, 'age': 0.5, 'muscle': 0.5, 'weight': 0.5, 'proportions': 0.5, 'height': 0.5,
         'cupsize': 0.5, 'firmness': 0.5, 'race': {'asian': 0.33, 'caucasian': 0.33, 'african': 0.33}}
    m.update(macro)
    extra = {k: m.pop(k) for k in list(m) if k.startswith('target:')}
    hum = HumanService.create_human(macro_detail_dict=m, feet_on_ground=True, scale=0.1)
    if extra:
        from bl_ext.user_default.mpfb.services.targetservice import TargetService
        for k, w in extra.items():
            name = k.split(':', 1)[1]
            TargetService.load_target(hum, TargetService.target_full_path(name), weight=w, name=name)
        bpy.context.view_layer.update()
    return hum


def body_mesh(obj):
    """Evaluated body-only triangles (helpers/joints masked out) in Blender coordinates."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    vg = obj.vertex_groups.get('body')
    bm = bmesh.new(); bm.from_mesh(me)
    deform = bm.verts.layers.deform.active
    if vg is not None and deform is not None:
        drop = [f for f in bm.faces if not all(v[deform].get(vg.index, 0.0) > 0.5 for v in f.verts)]
        bmesh.ops.delete(bm, geom=drop, context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    verts = [ev.matrix_world @ v.co for v in bm.verts]
    faces = [[v.index for v in f.verts] for f in bm.faces]
    bm.free(); ev.to_mesh_clear()
    return verts, faces


def volume(verts, faces):
    return abs(sum(verts[a].dot(verts[b].cross(verts[c])) for a, b, c in faces) / 6.0)


def stature(verts):
    zs = [v.z for v in verts]
    return max(zs) - min(zs)


def bmi_of(hum):
    v, f = body_mesh(hum)
    return volume(v, f) * 1010 / stature(v) ** 2, stature(v)


def bisect(fn, target, lo=0.0, hi=1.0, n=8):
    """Monotone increasing fn: slider in [lo, hi] with fn(slider) ~ target."""
    for _ in range(n):
        mid = (lo + hi) / 2
        if fn(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def depths(verts, levels):
    """Mid-sagittal torso depth (|x| < 2 cm) and thigh depth at x = +-9 cm, at given heights (Blender z)."""
    res = []
    for kind, z in levels:
        if kind == 'torso':
            band = [v for v in verts if abs(v.x) < 0.02 and abs(v.z - z) < 0.01]
        else:
            band = [v for v in verts if abs(abs(v.x) - 0.09) < 0.02 and abs(v.z - z) < 0.01]
        res.append(max(v.y for v in band) - min(v.y for v in band) if band else 0.0)
    return res


# ------------------------------------------------------------------ posing

def pose_body(hum, legs):
    rig = HumanService.add_builtin_rig(hum, 'default', import_weights=True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')
    J = {k: B(p) for k, p in pose['joints'].items()}
    BN = {k: {'p0': B(b['p0']), 'p1': B(b['p1'])} for k, b in pose['bones'].items()}

    def head_tail(name):
        pb = rig.pose.bones[name]
        return rig.matrix_world @ pb.head, rig.matrix_world @ pb.tail

    def rotate_bone(name, R):
        bpy.context.view_layer.update()
        pb = rig.pose.bones[name]
        M = rig.matrix_world @ pb.matrix
        head = M.translation.copy()
        pb.matrix = rig.matrix_world.inverted() @ (Matrix.Translation(head) @ R.to_4x4() @ Matrix.Translation(-head) @ M)
        bpy.context.view_layer.update()

    def align(name, direction, upto=None):
        h0, t0 = head_tail(name)
        if upto:
            t0 = head_tail(upto)[1]
        rotate_bone(name, (t0 - h0).normalized().rotation_difference(direction.normalized()).to_matrix())

    def roll_about(name, want, have):
        h, t = head_tail(name)
        ax = (t - h).normalized()
        a = (have - ax * have.dot(ax)).normalized(); b = (want - ax * want.dot(ax)).normalized()
        rotate_bone(name, Quaternion(ax, math.atan2(ax.dot(a.cross(b)), a.dot(b))).to_matrix())

    for s, word in (('L', 'left'), ('R', 'right')):
        sh, el, wr = J[f'shoulder.{s}'], J[f'elbow.{s}'], J[f'wrist.{s}']
        align(f'upperarm01.{s}', el - sh, upto=f'upperarm02.{s}')
        align(f'lowerarm01.{s}', wr - el, upto=f'lowerarm02.{s}')
        align(f'wrist.{s}', BN[f'proximal phalanx of {word} middle finger']['p0'] - wr)
        m2, m5 = BN[f'{word} second metacarpal bone'], BN[f'{word} fifth metacarpal bone']
        want = (m2['p1'] - m2['p0']).cross(m5['p0'] - m2['p0'])
        f2h, f2t = head_tail(f'metacarpal1.{s}'); f5h, _ = head_tail(f'metacarpal4.{s}')
        roll_about(f'wrist.{s}', want, (f2t - f2h).cross(f5h - f2h))
        for k, mc in ((2, 'second'), (3, 'third'), (4, 'fourth'), (5, 'fifth')):
            b = BN[f'{word} {mc} metacarpal bone']
            align(f'metacarpal{k - 1}.{s}', b['p1'] - b['p0'])
            fname = {2: 'index finger', 3: 'middle finger', 4: 'ring finger', 5: 'little finger'}[k]
            for j, ph in enumerate(('proximal', 'middle', 'distal')):
                b = BN.get(f'{ph} phalanx of {word} {fname}')
                if b:
                    align(f'finger{k}-{j + 1}.{s}', b['p1'] - b['p0'])
        for j, n in enumerate((f'{word} first metacarpal bone', f'proximal phalanx of {word} thumb', f'distal phalanx of {word} thumb')):
            b = BN.get(n)
            if b:
                align(f'finger1-{j + 1}.{s}', b['p1'] - b['p0'])
        hp, kn, an = J[f'hip.{s}'], J[f'knee.{s}'], J[f'ankle.{s}']
        if legs == 'male':
            align(f'upperleg01.{s}', kn - hp, upto=f'upperleg02.{s}')
            align(f'lowerleg01.{s}', an - kn, upto=f'lowerleg02.{s}')
        elif legs == 'female':
            # Natural female stance: knee centres 11 cm apart (medial condyles almost touching) and
            # ankles 9 cm apart, from the wider female hip joints - the thigh converges on the knee
            # (genu valgum, the larger female Q-angle). The thigh contact is flattened afterwards
            # (body_target.flatten_thigh_contact) so the skin never interpenetrates.
            sg = 1 if s == 'L' else -1
            fh, _ = head_tail(f'upperleg01.{s}')
            d, e = kn - hp, an - kn
            knee_t = Vector((sg * KNEE_X, fh.y + d.y, fh.z + d.z))
            align(f'upperleg01.{s}', knee_t - fh, upto=f'upperleg02.{s}')
            align(f'lowerleg01.{s}', Vector((sg * ANKLE_X - knee_t.x, e.y, e.z)), upto=f'lowerleg02.{s}')
    if 'C7' in J and 'vertex' in J:
        top = J.get('C1', J.get('C3'))
        align('neck01', top - J['C7'], upto='neck03')
        align('head', J['vertex'] - top)
    bpy.ops.object.mode_set(mode='OBJECT')
    return rig


def export(hum, rig, name, joints_name=None, header=''):
    if not any(m.type == 'SUBSURF' for m in hum.modifiers):
        sub = hum.modifiers.new('subd', 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
    # Rest-pose side of every vertex (left/right leg), for the thigh-contact flattening.
    arm = [m for m in hum.modifiers if m.type == 'ARMATURE']
    for m in arm:
        m.show_viewport = False
    rest, _ = body_mesh(hum)
    for m in arm:
        m.show_viewport = True
    (out / name.replace('.obj', '_restx.txt')).write_text('\n'.join(f'{p.x:.5f}' for p in rest))
    v, f = body_mesh(hum)
    with (out / name).open('w') as fh:
        fh.write(f'# {header} MPFB2 (MakeHuman) CC0 assets, posed to the BodyParts3D male pose.\n')
        for p in v:
            a = A(p); fh.write(f'v {a[0]:.6f} {a[1]:.6f} {a[2]:.6f}\n')
        for t in f:
            fh.write(f'f {t[0] + 1} {t[1] + 1} {t[2] + 1}\n')
    if joints_name:
        J = {}
        for pb in rig.pose.bones:
            J[pb.name] = {'head': A(rig.matrix_world @ pb.head), 'tail': A(rig.matrix_world @ pb.tail)}
        (out / joints_name).write_text(json.dumps(J))
    return len(v), len(f)


info = {}
# ---- female: stature, BMI (weight, then muscle if weight saturates).
h = bisect(lambda x: bmi_of(make({'height': x}))[1], STATURE)
w = bisect(lambda x: bmi_of(make({'height': h, 'weight': x}))[0], TARGET_BMI, n=9)
mu = 0.5
if bmi_of(make({'height': h, 'weight': w}))[0] < TARGET_BMI - 0.3 and w > 0.95:
    mu = bisect(lambda x: bmi_of(make({'height': h, 'weight': w, 'muscle': x}))[0], TARGET_BMI, 0.5, 1.0, n=7)
fem = {'height': h, 'weight': w, 'muscle': mu}
bmi, st = bmi_of(make(fem))
info['female'] = dict(fem, stature_m=st, bmi=bmi, density_kg_m3=1010)
info.update({'muscle_slider': mu, 'height_slider': h, 'weight_slider': w, 'stature_m': st, 'bmi': bmi})
print('MPFB_INFO', json.dumps(info))
hum = make(dict(fem, firmness=FIRMNESS)); rig = pose_body(hum, legs='female')
info['female']['vertices'], info['female']['triangles'] = export(hum, rig, 'mpfb_skin.obj', 'mpfb_joints.json', 'Average adult female.')
hum = make(dict(fem, cupsize=0.0, firmness=1.0)); rig = pose_body(hum, legs='female')
info['female_flat'] = dict(fem, cupsize=0.0)
info['female_flat']['vertices'], _ = export(hum, rig, 'mpfb_female_flat.obj', None, 'Same female, flat chest (warp target).')

# ---- male fitted to the BodyParts3D male.
T = pose['male_fit']
hm = bisect(lambda x: bmi_of(make({'gender': 1.0, 'height': x}))[1], T['stature'])


def err(wt, mus):
    v, _ = body_mesh(make({'gender': 1.0, 'height': hm, 'weight': wt, 'muscle': mus}))
    d = depths(v, [(k, z) for k, z, _ in T['levels']])
    return sum((a - t) ** 2 for a, (_, _, t) in zip(d, T['levels']))


best = None
for wt in (0.2, 0.35, 0.5, 0.65, 0.8):
    for mus in (0.3, 0.5, 0.7):
        e = err(wt, mus)
        if best is None or e < best[0]:
            best = (e, wt, mus)
_, wt, mus = best
for step in (0.08, 0.04, 0.02):          # local refinement
    for dw, dm in ((step, 0), (-step, 0), (0, step), (0, -step)):
        a, b = min(max(wt + dw, 0), 1), min(max(mus + dm, 0), 1)
        e = err(a, b)
        if e < best[0]:
            best = (e, a, b); wt, mus = a, b
male = {'gender': 1.0, 'height': hm, 'weight': wt, 'muscle': mus}
hum = make(male)
info['male'] = dict(male, rms_depth_error_m=math.sqrt(best[0] / len(T['levels'])))
rig = pose_body(hum, legs='male')
info['male']['vertices'], _ = export(hum, rig, 'mpfb_male.obj', 'mpfb_male_joints.json', 'Male fitted to BodyParts3D.')
(out / 'mpfb_info.json').write_text(json.dumps(info, indent=1))
print('MPFB_DONE', json.dumps(info))
