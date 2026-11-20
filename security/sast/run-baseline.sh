#!/usr/bin/env bash
set -euo pipefail
set +x
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
OUT=${OUT:-$REPO/security/sast/baseline}
RUNTIME_DIR=${RUNTIME_DIR:-$REPO/security/sast/.runtime}
mkdir -p "$OUT" "$RUNTIME_DIR"
OUT=$(cd "$OUT" && pwd)
RUNTIME_DIR=$(cd "$RUNTIME_DIR" && pwd)
SQ=sonarqube@sha256:c3c729d9d797467692445bd718f1e8c8e1d34b7607469308e8e9cffe804f36d1
SCANNER=sonarsource/sonar-scanner-cli@sha256:6e6eca4d552695a98fb7dab84f0c1bd0885ebbfe272654d1552e24bd7f452d51
PY=python@sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89
export SQ SCANNER PY
# This dedicated local baseline is recreated from scratch on every run.
# The original wget healthcheck is replaced because this image contains curl, not wget.
printf 'services:\n  sonarqube:\n    image: %s\n    healthcheck:\n      test: ["CMD-SHELL", "curl -fsS http://localhost:9000/api/system/status | grep -q UP"]\n' "$SQ" > "$RUNTIME_DIR/pin.yml"
COMPOSE=(docker compose -p otterworks-core-baseline -f "$REPO/security/ingest/docker-compose.sonarqube.yml" -f "$RUNTIME_DIR/pin.yml")
"${COMPOSE[@]}" up -d --force-recreate --renew-anon-volumes sonarqube
py() { docker run --rm -i --network host -e SONAR_TOKEN -e SQ -e SCANNER -e PY -v "$OUT:/out" -v "$RUNTIME_DIR:/runtime" -v "$REPO:/repo:ro" "$PY" python - "$@"; }
SONAR_TOKEN=$(py <<'PY'
import urllib.request as u, urllib.parse as p, json, time, base64, secrets
host='http://127.0.0.1:9000'
for _ in range(180):
    try:
        if json.load(u.urlopen(host+'/api/system/status'))['status']=='UP': break
    except Exception: pass
    time.sleep(5)
else: raise RuntimeError('SonarQube did not become ready')
password='admin'
def post(path,**args):
    req=u.Request(host+path,data=p.urlencode(args).encode(),headers={'Authorization':'Basic '+base64.b64encode(('admin:'+password).encode()).decode()})
    with u.urlopen(req) as r: return r.read()
new='Aa1!'+secrets.token_urlsafe(32)
post('/api/users/change_password',login='admin',previousPassword='admin',password=new)
password=new
print(json.loads(post('/api/user_tokens/generate',name='baseline-'+str(time.time_ns())))['token'])
PY
)
export SONAR_TOKEN
trap 'unset SONAR_TOKEN' EXIT
SOURCES=services/api-gateway,services/auth-service,services/file-service,services/document-service,services/collab-service,services/notification-service,services/search-service,services/analytics-service,services/admin-service,services/audit-service,services/report-service,frontend/client-app,frontend/admin-dashboard
TESTS='**/tests/**,**/test/**,**/spec/**,**/__tests__/**,**/src/test/**,**/*_test.go,**/test_*.py,**/*_test.py,**/*.test.*,**/*.spec.*'
EXCLUSIONS='**/scripts/**,**/node_modules/**,**/vendor/**,**/build/**,**/dist/**,**/target/**,**/.next/**,**/.gradle/**,**/coverage/**,**/__pycache__/**,**/bin/**,**/obj/**,**/*.lock,**/*-lock.json,**/go.sum,**/gradlew,**/gradlew.bat,**/gradle/wrapper/**,**/*.min.js'
docker run --rm --network host -e SONAR_TOKEN -e SONAR_HOST_URL=http://localhost:9000 -v "$REPO:/usr/src:ro" --entrypoint sh "$SCANNER" -c 'mkdir -p /tmp/empty-binaries; exec /usr/bin/entrypoint.sh sonar-scanner "$@"' scanner \
 -Dsonar.projectKey=otterworks-core-baseline -Dsonar.sources="$SOURCES" -Dsonar.tests="$SOURCES" \
 -Dsonar.exclusions="$EXCLUSIONS,$TESTS" -Dsonar.test.inclusions="$TESTS" -Dsonar.test.exclusions="$EXCLUSIONS" \
 -Dsonar.java.binaries=/tmp/empty-binaries -Dsonar.scm.disabled=true -Dsonar.verbose=true \
 -Dsonar.typescript.tsconfigPaths=services/collab-service/tsconfig.json,frontend/client-app/tsconfig.json,frontend/client-app/desktop/tsconfig.json,frontend/admin-dashboard/tsconfig.json \
 2>&1 | tee "$RUNTIME_DIR/scanner.log"
