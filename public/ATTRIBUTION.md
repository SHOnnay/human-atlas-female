# Anatomy data attribution

BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International.

- License: https://dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html (updated 2025-02-27)
- Dataset: https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html
- License terms: https://creativecommons.org/licenses/by/4.0/
- Source geometry: `isa_BP3D_4.0_obj_99.zip`, BodyParts3D 4.0.
- English names and relationships: IS-A and PART-OF concept, element, and inclusion tables from the same archive.
- Publication: Mitsuhashi et al. (2009), BodyParts3D: 3D structure database for anatomical concepts. https://doi.org/10.1093/nar/gkn613

Adaptations: axes and units converted from millimeters/Z-up to meters/Y-up; translated to rest at the stage; geometry simplified using meshoptimizer with 0.2% relative error limit per structure; normals quantized to signed 16-bit; packed into binary chunks; curated display system groupings and colors. The source contains 2,234 individual OBJ meshes; all remain represented. The combined hierarchy contains 3,432 named FMA concepts, which may reference multiple meshes. Original source identity is preserved in the manifest.

Source OBJ comments mention an older CC BY-SA 2.1 Japan license. The official current database license linked above supersedes that legacy text and explicitly permits redistribution and adaptation under CC BY 4.0.

BodyParts3D represents an adult male reference anatomy based on TARO MRI and anatomical illustration refinements. It is not a complete model of every possible human anatomical structure or variation. This interface is educational and is not a clinical tool.

## Female model (`/models/female/`)

Every mesh records its source (`source`) and provenance (`accuracy`: `scan-derived`, `warped`, or `generated`) in `models/female/atlas.json`. The viewer shows the provenance as a badge on every structure.

### 1. Human Reference Atlas — the female body (scan-derived)

Kristen Browne and Heidi Schlehlein, Human Reference Atlas / HuBMAP, *3D Reference Organ Set for Female v1.5* (2023), derived from the Visible Human Female. Licensed CC BY 4.0.

- Source DOI: https://doi.org/10.48539/HBM352.BTSQ.586
- Dataset: https://lod.humanatlas.io/ref-organ/united-female/v1.5
- Original GLB: https://cdn.humanatlas.io/digital-objects/ref-organ/united-female/v1.5/assets/3d-vh-f-united.glb
- License: https://creativecommons.org/licenses/by/4.0/

**Used:**
- the skin (the whole body surface)
- the pelvis (ilia, ischia, pubes, sacrum) and the coccyx
- the uterus, cervix and uterine tubes
- the ovaries and the ligaments of the uterus and ovaries
- the vagina and the urinary bladder
- the uterine arteries and veins
- the breasts: mammary lobes, lactiferous ducts and sinuses, breast adipose body, suspensory ligaments, nipples and areolae
- the lungs: all bronchopulmonary segments and hila

**Adaptations:**
- Translated so the feet rest on the stage; scale and mutual positions are unchanged.
- Coincident vertices welded.
- Cracks between uterine pieces closed by projecting near-coincident vertices (≤ 2.5 mm).
- Breasts moved forward by the measured overlap with the chest wall.
- Lactiferous ducts and sinuses kept 1.5 mm inside the skin.
- Thin uterine ligaments kept in front of the sacrum and medial to the hip bones.
- Simplified with a 0.2% per-structure error bound; normals quantized.
- Left/right labels of the round ligaments corrected (they are swapped in the source).

### 2. BodyParts3D 4.0 — every other structure (warped approximation)

BodyParts3D, © DBCLS, CC BY 4.0 (as above). All non-female-specific structures are carried into the HRA female body:
- **Torso, head, neck and legs:** a landmark-based thin-plate-spline warp.
- **Arms:** as articulated rigid segments (upper arm, forearm, hand).
- **Make-room adjustments:** bowel, vessels, nerves and pelvic floor muscles are locally displaced around the real female organs and pelvis.

Removed in the female model:
- male-only structures (26)
- the male hip bones, sacrum, urinary bladder and skin (replaced by HRA)
- head hair, eyebrows and lips (surface details of the male skin)

### 3. Generated structures (this project)

Created with the scripts in `scripts/female/` (Blender 4.2 and Python) and released under CC BY 4.0 together with this dataset:
- labia majora and minora
- vestibule
- clitoris (glans, body, crura) and its prepuce
- vestibular bulbs
- greater vestibular (Bartholin's) and paraurethral (Skene's) glands
- mons pubis
- perineal body
- female urethra
- female ischiocavernosus and bulbospongiosus
- ovarian arteries and veins
- gluteofemoral subcutaneous fat

**They are schematic, not scan-derived.** Dimensions come from published ranges (Lloyd et al. 2005; O'Connell et al. 1998 and 2005; Gray's Anatomy 42nd ed.), and positions from the real neighbouring structures. See `DATA_SOURCES.md`.

No CC BY-SA, non-commercial, SMPL or paid data is included, so no share-alike terms apply.

This interface is educational and is not a clinical, diagnostic or surgical tool. The female model is a composite: one real woman's body (the Visible Human Female, aged 59) combined with reshaped male anatomy and schematic structures. It does not represent every body or variation.

## Historical assets

Earlier repository revisions included female reference anatomy from the same HRA dataset (Kristen Browne and Heidi Schlehlein, *3D Reference Organ Set for Female v1.5*, CC BY 4.0).
