"""Offline lineage explorer and manifest-derived cutover plan."""

import json
from collections import Counter, defaultdict


LAYERS = ['Feeds', 'Loads', 'Staging', 'Core', 'Transforms / Spark', 'Serving', 'Consumers']


def layer(row):
    if row['kind'] == 'feed':
        return 0
    if row['kind'] == 'consumer':
        return 6
    if row['kind'] in ('fastload', 'tpt'):
        return 1
    if '.STG_' in row['name'] or '_STG_' in row['name']:
        return 2
    if row['kind'] == 'table':
        return 3
    return 5 if row['kind'] in ('view', 'macro', 'procedure', 'catalog') else 4


def graph(data, uid):
    inventory = {row['id']: row for row in data['artifacts']}
    nodes = [{**inventory[row['id']], **row} for row in data['objects']]
    nodes += [dict(row, kind='consumer', system='consumer',
                   source='warehouse/teradata/dbql/qrylog.csv' if row['hidden'] else 'consumers/registry.yaml')
              for row in data['consumers']]
    nodes += [dict(id=uid('feed:' + path), name=path, kind='feed', system='feed', source=path)
              for path in data['feeds']]
    nodes += [dict(row, system='external', source='', external=True) for row in data['external_relations']]
    for row in nodes:
        row['layer'] = layer(row)
        if row.get('retire_evidence') and row['system'] != 'spark':
            row['last_read'] = row['retire_evidence']['last_read']
    return {'nodes': nodes, 'links': [[uid(a) if a.startswith('feed:') else a, b]
                                    for a, b in data['links']], 'layers': LAYERS}


def lineage_html(data, uid):
    payload = json.dumps(graph(data, uid), sort_keys=True).replace('<', '\\u003c')
    return HTML.replace('__DATA__', payload)


def placement(row, dependencies, index):
    if row['target_type'] == 'retire':
        rule = 'retirement / storage or catalog replacement'
    elif row['system'] == 'spark':
        rule = 'Spark floor: billing 3, otherwise 2'
    elif row['kind'] == 'view':
        rule = 'compatibility serving views: wave 4'
    elif row['kind'] in ('workflow', 'worklet'):
        rule = 'orchestration: billing 3, otherwise 4'
    elif '.STG_' in row['name'] or '_STG_' in row['name'] or row['kind'] in ('fastload', 'tpt'):
        rule = 'landing/load/staging foundation: wave 1'
    elif row['subject_area'] == 'billing' or row['kind'] in ('macro', 'procedure'):
        rule = 'billing or procedural workload: wave 3'
    else:
        rule = 'core/relational transformation floor: wave 2'
    parents = sorted(index[a]['name'] + ' (wave ' + str(index[a]['wave']) + ')'
                     for a, b in dependencies if b == row['id'])
    return rule + '; final wave = max(floor, upstream waves). Dependencies: ' + (', '.join(parents) or 'none')


def retirement(row):
    facts = row['retire_evidence']
    if row['system'] == 'spark':
        return (f"runs={facts['runs_in_window']}; last run={facts['last_run']}; "
                f"cron={json.dumps(facts['cron'], sort_keys=True)}; readers={json.dumps(facts['readers'])}")
    last = max(facts['recent_accesses'], key=lambda r: (r['timestamp'], r['QueryID']), default={})
    return (f"reads={facts['read_count']}; writes={facts['usage_counts'].get('WRITE', 0)}; "
            f"last read={facts['last_read']}; last write={facts['last_write']}; "
            f"last QueryID/principal={last.get('QueryID')} / {last.get('principal')}; "
            f"feeds dead={', '.join(facts.get('feeds_dead_objects', [])) or 'n/a'}")


