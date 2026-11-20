# Human Atlas

An interactive 3D anatomy explorer built with React, Three.js, and shadcn/ui. Take the BodyParts3D adult male reference apart into **2,234 individually selectable meshes**, explore **15 anatomical systems**, and search **3,432 named concepts**. A **Male / Female** toggle switches to an adult female reference assembly (see [Female model](#female-model)).

**[Explore the live demo](https://human-atlas-seven.vercel.app)**

## Explore

- Orbit, zoom, and select structures directly on the body.
- Toggle individual systems or use skeleton and organ presets.
- Move from assembled anatomy to a spaced inventory of every visible piece.
- Search anatomical names and source identifiers.
- Isolate a selected structure and read its details.
- Use compact controls and detail panels on mobile.
- Switch between the male and female reference bodies. The choice is kept in the URL (`?body=female`) and in this browser.

## Run locally

Requires Node.js 22.13 or newer. No API keys or accounts are needed.

```sh
npm ci
npm run dev
```

Open http://localhost:3016. To build the static site, run `npm run build`; the output is in `dist/`.

## Validate

```sh
npm run check
node scripts/validate-atlas.mjs
node scripts/validate-interactions.mjs
npm run build
```

Both validators check the male and the female packages. For the female model they also check:
- every mesh has source and accuracy metadata
- no male-only structures are present
- every required female structure is present and searchable
- left/right labels agree with the geometry
- the WebMCP `body` parameter works
- selections carry over between bodies

Validation covers mesh buffers, names and concept membership, nonoverlapping exploded layouts at desktop and mobile aspect ratios, search and inspection contracts, and tap-versus-drag handling. Browser interaction checks have exercised selection, system controls, search, isolation, rotation, and 390×844, 320×568, and 844×390 layouts. Phone controls stay clear of the exploded inventory, and isolated structures fit the space above or beside the detail panel. Physical-device performance and real multitouch hardware have not been tested.

## Anatomy data

The current viewer uses **BodyParts3D 4.0**, an adult male reference anatomy, licensed **CC BY 4.0**. It does not represent every human structure or variation. Individual source meshes are distinct from named concepts, which may group multiple meshes. Descriptions distinguish general system context from individual organ explanations.

Geometry is simplified for browser performance while retaining every source mesh. The packaged model contains 2,288,268 triangles and downloads approximately 33 MB of compressed geometry. Full credits, source links, and adaptation details are in [ATTRIBUTION.md](public/ATTRIBUTION.md).

This is an educational explorer, not a diagnostic or surgical tool.

## Female model

The female model is built on a **real woman's body**: the Visible Human Female, as segmented by the Human Reference Atlas (CC BY 4.0). Every structure carries one of three labels, shown as a badge in the details panel:

| Label | What | Source |
|---|---|---|
| **Scan-derived** (100 structures) | Skin (whole body surface); pelvis, sacrum, coccyx; uterus, cervix, uterine tubes, ovaries and their ligaments; vagina; bladder; uterine vessels; breasts (glands, ducts, adipose body, Cooper's ligaments, nipples, areolae); lungs (all bronchopulmonary segments) | [HRA female organ set v1.5](https://doi.org/10.48539/HBM352.BTSQ.586), in native position and scale |
| **Warped approximation** (2,199) | Everything else: skull, spine, ribs, limbs, muscles, vessels, nerves, heart, digestive and other organs | BodyParts3D male, carried into the female body by a landmark thin-plate-spline warp (about 800 automatic correspondences; arms as articulated rigid segments). No uniform scaling. |
| **Generated · schematic** (28) | Vulva (labia majora and minora, vestibule), clitoris (glans, body, crura, prepuce), vestibular bulbs, Bartholin's and Skene's glands, mons pubis, perineal body, female urethra, female superficial perineal muscles, ovarian arteries and veins, gluteofemoral subcutaneous fat | Blender/Python scripts from published dimensions |

Male-only structures are not in the female model. Full sources and licenses (including the complete HRA inventory) are in [DATA_SOURCES.md](DATA_SOURCES.md), decisions in [DECISIONS.md](DECISIONS.md), and evidence in [VERIFICATION.md](VERIFICATION.md). Male-versus-female comparison renders are in `docs/screenshots/compare/`.

The female geometry (≈30 MB gzip) downloads only when the female body is selected. Selections carry over when the structure exists in both bodies; otherwise they are cleared with a notice. The WebMCP tools accept an optional `body` (`"male"` or `"female"`).

**Known limitations:**
- **One donor.** The body is one real woman (aged 59, broad-hipped), not a population average. Her skin shoulder-to-hip ratio (0.848), Q-angle (10.5°) and subpubic angle (111°) fall outside textbook female bands. She stood with her knees 23 cm apart, so the femurs barely converge toward the knees. These are reported, not altered.
- **Warped structures.** These are male shapes fitted to the female body. They follow its outline but do not carry true female detail such as muscle size. Some are visibly stretched, especially the gluteals.
- **Hands.** The finger bones are compressed, because the male hand is closed and the female hand is spread.
- **Other visible defects.** The skeletal ribcage is no narrower than the (already narrow) BodyParts3D male. The left labium minus is about 5 cm longer than the right.
- **Generated structures.** These are schematic.
- **Not yet used.** The University of Denver Visible Human Female musculoskeletal models (CC BY 4.0, 76 muscles and 28 bones) would make the lower-body muscles real. They are the recommended next step.
- **No pregnancy structures.**

The educational, non-diagnostic disclaimer applies equally to the female model.

## How it works

Geometry is merged into batches. Per-structure GPU textures control translation, visibility, and selection, while component geometry supports accurate picking. Exploded layouts pack only the visible pieces. Rendering updates when the scene changes; orbit controls remain responsive without thousands of separate draw calls.

The optional WebMCP tools expose anatomy search and inspection in compatible browsers. The visible interface works without them.

## Rebuilding geometry

The repository includes browser-ready geometry. Rebuilding it is optional: obtain the official BodyParts3D OBJ archive and English metadata tables, prepare the joined concepts and display-system mappings, run `scripts/convert-anatomy.py`, then `node scripts/optimize-anatomy.mjs` and `node scripts/compress-models.mjs`. Simplification uses a 0.2% relative error limit per structure.

`scripts/build-anatomy.py --sex male|female` wraps both pipelines.

To rebuild the female model (from the packaged male model and the HRA GLB):

1. Install Python 3.10+ with `pip install numpy scipy trimesh python-fcl rtree networkx`, and Blender 4.2 LTS. Set `BLENDER` to its executable. On Windows, install Blender in a short path; long paths break its file I/O.
2. Download the HRA female GLB (CC BY 4.0) to `work/sources/hra/3d-vh-f-united.glb`:
   `https://cdn.humanatlas.io/digital-objects/ref-organ/united-female/v1.5/assets/3d-vh-f-united.glb`
3. Run `python scripts/build-anatomy.py --sex female`. It runs:
   - `scripts/female/build_female.py` (HRA frame, landmark warp, articulated arms, collision fixes, the Blender `create_*.py` generators, manifest)
   - `node scripts/optimize-anatomy.mjs female/atlas.json`
   - `node scripts/compress-models.mjs female/atlas.json`
   - `node scripts/validate-atlas.mjs female/atlas.json`
   - `python scripts/female/measure.py` and `python scripts/female/gate_checks.py` (gates A and B)

   `python scripts/female/compare_renders.py` renders the male-versus-female composites (gate C).

The build is deterministic. It writes `public/models/female/` and a report at `work/female/report.json` (landmarks, scale factors, collision results). FMA identifiers are read from the cached `scripts/female/ontology_xrefs.json`; refresh it with `scripts/female/fetch_ontology_xrefs.py`, which needs network access.

`python scripts/verify-browser.py` (with `npm run dev` running and `pip install playwright`, `playwright install chromium`) takes the screenshots in `docs/screenshots/` and runs the body-switching and leak checks.

## Deploy

Import this repository into Vercel as a Vite project. The included `vercel.json` configures `npm ci`, `npm run build`, and the `dist` output directory. It can also be served by a static host.

## License

Original application code is released under the [MIT License](LICENSE). **The anatomy data has its own CC BY 4.0 license** (BodyParts3D; HRA female organ set; the generated female structures are released under CC BY 4.0 as part of the same dataset); preserve the attribution in [ATTRIBUTION.md](public/ATTRIBUTION.md) when redistributing it. Third-party dependencies retain their respective licenses.

Issues and pull requests are welcome. Please include reproduction steps and browser/device details for interaction problems.
