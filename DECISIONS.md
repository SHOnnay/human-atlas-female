# Decisions — female anatomy model

Each entry gives the decision, the reason and the consequence. Numbers come from `work/female/report.json`, `measurements.json` and `gate_b.json`, written by every build, and are summarised in VERIFICATION.md.

- **Version 1** used the male BodyParts3D body scaled ×0.969 with organs swapped in. It failed review.
- **Version 2** (D21–D32 below) rebuilt the model around the HRA Visible Human Female.
- **Version 3** (D33–D46, first) is the polish milestone. It changes the body surface and replaces every large-rotation and shape-changing step with rigid transforms. Where it conflicts with v2, v3 wins.

## Milestone 6: hybrid body (branch `hybrid`, `--body hybrid`)

**D47. One real donor as the anchor, rigid bones everywhere else.**

Taken as-is from the HRA Visible Human Female, in one consistent space and with no transform:
- her skin and breast set
- pelvis, sacrum, coccyx; femurs, patellae, tibiae, fibulae
- pelvic organs, lungs
- **vertebrae** (25, including a sixth lumbar vertebra — a donor variant) and spinal cord
- liver, gallbladder, pancreas, spleen, colon, small intestine, duodenum
- kidneys (cortex, pyramids, papillae, calyces)
- heart chambers, valves and papillary muscles
- trachea, main bronchi, thymus

The BodyParts3D equivalents are removed, including the male intervertebral discs, so none are left floating among the real vertebrae.

**D48. No non-rigid fitting of any BodyParts3D bone.**
- The milestone 5 CT-registered (CPD/ICP) shapes are not used: that fitting shredded the ribs and spine.
- Every remaining bone (ribs, sternum, costal cartilages, shoulder girdle, arm and hand bones, skull group) moves by one similarity: the best rotation, translation and uniform scale from its male shape to its warped position. The maximum vertex error after a similarity fit is 0 (≈ 5 × 10⁻¹² mm).
- The ribs are then translated rigidly to keep a 2–5 mm pleural gap outside the real HRA lungs.
- The head stays one rigid unit fitted to her real head skin.

**D49. Soft tissue.**
- Muscles, vessels and nerves follow the body warp: Version 2 correspondences on her real skin, pelvis and leg bones.
- The arms are rigid segments on her real A-pose arm axes.
- Fasciae are re-fitted as shells on the muscles they cover.
- Gluteals, tensor fasciae latae, obliques, transversus, quadratus lumborum and iliacus are pushed off the real hip bones (+3 mm), so they cover the iliac crests.
- Bone-attached limb skinning (v4) needs the MPFB rig joints, which this body does not have. It is not used; limb soft tissue follows the warp.

**D50. Breast fat.** One closed volume, only under skin within 1 cm of her real breast tissue (no shell toward the axilla), on the ray-cast chest wall. The real HRA lobes are not moved.

**D51. Vulva and perineum from cryosections — not done.**
- The full-colour cryosections are indexed and can be downloaded slice by slice.
- At the downsampled scale used for the section check, the crura, bulbs and labia are not separable by colour. Segmenting them needs full-resolution, slice-by-slice work that did not fit this milestone.
- The generated set (published dimensions, anchored to her real pubic arch and skin) remains, labelled generated.

**D52. Section check aligned regionally.**
- Bone Dice is computed after translating the CT bone mask onto the model's local bone (spine, pelvis, femur, tibia, humerus, radius/ulna) within that level's window.
- Body Dice is informational only: the cadaver was frozen supine, so her soft tissue is flattened.

## Version 3 (polish milestone)

**D33. Root cause: the pose. The body is now MPFB2's average adult female, posed by its rig into the male pose.**
The HRA female stands with abducted arms and wide-apart knees, so the v2 spline had to absorb large rotations. Those rotations sheared the hands, bent the spine and smeared the thighs.

v3 generates the body with **MPFB2** (MakeHuman; CC0 assets; the GPL add-on is used only as a tool) via `scripts/female/create_mpfb_body.py`:
- female, 25 years, average proportions
- stature 1.63 m; BMI 22.5 kg/m² (mass = closed volume × 1010 kg/m³), the brief's target
- weight is bisected first; when the weight slider saturates, muscle is bisected

Its **default rig is posed so that every bone points like the matching male bone**:
- upper arm, forearm and wrist (with palm roll)
- the four metacarpals and every phalanx
- neck and head