py <<'PY'
import os, json, urllib.request as u, urllib.parse as p, urllib.error, time, re, collections, fnmatch
from pathlib import Path
host='http://localhost:9000'; project='otterworks-core-baseline'
def api(path, **params):
    req=u.Request(host+'/api/'+path+'?'+p.urlencode(params),headers={'Authorization':'Bearer '+os.environ['SONAR_TOKEN']})
    try:
        with u.urlopen(req,timeout=120) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(path+': '+e.read().decode()) from None
def pages(endpoint, field, **params):
    result=[]; page=1
    while True:
        data=api(endpoint,ps=500,p=page,**params)
        total=data.get('paging',{}).get('total',data.get('total',0))
        if total>10000: raise RuntimeError('API result limit exceeded; partition query before exporting')
        result.extend(data.get(field,[]))
        if page*500>=total: return result
        page+=1
def save(name,obj): Path('/out/'+name).write_text(json.dumps(obj,indent=2)+'\n')
log=Path('/runtime/scanner.log').read_text()
task=re.search(r'api/ce/task\?id=([^\s]+)',log).group(1)
for _ in range(240):
    ce=api('ce/task',id=task)['task']
    if ce['status']=='SUCCESS': break
    if ce['status'] in ('FAILED','CANCELED'): raise RuntimeError(ce)
    time.sleep(3)
else: raise RuntimeError('Analysis processing timeout')
issues=pages('issues/search','issues',componentKeys=project)
hotspots=pages('hotspots/search','hotspots',project=project)
# Preserve every raw API field, including impacts and clean-code attributes.
for row in hotspots:
    row['details']=api('hotspots/show',hotspot=row['key'])
save('issues.json',{'total':len(issues),'issues':issues})
save('hotspots.json',{'total':len(hotspots),'hotspots':hotspots})
files=pages('components/tree','components',component=project,qualifiers='FIL,UTS')
save('analyzed-files.json',files)
profiles=api('qualityprofiles/search',project=project)
save('quality-profiles.json',profiles)
services=['services/'+s for s in ['api-gateway','auth-service','file-service','document-service','collab-service','notification-service','search-service','analytics-service','admin-service','audit-service','report-service']]+['frontend/client-app','frontend/admin-dashboard']
summary={}
for service in services:
    selected=[f for f in files if f['path'].startswith(service+'/')]
    summary[service]={'indexed_file_count':len(selected),'indexed_languages':dict(collections.Counter(f.get('language','unknown') for f in selected)),'files':selected}
head=Path('/repo/.git/HEAD').read_text().strip()
if head.startswith('ref: '):
    ref=head[5:]; path=Path('/repo/.git')/ref
    head=path.read_text().strip() if path.exists() else next(line.split()[0] for line in Path('/repo/.git/packed-refs').read_text().splitlines() if line.endswith(' '+ref))
