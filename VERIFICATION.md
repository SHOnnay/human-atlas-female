# Verification — female anatomy model

## Milestone 5: one real body (Visible Human Female), branch `vhf-real`, 2026-11-22

**Merge decision: NOT merged.** The rule was "merge only if the reviewer scores beat v4 on every area". They do not: the head scores 0/3 here against 4/5 in v4. main stays at v4 (tag `v4-mpfb`, 1b3a2fc); this work is on the `vhf-real` branch.

### Data and pipeline (Steps 1–5)

**Data:**
- VHF CT: IDC collection `nlm_visible_human_project`, patient VHP-F — two series, head→femur (985 slices, 0.94 × 0.94 × 1.01 mm) and femur→toes (749 slices).
- Colour cryosections: 5,186 slices at 0.33 mm, indexed from DICOM headers only; slices downloaded on demand.
- Courtesy of the U.S. National Library of Medicine.

**Segmentation:** TotalSegmentator `total` (Apache-2.0) on the CUDA GPU (RTX 4070), about 90 s per volume. No licensed tasks were used.

**Registration (Step 2):**
- The cadaver was CT-scanned frozen in a gelatin block, so the CT "body outline" is the block. The CT is therefore registered to the HRA frame on bone.
- Head→femur: TotalSegmentator hips, sacrum and femurs against the HRA pelvis and femurs. Rigid, no scale. Median bone-to-bone distance 4.2 mm, 90th percentile 10.5 mm.
- Femur→toes: **FAILED** (median 32 mm). The HRA VHF femur, patella, tibia and fibula (same donor) are used as leg targets instead.

**Per-structure registration (Step 4):**
- BodyParts3D structures were registered onto the VHF segment meshes (symmetric non-rigid ICP after a similarity fit) and gated at mean ≤ 2 mm, 95% Hausdorff ≤ 5 mm, plus an extent sanity check. The pass list is in `work/vhf/register_report.json`.
- The femurs, tibiae, fibulae and patellae failed the gate and are shown as the real HRA VHF bones, labelled scan-derived, with the BodyParts3D IDs kept.
- **Head CT targets unusable:** the CT "skull" segment is 27 × 21 × 36 cm (gelatin block artefact). The head was instead fitted as one rigid unit to the real VHF head skin — **approximate**.

**Body (Step 3):** the real HRA VHF skin and the real HRA breast set, with no transform. MPFB is removed from `--body vhf`.

**Warp (Step 5):** the Version 2 skin, pelvis and leg-bone correspondences plus dense pairs from every structure that passed. Fasciae are re-fitted as shells on the muscles they cover. Arms are rigid segments on the real VHF arm axes.

### Step 8C gates

| Gate | Target | Result |
|---|---|---|
| Parts through the skin | 0 | **78 FAIL** (76 warped, 2 generated) |
| Floating parts | 0 | 0 PASS |
| Warped triangles stretched > 2× | ≤ 0.05% | **6.2% FAIL** (135,344 / 2,166,224) |
| BodyParts3D IDs, names and systems kept | all | PASS (validator) |
| Package download | ≤ 40 MB | 28.7 MB PASS |

### Step 8A sections

These are model outlines against the real body: body outline against the VHF cryosection photo, bones against the VHF CT. Overlays are in `docs/screenshots/sections/`.

**Gates:** body Dice ≥ 0.95, bone Dice ≥ 0.85. **Both FAIL at every level.**

Two limits of the method:
- The cryosection height and in-plane placement are fitted per slice (translation and flips only).
- The leg levels lie outside the CT volume used for bone.

