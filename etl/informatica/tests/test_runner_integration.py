"""End-to-end runs of the exported workflows against a throwaway PostgreSQL database."""
import os
import subprocess
import sys

import pytest

from runner.repo import Repository
from runner.workflow import Integration

ESTATE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS = [os.path.join(ESTATE, "params", "sfx_d1110_daily.par")]
ORDER = [("SFX_CONTENT", "wf_SFX_CONTENT_DAILY"), ("SFX_BILLING", "wf_SFX_BILLING_DAILY"), ("SFX_AUDIT", "wf_SFX_AUDIT_DAILY")]


def q(conn, sql):
    return conn.execute(sql).fetchall()


def run_all(repo=None):
    repo = repo or Repository(os.path.join(ESTATE, "repository"))
    svc = Integration(repo, PARAMS)
    return {wf: svc.run_workflow(f, wf) for f, wf in ORDER}


def test_daily_batch_loads_every_area(warehouse):
    out = run_all()
    for wf, (status, results) in out.items():
        assert status == "SUCCEEDED", wf
        assert all(r["RUN_STATUS"] == "SUCCEEDED" for r in results.values()), wf
    assert "s_m_SFX_TEAM_MEMBER" not in out["wf_SFX_CONTENT_DAILY"][1]
    assert q(warehouse, "select count(*) from sfx_billing.customer_account")[0][0] == 40
    assert q(warehouse, "select count(*) from sfx_billing.invoice_hdr")[0][0] == 145
    rec = out["wf_SFX_BILLING_DAILY"][1]["s_m_SFX_INVOICE_HDR"]
    assert rec["FAILED_ROWS"] == 3                                  # Router DEFAULT group -> DD_REJECT
    assert os.path.exists(os.path.join(os.environ["PMROOTDIR"], "BadFiles", "invoice_hdr11.bad"))
    dr, cr = q(warehouse, "select sum(debit_amount), sum(credit_amount) from sfx_billing.gl_journal_line")[0]
    assert dr == cr and dr > 0
    assert q(warehouse, "select count(*) from sfx_billing.gl_journal_line where gl_account_id is null")[0][0] == 0
    assert q(warehouse, "select count(*) from sfx_documents.document")[0][0] == 154   # unknown owner filtered
    assert q(warehouse, "select count(*) from sfx_users.login_event")[0][0] == 412     # unknown outcomes dropped
    # trailing CHAR blanks are trimmed and two-argument IIF yields 0 for missing keys
    assert q(warehouse, "select count(*) from sfx_audit.audit_event where customer_id is null")[0][0] == 0
    assert q(warehouse, "select count(*) from sfx_audit.audit_event where customer_id = 0")[0][0] > 0
    assert q(warehouse, "select count(*) from sfx_documents.doc_share where access_level = 'OWNER'")[0][0] > 0


def test_rerun_upserts_and_appends(warehouse):
    run_all()
    before = q(warehouse, "select count(*), max(summary_id) from sfx_audit.audit_daily_summary")[0]
    out = run_all()
    billing = out["wf_SFX_BILLING_DAILY"][1]
    targets = {t["instance"]: t for t in billing["wklt_SFX_BILLING_STAGE.s_m_SFX_CUSTOMER_ACCOUNT"]["targets"]}
    assert targets["CUSTOMER_ACCOUNT"]["updated"] == 40 and targets["CUSTOMER_ACCOUNT"]["inserted"] == 0
    assert q(warehouse, "select count(*) from sfx_billing.invoice_hdr")[0][0] == 145
    assert q(warehouse, "select count(*) from sfx_billing.gl_journal_line")[0][0] == 441
    after = q(warehouse, "select count(*), min(summary_id), max(summary_id) from sfx_audit.audit_daily_summary")[0]
    assert after[0] == 2 * before[0]
    assert after[2] == before[1] + before[0]                          # sequence continues across runs
    log = open(os.path.join(os.environ["PMROOTDIR"], "WorkflowLogs", "wf_SFX_AUDIT_DAILY.log"), encoding="utf-8").read()
    assert "WRT_8170" in log and "audit_daily_summary" in log


