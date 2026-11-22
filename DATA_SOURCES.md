# Data sources for the female model

Checked on 2026-11-20. "Used" means the data is in `public/models/female/`. No SMPL, no non-commercial data and no paid data are used.

## Summary of what the female model is made of

Version 3 (polish milestone):

| Provenance (UI badge) | What | Source | License |
|---|---|---|---|
| **Generated · schematic**, source `mpfb` | Body surface (skin): average adult female, 1.63 m, BMI 22.5, posed by its rig into the reference pose | MPFB2 / MakeHuman parametric body (`scripts/female/create_mpfb_body.py`) | CC0 1.0 assets (GPL-3 add-on used as a tool only) |
| **Scan-derived** | Pelvis (ilia, ischia, pubes), sacrum, coccyx; uterus with cervix; uterine tubes; ovaries; ligaments; vagina; urinary bladder; uterine vessels; breast glands, lactiferous ducts and sinuses, Cooper's ligaments; lungs (all segments, hila) | HRA 3D Reference Organ Set for Female v1.5 (Visible Human Female). Bony pelvis, lungs and breast glands: shape-preserving similarity; pelvic organs: rigid, no scale | CC BY 4.0 |
| **Warped approximation** (2,199) | Every other structure: skull, spine, ribs, limbs, muscles, vessels, nerves, heart, digestive and other organs | BodyParts3D 4.0 (male). Soft tissue: thin-plate spline on dense same-topology MPFB pairs. Bones, hands, feet and head: rigid transforms with uniform scale | CC BY 4.0 |
| **Generated · schematic** | Breast adipose bodies, areolae, nipples; labia majora and minora, vestibule, clitoris (glans, body, crura), prepuce, vestibular bulbs, Bartholin's and Skene's glands, mons pubis, perineal body, female urethra, female ischiocavernosus and bulbospongiosus, ovarian arteries and veins, gluteofemoral subcutaneous fat | Blender / Python scripts in `scripts/female/` | CC BY 4.0 (this project) |

Up to version 2 the HRA skin scan was the body surface. It is no longer distributed (see DECISIONS.md D33).

## Milestones 5–6: Visible Human Female CT and cryosections (branches `vhf-real`, `hybrid`)

- **NLM Visible Human Project, female (VHP-F)**, via the NCI Imaging Data Commons collection `nlm_visible_human_project` (licence: National Library of Medicine Terms and Conditions, May 21, 2019). Courtesy of the U.S. National Library of Medicine.
  - **CT:** series "AXIAL 1X1 NCE" (985 slices, head→femur) and "1X1 AXIAL FEMUR-TOES NCE" (749 slices). Downloaded by `scripts/female/vhf_ct.py`.
  - **Colour cryosections:** "Fullcolor - direct digital", 5,186 slices at 0.33 mm, 38.7 GB in total. They are indexed from DICOM headers only, and slices are downloaded on demand by `scripts/female/vhf_cryo.py`.
  - The cadaver was imaged frozen inside a gelatin block. The CT body outline is therefore the block, so registration is done on bone.
- **TotalSegmentator `total`** (Apache-2.0; Wasserthal et al. 2023), run on the CT. No licensed tasks were used. The segments serve as registration targets and section checks.
- **HRA VH_F organs used in the hybrid body:** vertebrae, spinal cord, liver, gallbladder, pancreas, spleen, colon, small intestine, duodenum, kidneys, heart chambers/valves/papillary muscles, trachea, main bronchi and thymus, plus the earlier skin, breasts, pelvis, pelvic organs, lungs and leg bones.
- **Not used:**
  - The TotalSegmentator training dataset (CC BY 4.0, Zenodo 10047292, 23.6 GB) was not downloaded.
  - The 2025 female pelvic MRI dataset (doi 10.1038/s41597-025-05623-3) is of endometriosis patients, so it is not a normal reference, and its file licence was not confirmed.
  - Bowen et al. 2022 (Int Urogynecol J 33:1649) is cited, but its numbers are in the paywalled full text, so only O'Connell 1998/2005 values are used.

## Step 1 inventory

### HRA female reference set (VH_F) — **used**

- Dataset: Kristen Browne, Heidi Schlehlein; Human Reference Atlas / HuBMAP, *3D Reference Organ Set for Female v1.5* (2023). https://doi.org/10.48539/HBM352.BTSQ.586
- File: `https://cdn.humanatlas.io/digital-objects/ref-organ/united-female/v1.5/assets/3d-vh-f-united.glb` (212 MB).
- License: **CC BY 4.0**.
- Content: 888 meshes in 10 organ systems, from the Visible Human Female. Each mesh has a label and a UBERON/FMA id. The skin is a single watertight scan surface (382,640 triangles, 166.6 cm tall). The skeleton holds the pelvis, sacrum, coccyx and lower-limb bones. Every file is listed with its dimensions in Appendix A.
- What it lacks: external genitalia, female urethra, superficial perineal muscles, ovarian vessels, most muscles, the upper-limb and axial skeleton.

### NLM Visible Human Female — source images; no complete open segmentation found other than HRA and one partial set

- The NLM Visible Human Project images (cryosection, CT, MRI) are public. Since 2019 no license agreement is needed: https://www.nlm.nih.gov/research/visible/visible_human.html
- **University of Denver, "Visible Human Female" 3D STL models**, https://digitalcommons.du.edu/visiblehuman/1, **CC BY 4.0**. These are segmented musculoskeletal models: per the companion paper (Sci Data 2022, https://doi.org/10.1038/s41597-022-01905-2), 76 muscles, 28 bones, 16 cartilages, 8 ligaments and 2 fat geometries.
  - Status: **found but not yet integrated**. It would replace many warped male muscles of the lower limb and pelvis with real female ones, which needs registration into the HRA frame and a muscle-by-muscle name mapping. It is listed as the next improvement in README "Known limitations".
- AustinWoman (UT Austin voxel model built from VHF): password-gated, with a no-derivatives clause. **Not usable.**

### MakeHuman / MPFB2 — **used from version 3 (body surface)**