| Level | Body Dice | Bone Dice |
|---|---|---|
| C5 | 0.37 | 0.05 |
| T4 (nipple) | 0.79 | 0.19 |
| T10 | 0.75 | 0.17 |
| L3 | 0.68 | 0.28 |
| S1 | 0.77 | 0.33 |
| Pubic symphysis | 0.85 | 0.49 |
| Perineum | 0.81 | 0.30 |
| Mid-thigh | 0.34 | n/a |
| Knee | 0.07 | n/a |
| Mid-calf | 0.07 | n/a |
| Mid-upper-arm | 0.77 | 0.26 |
| Mid-forearm | 0.67 | 0.19 |
| Wrist | 0.82 | 0.49 |

What the overlays show:
- At L3 the real frozen body, in both CT and cryosection, is visibly wider than the HRA skin.
- The model's lumbar vertebrae sit about 2–3 cm anterior to the CT's.

So the HRA meshes, the CT and the cryosections do not share one consistent geometry under a rigid transform. Resolving this needs a deformable CT↔HRA registration, which is not done.

### Step 8E reviewers (round 1 of up to 5; one fresh subagent per area)

| Area | v4 (last result) | VHF round 1 |
|---|---|---|
| Whole body | 2/10 in the v3 overall review | 0/4 |
| Breasts | 0/5 | 1/4 (nipple and areola pass) |
| Pelvis and perineum | Phase 4: 0/5 on the vulva and uterus items | 0/3 |
| Limbs and hands | Phase 4: 0/5 on hands | 1/3 (leg bones pass) |
| Head and neck | **4/5** | 0/3 |
| Abdomen and organs | not reviewed | 0/3 |

**Not done in this milestone:**
- Step 6, segmenting the perineum from the cryosections: the vulva, clitoris and bulbs are still the generated structures anchored to the real pelvis and skin.
- Step 8B, the population check: the 23.6 GB TotalSegmentator dataset was not downloaded; the female pelvic MRI dataset is of endometriosis patients and is not a normal reference.
- Further review rounds (2–5) and web-app captures for this branch.

## Milestone 4 (phased), 2026-11-21

Each phase was judged by a fresh reviewer subagent that saw only that phase's screenshots (`docs/screenshots/compare/`, `docs/screenshots/webapp/`) and checklist. A phase gets at most 3 rounds.

### Phase 1 — Breasts: **FAILED after 3 rounds (0/5, 0/5, 0/5)**