def test_lookup_multiple_match_policy(warehouse):
    run_all()
    first = dict(q(warehouse, "select share_id, access_level from sfx_documents.doc_share"))
    repo = Repository(os.path.join(ESTATE, "repository"))
    repo.mapping("SFX_CONTENT", "m_SFX_DOC_SHARE").transformations["LKP_ROLE_GRANT"].attrs["Lookup policy on multiple match"] = "Use Last Value"
    status, _ = Integration(repo, PARAMS).run_workflow("SFX_CONTENT", "wf_SFX_CONTENT_DAILY")
    assert status == "SUCCEEDED"
    last = dict(q(warehouse, "select share_id, access_level from sfx_documents.doc_share"))
    assert set(first) == set(last)
    assert any(first[k] != last[k] for k in first)



def test_rerun_keeps_postings_of_unpostable_invoices(warehouse):
    run_all()
    # 7000248 is staged without a total, so FIL_POSTABLE drops it; a posting made earlier must survive the rerun
    warehouse.execute("insert into sfx_billing.gl_journal_line (journal_line_id, invoice_id, gl_account_id, posting_dt,"
                      " currency_cd, debit_amount, credit_amount, description)"
                      " select 7999999999999, 7000248, gl_account_id, date '2026-10-31', 'GBP', 120.00, 0, 'AR INV-2026-0012248'"
                      " from sfx_billing.gl_account where account_number = '1200'")
    warehouse.commit()
    before = q(warehouse, "select count(*) from sfx_billing.gl_journal_line")[0][0]
    svc = Integration(Repository(os.path.join(ESTATE, "repository")), PARAMS)
    assert svc.run_workflow("SFX_BILLING", "wf_SFX_BILLING_DAILY")[0] == "SUCCEEDED"
    assert q(warehouse, "select count(*) from sfx_billing.gl_journal_line where invoice_id = 7000248")[0][0] == 1
    assert q(warehouse, "select count(*) from sfx_billing.gl_journal_line")[0][0] == before

def test_pmcmd_cli_writes_logs(warehouse):
    env = dict(os.environ)
    res = subprocess.run([sys.executable, "-m", "runner", "startworkflow", "-f", "SFX_AUDIT", "wf_SFX_AUDIT_DAILY"],
                         cwd=ESTATE, env=env, capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "completed with status [SUCCEEDED]" in res.stdout
    root = os.environ["PMROOTDIR"]
    assert os.path.exists(os.path.join(root, "SessLogs", "s_m_SFX_AUDIT_EVENT.log"))
    hist = open(os.path.join(root, "REP_SESS_LOG.psv"), encoding="utf-8").read().splitlines()
    assert hist[0].startswith("SUBJECT_AREA|") and len(hist) == 5
    bad = subprocess.run([sys.executable, "-m", "runner", "startworkflow", "-f", "SFX_AUDIT", "wf_NOPE"], cwd=ESTATE, env=env,
                         capture_output=True, text=True)
    assert bad.returncode != 0



def test_mappings_selection_cli(warehouse):
    env = dict(os.environ, MAPPINGS="m_SFX_STG_INVOICE_HDR,m_SFX_GL_JOURNAL_LINE")
    res = subprocess.run([sys.executable, "-m", "runner", "startworkflow", "-f", "SFX_BILLING", "wf_SFX_BILLING_DAILY"],
                         cwd=ESTATE, env=env, capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "(2/2 sessions succeeded)" in res.stdout
    assert "[s_m_SFX_PAYMENT]: mapping not selected by MAPPINGS; skipped." in res.stdout
    res = subprocess.run([sys.executable, "-m", "runner", "startworkflow", "-f", "SFX_AUDIT", "wf_SFX_AUDIT_DAILY"],
                         cwd=ESTATE, env=env, capture_output=True, text=True)
    assert res.returncode == 0 and "not started" in res.stdout, res.stdout + res.stderr

@pytest.mark.parametrize("folder,wf", ORDER)
def test_listobjects(folder, wf):
    res = subprocess.run([sys.executable, "-m", "runner", "listobjects", "-f", folder], cwd=ESTATE, capture_output=True, text=True)
    assert res.returncode == 0 and wf in res.stdout
