import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {readFile} from 'node:fs/promises';
import {createExplosionLayout} from '../app/explosion-layout.ts';
import {PointerTap} from '../app/pointer-tap.ts';
import {atlasTools} from '../app/agent-tools.ts';
import {carrySelection} from '../app/selection-carry.ts';

const atlases={};
for (const [body,file] of [['male','atlas.json'],['female','female/atlas.json']]) {
  const url=new URL(`../public/models/${file}`,import.meta.url);
  if(!existsSync(url)){assert.notEqual(body,'male');console.log(`${file}: not built, skipped.`);continue;}
  const atlas=JSON.parse(await readFile(url));atlases[body]=atlas;
  const groups=[atlas.parts,...[...new Set(atlas.parts.map(p=>p.system))].map(system=>atlas.parts.filter(p=>p.system===system))];
  for(const group of groups) for(const aspect of [.46,1,1.7]) {
    const layout=createExplosionLayout(group,aspect),cells=[...layout.cells.values()];
    assert.equal(cells.length,group.length);
    for(let i=0;i<cells.length;i++) {
      const a=cells[i];
      assert.ok(Math.abs(a.x)+a.width/2<=layout.width/2+1e-8);
      assert.ok(Math.abs(a.y)+a.height/2<=layout.height/2+1e-8);
      for(let j=i+1;j<cells.length;j++) {
        const b=cells[j];
        assert.ok(Math.abs(a.x-b.x)>=(a.width+b.width)/2-1e-8 || Math.abs(a.y-b.y)>=(a.height+b.height)/2-1e-8,'Exploded pieces overlap');
      }
    }
  }
  let selected=null;
  const [find,inspect]=atlasTools(atlas,c=>{selected=c;});
  for(const q of body==='female'?['femur','uterus','clitoris','ovary']:['femur']){const results=find.execute({query:q});assert.ok(results.length>0,`${file}: no result for ${q}`);}
  const results=find.execute({query:'femur'});
  inspect.execute({id:results[0].id});
  const previous=selected;
  assert.throws(()=>inspect.execute({id:'nonexistent-structure'}));
  assert.equal(selected,previous);
  assert.throws(()=>find.execute({query:' '}));
  console.log(`${file}: packing at desktop/mobile aspect ratios and search/inspection contracts passed.`);
}

if(atlases.female){
  const {male,female}=atlases;
  // WebMCP `body` parameter: a provider holding both catalogues answers for either body.
  let inspected=null;
  const provider={body:'male',get:b=>atlases[b],load:b=>Promise.resolve(atlases[b])};
  const [find,inspect]=atlasTools(provider,(c,b)=>{inspected={c,b};});
  assert.equal(find.execute({query:'uterus'}).length,0,'male atlas must not contain a uterus');
  const uterus=find.execute({query:'uterus',body:'female'});
  assert.ok(uterus.length>0&&uterus.every(r=>r.body==='female'));
  inspect.execute({id:uterus[0].id,body:'female'});
  assert.equal(inspected.b,'female');
  assert.throws(()=>find.execute({query:'heart',body:'other'}));
  // Lazy load path: an unloaded body resolves asynchronously.
  const lazy=atlasTools({body:'male',get:b=>b==='male'?male:undefined,load:async b=>atlases[b]},()=>{});
  const pending=lazy[0].execute({query:'ovary',body:'female'});
  assert.ok(pending instanceof Promise);assert.ok((await pending).length>0);
  // Selection carried across a switch.
  const carry=(atlas,name)=>{const c=atlas.concepts.find(x=>x.name.toLowerCase()===name.toLowerCase());assert.ok(c,name);return {chosen:c,parts:c.elements.map(id=>({id,conceptId:atlas.parts.find(p=>p.id===id).conceptId})),isolate:false};};
  const heart=carrySelection(carry(male,'Heart'),female);assert.ok(heart&&heart.elements.length>0,'shared heart keeps its selection');
  assert.equal(carrySelection(carry(male,'Prostate'),female),null,'male-only prostate clears');
  const bladder=carrySelection(carry(male,'Urinary bladder'),female);assert.ok(bladder&&bladder.elements.every(id=>female.parts.some(p=>p.id===id)),'bladder maps to the female bladder');
  assert.equal(carrySelection(carry(female,'Body of uterus'),male),null,'female-only uterus clears');
  const femur=carrySelection(carry(female,'Left femur'),male);assert.ok(femur,'femur carries back to male');
  console.log('Both bodies: WebMCP body parameter (sync and lazy), and selection carry-over (kept, mapped, cleared) passed.');
}

const tap=new PointerTap();
tap.down(1,10,10,5);assert.equal(tap.up(1,12,11),true);
tap.down(1,10,10,5);tap.move(1,40,10);assert.equal(tap.up(1,10,10),false);
tap.down(1,10,10,12);tap.down(2,20,20,12);assert.equal(tap.up(2,20,20),false);assert.equal(tap.up(1,10,10),false);
tap.down(1,10,10,5);tap.cancel(1);assert.equal(tap.up(1,10,10),false);
tap.down(1,10,10,5);assert.equal(tap.up(1,10,10),true);
assert.equal(createExplosionLayout([]).cells.size,0);
console.log('Tap, drag, multitouch, cancellation, and empty-view checks passed.');