The legs take a natural female stance: knee centres 11 cm apart and ankles 9 cm apart, from the wider female hip joints. Where the thighs press together, each side is flattened onto its own side of the midline (`flatten_thigh_contact`, using rest-pose sides) instead of interpenetrating.

So large rotations are done by bones, never by the spline. Consequences:
- The skin is now **generated** (source `mpfb`), not scan-derived. This contradicts v2's "keep the HRA skin"; the brief's own root-cause fix requires a re-posed body, and the HRA scan has no rig.
- The HRA skin is no longer packaged.

**D34. Dense correspondences through a same-topology pair replace hand-tuned contour pairs.**
The same script also builds:
- **an MPFB male** fitted to the BodyParts3D male: stature, then weight and muscle by grid search on mid-sagittal torso and thigh depths, with legs posed like the male
- **the same female with a flat chest** (cup size 0)

All three meshes share one topology (53,514 vertices). The MPFB male is fitted to the BodyParts3D skin by:
1. a similarity ICP
2. a smooth non-rigid ICP (neighbourhood-averaged closest-point steps, outliers over 4 cm rejected)

That fit brings the median gap down from 8 mm to about 2 mm. Then each 2 cm cell gives one pair: *BodyParts3D male skin point → flat-female vertex with the same index*. About 4,400 pairs are used, plus rig joints (shoulder, elbow, wrist, knee, ankle, C3/C5/C7) offset like the male joint. The warp target is the **flat** female, so the chest wall is not pulled into the breasts.

**D35. Rigid parts are rigid.** Every bone that changed shape in v2 now gets a rotation plus *uniform* scale only:
- **Hands and feet:** each metacarpal and phalanx is anchored on its MPFB rig bone, proximal end on the joint, axis along the bone, with the male palm or sole normal for roll, and scaled by the rig-bone length. One limb-level similarity, with a common scale left/right, carries the carpals and tarsals. Soft tissue past the wrist or ankle follows by **linear blend skinning** (inverse-distance weights to the male bone axes).
- **Long bones:** femur + patella, tibia + fibula, humerus, radius + ulna. Each is a minimal rotation from the male segment onto the female one, which keeps the male axial roll so the patella faces forward. The female segments run real HRA acetabulum → rig knee → rig ankle, and shoulder → elbow → wrist.
- **The head:** one similarity fitted on the head and face pairs, plus heavily weighted eye anchors to the MPFB eye joints. It is blended into the neck between C3 and 5 cm above. Parts lying wholly in the head (skull, mandible, teeth, eyes, ears) are fully rigid. The jaw therefore keeps its closed male relation; brow and jaw become female only by the overall head scale, labelled "warped approximation".
- **Inside-skin correction for bones and sense organs:** translation first, then, only if needed, a uniform shrink about the centroid. They are never squashed vertex by vertex (in v2 that stretched eye parts up to 128×).

Gate: every hand and foot bone's PCA aspect ratios are within 3% of the male's. The measured maximum is in VERIFICATION.md.

**D36. Spine and sternum are pinned to the mid-sagittal plane.**
The lateral offset of each midline bone (vertebrae, sacrum, coccyx, sternum) is removed rigidly. The smoothed offset profile is subtracted from nearby tissue with a 7 cm Gaussian falloff, so the ribs and linea alba follow without tearing.

**D37. HRA pelvic organs move as one rigid block, without scale.**
The bony pelvis takes the pelvic similarity (acetabula → MPFB hip joints, plus front and back skin). The uterus, adnexa, vagina, bladder and uterine vessels keep their scanned size: their block centroid goes where the similarity sends it, and the block is only rotated.

The lungs and breast glands keep a uniform-scale similarity; a similarity is shape-preserving, and they must fit the smaller thorax.

**D38. Breasts are rebuilt on the parametric body.**
- **Breast mound and nipple level:** the mound is the exact difference between the female and flat-chest meshes. It is moved along the chest wall (resampled, so its shape is unchanged) until the nipple lies midway between the warped 4th and 5th ribs, i.e. the 4th intercostal space.
- **Adipose body:** the skin over the mound inset 4 mm, closed by a back surface 8 mm under the flat chest (on pectoralis major), lateral to the sternal edge, Taubin-smoothed so there are no hard edges. It is its own **Adipose tissue** system (pale yellow, `#eedc9a`). In the app it turns 22% opaque whenever a structure inside it is selected.
- **Areola** (19 mm disc lifted 0.2–1.2 mm off the skin) and **nipple** (5 mm capsule along the skin normal): generated meshes on the skin surface.
- **Glands:** the HRA glands, ducts and Cooper's ligaments are carried rigidly with one uniform scale, so their nipple meets the new nipple, and kept inside the fat. The HRA fat, areola and nipple are dropped.

