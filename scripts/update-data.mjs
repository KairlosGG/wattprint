// Actualiza la intensidad de carbono de la red en index.html con los últimos datos de Ember.
// - Países: Ember (Yearly Electricity Data), republicado por Our World in Data en
//   github.com/owid/energy-data (columna carbon_intensity_elec, gCO2e/kWh, ciclo de vida).
// - Estados de EE. UU. (Virginia, Oregón): Ember US Electricity Data (CSV público).
// Si una fuente falla o un valor no es plausible, se conserva el valor anterior.
// Uso: node scripts/update-data.mjs
import { readFile, writeFile, mkdir } from 'node:fs/promises';
const REPORT = { checked_at: new Date().toISOString(), sources: {} };

const FILE = new URL('../index.html', import.meta.url);
const OWID = 'https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv';
const EMBER_US = 'https://storage.googleapis.com/emb-prod-bkt-publicdata/public-downloads/generation/outputs/release_us_subnational_generation_yearly.csv';

// id, nombre ES, nombre EN, fuente, intensidad aproximada?, L/kWh agua de generación (WRI 2020), agua aproximada?
const SPEC = [
  ['world', 'Media mundial',           'World average',      {owid:'World'},               false, 4.81, false],
  ['no',    'Noruega',                 'Norway',             {owid:'Norway'},              false, 6.66, false],
  ['se',    'Suecia',                  'Sweden',             {owid:'Sweden'},              false, 6.02, false],
  ['fr',    'Francia',                 'France',             {owid:'France'},              false, 3.67, false],
  ['usw',   'EE. UU. Oeste (Oregón)',  'US West (Oregon)',   {us:'Oregon'},                true,  9.50, true ],
  ['es',    'España',                  'Spain',              {owid:'Spain'},               false, 6.21, false],
  ['eu',    'Media UE',                'EU average',         {owid:'European Union (27)'}, false, 4.81, true ],
  ['uk',    'Reino Unido',             'United Kingdom',     {owid:'United Kingdom'},      false, 2.35, false],
  ['ie',    'Irlanda',                 'Ireland',            {owid:'Ireland'},             false, 1.48, false],
  ['us',    'EE. UU. (media)',         'United States (average)', {owid:'United States'},  false, 3.14, false],
  ['use',   'EE. UU. Este (Virginia)', 'US East (Virginia)', {us:'Virginia'},              true,  2.38, false],
  ['de',    'Alemania',                'Germany',            {owid:'Germany'},             false, 1.93, false],
  ['sg',    'Singapur',                'Singapore',          {owid:'Singapore'},           false, 4.81, true ],
  ['jp',    'Japón',                   'Japan',              {owid:'Japan'},               false, 2.31, false],
  ['cn',    'China',                   'China',              {owid:'China'},               false, 6.02, false],
  ['in',    'India',                   'India',              {owid:'India'},               false, 3.44, false],
  ['pl',    'Polonia',                 'Poland',             {owid:'Poland'},              false, 2.50, false],
];

const START = '/*REGIONS:START*/', END = '/*REGIONS:END*/';

function parseCSV(text){
  const rows=[]; let row=[], cur='', q=false;
  for(let i=0;i<text.length;i++){
    const c=text[i];
    if(q){ if(c==='"'){ if(text[i+1]==='"'){cur+='"';i++;} else q=false; } else cur+=c; }
    else if(c==='"') q=true;
    else if(c===','){ row.push(cur); cur=''; }
    else if(c==='\n'){ row.push(cur.replace(/\r$/,'')); rows.push(row); row=[]; cur=''; }
    else cur+=c;
  }
  if(cur||row.length){ row.push(cur); rows.push(row); }
  return rows;
}
const plausible = v => Number.isFinite(v) && v > 0 && v < 1500;

async function get(url){
  const r = await fetch(url); if(!r.ok) throw new Error(`${r.status} ${url}`); return r.text();
}

async function fromOWID(){
  const rows=parseCSV(await get(OWID)); const h=rows[0];
  const ic=h.indexOf('country'), iy=h.indexOf('year'), iv=h.indexOf('carbon_intensity_elec');
  if(ic<0||iy<0||iv<0) throw new Error('OWID: columnas no encontradas');
  REPORT.sources.owid={ url:OWID, rows:rows.length-1 };
  const out={};
  for(const r of rows.slice(1)){
    const v=parseFloat(r[iv]), y=+r[iy];
    if(!plausible(v)) continue;
    if(!out[r[ic]] || y>out[r[ic]].year) out[r[ic]]={value:v, year:y};
  }
  return out;
}

