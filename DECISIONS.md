# Decisions — female anatomy model

Each entry gives the decision, the reason, and its consequences. Numbers come from `work/female/report.json`, written by every build. They are summarised in VERIFICATION.md.

## Data

**D1. Female-specific organs come from the HRA *3D Reference Organ Set for Female v1.5* (CC BY 4.0), not from Z-Anatomy, AnatomyTOOL or Sketchfab.**
HRA has the same license as BodyParts3D, so it adds no share-alike or NC obligations. The data is expert-segmented from the Visible Human female. It supplies the uterus (body, fundus, cornua, walls, lower segment), cervix with internal and external os, the uterine tubes with fimbriae, ovaries, ovarian, suspensory, round, broad, cardinal and uterosacral ligaments, mesosalpinx, mesovarium, vagina, a female bladder, uterine arteries and veins, mammary glands (lobes, ducts, sinuses, fat, Cooper's ligaments, nipples, areolae) and a coccyx. This repository already credited the same dataset for an earlier female release. See DATA_SOURCES.md for the alternatives that were checked.

**D2. BodyParts3D contributes only sex-neutral structures.**
The BodyParts3D metadata (`isa_element_parts.txt`) has no female structures. 26 male-only elements are removed from the female model (penis, testes, epididymides, seminal vesicles, prostate, deferent ducts, male urethra, penile and testicular vessels, male-pattern pubic hair). They are listed in `scripts/female/config.json`. The male bladder (224 triangles, male relations) is replaced by the HRA female bladder.

**D3. Uniform stature scale = 0.9691.**
This is the HRA female skin height (1.666 m) divided by the BodyParts3D skin height (1.719 m), applied to every shared structure about the floor centre. It is a measured value from the female reference body that supplies the female organs, which keeps those organs at their native size. The population ratio would be smaller: about 0.92 using US NHANES 2015–2018 mean adult statures of 161.3 cm and 175.3 cm (Fryar et al., *NHSR* 160, 2021). It was not used, because it would shrink the shared anatomy relative to the real female organs.

**D4. The female pelvis is the BodyParts3D male pelvis, morphed, not the HRA pelvis.**
The HRA pelvis is real female data, but its acetabula are 208 mm apart and the BodyParts3D femoral heads are 169 mm apart. Registering the HRA pelvis to the femoral heads shrinks it by 21%, which makes it narrower than the male pelvis (ASIS width 208 mm against 248 mm). Using it at native size would pull the femoral heads out of the hip sockets. Both options are anatomically wrong.

The morph instead follows the brief's Step 2b. A thin-plate-spline warp is driven by 27 bony landmarks. The acetabula and sacral base are held fixed, so the hips and L5 still articulate. The other landmarks are moved toward female proportions: intertuberous ×1.32, ischiopubic rami ×1.55, inferior symphysis ×1.5, inlet ×1.10, ASIS ×1.06, iliac flare ×1.08, sacral alae ×1.10, sacrum 10% shorter, symphysis 15% shorter, crests 4% lower.

The **same warp** is applied, with a 10 cm falloff, to every non-rigid structure around the pelvis (411 parts: muscles, ligaments, vessels, nerves, viscera, skin). Muscle attachments therefore stay on the bone. Femurs and vertebrae are excluded so they stay rigid. The pelvis is labelled *approximate* in the metadata and the UI. Before/after measures, with the HRA pelvis as a cross-check, are in VERIFICATION.md.

**D5. HRA pelvic organs are placed with a single similarity transform.**
The transform is a least-squares fit of the HRA pelvis landmarks to the morphed pelvis landmarks (Umeyama), giving scale 0.864 and 0.5° rotation. Inner-pelvis landmarks are weighted ×2. This keeps the organs' size and position relative to the pelvis that held them. A grid search then shifts the organ block by 5 mm upward to clear bone. All organs move together, so their mutual relations are untouched.

**D6. Breasts keep native HRA size.**
Statures are matched (D3), so HRA height above the floor maps directly onto the body. Lateral position is scaled by the ribcage width ratio (BodyParts3D ribs against HRA lungs plus 2 × 12 mm rib thickness). Each breast is then moved forward until its deep surface sits 1.5 mm in front of the pectoral wall. BodyParts3D has no lung volumes, only bronchial trees, so lungs could not be compared directly.

**D7. Coccyx from HRA.**
BodyParts3D has no coccyx. The HRA coccyx is re-oriented to continue the morphed sacrum, angled 15° further anterior, and attached at its apex.

**D8. The skin is adapted, not replaced.**
The HRA skin has a different arm pose (span 0.97 m against 0.67 m), so it cannot sit on BodyParts3D limbs. The BodyParts3D skin is used. Faces within 12–18 mm of the removed external male genitalia are deleted, and the opening is closed with a relaxed membrane (concentric rings, Laplacian-smoothed with the boundary fixed). The chest is pushed out to cover each breast's convex hull plus 2.5 mm. The skin is labelled *schematic*.

**D9. Missing structures are generated in Blender and labelled schematic.**
No openly licensed scan-derived data was found for the vulva (labia majora and minora, vestibule), clitoris (glans, body, crura), vestibular bulbs, female urethra, or female ischiocavernosus and bulbospongiosus. Each one is built by a reproducible script, `scripts/female/create_*.py`, run with `blender -b`. Dimensions come from published ranges (DATA_SOURCES.md), and positions come from real neighbouring structures (morphed pelvis, HRA vagina and bladder, adapted skin). The pipeline then checks them for collisions, fixes them and checks again. Their metadata is `source: "generated"`, `accuracy: "schematic"`, and the UI shows an "Approximate · schematic" badge.

**D10. Pelvic floor: BodyParts3D levator ani is adapted, not regenerated.**
Pubococcygeus, puborectalis, iliococcygeus, coccygeus, the tendinous arch and the external anal sphincter are real BodyParts3D muscles. They are warped by the pelvis morph (D4) and pushed out of the HRA vagina and urethra by the collision step, which widens the urogenital hiatus. They are labelled *warped*.

**D11. Display systems for new parts.**
Mammary lobes, ducts and sinuses are in *Reproductive*, so they are visible by default. Breast fat, nipples and areolae are in *Body surface*, which is hidden by default as before. Cooper's ligaments are in *Connective tissue*. Uterine ligaments are in *Reproductive*. Uterine vessels are in *Arteries* and *Veins*. The female urethra is in *Urinary*, the generated perineal muscles in *Muscles*, and the coccyx in *Skeleton*. The HRA placenta and umbilical structures are not included, because they are pregnancy-only references.

**D12. Source label errors are corrected in the build, and each correction is recorded.**
HRA names the round ligaments the wrong way round: the node labelled "Right round ligament" lies at +x, which is the body's left. Any part whose "left"/"right" label contradicts its centroid is renamed. The correction is listed in the manifest (`build.labelCorrections`) and in VERIFICATION.md.

**D13. FMA IDs only from EBI OLS, never guessed.**
`scripts/female/fetch_ontology_xrefs.py` caches UBERON→FMA cross-references and exact FMA label matches in `ontology_xrefs.json`, and the build reads only that cache. When OLS has no FMA term, the concept keeps its UBERON (HRA) or `GEN:` (generated) identifier.

## Pipeline

**D14. A parallel script rather than editing `convert-anatomy.py`.**
`scripts/build-anatomy.py --sex male|female` is the single entry point. The female path runs `scripts/female/build_female.py`, then `optimize-anatomy.mjs female/atlas.json`, then `compress-models.mjs female/atlas.json`. The male converter is untouched.

**D15. Shared parts are not simplified twice.**
They come from the already-optimized male package (0.2% bound). They are marked `preoptimized` and copied through. New HRA and generated parts get the same meshoptimizer step: 22% target, 0.002 relative error. HRA vertices are welded in Python first, as the removed female converter did.

**D16. Blender path.**
Blender 4.2 LTS (portable zip) is located through `$BLENDER`, `work/tools/blender-*` or `PATH`. On Windows, Blender fails to start or import files from paths longer than 260 characters, so all Blender input and output goes through `%TEMP%\ha-female`.

## App

**D17. The body choice lives in the header under the title.** This is where the earlier male/female selector sat; its CSS slot already existed. It is a shadcn `ToggleGroup`. On phones its buttons are 44 px tall, and the view controls and search panel move down 48 px to make room. The choice is stored in `?body=` and `localStorage` (`human-atlas:body`), with both wrapped in try/catch. Precedence is URL, then storage, then male.

**D18. The scene is still rebuilt per body.**
This was the existing lifecycle, and it guarantees no state crosses between datasets. Teardown now also calls `renderer.forceContextLoss()`. Browsers cap live WebGL contexts at about 16, so repeated switching would otherwise evict contexts. Teardown also removes the pointer listeners and clears the scene graph.

**D19. Selection on switch.**
If every selected part id exists in the new body (shared BodyParts3D parts keep their ids), the selection is kept. Otherwise the same concept id is used, then parts with the same concept id. If none of those match, the selection is cleared and a toast names the structure.

**D20. WebMCP.**
Both tools accept an optional `body`. They answer synchronously from a loaded catalogue, which keeps the existing validator contract, and otherwise fetch that body's manifest (metadata only). Inspecting in the other body switches the viewer to it.