**D39. Clitoris, bulbs and vulva are placed on the true midline of the parametric body.**
The vulva landmarks use only exactly mid-sagittal skin vertices (the MPFB mesh is symmetric). In v2 a 6 mm band could pick up inner-thigh skin. The pudendal cleft (8.5 cm, 7 mm deep) is indented on those vertices.

The crura now follow the ischiopubic rami from 15% to 85% of the symphysis–ischial tuberosity distance. Glans, body and crura and the vestibular bulbs are in a new **Erectile tissue** system (`#8e4f7a`), distinct from the uterus.

**D40. Ureters follow the lateral pelvic wall.**
Below the pelvic brim each warped ureter is re-routed along a path:
- in front of the common iliac bifurcation (at least 4.5 cm from the midline)
- down the lateral pelvic wall (1.2 cm medial to the hip bone)
- to the ureteric orifice

The cross-section is kept. The gate checks that neither ureter ever crosses the midline.

**D41. Breast position, uterus size and Q-angle are measured, not forced.**
The measurement table reports:
- nipple level against the warped ribs
- breast footprint (ribs 2–6, sternal edge to mid-axillary line)
- clitoral and crus length
- uterine dimensions, version and flexion
- the stretch gate (no warped triangle edge over 2× its source)

Values that miss a cited range are reported as such, with their cause, in VERIFICATION.md.

**D42. The web app can be photographed from the same cameras as the Blender composites.**
`?debug` now exposes `__atlasRenderer.camera / filter / opacity`. `scripts/female/capture_webapp.py` uses those calls to render, in headless Chromium, every Blender category and view from the same directions, with the same part sets and the same 40% skin.

## Version 2

## Body and frame

**D21. The body is the real Visible Human Female, taken from HRA, at native scale.**
The HRA female skin is one watertight, scan-derived surface: 382,640 triangles and 166.6 cm tall. It is closed at the vulva, mons and perineum, and has a female silhouette, with narrower shoulders than hips, a waist, wide hips, gluteofemoral fat and breasts with volume. It is the body surface ("Skin").

The whole HRA assembly keeps its native scale and mutual positions, only translated so the feet rest on y = 0. That covers the skin, pelvis, sacrum, coccyx, uterus/adnexa/ligaments, vagina, bladder, uterine vessels, breasts and lungs. Uniform scaling is removed entirely.

MakeHuman/MPFB2 (CC0) was considered and not used: Step 2 prefers the scan, and a real body beats a parametric average.

**D22. Every other structure is BodyParts3D male anatomy carried into this body by one thin-plate-spline warp.**
The warp (`scripts/female/body_warp.py`) uses about 800 correspondences, all extracted automatically by the same algorithm on both bodies:
- 27 pelvic landmarks (male hip bones → **real HRA pelvis**)
- femoral heads, greater trochanters, condyles, epicondyles, patellae, tibial plateaus, plafonds and malleoli (male → **real HRA lower-limb bones**)
- ribs 5, 8 and 10 lateral extremes → HRA lungs + 12 mm
- torso contours: 24 rays at 12 heights
- neck and head contours, plus vertex, nose and occiput
- leg contours: 16 rays at 9 heights per leg
- arm axes and perimeters: 14 stations per arm
- heel, toe and sole points

Male femoral heads therefore land in the real acetabula; the female acetabular width is 19.2 cm, against 17.5 cm male. Brow ridges, jaw and laryngeal prominence follow the female head and neck surface, labelled "warped approximation". The mean fit residual is under 1 mm. Every warped part is labelled `warped` in the metadata and the UI.

**D23. Breast regions are excluded from the torso correspondences.**
This keeps the chest wall following the ribs instead of being pulled into the breasts.

**D24. Extra female fat sits under the skin.**
In the gluteofemoral band, from the iliac crest down to 30 cm below the crotch, female skin targets are set 8 mm inside the skin. The warped male soft tissue therefore stops short of the skin, and the gap is filled by a **generated subcutaneous fat shell** (8 mm, tapered). Elsewhere the inset is 2 mm.

