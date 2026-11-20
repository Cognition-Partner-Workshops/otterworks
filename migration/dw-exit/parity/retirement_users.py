"""Current DBQL evidence, not conversion parity or retirement approval."""
import hashlib
from pathlib import Path
import subprocess

import assess

ROOT = Path(__file__).resolve().parents[3]
DEAD = {'SFX_USERS.USER_PREF', 'SFX_USERS.V_USER_SETTINGS'}
DEPENDENTS = {'SFX_USERS.STG_USER_PREF', 'users_user_pref'}
CAVEAT = 'Keep the independent Spark USER_PREF/PREF_JSON landing feed for user_pref_json_flatten; owner-approved retirement, no physical deletion by board generation'


def verify(root=ROOT):
    evidence = dict(passed=False, window=['2026-08-12', '2026-11-09'], caveat=CAVEAT)
    try:
        current = assess.build(root=root)
        queries, usage, catalog, dead = assess.dbql(root)
        dates = sorted(q['StartTime'][:10] for q in queries.values())
        reads = {name: sum(r['ObjectDatabaseName']+'.'+r['ObjectTableName'] == name
                          and r['UsageType'].upper() == 'READ' for r in usage) for name in sorted(DEAD)}
        declared = {r['name'] for r in current['objects'] if r['target_type'] == 'retire'}
        evidence.update(query_count=len(queries), reads=reads, dead=sorted(DEAD & set(current['dead'])),
                        dead_dependents=sorted(DEPENDENTS & set(current['dead_dependents'])),
                        observed_window=[dates[0], dates[-1]] if dates else [],
                        sha256={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (root/'warehouse/teradata/dbql'/name
                                          for name in ('qrylog.csv', 'objectusage.csv', 'tablesv.csv'))})
        evidence['passed'] = (bool(usage) and evidence['observed_window'] == evidence['window']
                              and not any(reads.values()) and DEAD <= set(dead)
                              and DEAD <= set(current['dead']) and DEPENDENTS <= set(current['dead_dependents'])
                              and (DEAD | DEPENDENTS) <= declared)
        evidence['reason'] = 'Current DBQL absence and dead-dependent propagation verified' if evidence['passed'] else 'Current DBQL retirement evidence failed'
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        evidence['reason'] = 'Current DBQL retirement evidence unavailable: '+str(error).splitlines()[0]
    return evidence
