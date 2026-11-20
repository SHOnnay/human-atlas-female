import fs from 'node:fs';
import assert from 'node:assert/strict';
// Usage: node scripts/validate-atlas.mjs [atlas.json | female/atlas.json]   (no argument: both)
const models=new URL('../public/models/',import.meta.url);
const targets=process.argv[2]?[process.argv[2]]:['atlas.json','female/atlas.json'];
const MALE_ONLY=/penis|testis|testicular|scrot|prostat|seminal|deferent|epididym|spermatic|cremaster|ejaculat|bulbourethral/i;
// Step 2b checklist: every item must be present in the female model (found, adapted or generated).
const FEMALE_REQUIRED={
 'hip bones':/^(left|right) (ilium|ischium|pubis)$/i,sacrum:/sacrum/i,coccyx:/coccyx/i,uterus:/body of uterus|fundus of uterus/i,cervix:/cervix/i,
 'uterine tubes':/uterine tube/i,fimbriae:/fimbria/i,ovaries:/^(left|right) ovary$/i,'ovarian ligament':/ovarian ligament/i,
 'round ligament':/round ligament/i,'broad ligament':/broad ligament/i,vagina:/^vagina$/i,'labia majora':/labium majus/i,
 'labia minora':/labium minus/i,clitoris:/clitoris/i,vestibule:/vestibule of vagina/i,'female urethra':/female urethra/i,
 'mammary glands':/mammary lobe|mammary gland/i,'breast fat':/adipose tissue of .*mammary/i,
 'pelvic floor muscles':/pubococcygeus|iliococcygeus|puborectalis/i,'female perineal muscles':/bulbospongiosus|ischiocavernosus/i,
 'lungs':/bronchopulmonary segment/i,'ovarian arteries':/ovarian artery/i,'ovarian veins':/ovarian vein/i,
 "Bartholin's glands":/greater vestibular/i,"Skene's glands":/paraurethral/i,'perineal body':/perineal body/i,
 'mons pubis':/mons pubis/i,'prepuce of clitoris':/prepuce of clitoris/i,'vestibular bulbs':/bulb of vestibule/i,
 'gluteofemoral fat':/subcutaneous fat of hips/i,
};
for(const filename of targets){
 const path=new URL(filename,models);
 if(!fs.existsSync(path)){if(process.argv[2])throw new Error(`${filename} not found`);console.log(`${filename}: not built, skipped.`);continue;}
 const base=new URL('.',path),atlas=JSON.parse(fs.readFileSync(path));
 const female=atlas.sex==='female';
 if(!female){assert.equal(atlas.parts.length,2234);assert.equal(atlas.concepts.length,3432);}
 const ids=new Set(atlas.parts.map(p=>p.id));assert.equal(ids.size,atlas.parts.length,'picking ids must be unique');
 const files=atlas.chunks.map(c=>{const b=fs.readFileSync(new URL(c.url.split('/').pop(),base));assert.equal(b.length,c.bytes);if(c.gzip){assert.ok(fs.existsSync(new URL(c.gzip.split('/').pop(),base)),`${c.gzip} missing`);}return b;});
 let tris=0;
 for(const p of atlas.parts){assert.ok(p.name.trim()&&p.name!=='-'&&!p.name.includes('Bounds('),`${p.id}: name`);assert.ok(p.conceptId&&p.conceptId!=='-',`${p.id}: conceptId`);assert.ok(p.system,`${p.id}: system`);const b=files[p.chunk];assert.ok(p.indices+p.indexCount*4<=b.length);const pos=new Float32Array(b.buffer,b.byteOffset+p.positions,p.vertexCount*3),indices=new Uint32Array(b.buffer,b.byteOffset+p.indices,p.indexCount);assert.ok(indices.length>=3);for(const i of indices)assert.ok(i<p.vertexCount,`${p.id}: invalid vertex`);for(const value of pos)assert.ok(Number.isFinite(value));tris+=p.indexCount/3;}
 for(const c of atlas.concepts){assert.ok(c.elements.length);for(const id of c.elements)assert.ok(ids.has(id),`${c.id}: missing ${id}`);}
 assert.equal(tris,atlas.triangles);
 let extra='';
 if(female){
  // Metadata: every part names its source and accuracy; generated parts are schematic.
  // Every structure is labelled scan-derived / warped / generated, consistently with its source.
  const expect={hra:'scan-derived',bp3d:'warped',generated:'generated'};
  for(const p of atlas.parts){assert.ok(atlas.sources[p.source],`${p.id}: unknown source ${p.source}`);assert.equal(p.accuracy,expect[p.source],`${p.id}: accuracy`);if(p.accuracy!=='scan-derived')assert.ok(p.note,`${p.id}: needs a provenance note`);}
  const skin=atlas.parts.filter(p=>p.name==='Skin');assert.equal(skin.length,1);assert.equal(skin[0].source,'hra','the body surface must be the scan-derived female skin');
  for(const name of ['Hip bone','Left hip bone','Right hip bone'])if(atlas.concepts.some(c=>c.name===name))assert.ok(atlas.concepts.find(c=>c.name===name).elements.every(id=>id.startsWith('VH_F_')),`${name} must be the real HRA pelvis`);
  const male=atlas.parts.filter(p=>MALE_ONLY.test(p.name));assert.deepEqual(male.map(p=>p.name),[],'male-only structures in the female model');
  for(const c of atlas.concepts)assert.ok(!MALE_ONLY.test(c.name),`male-only concept ${c.name}`);
  const missing=Object.entries(FEMALE_REQUIRED).filter(([,re])=>!atlas.parts.some(p=>re.test(p.name)));assert.deepEqual(missing.map(([k])=>k),[],'female checklist');
  // Search (the UI and WebMCP filter concept names) must find each checklist item.
  for(const [k,re] of Object.entries(FEMALE_REQUIRED))assert.ok(atlas.concepts.some(c=>re.test(c.name)),`search cannot find ${k}`);
  for(const q of ['uterus','ovary','vagina','clitoris','labium','urethra','mammary','pelvis'])assert.ok(atlas.concepts.some(c=>c.name.toLowerCase().includes(q)),`no search hit for ${q}`);
  // Left/right labels agree with geometry (+x is the body's left) for every structure added for the
  // female model. Shared BodyParts3D labels are reported only (they are identical in the male package).
  const sideMismatch=p=>{const x=(p.bounds[0][0]+p.bounds[1][0])/2,n=p.name.toLowerCase();return (/^left\b/.test(n)&&x<-0.004)||(/^right\b/.test(n)&&x>0.004);};
  for(const p of atlas.parts)if(p.source!=='bp3d')assert.ok(!sideMismatch(p),`${p.name} lies on the wrong side`);
  const sourceSide=atlas.parts.filter(p=>p.source==='bp3d'&&sideMismatch(p)).map(p=>p.name);
  // Many of these name a branch or territory rather than a body side (e.g. "right gastric artery").
  if(sourceSide.length)extra+=` Info: ${sourceSide.length} shared BodyParts3D names start with a side that differs from their centroid (branch/territory names or source labels; unchanged from the male package).`;
  const by=k=>Object.entries(atlas.parts.reduce((a,p)=>(a[p[k]]=(a[p[k]]??0)+1,a),{})).map(([a,b])=>`${a} ${b}`).join(', ');
  extra=`${extra} Sources: ${by('source')}. Accuracy: ${by('accuracy')}. No male-only structures; all ${Object.keys(FEMALE_REQUIRED).length} checklist structures present and searchable.`;
 }
 const gz=atlas.chunks.reduce((n,c)=>n+(c.gzipBytes??0),0);
 console.log(`${filename}: verified ${ids.size} individually indexed meshes, ${atlas.concepts.length} complete concept mappings, ${tris.toLocaleString()} triangles, and every binary buffer${gz?` (${(gz/1e6).toFixed(1)} MB gzip)`:''}.${extra}`);
}
