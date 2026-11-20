# Verification — female anatomy model (version 2)

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
