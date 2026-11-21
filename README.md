# Human Atlas

Based on [ashemag/human-atlas](https://github.com/ashemag/human-atlas).

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

The female model (version 3) has three parts:
- **Body:** an **average adult female body**, 1.63 m and BMI 22.5, generated with MPFB2/MakeHuman (CC0). Its rig poses it into the same pose as the male.
- **Pelvis and pelvic organs:** the **real pelvis and pelvic organs of the Visible Human Female**, from the Human Reference Atlas (CC BY 4.0).
- **Everything else:** BodyParts3D anatomy carried into the female body. Bones, hands, feet and the head move rigidly; soft tissue follows a smooth warp.

Every structure carries one of three labels, shown as a badge in the details panel:

| Label | What | Source |
|---|---|---|
| **Scan-derived** | Pelvis, sacrum, coccyx; uterus, cervix, uterine tubes, ovaries and their ligaments; vagina; bladder; uterine vessels; breast glands, ducts and Cooper's ligaments; lungs (all bronchopulmonary segments) | [HRA female organ set v1.5](https://doi.org/10.48539/HBM352.BTSQ.586). The pelvic organs are moved rigidly, without scaling |
| **Warped approximation** (2,199) | Everything else: skull, spine, ribs, limbs, muscles, vessels, nerves, heart, digestive and other organs | BodyParts3D male. Soft tissue: a thin-plate spline on dense same-topology MPFB correspondences. Long bones, hand/foot bones and head: rigid with uniform scale. Spine and sternum: pinned to the midline |
| **Generated · schematic** | Body surface (MPFB2); breast adipose tissue (own *Adipose* system), areolae, nipples; vulva, clitoris and vestibular bulbs (own *Erectile tissue* system), prepuce, Bartholin's and Skene's glands, mons pubis, perineal body, female urethra, female superficial perineal muscles, ovarian vessels, gluteofemoral fat | MPFB2, and Blender/Python scripts from published dimensions |

Selecting a breast gland or duct turns the breast fat semi-transparent.

Male-only structures are not in the female model. Full sources and licenses (including the complete HRA inventory) are in [DATA_SOURCES.md](DATA_SOURCES.md), decisions in [DECISIONS.md](DECISIONS.md), and evidence in [VERIFICATION.md](VERIFICATION.md). Male-versus-female comparison renders are in `docs/screenshots/compare/`.

The female geometry (≈30 MB gzip) downloads only when the female body is selected. Selections carry over when the structure exists in both bodies; otherwise they are cleared with a notice. The WebMCP tools accept an optional `body` (`"male"` or `"female"`).

**Known limitations:**
- **A parametric body around one donor's pelvis.** The body surface is a MakeHuman average, not a scan. The pelvis and pelvic organs belong to one real woman (aged 59). Her subpubic angle (117°) and her uterus (6.3 cm long) are reported as measured, not altered. See VERIFICATION.md.
- **Warped structures.** These are male shapes fitted to the female body. They follow its outline but do not carry true female detail such as muscle size. The brow and jaw are female only through the overall head scale.
- **Containment versus stretch.** A small share of warped triangles is still stretched more than 2× (VERIFICATION.md lists them).
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

1. Install Python 3.10+ with `pip install numpy scipy trimesh python-fcl rtree networkx`, and Blender 4.2 LTS with the **MPFB2** extension (from Blender's extension platform; v2.0.18 was used). Set `BLENDER` to its executable. On Windows, install Blender in a short path; long paths break its file I/O. The three MPFB bodies are generated once into `work/female/mpfb/`. Delete that folder to regenerate them.
2. Download the HRA female GLB (CC BY 4.0) to `work/sources/hra/3d-vh-f-united.glb`:
   `https://cdn.humanatlas.io/digital-objects/ref-organ/united-female/v1.5/assets/3d-vh-f-united.glb`
3. Run `python scripts/build-anatomy.py --sex female`. It runs:
   - `scripts/female/build_female.py`, which does:
     - the male pose and the MPFB bodies
     - the HRA retargeting
     - the dense-correspondence warp
     - the rigid bones, hands, feet and head
     - midline pinning
     - breasts
     - collision fixes
     - the Blender `create_*.py` generators
     - the manifest
   - `node scripts/optimize-anatomy.mjs female/atlas.json`
   - `node scripts/compress-models.mjs female/atlas.json`
   - `node scripts/validate-atlas.mjs female/atlas.json`
   - `python scripts/female/measure.py` and `python scripts/female/gate_checks.py` (gates A and B)

   `python scripts/female/compare_renders.py` renders the male-versus-female composites (gate C) into `docs/screenshots/compare/`. With `npm run dev` running, `python scripts/female/capture_webapp.py --base http://localhost:PORT` captures the same views from the web app into `docs/screenshots/webapp/`.

The build is deterministic. It writes `public/models/female/` and a report at `work/female/report.json` (landmarks, scale factors, collision results). FMA identifiers are read from the cached `scripts/female/ontology_xrefs.json`; refresh it with `scripts/female/fetch_ontology_xrefs.py`, which needs network access.

`python scripts/verify-browser.py` (with `npm run dev` running and `pip install playwright`, `playwright install chromium`) takes the screenshots in `docs/screenshots/` and runs the body-switching and leak checks.

## Deploy

Import this repository into Vercel as a Vite project. The included `vercel.json` configures `npm ci`, `npm run build`, and the `dist` output directory. It can also be served by a static host.

## License

Original application code is released under the [MIT License](LICENSE). **The anatomy data has its own CC BY 4.0 license** (BodyParts3D; HRA female organ set; the generated female structures are released under CC BY 4.0 as part of the same dataset); preserve the attribution in [ATTRIBUTION.md](public/ATTRIBUTION.md) when redistributing it. Third-party dependencies retain their respective licenses.

Issues and pull requests are welcome. Please include reproduction steps and browser/device details for interaction problems.