def wave_plan(data):
    objects = data['objects']
    index = {row['id']: row for row in objects}
    lines = ['# Wave plan', '', 'Generated from manifest rules and dependency edges. All objects remain not_started.',
             'Counts are planned scope, not completed migrations or realized licence savings.', '',
             'DBQL window: 2026-08-12..2026-11-09. Spark window: newest packaged start date minus 89 days through that date.',
             'Containment/data-availability edges do not prescribe execution order within a wave.', '']
    entries = {1: 'Approve retirement evidence and rollback/retention policy; provision Snowflake landing, roles and observability.',
               2: 'Foundation feeds and staging reconciled; owner-approved contracts for core and Spark outputs.',
               3: 'Upstream wave 1/2 dependencies passed parity; billing/procedural owners approve financial controls.',
               4: 'Upstream outputs reconciled; consumer owners approve compatibility and orchestration contracts.'}
    exits = {1: 'Owner signs retirement; retention and restore tested; replacement feeds pass counts/schema checks.',
             2: 'Core/Spark replacements pass keyed hashes, null/duplicate checks and scheduling/runtime gates.',
             3: 'Financial totals, period close, restartability and procedural side effects pass owner sign-off.',
             4: 'Consumer UAT, compatibility queries, schedules and rollback pass; monitor before disabling legacy access.'}
    for wave in range(1, 5):
        rows = [row for row in objects if row['wave'] == wave]
        lines += [f'## Wave {wave}', '', f'Objects: {len(rows)}', '',
                  f'Entry: {entries[wave]}', '', f'Exit: {exits[wave]}', '',
                  'Earlier-wave dependencies must pass their exit criteria; same-wave dependencies must be available before each dependent cuts over.', '',
                  '### Scope counts', '', '| Dimension | Value | Count |', '|---|---|---:|']
        for field in ('system', 'kind', 'target_type'):
            for value, count in sorted(Counter(row[field] for row in rows).items()):
                lines.append(f'| {field} | {value} | {count} |')
        licences = Counter(row['licence_dependency'] for row in rows)
        lines += ['', 'Licence dependencies eligible to free after verified cutover/decommission: ' +
                  ', '.join(f'{key}: {value} objects' for key, value in sorted(licences.items())) + '.',
                  'Teradata compute/catalog access, PowerCenter execution and Spark scheduling/compute can be removed only after all dependent consumers and retention obligations are cleared. These are object counts, not additive monetary savings.', '']
        areas = defaultdict(list)
        for row in rows:
            areas[row['subject_area']].append(row)
        for area, members in sorted(areas.items()):
            lines += [f'### {area}', '']
            for row in sorted(members, key=lambda r: r['name']):
                lines += [f"- **{row['name']}** — {row['owner']}; {row['system']}/{row['kind']}; {row['target_type']} → `{row['target']}`.",
                          '  - Placement: ' + placement(row, data['dependencies'], index)]
        if wave == 1:
            lines += ['', '### Retirement list and evidence', '']
            for row in sorted((r for r in rows if r['target_type'] == 'retire'), key=lambda r: r['name']):
                lines += [f"- **{row['name']}** — {'; '.join(row['risk_reasons'])}", '  - ' + retirement(row)]
        lines.append('')
    lines += ['## Review before cutover', '', '### Stale: owner review, not automatic retirement', '']
    for row in data['stale']:
        lines.append(f"- **{row['name']}** — {index[row['id']]['owner']}; last read={row['last_read']}; reads={row['read_count']}; last write={row['last_write']}; recent accesses={json.dumps(row['recent_accesses'], sort_keys=True)}")
    if not data['stale']:
        lines.append('None.')
    lines += ['', '### Running Spark jobs without a legacy output reader', '',
              'Confirm demand with the owner before building a replacement; no reader found is not proof of no consumer.', '']
    candidates = [r for r in objects if r['system'] == 'spark' and r['run_evidence']['runs_in_window'] > 0
                  and not r['run_evidence']['readers']]
    for row in candidates:
        facts = row['run_evidence']
        lines.append(f"- **{row['name']}** — {row['owner']}; target={row['target_type']}; runs={facts['runs_in_window']}; last run={facts['last_run']}; excluded mentions={len(facts['non_reader_mentions'])} (see manifest evidence).")
    if not candidates:
        lines.append('None.')
    lines += ['', '### Open finding: file_object_binary_extract', '',
              '`ModuleNotFoundError: No module named warehouse` during the local 2026-11-19 run. '
              '`common/binary_documents.py` imports `warehouse.run_config`, which is absent from common.zip and Spark service mounts. '
              'Estate source is unchanged. Owner: @otterworks/data-platform. Resolve deployment packaging and rerun before cutover; packaged history does not validate this local failure.', '']
    return '\n'.join(lines)


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DW exit · Lineage explorer</title><style>
*{box-sizing:border-box}body{margin:0;background:#0b1220;color:#e2e8f0;font:14px system-ui,sans-serif}header{padding:22px 28px;background:#111d32;border-bottom:1px solid #334155}h1{margin:0 0 6px;font-size:24px}p{color:#a9bad1;margin:6px 0}nav{display:flex;gap:14px;align-items:end;flex-wrap:wrap;margin-top:18px}label{display:grid;gap:5px;font-size:12px;color:#b8c8dd}input,select,button{font:inherit;color:#e2e8f0;background:#182840;border:1px solid #52647c;border-radius:6px;padding:9px}input[type=search]{width:270px}button{cursor:pointer}.focus{display:flex;align-items:center;gap:7px;padding:8px}main{display:grid;grid-template-columns:minmax(0,1fr) 370px;height:calc(100vh - 206px)}#canvas{overflow:auto;padding:18px}aside{overflow:auto;padding:22px;border-left:1px solid #334155;background:#101c2e}h2{font-size:18px;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 ui-monospace,monospace;background:#0b1424;border-radius:8px;padding:14px}dl{display:grid;grid-template-columns:120px 1fr;gap:9px;font-size:13px}dt{color:#94a8c4}dd{margin:0;overflow-wrap:anywhere}.legend{display:flex;gap:17px;margin-top:14px;font-size:12px;color:#b8c8dd}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}svg{display:block;width:100%;min-width:950px}.node{cursor:pointer;outline:none}.node rect{stroke-width:1.5}.node:hover rect,.node:focus rect{stroke:#fff;stroke-width:3}.node.selected rect{stroke:#fff;stroke-width:3}.node text{fill:#eff6ff;font:12px system-ui;pointer-events:none}.edge{fill:none;stroke:#49627e;stroke-width:1.2;opacity:.4}.edge.active{stroke:#5eead4;stroke-width:2.5;opacity:1}.dim{opacity:.14}.column{fill:#a5bad7;font:600 13px system-ui}#status{font-size:12px;color:#93a8c4;margin-bottom:12px}small{color:#a9bad1}@media(max-width:900px){main{grid-template-columns:1fr;height:auto}aside{border-left:0}#canvas{max-height:65vh}}
dt{overflow-wrap:anywhere;padding-right:8px}
</style></head><body><header><h1>DW exit / Lineage explorer</h1><p>Legacy estate → Snowflake · Click a node to trace upstream and downstream dependencies.</p>
<nav><label>Search nodes<input id="search" type="search" placeholder="Name, source or owner…"></label><label>Wave<select id="wave"><option value="">All waves</option></select></label><label>System<select id="system"><option value="">All systems</option></select></label><label>Subject area<select id="subject_area"><option value="">All areas</option></select></label><label class="focus"><input id="focus" type="checkbox" checked>Focus selected paths</label><button id="reset">Reset view</button></nav>
<div class="legend"><span><i class="dot" style="background:#3b82f6"></i>Wave 1</span><span><i class="dot" style="background:#14b8a6"></i>Wave 2</span><span><i class="dot" style="background:#a78bfa"></i>Wave 3</span><span><i class="dot" style="background:#f59e0b"></i>Wave 4</span><span>┄ Grey: retire</span><span style="color:#fb923c">Orange outline: hidden consumer</span></div></header>
<main><section id="canvas" aria-label="Lineage graph"><div id="status"></div><svg id="graph" role="img" aria-label="Layered dependency graph"></svg></section><aside><small>OBJECT INSPECTOR</small><h2 id="title">Select a node</h2><div id="details">Use search and filters to explore the estate. Arrows represent data availability or workflow containment, not within-wave execution order.</div></aside></main>
<script id="lineage-data" type="application/json">__DATA__</script><script>
'use strict';
const data=JSON.parse(document.getElementById('lineage-data').textContent),byId=new Map(data.nodes.map(n=>[n.id,n])),svg=document.getElementById('graph');
const colors={1:'#234e89',2:'#115e59',3:'#5b4389',4:'#854d0e'},NS='http://www.w3.org/2000/svg';let selected=null;
for(const field of ['wave','system','subject_area']){const select=document.getElementById(field);for(const value of [...new Set(data.nodes.map(n=>n[field]).filter(v=>v!==undefined&&v!==''))].sort()){const opt=document.createElement('option');opt.value=value;opt.textContent=field==='wave'?'Wave '+value:value;select.append(opt)}select.addEventListener('change',()=>{selected=null;render()})}
function el(tag,attrs={},text){const element=document.createElementNS(NS,tag);for(const [key,value]of Object.entries(attrs))element.setAttribute(key,value);if(text!==undefined)element.textContent=text;return element}
function reach(id,reverse){const seen=new Set([id]),queue=[id];for(let i=0;i<queue.length;i++)for(const[a,b]of data.links){const from=reverse?b:a,to=reverse?a:b;if(from===queue[i]&&!seen.has(to)){seen.add(to);queue.push(to)}}return seen}
function inspect(){const node=byId.get(selected),container=document.getElementById('details');container.replaceChildren();document.getElementById('title').textContent=node?node.name:'Select a node';if(!node){container.textContent='Click a node to inspect its fields and trace connected paths.';return}const dl=document.createElement('dl');for(const key of ['system','kind','wave','owner','subject_area','licence_dependency','target_type','target','risk','dbql_reads_90d','last_read','source']){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=key;dd.textContent=node[key]===undefined||node[key]===''?'Not recorded':String(node[key]);dl.append(dt,dd)}container.append(dl);for(const key of ['risk_reasons','retire_evidence','run_evidence'])if(node[key]){const h=document.createElement('h3'),pre=document.createElement('pre');h.textContent=key.replaceAll('_',' ');pre.textContent=JSON.stringify(node[key],null,2);container.append(h,pre)}}
function render(){const up=selected?reach(selected,true):new Set(),down=selected?reach(selected,false):new Set(),related=new Set([...up,...down]);const query=document.getElementById('search').value.toLowerCase();const nodes=data.nodes.filter(n=>(!selected||!document.getElementById('focus').checked||related.has(n.id))&&['wave','system','subject_area'].every(f=>!document.getElementById(f).value||String(n[f])===document.getElementById(f).value)&&(!query||[n.name,n.source,n.owner].some(v=>String(v||'').toLowerCase().includes(query))));const positions=new Map(),columns=data.layers.map((_,i)=>nodes.filter(n=>n.layer===i).sort((a,b)=>a.name.localeCompare(b.name))),max=Math.max(1,...columns.map(c=>c.length)),height=Math.max(440,max*58+65);svg.replaceChildren();svg.setAttribute('viewBox',`0 0 1750 ${height}`);svg.style.height=(height/1750*Math.max(950,svg.clientWidth))+'px';const defs=el('defs'),marker=el('marker',{id:'arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});marker.append(el('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#83a6b5'}));defs.append(marker);svg.append(defs);columns.forEach((rows,i)=>{svg.append(el('text',{x:i*250+14,y:22,class:'column'},data.layers[i]));rows.forEach((n,j)=>positions.set(n.id,{x:i*250+10,y:55+j*58+(max-rows.length)*29}))});let edges=0;for(const[a,b]of data.links){const s=positions.get(a),t=positions.get(b);if(!s||!t)continue;edges++;const active=selected&&((up.has(a)&&up.has(b))||(down.has(a)&&down.has(b)));const x=s.x+225,y=s.y+19,tx=t.x,ty=t.y+19;svg.append(el('path',{d:`M${x},${y} C${x+65},${y} ${tx-65},${ty} ${tx},${ty}`,class:'edge'+(active?' active':selected?' dim':''),'marker-end':'url(#arrow)'}))}for(const n of nodes){const p=positions.get(n.id),retire=n.target_type==='retire',g=el('g',{class:'node'+(selected===n.id?' selected':selected&&!related.has(n.id)?' dim':''),transform:`translate(${p.x},${p.y})`,tabindex:0,role:'button','aria-label':n.name,'data-id':n.id});g.append(el('rect',{width:225,height:38,rx:7,fill:retire?'#374151':colors[n.wave]||'#20324c',stroke:n.hidden?'#fb923c':retire?'#9ca3af':'#526f91','stroke-dasharray':retire?'5 3':'none'}));g.append(el('text',{x:10,y:23},n.name.length>29?n.name.slice(0,27)+'…':n.name));g.append(el('title',{},n.name));const choose=()=>{selected=n.id;render();document.getElementById('canvas').scrollTop=0};g.addEventListener('click',choose);g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose()}});svg.append(g)}document.getElementById('status').textContent=`${nodes.length} / ${data.nodes.length} nodes · ${edges} visible edges${selected?' · upstream/downstream paths selected':''}${nodes.length?'':' · No matching nodes'}`;inspect()}
document.getElementById('search').addEventListener('input',()=>{selected=null;render()});document.getElementById('focus').addEventListener('change',render);document.getElementById('reset').addEventListener('click',()=>{selected=null;document.getElementById('search').value='';for(const f of ['wave','system','subject_area'])document.getElementById(f).value='';render()});render();
</script></body></html>
'''
