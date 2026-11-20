# Architecture notes

Written before the female model was added. Line references are to the code as of commit `1c38bf3`. The "Female model additions" section at the end describes what changed.

## 1. From BodyParts3D source to packaged model

Source inputs (not in the repository; see `public/ATTRIBUTION.md`):

- `isa_BP3D_4.0_obj_99.zip`: 2,234 OBJ meshes, one per BodyParts3D *element* (`FJxxxx`). Units are millimetres, Z-up.
- `isa_element_parts.txt` / `isa_parts_list_e.txt` / `isa_inclusion_relation_list.txt`, plus the `partof_*` equivalents: FMA concept ⇄ element membership, English names, and the IS-A / PART-OF hierarchy.

The pipeline has three stages:

1. **`scripts/convert-anatomy.py OBJ_DIR CONCEPT_MAP SYSTEM_MAP`**
   - `CONCEPT_MAP` is a prepared JSON `{elements:[{id,name,conceptId}], concepts:[{id,name,elements[]}]}` built by joining the IS-A and PART-OF tables. The tool that prepared it is not in the repository.
   - `SYSTEM_MAP` is a curated `element id → display system` table (also prepared outside the repository).
   - Each OBJ is parsed without changing topology. Positions go from mm/Z-up to metres/Y-up: `(x, z+78.1mm, -y-100mm)·0.001`, so the feet rest on y=0 and the body is centred on the stage. Normals become signed 16-bit integers. Polygons are fan-triangulated into `Uint32` indices.
   - Per part it writes `{id, name, conceptId, system, chunk, positions, normals, indices, vertexCount, indexCount, bounds}`. Offsets are byte offsets into a chunk `.bin`, 4-byte aligned. Chunks roll over at about 7 MB.
   - Writes `public/models/atlas.json` with `{version, parts, chunks, triangles, concepts}`.
2. **`scripts/optimize-anatomy.mjs [manifest]`**
   - Simplifies each part with meshoptimizer: target 22% of indices (minimum 96), error bound 0.002 (0.2% of the part's extent). It then compacts the vertices and rechunks at about 4 MB into `body-N.bin`.
   - It refuses to run twice (`manifest.optimized`).
   - A dormant `female` prefix branch welds coincident vertices. That branch was used by the removed HRA female atlas.
3. **`scripts/compress-models.mjs`**: gzips each chunk at level 9 to `*.bin.gz` and records `gzip` / `gzipBytes` in the manifest.

Output is about 33 MB gz / 57 MB raw for 2,288,268 triangles.

## 2. Concepts and display systems

- A **part** is one source mesh (one BodyParts3D element). It has exactly one `system` (one of 15 `SystemId`s in `app/anatomy.ts`), and it carries the FMA `conceptId` it represents directly.
- A **concept** is a named FMA concept, possibly compound (for example "Hip bone" or a whole organ). Its `elements` lists the part ids. There are 3,432 concepts, and they overlap freely.
- **Display systems** are curated groupings, not FMA systems. `SYSTEMS` defines each one's name, colour and generic description, and they drive the toggles, the presets (All / Skeleton / Organs) and the materials. `integumentary` is hidden by default (`DEFAULT_VISIBLE`) and rendered at 10% opacity without depth writes.

## 3. Batching (`app/scene.tsx`)

- Chunks are fetched 3 in parallel. Each part becomes a small `BufferGeometry`. Its typed arrays are views on the chunk buffer, so there are no copies, and normals are normalized `Int16`.
- Every part gets a per-vertex float attribute `partIndex`, its index in `atlas.parts`.
- Within a chunk, part geometries are merged **per system** (`mergeGeometries`) into one mesh with one shared material per system. The draw call count is about chunks × systems (≈15×15), not 2,234.

## 4. Per-structure GPU state textures

- `partTexture`: an RGBA float `DataTexture` of width `nextPow2(parts)` × 1. Texel *i* = (dx, dy, dz, visible) for part *i*.
- `selectionTexture`: an RGBA8 texture. R = 255 when part *i* is selected.
- Each system material patches its shader in `onBeforeCompile`. The vertex shader samples the textures at `(partIndex+0.5)/width` and adds the translation in `begin_vertex`. The fragment shader discards fragments where visible < 0.5 and tints selected parts teal.
- The animation loop recomputes texels only when visibility, selection or isolate changes, or while the explode amount is moving. Explode has two stages. From 0 to 0.45 parts are spread radially by system. From 0.45 to 1 they lerp into the 2-D packed "inventory" layout from `createExplosionLayout`, a shelf-packing of the visible parts' x/y bounding boxes. Rendering is on demand (`dirty`).

## 5. Picking

- Every part also keeps an un-merged `pick` Mesh that shares its geometry (not added to the scene). On a valid tap (`PointerTap` separates taps from drags and pinches), the ray is tested against each visible part's translated AABB, then against the triangles of that part's pick mesh. Its position mirrors the state-texture translation.
- Skin (`integumentary`) is skipped when any solid system is visible.
- In exploded mode (amount > 0.45), a fallback finds the nearest projected 2-D bounding box (`targets`), which is also used for hover labels.

## 6. Search and WebMCP

- The search panel (`page.tsx`) filters `atlas.concepts` by name or id substring, sorts by name length and shows up to 80. With no query it shows a fixed list of major organs.
- `app/agent-tools.ts` `atlasTools(atlas, inspect)` returns two WebMCP tools: `find_anatomy({query})` and `inspect_anatomical_structure({id})`. `registerAtlasTools` registers them on `document.modelContext` when it exists and aborts them on cleanup. Both read only the loaded `atlas` object, so search, the tools and the validator all use the same manifest data.
- `scripts/validate-interactions.mjs` imports these modules directly (Node type-stripping). It checks packing overlap at 3 aspect ratios per system, the search/inspect contracts and tap handling.

## 7. Lifecycle

`AnatomyScene` builds the renderer, scene, textures and geometries in one `useEffect` keyed on `atlas`. Changing the atlas tears everything down and rebuilds it. Before this work, cleanup disposed geometries, materials, textures and the renderer but did not release the WebGL context.

## Female model additions

- `scripts/female/`: the female pipeline (see README "Rebuilding geometry"). It writes `public/models/female/atlas.json` and `female-N.bin[.gz]`. The male package is unchanged.
- Parts may carry `src` (a key into `atlas.sources`) and `accuracy` (`source` | `registered` | `schematic`). The UI shows an "Approximate" badge for `schematic`.
- `app/scene.tsx` now also calls `renderer.forceContextLoss()` on teardown, so switching bodies repeatedly does not exhaust WebGL contexts. It also exposes `window.__atlasRenderer` diagnostics behind `?debug`.
- `app/agent-tools.ts`: both tools accept an optional `body` ('male' | 'female').
