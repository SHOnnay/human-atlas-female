import type {Atlas,Concept} from './anatomy';
/** A selection made in one body, described independently of that body's atlas. */
export interface Carry {chosen:Concept;parts:{id:string;conceptId:string}[];isolate:boolean}
/** Map a selection onto another body's atlas. Returns the concept to select, or null when the
 * structure does not exist there. Order: identical part ids (shared BodyParts3D meshes), then the
 * same concept id, then parts carrying that concept id. */
export function carrySelection(from:Carry,atlas:Atlas):Concept|null{
 const ids=new Set(atlas.parts.map(p=>p.id));
 if(from.parts.length&&from.parts.every(p=>ids.has(p.id)))return {...from.chosen,elements:from.parts.map(p=>p.id)};
 const concept=atlas.concepts.find(c=>c.id===from.chosen.id);
 if(concept)return concept;
 const same=atlas.parts.filter(p=>p.conceptId===from.chosen.id);
 if(same.length)return {id:from.chosen.id,name:same.length===1?same[0].name:from.chosen.name,elements:same.map(p=>p.id)};
 return null;
}
