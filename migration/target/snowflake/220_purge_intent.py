"""PURGE_INTENT(run_id, as_of, namespace): RETENTION_PKG.PURGE_ELIGIBLE without the deletes.

Snowpark Python handler of the MIG.PURGE_INTENT procedure (registered, with this file's text inlined, by
220_purge_intent.sql). It records in MIG.PURGE_INTENT the rows PURGE_ELIGIBLE would have destroyed - every FILEAUD
child of an eligible parent, then the DOCARCH parent, in ARCH_KEY order - and returns the parent count (the
procedure's p_purged). It never deletes, truncates or drops anything: destruction stays with the migration engine.

Selection = PURGE_ELIGIBLE's cursor over ARCH.*: V_POLICY_LINEAGE.IN_CLOSED_SCHEDULE = 1, LEGAL_HOLD_FLAG = 'N',
LAST_ACCESS_TS < CUTOFF_TS(as_of), per NAMESPACE, all of it (no ROWNUM batch). Errors are the package codes:
-20001 the call cannot be recorded (no run_id, or run_id already recorded for another as-of date), -20002 / -20003
a non-held row whose RETENTION_CLASS does not resolve (Oracle's FK makes that impossible there; Snowflake does not
enforce FKs, so the procedure refuses instead of guessing). -20004 cannot arise: DISPOSITION_DT is not read.
"""

SCHEDULE_CODE = "CLSD7Y"
DEFAULT_AS_OF = "2026-01-01"

ERR_CONFIRM = -20001
ERR_UNKNOWN_CODE = -20002
ERR_CYCLE = -20003

PRIOR_SQL = """
SELECT COUNT_IF(TABLE_NAME = 'DOCARCH'), MIN(AS_OF_DT), MAX(AS_OF_DT)
  FROM MIG.PURGE_INTENT
 WHERE RUN_ID = ? AND (? IS NULL OR NAMESPACE = ?)
"""

UNRESOLVED_SQL = """
SELECT d.NAMESPACE, d.RETENTION_CLASS, r.STATUS, r.UNKNOWN_CODE
  FROM ARCH.DOCARCH d
  LEFT JOIN ARCH.V_POLICY_RESOLUTION r ON r.NAMESPACE = d.NAMESPACE AND r.POLICY_KEY = RTRIM(d.RETENTION_CLASS)
 WHERE (? IS NULL OR d.NAMESPACE = ?)
   AND COALESCE(d.LEGAL_HOLD_FLAG, 'N') <> 'Y'
   AND r.STATUS IS DISTINCT FROM 'RESOLVED'
 ORDER BY d.NAMESPACE, d.RETENTION_CLASS
 LIMIT 1
"""

INSERT_SQL = """
INSERT INTO MIG.PURGE_INTENT (RUN_ID, NAMESPACE, INTENT_SEQ, TABLE_NAME, SOURCE_KEY, ARCH_KEY, SOR_CLASS,
                              SCHEDULE_CODE, REASON_CODE, AS_OF_DT, CUTOFF_TS)
WITH PARENTS AS (
    SELECT d.NAMESPACE, d.ARCH_KEY, d.SOURCE_KEY, l.SOR_CODE,
           ARCH.DISPOSITION_CODE_OF(
               d.LEGAL_HOLD_FLAG, r.DISPOSITION_ACTION,
               IFF(r.DISPOSITION_ACTION = 'PERM', NULL,
                   ARCH.ADD_RETENTION_YEARS(ARCH.TS9(d.LAST_ACCESS_TS, d.LAST_ACCESS_TS_NANOS_TAIL), r.RETENTION_YEARS)),
               ?::DATE) AS REASON_CODE
      FROM ARCH.DOCARCH d
      JOIN ARCH.V_POLICY_LINEAGE l ON l.NAMESPACE = d.NAMESPACE AND RTRIM(l.POLICY_CODE) = RTRIM(d.RETENTION_CLASS)
      JOIN ARCH.V_POLICY_RESOLUTION r ON r.NAMESPACE = d.NAMESPACE AND r.POLICY_KEY = RTRIM(d.RETENTION_CLASS)
     WHERE l.IN_CLOSED_SCHEDULE = 1
       AND d.LEGAL_HOLD_FLAG = 'N'
       AND ARCH.TS9(d.LAST_ACCESS_TS, d.LAST_ACCESS_TS_NANOS_TAIL) < ARCH.CUTOFF_TS(?::DATE)
       AND (? IS NULL OR d.NAMESPACE = ?)
),
INTENTS AS (
    SELECT p.NAMESPACE, p.ARCH_KEY, 0 AS PHASE, f.AUDIT_KEY AS CHILD_KEY, 'FILEAUD' AS TABLE_NAME,
           f.SOURCE_KEY, p.SOR_CODE, p.REASON_CODE
      FROM PARENTS p
      JOIN ARCH.FILEAUD f ON f.NAMESPACE = p.NAMESPACE AND RTRIM(f.ARCH_KEY) = RTRIM(p.ARCH_KEY)
    UNION ALL
    SELECT p.NAMESPACE, p.ARCH_KEY, 1, '', 'DOCARCH', p.SOURCE_KEY, p.SOR_CODE, p.REASON_CODE
      FROM PARENTS p
)
SELECT ?, NAMESPACE,
       ROW_NUMBER() OVER (PARTITION BY NAMESPACE ORDER BY RPAD(ARCH_KEY, 16), PHASE, CHILD_KEY),
       TABLE_NAME, SOURCE_KEY, ARCH_KEY, SOR_CODE, ?, REASON_CODE, ?::DATE, ARCH.CUTOFF_TS(?::DATE)
  FROM INTENTS
"""


class PurgeIntentError(Exception):
    """Carries a RETENTION_PKG error code; the text is "<code>: <message>" like RAISE_APPLICATION_ERROR."""

    def __init__(self, code: int, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def _first(session, sql: str, params: list) -> tuple:
    rows = session.sql(sql, params=params).collect()
    return tuple(rows[0]) if rows else ()


def purge_intent(session, run_id, as_of=DEFAULT_AS_OF, namespace=None) -> int:
    if run_id is None or not str(run_id).strip():
        raise PurgeIntentError(ERR_CONFIRM, "RETENTION_PKG.PURGE_INTENT: run_id missing")
    if as_of is None:
        return 0
    as_of_text = str(as_of)[:10]

    recorded, first_as_of, last_as_of = _first(session, PRIOR_SQL, [run_id, namespace, namespace])
    if recorded or first_as_of is not None:
        if str(first_as_of)[:10] == as_of_text and str(last_as_of)[:10] == as_of_text:
            return int(recorded)
        raise PurgeIntentError(
            ERR_CONFIRM,
            f"RETENTION_PKG.PURGE_INTENT: run {run_id} already recorded as_of={str(first_as_of)[:10]}",
        )

    bad = _first(session, UNRESOLVED_SQL, [namespace, namespace])
    if bad:
        _, code, status, unknown_code = bad
        if status == "CYCLE":
            raise PurgeIntentError(ERR_CYCLE, f'RETENTION_PKG: successor chain from "{code}" does not terminate')
        shown = unknown_code if unknown_code is not None else str(code or "").ljust(4)[:4]
        raise PurgeIntentError(ERR_UNKNOWN_CODE, f'RETENTION_PKG: unknown policy code "{shown}"')

    session.sql(
        INSERT_SQL,
        params=[as_of_text, as_of_text, namespace, namespace, run_id, SCHEDULE_CODE, as_of_text, as_of_text],
    ).collect()
    recorded, _, _ = _first(session, PRIOR_SQL, [run_id, namespace, namespace])
    return int(recorded)
