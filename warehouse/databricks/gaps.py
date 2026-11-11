"""Focused semantic probes, independent of either conversion implementation."""
from datetime import datetime, timezone
import json
from pathlib import Path

from .baseline import literal
from .parity import DOCUMENT_VERSION, RESULTS


BEFORE = "cpw.dbx_d1111_before."
AFTER = "cpw.dbx_d1111_after."


def difference_query(before, after):
    return (f"WITH b AS ({before}), a AS ({after}) SELECT coalesce(b.k,a.k) key, "
            "b.v before_value,a.v after_value,COUNT(*) OVER () difference_count "
            "FROM b FULL OUTER JOIN a ON b.k=a.k WHERE NOT(b.v <=> a.v) ORDER BY key LIMIT 20")


def projection(table, key, columns, where=""):
    return f"SELECT CAST({key} AS STRING) k,to_json(array({','.join('CAST('+c+' AS STRING)' for c in columns)})) v FROM {table} {where}"


def tie_query():
    columns = "version_id,document_id,version_no,version_ts,file_size,content_hash"
    row = "to_json(array(" + ",".join("CAST(" + c + " AS STRING)" for c in columns.split(',')) + "))"
    return f"""WITH candidates AS (
      SELECT *,COUNT(*) OVER (PARTITION BY document_id) candidate_count FROM (
        SELECT * FROM {BEFORE}documents__stg_doc_version
        QUALIFY DENSE_RANK() OVER (PARTITION BY document_id ORDER BY version_ts DESC NULLS LAST)=1
      ) m
    ), final_pick AS (SELECT document_id,{row} v FROM candidates
      QUALIFY ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY version_no DESC,version_id DESC)=1),
    c AS (SELECT document_id,MAX(candidate_count) n,collect_set({row}) allowed FROM candidates GROUP BY document_id),
    b AS (SELECT document_id,{row} v FROM {BEFORE}documents__doc_version),
    a AS (SELECT document_id,{row} v FROM {AFTER}billing__in_documents_doc_version),
    checked AS (SELECT c.document_id,c.n,b.v bv,a.v av,
      a.v IS NOT NULL AND array_contains(c.allowed,a.v) valid_candidate FROM c
      LEFT JOIN b ON c.document_id=b.document_id LEFT JOIN a ON c.document_id=a.document_id)
    SELECT SUM(CASE WHEN NOT coalesce(valid_candidate,false) OR (n=1 AND NOT(bv <=> av)) THEN 1 ELSE 0 END) invalid_rows,
      SUM(CASE WHEN n>1 THEN 1 ELSE 0 END) tied_documents,
      SUM(CASE WHEN n>1 AND NOT(bv <=> av) THEN 1 ELSE 0 END) different_baseline_picks,
      (SELECT COUNT(*) FROM a LEFT ANTI JOIN c ON a.document_id=c.document_id) extra_documents,
      (SELECT COUNT(*) FROM final_pick f FULL OUTER JOIN a ON f.document_id=a.document_id WHERE NOT(f.v <=> a.v)) final_rule_mismatches
    FROM checked"""


def untied_query():
    columns = 'version_id,document_id,version_no,version_ts,file_size,content_hash'
    projection = ','.join('v.'+c for c in columns.split(','))
    return f"""WITH maxima AS (
      SELECT * FROM {BEFORE}documents__stg_doc_version
      QUALIFY DENSE_RANK() OVER (PARTITION BY document_id ORDER BY version_ts DESC NULLS LAST)=1
    ), untied AS (SELECT document_id FROM maxima GROUP BY document_id HAVING COUNT(*)=1),
    b AS (SELECT {projection} FROM {BEFORE}documents__doc_version v JOIN untied u ON v.document_id=u.document_id),
    a AS (SELECT {projection} FROM {AFTER}{DOCUMENT_VERSION} v JOIN untied u ON v.document_id=u.document_id)
    SELECT 'missing_or_different_after' difference,* FROM (SELECT * FROM b EXCEPT ALL SELECT * FROM a)
    UNION ALL SELECT 'missing_or_different_before' difference,* FROM (SELECT * FROM a EXCEPT ALL SELECT * FROM b)"""


