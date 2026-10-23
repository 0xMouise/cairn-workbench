import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import os from 'node:os';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const modules=path.join(root,'web/node_modules');
const notices=[];
function scan(directory){
 for(const entry of fs.readdirSync(directory,{withFileTypes:true})){
  if(!entry.isDirectory()||entry.name.startsWith('.'))continue;
  const folder=path.join(directory,entry.name);
  if(entry.name.startsWith('@')){scan(folder);continue}
  const manifest=path.join(folder,'package.json');
  if(!fs.existsSync(manifest))continue;
  const meta=JSON.parse(fs.readFileSync(manifest,'utf8'));
  const licenses=fs.readdirSync(folder).filter(name=>/^(licen[cs]e|copying|notice)(\.|$)/i.test(name));
  for(const name of licenses){const file=path.join(folder,name);if(fs.statSync(file).isFile())notices.push(`\n${'='.repeat(72)}\n${meta.name} ${meta.version} (${meta.license||'see below'})\n${'='.repeat(72)}\n${fs.readFileSync(file,'utf8')}`)}
  if(fs.existsSync(path.join(folder,'node_modules')))scan(path.join(folder,'node_modules'));
 }
}
scan(modules);
const cargoLock=fs.readFileSync(path.join(root,'web/src-tauri/Cargo.lock'),'utf8');
const cargoSource=path.join(process.env.CARGO_HOME||path.join(os.homedir(),'.cargo'),'registry/src');
if(fs.existsSync(cargoSource)){
 const registries=fs.readdirSync(cargoSource).map(name=>path.join(cargoSource,name));
 for(const match of cargoLock.matchAll(/\[\[package\]\]\s+name\s*=\s*"([^"]+)"\s+version\s*=\s*"([^"]+)"/g)){
  const [,name,version]=match;
  for(const registry of registries){
   const folder=path.join(registry,`${name}-${version}`);if(!fs.existsSync(folder))continue;
   for(const license of fs.readdirSync(folder).filter(n=>/^(licen[cs]e|copying|notice)([._-]|$)/i.test(n))){
    const file=path.join(folder,license);if(fs.statSync(file).isFile())notices.push(`\n${'='.repeat(72)}\nRust crate ${name} ${version} - ${license}\n${'='.repeat(72)}\n${fs.readFileSync(file,'utf8')}`);
   }
   break;
  }
 }
}
const out=path.join(root,'web/src-tauri/resources/THIRD_PARTY_LICENSES.txt');
fs.mkdirSync(path.dirname(out),{recursive:true});
fs.writeFileSync(out,('Cairn Workbench - JavaScript and Rust dependency licenses\n'+notices.join('\n')).split(/\r?\n/).map(line=>line.trimEnd()).join('\n'));
console.log(`Collected ${notices.length} license/notice files.`);
