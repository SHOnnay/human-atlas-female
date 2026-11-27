// Milestone 10: simplify one mesh exactly as scripts/optimize-anatomy.mjs does for a female part
// (same target count and 0.2 % error bound), so the build can know the PACKAGED skin surface.
// Usage: node simplify_like_package.mjs in.bin out.bin
//   in.bin:  uint32 vertexCount, uint32 indexCount, float32 positions[vc*3], uint32 indices[ic]
//   out.bin: same layout, simplified and compacted.
import fs from 'node:fs';
import {MeshoptSimplifier} from 'meshoptimizer';
await MeshoptSimplifier.ready;
const b = fs.readFileSync(process.argv[2]);
const vc = b.readUInt32LE(0), ic = b.readUInt32LE(4);
const pos = new Float32Array(b.buffer.slice(b.byteOffset + 8, b.byteOffset + 8 + vc * 12));
const idx = new Uint32Array(b.buffer.slice(b.byteOffset + 8 + vc * 12, b.byteOffset + 8 + vc * 12 + ic * 4));
const target = Math.max(96, Math.floor(ic * .22 / 3) * 3);
const [simplified] = MeshoptSimplifier.simplify(idx, pos, 3, Math.min(idx.length, target), .002);
const [remap, count] = MeshoptSimplifier.compactMesh(simplified);
const out = new Float32Array(count * 3);
for (let old = 0; old < remap.length; old++) { const n = remap[old]; if (n === 0xffffffff) continue; out.set(pos.subarray(old * 3, old * 3 + 3), n * 3); }
const head = Buffer.alloc(8); head.writeUInt32LE(count, 0); head.writeUInt32LE(simplified.length, 4);
fs.writeFileSync(process.argv[3], Buffer.concat([head, Buffer.from(out.buffer), Buffer.from(simplified.buffer, simplified.byteOffset, simplified.byteLength)]));
