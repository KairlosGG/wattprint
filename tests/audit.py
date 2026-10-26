"""Auditoría completa de Wattprint.
Uso: python3 -m http.server 8799 (en la raíz) y, en otra terminal:
  OWID_CSV=owid-energy-data.csv WRI_XLSX=apendices-wri.xlsx python3 tests/audit.py
OWID: https://github.com/owid/energy-data · WRI (apéndices 1 a 7): https://www.wri.org/data/dataset-guidance-calculating-water-use-embedded-purchased-electricity
Requiere: pip install playwright openpyxl && playwright install chromium

A. Datos: cada región/país frente a sus fuentes (OWID/Ember, WRI apéndices 1 y 2, tabla 4).
B. Fórmulas: implementación de referencia en Python frente a compute() en una rejilla exhaustiva
   (todas las regiones, GPU, centros, modos, servidor, palancas, duraciones, vida útil, %).
C. Interfaz: lo que se ve (cifras, desglose, equivalencias, por petición/año, mapa, palancas) frente a compute().
D. Enlace compartible: ida y vuelta del estado.
E. Exportaciones: CSV frente a compute().
F. Entradas extremas o inválidas.
"""
import csv, json, math, random, itertools, sys, re, io
import openpyxl
from playwright.sync_api import sync_playwright

import os
BASE = os.environ.get('WP_URL', 'http://localhost:8799/')
OWID_CSV = os.environ.get('OWID_CSV', '/tmp/owid/owid.csv')
WRI_XLSX = os.environ.get('WRI_XLSX', '/tmp/wri/a.xlsx')
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
random.seed(7)
FAIL = []
def fail(msg):
    FAIL.append(msg)
    if len(FAIL) <= 40: print('  FAIL', msg)

# ---------- fuentes ----------
owid = {}
with open(OWID_CSV, newline='') as f:
    for r in csv.DictReader(f):
        v = r['carbon_intensity_elec']
        if not v: continue
        y = int(r['year'])
        for key in (r['iso_code'] or None, 'NAME:' + r['country']):
            if key and (key not in owid or y > owid[key][1]): owid[key] = (float(v), y)
wb = openpyxl.load_workbook(WRI_XLSX, data_only=True, read_only=True)
rows = list(wb['Appendix 1 & 2'].iter_rows(min_row=3, values_only=True))
wri_country = {r[4]: r[6] for r in rows if r[4]}
wri_sub = {r[0]: r[2] for r in rows if r[0]}
LPG = 3.785
last_update = json.load(open(os.path.join(ROOT, 'data', 'last-update.json')))

CURATED_OWID = {'world':'World','no':'Norway','se':'Sweden','fr':'France','es':'Spain','eu':'European Union (27)','uk':'United Kingdom',
                'ie':'Ireland','us':'United States','de':'Germany','sg':'Singapore','jp':'Japan','cn':'China','in':'India','pl':'Poland'}
CURATED_WRI = {'no':'Norway','se':'Sweden','fr':'France','es':'Spain','uk':'Great Britain','ie':'Ireland','de':'Germany','us':'United States',
               'jp':'Japan','cn':'China','pl':'Poland','in':'India'}
CURATED_SUB = {'use':'SRVC (SERC Virginia/Carolina)','usw':'NWPP (WECC Northwest)'}
WORLD_W = round(1.27 * LPG, 2)

# ---------- modelo de referencia (escrito a partir de la metodología, no del código) ----------
HOST = 1.41; EMB = 150 + 2500 / 8; PUE = {'hyper': (1.09 + 1.17) / 2, 'avg': 1.54}; WUE = {'hyper': 0.27, 'avg': 0.36}
GPU_W = {'h100': 700, 'h100p': 350, 'a100': 400, 'v100': 300, 't4': 70, 'avg': 400}
def sched_default(h):  # Dodge et al. 2022
    return 26.4 if h <= 1 else 14.5 if h <= 6 else 11.0
