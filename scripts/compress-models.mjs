import fs from 'node:fs';
import {gzipSync} from 'node:zlib';
// Gzip every chunk of each packaged body: models/atlas.json (male) and models/female/atlas.json.
// Pass a manifest (e.g. `female/atlas.json`) to compress only that body.
const models=new URL('../public/models/',import.meta.url);
for(const name of process.argv.length>2?process.argv.slice(2):['atlas.json','female/atlas.json']){
 const path=new URL(name,models);if(!fs.existsSync(path))continue;
 const base=new URL('.',path),atlas=JSON.parse(fs.readFileSync(path));
 let bytes=0;
 for(const c of atlas.chunks){const compressed=gzipSync(fs.readFileSync(new URL(c.url.split('/').pop(),base)),{level:9});c.gzip=c.url+'.gz';c.gzipBytes=compressed.length;fs.writeFileSync(new URL(c.gzip.split('/').pop(),base),compressed);bytes+=compressed.length;}
 fs.writeFileSync(path,JSON.stringify(atlas));console.log(`${name}: ${(bytes/1e6).toFixed(1)} MB compressed download`);
}
