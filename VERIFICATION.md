# Verification — female anatomy model

Run on 2026-11-20 on Windows 10 with Node 24.11, Python 3.12 and Blender 4.2.23 LTS. Playwright drove headless Chromium with software WebGL (SwiftShader).

**Evidence levels**:
- **[V]**: validation script, deterministic; run with `node scripts/validate-*.mjs`
- **[B]**: build-time geometric check; output in `work/female/report.json`
- **[H]**: headless browser (`scripts/verify-browser.py`)
- **[I]**: I inspected the image
- **[—]**: not tested

Nothing was tested on a physical phone, a GPU or real multitouch hardware.

## Commands

| Command | Result |
|---|---|
| `npm run check` | pass (tsc, no errors) |
| `node scripts/validate-atlas.mjs` | pass: male 2,234 meshes / 3,432 concepts / 2,288,268 triangles; female 2,287 / 3,497 / 2,503,013; all buffers, indices and concept memberships valid |
| `node scripts/validate-interactions.mjs` | pass: packing at 3 aspect ratios for both bodies and every system, search/inspect contracts, WebMCP `body` (sync and lazy), selection carry-over, tap handling |
| `npm run build` | pass (same chunk-size warning as the baseline) |
| `python scripts/verify-browser.py` | pass (screenshots below, `work/browser-report.json`) |

Baseline before any change: all four commands passed, and the male package was byte-identical. The male files under `public/models/` are not modified by this branch.

## Size

| | Male | Female |
|---|---|---|
| Meshes | 2,234 | 2,287 (2,206 BodyParts3D, 65 HRA, 16 generated) |
| Concepts | 3,432 | 3,497 |
| Triangles | 2,288,268 | 2,503,013 (BodyParts3D 2,236,428 · HRA 250,889 · generated 15,696) |
| Raw geometry | 59.5 MB | 63.4 MB |
| **Download (gzip)** | **33.0 MB** | **35.9 MB** (+9%) |
| Max simplification error | 0.2% | 0.19998% (same meshoptimizer bound; shared parts reused, not re-simplified) |

## Data checks [V]

- Every female mesh has a name, concept id, system, `source` and `accuracy`. Every `schematic` part has a note, and every `generated` part is `schematic`.
- No male-only structures: no part or concept name matches penis, testis, scrotum, prostate, seminal, deferent, epididymis, spermatic, cremaster, ejaculatory or bulbourethral.
- The checklist is complete: all 21 items are present **and** found by search. They are hip bones, sacrum, coccyx, uterus, cervix, uterine tubes, fimbriae, ovaries, ovarian ligament, round ligament, broad ligament, vagina, labia majora, labia minora, clitoris, vestibule, female urethra, mammary glands, breast fat, pelvic floor muscles and female perineal muscles.
- Picking ids are unique (2,287), and every chunk and `.gz` file exists with the declared size.
- Left/right labels of all HRA and generated parts match their side.
  - Two HRA round-ligament labels were swapped in the source and were corrected (DECISIONS D12).
  - 20 shared BodyParts3D names begin with a side opposite their centroid. Most are branch names, such as "right gastric artery". They are unchanged from the male package and are reported, not altered.

## Geometry checks [B]

### Scale and pelvis

- Stature scale: **0.9691** (HRA skin 1.666 m / BodyParts3D skin 1.719 m).

| Measure (mm) | Male BodyParts3D | **Female (morphed)** | HRA female, cross-check |
|---|---|---|---|
| Acetabular centre distance | 169.5 | 169.5 (held fixed) | 207.6 |
| Interspinous (ASIS) | 248.1 | **263.0** | 263.8 |
| Intercristal | 280.8 | **303.2** | 316.9 |
| Inlet transverse (brim proxy) | 111.8 | **121.3** | 135.5 |
| Intertuberous (outlet) | 82.2 | **108.6** | 116.8 |
| Sacral width (alae) | 112.2 | **123.4** | 127.5 |
| Sacral length | 123.2 | **110.6** | 104.6 |
| Symphysis height | 29.7 | **20.9** | 25.9 |
| Subpubic arch (automated measure) | 115.7° | 114.9° | 152.5° |