def ref(s, R, NO):
    I, ew, pue, wue = R['g'], R['w'], PUE[s['dc']], WUE[s['dc']]
    em = im = 1.0
    for lv in s['levers']:
        if lv == 'own': em *= 1 - min(90, max(0, s['own'])) / 100
        if lv == 'sched': im *= 1 - (min(90, max(0, s['schedPct'])) if s['schedPct'] is not None else sched_default(s['hours'])) / 100
        if lv == 'region' and NO['g'] < I: I, ew = NO['g'], NO['w']
        if lv == 'hyper': pue, wue = min(pue, PUE['hyper']), min(wue, WUE['hyper'])
    extra = HOST - 1 if s['host'] else 0
    it0 = s['meas'] * (1 + extra) if s['mode'] == 'meas' else GPU_W[s['gpu']] * s['units'] * s['hours'] * (s['util'] + extra) / 1000
    it = it0 * em; kwh = it * pue; op = kwh * I * im / 1000
    emb = EMB * s['units'] * s['hours'] / (s['life'] * 365 * 24)
    return {'kwhIT': it, 'kwh': kwh, 'operational': op, 'embodied': emb, 'co2': op + emb,
            'waterOn': it * wue, 'waterOff': kwh * ew, 'water': it * wue + kwh * ew}
