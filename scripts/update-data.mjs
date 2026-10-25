// Actualiza la intensidad de carbono de la red en index.html con los últimos datos de Ember.
// - Países: Ember (Yearly Electricity Data), republicado por Our World in Data en
//   github.com/owid/energy-data (columna carbon_intensity_elec, gCO2e/kWh, ciclo de vida).
// - Estados de EE. UU. (Virginia, Oregón): Ember US Electricity Data (CSV público).
// Si una fuente falla o un valor no es plausible, se conserva el valor anterior.
// Uso: node scripts/update-data.mjs
import { readFile, writeFile } from 'node:fs/promises';

const FILE = new URL('../index.html', import.meta.url);
const OWID = 'https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv';
const EMBER_US = 'https://storage.googleapis.com/emb-prod-bkt-publicdata/public-downloads/generation/outputs/release_us_subnational_generation_yearly.csv';

// id, nombre ES, nombre EN, fuente, intensidad aproximada?, L/kWh agua de generación (WRI 2020), agua aproximada?
const SPEC = [
  ['world', 'Media mundial',           'World average',      {owid:'World'},               false, 4.81, false],
  ['no',    'Noruega',                 'Norway',             {owid:'Norway'},              false, 6.66, false],
  ['se',    'Suecia',                  'Sweden',             {owid:'Sweden'},              false, 6.02, false],
  ['fr',    'Francia',                 'France',             {owid:'France'},              false, 3.67, false],
  ['usw',   'EE. UU. Oeste (Oregón)',  'US West (Oregon)',   {us:'Oregon'},                true,  9.50, false],
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
  const out={};
  for(const r of rows.slice(1)){
    const v=parseFloat(r[iv]), y=+r[iy];
    if(!plausible(v)) continue;
    if(!out[r[ic]] || y>out[r[ic]].year) out[r[ic]]={value:v, year:y};
  }
  return out;
}

async function fromEmberUS(){
  const rows=parseCSV(await get(EMBER_US)); const h=rows[0].map(x=>x.toLowerCase());
  const find=re=>h.findIndex(x=>re.test(x));
  const is=find(/^state$/)>=0?find(/^state$/):find(/state(?!.*code)/), iy=find(/^year$/),
        ivar=find(/^variable$/), iu=find(/^unit$/), iv=find(/^value$/);
  if([is,iy,ivar,iv].some(i=>i<0)) throw new Error('Ember US: columnas no encontradas: '+rows[0].join('|'));
  const out={};
  for(const r of rows.slice(1)){
    if(!/co2 intensity|emissions intensity|carbon intensity/i.test(r[ivar]||'')) continue;
    if(iu>=0 && !/gco2/i.test(r[iu]||'')) continue;
    const v=parseFloat(r[iv]), y=+r[iy];
    if(!plausible(v)) continue;
    if(!out[r[is]] || y>out[r[is]].year) out[r[is]]={value:v, year:y};
  }
  return out;
}

const html = await readFile(FILE,'utf8');
const a=html.indexOf(START), b=html.indexOf(END);
if(a<0||b<0) throw new Error('Marcadores no encontrados');
const prev={};
for(const m of html.slice(a,b).matchAll(/\['(\w+)',\s*'[^']*',\s*'[^']*',\s*([\d.]+),\s*'(\d{4})'/g)) prev[m[1]]={value:+m[2], year:+m[3]};

let owid={}, us={};
try{ owid=await fromOWID(); }catch(e){ console.warn('⚠️', e.message); }
try{ us=await fromEmberUS(); }catch(e){ console.warn('⚠️', e.message); }

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
if(out!==html){ await writeFile(FILE,out); console.log('Actualizado:\n'+changes.join('\n')); }
else console.log('Sin cambios.');
