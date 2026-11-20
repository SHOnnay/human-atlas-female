import type {Atlas,Body,Concept} from './anatomy';
type Tool={name:string;description:string;inputSchema:object;annotations:{readOnlyHint:boolean};execute:(input:unknown)=>unknown};
/** Supplies the catalogue for either reference body; `get` returns it only when already loaded. */
export interface AtlasProvider {body:Body;get(body:Body):Atlas|undefined;load(body:Body):Promise<Atlas>}
function record(input:unknown):Record<string,unknown>{if(!input||typeof input!=='object'||Array.isArray(input))throw new Error('Expected an object.');return input as Record<string,unknown>;}
function provider(source:Atlas|AtlasProvider):AtlasProvider{
 if('get' in source)return source;
 const body:Body=source.sex??'male';
 return {body,get:b=>b===body?source:undefined,load:b=>b===body?Promise.resolve(source):Promise.reject(new Error(`The ${b} model is not available here.`))};
}
function bodyOf(data:Record<string,unknown>,fallback:Body):Body{
 if(data.body===undefined)return fallback;
 if(data.body!=='male'&&data.body!=='female')throw new Error('body must be "male" or "female".');
 return data.body;
}
/** Run `fn` with the requested body's atlas: synchronously when loaded, otherwise after loading it. */
function withAtlas<T>(p:AtlasProvider,body:Body,fn:(atlas:Atlas)=>T):T|Promise<T>{const a=p.get(body);return a?fn(a):p.load(body).then(fn);}
const bodyProperty={type:'string',enum:['male','female'],description:'Reference body to use. Defaults to the body currently shown.'};
export function atlasTools(source:Atlas|AtlasProvider,inspect:(concept:Concept,body:Body)=>void):Tool[]{const p=provider(source);return [
 {name:'find_anatomy',description:'Find anatomical structures by name or source atlas identifier in the male or female atlas.',inputSchema:{type:'object',properties:{query:{type:'string',minLength:1},body:bodyProperty},required:['query'],additionalProperties:false},annotations:{readOnlyHint:true},execute(input){const data=record(input);if(typeof data.query!=='string'||!data.query.trim())throw new Error('A nonempty query is required.');const q=data.query.toLowerCase().trim(),body=bodyOf(data,p.body);return withAtlas(p,body,atlas=>atlas.concepts.filter(c=>c.name.toLowerCase().includes(q)||c.id.toLowerCase().includes(q)).slice(0,30).map(c=>({id:c.id,name:c.name,pieces:c.elements.length,body})));}},
 {name:'inspect_anatomical_structure',description:'Select an atlas concept in the 3D anatomy and open its visible detail panel. Passing a different body switches the viewer to it.',inputSchema:{type:'object',properties:{id:{type:'string'},body:bodyProperty},required:['id'],additionalProperties:false},annotations:{readOnlyHint:false},execute(input){const data=record(input);if(typeof data.id!=='string')throw new Error('An atlas identifier is required.');const body=bodyOf(data,p.body);return withAtlas(p,body,atlas=>{const concept=atlas.concepts.find(c=>c.id===data.id);if(!concept)throw new Error('That structure is not present in this atlas.');inspect(concept,body);return {id:concept.id,name:concept.name,selectedPieces:concept.elements.length,body};});}}
 ];}
export function registerAtlasTools(source:Atlas|AtlasProvider,inspect:(concept:Concept,body:Body)=>void){
 const context=(document as Document&{modelContext?:{registerTool:(tool:Tool,options:{signal:AbortSignal})=>void|Promise<void>}}).modelContext;
 if(!context?.registerTool)return;const lifecycle=new AbortController();
 for(const tool of atlasTools(source,inspect)){try{void Promise.resolve(context.registerTool(tool,{signal:lifecycle.signal})).catch(()=>{});}catch{/* Optional browser capability; the visible UI remains available. */}}
 return()=>lifecycle.abort();
}