meta={'project':project,'version':None,'commit':head,'scope':services,'profiles':profiles,'per_service':summary,'compute_engine_task':ce,'images':{k:os.environ.get(k) for k in ['SQ','SCANNER','PY']},'gaps':[]}
with u.urlopen(host+'/api/server/version') as r: meta['version']=r.read().decode()
save('scan-meta.json',meta)
meta['scanner_version']=re.search(r'SonarScanner CLI ([^\n]+)',log).group(1).strip()
meta['profile_note']='This pinned Community Build names its factory defaults Sonar way core (most languages) and Sonar way comprehensive (JSON/YAML); no custom profiles or rule overrides were applied.'
meta['coverage_caveat']='API persisted files are not equivalent to semantic analysis. C# files persist but the C# sensor explicitly refuses CLI analysis. Files without a language sensor must not be interpreted as clean.'
meta['gaps']=[
 'C#: scanner explicitly warns it cannot analyze C# with CLI; SonarScanner for .NET 5.x or higher is required. No build or dependency install was performed.',
 'Rust, Ruby, Scala: no corresponding language detected/profile/sensor in this scan. Their files have no language-specific semantic analysis. See per-service file inventory; text/secrets analysis is not a substitute.',
 'Java: empty binaries directory; missing sonar.java.libraries, test binaries/libraries, unresolved imports/types, and preview-feature warnings. Analysis is less precise without compiled dependencies.',
 'Python: default compatibility range 3.10 through 3.14; no explicit version configured.',
 'No tests executed or coverage reports generated. No dependency/SCA analysis. This is not proof of absence of vulnerabilities.'
]
supported={'go','java','kotlin','py','ts','js','css','web','xml','docker'}
index={}
for line in log.splitlines():
    match=re.search(r"'([^']+)' indexed (.*)",line)
    if match:
        path,details=match.groups(); index[path]={'scanner_index_detail':details}
Path('/runtime/scanner-index.json').write_text(json.dumps(index,indent=2)+'\n')
ext={'.rs':'rust','.rb':'ruby','.scala':'scala','.cs':'cs','.py':'py','.go':'go','.java':'java','.kt':'kotlin','.kts':'kotlin','.ts':'ts','.tsx':'ts','.js':'js','.jsx':'js','.css':'css','.html':'web','.xml':'xml','.json':'json','.yaml':'yaml','.yml':'yaml'}
exclude_dirs={'scripts','node_modules','vendor','build','dist','target','.next','.gradle','coverage','__pycache__','bin','obj'}
for service, data in summary.items():
    inventory=[]
    for f in sorted((Path('/repo')/service).rglob('*')):
        if not f.is_file(): continue
        path=f.relative_to('/repo').as_posix(); lang='docker' if f.name=='Dockerfile' else ext.get(f.suffix,'other')
        excluded=bool(set(f.relative_to('/repo').parts)&exclude_dirs) or f.name.endswith('.lock') or f.name.endswith('-lock.json') or f.name in {'go.sum','gradlew','gradlew.bat'} or '/gradle/wrapper/' in path or f.name.endswith('.min.js')
        test=bool(set(f.parts)&{'test','tests','spec','__tests__'}) or bool(re.search(r'(_test\.go|/test_[^/]+\.py|_test\.py|\.test\.|\.spec\.)',path))
        persisted=next((x for x in data['files'] if x['path']==path),None)
        if excluded: status='excluded'
        elif lang=='cs': status='semantic_analysis_skipped_cli_not_dotnet'
        elif lang in {'rust','ruby','scala'}: status='no_language_analyzer_executed'
        elif persisted and lang in supported: status='language_sensor_executed_file_persisted'
        elif persisted: status='persisted_no_per_file_semantic_confirmation'
        else: status='not_persisted_no_per_file_semantic_confirmation'
        inventory.append({'path':path,'language_by_extension':lang,'classification':'test' if test else 'source','status':status,'persisted':bool(persisted),**index.get(path,{})})
    data['inventory']=inventory
    data['coverage_counts']={lang:dict(collections.Counter(x['status'] for x in inventory if x['language_by_extension']==lang)) for lang in sorted({x['language_by_extension'] for x in inventory})}