def close(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
    ctx.add_init_script("localStorage.setItem('wp_tour','1')")
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
    pg.goto(BASE); pg.wait_for_load_state('networkidle')

    # ===== A. Datos =====
    print('A. Datos frente a fuentes')
    data = pg.evaluate("()=>({all:ALL.map(r=>({id:r[0],g:r[3],y:+r[4],ap:r[5],w:r[6],wap:r[7]})), countries:DATA.COUNTRIES, wri:DATA.WRI_GAL, cloud:[...CLOUD_IDS], updated:DATA.UPDATED})")
    regs = {r['id']: r for r in data['all']}
    nA = 0
    for a2, a3, g, y in data['countries']:
        nA += 1
        src = owid.get(a3)
        if not src: fail(f'A {a3}: no está en OWID'); continue
        if math.floor(src[0]+0.5) != g or src[1] != int(y): fail(f'A carbono {a3}: herramienta {g} ({y}) / OWID {src[0]:.2f} ({src[1]})')
        r = regs[a2.lower()]
        if a2 in data['wri']:
            exp = round(data['wri'][a2] * LPG, 2)
            if r['w'] != exp or r['wap']: fail(f'A agua {a2}: {r["w"]} ap={r["wap"]} / WRI {exp}')
        else:
            if r['w'] != WORLD_W or not r['wap']: fail(f'A agua {a2}: {r["w"]} ap={r["wap"]} / media mundial {WORLD_W}')
    # tabla WRI embebida = Excel
    name2a2 = {'Argentina':'AR','Australia':'AU','Austria':'AT','Belgium':'BE','Brazil':'BR','Bulgaria':'BG','Canada':'CA','Chile':'CL','China':'CN','Cyprus':'CY','Czech Republic':'CZ','Denmark':'DK','Estonia':'EE','Finland':'FI','France':'FR','Germany':'DE','Great Britain':'GB','Greece':'GR','Hungary':'HU','Iceland':'IS','India':'IN','Indonesia':'ID','Ireland':'IE','Italy':'IT','Japan':'JP','Latvia':'LV','Lithuania':'LT','Luxembourg':'LU','Malaysia':'MY','Malta':'MT','Mexico':'MX','Netherlands':'NL','New Zealand':'NZ','Norway':'NO','Poland':'PL','Portugal':'PT','Romania':'RO','Russia':'RU','Slovakia':'SK','Slovenia':'SI','South Korea':'KR','Spain':'ES','Sweden':'SE','Switzerland':'CH','Taiwan':'TW','Thailand':'TH','Turkey':'TR','Ukraine':'UA','United States':'US'}
    for n, gal in wri_country.items():
        if round(gal, 4) != data['wri'].get(name2a2[n]): fail(f'A tabla WRI {n}: {data["wri"].get(name2a2[n])} / Excel {gal:.4f}')
    if len(data['wri']) != len(wri_country): fail('A tabla WRI: número de países distinto')
    # lista principal
    for rid in data['cloud']:
        r = regs[rid]; nA += 1
        if rid in CURATED_OWID:
            src = owid['NAME:' + CURATED_OWID[rid]]
            if math.floor(src[0]+0.5) != r['g'] or src[1] != r['y']: fail(f'A carbono {rid}: {r["g"]} ({r["y"]}) / OWID {src[0]:.2f} ({src[1]})')
        else:
            v = last_update.get('values', {}).get(rid)
            if not v or v['gco2e_kwh'] != r['g'] or v['year'] != r['y']: fail(f'A carbono {rid}: {r["g"]} / Ember US (acción) {v}')
        if rid in CURATED_WRI: exp, ap = round(wri_country[CURATED_WRI[rid]] * LPG, 2), False
        elif rid in CURATED_SUB: exp, ap = round(wri_sub[CURATED_SUB[rid]] * LPG, 2), rid == 'usw'
        else: exp, ap = WORLD_W, rid != 'world'  # la media mundial ES el dato de la tabla 4; UE y Singapur la usan como aproximación
        if r['w'] != exp or r['wap'] != ap: fail(f'A agua {rid}: {r["w"]} ap={r["wap"]} / esperado {exp} ap={ap}')
    print(f'  {nA} regiones comprobadas; tabla WRI de {len(wri_country)} países; fallos hasta ahora: {len(FAIL)}')

    # ===== B. Fórmulas: rejilla exhaustiva =====
    print('B. Fórmulas (referencia Python frente a compute)')
    LEVERS = ['region', 'hyper', 'sched', 'own']
    lever_sets = [list(c) for k in range(5) for c in itertools.combinations(LEVERS, k)]
    region_ids = list(regs)
    scen = []
    for gpu, dc, mode, host, hours, life in itertools.product(GPU_W, ['hyper', 'avg'], ['est', 'meas'], [True, False], [1, 2, 6, 7, 72, 720], [4, 5, 6]):
        for lv in lever_sets:
            scen.append(dict(gpu=gpu, dc=dc, mode=mode, host=host, hours=hours, life=life, levers=lv, region=random.choice(region_ids),
                             units=random.choice([1, 2, 3, 8, 16, 64, 4096]), util=random.choice([0.1, 0.35, 0.5, 0.93, 1.0]),
                             meas=random.choice([0, 0.5, 50, 12345.6]), own=random.choice([0, 5, 20, 90, 150, -5]),
                             schedPct=random.choice([None, None, 0, 11, 90, 120])))
    for rid in region_ids:  # cada región con todas las combinaciones de palancas
        for lv in lever_sets:
            scen.append(dict(gpu='h100', dc=random.choice(['hyper', 'avg']), mode='est', host=True, hours=72, life=6, levers=lv, region=rid,
                             units=2, util=1.0, meas=0, own=20, schedPct=None))
    print(f'  {len(scen)} escenarios')
    js = """(list)=>{ const out=[]; const keep=JSON.parse(JSON.stringify({...state,active:[...state.active]}));
      for(const s of list){ state.gpu=s.gpu; state.watts=gpuRow(s.gpu)[2]; state.dc=s.dc; state.pue=DC[s.dc].pue; state.wue=DC[s.dc].wue;
        state.mode=s.mode; state.host=s.host; state.hours=s.hours; state.life=s.life; state.region=s.region; state.units=s.units;
        state.util=s.util; state.measKwh=s.meas; state.ownPct=s.own; state.schedPct=s.schedPct; state.active=new Set(s.levers);
        const b=compute(), o=compute({optimized:true}); out.push([b,o]); }
      Object.assign(state,keep); state.active=new Set(keep.active); return out; }"""
    NO = regs['no']; nB = 0
    for i in range(0, len(scen), 4000):
        chunk = scen[i:i + 4000]
        res = pg.evaluate(js, chunk)
        for s, (b, o) in zip(chunk, res):
            R = regs[s['region']]
            rb = ref({**s, 'levers': []}, R, NO); ro = ref(s, R, NO)
            for k in rb:
                nB += 2
                if not close(b[k], rb[k]): fail(f'B base {k} {s} herramienta {b[k]} ref {rb[k]}')
                if not close(o[k], ro[k]): fail(f'B opt {k} {s} herramienta {o[k]} ref {ro[k]}')
            for v in list(b.values()) + list(o.values()):
                if isinstance(v, (int, float)) and (math.isnan(v) or math.isinf(v) or v < 0): fail(f'B valor no válido {v} en {s}')
    print(f'  {nB} comparaciones; fallos hasta ahora: {len(FAIL)}')

    # ===== C. Interfaz =====
    print('C. Lo que se ve frente a compute()')
    pyfmt = """(n)=>fmt(n)"""
    ui_cases = random.sample(scen, 60) + [dict(s, wl=w, reqs=q, reps=y) for s in random.sample(scen, 6) for w in ['train','ft','inf','exp'] for q, y in [(0, 1), (250000, 12)]] + [dict(gpu='a100', dc='hyper', mode='est', host=True, hours=720, life=6, levers=[], region='world', units=2,
                                              util=1.0, meas=0, own=0, schedPct=None, reqs=1000000, reps=12)]
    nC = 0
    for s in ui_cases:
        cfg = {'w': s.get('wl') or ('inf' if s.get('reqs') else 'train'), 'g': s['gpu'], 'd': s['dc'], 'm': s['mode'], 'k': s['meas'], 'sv': '1' if s['host'] else '0',
               'u': s['units'], 'h': s['hours'], 'l': s['life'], 'r': s['region'], 'ut': round(s['util'] * 100), 'oe': s['own'],
               'cs': s['schedPct'], 'c': s['levers'], 'q': s.get('reqs', 0), 'y': s.get('reps', 1)}
        pg.evaluate("cfg=>applyConfig(cfg)", cfg); pg.wait_for_timeout(800)
        got = pg.evaluate("""()=>{ const R=compute({optimized:true}), B=compute();
          const txt=id=>document.getElementById(id).textContent.trim();
          return {R,B, v:[txt('vCO2'),txt('vKWH'),txt('vH2O')], f:[fmt(R.co2*dScale()),fmt(R.kwh*dScale()),fmt(R.water*dScale())], u:[txt('uCO2'),txt('uKWH'),txt('uH2O')], pr:perReqMode(),
                  eq:[txt('eCO2'),txt('eKWH'),txt('eH2O')], eqf:[fmt(R.co2*1000/DATA.EQ.car),fmt(R.kwh/DATA.EQ.phone),fmt(R.water/DATA.EQ.waterDay)],
                  st:[txt('lCO2'),txt('lKWH'),txt('lH2O')], was:[txt('wCO2'),txt('wKWH'),txt('wH2O')],
                  wasf:[fmt(B.co2*dScale()),fmt(B.kwh*dScale()),fmt(B.water*dScale())], act:activeLevers(), reqs:state.reqs, reps:state.reps,
                  fx:[...document.querySelectorAll('[data-fx]')].map(e=>[e.dataset.fx,e.textContent.trim()]),
                  sel:document.getElementById('region').value, regionState:state.region }; }""")
        nC += 1
        if got['v'] != got['f']: fail(f'C cifras {got["v"]} / {got["f"]} en {cfg}')
        for e, f in zip(got['eq'], got['eqf']):
            if f not in e: fail(f'C equivalencia "{e}" no contiene {f}')
        if got['sel'] != got['regionState']: fail(f'C desplegable {got["sel"]} / estado {got["regionState"]}')
        changed = got['act'] and any(abs(got['R'][k] - got['B'][k]) / max(got['B'][k], 1e-12) >= 0.005 for k in ['co2'])
        if changed and got['wasf'][0] not in got['was'][0]: fail(f'C "antes" {got["was"][0]} no contiene {got["wasf"][0]}')
        if not got['act'] and any(w and 'kWh medidos' not in w for w in got['was']): fail(f'C muestra "antes" sin opciones activas: {got["was"]}')
        # porcentajes del desglose suman ~100
        for t in got['st']:
            pcs = [int(x) for x in re.findall(r'(\d+)\s?%', t)]
            if pcs and not (98 <= sum(pcs) <= 102): fail(f'C desglose no suma 100: {t}')
        # chips de cada palanca = efecto real
        chk = pg.evaluate("""()=>LEVERS.map(id=>{ if(!leverApplies(id)||(id==='own'&&!(state.ownPct>0))) return [id,null,0];
            const on=state.active.has(id); const a=compute({levers:on?state.active:withLever(id)}), b=compute({levers:on?without(id):state.active});
            return [id, pctTxt(a.co2,b.co2), Math.abs(a.co2-b.co2)/Math.max(b.co2,1e-12)]; })""")
        fx = dict(got['fx'])
        for lid, ptxt, d in chk:
            if ptxt is None: continue
            if d >= 0.005 and ptxt not in fx[lid]: fail(f'C chip {lid} "{fx[lid]}" no contiene {ptxt}')
        # por petición y año
        if got['reqs'] > 0 and got['pr']:
            want = pg.evaluate("()=>[gOrKg(compute({optimized:true}).co2*1000), fmt(compute({optimized:true}).co2*1e6/state.reqs)]")
            if want[0] not in got['eq'][0]: fail(f'C total en modo por petición: "{got["eq"][0]}" no contiene {want[0]}')
            if got['v'][0] != want[1] or got['u'][0] != 'g': fail(f'C cifra por 1.000 peticiones: {got["v"][0]} {got["u"][0]} / {want[1]} g')
        if got['reps'] > 1:
            want = pg.evaluate("()=>gOrKg(compute({optimized:true}).co2*state.reps*1000)")
            if want not in got['eq'][0]: fail(f'C al año: "{got["eq"][0]}" no contiene {want}')
    # mapa: valor de cada región = misma tarea en esa red (sin la palanca de región)
    pg.evaluate("cfg=>applyConfig(cfg)", {'w': 'train', 'g': 'h100', 'd': 'avg', 'u': 2, 'h': 72, 'l': 6, 'r': 'pl', 'c': ['region', 'hyper']}); pg.wait_for_timeout(400)
    mm = pg.evaluate("""()=>ALL.filter(r=>{ const a=regionVals[r[0]], b=compute({region:r[0],levers:without('region')}); return Math.abs(a.co2-b.co2)>1e-12||Math.abs(a.water-b.water)>1e-12; }).map(r=>r[0])""")
    if mm: fail(f'C mapa: valores distintos en {mm[:10]}')
    # energía: las partes suman el total
    pg.click('[data-metric="kwh"]'); pg.wait_for_timeout(300)
    parts = pg.evaluate("()=>[...document.querySelectorAll('.mixl li b')].map(b=>b.textContent)")
    tot = pg.evaluate("()=>compute({optimized:true}).kwh")
    s_parts = sum(float(x.replace('.', '').replace(',', '.').replace(' kWh', '')) for x in parts)
    if abs(s_parts - tot) > 0.15 * len(parts): fail(f'C energía: partes {parts} no suman {tot}')
    pg.click('[data-metric="co2"]')
    print(f'  {nC} pantallas comprobadas; fallos hasta ahora: {len(FAIL)}')

    # ===== D. Enlace =====
    print('D. Enlace compartible (ida y vuelta)')
    nD = 0
    for s in random.sample(scen, 40):
        cfg = {'w': 'ft', 'g': s['gpu'], 'd': s['dc'], 'm': s['mode'], 'k': s['meas'], 'sv': '1' if s['host'] else '0', 'u': s['units'], 'h': s['hours'],
               'l': s['life'], 'r': s['region'], 'ut': round(s['util'] * 100), 'oe': s['own'], 'cs': s['schedPct'], 'c': s['levers'], 'q': 0, 'y': 3, 'mt': 'h2o'}
        pg.evaluate("cfg=>applyConfig(cfg)", cfg)
        a = pg.evaluate("()=>({q:shareParams().toString(), b:compute(), o:compute({optimized:true})})")
        p2 = ctx.new_page(); p2.goto(BASE + '?' + a['q']); p2.wait_for_load_state('networkidle')
        b = p2.evaluate("()=>({q:shareParams().toString(), b:compute(), o:compute({optimized:true})})"); p2.close()
        nD += 1
        if a['q'] != b['q']: fail(f'D parámetros distintos: {a["q"]} / {b["q"]}')
        for k in a['o']:
            if not close(a['o'][k], b['o'][k]) or not close(a['b'][k], b['b'][k]): fail(f'D {k} distinto tras recargar {a["q"]}')
    print(f'  {nD} enlaces; fallos hasta ahora: {len(FAIL)}')

    # ===== E. CSV =====
    print('E. CSV frente a compute()')
    for s in random.sample(scen, 8):
        cfg = {'w': 'train', 'g': s['gpu'], 'd': s['dc'], 'm': s['mode'], 'k': s['meas'], 'sv': '1' if s['host'] else '0', 'u': s['units'], 'h': s['hours'],
               'l': s['life'], 'r': s['region'], 'ut': round(s['util'] * 100), 'oe': s['own'], 'cs': s['schedPct'], 'c': s['levers']}
        pg.evaluate("cfg=>applyConfig(cfg)", cfg)
        exp = pg.evaluate("()=>{ const b=compute(), o=compute({optimized:true}); return {b:resultRows(b).map(r=>r[1]), o:resultRows(o).map(r=>r[1]), has:activeLevers().length>0}; }")
        pg.click('#btnShare')
        with pg.expect_download() as d: pg.click('#sCsv')
        pg.keyboard.press('Escape')
        text = open(d.value.path(), encoding='utf-8-sig').read()
        lines = [l for l in text.splitlines() if l]
        hdr = [i for i, l in enumerate(lines) if l.startswith('"Concepto";"Antes"')]
        if not hdr: print(lines[:14]); raise SystemExit(2)
        hdr = hdr[0]
        for j, l in enumerate(lines[hdr + 1: hdr + 10]):
            cells = l.split(';')
            vb = float(cells[1].replace(',', '.'))
            if abs(vb - exp['b'][j]) > 0.5e-4 + 1e-9: fail(f'E CSV fila {j}: {vb} / {exp["b"][j]}')
            if exp['has']:
                vo = float(cells[2].replace(',', '.'))
                if abs(vo - exp['o'][j]) > 0.5e-4 + 1e-9: fail(f'E CSV opt fila {j}: {vo} / {exp["o"][j]}')
    print(f'  fallos hasta ahora: {len(FAIL)}')

    # ===== F. Entradas extremas =====
    print('F. Entradas extremas o inválidas')
    bad = ['u=-5&h=99999&r=xx&ut=0&oe=200&cs=abc&l=9&d=zz&g=nope&w=zz', 'u=0&h=0', 'm=meas&k=-3', 'm=meas&k=abc', 'h=1.5&u=2.7',
           'q=-10&y=0', 'c=region.region.foo', 'r=__proto__', 'r=constructor', 'lang=xx&h=24']
    for q in bad:
        pg.goto(BASE + '?' + q); pg.wait_for_load_state('networkidle')
        st = pg.evaluate("()=>{ const b=compute(), o=compute({optimized:true}); return {s:{u:state.units,h:state.hours,r:state.region,util:state.util,own:state.ownPct,cs:state.schedPct,life:state.life,dc:state.dc,gpu:state.gpu,meas:state.measKwh,reqs:state.reqs,reps:state.reps}, ok:[...Object.values(b),...Object.values(o)].every(v=>Number.isFinite(v)&&v>=0), v:document.getElementById('vCO2').textContent}; }")
        s = st['s']
        if not st['ok'] or st['v'] in ('NaN', '—', ''): fail(f'F {q}: valores no válidos {st}')
        if not (1 <= s['u'] <= 4096 and 1 <= s['h'] <= 720 and 0.1 <= s['util'] <= 1 and 0 <= s['own'] <= 90 and s['life'] in (4, 5, 6)
                and s['dc'] in ('hyper', 'avg') and s['gpu'] in GPU_W and s['meas'] >= 0 and s['reqs'] >= 0 and s['reps'] >= 1
                and (s['cs'] is None or 0 <= s['cs'] <= 90) and s['r'] in regs): fail(f'F {q}: estado fuera de rango {s}')
    print(f'  {len(bad)} casos')

    if errs: fail(f'errores de la página: {errs[:5]}')
    br.close()

print('\nRESULTADO:', 'SIN FALLOS' if not FAIL else f'{len(FAIL)} FALLOS')
sys.exit(1 if FAIL else 0)