def probe_queries():
    probes = {}
    def pair(name, obj, source, key, columns, where=""):
        probes[name] = (obj, difference_query(projection(BEFORE+source,key,columns,where), projection(AFTER+obj,key,columns,where)))
    pair('char_padding','billing__subscription','billing__subscription','subscription_id',['status_cd'], 'WHERE subscription_id>=9000000001')
    b = f"SELECT CAST(storage_usage_id AS STRING) k,to_json(array(CAST(COUNT(*) AS STRING))) v FROM {BEFORE}documents__storage_usage_daily WHERE storage_usage_id>=9000000001 GROUP BY storage_usage_id"
    a = b.replace(BEFORE+'documents__storage_usage_daily',AFTER+'billing__in_documents_storage_usage_daily')
    probes['set_duplicates'] = ('billing__in_documents_storage_usage_daily',difference_query(b,a))
    probes['qualify_ties'] = ('billing__in_documents_doc_version',tie_query())
    probes['untied_exact'] = (DOCUMENT_VERSION,untied_query())
    pair('format_period_key','billing__invoice_hdr','billing__invoice_hdr','invoice_id',['invoice_period','period_key'],'WHERE invoice_id>=9000000001')
    pair('date_arithmetic','billing__invoice_hdr','billing__invoice_hdr','invoice_id',['CAST(invoice_dt AS STRING)','CAST(bill_dt AS STRING)','invoice_month','CAST(prior_period_end_dt AS STRING)','period_closed_cd'],'WHERE invoice_id>=9000000001')
    pair('silent_truncation','billing__in_users_app_user','users__app_user','user_id',['display_name','length(display_name)'],'WHERE user_id>=9000000001')
    def ci(side):
        prefix = BEFORE if side=='before' else AFTER
        return (projection(prefix+'billing__m_subscription_plans',"concat('plan:',subscription_id)",['plan_code','monthly_fee'],'WHERE subscription_id>=9000000001')+
                ' UNION ALL '+projection(prefix+'billing__m_currency_totals',"concat('currency:',currency_cd)",['currency_cd','invoice_count','total_amount']))
    probes['case_insensitive'] = ('billing__m_subscription_plans',difference_query(ci('before'),ci('after')))
    return probes


def run_gaps(client, label, evidence_dir=None, *, objects=None):
    directory = Path(evidence_dir or Path.home()/'dbx-evidence')
    path = directory/f'gaps_{label}.json'
    results = json.loads(path.read_text()) if path.exists() else []
    for name,(obj,query) in probe_queries().items():
        if objects is not None and obj not in objects:
            continue
        response = client.execute(query,step='gap-'+name)
        if name=='qualify_ties':
            values = [int(v or 0) for v in response['rows'][0]]
            passed = values[0]==0 and values[3]==0 and (label!='v2-fixed' or values[4]==0)
            detail = dict(zip(['invalid_rows','tied_documents','different_baseline_picks','extra_documents','final_rule_mismatches'],values))
        else:
            passed = not response['rows']
            detail = {'differences':response['rows']}
        if name=='format_period_key':
            history = client.execute("SELECT statement_id,execution_status,error_message FROM system.query.history "
                "WHERE statement_text LIKE '/* run=dbx-d1111 act=prove step=direct-% consumer=billing */%' "
                "AND execution_status='FAILED' AND error_message LIKE '%YYYY-MM%' ORDER BY start_time LIMIT 1",step='gap-format-history')
            if not history['rows']:
                raise RuntimeError('missing tagged YYYY-MM failure evidence in query history')
            detail['literal_format_failure'] = history
            if label=='v1-direct':
                passed = False
        row = {'object':obj,'rung':name,'status':'pass' if passed else 'fail','detail':detail,
               'statement_id':response['statement_id'],'run_label':label,'measured_at':datetime.now(timezone.utc).isoformat()}
        client.execute(f"DELETE FROM {RESULTS} WHERE run_label={literal(label)} AND object={literal(obj)} AND rung={literal(name)}",step='parity-results')
        values = [label,obj,name,row['status'],json.dumps(detail),row['statement_id']]
        receipt = client.execute(f"INSERT INTO {RESULTS} VALUES ("+','.join(literal(v) for v in values)+",current_timestamp())",step='parity-results')
        row['receipt_statement_id'] = receipt['statement_id']
        results = [r for r in results if not(r['object']==obj and r['rung']==name)]
        results.append(row)
    directory.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(results,indent=2))
    return results