- MPFB2 v2.0.18 (Blender 4.2 extension) is GPL-3 code with CC0 core assets (base mesh, targets, rigs): https://static.makehumancommunity.org/about/license.html. Only generated meshes are distributed, never add-on code.
- Version 2 did not use it (the HRA scan skin was preferred). Version 3 needs a body that can be **posed by a rig** into the male reference pose, so that no large rotation is left to the spline (the brief's root-cause fix). The HRA scan has no rig, so v3 uses MPFB2.
- Generated with these settings:
  - female, age 25, proportions 0.5, cup 0.5, firmness 1.0
  - height bisected to 1.63 m (NHANES adult women: median ~1.62 m)
  - weight, then muscle, bisected to BMI 22.5 kg/m² (body mass = closed volume × 1010 kg/m³). This sits inside the WHO normal range 18.5–24.9 and matches the brief's "average adult female, BMI ~22–23".
- Helper bodies with the same topology, used only to compute the warp: an MPFB male fitted to BodyParts3D, and the female with cup size 0.

### BodyParts3D / FMA (DBCLS) — **used for warped structures**

- https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html, **CC BY 4.0** (the database license supersedes the CC BY-SA 2.1 JP text in the OBJ comments).
- It has no female structures. A search of `isa_element_parts.txt` for uterus, ovary, vagina, mammary, breast, clitoris, labium and vulva found nothing.

### Z-Anatomy — **not used**

- https://github.com/Z-Anatomy/Models-of-human-anatomy. **CC BY-SA 4.0** overall, with some CC BY-NC and CC BY-NC-SA components. It is built on the BodyParts3D male and has no female structures.

### Single-organ models — **not used**

- AnatomyTOOL "Vallance – 3D model Female reproductive organs" (CC BY, an illustrator's model, Sketchfab download). HRA has segmented equivalents.
- The Odile Fillod clitoris model (CC variant unclear).
- CGTrader, MakerWorld and Cults3D (proprietary licenses).
- UNIGE charts (2D, CC BY-SA).
- NIH 3D, Smithsonian 3D, Thingiverse and Printables: nothing found with both an open license and scan provenance for the missing structures.

## Generated structures — reference dimensions

| Structure | Script | Basis |
|---|---|---|
| Labia majora (fat pads, ~1 cm under the skin), labia minora, vestibule | `create_vulva.py` | Labia majora 70–120 mm long; labia minora 20–100 mm long and 7–50 mm wide; clitoris to urethra 16–45 mm (Lloyd et al., BJOG 2005;112:643–646) |
| Glans, body, crura of clitoris; vestibular bulbs | `create_clitoris.py` | O'Connell et al., J Urol 1998;159:1892–1897 and 2005;174:1189–1195; glans width 3–10 mm (Lloyd 2005) |
| Female urethra (~4 cm, 6 mm) | `create_female_urethra.py` | Gray's Anatomy, 42nd ed. (2020) |
| Female ischiocavernosus, bulbospongiosus | `create_perineal_muscles.py` | Gray's Anatomy, 42nd ed. |
| Ovarian arteries and veins; Bartholin's glands (~1 cm, at 4 and 8 o'clock); Skene's glands; perineal body; mons pubis; prepuce | `create_female_extras.py` | Gray's Anatomy, 42nd ed. |
| Breast adipose body (skin inset 4 mm, on pectoralis), areola (19 mm radius), nipple (5 mm radius); nipple at the 4th intercostal space | `body_target.py: breast_fat_from_pair, areola_and_nipple, raise_breasts` | Gray's Anatomy 42nd ed.: breast base from rib 2 to rib 6, sternal edge to mid-axillary line; nipple usually at the 4th intercostal space in the young nulliparous breast. Areola 15–60 mm diameter |
| Clitoral complex total length 9–11 cm, crura 5–9 cm | `create_clitoris.py` | O'Connell et al. 1998 and 2005; Di Marino & Lepidi, *Anatomic Study of the Clitoris and the Bulbo-Clitoral Organ*, Springer 2014 |
| Gluteofemoral subcutaneous fat (8 mm extra, tapered) | `build_female.py: gluteofemoral_fat` | Design value representing the sex difference in gluteofemoral fat (Wells JCK, Best Pract Res Clin Endocrinol Metab 2007;21:415–430) |

Placement comes from real neighbouring structures: the HRA pelvis and pubic arch, the HRA vagina, bladder neck and ovaries, the HRA skin surface, and the warped aorta, IVC and renal vein. Python-fcl checks each structure against bone, organs and thigh muscles, and a voxel test keeps it inside the skin. Each is re-checked after every fix.

## Ontology identifiers

FMA ids come from EBI OLS4: UBERON cross-references and exact FMA label matches. They are cached in `scripts/female/ontology_xrefs.json`, and nothing is guessed. When OLS has no FMA term, a part keeps its UBERON id (HRA) or a `GEN:` id (generated).

## Reference ranges used in gate A

See `scripts/female/measure.py` (REFERENCE) and VERIFICATION.md:
- **Stature:** NHANES 2015–2018 (Fryar et al., NHSR 160, 2021).
- **Body dimensions:** ANSUR II (Gordon et al., 2014, NATICK/TR-15/007).
- **Thoracic width:** Bellemare et al., Am J Respir Crit Care Med 2003;168:305–312.
- **Pelvimetry and subpubic angle:** Gray's Anatomy 42nd ed.; Williams Obstetrics.
- **Q-angle:** Horton & Hall, Phys Ther 1989;69:897–901 (women 15.8 ± 4.5°).
- **BMI:** WHO (normal 18.5–24.9 kg/m²).
- **Clitoris:** O'Connell 1998 and 2005.
- **Uterus (nulliparous ~7.5 × 5 × 2.5–3 cm):** Gray's Anatomy 42nd ed.

Several ranges are approximate bands taken from these sources rather than exact percentiles; VERIFICATION.md says which.

## Appendix A — complete HRA female (VH_F) inventory

Source: HRA *3D Reference Organ Set for Female v1.5* united GLB (`3d-vh-f-united.glb`), **CC BY 4.0** (Kristen Browne, Heidi Schlehlein; Human Reference Atlas / HuBMAP; https://doi.org/10.48539/HBM352.BTSQ.586). Every one of its 888 meshes is listed. Dimensions are the bounding-box extents in mm (x × y × z, native scale). "Used" marks what the female model includes.

| Organ system (GLB group) | Meshes |
|---|---|
| circulatory_system | 124 |
| digestive_system | 61 |
| integumentary_system | 17 |
| lymphatic_system | 14 |
| muscular_system | 16 |
| nervous_system | 362 |
| reproductive_system | 46 |
| respiratory_system | 70 |
| skeletal_system | 91 |
| urinary_system | 87 |

| Group | Node | Label | Ontology ID | Triangles | Size (mm) | Used |
|---|---|---|---|---|---|---|
| integumentary_system | `VH_F_skin` | skin of body | UBERON:0002097 | 382,640 | 967 × 1666 × 329 | yes |
| integumentary_system | `VH_F_fat_L` | Interlobar adipose tissue of left mammary gland | FMA:73166 | 66,420 | 128 × 182 × 106 | yes |
| integumentary_system | `VH_F_areolar_tubercles_L` | areolar tubercle | UBERON:0011828 | 4,621 | 20 × 22 × 10 | yes |
| integumentary_system | `VH_F_nipple_L` | left nipple | UBERON:0013772 | 9,696 | 10 × 11 × 6 | yes |
| integumentary_system | `VH_F_areola_L` | Left female areola | FMA:223679 | 23,785 | 24 × 25 × 11 | yes |
| integumentary_system | `VH_F_mammary_lobes_L` | mammary lobe | UBERON:0018140 | 75,788 | 71 × 111 × 55 | yes |
| integumentary_system | `VH_F_main_lactiferous_ducts_L` | main lactiferous duct | UBERON:0015134 | 34,755 | 57 × 101 × 57 | yes |
| integumentary_system | `VH_F_main_lactiferous_sinuses_L` | Lactiferous sinus | FMA:58088 | 11,456 | 18 × 11 × 13 | yes |
| integumentary_system | `VH_F_suspensory_ligaments_L` | Suspensory ligament of left breast | FMA:73119 | 44,278 | 68 × 74 × 47 | yes |
| integumentary_system | `VH_F_fat_R` | Interlobar adipose tissue of right mammary gland | FMA:73165 | 373,649 | 128 × 180 × 107 | yes |
| integumentary_system | `VH_F_areolar_tubercles_R` | areolar tubercle | UBERON:0011828 | 4,621 | 20 × 22 × 10 | yes |
| integumentary_system | `VH_F_nipple_R` | right nipple | UBERON:0013773 | 9,696 | 10 × 11 × 6 | yes |
| integumentary_system | `VH_F_areola_R` | Right female areola | FMA:223677 | 23,785 | 24 × 25 × 11 | yes |
| integumentary_system | `VH_F_main_lactiferous_sinuses_R` | Lactiferous sinus | FMA:58088 | 11,449 | 18 × 11 × 13 | yes |
| integumentary_system | `VH_F_main_lactiferous_ducts_R` | main lactiferous duct | UBERON:0015134 | 34,660 | 58 × 101 × 57 | yes |
| integumentary_system | `VH_F_mammary_lobes_R` | mammary lobe | UBERON:0018140 | 75,788 | 71 × 111 × 55 | yes |
| integumentary_system | `VH_F_suspensory_ligaments_R` | Suspensory ligament of right breast | FMA:73118 | 51,682 | 68 × 74 × 47 | yes |
| nervous_system | `VH_F_retina_R` | Right retina | FMA:58302 | 10,778 | 22 × 22 × 18 |  |
| nervous_system | `VH_F_fovea_R` | Right fovea centralis | FMA:58661 | 226 | 1 × 1 × 0 |  |
| nervous_system | `VH_F_macula_lutea_R` | Right macula lutea | FMA:58638 | 2,224 | 4 × 4 × 1 |  |
| nervous_system | `VH_F_optic_disc_R` | Right optic disc | FMA:58635 | 12,418 | 2 × 3 × 1 |  |
| nervous_system | `VH_F_palpebral_conjunctiva_of_right_upper_eyelid` | Palpebral conjunctiva of right upper eyelid | FMA:223076 | 8,984 | 17 × 8 × 5 |  |
| nervous_system | `VH_F_palpebral_conjunctiva_of_right_lower_eyelid` | Palpebral conjunctiva of right lower eyelid | FMA:223074 | 8,694 | 18 × 9 × 5 |  |
| nervous_system | `VH_F_sclera_R` | Right sclera | FMA:58271 | 12,192 | 24 × 24 × 23 |  |
| nervous_system | `VH_F_optic_choroid_R` | Right choroid | FMA:58299 | 12,100 | 22 × 22 × 19 |  |
| nervous_system | `VH_F_pupil_R` | right pupil | UBERON:0010224 | 960 | 3 × 3 × 0 |  |
| nervous_system | `VH_F_ciliary_processes_R` | ciliary processes | UBERON:0010427 | 25,536 | 13 × 13 × 1 |  |
| nervous_system | `VH_F_suspensory_ligament_of_lens_R` | Suspensory ligament of right lens | FMA:58839 | 10,456 | 15 × 15 × 2 |  |
| nervous_system | `VH_F_ora_serrata_of_retina_R` | Right ora serrata | FMA:58601 | 13,326 | 15 × 15 × 1 |  |
| nervous_system | `VH_F_corneo_scleral_junction_R` | Right corneoscleral junction | FMA:58343 | 4,928 | 12 × 12 × 1 |  |
| nervous_system | `VH_F_lens_R` | Right lens | FMA:58242 | 1,684 | 8 × 8 × 4 |  |
| nervous_system | `VH_F_schlemms_canal_R` | Right scleral venous sinus | FMA:51874 | 25,232 | 11 × 11 × 0 |  |
| nervous_system | `VH_F_aqueous_humor_R` | Aqueous humor of right eyeball | FMA:58820 | 5,697 | 10 × 11 × 3 |  |
| nervous_system | `VH_F_ciliary_body_R` | Right ciliary body | FMA:58296 | 15,886 | 15 × 15 × 2 |  |
| nervous_system | `VH_F_ciliary_muscle_R` | Right ciliary muscle | FMA:49152 | 54,614 | 15 × 15 × 2 |  |
| nervous_system | `VH_F_trabecular_meshwork_R` | eye trabecular meshwork | UBERON:0005969 | 24,552 | 11 × 11 × 1 |  |
| nervous_system | `VH_F_iris_R` | Right iris | FMA:58236 | 32,829 | 10 × 10 × 1 |  |
| nervous_system | `VH_F_bulbar_conjunctiva_R` | Right bulbar conjunctiva | FMA:59028 | 16,062 | 18 × 17 × 2 |  |
| nervous_system | `VH_F_cornea_R` | Right cornea | FMA:58239 | 9,788 | 12 × 12 × 4 |  |
| nervous_system | `VH_F_vitreous_humor_R` | Humor of right vitreous body | FMA:261236 | 37,464 | 21 × 21 × 18 |  |
| nervous_system | `VH_F_retina_L` | Left retina | FMA:58303 | 10,778 | 22 × 22 × 18 |  |
| nervous_system | `VH_F_fovea_L` | Left fovea centralis | FMA:58663 | 226 | 1 × 1 × 0 |  |
| nervous_system | `VH_F_macula_lutea_L` | Left macula lutea | FMA:58639 | 2,224 | 4 × 4 × 1 |  |
| nervous_system | `VH_F_optic_disc_L` | Left optic disc | FMA:58636 | 12,418 | 2 × 3 × 1 |  |
| nervous_system | `VH_F_palpebral_conjunctiva_of_left_upper_eyelid` | Palpebral conjunctiva of left upper eyelid | FMA:223078 | 8,984 | 17 × 8 × 5 |  |
| nervous_system | `VH_F_palpebral_conjunctiva_of_left_lower_eyelid` | Palpebral conjunctiva of left lower eyelid | FMA:223075 | 8,694 | 18 × 9 × 5 |  |
| nervous_system | `VH_F_vitreous_humor_L` | Humor of left vitreous body | FMA:261238 | 37,464 | 21 × 21 × 18 |  |
| nervous_system | `VH_F_cornea_L` | Left cornea | FMA:58240 | 9,788 | 12 × 12 × 4 |  |
| nervous_system | `VH_F_bulbar_conjunctiva_L` | Left bulbar conjunctiva | FMA:59029 | 16,062 | 18 × 17 × 2 |  |
| nervous_system | `VH_F_iris_L` | Left iris | FMA:58237 | 32,829 | 10 × 10 × 1 |  |
| nervous_system | `VH_F_trabecular_meshwork_L` | eye trabecular meshwork | UBERON:0005969 | 24,552 | 11 × 11 × 1 |  |
| nervous_system | `VH_F_ciliary_body_L` | Left ciliary body | FMA:58297 | 15,886 | 15 × 15 × 2 |  |
| nervous_system | `VH_F_ciliary_muscle_L` | Left ciliary muscle | FMA:49153 | 54,614 | 15 × 15 × 2 |  |
| nervous_system | `VH_F_aqueous_humor_L` | Aqueous humor of left eyeball | FMA:58821 | 5,697 | 10 × 11 × 3 |  |
| nervous_system | `VH_F_schlemms_canal_L` | Left scleral venous sinus | FMA:51875 | 25,232 | 11 × 11 × 0 |  |
| nervous_system | `VH_F_lens_L` | Left lens | FMA:58243 | 1,684 | 8 × 8 × 4 |  |
| nervous_system | `VH_F_corneo_scleral_junction_L` | Left corneoscleral junction | FMA:58344 | 4,928 | 12 × 12 × 1 |  |
| nervous_system | `VH_F_ora_serrata_of_retina_L` | Left ora serrata | FMA:58602 | 13,326 | 15 × 15 × 1 |  |
| nervous_system | `VH_F_suspensory_ligament_of_lens_L` | Suspensory ligament of left lens | FMA:58840 | 10,456 | 15 × 15 × 2 |  |
| nervous_system | `VH_F_ciliary_processes_L` | ciliary processes | UBERON:0010427 | 25,536 | 13 × 13 × 1 |  |
| nervous_system | `VH_F_pupil_L` | left pupil | UBERON:0010223 | 960 | 3 × 3 × 0 |  |
| nervous_system | `VH_F_optic_choroid_L` | Left choroid | FMA:58300 | 12,100 | 22 × 22 × 19 |  |
| nervous_system | `VH_F_sclera_L` | Left sclera | FMA:58272 | 12,192 | 24 × 24 × 23 |  |
| nervous_system | `VH_F_dura_mater_right` | dura mater | UBERON:0002363 | 19,318 | 30 × 8 × 42 |  |
| nervous_system | `VH_F_right_optic_nerve` | Right optic nerve | FMA:50875 | 9,732 | 30 × 7 × 42 |  |
| nervous_system | `VH_F_dura_mater_left` | dura mater | UBERON:0002363 | 19,318 | 31 × 8 × 42 |  |
| nervous_system | `VH_F_left_optic_nerve` | Left optic nerve | FMA:50878 | 9,732 | 31 × 7 × 41 |  |
| nervous_system | `VH_F_optic_chiasm` | optic chiasma | UBERON:0000959 | 3,706 | 13 × 8 × 12 |  |
| nervous_system | `Allen_olfactory_bulb_L` | olfactory bulb | UBERON:0002264 | 8 | 5 × 4 × 9 |  |
| nervous_system | `Allen_anterior_olfactory_nucleus_L` | anterior olfactory nucleus | UBERON:0002266 | 14 | 5 × 8 × 8 |  |
| nervous_system | `Allen_piriform_region_L` | piriform cortex | UBERON:0004725 | 492 | 15 × 14 × 8 |  |
| nervous_system | `Allen_frontal_agranular_insular_cortex_area_Fl_L` | - | - | 88 | 8 × 4 × 3 |  |
| nervous_system | `Allen_temporal_agranular_insular_cortex_area_Tl_L` | - | - | 480 | 13 × 11 × 5 |  |
| nervous_system | `Allen_head_of_caudate_L` | - | - | 2,466 | 15 × 27 × 26 |  |
| nervous_system | `Allen_body_of_caudate_L` | - | - | 1,708 | 16 × 16 × 37 |  |
| nervous_system | `Allen_tail_of_caudate_L` | - | - | 610 | 18 × 26 × 29 |  |
| nervous_system | `Allen_putamen_L` | left putamen | UBERON:0008884 | 2,098 | 20 × 24 × 41 |  |
| nervous_system | `Allen_nucleus_accumbens_L` | - | - | 472 | 16 × 13 × 11 |  |
| nervous_system | `Allen_external_segment_of_globus_pallidus_L` | - | - | 638 | 16 × 13 × 23 |  |
| nervous_system | `Allen_internal_segment_of_globus_pallidus_L` | - | - | 454 | 13 × 8 × 13 |  |
| nervous_system | `Allen_claustrum_L` | - | - | 3,258 | 15 × 37 × 39 |  |
| nervous_system | `Allen_basal_forebrain_L` | - | - | 868 | 23 × 16 × 13 |  |
| nervous_system | `Allen_septal_nuclei_L` | - | - | 902 | 4 × 20 × 32 |  |
| nervous_system | `Allen_amygdaloid_complex_L` | - | - | 680 | 20 × 13 × 18 |  |
| nervous_system | `Allen_anterior_amygdaloid_area_L` | - | - | 166 | 9 × 5 × 7 |  |
| nervous_system | `Allen_central_nuclear_group_L` | - | - | 92 | 5 × 5 × 7 |  |
| nervous_system | `Allen_lateral_nucleus_L` | - | - | 498 | 13 × 11 × 10 |  |
| nervous_system | `Allen_basolateral_nucleus_basal_nucleus_L` | - | - | 424 | 14 × 10 × 11 |  |
| nervous_system | `Allen_basomedial_nucleus_accessory_basal_nucleus_L` | - | - | 150 | 8 × 6 × 9 |  |
| nervous_system | `Allen_anterior_cortical_nucleus_L` | - | - | 180 | 9 × 7 × 8 |  |
| nervous_system | `Allen_posterior_cortical_nucleus_L` | - | - | 102 | 7 × 5 × 5 |  |
| nervous_system | `Allen_medial_nucleus_L` | - | - | 86 | 5 × 4 × 6 |  |
| nervous_system | `Allen_amygdalohippocampal_area_L` | - | - | 106 | 8 × 4 × 5 |  |
| nervous_system | `Allen_bed_nucleus_of_stria_terminalis_L` | - | - | 576 | 10 × 22 × 18 |  |
| nervous_system | `Allen_thalamus_L` | - | - | 5,702 | 25 × 29 × 33 |  |
| nervous_system | `Allen_anterior_nuclear_complex_of_thalamus_L` | - | - | 244 | 6 × 9 × 11 |  |
| nervous_system | `Allen_lateral_dorsal_nucleus_of_thalamus_L` | - | - | 222 | 9 × 9 × 14 |  |
| nervous_system | `Allen_mediodorsal_nucleus_of_thalamus_L` | - | - | 760 | 9 × 14 × 18 |  |
| nervous_system | `Allen_reuniens_nucleus_medioventral_nucleus_of_thalamus_L` | - | - | 160 | 4 × 6 × 9 |  |
| nervous_system | `Allen_lateral_posterior_nucleus_of_thalamus_L` | - | - | 380 | 11 × 9 × 12 |  |
| nervous_system | `Allen_pulvinar_of_thalamus_L` | - | - | 894 | 17 × 17 × 11 |  |
| nervous_system | `Allen_ventral_anterior_nucleus_of_thalamus_L` | - | - | 820 | 14 × 18 × 18 |  |
| nervous_system | `Allen_ventral_lateral_nucleus_of_thalamus_L` | - | - | 878 | 12 × 18 × 17 |  |
| nervous_system | `Allen_ventral_posterior_lateral_nucleus_L` | - | - | 442 | 12 × 13 × 13 |  |
| nervous_system | `Allen_ventral_posterior_medial_nucleus_L` | - | - | 186 | 7 × 8 × 8 |  |
| nervous_system | `Allen_dorsal_lateral_geniculate_nucleus_L` | - | - | 170 | 6 × 6 × 8 |  |
| nervous_system | `Allen_medial_geniculate_nuclei_L` | - | - | 120 | 6 × 6 × 6 |  |
| nervous_system | `Allen_centromedian_nucleus_of_thalamus_L` | - | - | 246 | 7 × 7 × 12 |  |
| nervous_system | `Allen_parafascicular_nucleus_of_thalamus_L` | - | - | 112 | 6 × 5 × 10 |  |
| nervous_system | `Allen_habenular_nuclei_L` | - | - | 110 | 5 × 8 × 5 |  |
| nervous_system | `Allen_pineal_body_L` | pineal body | UBERON:0001905 | 98 | 3 × 4 × 8 |  |
| nervous_system | `Allen_zona_incerta_L` | - | - | 314 | 15 × 12 × 15 |  |
| nervous_system | `Allen_supraoptic_region_of_HTH_L` | - | - | 340 | 10 × 13 × 7 |  |
| nervous_system | `Allen_preoptic_region_of_HTH_L` | - | - | 222 | 7 × 12 × 8 |  |
| nervous_system | `Allen_tuberal_region_of_HTH_L` | - | - | 642 | 14 × 18 × 13 |  |
| nervous_system | `Allen_white_matter_of_forebrain_L` | - | - | 44,758 | 68 × 130 × 159 |  |
| nervous_system | `Allen_anterior_commissure_L` | anterior commissure | UBERON:0000935 | 274 | 30 × 11 × 10 |  |
| nervous_system | `Allen_corpus_callosum_L` | corpus callosum | UBERON:0002336 | 6,034 | 18 × 36 × 78 |  |
| nervous_system | `Allen_fornix_L` | fornix of brain | UBERON:0000052 | 644 | 17 × 27 × 37 |  |
| nervous_system | `Allen_mammillothalamic_tract_L` | - | - | 124 | 5 × 19 × 3 |  |
| nervous_system | `Allen_optic_tract_L` | optic tract | UBERON:0001908 | 276 | 22 × 7 × 24 |  |
| nervous_system | `Allen_anterior_horn_of_lateral_ventricle_L` | - | - | 2,708 | 17 × 25 × 46 |  |
| nervous_system | `Allen_body_of_lateral_ventricle_L` | - | - | 1,544 | 26 × 28 × 30 |  |
| nervous_system | `Allen_posterior_horn_of_lateral_ventricle_L` | - | - | 418 | 12 × 12 × 23 |  |
| nervous_system | `Allen_inferior_horn_of_lateral_ventricle_L` | - | - | 1,328 | 21 × 22 × 39 |  |
| nervous_system | `Allen_third_ventricle_L` | - | - | 1,168 | 4 × 20 × 36 |  |
| nervous_system | `Allen_cerebellar_vermis_L` | cerebellar vermis | UBERON:0004720 | 4,732 | 7 × 51 × 37 |  |
| nervous_system | `Allen_cerebellar_deep_nuclei_L` | - | - | 654 | 15 × 15 × 15 |  |
| nervous_system | `Allen_white_matter_of_hindbrain_L` | - | - | 14,264 | 48 × 41 × 53 |  |
| nervous_system | `Allen_olfactory_tract_L` | - | - | 142 | 8 × 3 × 29 |  |
| nervous_system | `Allen_precentral_gyrus_L` | precentral gyrus | UBERON:0002703 | 11,082 | 56 × 68 × 65 |  |
| nervous_system | `Allen_superior_frontal_gyrus_L` | superior frontal gyrus | UBERON:0002661 | 20,300 | 33 × 54 × 100 |  |
| nervous_system | `Allen_middle_frontal_gyrus_L` | middle frontal gyrus | UBERON:0002702 | 13,462 | 35 × 52 × 82 |  |
| nervous_system | `Allen_inferior_frontal_gyrus_triangular_part_L` | triangular part of inferior frontal gyrus | UBERON:0002629 | 5,096 | 30 × 31 × 30 |  |
| nervous_system | `Allen_inferior_frontal_gyrus_opercular_part_L` | opercular part of inferior frontal gyrus | UBERON:0002980 | 2,974 | 31 × 33 × 21 |  |
| nervous_system | `Allen_gyrus_rectus_straight_gyrus_L` | gyrus rectus | UBERON:0004671 | 1,866 | 14 × 22 × 50 |  |
| nervous_system | `Allen_medial_orbital_gyrus_L` | medial orbital gyrus | UBERON:0002570 | 2,406 | 20 × 23 × 47 |  |
| nervous_system | `Allen_anterior_intermediate_orbital_gyrus_L` | intermediate orbital gyrus | UBERON:0002644 | 1,162 | 23 × 18 × 24 |  |
| nervous_system | `Allen_posterior_intermediate_orbital_gyrus_L` | intermediate orbital gyrus | UBERON:0002644 | 1,938 | 24 × 25 × 28 |  |
| nervous_system | `Allen_lateral_orbital_gyrus_L` | lateral orbital gyrus | UBERON:0002564 | 2,986 | 26 × 23 × 35 |  |
| nervous_system | `Allen_paracentral_lobule_rostral_part_L` | anterior segment of paracentral lobule | UBERON:0035932 | 3,082 | 18 × 39 × 28 |  |
| nervous_system | `Allen_frontal_operculum_L` | frontal operculum | UBERON:0002947 | 1,330 | 18 × 18 × 32 |  |
| nervous_system | `Allen_postcentral_gyrus_L` | postcentral gyrus | UBERON:0002581 | 9,084 | 60 × 59 × 66 |  |
| nervous_system | `Allen_supraparietal_lobule_L` | - | - | 9,278 | 36 × 53 × 47 |  |
| nervous_system | `Allen_supramarginal_gyrus_L` | - | - | 4,734 | 34 × 41 × 40 |  |
| nervous_system | `Allen_angular_gyrus_L` | - | - | 6,246 | 36 × 47 × 39 |  |
| nervous_system | `Allen_precuneus_L` | precuneus cortex | UBERON:0006093 | 9,366 | 27 × 71 × 43 |  |
| nervous_system | `Allen_paracentral_lobule_caudal_part_L` | - | - | 2,020 | 18 × 34 × 23 |  |
| nervous_system | `Allen_superior_temporal_gyrus_L` | superior temporal gyrus | UBERON:0002769 | 4,198 | 33 × 40 × 75 |  |
| nervous_system | `Allen_middle_temporal_gyrus_L` | middle temporal gyrus | UBERON:0002771 | 10,316 | 42 × 42 × 96 |  |
| nervous_system | `Allen_inferior_temporal_gyrus_L` | inferior temporal gyrus | UBERON:0002751 | 7,058 | 32 × 29 × 82 |  |
| nervous_system | `Allen_occipitotemporal_fusiform_gyrus_temporal_part_L` | - | - | 4,584 | 31 × 22 × 42 |  |
| nervous_system | `Allen_transverse_temporal_gyrus_Heschls_gyrus_L` | - | - | 1,434 | 29 × 17 × 30 |  |
| nervous_system | `Allen_planum_temporale_L` | planum temporale | UBERON:0022268 | 1,646 | 24 × 17 × 33 |  |
| nervous_system | `Allen_temporal_pole_L` | temporal pole | UBERON:0002576 | 2,570 | 32 × 35 × 22 |  |
| nervous_system | `Allen_planum_polare_L` | planum polare | UBERON:0023861 | 2,336 | 25 × 25 × 45 |  |
| nervous_system | `Allen_occipital_pole_L` | occipital pole | UBERON:0002902 | 1,520 | 24 × 34 × 19 |  |
| nervous_system | `Allen_cuneus_L` | cuneus cortex | UBERON:0006092 | 6,032 | 25 × 46 × 39 |  |
| nervous_system | `Allen_lingual_gyrus_medial_occipitotemporal_gyrus_L` | lingual gyrus | UBERON:0002943 | 7,406 | 31 × 35 × 63 |  |
| nervous_system | `Allen_lateral_occipitotemporal_fusiform_gyrus_occipital_part_L` | occipital fusiform gyrus | UBERON:0022364 | 1,908 | 30 × 19 × 17 |  |
| nervous_system | `Allen_inferior_occipital_gyrus_L` | inferior occipital gyrus | UBERON:0014608 | 4,628 | 38 × 42 × 40 |  |
| nervous_system | `Allen_superior_occipital_gyrus_L` | superior occipital gyrus | UBERON:0002948 | 6,032 | 41 × 51 × 32 |  |
| nervous_system | `Allen_cingulate_gyrus_rostral_anterior_part_L` | anterior cingulate gyrus | UBERON:0002756 | 3,508 | 14 × 49 × 57 |  |
| nervous_system | `Allen_cingulate_gyrus_caudal_posterior_part_L` | posterior cingulate gyrus | UBERON:0002740 | 4,316 | 27 × 55 × 46 |  |
| nervous_system | `Allen_ingulo_parahippocampal_isthmus_L` | isthmus of cingulate gyrus | UBERON:0002738 | 246 | 13 × 11 × 12 |  |
| nervous_system | `Allen_subcallosal_gyrus_parolfactory_gyrus_L` | subcallosal area | UBERON:0003020 | 406 | 7 × 18 × 17 |  |
| nervous_system | `Allen_anterior_parahippocampal_gyrus_L` | anterior parahippocampal gyrus | UBERON:0022383 | 1,342 | 20 × 19 × 30 |  |
| nervous_system | `Allen_posterior_parahippocampal_gyrus_L` | posterior parahippocampal gyrus | UBERON:0002657 | 1,110 | 21 × 18 × 25 |  |
| nervous_system | `Allen_gyrus_ambiens_L` | - | - | 180 | 6 × 8 × 13 |  |
| nervous_system | `Allen_head_of_hippocampus_L` | - | - | 516 | 24 × 14 × 16 |  |
| nervous_system | `Allen_body_of_hippocampus_L` | - | - | 430 | 19 × 11 × 14 |  |
| nervous_system | `Allen_tail_of_hippocampus_L` | - | - | 524 | 23 × 16 × 17 |  |
| nervous_system | `Allen_long_insular_gyri_L` | - | - | 1,218 | 15 × 30 × 40 |  |
| nervous_system | `Allen_short_insular_gyri_L` | - | - | 1,480 | 21 × 33 × 42 |  |
| nervous_system | `Allen_limen_insula_L` | - | - | 64 | 8 × 6 × 4 |  |
| nervous_system | `Allen_pretectal_region_L` | - | - | 56 | 11 × 9 × 7 |  |
| nervous_system | `Allen_substantia_nigra_L` | substantia nigra | UBERON:0002038 | 118 | 9 × 11 × 12 |  |
| nervous_system | `Allen_superior_colliculus_L` | superior colliculus | UBERON:0001945 | 72 | 10 × 8 × 8 |  |
| nervous_system | `Allen_cerebral_peduncle_crus_cerebri_L` | cerebral peduncle | UBERON:0002623 | 462 | 17 × 17 × 19 |  |
| nervous_system | `Allen_superior_cerebellar_peduncle_brachium_conjunctivum_L` | - | - | 258 | 6 × 18 × 11 |  |
| nervous_system | `Allen_cerebral_aqueduct_L` | - | - | 76 | 4 × 20 × 9 |  |
| nervous_system | `Allen_paravermis_of_cerebellum_L` | - | - | 3,423 | 16 × 59 × 56 |  |
| nervous_system | `Allen_lateral_hemisphere_of_cerebellum_L` | - | - | 11,928 | 41 × 49 × 60 |  |
| nervous_system | `Allen_basilar_part_of_pons_L` | pontine nuclear group | UBERON:0002151 | 940 | 20 × 28 × 21 |  |
| nervous_system | `Allen_pontine_tegmentum_L` | pontine tegmentum | UBERON:0003023 | 528 | 13 × 29 × 13 |  |
| nervous_system | `Allen_pyramidal_part_of_medulla_oblongata_L` | - | - | 116 | 5 × 23 × 4 |  |
| nervous_system | `Allen_tegmentum_of_medulla_oblongata_L` | - | - | 632 | 11 × 26 × 14 |  |
| nervous_system | `Allen_inferior_olive_L` | - | - | 124 | 4 × 13 × 7 |  |
| nervous_system | `Allen_middle_cerebellar_peduncle_L` | - | - | 332 | 15 × 14 × 14 |  |
| nervous_system | `Allen_fourth_ventricle_L` | fourth ventricle | UBERON:0002422 | 426 | 14 × 39 × 16 |  |
| nervous_system | `Allen_central_canal_of_medulla_oblongata_L` | - | - | 12 | 1 × 10 × 3 |  |
| nervous_system | `Allen_midline_nuclear_complex_L` | - | - | 248 | 5 × 14 × 18 |  |
| nervous_system | `Allen_lateral_olfactory_gyrus_L` | - | - | 130 | 14 × 8 × 7 |  |
| nervous_system | `Allen_parietal_operculum_L` | parietal operculum | UBERON:0002911 | 1,234 | 30 × 16 × 39 |  |
| nervous_system | `Allen_optic_radiation_L` | optic radiation | UBERON:0022264 | 84 | 9 × 8 × 13 |  |
| nervous_system | `Allen_posteroventral_putamen_L` | - | - | 2,100 | 18 × 50 × 82 |  |
| nervous_system | `Allen_atrium_of_lateral_ventricle_L` | - | - | 622 | 12 × 23 × 36 |  |
| nervous_system | `Allen_paracingulate_gyrus_L` | - | - | 824 | 35 × 28 × 20 |  |
| nervous_system | `Allen_rostral_gyrus_L` | - | - | 1,160 | 28 × 38 × 19 |  |
| nervous_system | `Allen_frontomarginal_gyrus_L` | - | - | 1,084 | 25 × 25 × 48 |  |
| nervous_system | `Allen_frontal_pole_L` | - | - | 2,116 | 23 × 29 × 65 |  |
| nervous_system | `Allen_inferior_cerebellar_peduncle_L` | - | - | 112 | 5 × 16 × 10 |  |
| nervous_system | `Allen_perirhinal_gyrus_rostral_part_of_FuGt_L` | - | - | 90 | 17 × 20 × 21 |  |
| nervous_system | `Allen_olfactory_bulb_R` | - | - | 8 | 4 × 4 × 9 |  |
| nervous_system | `Allen_anterior_olfactory_nucleus_R` | - | - | 14 | 5 × 8 × 8 |  |
| nervous_system | `Allen_piriform_region_R` | - | - | 492 | 15 × 14 × 8 |  |
| nervous_system | `Allen_frontal_agranular_insular_cortex_area_Fl_R` | - | - | 88 | 8 × 4 × 3 |  |
| nervous_system | `Allen_temporal_agranular_insular_cortex_area_Tl_R` | - | - | 480 | 13 × 11 × 6 |  |
| nervous_system | `Allen_head_of_caudate_R` | - | - | 2,466 | 16 × 27 × 26 |  |
| nervous_system | `Allen_body_of_caudate_R` | - | - | 1,708 | 13 × 16 × 37 |  |
| nervous_system | `Allen_tail_of_caudate_R` | - | - | 610 | 17 × 26 × 28 |  |
| nervous_system | `Allen_putamen_R` | right putamen | UBERON:0008885 | 2,098 | 18 × 25 × 42 |  |
| nervous_system | `Allen_nucleus_accumbens_R` | - | - | 472 | 16 × 13 × 10 |  |
| nervous_system | `Allen_external_segment_of_globus_pallidus_R` | - | - | 638 | 15 × 13 × 24 |  |
| nervous_system | `Allen_internal_segment_of_globus_pallidus_R` | - | - | 454 | 12 × 9 × 14 |  |
| nervous_system | `Allen_claustrum_R` | - | - | 3,258 | 14 × 37 × 39 |  |
| nervous_system | `Allen_basal_forebrain_R` | - | - | 868 | 22 × 17 × 14 |  |
| nervous_system | `Allen_septal_nuclei_R` | - | - | 902 | 4 × 20 × 32 |  |
| nervous_system | `Allen_amygdaloid_complex_R` | - | - | 680 | 20 × 13 × 18 |  |
| nervous_system | `Allen_anterior_amygdaloid_area_R` | - | - | 166 | 9 × 6 × 6 |  |
| nervous_system | `Allen_central_nuclear_group_R` | - | - | 92 | 5 × 5 × 7 |  |
| nervous_system | `Allen_lateral_nucleus_R` | - | - | 498 | 13 × 11 × 10 |  |
| nervous_system | `Allen_basolateral_nucleus_basal_nucleus_R` | - | - | 424 | 15 × 10 × 11 |  |
| nervous_system | `Allen_basomedial_nucleus_accessory_basal_nucleus_R` | - | - | 150 | 7 × 6 × 9 |  |
| nervous_system | `Allen_anterior_cortical_nucleus_R` | - | - | 180 | 9 × 7 × 8 |  |
| nervous_system | `Allen_posterior_cortical_nucleus_R` | - | - | 102 | 7 × 5 × 5 |  |
| nervous_system | `Allen_medial_nucleus_R` | - | - | 86 | 5 × 4 × 6 |  |
| nervous_system | `Allen_amygdalohippocampal_area_R` | - | - | 106 | 7 × 4 × 5 |  |
| nervous_system | `Allen_bed_nucleus_of_stria_terminalis_R` | - | - | 576 | 10 × 22 × 19 |  |
| nervous_system | `Allen_thalamus_R` | - | - | 5,702 | 24 × 29 × 33 |  |
| nervous_system | `Allen_anterior_nuclear_complex_of_thalamus_R` | - | - | 244 | 6 × 9 × 11 |  |
| nervous_system | `Allen_lateral_dorsal_nucleus_of_thalamus_R` | - | - | 222 | 8 × 9 × 15 |  |
| nervous_system | `Allen_mediodorsal_nucleus_of_thalamus_R` | - | - | 760 | 9 × 14 × 19 |  |
| nervous_system | `Allen_reuniens_nucleus_medioventral_nucleus_of_thalamus_R` | - | - | 160 | 4 × 6 × 9 |  |
| nervous_system | `Allen_lateral_posterior_nucleus_of_thalamus_R` | - | - | 380 | 10 × 9 × 12 |  |
| nervous_system | `Allen_pulvinar_of_thalamus_R` | - | - | 894 | 17 × 18 × 11 |  |
| nervous_system | `Allen_ventral_anterior_nucleus_of_thalamus_R` | - | - | 820 | 14 × 17 × 19 |  |
| nervous_system | `Allen_ventral_lateral_nucleus_of_thalamus_R` | - | - | 878 | 11 × 17 × 17 |  |
| nervous_system | `Allen_ventral_posterior_lateral_nucleus_R` | - | - | 442 | 12 × 13 × 13 |  |
| nervous_system | `Allen_ventral_posterior_medial_nucleus_R` | - | - | 186 | 7 × 8 × 8 |  |
| nervous_system | `Allen_dorsal_lateral_geniculate_nucleus_R` | - | - | 170 | 6 × 7 × 8 |  |
| nervous_system | `Allen_medial_geniculate_nuclei_R` | - | - | 120 | 7 × 6 × 6 |  |
| nervous_system | `Allen_centromedian_nucleus_of_thalamus_R` | - | - | 246 | 7 × 7 × 12 |  |
| nervous_system | `Allen_parafascicular_nucleus_of_thalamus_R` | - | - | 112 | 5 × 5 × 10 |  |
| nervous_system | `Allen_habenular_nuclei_R` | - | - | 110 | 5 × 8 × 5 |  |
| nervous_system | `Allen_pineal_body_R` | pineal body | UBERON:0001905 | 98 | 3 × 4 × 8 |  |
| nervous_system | `Allen_zona_incerta_R` | - | - | 314 | 14 × 12 × 16 |  |
| nervous_system | `Allen_supraoptic_region_of_HTH_R` | - | - | 340 | 10 × 13 × 7 |  |
| nervous_system | `Allen_white_matter_of_forebrain_R` | - | - | 44,758 | 66 × 129 × 159 |  |
| nervous_system | `Allen_anterior_commissure_R` | anterior commissure | UBERON:0000935 | 274 | 29 × 13 × 11 |  |
| nervous_system | `Allen_corpus_callosum_R` | corpus callosum | UBERON:0002336 | 6,034 | 18 × 36 × 78 |  |
| nervous_system | `Allen_fornix_R` | fornix of brain | UBERON:0000052 | 644 | 15 × 27 × 38 |  |
| nervous_system | `Allen_mammillothalamic_tract_R` | - | - | 124 | 6 × 19 × 4 |  |
| nervous_system | `Allen_optic_tract_R` | optic tract | UBERON:0001908 | 276 | 21 × 6 × 25 |  |
| nervous_system | `Allen_anterior_horn_of_lateral_ventricle_R` | - | - | 2,708 | 18 × 25 × 45 |  |
| nervous_system | `Allen_body_of_lateral_ventricle_R` | - | - | 1,544 | 23 × 28 × 31 |  |
| nervous_system | `Allen_posterior_horn_of_lateral_ventricle_R` | - | - | 418 | 14 × 11 × 22 |  |
| nervous_system | `Allen_inferior_horn_of_lateral_ventricle_R` | - | - | 1,328 | 20 × 22 × 40 |  |
| nervous_system | `Allen_third_ventricle_R` | - | - | 1,168 | 5 × 20 × 36 |  |
| nervous_system | `Allen_cerebellar_vermis_R` | - | - | 4,732 | 7 × 51 × 37 |  |
| nervous_system | `Allen_cerebellar_deep_nuclei_R` | - | - | 654 | 14 × 15 × 15 |  |
| nervous_system | `Allen_white_matter_of_hindbrain_R` | - | - | 14,264 | 47 × 42 × 53 |  |
| nervous_system | `Allen_olfactory_tract_R` | - | - | 142 | 6 × 3 × 30 |  |
| nervous_system | `Allen_precentral_gyrus_R` | precentral gyrus | UBERON:0002703 | 11,082 | 57 × 70 × 62 |  |
| nervous_system | `Allen_superior_frontal_gyrus_R` | superior frontal gyrus | UBERON:0002661 | 20,300 | 34 × 55 × 99 |  |
| nervous_system | `Allen_middle_frontal_gyrus_R` | middle frontal gyrus | UBERON:0002702 | 13,462 | 34 × 53 × 81 |  |
| nervous_system | `Allen_inferior_frontal_gyrus_triangular_part_R` | triangular part of inferior frontal gyrus | UBERON:0002629 | 5,096 | 30 × 30 × 31 |  |
| nervous_system | `Allen_inferior_frontal_gyrus_opercular_part_R` | opercular part of inferior frontal gyrus | UBERON:0002980 | 2,974 | 31 × 33 × 20 |  |
| nervous_system | `Allen_gyrus_rectus_straight_gyrus_R` | gyrus rectus | UBERON:0004671 | 1,866 | 13 × 21 × 50 |  |
| nervous_system | `Allen_medial_orbital_gyrus_R` | medial orbital gyrus | UBERON:0002570 | 2,406 | 19 × 23 × 48 |  |
| nervous_system | `Allen_anterior_intermediate_orbital_gyrus_R` | intermediate orbital gyrus | UBERON:0002644 | 1,162 | 23 × 18 × 24 |  |
| nervous_system | `Allen_posterior_intermediate_orbital_gyrus_R` | intermediate orbital gyrus | UBERON:0002644 | 1,938 | 26 × 24 × 27 |  |
| nervous_system | `Allen_lateral_orbital_gyrus_R` | lateral orbital gyrus | UBERON:0002564 | 2,986 | 27 × 23 × 35 |  |
| nervous_system | `Allen_paracentral_lobule_rostral_part_R` | anterior segment of paracentral lobule | UBERON:0035932 | 3,082 | 17 × 39 × 27 |  |
| nervous_system | `Allen_frontal_operculum_R` | frontal operculum | UBERON:0002947 | 1,330 | 17 × 19 × 31 |  |
| nervous_system | `Allen_postcentral_gyrus_R` | postcentral gyrus | UBERON:0002581 | 9,084 | 60 × 62 × 63 |  |
| nervous_system | `Allen_supraparietal_lobule_R` | - | - | 9,278 | 39 × 54 × 46 |  |
| nervous_system | `Allen_supramarginal_gyrus_R` | - | - | 4,734 | 35 × 41 × 39 |  |
| nervous_system | `Allen_angular_gyrus_R` | - | - | 6,246 | 37 × 47 × 38 |  |
| nervous_system | `Allen_precuneus_R` | precuneus cortex | UBERON:0006093 | 9,366 | 27 × 71 × 42 |  |
| nervous_system | `Allen_paracentral_lobule_caudal_part_R` | - | - | 2,020 | 17 × 34 × 22 |  |
| nervous_system | `Allen_superior_temporal_gyrus_R` | superior temporal gyrus | UBERON:0002769 | 4,198 | 31 × 39 × 77 |  |
| nervous_system | `Allen_middle_temporal_gyrus_R` | middle temporal gyrus | UBERON:0002771 | 10,316 | 38 × 42 × 97 |  |
| nervous_system | `Allen_inferior_temporal_gyrus_R` | inferior temporal gyrus | UBERON:0002751 | 7,058 | 30 × 28 × 83 |  |
| nervous_system | `Allen_occipitotemporal_fusiform_gyrus_temporal_part_R` | - | - | 4,584 | 29 × 22 × 41 |  |
| nervous_system | `Allen_transverse_temporal_gyrus_Heschls_gyrus_R` | - | - | 1,434 | 30 × 17 × 28 |  |
| nervous_system | `Allen_planum_temporale_R` | planum temporale | UBERON:0022268 | 1,646 | 25 × 17 × 32 |  |
| nervous_system | `Allen_temporal_pole_R` | temporal pole | UBERON:0002576 | 2,570 | 33 × 34 × 22 |  |
| nervous_system | `Allen_planum_polare_R` | planum polare | UBERON:0023861 | 2,336 | 25 × 24 × 45 |  |
| nervous_system | `Allen_occipital_pole_R` | occipital pole | UBERON:0002902 | 1,520 | 23 × 35 × 19 |  |
| nervous_system | `Allen_cuneus_R` | cuneus cortex | UBERON:0006092 | 6,032 | 26 × 46 × 38 |  |
| nervous_system | `Allen_lingual_gyrus_medial_occipitotemporal_gyrus_R` | lingual gyrus | UBERON:0002943 | 7,406 | 34 × 36 × 63 |  |
| nervous_system | `Allen_lateral_occipitotemporal_fusiform_gyrus_occipital_part_R` | occipital fusiform gyrus | UBERON:0022364 | 1,908 | 30 × 19 × 16 |  |
| nervous_system | `Allen_inferior_occipital_gyrus_R` | inferior occipital gyrus | UBERON:0014608 | 4,628 | 40 × 41 × 39 |  |
| nervous_system | `Allen_superior_occipital_gyrus_R` | superior occipital gyrus | UBERON:0002948 | 6,032 | 42 × 50 × 31 |  |
| nervous_system | `Allen_cingulate_gyrus_rostral_anterior_part_R` | anterior cingulate gyrus | UBERON:0002756 | 3,508 | 15 × 49 × 57 |  |
| nervous_system | `Allen_cingulate_gyrus_caudal_posterior_part_R` | posterior cingulate gyrus | UBERON:0002740 | 4,316 | 24 × 56 × 46 |  |
| nervous_system | `Allen_ingulo_parahippocampal_isthmus_R` | isthmus of cingulate gyrus | UBERON:0002738 | 246 | 13 × 11 × 12 |  |
| nervous_system | `Allen_subcallosal_gyrus_parolfactory_gyrus_R` | subcallosal area | UBERON:0003020 | 406 | 7 × 18 × 17 |  |
| nervous_system | `Allen_anterior_parahippocampal_gyrus_R` | anterior parahippocampal gyrus | UBERON:0022383 | 1,342 | 18 × 19 × 30 |  |
| nervous_system | `Allen_posterior_parahippocampal_gyrus_R` | posterior parahippocampal gyrus | UBERON:0002657 | 1,110 | 20 × 18 × 25 |  |
| nervous_system | `Allen_gyrus_ambiens_R` | - | - | 180 | 7 × 8 × 13 |  |
| nervous_system | `Allen_head_of_hippocampus_R` | - | - | 516 | 24 × 14 × 16 |  |
| nervous_system | `Allen_body_of_hippocampus_R` | - | - | 430 | 20 × 11 × 14 |  |
| nervous_system | `Allen_tail_of_hippocampus_R` | - | - | 524 | 24 × 16 × 15 |  |
| nervous_system | `Allen_long_insular_gyri_R` | - | - | 1,218 | 16 × 30 × 39 |  |
| nervous_system | `Allen_short_insular_gyri_R` | - | - | 1,480 | 20 × 33 × 42 |  |
| nervous_system | `Allen_limen_insula_R` | - | - | 64 | 8 × 6 × 5 |  |
| nervous_system | `Allen_pretectal_region_R` | - | - | 56 | 11 × 10 × 7 |  |
| nervous_system | `Allen_red_nucleus_R` | red nucleus | UBERON:0001947 | 100 | 8 × 10 × 9 |  |
| nervous_system | `Allen_substantia_nigra_R` | substantia nigra | UBERON:0002038 | 118 | 9 × 11 × 13 |  |
| nervous_system | `Allen_superior_colliculus_R` | superior colliculus | UBERON:0001945 | 72 | 11 × 8 × 8 |  |
| nervous_system | `Allen_inferior_colliculus_R` | inferior colliculus | UBERON:0001946 | 168 | 11 × 9 × 10 |  |
| nervous_system | `Allen_cerebral_peduncle_crus_cerebri_R` | cerebral peduncle | UBERON:0002623 | 462 | 17 × 17 × 19 |  |
| nervous_system | `Allen_superior_cerebellar_peduncle_brachium_conjunctivum_R` | - | - | 258 | 6 × 18 × 11 |  |
| nervous_system | `Allen_cerebral_aqueduct_R` | - | - | 76 | 3 × 20 × 9 |  |
| nervous_system | `Allen_paravermis_of_cerebellum_R` | - | - | 3,423 | 16 × 59 × 56 |  |
| nervous_system | `Allen_lateral_hemisphere_of_cerebellum_R` | - | - | 11,928 | 40 × 49 × 59 |  |
| nervous_system | `Allen_basilar_part_of_pons_R` | pontine nuclear group | UBERON:0002151 | 940 | 20 × 28 × 21 |  |
| nervous_system | `Allen_pontine_tegmentum_R` | pontine tegmentum | UBERON:0003023 | 528 | 12 × 29 × 14 |  |
| nervous_system | `Allen_pyramidal_part_of_medulla_oblongata_R` | - | - | 116 | 6 × 23 × 4 |  |
| nervous_system | `Allen_tegmentum_of_medulla_oblongata_R` | - | - | 632 | 11 × 26 × 14 |  |
| nervous_system | `Allen_inferior_olive_R` | - | - | 124 | 4 × 13 × 7 |  |
| nervous_system | `Allen_inferior_cerebellar_peduncle_R` | - | - | 112 | 5 × 16 × 9 |  |
| nervous_system | `Allen_middle_cerebellar_peduncle_R` | - | - | 332 | 15 × 14 × 14 |  |
| nervous_system | `Allen_fourth_ventricle_R` | fourth ventricle | UBERON:0002422 | 426 | 14 × 39 × 17 |  |
| nervous_system | `Allen_central_canal_of_medulla_oblongata_R` | - | - | 12 | 1 × 10 × 3 |  |
| nervous_system | `Allen_midline_nuclear_complex_R` | - | - | 248 | 4 × 15 × 18 |  |
| nervous_system | `Allen_lateral_olfactory_gyrus_R` | - | - | 130 | 14 × 8 × 7 |  |
| nervous_system | `Allen_parietal_operculum_R` | parietal operculum | UBERON:0002911 | 1,234 | 31 × 17 × 39 |  |
| nervous_system | `Allen_optic_radiation_R` | optic radiation | UBERON:0022264 | 84 | 8 × 8 × 13 |  |
| nervous_system | `Allen_posteroventral_putamen_R` | - | - | 2,100 | 17 × 50 × 81 |  |
| nervous_system | `Allen_atrium_of_lateral_ventricle_R` | - | - | 622 | 14 × 23 × 36 |  |
| nervous_system | `Allen_paracingulate_gyrus_R` | - | - | 824 | 35 × 27 × 21 |  |
| nervous_system | `Allen_rostral_gyrus_R` | - | - | 1,160 | 28 × 38 × 19 |  |
| nervous_system | `Allen_frontomarginal_gyrus_R` | - | - | 1,084 | 23 × 25 × 48 |  |
| nervous_system | `Allen_frontal_pole_R` | - | - | 2,116 | 27 × 29 × 64 |  |
| nervous_system | `Allen_perirhinal_gyrus_rostral_part_of_FuGt_R` | - | - | 90 | 17 × 21 × 22 |  |
| nervous_system | `Allen_hypothalamus_L` | hypothalamus | UBERON:0001898 | 150 | 6 × 10 × 6 |  |
| nervous_system | `Allen_hypothalamus_R` | hypothalamus | UBERON:0001898 | 150 | 6 × 10 × 6 |  |
| nervous_system | `Allen_subthalamic_nucleus_R` | - | - | 204 | 8 × 7 × 10 |  |
| nervous_system | `Allen_mammillary_region_of_HTH_R` | - | - | 462 | 14 × 14 × 8 |  |
| nervous_system | `Allen_midbrain_tegmentum_R` | - | - | 724 | 16 × 18 × 25 |  |
| nervous_system | `Allen_tuberal_region_of_HTH_R` | - | - | 642 | 14 × 17 × 13 |  |
| nervous_system | `Allen_preoptic_region_of_HTH_R` | - | - | 222 | 7 × 12 × 8 |  |
| nervous_system | `Allen_midbrain_tegmentum_L` | - | - | 724 | 16 × 18 × 25 |  |
| nervous_system | `Allen_red_nucleus_L` | red nucleus | UBERON:0001947 | 100 | 8 × 10 × 9 |  |
| nervous_system | `Allen_inferior_colliculus_L` | inferior colliculus | UBERON:0001946 | 168 | 11 × 9 × 10 |  |
| nervous_system | `Allen_mammillary_region_of_HTH_L` | - | - | 462 | 14 × 14 × 8 |  |
| nervous_system | `Allen_subthalamic_nucleus_L` | - | - | 204 | 8 × 7 × 9 |  |
| nervous_system | `VH_F_C1_segment_of_cervical_spinal_cord` | C1 segment of cervical spinal cord | UBERON:0006469 | 9,996 | 11 × 12 × 9 |  |
| nervous_system | `VH_F_C2_segment_of_cervical_spinal_cord` | C2 segment of cervical spinal cord | UBERON:0006489 | 10,032 | 10 × 11 × 9 |  |
| nervous_system | `VH_F_C3_segment_of_cervical_spinal_cord` | C3 segment of cervical spinal cord | UBERON:0006488 | 9,996 | 11 × 15 × 10 |  |
| nervous_system | `VH_F_C4_segment_of_cervical_spinal_cord` | C4 segment of cervical spinal cord | UBERON:0006490 | 9,964 | 12 × 12 × 8 |  |
| nervous_system | `VH_F_C5_segment_of_cervical_spinal_cord` | C5 segment of cervical spinal cord | UBERON:0006491 | 9,984 | 9 × 13 × 9 |  |
| nervous_system | `VH_F_C6_segment_of_cervical_spinal_cord` | C6 segment of cervical spinal cord | UBERON:0006492 | 9,964 | 9 × 14 × 12 |  |
| nervous_system | `VH_F_C7_segment_of_cervical_spinal_cord` | C7 segment of cervical spinal cord | UBERON:0006493 | 9,856 | 9 × 18 × 15 |  |
| nervous_system | `VH_F_C8_segment_of_cervical_spinal_cord` | C8 segment of cervical spinal cord | UBERON:0006470 | 10,044 | 9 × 17 × 13 |  |
| nervous_system | `VH_F_first_thoracic_spinal_cord_segment` | first thoracic spinal cord segment | UBERON:0006457 | 10,004 | 9 × 21 × 15 |  |
| nervous_system | `VH_F_second_thoracic_spinal_cord_segment` | second thoracic spinal cord segment | UBERON:0006458 | 10,030 | 9 × 20 × 15 |  |
| nervous_system | `VH_F_third_thoracic_spinal_cord_segment` | third thoracic spinal cord segment | UBERON:0006459 | 9,882 | 10 × 21 × 16 |  |
| nervous_system | `VH_F_fourth_thoracic_spinal_cord_segment` | fourth thoracic spinal cord segment | UBERON:0006452 | 10,032 | 11 × 24 × 15 |  |
| nervous_system | `VH_F_fifth_thoracic_spinal_cord_segment` | fifth thoracic spinal cord segment | UBERON:0006453 | 9,984 | 11 × 23 × 13 |  |
| nervous_system | `VH_F_seventh_thoracic_spinal_cord_segment` | seventh thoracic spinal cord segment | UBERON:0006455 | 9,984 | 10 × 22 × 11 |  |
| nervous_system | `VH_F_eigth_thoracic_spinal_cord_segment` | eighth thoracic spinal cord segment | UBERON:0006456 | 10,092 | 10 × 19 × 9 |  |
| nervous_system | `VH_F_sixth_thoracic_spinal_cord_segment` | sixth thoracic spinal cord segment | UBERON:0006454 | 9,940 | 11 × 27 × 12 |  |
| nervous_system | `VH_F_ninth_thoracic_spinal_cord_segment` | ninth thoracic spinal cord segment | UBERON:0006465 | 10,010 | 10 × 23 × 9 |  |
| nervous_system | `VH_F_tenth_thoracic_spinal_cord_segment` | tenth thoracic spinal cord segment | UBERON:0006466 | 10,030 | 10 × 20 × 10 |  |
| nervous_system | `VH_F_eleventh_thoracic_spinal_cord_segment` | eleventh thoracic spinal cord segment | UBERON:0006467 | 9,936 | 11 × 17 × 9 |  |
| nervous_system | `VH_F_twelfth_thoracic_spinal_cord_segment` | twelfth thoracic spinal cord segment | UBERON:0006468 | 9,964 | 11 × 17 × 9 |  |
| nervous_system | `VH_F_first_lumbar_spinal_cord_segment` | first lumbar spinal cord segment | UBERON:0006448 | 9,870 | 12 × 14 × 10 |  |
| nervous_system | `VH_F_second_lumbar_spinal_cord_segment` | second lumbar spinal cord segment | UBERON:0006450 | 9,990 | 12 × 9 × 9 |  |
| nervous_system | `VH_F_third_lumbar_spinal_cord_segment` | third lumbar spinal cord segment | UBERON:0006449 | 9,828 | 12 × 9 × 8 |  |
| nervous_system | `VH_F_fourth_lumbar_spinal_cord_segment` | fourth lumbar spinal cord segment | UBERON:0006451 | 9,840 | 10 × 8 × 7 |  |
| nervous_system | `VH_F_fifth_lumbar_spinal_cord_segment` | fifth lumbar spinal cord segment | UBERON:0006447 | 10,008 | 9 × 6 × 6 |  |
| nervous_system | `VH_F_first_sacral_spinal_cord_segment` | first sacral spinal cord segment | UBERON:0006460 | 9,906 | 8 × 6 × 6 |  |
| nervous_system | `VH_F_second_sacral_spinal_cord_segment` | second sacral spinal cord segment | UBERON:0006461 | 10,080 | 6 × 5 × 5 |  |
| nervous_system | `VH_F_third_sacral_spinal_cord_segment` | third sacral spinal cord segment | UBERON:0006462 | 9,976 | 5 × 6 × 5 |  |
| nervous_system | `VH_F_fourth_sacral_spinal_cord_segment` | fourth sacral spinal cord segment | UBERON:0006463 | 9,690 | 5 × 6 × 4 |  |
| muscular_system | `VH_F_medial_rectus_extraocular_muscle_L` | Left medial rectus | FMA:49057 | 1,238 | 12 × 8 × 44 |  |
| muscular_system | `VH_F_inferior_rectus_extraocular_muscle_L` | Left inferior rectus | FMA:49047 | 12,062 | 26 × 9 × 44 |  |
| muscular_system | `VH_F_superior_rectus_extraocular_muscle_L` | Left superior rectus | FMA:49045 | 1,390 | 23 × 16 × 43 |  |
| muscular_system | `VH_F_inferior_oblique_extraocular_muscle_L` | Left inferior oblique | FMA:49051 | 12,498 | 31 × 13 × 13 |  |
| muscular_system | `VH_F_lateral_rectus_extraocular_muscle_L` | Left lateral rectus | FMA:49055 | 13,822 | 31 × 8 × 46 |  |
| muscular_system | `VH_F_superior_oblique_extraocular_muscle_L` | Left superior oblique | FMA:49053 | 1,668 | 22 × 18 × 46 |  |
| muscular_system | `VH_F_medial_rectus_extraocular_muscle_R` | Right medial rectus | FMA:49056 | 1,238 | 10 × 8 × 44 |  |
| muscular_system | `VH_F_inferior_rectus_extraocular_muscle_R` | Right inferior rectus | FMA:49046 | 12,062 | 24 × 9 × 45 |  |
| muscular_system | `VH_F_superior_rectus_extraocular_muscle_R` | Right superior rectus | FMA:49044 | 1,390 | 22 × 16 × 44 |  |
| muscular_system | `VH_F_inferior_oblique_extraocular_muscle_R` | Right inferior oblique | FMA:49050 | 12,498 | 32 × 13 × 13 |  |
| muscular_system | `VH_F_lateral_rectus_extraocular_muscle_R` | Right lateral rectus | FMA:49054 | 13,822 | 30 × 8 × 47 |  |
| muscular_system | `VH_F_superior_oblique_extraocular_muscle_R` | Right superior oblique | FMA:49052 | 1,668 | 21 × 18 × 46 |  |
| muscular_system | `VH_F_rectus_femoris_L` | Left rectus femoris | FMA:38929 | 11,216 | 73 × 351 × 47 |  |
| muscular_system | `VH_F_tendon_of_quadriceps_femoris_L` | Tendon of left quadriceps femoris | FMA:46902 | 1,464 | 16 × 57 × 11 |  |
| muscular_system | `VH_F_rectus_femoris_R` | Right rectus femoris | FMA:38928 | 11,216 | 73 × 351 × 47 |  |
| muscular_system | `VH_F_tendon_of_quadriceps_femoris_R` | Tendon of right quadriceps femoris | FMA:46901 | 1,464 | 16 × 57 × 11 |  |
| reproductive_system | `VH_F_basal_plate` | - | - | 17,273 | 198 × 200 × 106 |  |
| reproductive_system | `VH_F_chorionic_plate` | chorionic plate | UBERON:0004027 | 17,219 | 195 × 195 × 90 |  |
| reproductive_system | `VH_F_placenta_vessels` | - | - | 75,578 | 164 × 139 × 66 |  |
| reproductive_system | `VH_F_amnion` | amnion | UBERON:0000305 | 14,642 | 251 × 231 × 111 |  |
| reproductive_system | `VH_F_umbilical_cord` | umbilical cord | UBERON:0002331 | 30,426 | 23 × 54 × 67 |  |
| reproductive_system | `VH_F_umbilical_artery_1` | umbilical artery | UBERON:0001310 | 10,647 | 20 × 54 × 60 |  |
| reproductive_system | `VH_F_umbilical_artery_2` | umbilical artery | UBERON:0001310 | 12,420 | 20 × 56 × 56 |  |
| reproductive_system | `VH_F_umbilical_vein` | umbilical vein | UBERON:0002066 | 10,160 | 15 × 58 × 65 |  |
| reproductive_system | `VH_F_vagina` | vagina | UBERON:0000996 | 8,780 | 45 × 59 × 24 | yes |
| reproductive_system | `VH_F_cervicovaginal_junction` | - | - | 3,766 | 38 × 23 × 25 | yes |
| reproductive_system | `VH_F_ampulla_of_uterine_tube_R` | Ampulla of right uterine tube | FMA:18491 | 10,440 | 27 × 42 × 15 | yes |
| reproductive_system | `VH_F_isthmus_of_fallopian_tube_R` | Isthmus of right uterine tube | FMA:18493 | 1,600 | 9 × 5 × 4 | yes |
| reproductive_system | `VH_F_fibria_of_uterine_tube_R` | Fimbria of right uterine tube | FMA:18497 | 3,530 | 7 × 4 × 6 | yes |
| reproductive_system | `VH_F_uterine_tube_infundibulum_R` | Infundibulum of right uterine tube | FMA:18489 | 2,200 | 8 × 11 × 7 | yes |
| reproductive_system | `VH_F_uterine_tube_infundibulum_L` | Infundibulum of left uterine tube | FMA:18490 | 2,116 | 8 × 11 × 8 | yes |
| reproductive_system | `VH_F_fibria_of_uterine_tube_L` | Fimbria of left uterine tube | FMA:18498 | 2,871 | 7 × 5 × 8 | yes |
| reproductive_system | `VH_F_isthmus_of_fallopian_tube_L` | Isthmus of left uterine tube | FMA:18494 | 1,870 | 10 × 4 × 4 | yes |
| reproductive_system | `VH_F_ampulla_of_uterine_tube_L` | Ampulla of left uterine tube | FMA:18492 | 11,424 | 29 × 43 × 15 | yes |
| reproductive_system | `VH_F_uterovesical_pouch` | Uterovesical pouch | FMA:14729 | 25,352 | 52 × 28 × 64 | yes |
| reproductive_system | `VH_F_right_round_ligament_of_uterus` | Right round ligament of uterus | FMA:57789 | 902 | 47 × 62 × 49 | yes |
| reproductive_system | `VH_F_left_round_ligament_of_uterus` | Left round ligament of uterus | FMA:57790 | 1,024 | 61 × 67 × 45 | yes |
| reproductive_system | `VH_F_right_uterosacral_ligament` | Right uterosacral ligament | FMA:19119 | 1,990 | 14 × 55 × 80 | yes |
| reproductive_system | `VH_F_left_uterosacral_ligament` | Left uterosacral ligament | FMA:19120 | 1,948 | 6 × 52 × 82 | yes |
| reproductive_system | `VH_F_right_cardinal_ligament_of_uterus` | Cardinal ligament | FMA:77064 | 4,056 | 67 × 25 × 53 | yes |
| reproductive_system | `VH_F_left_cardinal_ligament_of_uterus` | Cardinal ligament | FMA:77064 | 4,056 | 62 × 19 × 51 | yes |
| reproductive_system | `VH_F_suspensory_ligament_of_ovary_R` | Suspensory ligament of right ovary | FMA:19823 | 880 | 8 × 31 × 14 | yes |
| reproductive_system | `VH_F_suspensory_ligament_of_ovary_L` | Suspensory ligament of left ovary | FMA:19824 | 1,270 | 11 × 36 × 21 | yes |
| reproductive_system | `VH_F_ovarian_ligament_L` | Left ovarian ligament | FMA:55424 | 208 | 33 × 11 × 4 | yes |
| reproductive_system | `VH_F_ovarian_ligament_R` | Right ovarian ligament | FMA:55423 | 198 | 33 × 13 × 4 | yes |
| reproductive_system | `VH_F_broad_ligament` | broad ligament of uterus | UBERON:0012332 | 29,442 | 140 × 63 × 126 | yes |
| reproductive_system | `VH_F_mesosalpinx_L` | Left mesosalpinx | FMA:19810 | 1,914 | 45 × 51 × 17 | yes |
| reproductive_system | `VH_F_mesosalpinx_R` | Right mesosalpinx | FMA:19809 | 1,755 | 46 × 49 × 19 | yes |
| reproductive_system | `VH_F_mesovarium_R` | Right mesovarium | FMA:19817 | 183 | 12 × 21 × 5 | yes |
| reproductive_system | `VH_F_mesovarium_L` | Left mesovarium | FMA:19818 | 644 | 18 × 25 × 10 | yes |
| reproductive_system | `VH_F_left_ovary` | Left ovary | FMA:7214 | 424 | 12 × 24 × 11 | yes |
| reproductive_system | `VH_F_right_ovary` | Right ovary | FMA:7213 | 410 | 12 × 24 × 11 | yes |
| reproductive_system | `VH_F_abdominal_ostium_of_uterine_tube` | Abdominal ostium of uterine tube | FMA:77049 | 546 | 52 × 4 × 2 | yes |
| reproductive_system | `VH_F_body_of_uterus` | body of uterus | UBERON:0009853 | 5,344 | 43 × 30 × 28 | yes |
| reproductive_system | `VH_F_fundus_of_uterus` | Fundus of uterus | FMA:17561 | 3,062 | 41 × 21 × 22 | yes |
| reproductive_system | `VH_F_cornua` | - | - | 660 | 52 × 9 × 10 | yes |
| reproductive_system | `VH_F_lower_uterine_segment` | Lower uterine segment | FMA:17752 | 1,408 | 18 × 20 × 15 | yes |
| reproductive_system | `VH_F_posterior_wall_of_uterus` | Posterior wall of uterus | FMA:224878 | 12,022 | 43 × 26 × 34 | yes |
| reproductive_system | `VH_F_anterior_wall_of_uterus` | Anterior wall of uterus | FMA:224876 | 10,148 | 43 × 25 × 36 | yes |
| reproductive_system | `VH_F_cervix` | uterine cervix | UBERON:0000002 | 3,508 | 27 × 29 × 24 | yes |
| reproductive_system | `VH_F_internal_cervical_os` | internal cervical os | UBERON:0013759 | 216 | 3 × 4 × 4 | yes |
| reproductive_system | `VH_F_external_cervical_os` | external cervical os | UBERON:0013760 | 270 | 7 × 7 × 6 | yes |
| digestive_system | `VH_F_palatine_tonsil_L` | left palatine tonsil | FMA:54974 | 17,202 | 16 × 24 × 16 |  |
| digestive_system | `VH_F_palatine_tonsil_R` | right palatine tonsil | FMA:54973 | 12,256 | 17 × 24 × 14 |  |
| digestive_system | `VH_F_hepatic_flexure_of_colon` | hepatic flexure of colon | UBERON:0022277 | 1,479 | 68 × 71 × 79 |  |
| digestive_system | `VH_F_transverse_colon` | transverse colon | UBERON:0001157 | 5,001 | 201 × 106 × 117 |  |
| digestive_system | `VH_F_ascending_colon` | ascending colon | UBERON:0001156 | 1,656 | 51 × 125 × 57 |  |
| digestive_system | `VH_F_vermiform_appendix` | vermiform appendix | UBERON:0001154 | 264 | 16 × 24 × 23 |  |
| digestive_system | `VH_F_descending_colon` | descending colon | UBERON:0001158 | 4,871 | 136 × 255 × 80 |  |
| digestive_system | `VH_F_ileocecal_valve` | ileocecal valve | UBERON:0000569 | 46 | 6 × 20 × 20 |  |
| digestive_system | `VH_F_caecum` | caecum | UBERON:0001153 | 840 | 54 × 69 × 52 |  |
| digestive_system | `VH_F_rectum` | rectum | UBERON:0001052 | 1,880 | 53 × 106 × 63 |  |
| digestive_system | `VH_F_sigmoid_colon` | sigmoid colon | UBERON:0001159 | 2,848 | 88 × 63 × 93 |  |
| digestive_system | `VH_F_splenic_flexure_of_colon` | splenic flexure of colon | UBERON:0022276 | 1,536 | 65 × 74 × 72 |  |
| digestive_system | `VH_F_duodenum_superior` | superior part of duodenum | FMA:7206 | 1,224 | 38 × 51 × 69 |  |
| digestive_system | `VH_F_duodenal_ampulla` | duodenal ampulla | UBERON:0013644 | 1,116 | 29 × 29 × 30 |  |
| digestive_system | `VH_F_duodenum_descending` | descending part of duodenum | FMA:14928 | 936 | 35 × 60 × 27 |  |
| digestive_system | `VH_F_sphincter_of_heptopancreatic_ampulla` | Sphincter of hepatopancreatic ampulla | FMA:15077 | 4,096 | 5 × 5 × 5 |  |
| digestive_system | `VH_F_duodenum_ascending` | ascending part of duodenum | FMA:14930 | 504 | 27 × 26 × 41 |  |
| digestive_system | `VH_F_duodenum_horizontal` | horizontal part of duodenum | FMA:14929 | 1,080 | 65 × 27 × 28 |  |
| digestive_system | `VH_F_jejenum` | jejunum | UBERON:0002115 | 11,380 | 137 × 137 × 64 |  |
| digestive_system | `VH_F_ileum` | ileum | UBERON:0002116 | 21,084 | 160 × 134 × 99 |  |
| digestive_system | `VH_F_ileum_terminal` | distal part of ileum | FMA:14966 | 2,332 | 72 × 68 × 15 |  |
| digestive_system | `VH_F_right_hepatic_duct` | right hepatic duct | UBERON:0001176 | 400 | 14 × 8 × 9 |  |
| digestive_system | `VH_F_left_hepatic_duct` | left hepatic duct | UBERON:0001177 | 720 | 21 × 19 × 17 |  |
| digestive_system | `VH_F_common_hepatic_duct` | common hepatic duct | UBERON:0001175 | 432 | 7 × 8 × 6 |  |
| digestive_system | `VH_F_hepatopancreatic_ampulla` | hepatopancreatic ampulla | UBERON:0004913 | 688 | 8 × 7 × 4 |  |
| digestive_system | `VH_F_dorsal_pancreatic_duct` | dorsal pancreatic duct | UBERON:0005429 | 920 | 19 × 14 × 11 |  |
| digestive_system | `VH_F_common_bile_duct` | common bile duct | UBERON:0001174 | 1,472 | 21 × 69 × 6 |  |
| digestive_system | `VH_F_ventral_pancreatic_duct` | Ventral pancreatic duct | UBERON:0001064 | 5,124 | 151 × 34 × 63 |  |
| digestive_system | `VH_F_cystic_duct` | cystic duct | UBERON:0001152 | 1,080 | 16 × 30 × 7 |  |
| digestive_system | `VH_F_gastric_impression_of_liver` | gastric impression of liver | FMA:14487 | 2,970 | 98 × 117 × 75 |  |
| digestive_system | `VH_F_suprarenal_impression_of_liver` | Suprarenal impression of liver | FMA:14489 | 87 | 31 × 17 × 35 |  |
| digestive_system | `VH_F_renal_impression_of_liver` | renal impression of liver | FMA:14488 | 954 | 56 × 43 × 50 |  |
| digestive_system | `VH_F_duodenal_impression_of_liver` | duodenal impression of liver | FMA:14485 | 68 | 14 × 13 × 11 |  |
| digestive_system | `VH_F_esophageal_impression_of_liver` | esophageal impression of liver | FMA:14486 | 374 | 24 × 43 × 16 |  |
| digestive_system | `VH_F_porta_hepatis` | porta hepatis | FMA:15758 | 850 | 49 × 38 × 41 |  |
| digestive_system | `VH_F_colic_impression_of_liver` | colic impression of liver | FMA:14484 | 584 | 77 × 32 × 70 |  |
| digestive_system | `VH_F_capsule_of_the_liver` | capsule of the liver | UBERON:0016479 | 30,034 | 247 × 170 × 153 |  |
| digestive_system | `VH_F_bare_area_of_liver` | bare area of liver | UBERON:0001149 | 5,864 | 160 × 110 × 100 |  |
| digestive_system | `VH_F_diaphragmatic_surface_of_liver` | diaphragmatic surface of liver | FMA:15729 | 12,448 | 228 × 135 × 152 |  |
| digestive_system | `VH_F_left_anterolateral_segment` | - | - | 4,904 | 128 × 70 × 74 |  |
| digestive_system | `VH_F_left_superomedial_segment` | - | - | 6,444 | 125 × 76 × 88 |  |
| digestive_system | `VH_F_left_superomedial_segment1` | - | - | 2,882 | 105 × 92 × 67 |  |
| digestive_system | `VH_F_left_inferomedial_segment` | - | - | 1,476 | 82 × 62 × 29 |  |
| digestive_system | `VH_F_quadrate_lobe` | quadrate lobe of liver | UBERON:0001116 | 2,008 | 64 × 66 × 66 |  |
| digestive_system | `VH_F_right_anterosuperior_segment` | - | - | 2,550 | 111 × 102 × 79 |  |
| digestive_system | `VH_F_right_posteroinferior_segment` | - | - | 2,386 | 97 × 74 × 62 |  |
| digestive_system | `VH_F_right_posterosuperior_segment` | - | - | 3,076 | 102 × 95 × 64 |  |
| digestive_system | `VH_F_right_anteroinferior_segment` | - | - | 2,418 | 90 × 75 × 81 |  |
| digestive_system | `VH_F_caudate_lobe` | caudate lobe of liver | UBERON:0001117 | 5,354 | 81 × 114 × 67 |  |
| digestive_system | `VH_F_coronary_ligament_of_liver` | coronary ligament of liver | UBERON:0013138 | 2,426 | 162 × 122 × 93 |  |
| digestive_system | `VH_F_falciform_ligament` | falciform ligament | UBERON:0001247 | 516 | 55 × 107 × 59 |  |
| digestive_system | `VH_F_triangular_ligament_of_liver` | triangular ligament of liver | UBERON:0035444 | 276 | 34 × 7 × 10 |  |
| digestive_system | `VH_F_ligamentum_venosum` | ligamentum venosum | UBERON:0006587 | 702 | 41 × 85 × 35 |  |
| digestive_system | `VH_F_round_ligament_of_liver` | round ligament of liver | UBERON:0006588 | 558 | 25 × 38 × 46 |  |
| digestive_system | `VH_F_hepataduodenal_ligament` | hepatoduodenal ligament | UBERON:0012472 | 1,094 | 61 × 30 × 39 |  |
| digestive_system | `VH_F_tail_of_pancreas` | tail of pancreas | UBERON:0001151 | 3,997 | 76 × 39 × 62 |  |
| digestive_system | `VH_F_body_of_pancreas` | body of pancreas | UBERON:0001150 | 3,595 | 64 × 42 × 48 |  |
| digestive_system | `VH_F_ucinate_process1` | uncinate process of pancreas | UBERON:0010373 | 831 | 39 × 22 × 23 |  |
| digestive_system | `VH_F_head_of_pancreas` | head of pancreas | UBERON:0001069 | 3,733 | 54 × 44 × 40 |  |
| digestive_system | `VH_F_neck_of_pancreas` | Neck of pancreas | FMA:14517 | 738 | 22 × 24 × 19 |  |
| digestive_system | `VH_F_gallbladder` | gallbladder | UBERON:0002110 | 2,396 | 41 × 38 × 52 |  |
| urinary_system | `VH_F_kidney_capsule_L` | kidney capsule | UBERON:0002015 | 10,850 | 73 × 125 × 78 |  |
| urinary_system | `VH_F_hilum_of_kidney_L` | hilum of kidney | UBERON:0008716 | 5,927 | 39 × 73 × 40 |  |
| urinary_system | `VH_F_renal_papilla_L_a` | renal papilla | UBERON:0001228 | 70 | 4 × 4 × 5 |  |
| urinary_system | `VH_F_renal_papilla_L_b` | renal papilla | UBERON:0001228 | 50 | 3 × 4 × 4 |  |
| urinary_system | `VH_F_renal_papilla_L_c` | renal papilla | UBERON:0001228 | 42 | 5 × 5 × 3 |  |
| urinary_system | `VH_F_renal_papilla_L_d` | renal papilla | UBERON:0001228 | 78 | 5 × 3 × 4 |  |
| urinary_system | `VH_F_renal_papilla_L_e` | renal papilla | UBERON:0001228 | 66 | 3 × 5 × 4 |  |
| urinary_system | `VH_F_renal_papilla_L_f` | renal papilla | UBERON:0001228 | 72 | 3 × 7 × 6 |  |
| urinary_system | `VH_F_renal_papilla_L_g` | renal papilla | UBERON:0001228 | 50 | 7 × 8 × 3 |  |
| urinary_system | `VH_F_renal_papilla_L_h` | renal papilla | UBERON:0001228 | 60 | 3 × 4 × 4 |  |
| urinary_system | `VH_F_renal_papilla_L_i` | renal papilla | UBERON:0001228 | 62 | 4 × 7 × 4 |  |
| urinary_system | `VH_F_renal_papilla_L_j` | renal papilla | UBERON:0001228 | 86 | 5 × 5 × 5 |  |
| urinary_system | `VH_F_renal_papilla_L_k` | renal papilla | UBERON:0001228 | 102 | 6 × 4 × 5 |  |
| urinary_system | `VH_F_renal_pyramid_L_a` | renal pyramid | UBERON:0004200 | 2,782 | 22 × 49 × 35 |  |
| urinary_system | `VH_F_renal_pyramid_L_b` | renal pyramid | UBERON:0004200 | 1,008 | 15 × 21 × 27 |  |
| urinary_system | `VH_F_renal_pyramid_L_c` | renal pyramid | UBERON:0004200 | 668 | 17 × 17 × 16 |  |
| urinary_system | `VH_F_renal_pyramid_L_d` | renal pyramid | UBERON:0004200 | 1,462 | 38 × 20 × 18 |  |
| urinary_system | `VH_F_renal_pyramid_L_e` | renal pyramid | UBERON:0004200 | 1,334 | 26 × 20 × 25 |  |
| urinary_system | `VH_F_renal_pyramid_L_f` | renal pyramid | UBERON:0004200 | 1,730 | 34 × 27 × 32 |  |
| urinary_system | `VH_F_renal_pyramid_L_g` | renal pyramid | UBERON:0004200 | 2,724 | 38 × 31 × 24 |  |
| urinary_system | `VH_F_renal_pyramid_L_h` | renal pyramid | UBERON:0004200 | 718 | 17 × 17 × 23 |  |
| urinary_system | `VH_F_renal_pyramid_L_i` | renal pyramid | UBERON:0004200 | 1,266 | 23 × 31 × 27 |  |
| urinary_system | `VH_F_renal_pyramid_L_j` | renal pyramid | UBERON:0004200 | 1,292 | 25 × 27 × 23 |  |
| urinary_system | `VH_F_renal_pyramid_L_k` | renal pyramid | UBERON:0004200 | 1,128 | 28 × 23 × 19 |  |
| urinary_system | `VH_F_renal_column_L` | renal column | UBERON:0001284 | 26,115 | 53 × 102 × 58 |  |
| urinary_system | `VH_F_outer_cortex_of_kidney_L` | outer cortex of kidney | UBERON:0002189 | 13,784 | 72 × 124 × 77 |  |
| urinary_system | `VH_F_kidney_capsule_R` | kidney capsule | UBERON:0002015 | 10,642 | 73 × 98 × 70 |  |
| urinary_system | `VH_F_hilum_of_kidney_R` | hilum of kidney | UBERON:0008716 | 4,216 | 38 × 47 × 30 |  |
| urinary_system | `VH_F_outer_cortex_of_kidney_R` | outer cortex of kidney | UBERON:0002189 | 13,824 | 72 × 96 × 68 |  |
| urinary_system | `VH_F_renal_column_R` | renal column | UBERON:0001284 | 23,628 | 58 × 81 × 54 |  |
| urinary_system | `VH_F_renal_papilla_R_a` | renal papilla | UBERON:0001228 | 122 | 4 × 5 × 5 |  |
| urinary_system | `VH_F_renal_papilla_R_b` | renal papilla | UBERON:0001228 | 58 | 3 × 5 × 3 |  |
| urinary_system | `VH_F_renal_papilla_R_c` | renal papilla | UBERON:0001228 | 80 | 4 × 5 × 5 |  |
| urinary_system | `VH_F_renal_papilla_R_d` | renal papilla | UBERON:0001228 | 72 | 4 × 7 × 4 |  |
| urinary_system | `VH_F_renal_papilla_R_e` | renal papilla | UBERON:0001228 | 106 | 4 × 4 × 4 |  |
| urinary_system | `VH_F_renal_papilla_R_f` | renal papilla | UBERON:0001228 | 83 | 2 × 4 × 5 |  |
| urinary_system | `VH_F_renal_papilla_R_g` | renal papilla | UBERON:0001228 | 124 | 3 × 3 × 4 |  |
| urinary_system | `VH_F_renal_papilla_R_h` | renal papilla | UBERON:0001228 | 26 | 2 × 4 × 4 |  |
| urinary_system | `VH_F_renal_papilla_R_i` | renal papilla | UBERON:0001228 | 106 | 5 × 4 × 3 |  |
| urinary_system | `VH_F_renal_papilla_R_j` | renal papilla | UBERON:0001228 | 78 | 4 × 4 × 4 |  |
| urinary_system | `VH_F_renal_pyramid_R_a` | renal pyramid | UBERON:0004200 | 2,696 | 20 × 32 × 29 |  |
| urinary_system | `VH_F_renal_pyramid_R_b` | renal pyramid | UBERON:0004200 | 956 | 14 × 27 × 15 |  |
| urinary_system | `VH_F_renal_pyramid_R_c` | renal pyramid | UBERON:0004200 | 2,254 | 28 × 22 × 28 |  |
| urinary_system | `VH_F_renal_pyramid_R_d` | renal pyramid | UBERON:0004200 | 2,234 | 25 × 31 × 23 |  |
| urinary_system | `VH_F_renal_pyramid_R_e` | renal pyramid | UBERON:0004200 | 2,328 | 27 × 23 × 24 |  |
| urinary_system | `VH_F_renal_pyramid_R_f` | renal pyramid | UBERON:0004200 | 2,267 | 19 × 14 × 33 |  |
| urinary_system | `VH_F_renal_pyramid_R_g` | renal pyramid | UBERON:0004200 | 2,454 | 34 × 15 × 20 |  |
| urinary_system | `VH_F_renal_pyramid_R_h` | renal pyramid | UBERON:0004200 | 2,262 | 34 × 18 × 27 |  |
| urinary_system | `VH_F_renal_pyramid_R_i` | renal pyramid | UBERON:0004200 | 1,660 | 32 × 15 × 14 |  |
| urinary_system | `VH_F_renal_pyramid_R_j` | renal pyramid | UBERON:0004200 | 2,862 | 33 × 27 × 21 |  |
| urinary_system | `VH_F_minor_calyx_R_a` | minor calyx | UBERON:0001227 | 1,060 | 14 × 12 × 9 |  |
| urinary_system | `VH_F_minor_calyx_R_b` | minor calyx | UBERON:0001227 | 1,220 | 13 × 16 × 9 |  |
| urinary_system | `VH_F_minor_calyx_R_c` | minor calyx | UBERON:0001227 | 856 | 8 × 12 × 8 |  |
| urinary_system | `VH_F_minor_calyx_R_d` | minor calyx | UBERON:0001227 | 1,482 | 8 × 13 × 11 |  |
| urinary_system | `VH_F_minor_calyx_R_e` | minor calyx | UBERON:0001227 | 1,002 | 7 × 7 × 8 |  |
| urinary_system | `VH_F_minor_calyx_R_f` | minor calyx | UBERON:0001227 | 1,216 | 8 × 8 × 9 |  |
| urinary_system | `VH_F_minor_calyx_R_g` | minor calyx | UBERON:0001227 | 1,368 | 7 × 5 × 8 |  |
| urinary_system | `VH_F_minor_calyx_R_h` | minor calyx | UBERON:0001227 | 736 | 6 × 6 × 6 |  |
| urinary_system | `VH_F_minor_calyx_R_i` | minor calyx | UBERON:0001227 | 1,302 | 7 × 9 × 8 |  |
| urinary_system | `VH_F_minor_calyx_R_j` | minor calyx | UBERON:0001227 | 2,166 | 11 × 10 × 10 |  |
| urinary_system | `VH_F_major_calyx_R_a` | major calyx | UBERON:0001226 | 1,218 | 7 × 14 × 13 |  |
| urinary_system | `VH_F_major_calyx_R_b` | major calyx | UBERON:0001226 | 636 | 7 × 8 × 6 |  |
| urinary_system | `VH_F_major_calyx_R_c` | major calyx | UBERON:0001226 | 2,090 | 14 × 11 × 11 |  |
| urinary_system | `VH_F_renal_pelvis_R` | renal pelvis | UBERON:0001224 | 3,012 | 19 × 20 × 14 |  |
| urinary_system | `VH_F_right_ureter` | right ureter | UBERON:0001222 | 12,952 | 35 × 224 × 36 |  |
| urinary_system | `VH_F_minor_calyx_L_a` | minor calyx | UBERON:0001227 | 2,272 | 14 × 14 × 9 |  |
| urinary_system | `VH_F_minor_calyx_L_b` | minor calyx | UBERON:0001227 | 844 | 6 × 10 × 8 |  |
| urinary_system | `VH_F_minor_calyx_L_c` | minor calyx | UBERON:0001227 | 1,862 | 11 × 11 × 9 |  |
| urinary_system | `VH_F_minor_calyx_L_d` | minor calyx | UBERON:0001227 | 732 | 8 × 10 × 6 |  |
| urinary_system | `VH_F_minor_calyx_L_e` | minor calyx | UBERON:0001227 | 1,756 | 10 × 12 × 9 |  |
| urinary_system | `VH_F_minor_calyx_L_f` | minor calyx | UBERON:0001227 | 1,598 | 9 × 11 × 7 |  |
| urinary_system | `VH_F_minor_calyx_L_g` | minor calyx | UBERON:0001227 | 910 | 10 × 7 × 7 |  |
| urinary_system | `VH_F_minor_calyx_L_h` | minor calyx | UBERON:0001227 | 1,706 | 10 × 14 × 9 |  |
| urinary_system | `VH_F_minor_calyx_L_i` | minor calyx | UBERON:0001227 | 878 | 7 × 10 × 7 |  |
| urinary_system | `VH_F_minor_calyx_L_j` | minor calyx | UBERON:0001227 | 966 | 11 × 14 × 10 |  |
| urinary_system | `VH_F_major_calyx_L_a` | major calyx | UBERON:0001226 | 1,644 | 10 × 18 × 13 |  |
| urinary_system | `VH_F_major_calyx_L_b` | major calyx | UBERON:0001226 | 878 | 7 × 7 × 10 |  |
| urinary_system | `VH_F_major_calyx_L_c` | major calyx | UBERON:0001226 | 949 | 12 × 10 × 7 |  |
| urinary_system | `VH_F_major_calyx_L_d` | major calyx | UBERON:0001226 | 1,081 | 9 × 17 × 6 |  |
| urinary_system | `VH_F_renal_pelvis_L` | renal pelvis | UBERON:0001224 | 3,206 | 13 × 24 × 16 |  |
| urinary_system | `VH_F_left_ureter` | left ureter | UBERON:0001223 | 14,944 | 53 × 220 × 37 |  |
| urinary_system | `VH_F_fundus_of_urinary_bladder_dome` | fundus of urinary bladder | UBERON:0006082 | 11,916 | 52 × 18 × 61 | yes |
| urinary_system | `VH_F_urinary_bladder_neck_smooth_muscle` | urinary bladder neck smooth muscle | UBERON:0004230 | 1,790 | 7 × 4 × 6 | yes |
| urinary_system | `VH_F_fundus_of_urinary_bladder_base` | fundus of urinary bladder | UBERON:0006082 | 25,526 | 52 × 35 × 62 | yes |
| urinary_system | `VH_F_trigone_of_urinary_bladder` | trigone of urinary bladder | UBERON:0001257 | 1,684 | 43 × 26 × 5 | yes |
| urinary_system | `VH_F_ureteral_orifice_R` | Right ureteral orifice | FMA:15939 | 180 | 3 × 3 × 2 | yes |
| urinary_system | `VH_F_ureteral_orifice_L` | Left ureteral orifice | FMA:15940 | 194 | 2 × 3 × 3 | yes |
| circulatory_system | `VH_F_interventricular_septum` | interventricular septum | UBERON:0002094 | 15,566 | 68 × 66 × 60 |  |
| circulatory_system | `VH_F_left_cardiac_atrium` | left cardiac atrium | UBERON:0002079 | 9,175 | 74 × 65 × 55 |  |
| circulatory_system | `VH_F_left_ventricle` | heart left ventricle | UBERON:0002084 | 9,822 | 97 × 83 × 88 |  |
| circulatory_system | `VH_F_right_cardiac_atrium` | right cardiac atrium | UBERON:0002078 | 9,368 | 51 × 83 × 79 |  |
| circulatory_system | `VH_F_right_ventricle` | heart right ventricle | UBERON:0002080 | 17,222 | 93 × 110 × 59 |  |
| circulatory_system | `VH_F_papillary_muscle_of_heart_ant` | Anterior papillary muscle of left ventricle | FMA:7264 | 709 | 30 × 18 × 9 |  |
| circulatory_system | `VH_F_papillary_muscle_of_heart_antlat` | Anterolateral head of lateral papillary muscle of left ventricle | FMA:7265 | 3,004 | 36 × 29 × 29 |  |
| circulatory_system | `VH_F_papillary_muscle_of_heart_med` | Septal papillary muscle of right ventricle | FMA:7262 | 82 | 8 × 6 × 8 |  |
| circulatory_system | `VH_F_papillary_muscle_of_heart_pos` | Posterior papillary muscle of right ventricle | FMA:7261 | 76 | 6 × 5 × 6 |  |
| circulatory_system | `VH_F_papillary_muscle_of_heart_posmed` | Posteromedial head of posterior papillary muscle of left ventricle | FMA:7267 | 1,562 | 31 × 24 × 28 |  |
| circulatory_system | `VH_F_aortic_valve` | aortic valve | UBERON:0002137 | 4,136 | 25 × 30 × 25 |  |
| circulatory_system | `VH_F_pulmonary_valve` | pulmonary valve | UBERON:0002146 | 1,764 | 25 × 23 × 18 |  |
| circulatory_system | `VH_F_mitral_valve` | mitral valve | UBERON:0002135 | 1,966 | 27 × 32 × 30 |  |
| circulatory_system | `VH_F_tricuspid_valve` | tricuspid valve | UBERON:0002134 | 11,462 | 31 × 47 × 37 |  |
| circulatory_system | `VH_F_left_uterine_artery` | Left uterine artery | FMA:18831 | 1,382 | 49 × 15 × 36 | yes |
| circulatory_system | `VH_F_right_uterine_artery` | Right uterine artery | FMA:18830 | 1,392 | 45 × 17 × 34 | yes |
| circulatory_system | `VH_F_left_uterine_vein` | Left uterine vein | FMA:18898 | 2,474 | 46 × 31 × 57 | yes |
| circulatory_system | `VH_F_right_uterine_vein` | Right uterine vein | FMA:18897 | 2,332 | 47 × 28 × 44 | yes |
| circulatory_system | `VH_F_ophthalmic_vein_L` | ophthalmic vein | UBERON:0011191 | 1,628 | 6 × 2 × 5 |  |
| circulatory_system | `VH_F_superior_ophthalmic_vein_L` | Left superior ophthalmic vein | FMA:51249 | 13,080 | 12 × 22 × 51 |  |
| circulatory_system | `VH_F_inferior_ophthalmic_vein_L` | Left inferior ophthalmic vein | FMA:51251 | 8,384 | 4 × 9 × 44 |  |
| circulatory_system | `VH_F_central_retinal_vein_L` | Left central retinal vein | FMA:51885 | 2,078 | 11 × 3 × 26 |  |
| circulatory_system | `VH_F_ophthalmic_vein_R` | ophthalmic vein | UBERON:0011191 | 1,628 | 6 × 2 × 5 |  |
| circulatory_system | `VH_F_superior_ophthalmic_vein_R` | Right superior ophthalmic vein | FMA:51248 | 13,080 | 12 × 24 × 50 |  |
| circulatory_system | `VH_F_inferior_ophthalmic_vein_R` | Right inferior ophthalmic vein | FMA:51250 | 8,384 | 5 × 8 × 44 |  |
| circulatory_system | `VH_F_central_retinal_vein_R` | Right central retinal vein | FMA:51884 | 2,078 | 12 × 3 × 26 |  |
| circulatory_system | `VH_F_long_posterior_ciliary_artery_L` | Left long posterior ciliary artery | FMA:49958 | 28,546 | 17 × 4 × 7 |  |
| circulatory_system | `VH_F_opthalmic_artery_L` | ophthalmic artery | UBERON:0001619 | 18,432 | 9 × 11 × 49 |  |
| circulatory_system | `VH_F_central_retinal_artery_L` | Left central retinal artery | FMA:49881 | 4,352 | 11 × 3 × 24 |  |
| circulatory_system | `VH_F_long_posterior_ciliary_artery_R` | Right long posterior ciliary artery | FMA:49957 | 28,546 | 17 × 3 × 7 |  |
| circulatory_system | `VH_F_opthalmic_artery_R` | ophthalmic artery | UBERON:0001619 | 18,432 | 9 × 12 × 48 |  |
| circulatory_system | `VH_F_central_retinal_artery_R` | Right central retinal artery | FMA:49880 | 4,352 | 12 × 3 × 24 |  |
| circulatory_system | `VH_F_right_renal_artery` | right renal artery | UBERON:0001185 | 3,198 | 73 × 42 × 17 |  |
| circulatory_system | `VH_F_left_renal_artery` | left renal artery | UBERON:0001186 | 5,730 | 44 × 46 × 26 |  |
| circulatory_system | `VH_F_left_renal_vein` | left renal vein | UBERON:0001142 | 2,898 | 50 × 45 × 18 |  |
| circulatory_system | `VH_F_right_renal_vein` | right renal vein | UBERON:0001141 | 1,072 | 22 × 28 × 19 |  |
| circulatory_system | `VH_F_superior_mesenteric_vein` | superior mesenteric vein | UBERON:0001138 | 4,060 | 21 × 101 × 19 |  |
| circulatory_system | `VH_F_superior_rectal_vein` | superior rectal artery | UBERON:0035040 | 3,592 | 28 × 29 × 60 |  |
| circulatory_system | `VH_F_left_common_iliac_vein` | Left common iliac vein | FMA:21388 | 1,932 | 65 × 86 × 24 |  |
| circulatory_system | `VH_F_right_common_iliac_vein` | Right common iliac vein | FMA:21387 | 1,386 | 40 × 85 × 23 |  |
| circulatory_system | `VH_F_left_colic_vein` | Left colic vein | FMA:15394 | 1,613 | 34 × 18 × 23 |  |
| circulatory_system | `VH_F_right_colic_vein` | Right colic vein | FMA:15407 | 1,958 | 39 × 50 × 14 |  |
| circulatory_system | `VH_F_ileocolic_vein` | ileocolic vein | UBERON:0001219 | 1,878 | 26 × 56 × 22 |  |
| circulatory_system | `VH_F_middle_colic_vein` | middle colic vein | UBERON:0001218 | 2,506 | 49 × 22 × 29 |  |
| circulatory_system | `VH_F_inferior_rectal_vein_L` | Inferior rectal vein | FMA:21242 | 1,678 | 50 × 17 × 41 |  |
| circulatory_system | `VH_F_inferior_rectal_vein_R` | Inferior rectal vein | FMA:21242 | 1,668 | 52 × 20 × 38 |  |
| circulatory_system | `VH_F_internal_iliac_vein_L` | internal iliac vein | UBERON:0001317 | 574 | 15 × 34 × 16 |  |
| circulatory_system | `VH_F_internal_iliac_vein_R` | internal iliac vein | UBERON:0001317 | 838 | 12 × 46 × 26 |  |
| circulatory_system | `VH_F_internal_pudendal_vein_L` | internal pudendal vein | UBERON:0018252 | 1,404 | 12 × 69 × 32 |  |
| circulatory_system | `VH_F_internal_pudendal_vein_R` | internal pudendal vein | UBERON:0018252 | 1,560 | 16 × 76 × 23 |  |
| circulatory_system | `VH_F_middle_rectal_vein_L` | Left middle rectal vein | FMA:18895 | 1,036 | 40 × 20 × 32 |  |
| circulatory_system | `VH_F_middle_rectal_vein_R` | Right middle rectal vein | FMA:18894 | 1,000 | 32 × 16 × 30 |  |
| circulatory_system | `VH_F_sigmoid_vein_a` | sigmoid vein | FMA:15395 | 416 | 3 × 8 × 3 |  |
| circulatory_system | `VH_F_sigmoid_vein_c` | sigmoid vein | FMA:15395 | 700 | 5 × 17 × 12 |  |
| circulatory_system | `VH_F_median_sacral_vein` | median sacral vein | UBERON:0006687 | 1,835 | 12 × 115 × 89 |  |
| circulatory_system | `VH_F_sigmoid_vein_b` | sigmoid vein | FMA:15395 | 1,732 | 30 × 38 × 12 |  |
| circulatory_system | `VH_F_inferior_pancreaticoduodenal_vein` | Inferior pancreaticoduodenal vein | FMA:0329299 | 1,856 | 28 × 24 × 5 |  |
| circulatory_system | `VH_F_inferior_mesenteric_vein` | superior mesenteric artery | UBERON:0001182 | 6,934 | 35 × 155 × 34 |  |
| circulatory_system | `VH_F_left_colic_artery` | Left colic artery | FMA:14826 | 1,264 | 38 × 22 × 26 |  |
| circulatory_system | `VH_F_right_colic_artery` | Right colic artery | FMA:14811 | 1,650 | 45 × 56 × 12 |  |
| circulatory_system | `VH_F_ileocolic_artery` | ileocolic artery | UBERON:0035548 | 1,486 | 31 × 65 × 12 |  |
| circulatory_system | `VH_F_middle_colic_artery` | middle colic artery | UBERON:0001196 | 1,405 | 49 × 17 × 21 |  |
| circulatory_system | `VH_F_celiac_trunk` | Celiac trunk | FMA:14812 | 384 | 10 × 10 × 18 |  |
| circulatory_system | `VH_F_superior_rectal_artery` | superior rectal artery | UBERON:0035040 | 2,080 | 31 × 35 × 63 |  |
| circulatory_system | `VH_F_superior_mesenteric_artery` | superior mesenteric artery | UBERON:0001182 | 2,833 | 34 × 113 × 34 |  |
| circulatory_system | `VH_F_inferior_mesenteric_artery` | inferior mesenteric artery | UBERON:0001183 | 2,179 | 15 × 96 × 33 |  |
| circulatory_system | `VH_F_marginal_artery_of_Drummond` | marginal colic artery | FMA:14824 | 7,647 | 150 × 123 × 68 |  |
| circulatory_system | `VH_F_sigmoid_artery_c` | sigmoid artery | UBERON:0035180 | 646 | 11 × 29 × 18 |  |
| circulatory_system | `VH_F_sigmoid_artery_b` | sigmoid artery | UBERON:0035180 | 520 | 14 × 22 × 4 |  |
| circulatory_system | `VH_F_sigmoid_artery_a` | sigmoid artery | UBERON:0035180 | 794 | 33 × 37 × 9 |  |
| circulatory_system | `VH_F_splenic_artery` | splenic artery | UBERON:0001194 | 5,894 | 98 × 74 × 74 |  |
| circulatory_system | `VH_F_splenic_vein` | splenic vein | UBERON:0003713 | 9,254 | 109 × 101 × 80 |  |
| circulatory_system | `VH_F_cystic_artery` | cystic artery | UBERON:0039222 | 1,430 | 44 × 58 × 41 |  |
| circulatory_system | `VH_F_cystic_vein` | cystic vein | UBERON:0035392 | 3,240 | 47 × 54 × 38 |  |
| circulatory_system | `VH_F_middle_hepatic_artery_branch_of_left_hepatic_artery` | - | - | 468 | 17 × 11 × 16 |  |
| circulatory_system | `VH_F_proper_hepatic_artery` | Hepatic artery proper | FMA:14772 | 620 | 19 × 23 × 8 |  |
| circulatory_system | `VH_F_right_hepatic_artery` | Right hepatic artery | FMA:14778 | 652 | 23 × 11 × 20 |  |
| circulatory_system | `VH_F_common_hepatic_artery` | common hepatic artery | UBERON:0005436 | 582 | 22 × 9 × 18 |  |
| circulatory_system | `VH_F_posterior_segmental_right_hepatic_artery` | - | - | 762 | 7 × 9 × 42 |  |
| circulatory_system | `VH_F_anterior_segmental_right_hepatic_artery` | - | - | 270 | 12 × 9 × 9 |  |
| circulatory_system | `VH_F_left_hepatic_artery` | Left hepatic artery | FMA:14779 | 1,276 | 55 × 32 × 19 |  |
| circulatory_system | `VH_F_hepatic_portal_vein` | hepatic portal vein | UBERON:0001639 | 2,262 | 35 × 63 × 17 |  |
| circulatory_system | `VH_F_middle_hepatic_vein` | Middle hepatic vein | FMA:14340 | 824 | 49 × 39 × 34 |  |
| circulatory_system | `VH_F_left_hepatic_vein` | Left hepatic vein | FMA:14339 | 650 | 19 × 36 × 40 |  |
| circulatory_system | `VH_F_right_hepatic_vein` | Right hepatic vein | FMA:14338 | 1,044 | 73 × 20 × 13 |  |
| circulatory_system | `VH_F_right_branch_of_portal_vein` | - | - | 1,788 | 32 × 13 × 16 |  |
| circulatory_system | `VH_F_left_branch_of_portal_vein` | - | - | 1,612 | 27 × 19 × 26 |  |
| circulatory_system | `VH_F_pulmonary_vein_L_sup` | left superior pulmonary vein | FMA:49916 | 2,118 | 32 × 21 × 23 |  |
| circulatory_system | `VH_F_pulmonary_vein_R_inf` | left inferior pulmonary vein | FMA:49913 | 1,596 | 25 × 22 × 17 |  |
| circulatory_system | `VH_F_pulmonary_vein_R_sup` | right superior pulmonary vein | FMA:49914 | 2,208 | 27 × 28 × 27 |  |
| circulatory_system | `VH_F_pulmonary_vein_L_inf` | right inferior pulmonary vein | FMA:49911 | 1,894 | 32 × 18 × 14 |  |
| circulatory_system | `VH_F_coronary_sinus` | coronary sinus | UBERON:0005438 | 6,034 | 26 × 68 × 33 |  |
| circulatory_system | `VH_F_great_cardiac_vein` | great vein of heart | UBERON:0006958 | 6,862 | 55 × 56 × 77 |  |
| circulatory_system | `VH_F_middle_cardiac_vein` | middle cardiac vein | UBERON:0009687 | 3,620 | 67 × 8 × 30 |  |
| circulatory_system | `VH_F_oblique_vein_of_left_atrium` | Oblique vein of left atrium | FMA:4715 | 948 | 2 × 10 × 14 |  |
| circulatory_system | `VH_F_left_marginal_vein` | left marginal vein | FMA:4708 | 3,356 | 46 × 8 × 17 |  |
| circulatory_system | `VH_F_posterior_vein_of_left_ventricle` | Posterior vein of left ventricle | FMA:4712 | 4,082 | 63 × 26 × 17 |  |
| circulatory_system | `VH_F_anterior_cardiac_vein` | Anterior cardiac vein | FMA:76767 | 3,348 | 33 × 32 × 25 |  |
| circulatory_system | `VH_F_small_cardiac_vein` | small cardiac vein | UBERON:0035374 | 4,796 | 28 × 13 × 53 |  |
| circulatory_system | `VH_F_superior_vena_cava` | superior vena cava | FMA:4720 | 3,978 | 25 × 82 × 34 |  |
| circulatory_system | `VH_F_inferior_vena_cava_a` | inferior vena cava | FMA:10951 | 3,614 | 32 × 52 × 32 |  |
| circulatory_system | `VH_F_inferior_vena_cava_b` | inferior vena cava | FMA:10951 | 10,866 | 31 × 226 × 48 |  |
| circulatory_system | `VH_F_left_anterior_descending_artery` | Anterior descending branch of left pulmonary artery | FMA:8636 | 3,230 | 61 × 76 × 43 |  |
| circulatory_system | `VH_F_left_circumflex_artery` | circumflex branch of left coronary artery | UBERON:0035422 | 1,482 | 13 × 21 × 31 |  |
| circulatory_system | `VH_F_diagonal_branch_of_left_anterior_descending_artery` | Diagonal branch of anterior descending branch of left coronary artery | FMA:3860 | 1,180 | 32 × 21 × 35 |  |
| circulatory_system | `VH_F_left_coronary_artery` | left coronary artery | UBERON:0001626 | 626 | 11 × 13 × 12 |  |
| circulatory_system | `VH_F_left_marginal_branch` | Left marginal artery | FMA:3902 | 1,084 | 35 × 10 × 5 |  |
| circulatory_system | `VH_F_left_posterior_descending_branch_of_circumflex_branch_of_left_coronary_artery` | left posterior descending branch of circumflex branch of left coronary artery | FMA:322904 | 2,444 | 69 × 18 × 24 |  |
| circulatory_system | `VH_F_posterior_left_ventricular_branch` | Posterior ventricular branch of circumflex coronary artery | FMA:13905 | 1,620 | 50 × 29 × 13 |  |
| circulatory_system | `VH_F_right_coronary_artery` | right coronary artery | UBERON:0001625 | 5,446 | 37 × 63 × 80 |  |
| circulatory_system | `VH_F_right_marginal_artery` | marginal branch of right coronary artery | FMA:3818 | 1,636 | 49 × 10 × 15 |  |
| circulatory_system | `VH_F_pulmonary_artery_L` | left pulmonary artery | UBERON:0001652 | 2,946 | 43 × 22 × 45 |  |
| circulatory_system | `VH_F_pulmonary_trunk` | pulmonary trunk | UBERON:0002333 | 2,350 | 33 × 40 × 48 |  |
| circulatory_system | `VH_F_pulmonary_artery_R` | right pulmonary artery | UBERON:0001651 | 3,060 | 51 × 30 × 34 |  |
| circulatory_system | `VH_F_aortic_arch` | arch of aorta | UBERON:0001508 | 6,094 | 49 × 40 × 70 |  |
| circulatory_system | `VH_F_ascending_aorta` | ascending aorta | UBERON:0001496 | 5,344 | 38 × 67 × 31 |  |
| circulatory_system | `VH_F_descending_aorta_a` | descending aorta | UBERON:0001514 | 6,004 | 28 × 151 × 38 |  |
| circulatory_system | `VH_F_descending_aorta_b` | descending aorta | UBERON:0001514 | 7,930 | 43 × 219 × 69 |  |
| circulatory_system | `VH_F_left_common_carotid_artery_a` | left common carotid artery plus branches | UBERON:0001536 | 684 | 9 × 15 × 10 |  |
| circulatory_system | `VH_F_left_common_carotid_artery_b` | left common carotid artery plus branches | UBERON:0001536 | 2,640 | 11 × 50 × 24 |  |
| circulatory_system | `VH_F_left_subclavian_artery_a` | left subclavian artery | UBERON:0001584 | 1,216 | 14 × 19 × 15 |  |
| circulatory_system | `VH_F_left_subclavian_artery_b` | left subclavian artery | UBERON:0001584 | 2,686 | 12 × 31 × 14 |  |
| circulatory_system | `VH_F_brachiocephalic_artery_b` | brachiocephalic artery | UBERON:0001529 | 3,358 | 26 × 60 × 16 |  |
| circulatory_system | `VH_F_brachiocephalic_artery_a` | brachiocephalic artery | UBERON:0001529 | 684 | 15 × 18 × 10 |  |
| respiratory_system | `VH_F_hilum_L` | left lung hilus | UBERON:0004887 | 1,414 | 29 × 43 × 46 | yes |
| respiratory_system | `VH_F_hilum_upper_L` | left lung hilus | UBERON:0004887 | 792 | 28 × 35 × 43 | yes |
| respiratory_system | `VH_F_lingula_superior_bronchopulmonary_segment` | Superior lingular bronchopulmonary segment | FMA:7374 | 1,312 | 107 × 73 × 89 | yes |
| respiratory_system | `VH_F_left_anterior_bronchopulmonary_segment` | Left Anterior Bronchopulmonary Segment | FMA:7373 | 1,024 | 106 × 93 × 101 | yes |
| respiratory_system | `VH_F_left_apical_bronchopulmonary_segment` | Left apical bronchopulmonary segment | FMA:7385 | 458 | 96 × 65 × 55 | yes |
| respiratory_system | `VH_F_left_posterior_bronchopulmonary_segment` | Left posterior bronchopulmonary segment | FMA:7386 | 1,028 | 97 × 71 × 57 | yes |
| respiratory_system | `VH_F_lingula_inferior_bronchopulmonary_segment` | Inferior lingular bronchopulmonary segment | FMA:7375 | 1,142 | 88 × 61 × 80 | yes |
| respiratory_system | `VH_F_left_superior_bronchopulmonary_segment` | Left superior bronchopulmonary segment | FMA:7376 | 1,359 | 93 × 76 × 51 | yes |
| respiratory_system | `VH_F_left_posterior_basal_bronchopulmonary_segment` | Left posterior basal bronchopulmonary segment | FMA:7380 | 1,674 | 78 × 135 × 64 | yes |
| respiratory_system | `VH_F_left_anterior_basal_bronchopulmonary_segment` | left anterior basal bronchopulmonary segment | FMA:7378 | 606 | 72 × 92 × 91 | yes |
| respiratory_system | `VH_F_left_lateral_basal_bronchopulmonary_segment` | left Lateral Basal Bronchopulmonary Segment | FMA:7379 | 616 | 61 × 97 × 58 | yes |
| respiratory_system | `VH_F_left_medial_basal_bronchopulmonary_segment` | Left Medial Basal Bronchopulmonary Segment | FMA:7377 | 1,741 | 82 × 107 × 78 | yes |
| respiratory_system | `VH_F_hilum_lower_L` | left lung hilus | UBERON:0004887 | 622 | 27 × 34 × 32 | yes |
| respiratory_system | `VH_F_hilum_R` | right lung hilus | UBERON:0004888 | 3,784 | 61 × 92 × 57 | yes |
| respiratory_system | `VH_F_right_medial_basal_bronchopulmonary_segment` | Right Medial Basal Bronchopulmonary Segment | FMA:7365 | 434 | 28 × 64 × 54 | yes |
| respiratory_system | `VH_F_right_posterior_basal_bronchopulmonary_segment` | Right Posterior Basal Bronchopulmonary Segment | FMA:7362 | 1,602 | 105 × 92 × 55 | yes |
| respiratory_system | `VH_F_right_anterior_basal_bronchopulmonary_segment` | Right anterior basal bronchopulmonary segment | FMA:7364 | 2,202 | 90 × 109 × 94 | yes |
| respiratory_system | `VH_F_right_lateral_basal_bronchopulmonary_segment` | Right Lateral Basal Bronchopulmonary Segment | FMA:7363 | 784 | 99 × 82 × 58 | yes |
| respiratory_system | `VH_F_right_superior_bronchopulmonary_segment` | Right Superior Bronchopulmonary Segment | FMA:7366 | 2,158 | 102 × 104 × 62 | yes |
| respiratory_system | `VH_F_hilum_lower_R` | right lung hilus | UBERON:0004888 | 2,276 | 47 × 92 × 42 | yes |
| respiratory_system | `VH_F_right_medial_bronchopulmonary_segment` | Right Medial Bronchopulmonary Segment | FMA:7360 | 1,950 | 73 × 95 × 78 | yes |
| respiratory_system | `VH_F_right_lateral_bronchopulmonary_segmennt` | Right Lateral Bronchopulmonary Segment | FMA:7361 | 1,134 | 70 × 96 × 91 | yes |
| respiratory_system | `VH_F_hilum_middle_R` | right lung hilus | UBERON:0004888 | 482 | 48 × 39 × 42 | yes |
| respiratory_system | `VH_F_right_anterior_bronchopulmonary_segm` | Right Anterior Bronchopulmonary Segment | FMA:7359 | 2,744 | 127 × 107 × 81 | yes |
| respiratory_system | `VH_F_right_apical_bronchopulmonary_segment` | Right Apical Bronchopulmonary Segment | FMA:7338 | 1,176 | 84 × 62 × 75 | yes |
| respiratory_system | `VH_F_right_posterior_bronchopulmonary_segment` | Right Posterior Bronchopulmonary Segment | FMA:7339 | 1,224 | 99 × 91 × 64 | yes |
| respiratory_system | `VH_F_hilum_upper_R` | right lung hilus | UBERON:0004888 | 1,026 | 35 × 59 × 48 | yes |
| respiratory_system | `VH_F_arytenoid_cartilage_R` | Right arytenoid cartilage | FMA:55113 | 2,384 | 10 × 19 × 13 |  |
| respiratory_system | `VH_F_arytenoid_cartilage_L` | Left arytenoid cartilage | FMA:55114 | 2,400 | 10 × 19 × 13 |  |
| respiratory_system | `VH_F_epiglotic_cartilage` | epiglottic cartilage | UBERON:0001742 | 3,394 | 20 × 32 × 11 |  |
| respiratory_system | `VH_F_cricoid_cartilage` | cricoid cartilage | UBERON:0002375 | 3,403 | 31 × 27 × 25 |  |
| respiratory_system | `VH_F_thyroid_cartilage` | thyroid cartilage | UBERON:0001738 | 4,560 | 46 × 47 × 35 |  |
| respiratory_system | `VH_F_corniculate_cartilage_L` | Left corniculate cartilage | FMA:55116 | 574 | 4 × 6 × 4 |  |
| respiratory_system | `VH_F_corniculate_cartilage_R` | Right corniculate cartilage | FMA:55115 | 776 | 6 × 6 × 5 |  |
| respiratory_system | `VH_F_trachea` | trachea | UBERON:0003126 | 2,268 | 24 × 108 × 77 |  |
| respiratory_system | `VH_F_tracheal_cartilage` | trachea cartilage | UBERON:0003604 | 21,180 | 25 × 68 × 53 |  |
| respiratory_system | `VH_F_carina` | carina of trachea | UBERON:0006679 | 4,272 | 26 × 23 × 19 |  |
| respiratory_system | `VH_F_right_main_bronchus` | Right Main Bronchus | UBERON:0002177 | 374 | 36 × 52 × 28 |  |
| respiratory_system | `VH_F_cartilage_of_main_bronchus_R` | Cartilage of right main bronchus | FMA:13143 | 17,854 | 33 × 51 × 28 |  |
| respiratory_system | `VH_F_left_main_bronchus` | Left Main Bronchus | UBERON:0002178 | 495 | 53 × 45 × 31 |  |
| respiratory_system | `VH_F_cartilage_of_main_bronchus_L` | Cartilage of left main bronchus | FMA:13144 | 15,142 | 48 × 45 × 27 |  |
| respiratory_system | `VH_F_cartilage_of_lobar_bronchus_L` | Cartilage of lobar bronchus | FMA:62659 | 21,358 | 31 × 65 × 44 |  |
| respiratory_system | `VH_F_cartilage_of_tertiary_bronchus_L` | Cartilage of segmental bronchus | FMA:62662 | 88,352 | 61 × 129 × 114 |  |
| respiratory_system | `VH_F_left_superior_lobar_bronchus` | lobar bronchus of left lung upper lobe | UBERON:0012065 | 385 | 21 × 35 × 19 |  |
| respiratory_system | `VH_F_left_inferior_lobar_bronchus` | lobar bronchus of left lung lower lobe | UBERON:0012066 | 558 | 32 × 46 × 26 |  |
| respiratory_system | `VH_F_left_anterior_basal_bronchus` | Left anterior basal segmental bronchus | FMA:7506 | 395 | 24 × 21 × 12 |  |
| respiratory_system | `VH_F_left_lingula_superior_bronchus` | Superior lingular bronchus | FMA:7430 | 1,052 | 44 × 19 × 69 |  |
| respiratory_system | `VH_F_left_apical_bronchus` | Left apical segmental bronchus | FMA:7426 | 270 | 20 × 25 × 22 |  |
| respiratory_system | `VH_F_left_posterior_basal_bronchus` | Left posterior basal segmental bronchus | FMA:7508 | 750 | 25 × 47 × 21 |  |
| respiratory_system | `VH_F_left_medial_basal_bronchus` | Left medial basal segmental bronchus | FMA:7505 | 377 | 27 × 14 × 11 |  |
| respiratory_system | `VH_F_left_superior_bronchus` | Left superior segmental bronchus | FMA:7504 | 610 | 31 × 26 × 19 |  |
| respiratory_system | `VH_F_left_anterior_bronchus` | Left anterior segmental bronchus | FMA:7428 | 530 | 26 × 19 × 48 |  |
| respiratory_system | `VH_F_left_posterior_bronchus` | Left posterior segmental bronchus | FMA:7427 | 666 | 34 × 41 × 21 |  |
| respiratory_system | `VH_F_left_lateral_basal_bronchus` | Left lateral basal segmental bronchus | FMA:7507 | 510 | 30 × 34 × 14 |  |
| respiratory_system | `VH_F_left_lingula_inferior_bronchi` | Inferior lingular bronchus | FMA:7431 | 1,055 | 45 × 29 × 45 |  |
| respiratory_system | `VH_F_cartilage_of_lobar_bronchus_R` | Cartilage of lobar bronchus | FMA:62659 | 29,218 | 30 × 74 × 48 |  |
| respiratory_system | `VH_F_cartilage_of_tertiary_bronchus_R` | Cartilage of segmental bronchus | FMA:62662 | 105,786 | 66 × 121 × 110 |  |
| respiratory_system | `VH_F_right_middle_lobar_bronchus` | Middle lobar bronchus | FMA:7401 | 262 | 17 × 15 × 21 |  |
| respiratory_system | `VH_F_right_superior_lobar_bronchus` | Right superior lobar bronchus | FMA:7397 | 224 | 21 × 19 × 21 |  |
| respiratory_system | `VH_F_right_inferior_lobar_bronchus` | Right inferior lobar bronchus | FMA:7404 | 692 | 32 × 45 × 35 |  |
| respiratory_system | `VH_F_right_anterior_bronchus` | Right anterior segmental bronchus | FMA:7400 | 1,197 | 45 × 36 × 56 |  |
| respiratory_system | `VH_F_right_lateral_basal_bronchus` | Right lateral basal segmental bronchus | FMA:7419 | 376 | 39 × 18 × 19 |  |
| respiratory_system | `VH_F_right_lateral_bronchus` | Lateral segmental bronchus | FMA:7402 | 458 | 29 × 16 × 25 |  |
| respiratory_system | `VH_F_right_medial_bronchus` | Medial segmental bronchus | FMA:7403 | 612 | 15 × 29 × 38 |  |
| respiratory_system | `VH_F_right_medial_basal_bronchus` | Right medial basal segmental bronchus | FMA:7417 | 474 | 28 × 23 × 28 |  |
| respiratory_system | `VH_F_right_posterior_basal_bronchus` | Right posterior basal segmental bronchus | FMA:7420 | 522 | 29 × 24 × 26 |  |
| respiratory_system | `VH_F_right_posterior_bronchus` | Right posterior segmental bronchus | FMA:7399 | 832 | 44 × 32 × 33 |  |
| respiratory_system | `VH_F_right_superior_bronchus` | Right superior segmental bronchus | FMA:7416 | 708 | 31 × 18 × 31 |  |
| respiratory_system | `VH_F_right_apical_bronchus` | Right apical segmental bronchus | FMA:7398 | 1,270 | 32 × 43 × 49 |  |
| respiratory_system | `VH_F_right_anterior_basal_bronchus` | Right anterior basal segmental bronchus | FMA:7418 | 834 | 46 × 22 × 38 |  |
| lymphatic_system | `VH_F_gastric_surface_of_spleen` | gastric surface of spleen | FMA:15837 | 1,778 | 82 × 81 × 47 |  |
| lymphatic_system | `VH_F_diaphragmatic_surface_of_spleen` | diaphragmatic surface of spleen | FMA:15828 | 4,338 | 90 × 102 × 70 |  |
| lymphatic_system | `VH_F_colic_surface_of_spleen` | colic surface of spleen | FMA:15838 | 130 | 17 × 18 × 9 |  |
| lymphatic_system | `VH_F_hilum_of_spleen` | hilum of spleen | UBERON:0001248 | 1,506 | 52 × 62 × 38 |  |
| lymphatic_system | `VH_F_renal_surface_of_spleen` | renal surface of spleen | FMA:15839 | 792 | 71 × 54 × 45 |  |
| lymphatic_system | `VH_F_thymus_lobe_L` | left thymus lobe | UBERON:0005457 | 2,144 | 73 × 124 × 54 |  |
| lymphatic_system | `VH_F_thymus_lobe_R` | right thymus lobe | UBERON:0005469 | 1,720 | 37 × 119 × 50 |  |
| lymphatic_system | `Yao_afferent_lymphatic_vessel` | afferent lymphatic vessel | UBERON:0010396 | 4,526 | 9 × 4 × 7 |  |
| lymphatic_system | `Yao_capsule_of_lymph_node` | capsule of lymph node | UBERON:0002194 | 9,442 | 20 × 9 × 12 |  |
| lymphatic_system | `Yao_follicles` | lymph node follicle | UBERON:0010748 | 5,758 | 17 × 8 × 10 |  |
| lymphatic_system | `Yao_efferent_lymph_node` | efferent lymphatic vessel | UBERON:0010397 | 4,154 | 9 × 5 × 9 |  |
| lymphatic_system | `Yao_medulla_of_lymph_node` | medulla of lymph node | UBERON:0002007 | 88,388 | 19 × 8 × 11 |  |
| lymphatic_system | `Yao_paracortex` | lymph node T cell domain | UBERON:0010417 | 10,910 | 18 × 6 × 10 |  |
| lymphatic_system | `Yao_blood_vasculature` | Lymph vasculature | UBERON:0004536 | 131,485 | 18 × 8 × 12 |  |
| skeletal_system | `VH_F_sacrum` | fused sacrum | UBERON:0003690 | 19,636 | 127 × 99 × 105 | yes |
| skeletal_system | `VH_F_coccyx` | coccyx | UBERON:0001350 | 1,390 | 32 × 27 × 38 | yes |
| skeletal_system | `VH_F_pubis_spongy_bone_L` | trabecular bone tissue | UBERON:0002483 | 2,312 | 92 × 89 × 67 |  |
| skeletal_system | `VH_F_pubis_spongy_bone_R` | trabecular bone tissue | UBERON:0002483 | 2,172 | 92 × 91 × 69 |  |
| skeletal_system | `VH_F_pubis_compact_bone_R` | compact bone tissue | UBERON:0001439 | 5,080 | 94 × 93 × 71 | yes |
| skeletal_system | `VH_F_pubis_compact_bone_L` | compact bone tissue | UBERON:0001439 | 5,376 | 94 × 91 × 68 | yes |
| skeletal_system | `VH_F_ilium_compact_bone_R` | compact bone tissue | UBERON:0001439 | 11,810 | 115 × 140 × 162 | yes |
| skeletal_system | `VH_F_ilium_compact_bone_L` | compact bone tissue | UBERON:0001439 | 12,684 | 119 × 138 × 166 | yes |
| skeletal_system | `VH_F_ilium_spongy_bone_L` | trabecular bone tissue | UBERON:0002483 | 6,022 | 116 × 136 × 163 |  |
| skeletal_system | `VH_F_ilium_spongy_bone_R` | trabecular bone tissue | UBERON:0002483 | 5,597 | 113 × 138 × 159 |  |
| skeletal_system | `VH_F_ischium_compact_bone_R` | compact bone tissue | UBERON:0001439 | 5,390 | 81 × 95 × 68 | yes |
| skeletal_system | `VH_F_ischium_compact_bone_L` | compact bone tissue | UBERON:0001439 | 5,392 | 83 × 95 × 65 | yes |
| skeletal_system | `VH_F_ischium_spongy_bone_R` | trabecular bone tissue | UBERON:0002483 | 2,291 | 79 × 93 × 66 |  |
| skeletal_system | `VH_F_ischium_spongy_bone_L` | trabecular bone tissue | UBERON:0002483 | 2,296 | 81 × 93 × 63 |  |
| skeletal_system | `VH_F_right_tibial_collateral_ligament` | Right tibial collateral ligament | FMA:44601 | 1,680 | 45 × 108 × 18 |  |
| skeletal_system | `VH_F_anterior_cruciate_ligament_of_knee_R` | Right anterior cruciate ligament | FMA:44615 | 988 | 22 × 27 × 39 |  |
| skeletal_system | `VH_F_posterior_cruciate_ligament_of_knee_R` | Right posterior cruciate ligament | FMA:44618 | 988 | 27 × 37 × 22 |  |
| skeletal_system | `VH_F_anterolateral_ligament_of_knee_R` | anterolateral ligament of knee | UBERON:0014899 | 1,680 | 9 × 57 × 14 |  |
| skeletal_system | `VH_F_fibular_collateral_ligament_R` | Right fibular collateral ligament | FMA:44609 | 1,680 | 17 × 64 × 46 |  |
| skeletal_system | `VH_F_patellar_ligament_R` | Right patellar ligament | FMA:44585 | 1,104 | 26 × 74 × 42 |  |
| skeletal_system | `VH_F_meniscus_R` | Articular disk of knee joint | FMA64019 | 2,384 | 73 × 20 × 59 |  |
| skeletal_system | `VH_F_femur_R` | Right femur | FMA:24474 | 8,916 | 98 × 421 × 65 |  |
| skeletal_system | `VH_F_trochlear_groove_R` | Patellar surface of right femur | FMA:43746 | 26 | 10 × 19 × 32 |  |
| skeletal_system | `VH_F_medial_perichondular_surface_R` | - | - | 66 | 8 × 20 × 26 |  |
| skeletal_system | `VH_F_articular_cartilage_of_knee_R` | Articular cartilage of distal epiphysis of right femur | FMA:33189 | 328 | 79 × 44 × 61 |  |
| skeletal_system | `VH_F_medial_condyle_of_right_femur_sup` | Medial condyle of right femur | FMA:32862 | 90 | 25 × 23 × 24 |  |
| skeletal_system | `VH_F_lateral_condyle_of_femur_sup_R` | Lateral condyle of right femur | FMA:32860 | 68 | 25 × 21 × 24 |  |
| skeletal_system | `VH_F_medial_condyle_of_right_femur_inf` | Medial condyle of right femur | FMA:32862 | 158 | 27 × 35 × 13 |  |
| skeletal_system | `VH_F_lateral_condyle_of_femur_inf_R` | Lateral condyle of right femur | FMA:32860 | 140 | 27 × 33 × 14 |  |
| skeletal_system | `VH_F_lateral_condyle_of_femur_frontal_R` | Lateral condyle of right femur | FMA:32860 | 88 | 31 × 6 × 24 |  |
| skeletal_system | `VH_F_distal_most_point_of_medial_condyle_R` | distal-most point of medial condyle of femur | UBERON:7500033 | 88 | 33 × 10 × 29 |  |
| skeletal_system | `VH_F_intercondylar_fossa_R` | Intercondylar fossa of right femur | FMA:43749 | 58 | 7 × 29 × 13 |  |
| skeletal_system | `VH_F_posterior_cruciate_enthesis_R` | - | - | 80 | 20 × 29 × 13 |  |
| skeletal_system | `VH_F_anterior_cruciate_enthesis_R` | - | - | 78 | 10 × 27 × 20 |  |
| skeletal_system | `VH_F_lateral_perichondular_surface_R` | - | - | 75 | 4 × 17 × 24 |  |
| skeletal_system | `VH_F_lateral_epicondylar_enthesis_R` | - | - | 40 | 6 × 17 × 25 |  |
| skeletal_system | `VH_F_medial_epicondylar_enthesis_R` | - | - | 47 | 7 × 19 × 29 |  |
| skeletal_system | `VH_F_tibia_R` | Right tibia | FMA:24477 | 3,490 | 79 × 343 × 62 |  |
| skeletal_system | `VH_F_fibula_R` | Right fibula | FMA:24480 | 1,210 | 28 × 337 × 32 |  |
| skeletal_system | `VH_F_patella_R` | Right patella | FMA:24486 | 414 | 46 × 47 × 26 |  |
| skeletal_system | `VH_F_anterolateral_ligament_of_knee_L` | anterolateral ligament of knee | UBERON:0014899 | 1,680 | 9 × 57 × 14 |  |
| skeletal_system | `VH_F_fibular_collateral_ligament_L` | Left fibular collateral ligament | FMA:44610 | 1,680 | 17 × 64 × 46 |  |
| skeletal_system | `VH_F_patellar_ligament_L` | Left patellar ligament | FMA:44586 | 1,104 | 26 × 74 × 42 |  |
| skeletal_system | `VH_F_left_tibial_collateral_ligament` | Left tibial collateral ligament | FMA:44602 | 1,680 | 45 × 108 × 18 |  |
| skeletal_system | `VH_F_anterior_cruciate_ligament_of_knee_L` | Left anterior cruciate ligament | FMA:44616 | 988 | 22 × 27 × 39 |  |
| skeletal_system | `VH_F_posterior_cruciate_ligament_of_knee_L` | Left posterior cruciate ligament | FMA:44619 | 988 | 27 × 37 × 22 |  |
| skeletal_system | `VH_F_meniscus_L` | Articular disk of knee joint | FMA64019 | 2,384 | 73 × 20 × 59 |  |
| skeletal_system | `VH_F_femur_L` | Left femur | FMA:24475 | 8,916 | 98 × 421 × 65 |  |
| skeletal_system | `VH_F_intercondylar_fossa_L` | Intercondylar fossa of left femur | FMA:43750 | 58 | 7 × 29 × 13 |  |
| skeletal_system | `VH_F_anterior_cruciate_enthesis_L` | - | - | 78 | 10 × 27 × 20 |  |
| skeletal_system | `VH_F_posterior_cruciate_enthesis_L` | - | - | 80 | 20 × 29 × 13 |  |
| skeletal_system | `VH_F_lateral_perichondular_surface_L` | - | - | 75 | 4 × 17 × 24 |  |
| skeletal_system | `VH_F_lateral_epicondylar_enthesis_L` | - | - | 40 | 6 × 17 × 25 |  |
| skeletal_system | `VH_F_medial_epicondylar_enthesis_L` | - | - | 47 | 7 × 19 × 29 |  |
| skeletal_system | `VH_F_trochlear_groove_L` | Patellar surface of left femur | FMA:43747 | 26 | 10 × 19 × 32 |  |
| skeletal_system | `VH_F_medial_perichondular_surface_L` | - | - | 66 | 8 × 20 × 26 |  |
| skeletal_system | `VH_F_articular_cartilage_of_knee_L` | Articular cartilage of distal epiphysis of left femur | FMA:33190 | 328 | 79 × 44 × 61 |  |
| skeletal_system | `VH_F_medial_condyle_of_left_femur_inf` | Medial condyle of left femur | FMA:32863 | 158 | 27 × 35 × 13 |  |
| skeletal_system | `VH_F_lateral_condyle_of_femur_inf_L` | Lateral condyle of left femur | FMA:32861 | 140 | 27 × 33 × 14 |  |
| skeletal_system | `VH_F_lateral_condyle_of_femur_frontal_L` | Lateral condyle of left femur | FMA:32861 | 88 | 31 × 6 × 24 |  |
| skeletal_system | `VH_F_distal_most_point_of_medial_condyle_L` | distal-most point of medial condyle of femur | UBERON:7500033 | 88 | 33 × 10 × 29 |  |
| skeletal_system | `VH_F_lateral_condyle_of_femur_sup_L` | Lateral condyle of left femur | FMA:32861 | 68 | 25 × 21 × 24 |  |
| skeletal_system | `VH_F_medial_condyle_of_left_femur_sup` | Medial condyle of left femur | FMA:32863 | 90 | 25 × 23 × 24 |  |
| skeletal_system | `VH_F_patella_L` | Left patella | FMA:24487 | 414 | 46 × 47 × 26 |  |
| skeletal_system | `VH_F_tibia_L` | Left tibia | FMA:24478 | 3,490 | 79 × 343 × 62 |  |
| skeletal_system | `VH_F_fibula_L` | Left fibula | FMA:24481 | 1,210 | 28 × 337 × 32 |  |
| skeletal_system | `VH_F_lumbar_vertebra_1` | lumbar vertebra 1 | UBERON:0004617 | 18,208 | 91 × 48 × 81 |  |
| skeletal_system | `VH_F_lumbar_vertebra_2` | lumbar vertebra 2 | UBERON:0004618 | 17,612 | 80 × 51 × 89 |  |
| skeletal_system | `VH_F_lumbar_vertebra_3` | lumbar vertebra 3 | UBERON:0004619 | 18,540 | 91 × 56 × 89 |  |
| skeletal_system | `VH_F_lumbar_vertebra_4` | lumbar vertebra 4 | UBERON:0004620 | 19,238 | 97 × 53 × 93 |  |
| skeletal_system | `VH_F_lumbar_vertebra_5` | lumbar vertebra 5 | UBERON:0004621 | 18,002 | 96 × 51 × 91 |  |
| skeletal_system | `VH_F_lumbar_vertebra_6` | - | - | 17,860 | 105 × 46 × 87 |  |
| skeletal_system | `VH_F_thoracic_vertebra_1` | thoracic vertebra 1 | UBERON:0004626 | 15,084 | 79 × 34 × 67 |  |
| skeletal_system | `VH_F_thoracic_vertebra_2` | thoracic vertebra 2 | UBERON:0004627 | 15,536 | 71 × 40 × 69 |  |
| skeletal_system | `VH_F_thoracic_vertebra_3` | thoracic vertebra 3 | UBERON:0004628 | 16,232 | 66 × 37 × 73 |  |
| skeletal_system | `VH_F_thoracic_vertebra_4` | thoracic vertebra 4 | UBERON:0004629 | 15,292 | 64 × 44 × 79 |  |
| skeletal_system | `VH_F_thoracic_vertebra_5` | thoracic vertebra 5 | UBERON:0004630 | 15,846 | 65 × 45 × 74 |  |
| skeletal_system | `VH_F_thoracic_vertebra_6` | thoracic vertebra 6 | UBERON:0004631 | 16,030 | 64 × 46 × 77 |  |
| skeletal_system | `VH_F_thoracic_vertebra_7` | thoracic vertebra 7 | UBERON:0004632 | 15,848 | 67 × 50 × 72 |  |
| skeletal_system | `VH_F_thoracic_vertebra_8` | thoracic vertebra 8 | UBERON:0011050 | 16,830 | 66 × 48 × 73 |  |
| skeletal_system | `VH_F_thoracic_vertebra_9` | thoracic vertebra 9 | UBERON:0004633 | 16,486 | 70 × 44 × 73 |  |
| skeletal_system | `VH_F_thoracic_vertebra_10` | thoracic vertebra 10 | UBERON:0004634 | 16,402 | 68 × 41 × 77 |  |
| skeletal_system | `VH_F_thoracic_vertebra_11` | thoracic vertebra 11 | UBERON:0004635 | 15,614 | 57 × 40 × 75 |  |
| skeletal_system | `VH_F_thoracic_vertebra_12` | thoracic vertebra 12 | UBERON:0004636 | 17,736 | 55 × 45 × 75 |  |
| skeletal_system | `VH_F_cervical_vertebra_1` | vertebral bone 1 | UBERON:0001092 | 15,952 | 86 × 30 × 49 |  |
| skeletal_system | `VH_F_cervical_vertebra_2` | vertebral bone 2 | UBERON:0001093 | 15,426 | 60 × 44 × 54 |  |
| skeletal_system | `VH_F_cervical_vertebra_3` | mammalian cervical vertebra 3 | UBERON:0004612 | 17,926 | 60 × 22 × 49 |  |
| skeletal_system | `VH_F_cervical_vertebra_4` | mammalian cervical vertebra 4 | UBERON:0004613 | 19,724 | 61 × 25 × 44 |  |
| skeletal_system | `VH_F_cervical_vertebra_5` | mammalian cervical vertebra 5 | UBERON:0004614 | 19,472 | 63 × 27 × 44 |  |
| skeletal_system | `VH_F_cervical_vertebra_6` | mammalian cervical vertebra 6 | UBERON:0004615 | 18,848 | 60 × 28 × 51 |  |
| skeletal_system | `VH_F_cervical_vertebra_7` | mammalian cervical vertebra 7 | UBERON:0004616 | 16,724 | 70 × 32 × 62 |  |