**D25. Arms are articulated, not warped.**
The pose changes from the male's hanging arms to the female's A-pose. A smooth warp sheared the forearm and crumpled the hand bones, as seen in the gate C images.

Upper arm, forearm and hand now move as rigid segments about the male shoulder, elbow and wrist (from the humerus and radius). Those joints map to the same arc-length positions on the female arm axis. The segments blend over ±2 cm at each joint, and into the body warp at the shoulder.

Parts are assigned to an arm by distance to the male arm axis, so the thigh beside the hanging male hand is never moved.

## Real female pelvis, organs, breasts and lungs

**D26. The pelvis is the real HRA female pelvis.**
It consists of the left and right ilium, ischium and pubis (compact bone), the sacrum and the coccyx. The morphed male pelvis has been removed. The "Left/Right hip bone" concepts (FMA16587/16586) now group the real bones.

Warped male muscles, vessels and nerves that cut into the real bones are pushed onto the bone surface (`soft_tissue_off_pelvis`).

**D27. Pelvic organs keep their real positions and scale.**
In the HRA assembly the uterus is anteverted over the bladder, the cervix sits in the vaginal vault and the ovaries lie at the lateral pelvic walls. No shrinking or re-placement was needed.

Cracks between uterine pieces are closed (`seal_uterus`): vertices within 2.5 mm of a neighbouring piece are projected onto it. Each piece stays a separate selectable structure.

**D28. Breasts are the real HRA glands, ducts, adipose body and Cooper's ligaments.**
The breast adipose body is in the **Connective tissue** system, which is visible by default, so the breasts show volume.

Where the warped chest wall still met the fat, the warped pectoral muscles were pushed back, and the breast as a whole was moved forward by the measured amount. The HRA lactiferous ducts and sinuses reach the nipple surface in the source; they are kept 1.5 mm inside the skin.

**D29. Real lungs added.**
BodyParts3D models only the bronchial trees. All HRA bronchopulmonary segments and hila are included as scan-derived lung tissue.

## Generated structures

**D30. Anything still missing is generated and labelled.**
To make the anatomy complete for students, Blender scripts generate:
- the vulva (labia majora as fat pads about 1 cm under the skin, labia minora and the vestibule inside the cleft)
- the clitoris (glans under the prepuce about 7 mm deep, body, crura along the real ischiopubic rami)
- the prepuce
- the vestibular bulbs
- Bartholin's and Skene's glands
- the mons pubis fat pad
- the perineal body
- the female urethra
- the female ischiocavernosus and bulbospongiosus
- the ovarian arteries and veins (from the aorta below the renal arteries, and to the IVC / left renal vein, over the suspensory ligament to the ovary)

Each is collision-checked against bone, thigh muscles, organs and, for the ovarian vessels, the retroperitoneal structures. A voxel test keeps each inside the skin, it is Taubin-smoothed, and then re-checked. Dimensions and sources are in DATA_SOURCES.md.

## Labels

**D31. Every structure carries one provenance label, in metadata (`accuracy`) and in the UI badge.**
- **Scan-derived:** 100 HRA meshes.
- **Warped approximation:** 2,199 BodyParts3D meshes.
- **Generated · schematic:** 28 meshes.

`validate-atlas.mjs` enforces that the label matches the source, and that the skin and hip-bone concepts are the real HRA ones.

## Measurement honesty

**D32. Real scan geometry is not bent to meet a target range.**
Three gate A values fall outside the cited female ranges:
- **Q-angle 10.5°:** set by the real VHF patella and knee positions. She stood with her knees 23 cm apart, so the femurs barely converge toward the knees (obliquity 2.7°).
- **Shoulder/hip ratio 0.848:** the donor's skin hip breadth is 41.3 cm.
- **Subpubic angle 111°:** passes the ≥80° rule but is above the 80–100° textbook band; this is the real VHF arch.

These are reported as properties of this one real donor (59 years old, broad-hipped). The alternatives were adjusting HRA bones or skin, or switching measure definitions until the values passed, and both would misrepresent the data.

## Pipeline and app

The earlier decisions still apply, renumbered where needed:
- D13: FMA IDs only from OLS
- D14: a parallel script plus `build-anatomy.py --sex female`
- D16: Blender on a short path
- D17–D20: toggle, scene lifecycle, selection carry-over, WebMCP `body`

The male files are not modified.