**Data used.**
- The HRA set has a complete real breast for each side: interlobar fat, mammary lobes, main lactiferous ducts and sinuses, suspensory (Cooper's) ligaments, nipple, areola and areolar tubercles.
- The real lobes, ducts, sinuses and ligaments are used, placed by one rigid transform plus one uniform scale per side.
- The breast fat is generated: the volume between the chest wall (ray-cast onto pectoralis, serratus, intercostals and ribs, plus 3 mm) and the breast skin inset 2.5 mm, with the thickness tapering to zero at the border.
- The areola and nipple are generated from the skin surface.

**What changed across the rounds.**
- Round 1: the fat floated in front of the chest wall. Fixed by ray-casting the fat's back surface onto the real chest wall.
- Round 2: the fat was a wedge, the areola rim was spiky and the glands sprayed out. Changed: the mound displacement field is smoothed into a dome, the areola and nipple are single surfaces, and the gland scale is 0.8.

**Round 3 still fails all five items.**

| Item | Verdict | Reviewer's reason |
|---|---|---|
| B1 shape | FAIL | Side views still read as a truncated wedge with planar faces |
| B2 areola and nipple | FAIL | The nipple sits as a knob on a disc; a spike under the areola in the web app |
| B3 lobes | FAIL | Lobes cluster above the nipple; the lower breast is empty; the bundle floats in front of the chest wall in side view |
| B4 colours | FAIL | Fat looks khaki in Blender (pale yellow in the web app); lobe and duct colours are distinct |
| B5 artefacts | FAIL | Spur under the areola, stepped cut-outs in the fat, hard silhouette |

Root cause (not fixed): the MPFB breast skin mound is conical, and the real HRA gland comes from a larger, older donor breast, so it does not fit a generated 22.5-BMI breast. **The breasts remain approximate.**

### Phase 2 — Skin layer: **PASSED (3/3, round 1)**

| Item | Verdict |
|---|---|
| S1 translucent skin with readable silhouette, anatomy visible | PASS |
| S2 no z-fighting or sorting artefacts | PASS |
| S3 same treatment on both bodies | PASS |

Implementation:
- The skin is shown by default at 20% opacity with a Fresnel rim light.
- It is drawn last, with depth writes off.
- Picking skips the skin whenever solid structures are visible.
- A "Skin opacity" slider (0–100%) sits in the systems panel, is stored in localStorage behind try/catch, and has a 44 px touch target on mobile.

### Phase 3 — Head: **4/5 after 3 rounds (0/5 → 2/5 → 4/5)**

| Item | Final verdict |
|---|---|
| H1 skull is one intact rigid unit | PASS |
| H2 teeth in sockets, jaw closed | PASS |
| H3 orbits not crushed, eyes in place | PASS |
| H4 head proportion and smooth head skin | PASS |
| H5 natural neck | **FAIL** — strap-like structures run from the neck to the shoulders/scapula |

Fixes that got here:
- The skull, mandible, teeth, eyes, ears and brain move as ONE rigid group with one transform.
- They are never shifted part by part, and never smoothed by the stretch relaxation.
- The MPFB head skin is enlarged about the skull centre, blended to zero across the neck and capped at 1.10, until less than 0.5% of skull vertices are outside it.
- Any residual protrusion of the head group (lips, nose tip) is reported, not hidden by breaking the skull.

### Phase 4 — Remaining fails: **1/5 after 3 rounds (0/5 → 0/5 → 1/5)**

| Item | Final verdict | Reviewer's reason |
|---|---|---|
| P1 hands and forearms | **FAIL** | Forearm muscles form a stretched loop above the wrist; hand bones cluster |
| P2 clitoris, crura, bulbs | **FAIL** | Labial/bulb pieces read as hanging below the vulva outline; erectile plum not distinct enough in Blender |
| P3 uterus vs bladder | **FAIL** | The anteverted uterus covers the ochre bladder in the front views |
| P4 deltoids and pectorals | PASS | Deltoids reduced radially (×0.75) toward the humeral axis |
| P5 no protrusions or smeared strips | **FAIL** | Sheet-like strips along the femurs; forearm sheets |

What changed in this phase:
- **Limbs:** limb soft tissue now follows the rigid long bones (bone-attached skinning).
- **Pelvic connective tissue:** the uterine ligaments and peritoneal pouches are connective tissue, so the 14 cm broad ligament no longer hides the bladder.
- **Generated vulval parts:** kept at least 2 mm inside the skin. 0 generated parts protrude.

**Still failing:** the forearm and thigh "sheets" (warped BodyParts3D fasciae and long muscles), crus and bulb placement, and the bladder's visibility behind the uterus.

### Final gates (milestone 4)

**Containment** (after simplification, packaged meshes):
- 96 of 2,325 parts have some vertices through the skin — all warped BodyParts3D parts, including head parts left in place by design.
- 0 floating parts.
- 0 generated parts protrude.

**Stretch:**
- 6,979 of 2,169,868 warped triangles (0.32%) are over 2× their source; v3 had 12,953.
- The zero target is not met.

**Checks:**
- `npm run check`, both validators, `npm run build` and `scripts/verify-browser.py` (headless Chromium) pass.
- The male package files are unchanged.

## Version 3 (polish milestone), 2026-11-21

Produced by `python scripts/build-anatomy.py --sex female`, which builds the model and runs the validators and gates A and B. Every number comes from `work/female/measurements.json`, `gate_b.json` and `report.json`.

### A. Composites
- **Blender, same camera:** `docs/screenshots/compare/` (41 images) — all-systems, skin-only and skeleton-only (front, side, back, oblique); hand (palm, dorsum, front, back); breast with fat on and off (front, side); vulva with the skin at 40% (front, below, oblique); uterus isolated; head skeleton; pelvis and perineum.
- **Web app (B):** `docs/screenshots/webapp/` (41 images) — the same categories, views and part sets, captured from `npm run dev` in headless Chromium through the `?debug` capture API.

### C. Measurements (female; cited ranges in `scripts/female/measure.py`)

| Measure | Female | Range | Result |
|---|---|---|---|
| Stature | 163.9 cm | 150–178 | pass |
| BMI | 22.5 | 21–24 (target 22–23) | pass |
| Biacromial / hip ratio | 33.4 cm / 0.9 | 32–41 / 0.85–1.10 | pass |
| Waist circumference | 71.4 cm | 62–110 | pass |
| Inlet transverse / AP | 12.5 / 10.6 cm | 11.5–14.5 / 10–12.5 | pass |
| Q-angle | 12.0° (L 10.2°, R 13.8°); knees 12.0 cm apart, femoral obliquity 5.1° (male 10.7°) | 11–21 (brief: ~15–17) | pass, below the brief's 15–17° target |
| Subpubic angle | 118° | 80–100 | **fail**: the real VHF pelvis, not altered |
| Clitoral length (glans + body + crus) | 9.5 cm | 9–11 (O'Connell 2005) | pass |
| Crus length | 5.3 / 6.1 cm | 5–9 | pass |
| Uterus L × W × AP | 6.3 × 4.3 × 2.7 cm | 6.5–9 × 4–6 × 2–4 | **length fail**: the real VHF uterus, rigid, no scale |
| Uterus | anteverted 67° from vertical; cervix in the vaginal vault | — | pass; anteflexion is only 1° (the VHF uterus is straight) |
| Nipple level | 1.232 m, between the 4th (1.265) and 5th (1.206) ribs | 4th intercostal space | pass |
| Breast footprint | ribs 2–6 (1.317–1.171 m); medial edge 3.3 cm, lateral to the sternal edge at 2.5 cm; lateral edge 13.7 cm (mid-axillary line 19.9 cm) | ribs 2–6, sternal edge → mid-axillary | pass. The lateral edge stops short of the mid-axillary line |
| Ureters | never cross the midline (closest 17 mm and 20 mm) | lateral | pass |
| Hand and foot bone aspect ratios | 75 of 76 within 3 %; right 5th metatarsal 3.4 % (after simplification) | ≤ 3 % | 1 marginal |

### D. Containment and mesh quality
- **Floating parts:** 0.
- **Protruding parts:** 25 of 2,325 parts (22 warped, 3 generated) still have a few vertices outside the skin after simplification. The fix (3 mm margin, rigid group moves) removed the lung protrusions; these residuals remain.
- **Stretch gate (no edge over 2× its source):** not met. 12,953 of 2,169,868 warped triangles (0.6 %) exceed 2×, mostly in the pharynx and palate. They come from fitting the rigid head group inside the smaller MPFB face. The body warp itself now stretches 130 parts, down from 225 before regularization.
- **Validators:** `validate-atlas.mjs` passes for the male and female packages, as does `tsc --noEmit`. The male package files are unchanged (`git status` shows no changes under `public/models` outside `female/`).

### E. Independent review (v3, round 1) — **2/10 pass**
A fresh subagent was given only the 82 screenshots and the 10-issue list. Verdicts:
1. Pose — PASS
2. Hands — FAIL (carpals bunched, fingers thin and splayed)
3. Breasts — FAIL (angular fat, hard edges, V-notch between the breasts)
4. Vulva — FAIL (structures hang below the vulva skin; erectile colour too close to the uterus)
5. Uterus — FAIL (round pink organ over the bladder; elongated uterus)
6. Neck — FAIL (shards above the clavicles)
7. Limb mesh — FAIL (smeared forearm sheet, fragments beside the femurs)
8. Knees — PASS
9. Body — FAIL (chest shape, wide deltoids)
10. Ureters PASS but face — FAIL (broken facial skeleton, jumbled teeth)

**The acceptance loop is not complete: 8 issues still fail.** They are recorded here unmodified.

# Version 2

Run on 2026-11-20 with Windows 10, Node 24.11, Python 3.12, Blender 4.2.23 LTS, and Playwright with headless Chromium (software WebGL).

Evidence levels:
- **[V]**: validation script
- **[B]**: build or gate script (`work/female/*.json`)
- **[H]**: headless browser
- **[I]**: images reviewed by me
- **[—]**: not tested

Nothing was tested on physical devices or by an anatomist.

## Gate D — commands

| Command | Result |
|---|---|
| `npm run check` | pass |
| `node scripts/validate-atlas.mjs` | pass. Male: 2,234 meshes, 3,432 concepts, 2,288,268 triangles, unchanged. Female: 2,327 meshes, 3,524 concepts, 2,052,290 triangles. Every buffer is valid, every mesh is labelled scan-derived/warped/generated consistently with its source, the skin and hip bones are the real HRA ones, there are no male-only structures, and all 31 checklist structures are present and searchable. |
| `node scripts/validate-interactions.mjs` | pass, for both bodies: packing, search/inspect, WebMCP `body` (sync and lazy), selection carry-over, taps |
| `npm run build` | pass |
| `python scripts/verify-browser.py` | see "Browser" below |
| Male files | byte-identical to the base commit (`git diff 1c38bf3 -- public/models/atlas.json public/models/body-*` is empty) |

**Size:**

| | Male | Female |
|---|---|---|
| Triangles | 2,288,268 | 2,052,290 |
| Download (gzip) | 33.0 MB | 30.1 MB |

## Gate A — measurements [B] (`python scripts/female/measure.py`, the same code for both bodies)

| Measure | Male | **Female** | Female reference range (source) | Result |
|---|---|---|---|---|
| Height | 171.9 cm | **166.6 cm** | 150–178 cm (NHANES 2015–18, Fryar 2021) | PASS |
| Biacromial width (over the acromia, skin) | 36.8 cm | **35.0 cm** | 32–41 cm (ANSUR II, Gordon 2014) | PASS |
| Ribcage width (ribs, skeletal) | 27.3 cm | **27.4 cm** | 22–30 cm (Bellemare 2003) | PASS. Note: not narrower than the BodyParts3D male, which is itself narrow. |
| Waist circumference (minimum, skin) | 77.2 cm | **93.6 cm** | 62–110 cm (NHANES) | PASS |
| Bi-iliac (intercristal) | 29.0 cm | **31.7 cm** | 25–32 cm (pelvimetry texts) | PASS |
| Bitrochanteric | 30.0 cm | **35.2 cm** | 29–37 cm | PASS |
| Shoulder-to-hip ratio (biacromial / skin hip breadth 41.3 cm) | 1.1 | **0.85 (0.848)** | 0.85–1.10 (derived from ANSUR II) | **FAIL by 0.002**: this donor's hips are broad |
| Pelvic inlet, transverse (arcuate lines) | 11.2 cm | **13.9 cm** | 11.5–14.5 cm (Gray's; Williams Obstetrics) | PASS |
| Pelvic inlet, AP (true conjugate) | 10.0 cm | **11.6 cm** | 10.0–12.5 cm | PASS |
| Subpubic angle (AP-radiograph method) | 52° | **111°** | ≥ 80° gate; textbook band 80–100° | **Gate ≥ 80° PASS**, but above the textbook band. This is the real VHF arch (projection plot checked). |
| Q-angle | 10.7° | **10.5°** | 11–21° (Horton & Hall 1989: 15.8 ± 4.5°) | **FAIL** |

Supporting values:
- **Acetabular width:** 17.5 cm male against 19.2 cm female.
- **Femoral shaft obliquity:** 1.8° male against 2.7° female.
- **Knee separation:** 14.8 cm male against 22.9 cm female.

**Honest reading:** the pelvis, inlet, outlet, hips and silhouette are clearly female. The **femurs do not angle inward to the knees** in this model. The real VHF donor stood with her knees 23 cm apart, so her femoral shafts are nearly vertical and the Q-angle stays at 10.5°.

I did not alter the real bones or skin to reach 15–17°. That would require changing the scan-derived knee and skin positions, which misrepresents the data (DECISIONS D32). If a population-typical Q-angle matters more than a real donor, the fix is an MPFB2 (CC0) average female body. See README "Known limitations".

## Gate B — collisions and floating parts [B] (`python scripts/female/gate_checks.py`)

| Check | Female | Male baseline |
|---|---|---|
| Parts with vertices outside the skin (all scan-derived, warped and generated parts; skin surface details excluded) | **0** | not measurable: the BodyParts3D skin is not watertight, so its voxel fill fails and all 2,227 parts register as "outside" |
| Floating parts (no other part within 5 mm) | **0** | 0 |

Remaining triangle intersections between neighbouring structures (`work/female/report.json → final_intersections`):
- **HRA pelvic vs warped (180 pairs).** Most are warped male muscles meeting the real female pelvic bones at their attachments (piriformis, gemelli, gluteals, iliacus, psoas, levator ani) after the push-off step. Thin peritoneal and ligament sheets touch vessels and the ureter, which is anatomical contact.
- **Breast vs chest wall (24 pairs).** The deep surface of the breast adipose body meets pectoralis and costal cartilages.
- **Generated vs warped (36 pairs).** Ovarian vessels on psoas, crossing the ureter and external iliac vessels, and behind the duodenum and colon: their real course. Also the left labium majus fat pad touching the great saphenous vein.
- **Generated vs scan-derived organs:** not intersecting (the build pushes them apart).

Depth of generated perineal structures below the skin [B]:
- glans 4–10 mm
- vestibule 4–12 mm
- crura 19–43 mm
- bulbs 12–27 mm

Every part sits above the lowest perineal skin point (y = 0.655 m), so **nothing hangs below the perineum**.

## Gate C — male vs female, same camera [I] (`docs/screenshots/compare/`, also `female-review.zip`)

One line per image: does it read as female, and what is still wrong.

| Image | Verdict |
|---|---|
| all-systems_front | **Female**: breasts with volume, waist, wide hips, uterus and adnexa in the pelvis, A-pose. Wrong: the hands look rough; the facial musculature covers the skull less completely than in the male. |
| all-systems_side | **Female**: breast projection, protruding abdomen and gluteal curve of the real donor. Wrong: the neck musculature looks thin. |
| all-systems_back | **Female** proportions. Wrong: the gluteal muscles are stretched into broad flat plates by the warp. |
| all-systems_oblique | **Female**. Wrong: rough hands; the warped thigh muscles look smoother and less defined than the male's. |
| skin-only_front | **Female** (real VHF scan): breasts, waist, wide hips, closed smooth vulva and mons. No holes. |
| skin-only_side | **Female**. Accurate to the donor: protruding abdomen and pendulous breasts (age 59). |
| skin-only_back | **Female**: gluteofemoral shape, wider hips than shoulders. |
| skin-only_oblique | **Female**. No defects seen. |
| skeleton-only_front | **Female**: wide real pelvis, broad pubic arch, the skull with its brow and jaw taking on the female head shape. Wrong: hand bones compressed and boxy; the ribcage is not narrower than the male's; the femurs do not converge to the knees (knees 23 cm apart). |
| skeleton-only_side | **Female**. Wrong: the iliotibial tract (skeletal system) renders as a broad plate along the thigh. |
| skeleton-only_back | **Female** pelvis and sacrum. Wrong: the lumbar spine shows a slight lateral kink from the warp; boxy hand bones. |
| skeleton-only_oblique | **Female**. Same hand and thigh-plate issues. |
| pelvis-closeup_front | **Female**: real wide pelvis, uterus over the bladder, tubes and ovaries at the lateral walls, real kidneys and ureters; femoral heads in the acetabula. Wrong: the generated labia hang 2–7 cm below the arch along the cleft, which is correct for the vulva but looks long in isolation; flat iliotibial plates. |
| pelvis-closeup_side | **Female**: anteverted uterus, real sacral curve. Wrong: the thigh plates are distracting. |
| pelvis-closeup_back | **Female** sacrum and coccyx. No other issue seen. |
| pelvis-closeup_oblique | **Female**. Wrong: as front. |
| perineum-closeup_front | **Female**: the vulva and clitoral complex lie in the pubic arch at the perineum. Wrong: the left labium minus reaches about 5 cm lower than the right (residual asymmetry). |
| perineum-closeup_below | **Female**: crura along the ischiopubic rami, bulbs beside the vestibule, mons pad over the symphysis, levator ani around the vagina. Wrong: the image is busy; the mons pad shows as a flat disk. |
| perineum-closeup_side | **Female**. Wrong: thigh plates obscure it. |
| perineum-closeup_back | **Female** (coccyx, levator ani, perineal body). No other issue seen. |
| perineum-closeup_oblique | **Female**. Wrong: as front. |
| breast-closeup_front | **Female**: the adipose body covers the glands and rests on pectoralis major over about ribs 2–6. Wrong: the cervical region looks spiky in this framing (cropped neck muscles). |
| breast-closeup_side | **Female**: breast projection, glands inside the fat, no gap to the chest wall. Wrong: as front. |
| breast-closeup_back | Shows the back of the ribcage and scapulae; the breasts are hidden. Not informative, and nothing wrong seen. |
| breast-closeup_oblique | **Female**. Wrong: as front. |

**Overall:** no image reads as male in silhouette or pelvis. The remaining visual defects are:
- compressed hand bones
- flat iliotibial and gluteal plates from the warp
- a ribcage no narrower than the male
- knees that do not converge
- a left labium minus asymmetry

They are listed in README "Known limitations".

## Browser [H]

`python scripts/verify-browser.py` against `npm run dev` with the final package passes. Screenshots are in `docs/screenshots/`.

- **Selection carry-over:** Heart selected on the male body stays selected after switching to female. The URL becomes `?body=female` and localStorage stores `female`. Uterus selected, then switching to male, gives the toast "Uterus is not part of the male model." and clears the selection.
- **Badge:** the clitoris shows the **"Generated · schematic"** badge; every structure shows its provenance badge.
- **WebMCP:** `find_anatomy({query:'ovary', body:'female'})` from the male view returns female results. `{query:'uterus'}` on the male body returns `[]`. `inspect_anatomical_structure({body:'female'})` switches the body.
- **Memory over 10 switches (`renderer.info`, after forced GC):**
  - Geometries, textures and programs return to each body's value (male 73/3/6), with one canvas throughout.
  - Listeners stay flat (544), and DOM nodes level at 340.
  - The JS heap drifts 22.3 → 25.4 MB. The intended manifest cache explains part of this; the rest is unexplained, so a slow JS-side leak is not fully ruled out.
- **Console:** no errors (only SwiftShader ReadPixels performance notes).

## Not tested [—]

Physical devices, native WebMCP, and anatomist review.

## Milestone 6: hybrid body (branch `hybrid`) — NOT merged

Build: `python scripts/build-anatomy.py --sex female --body hybrid`. 2,384 parts: bp3d 2,031, hra 324 (scan-derived), generated 29.

### Gates
| Gate | Target | Result |
|---|---|---|
| Bone rigidity (max vertex error after similarity fit, 238 bones) | < 0.1 mm | 5e-12 mm — PASS |
| Ribs outside lungs | 2–5 mm | 24 ribs adjusted |
| Muscles covering iliac crests | — | 12 muscles pushed off |
| Through skin (except eyes/teeth) | 0 | 73 parts (72 bp3d, 1 generated) — FAIL |
| Floating | 0 | 0 — PASS |
| Stretch > 2x | ≤ 0.1% | 13,048 / 1,969,056 = 0.66% — FAIL |
| Vulva from cryosections | done | not done (generated set kept, D51) — FAIL |

### Sections (regionally aligned bone Dice; gate ≥ 0.70)
| Level | Body Dice (info) | Bone Dice |
|---|---|---|
| C5 | 0.347 | 0.501 |
| T4 | 0.780 | 0.344 |
| T10 | 0.727 | 0.263 |
| L3 | 0.678 | 0.410 |
| S1 | 0.750 | 0.168 |
| Pubic symphysis | 0.835 | 0.500 |
| Perineum | 0.758 | 0.317 |
| Mid-thigh | 0.338 | 0.396 |
| Knee / mid-calf | 0.04 | n/a (CT registration failed) |
| Mid-upper-arm | 0.769 | 0.005 |
| Mid-forearm | 0.660 | 0.025 |
| Wrist | 0.794 | 0.056 |
| Mid-hand | 0.837 | 0.000 |

All levels fail the bone gate. The arm levels fail because the cadaver's arms lie at her sides in the CT, while the model is in A-pose.

### Fresh reviewers (1 round, v4 vs hybrid side by side)
| Area | Better | Hybrid |
|---|---|---|
| Whole body | v4 | FAIL |
| Breasts | v4 | FAIL (midline shell, low/medial) |
| Pelvis/perineum | v4 | FAIL (vulva below pubic arch) |
| Limbs/hands | v4 | FAIL (scattered hand bones) |
| Head/neck | hybrid | PASS |
| Abdomen/organs | v4 | FAIL |

Merge rule (better in ≥ 5/6 areas, none worse) **fails, 1/6**. The branch was pushed; main is unchanged. Further rounds were not run because the result could not reach 5/6 without rework.

Tests: npm run check, validate-atlas, validate-interactions, npm run build and verify-browser all pass.

## Milestone 7: breast fat, hands/forearms, thigh sheets, framing (branch `hybrid`, not merged by rule)

### Gates
| Gate | Target | Result |
|---|---|---|
| Parts through skin | no increase from 73; zero among touched parts | **101 — FAIL**. 81 are hand/forearm parts, mostly finger bones and small digital vessels: a rigid male hand does not fit inside her skin fingers, even after searching rotation about the wrist. The breast fat accounts for 1 (10 vertices). |
| Stretch (> 2×) | ≤ 0.66 % | 9,689 / 1,969,056 = **0.49 % — PASS** |
| Floating | 0 | 0 — PASS |
| Rigid bones | similarity error < 0.1 mm | 5e-12 mm — PASS |
| npm run check, validate-atlas, validate-interactions, build, verify-browser | pass | **all PASS** |
| Male package | unchanged | unchanged |

Section Dice is information only (overlays in docs/screenshots/sections/).

### Reviewers (round 1 of up to 3; further rounds not run)
| Item | vs previous hybrid | vs v4 | Verdict | Main remaining defect |
|---|---|---|---|---|
| 1 Breast fat | improved | same | FAIL | A thin translucent strip still crosses the midline at the xiphoid |
| 2 Hands/forearms | improved | better | FAIL | Finger soft tissue splays out; a loose sheet sits by the thumb; carpals are offset in palm views |
| 3 Thigh sheets | improved | better | FAIL | The IT tract is gone from skeleton-only, but its upper end flares off the muscle above the trochanter |
| 4 Framing | improved | better | FAIL | Body views are fixed; hand views still frame the whole forearm |
| No-regression | — | — | Head, spine, ribs and pelvic organs unchanged (uterus images identical pixel for pixel) | The only change flagged is the intended removal of the IT-tract plates from the leg views |

Each reviewer listed every image it viewed. Those lists are in the milestone report.