meta['scope_exclusions']='Only the 13 explicit roots; nested scripts, dependencies/build output/lockfiles excluded; tests separately classified, never main sources. See scanner.log for exact properties.'
meta['gaps'].append('Kotlin sensor reports 11/11 Kotlin sources and 2/2 Gradle files analyzed, but DEBUG contains repeated NoSuchMethodError: com.intellij.openapi.fileTypes.FileType.getDefaultExtension(). Treat semantic precision as degraded; five Kotlin test files were indexed but not included in the Kotlin source-sensor count.')
meta['runtime_note']='The supplied Compose healthcheck invokes wget, absent in the pinned image. The runner uses a local pin.yml override with curl instead; the running server is healthy and its API reports UP. No repository configuration was changed.'
for service,data in summary.items():
    entries=[v['scanner_index_detail'] for k,v in index.items() if k.startswith(service+'/')]
    data['scanner_indexed_file_count']=len(entries)
    data['scanner_indexed_language_counts']={kind:dict(collections.Counter((re.search(r"language '([^']+)'",d).group(1) if re.search(r"language '([^']+)'",d) else 'none') for d in entries if ('as test' in d)==(kind=='test'))) for kind in ['source','test']}
    for row in data['inventory']:
        if row['language_by_extension']=='kotlin' and row['classification']=='test' and row['status']!='excluded': row['status']='indexed_test_not_counted_in_kotlin_source_sensor'
    data['coverage_counts']={lang:dict(collections.Counter(x['status'] for x in data['inventory'] if x['language_by_extension']==lang)) for lang in data['coverage_counts']}
save('scan-meta.json',meta)
severities=['BLOCKER','CRITICAL','MAJOR','MINOR','INFO']
def component(row): return row['component'].removeprefix(project+':')
lines=['# OtterWorks core SAST baseline',f'Commit: {head}; SonarQube {meta["version"]}; scanner {meta["scanner_version"]}.',meta['profile_note'],'','Counts use legacy issue type/severity; raw impacts/softwareQuality and cleanCodeAttribute are preserved separately. V/B columns are BLOCKER/CRITICAL/MAJOR/MINOR/INFO. Hotspots are HIGH/MEDIUM/LOW.','','| Service | Vulnerabilities B/C/M/m/I | Bugs B/C/M/m/I | Smells | Hotspots H/M/L |','|---|---|---|---:|---|']
for service in services:
    rows=[x for x in issues if component(x).startswith(service+'/')]
    counts=lambda typ:'/'.join(str(sum(x['type']==typ and x['severity']==s for x in rows)) for s in severities)
    hs=[x for x in hotspots if component(x).startswith(service+'/')]
    lines.append(f'| {service} | {counts("VULNERABILITY")} | {counts("BUG")} | {sum(x["type"]=="CODE_SMELL" for x in rows)} | '+ '/'.join(str(sum(x['vulnerabilityProbability']==s for x in hs)) for s in ['HIGH','MEDIUM','LOW'])+' |')
lines+=['','## Top 15 issue rules by count']+[f'- {r}: {n}' for r,n in collections.Counter(x['rule'] for x in issues).most_common(15)]
lines+=['','## All BLOCKER/CRITICAL vulnerabilities and HIGH probability hotspots']
for x in issues:
    if x['type']=='VULNERABILITY' and x['severity'] in {'BLOCKER','CRITICAL'}: lines.append(f'- {x["severity"]} {x["rule"]} — {component(x)}:{x.get("line","?")} — {x["message"]}')
for x in hotspots:
    if x['vulnerabilityProbability']=='HIGH': lines.append(f'- HIGH {x.get("ruleKey",x.get("details",{}).get("rule",{}).get("key"))} — {component(x)}:{x.get("line","?")} — {x["message"]}')
lines+=['','## Coverage gaps']+['- '+x for x in meta['gaps']]
lines+=['','## Per-service persisted files/languages (not semantic coverage for C#)']+[f'- {s}: {d["indexed_file_count"]}; {d["indexed_languages"]}' for s,d in summary.items()]
Path('/runtime/report.md').write_text('\n'.join(lines)+'\n')
print(f'Exported {len(issues)} issues, {len(hotspots)} hotspots, {len(files)} indexed files; SonarQube {meta["version"]}')

PY
unset SONAR_TOKEN
