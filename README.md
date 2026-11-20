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

The female model is a **composite reference assembly**, not a scan of one person. It combines:

| Part of the body | Source | Accuracy label |
|---|---|---|
| Sex-neutral organs, vessels, nerves, skull, spine, limbs, muscles | BodyParts3D 4.0 (CC BY 4.0), uniformly scaled ×0.969 to the stature of the female reference | source |
| Soft tissue around the pelvis, the bowel near the female organs, levator ani | BodyParts3D, smoothly warped to fit the female pelvis and organs | warped |
| Uterus, cervix, uterine tubes, ovaries and their ligaments, vagina, bladder, uterine vessels, mammary glands, coccyx | [HRA 3D Reference Organ Set for Female v1.5](https://doi.org/10.48539/HBM352.BTSQ.586) (CC BY 4.0) | source |
| Hip bones and sacrum | BodyParts3D male pelvis **morphed** toward female proportions (wider outlet, inlet and pubic arch, shorter and wider sacrum) | **approximate** |
| Labia majora and minora, vestibule, clitoris (glans, body, crura), vestibular bulbs, female urethra, female ischiocavernosus and bulbospongiosus | **Generated** in Blender from published dimensions | **approximate** |
| Skin | BodyParts3D skin adapted (male external genitalia removed and closed, chest reshaped over the breasts) | **approximate** |

Male-only structures (prostate, seminal vesicles, deferent ducts, testes, epididymides, penis, male urethra, and their vessels) are not in the female model. Structures marked approximate show an **"Approximate · schematic"** badge in the details panel. Their metadata carries `accuracy: "schematic"`, and for generated parts also `source: "generated"`. Full source and license details are in [DATA_SOURCES.md](DATA_SOURCES.md). The reasoning behind each choice is in [DECISIONS.md](DECISIONS.md), and the evidence is in [VERIFICATION.md](VERIFICATION.md).

The female geometry downloads only when the female body is selected. Selections carry over when the structure exists in both bodies; otherwise they are cleared with a notice. The WebMCP tools accept an optional `body` (`"male"` or `"female"`).

**Known limitations:**
- The shared anatomy is male-derived, so it does not show female differences outside the pelvis and breasts, such as thyroid cartilage, muscle mass or limb proportions.
- The morphed pelvis and the generated vulva, clitoris, urethra and perineal muscles are schematic, not measured anatomy.
- The HRA organs come from a different person than BodyParts3D. They are fitted by landmarks, and nearby bowel and vessels were displaced to make room.
- Ovarian vessels are not modelled; the male testicular vessels were removed.
- No pregnancy structures are included.

The educational, non-diagnostic disclaimer applies equally to the female model.

## How it works

Geometry is merged into batches. Per-structure GPU textures control translation, visibility, and selection, while component geometry supports accurate picking. Exploded layouts pack only the visible pieces. Rendering updates when the scene changes; orbit controls remain responsive without thousands of separate draw calls.

The optional WebMCP tools expose anatomy search and inspection in compatible browsers. The visible interface works without them.

## Rebuilding geometry

The repository includes browser-ready geometry. Rebuilding it is optional: obtain the official BodyParts3D OBJ archive and English metadata tables, prepare the joined concepts and display-system mappings, run `scripts/convert-anatomy.py`, then `node scripts/optimize-anatomy.mjs` and `node scripts/compress-models.mjs`. Simplification uses a 0.2% relative error limit per structure.

`scripts/build-anatomy.py --sex male|female` wraps both pipelines.

To rebuild the female model (from the packaged male model):

1. Install Python 3.10+ with `pip install numpy scipy trimesh python-fcl rtree networkx`, and Blender 4.2 LTS. Set `BLENDER` to its executable. On Windows, install Blender in a short path; long paths break its file I/O.
2. Download the HRA female GLB (CC BY 4.0) to `work/sources/hra/3d-vh-f-united.glb`:
   `https://cdn.humanatlas.io/digital-objects/ref-organ/united-female/v1.5/assets/3d-vh-f-united.glb`
3. Run `python scripts/build-anatomy.py --sex female`. It runs:
   - `scripts/female/build_female.py` (scale, pelvis morph, HRA registration, collision fixes, skin, the Blender `create_*.py` generators, manifest)
   - `node scripts/optimize-anatomy.mjs female/atlas.json`
   - `node scripts/compress-models.mjs female/atlas.json`
   - `node scripts/validate-atlas.mjs female/atlas.json`

The build is deterministic. It writes `public/models/female/` and a report at `work/female/report.json` (landmarks, scale factors, collision results). FMA identifiers are read from the cached `scripts/female/ontology_xrefs.json`; refresh it with `scripts/female/fetch_ontology_xrefs.py`, which needs network access.

`python scripts/verify-browser.py` (with `npm run dev` running and `pip install playwright`, `playwright install chromium`) takes the screenshots in `docs/screenshots/` and runs the body-switching and leak checks.

## Deploy

Import this repository into Vercel as a Vite project. The included `vercel.json` configures `npm ci`, `npm run build`, and the `dist` output directory. It can also be served by a static host.

## License

Original application code is released under the [MIT License](LICENSE). **The anatomy data has its own CC BY 4.0 license** (BodyParts3D; HRA female organ set; the generated female structures are released under CC BY 4.0 as part of the same dataset); preserve the attribution in [ATTRIBUTION.md](public/ATTRIBUTION.md) when redistributing it. Third-party dependencies retain their respective licenses.

Issues and pull requests are welcome. Please include reproduction steps and browser/device details for interaction problems.