async function fromEmberUS(){
  // Formato ancho: una fila por estado, año y fuente; columna "Emissions intensity (gCO2e/kWh)".
  const rows=parseCSV(await get(EMBER_US)); const H=rows[0], h=H.map(x=>x.toLowerCase().trim());
  const col=name=>h.indexOf(name);
  const is=col('state'), iy=col('year'), isrc=col('electricity source'), iagg=col('is aggregated source'),
        iint=h.findIndex(x=>x.startsWith('emissions intensity')), igen=h.findIndex(x=>x.startsWith('generation (twh)')),
        iem=h.findIndex(x=>x.startsWith('emissions (mtco2e)'));
  REPORT.sources.ember_us={ url:EMBER_US, rows:rows.length-1, header:H };
  if([is,iy,isrc].some(i=>i<0) || (iint<0 && (igen<0||iem<0))) throw new Error('Ember US: columnas no encontradas: '+H.join('|'));
  const srcs=new Set(), total={}, sums={};
  for(const r of rows.slice(1)){
    const st=r[is], y=+r[iy], src=(r[isrc]||'').trim(); if(!st||!y) continue; srcs.add(src);
    const k=st+'|'+y;
    if(/^total/i.test(src) && iint>=0){ const v=parseFloat(r[iint]); if(plausible(v)) total[k]=v; }
    const agg = iagg>=0 ? /true|yes|1/i.test(r[iagg]||'') : false;
    if(!agg && igen>=0 && iem>=0){ const g=parseFloat(r[igen]), e=parseFloat(r[iem]);
      if(Number.isFinite(g)&&Number.isFinite(e)){ sums[k]??={g:0,e:0}; sums[k].g+=g; sums[k].e+=e; } }
  }
  REPORT.sources.ember_us.sources_seen=[...srcs].slice(0,30);
  const out={};
  const keys=new Set([...Object.keys(total),...Object.keys(sums)]);
  for(const k of keys){
    const [st,y]=k.split('|'); let v=total[k], how='total';
    if(!plausible(v) && sums[k]?.g>0){ v=sums[k].e/sums[k].g*1000; how='emisiones/generación'; }
    if(!plausible(v)) continue;
    if(!out[st] || +y>out[st].year) out[st]={value:v, year:+y, how};
  }
  REPORT.sources.ember_us.method={ Virginia:out.Virginia?.how, Oregon:out.Oregon?.how };
  return out;
}

const html = await readFile(FILE,'utf8');
const a=html.indexOf(START), b=html.indexOf(END);
if(a<0||b<0) throw new Error('Marcadores no encontrados');
const prev={};
for(const m of html.slice(a,b).matchAll(/\['(\w+)',\s*'[^']*',\s*'[^']*',\s*([\d.]+),\s*'(\d{4})'/g)) prev[m[1]]={value:+m[2], year:+m[3]};

let owid={}, us={};
try{ owid=await fromOWID(); }catch(e){ console.warn('⚠️', e.message); REPORT.sources.owid={...REPORT.sources.owid, error:e.message}; }
try{ us=await fromEmberUS(); REPORT.sources.ember_us.states_found=Object.keys(us).length; }catch(e){ console.warn('⚠️', e.message); REPORT.sources.ember_us={...REPORT.sources.ember_us, error:e.message}; }

const changes=[];
const regions=SPEC.map(([id,es,en,src,ap,w,wap])=>{
  const got = src.owid ? owid[src.owid] : us[src.us];
  const p = prev[id];
  const use = got && (!p || got.year>=p.year) ? got : p;
  if(!use) throw new Error(`Sin dato para ${id}`);
  const val=Math.round(use.value);
  if(!p || p.value!==val || p.year!==use.year) changes.push(`${id}: ${p?`${p.value} (${p.year})`:'—'} → ${val} (${use.year})`);
  return {id,es,en,val,year:use.year,ap,w,wap};
});
const world=regions.shift(); regions.sort((x,y)=>x.val-y.val); regions.unshift(world);
const q=s=>`'${s.replace(/'/g,"\\'")}',`;
const lines=regions.map(r=>`    [${q(r.id).padEnd(9)} ${q(r.es).padEnd(28)} ${q(r.en).padEnd(28)} ${String(r.val).padStart(4)}, '${r.year}', ${String(r.ap).padEnd(5)}, ${r.w.toFixed(2)}, ${String(r.wap).padEnd(5)}],`);
const today=new Date().toISOString().slice(0,10);
let out = html.slice(0,a+START.length)+'\n'+lines.join('\n')+'\n  '+html.slice(b);
if(changes.length) out = out.replace(/UPDATED: '\d{4}-\d{2}-\d{2}'/, `UPDATED: '${today}'`);
REPORT.changes=changes;
REPORT.values=Object.fromEntries(regions.map(r=>[r.id,{gco2e_kwh:r.val,year:r.year}]));
await mkdir(new URL('../data/', import.meta.url),{recursive:true});
await writeFile(new URL('../data/last-update.json', import.meta.url), JSON.stringify(REPORT,null,2)+'\n');
if(out!==html){ await writeFile(FILE,out); console.log('Actualizado:\n'+changes.join('\n')); }
else console.log('Sin cambios.');
