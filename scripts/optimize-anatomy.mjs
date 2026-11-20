import fs from 'node:fs';
import path from 'node:path';
import {MeshoptSimplifier} from 'meshoptimizer';
await MeshoptSimplifier.ready;
// Usage: node scripts/optimize-anatomy.mjs [atlas.json | female/atlas.json]
// Chunk files are written next to the manifest: models/body-N.bin or models/female/female-N.bin.
const name=process.argv[2]??'atlas.json',prefix=name.includes('female')?'female':'body';
const dir=new URL('../public/models/'+(path.posix.dirname(name)==='.'?'':path.posix.dirname(name)+'/'),import.meta.url),manifest=JSON.parse(fs.readFileSync(new URL(path.posix.basename(name),dir),'utf8'));
const urlBase='/models/'+(path.posix.dirname(name)==='.'?'':path.posix.dirname(name)+'/');
const originals=manifest.chunks.map(c=>c.url.split('/').pop());
if(manifest.optimized)throw new Error('Already optimized. Re-run the source converter first.');
const source=manifest.chunks.map(c=>fs.readFileSync(new URL(c.url.split('/').pop(),dir)));
let chunks=[],segments=[],bytes=0,triangles=0,maxError=0,copied=0;
const flush=()=>{if(!bytes)return;const url=`${urlBase}${prefix}-${chunks.length}.bin`;fs.writeFileSync(new URL(url.split('/').pop(),dir),Buffer.concat(segments));chunks.push({url,bytes});segments=[];bytes=0;};
const append=a=>{const padding=(4-bytes%4)%4;if(padding){segments.push(Buffer.alloc(padding));bytes+=padding;}const offset=bytes;const b=Buffer.from(a.buffer,a.byteOffset,a.byteLength);segments.push(b);bytes+=b.length;return offset;};
for(const p of manifest.parts){
 const b=source[p.chunk];let pos=new Float32Array(b.buffer,b.byteOffset+p.positions,p.vertexCount*3),normal=new Int16Array(b.buffer,b.byteOffset+p.normals,p.vertexCount*3),indices=new Uint32Array(b.buffer,b.byteOffset+p.indices,p.indexCount);
 if(p.preoptimized){
  // Shared BodyParts3D structures in the female package were already simplified with the same
  // 0.2% bound when the male package was built; simplifying again would compound the error.
  if(bytes>4_000_000)flush();
  p.chunk=chunks.length;p.positions=append(pos);p.normals=append(normal);p.indices=append(indices);triangles+=p.indexCount/3;copied++;delete p.preoptimized;continue;
 }
 // Preserve each named mesh, narrow vessels, and small organs. Bound geometric error to 0.2% of each part's extent.
 const target=Math.max(96,Math.floor(p.indexCount*.22/3)*3);
 const [simplified,error]=MeshoptSimplifier.simplify(indices,pos,3,Math.min(indices.length,target),.002);
 maxError=Math.max(maxError,error);const [remap,count]=MeshoptSimplifier.compactMesh(simplified);
 const positions=new Float32Array(count*3),normals=new Int16Array(count*3);
 for(let old=0;old<remap.length;old++){const n=remap[old];if(n===0xffffffff)continue;positions.set(pos.subarray(old*3,old*3+3),n*3);normals.set(normal.subarray(old*3,old*3+3),n*3);}
 if(bytes>4_000_000)flush();
 p.chunk=chunks.length;p.positions=append(positions);p.normals=append(normals);p.indices=append(simplified);p.vertexCount=count;p.indexCount=simplified.length;triangles+=simplified.length/3;
 // Female package: bounds can shrink slightly after simplification (male output is unchanged).
 if(prefix==='female'){const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];for(let i=0;i<positions.length;i++){const a=i%3;lo[a]=Math.min(lo[a],positions[i]);hi[a]=Math.max(hi[a],positions[i]);}p.bounds=[lo,hi];}
}
flush();manifest.sourceTriangles=manifest.triangles;manifest.triangles=triangles;manifest.chunks=chunks;manifest.optimized={method:'meshoptimizer quadric simplification',maximumRelativeError:.002,preservedMeshes:manifest.parts.length,...(copied?{reusedPreoptimized:copied}:{})};
fs.writeFileSync(new URL(path.posix.basename(name),dir),JSON.stringify(manifest));
// Remove only converter outputs superseded by the optimized chunks.
for(const name of originals)if(!chunks.some(c=>c.url.endsWith('/'+name)))fs.unlinkSync(new URL(name,dir));
console.log(JSON.stringify({parts:manifest.parts.length,triangles,bytes:chunks.reduce((n,c)=>n+c.bytes,0),chunks:chunks.length,maxError,reusedPreoptimized:copied}));