Every morph target moved toward the real female reference, except the automated subpubic-angle measure. **It did not register a wider arch, so a widened subpubic angle is not demonstrated.** The landmarks on the rami were moved ×1.55, and the outlet widened by 26 mm. However, the measure (`meshlib.subpubic_angle`) samples the lower ramus border 25 mm from the apex and appears insensitive to that change. The pelvis is labelled approximate either way.

Other pelvis and placement results:
- The warp moved 410 shared parts, by at most 14.3 mm; muscle attachments travel with the bone.
- HRA pelvic organs: similarity scale 0.862 and rotation 1.2°, with a mean landmark residual of 17 mm after fitting the HRA pelvis to the morphed one. A 5 mm upward block shift took sampled organ vertices inside bone from 210 to 0.
- Coccyx: rotated 17° to continue the sacrum.
- Ureters: distal ends bent 19 mm and 20 mm to reach the HRA ureteral orifices.
- Breasts: native size, lateral ratio 0.96, moved forward to rest on the chest wall. The skin was pushed out by up to 20 mm over them.
- Skin: 1,496 faces of the external male genitalia removed and 5 openings closed.
- Generated female urethra: 43.0 mm long (reference about 40 mm).

### Interpenetration (python-fcl triangle–triangle tests)

Fix-and-recheck loops:
1. Bowel, vessels and the levator group were moved out of convex hulls of the uterus, vagina, bladder, adnexa and coccyx (34 make-room moves, at most 36 mm, all clean).
2. Thin ligaments were clamped in front of the sacrum and medial to the hip bones.
3. Every generated structure was pushed out of bone, thigh muscles and HRA organs, Taubin-smoothed and re-checked. **Generated vs HRA organs: 0 intersections.**

Remaining intersections in the final build, with their classification:

| Pair (count) | Classification |
|---|---|
| Broad / cardinal ligament, uterine artery and vein × ureter (6) | **Anatomical contact.** The ureter passes through the base of the broad and cardinal ligaments, under the uterine artery. |
| Round ligament × inferior epigastric vessels, external iliac vein, external oblique, epigastric veins (7) | **Anatomical contact.** The round ligament hooks around the inferior epigastric vessels and traverses the abdominal wall in the inguinal canal. |
| Broad / cardinal ligament, uterine vessels × obturator and internal iliac veins, external iliac vessels (10) | Thin sheet on the pelvic side wall, which these vessels line. Contact expected; small overlap. |
| Suspensory ligament of ovary × psoas (1) | **Anatomical contact.** It crosses psoas and the external iliac vessels. |
| Uterosacral / broad ligament × rectum, lateral sacral vein, taenia (6) | Peritoneal folds lying against the rectum. Contact expected; small overlap. |
| Coccyx × gluteus maximus (2); ischiocavernosus × ischiopubic ramus (2) | **Attachment.** Gluteus maximus and ischiocavernosus attach there. |
| Right breast fat × external oblique (1) | The lower lateral breast lies over external oblique and serratus. Contact expected. |
| **Vagina × internal pudendal veins (2)** | **Genuine conflict, not resolved.** The male-derived pudendal veins sit too medially for the wider female outlet, and moving them radially by up to 20 mm did not clear them. |

## Browser checks [H] and screenshots [I]

All screenshots are in `docs/screenshots/` and I reviewed each one.

