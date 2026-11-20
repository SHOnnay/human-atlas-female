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

The female model combines three sources. Each mesh records its source (`source`) and how faithful it is (`accuracy`: `source`, `warped`, or `schematic`) in `models/female/atlas.json`.

### 1. BodyParts3D 4.0 — shared structures

BodyParts3D, © The Database Center for Life Science, licensed under CC Attribution 4.0 International (as above).

Adaptations:
- Uniformly scaled by 0.9691, so that skin height matches the HRA female reference body.
- 26 male-only meshes removed. The male urinary bladder is replaced by the HRA one.
- **The hip bones and sacrum are morphed toward female pelvic proportions** with a landmark-driven thin-plate-spline warp. They are marked approximate.
- The same smooth warp is applied to surrounding soft tissue.
- Bowel, ureters, vessels and pelvic floor muscles near the female organs are locally displaced to clear them.
- The skin has the external male genitalia removed, the opening closed schematically, and the chest reshaped over the breasts. It is marked approximate.

### 2. Human Reference Atlas — female organs

Kristen Browne and Heidi Schlehlein, Human Reference Atlas / HuBMAP, *3D Reference Organ Set for Female v1.5* (2023). Licensed CC BY 4.0.

- Source DOI: https://doi.org/10.48539/HBM352.BTSQ.586
- Dataset: https://lod.humanatlas.io/ref-organ/united-female/v1.5
- Original GLB: https://cdn.humanatlas.io/digital-objects/ref-organ/united-female/v1.5/assets/3d-vh-f-united.glb
- License: https://creativecommons.org/licenses/by/4.0/

Used: uterus, cervix, uterine tubes, ovaries, uterine and ovarian ligaments, mesosalpinx, mesovarium, uterovesical pouch, vagina, urinary bladder, uterine arteries and veins, mammary glands (lobes, ducts, sinuses, fat, suspensory ligaments, nipples, areolae) and coccyx.

Adaptations:
- Coincident vertices welded and normals averaged.
- Pelvic organs placed with one similarity transform (scale 0.864) fitted to pelvic landmarks, then shifted 5 mm to clear bone.
- Breasts placed by height and chest-wall contact at native size.
- Coccyx re-oriented to continue the morphed sacrum.
- Thin ligaments and uterine vessels locally displaced to stay inside the pelvic walls.
- Simplified with a 0.2% per-structure error bound; normals quantized.
- Two labels corrected: the source swaps the left and right round ligaments.

The HRA pelvis was used only as a measurement reference. Placenta and umbilical structures are not included.

### 3. Generated schematic structures (this project)

These were created for Human Atlas with Blender scripts in `scripts/female/create_*.py` and are released under CC BY 4.0, together with this dataset:
- labia majora and minora
- vestibule
- glans, body and crura of the clitoris
- vestibular bulbs
- female urethra
- female ischiocavernosus and bulbospongiosus

**They are approximate / schematic and not scan-derived.** Dimensions are taken from published ranges (Lloyd et al. 2005, BJOG; O'Connell et al. 1998 and 2005, J Urol; Gray's Anatomy 42nd ed.), and positions are derived from neighbouring atlas structures. See `DATA_SOURCES.md` in the repository.

No CC BY-SA or non-commercial data is included, so no share-alike terms apply.

This interface is educational and is not a clinical, diagnostic or surgical tool. The female model is a composite reference assembly, not a single person, and does not represent every body or variation.

## Historical assets

Earlier repository revisions included female reference anatomy: Kristen Browne and Heidi Schlehlein, Human Reference Atlas / HuBMAP, *3D Reference Organ Set for Female v1.5* (2023). CC BY 4.0. Geometry adapted for this viewer.

- Source DOI: https://doi.org/10.48539/HBM352.BTSQ.586
- Dataset: https://lod.humanatlas.io/ref-organ/united-female/v1.5
- Original GLB: https://cdn.humanatlas.io/digital-objects/ref-organ/united-female/v1.5/assets/3d-vh-f-united.glb
- License: https://creativecommons.org/licenses/by/4.0/

Adaptations: translated native meter/Y-up coordinates onto the stage, coincident vertices welded and source normals averaged, geometry simplified with a 0.2% per-structure relative error bound, and normals quantized. Colors and display systems are curated for this interface. All 888 source meshes are represented, with 1,073 source nodes available as selectable individual or compound concepts.

This is a reference assembly with whole-body surface and selected organs, including female reproductive anatomy. Its skeleton and muscle coverage is partial. It is not a complete model of every human structure or a single-person scan. Eight placenta/umbilical structures are classified under Pregnancy reference and hidden by default.
