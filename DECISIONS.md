# Decisions — female anatomy model (version 2)

The first version used the male BodyParts3D body scaled ×0.969 with organs swapped in, and it failed review. Version 2 rebuilds the model around the real female body. Each entry gives the decision, the reason and the consequence. Numbers come from `work/female/report.json`, `measurements.json` and `gate_b.json`, written by every build, and are summarised in VERIFICATION.md.

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