| File | What it shows | Result |
|---|---|---|
| `01-male-default.png` | Male default | Same view as before. Toggle under the title. Caption "ADULT HUMAN · MALE". |
| `02-female-default.png` | Female default | Body assembled on the stage, breast glandular tissue on the chest, caption "ADULT HUMAN · FEMALE", "2,287 modeled pieces · BodyParts3D + HRA". No floating parts or scale break. |
| `03-female-reproductive-system.png` | Reproductive system only, front | Mammary lobes and ducts at chest height. Uterus, adnexa, vagina and vulva in the pelvis. |
| `03b-female-uterus-isolated.png` | Uterus isolated | 10 pieces, FMA17558, explanation and member list. |
| `04-female-skeleton-front.png`, `04b-…-three-quarter.png` | Skeleton preset | Pelvis present and articulated with the femurs and L5. Coccyx present. |
| `05-female-exploded.png` | Exploded inventory, all systems | Packed inventory, caption "ANATOMICAL INVENTORY". |
| `06-female-search-uterus.png` | Search "uterus" | Uterus, body, fundus, walls, ligaments and uterine vessels. |
| `07-female-clitoris-approximate-badge.png` | Generated clitoris isolated | **"Approximate · schematic" badge** and note in the details panel. |
| `08-toast-selection-cleared.png` | Uterus selected → switch to male | Toast "Uterus is not part of the male model." Selection cleared. |
| `09-mobile-female.png`, `10-mobile-male.png`, `11-mobile-320-female.png` | 390×844 and 320×568 | Toggle with 44 px targets. View controls moved below it. Body fully visible. |
| `12-generated-perineal-structures-below.png`, `12b-…-oblique.png` | Blender renders of all 16 generated structures with pelvis, bladder and vagina | Symmetric about the midline. Crura follow the rami. Bulbs flank the vestibule. Urethra runs from the bladder neck to the vestibule. |
| `13-adapted-skin-vulva-front.png` | Adapted skin with labia | The male genitalia are gone and the cleft is closed; the labia majora lie in it. |

Generated structures, all labelled *approximate / schematic*, each covered by screenshots 07, 12, 12b and 13:

left and right labium majus, left and right labium minus, vestibule of vagina, glans of clitoris, body of clitoris, left and right crus of clitoris, left and right bulb of vestibule, female urethra, left and right ischiocavernosus, left and right bulbospongiosus.

Other parts labelled approximate, in metadata and in the UI badge:
- right and left hip bone and sacrum (morphed)
- skin (adapted)

Functional results [H] (`work/browser-report.json`):
- Selecting Heart on the male body and switching keeps "Heart" selected on the female body.
- The URL becomes `?body=female` and localStorage stores `female`.
- WebMCP, through an injected `document.modelContext`, registers both tools:
  - `find_anatomy({query:'ovary', body:'female'})` called from the male view returns female results.
  - `find_anatomy({query:'uterus'})` on the male body returns `[]`.
  - `inspect_anatomical_structure({id, body:'female'})` switches the viewer to female and opens the structure.
- Console: no errors, and no WebGL context-loss or too-many-contexts warnings. The only messages are SwiftShader "GPU stall due to ReadPixels" performance notes caused by taking screenshots.

**Memory across 10 switches [H].** Readings from `?debug` (`renderer.info`) and CDP metrics after forced GC:

| Switch | Body | Geometries | Textures | Programs | Canvases | DOM nodes | Listeners | JS heap |
|---|---|---|---|---|---|---|---|---|
| 0 | male | 73 | 3 | 6 | 1 | 320 | 546 | 22.3 MB |
| 1 | female | 82 | 3 | 6 | 1 | 330 | 546 | 24.1 MB |
| 2 | male | 73 | 3 | 6 | 1 | 340 | 546 | 24.0 MB |
| 10 | male | 73 | 3 | 6 | 1 | 340 | 546 | 25.1 MB |

GPU resource counts return exactly to each body's value. There is always one canvas and one context. Listeners and nodes are flat after the first switch. The JS heap drifts by about 0.1 MB per switch after warm-up (24.0 → 25.1 MB across switches 2–10). Some of that is the intended manifest cache for both bodies; the rest is not explained, so a slow JS-side leak is not fully ruled out.

## Not tested [—]

- Physical phones and tablets, real GPUs and real multitouch.
- Native browser WebMCP; only an injected test shim was used.
- Visual review by an anatomist. The generated structures and the morphed pelvis are schematic and should be read as such.
