#!/usr/bin/env python3
"""Synthetic CUSTOMER_MASTER / CUSTOMER_MASTER_HIST / ENTITY_ATTR_VALUE rows
for the w1-b02 fixture (LOCAL ORACLE FIXTURE ONLY).

200 customers (SYNTH-CUST-0000..0199) exercising the wide-table traps that can
still reconcile under recon:

- sparse columns: most of the 155 columns left NULL on most rows
- *_yn flags cycling Y/N/NULL across customers
- *_dt text dates as DD-MON-YY strings (always parseable -- see notes:
  unparseable strings stay raw under canonicalization and would be a
  legitimate Tier-3 diff, so they are exercised via the fault leg, not here)
- *_ids/*_csv as well-formed CSVs incl. NULL and single-item
- CHAR flags, sequence cust_seq_no, conversion_batch_no, copied amounts at
  NUMBER(14,2) edges
- 60 hist rows with HIST_DT 'DD-MON-YY HH24:MI:SS' strings
- ~600 EAV rows: CUSTOMER-type rows whose ENTITY_ID matches a seeded
  customer, plus non-CUSTOMER types (PLAN/TENANT) incl. ENTITY_IDs that match
  nothing (those load into the scoped entityAttrValue collection)

Idempotent: delete-then-insert of the SYNTH-* namespace. Fault support:
--inject-orphan-eav / --remove-orphan-eav plant/remove one CUSTOMER-type EAV
row whose ENTITY_ID matches no customer (legitimate Tier-1 embed FAIL).
Writes .migration/fixtures/w1-b02.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / ".migration" / "fixtures" / "w1-b02.json"

N_CUSTOMERS = 200
N_HIST = 60
N_EAV_CUSTOMER = 550
N_EAV_OTHER = 50
EAV_ID_BASE = 9200000
HIST_ID_BASE = 9100000
ORPHAN_EAV_ID = 9200999
ORPHAN_ENTITY_ID = "SYNTH-ORPHAN-GHOST"

MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
TENANTS = ["SYNTH-TEN-1", "SYNTH-TEN-2", "SYNTH-TEN-3"]
YN = ["Y", "N", None]
ATTR_NAMES = ["PORTAL_THEME", "TAX_REGION_OVERRIDE", "LANG_PREF",
              "PAPER_BILL", "BUDGET_BILL", "ACCOUNT_TAG"]
NON_CUST_TYPES = ["PLAN", "TENANT", "INVOICE"]


def _cust_row(i: int) -> list:
    """Full 155-column CUSTOMER_MASTER row for SYNTH-CUST-i."""
    cid = f"SYNTH-CUST-{i:04d}"
    row: list = [None] * 155
    col = {name: idx for idx, name in enumerate(CM_COLS.split(","))}
    def s(name, v):
        row[col[name]] = v
    s("cust_id", cid)
    s("cust_seq_no", 800000 + i)
    s("tenant_id", TENANTS[i % len(TENANTS)])
    s("cust_no", f"SC{i:05d}")
    s("cust_name", f"Synthetic Customer {i:04d}")
    s("cust_name_upper", f"SYNTHETIC CUSTOMER {i:04d}")
    s("legal_name", f"Synthetic Customer {i:04d} Ltd")
    s("status_cd", 10 if i % 11 else 999)
    s("sub_status_cd", 10 if i % 7 else None)
    s("cust_type_cd", 1 + i % 4)
    s("segment_cd", 1 + i % 3)
    s("tax_exempt_yn", YN[i % 3])
    s("credit_hold_yn", YN[(i + 1) % 3])
    s("dunning_exempt_yn", YN[(i + 2) % 3])
    s("vip_yn", "Y" if i % 25 == 0 else "N")
    s("cur_bal_amt", f"{i * 13}.{i % 100:02d}")
    s("past_due_amt", "0.00" if i % 6 else f"{i}.99")
    s("credit_limit_amt", f"{5000 + i * 10}.00")
    s("conversion_batch_no", 20260900 + (i % 3))
    s("row_version_no", i % 9)
    s("legacy_sys_key", f"MF{i:07d}")
    s("mainframe_acct_no", f"MA-{i:08d}")
    if i % 4 != 3:  # every 4th leaves all *_dt NULL
        s("signup_dt", f"{(i % 28) + 1:02d}-{MONTHS[i % 12]}-{20 + i % 7}")
        s("last_activity_dt", f"{(i % 27) + 1:02d}-{MONTHS[(i + 3) % 12]}-{25 + i % 2}")
    if i % 13 == 5:
        s("terminate_dt", "01-DEC-25")
    # repeating groups: phones, addresses, udfs
    for p in range(1, 5):
        if (i + p) % 4 != 0:
            s(f"phone{p}", f"+1-555-{i:04d}"[:12])
            s(f"phone{p}_type_cd", p if (i + p) % 9 else 999)
        if (i + p) % 5 != 0:
            s(f"addr_line_{p}", f"{i} Synthetic Ave L{p}")
    s("city", ["Springfield", "Riverton", "Fairview"][i % 3])
    s("state_cd", ["IL", "OH", "WA"][i % 3])
    s("zip", f"{60000 + i:05d}")
    s("country_cd", "US")
    s("mail_city", row[col["city"]])
    # flags: CHAR(1) -- Y/N/NULL pattern, never oddballs (canonicalizable)
    for fn in range(1, 21):
        s(f"flag_{fn:02d}", YN[(i + fn) % 3])
    for un in range(1, 41):
        if (i + un) % 6 == 0:
            s(f"udf_{un:02d}", f"udf-{un}-{i}")
    for an in range(1, 11):
        if (i + an) % 3 == 0:
            s(f"udf_amt_{an:02d}", f"{an}.{i % 100:02d}")
        if (i + an) % 7 == 0:
            s(f"udf_dt_{an:02d}", f"{an:02d}-{MONTHS[an % 12]}-24")
    # CSVs: well-formed only (a malformed item is a legit recon FAIL)
    s("related_acct_ids", f"RA-{i:05d},RA-{i:05d}-B" if i % 3 else None)
    s("child_acct_ids", f"CA-{i:05d}" if i % 5 == 0 else None)
    s("promo_codes_csv", "SAVE10,WELCOME" if i % 6 == 0 else None)
    s("email_1", f"cust{i:04d}@example.com")
    s("created_by", "w1-b02-seed")
    s("created_dt", dt.datetime(2026, 1, 1))
    s("updated_by", "w1-b02-seed")
    s("updated_dt", dt.datetime(2026, 6, 1))
    return row


def _hist_row(i: int) -> list:
    """Full 158-column CUSTOMER_MASTER_HIST row."""
    base = _cust_row(i % N_CUSTOMERS)
    row = [HIST_ID_BASE + i,
           f"{(i % 28) + 1:02d}-{MONTHS[i % 12]}-26 {i % 24:02d}:{(i * 7) % 60:02d}:{(i * 13) % 60:02d}",
           ["INS", "UPD", "DEL"][i % 3]] + base
    if i % 10 == 9:  # sparse hist row: most fields NULL
        for j in range(3, 158):
            if j % 4:
                row[j] = None
    return row


def _eav_row(i: int) -> list:
    eav_id = EAV_ID_BASE + i
    if i < N_EAV_CUSTOMER:
        etype, eid = "CUSTOMER", f"SYNTH-CUST-{i % N_CUSTOMERS:04d}"
    else:
        etype = NON_CUST_TYPES[i % 3]
        eid = (f"SYNTH-{etype}-{i % 7}" if i % 4
               else f"SYNTH-NOMATCH-{i}")     # points at nothing
    return [eav_id, etype, eid,
            ATTR_NAMES[i % len(ATTR_NAMES)] + ("" if i % 8 else f"_{i}"),
            f"value-{i}" if i % 6 else None,
            ["STR", "NUM", "DATE", None][i % 4],
            f"{(i % 28) + 1:02d}-{MONTHS[i % 12]}-26" if i % 5 else None]


CM_COLS = "cust_id,cust_seq_no,tenant_id,cust_no,cust_name,cust_name_upper,legal_name,dba_name,addr_line_1,addr_line_2,addr_line_3,addr_line_4,addr_line_5,addr_line_6,city,state_cd,zip,zip4,country_cd,mail_addr_line_1,mail_addr_line_2,mail_addr_line_3,mail_addr_line_4,mail_addr_line_5,mail_addr_line_6,mail_city,mail_state_cd,mail_zip,phone1,phone2,phone3,phone4,phone1_type_cd,phone2_type_cd,phone3_type_cd,phone4_type_cd,fax,email_1,email_2,email_3,signup_dt,last_activity_dt,last_invoice_dt,last_payment_dt,terminate_dt,status_cd,sub_status_cd,cust_type_cd,segment_cd,region_cd,territory_cd,channel_cd,rate_class_cd,tax_exempt_yn,credit_hold_yn,dunning_exempt_yn,vip_yn,cur_bal_amt,past_due_amt,ytd_billed_amt,ltd_billed_amt,ytd_paid_amt,credit_limit_amt,related_acct_ids,child_acct_ids,promo_codes_csv,contact_notes,legacy_sys_key,mainframe_acct_no,conversion_batch_no,flag_01,flag_02,flag_03,flag_04,flag_05,flag_06,flag_07,flag_08,flag_09,flag_10,flag_11,flag_12,flag_13,flag_14,flag_15,flag_16,flag_17,flag_18,flag_19,flag_20,udf_01,udf_02,udf_03,udf_04,udf_05,udf_06,udf_07,udf_08,udf_09,udf_10,udf_11,udf_12,udf_13,udf_14,udf_15,udf_16,udf_17,udf_18,udf_19,udf_20,udf_21,udf_22,udf_23,udf_24,udf_25,udf_26,udf_27,udf_28,udf_29,udf_30,udf_31,udf_32,udf_33,udf_34,udf_35,udf_36,udf_37,udf_38,udf_39,udf_40,udf_amt_01,udf_amt_02,udf_amt_03,udf_amt_04,udf_amt_05,udf_amt_06,udf_amt_07,udf_amt_08,udf_amt_09,udf_amt_10,udf_dt_01,udf_dt_02,udf_dt_03,udf_dt_04,udf_dt_05,udf_dt_06,udf_dt_07,udf_dt_08,udf_dt_09,udf_dt_10,created_by,created_dt,updated_by,updated_dt,row_version_no"
HM_COLS = "hist_id,hist_dt,hist_op," + CM_COLS


def connection(uri: str):
    """Declares the migration target for the offline run. MongoClient is lazy
    -- this opens no socket; the seeder only ever touches Oracle."""
    from pymongo import MongoClient
    return MongoClient(uri)


def _connect(dsn_override=None):
    import oracledb
    raw = os.environ.get("ORACLE_FIXTURE_DSN")
    if not raw:
        sys.exit("ORACLE_FIXTURE_DSN not set (JSON {user,password,dsn})")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _local import require_local_dsn
    dsn = json.loads(raw)
    easy = dsn_override or dsn["dsn"]
    require_local_dsn(easy)
    return oracledb.connect(user=dsn["user"], password=dsn["password"],
                            dsn=easy)


def _seed(conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM entity_attr_value WHERE entity_id LIKE 'SYNTH-%'")
    cur.execute("DELETE FROM customer_master_hist WHERE cust_id LIKE 'SYNTH-CUST-%'")
    cur.execute("DELETE FROM customer_master WHERE cust_id LIKE 'SYNTH-CUST-%'")
    cm_sql = """INSERT INTO customer_master (cust_id,cust_seq_no,tenant_id,cust_no,cust_name,cust_name_upper,legal_name,dba_name,addr_line_1,addr_line_2,addr_line_3,addr_line_4,addr_line_5,addr_line_6,city,state_cd,zip,zip4,country_cd,mail_addr_line_1,mail_addr_line_2,mail_addr_line_3,mail_addr_line_4,mail_addr_line_5,mail_addr_line_6,mail_city,mail_state_cd,mail_zip,phone1,phone2,phone3,phone4,phone1_type_cd,phone2_type_cd,phone3_type_cd,phone4_type_cd,fax,email_1,email_2,email_3,signup_dt,last_activity_dt,last_invoice_dt,last_payment_dt,terminate_dt,status_cd,sub_status_cd,cust_type_cd,segment_cd,region_cd,territory_cd,channel_cd,rate_class_cd,tax_exempt_yn,credit_hold_yn,dunning_exempt_yn,vip_yn,cur_bal_amt,past_due_amt,ytd_billed_amt,ltd_billed_amt,ytd_paid_amt,credit_limit_amt,related_acct_ids,child_acct_ids,promo_codes_csv,contact_notes,legacy_sys_key,mainframe_acct_no,conversion_batch_no,flag_01,flag_02,flag_03,flag_04,flag_05,flag_06,flag_07,flag_08,flag_09,flag_10,flag_11,flag_12,flag_13,flag_14,flag_15,flag_16,flag_17,flag_18,flag_19,flag_20,udf_01,udf_02,udf_03,udf_04,udf_05,udf_06,udf_07,udf_08,udf_09,udf_10,udf_11,udf_12,udf_13,udf_14,udf_15,udf_16,udf_17,udf_18,udf_19,udf_20,udf_21,udf_22,udf_23,udf_24,udf_25,udf_26,udf_27,udf_28,udf_29,udf_30,udf_31,udf_32,udf_33,udf_34,udf_35,udf_36,udf_37,udf_38,udf_39,udf_40,udf_amt_01,udf_amt_02,udf_amt_03,udf_amt_04,udf_amt_05,udf_amt_06,udf_amt_07,udf_amt_08,udf_amt_09,udf_amt_10,udf_dt_01,udf_dt_02,udf_dt_03,udf_dt_04,udf_dt_05,udf_dt_06,udf_dt_07,udf_dt_08,udf_dt_09,udf_dt_10,created_by,created_dt,updated_by,updated_dt,row_version_no
) VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12,:13,:14,:15,:16,:17,:18,:19,:20,:21,:22,:23,:24,:25,:26,:27,:28,:29,:30,:31,:32,:33,:34,:35,:36,:37,:38,:39,:40,:41,:42,:43,:44,:45,:46,:47,:48,:49,:50,:51,:52,:53,:54,:55,:56,:57,:58,:59,:60,:61,:62,:63,:64,:65,:66,:67,:68,:69,:70,:71,:72,:73,:74,:75,:76,:77,:78,:79,:80,:81,:82,:83,:84,:85,:86,:87,:88,:89,:90,:91,:92,:93,:94,:95,:96,:97,:98,:99,:100,:101,:102,:103,:104,:105,:106,:107,:108,:109,:110,:111,:112,:113,:114,:115,:116,:117,:118,:119,:120,:121,:122,:123,:124,:125,:126,:127,:128,:129,:130,:131,:132,:133,:134,:135,:136,:137,:138,:139,:140,:141,:142,:143,:144,:145,:146,:147,:148,:149,:150,:151,:152,:153,:154,:155)"""
    hm_sql = """INSERT INTO customer_master_hist (hist_id,hist_dt,hist_op,cust_id,cust_seq_no,tenant_id,cust_no,cust_name,cust_name_upper,legal_name,dba_name,addr_line_1,addr_line_2,addr_line_3,addr_line_4,addr_line_5,addr_line_6,city,state_cd,zip,zip4,country_cd,mail_addr_line_1,mail_addr_line_2,mail_addr_line_3,mail_addr_line_4,mail_addr_line_5,mail_addr_line_6,mail_city,mail_state_cd,mail_zip,phone1,phone2,phone3,phone4,phone1_type_cd,phone2_type_cd,phone3_type_cd,phone4_type_cd,fax,email_1,email_2,email_3,signup_dt,last_activity_dt,last_invoice_dt,last_payment_dt,terminate_dt,status_cd,sub_status_cd,cust_type_cd,segment_cd,region_cd,territory_cd,channel_cd,rate_class_cd,tax_exempt_yn,credit_hold_yn,dunning_exempt_yn,vip_yn,cur_bal_amt,past_due_amt,ytd_billed_amt,ltd_billed_amt,ytd_paid_amt,credit_limit_amt,related_acct_ids,child_acct_ids,promo_codes_csv,contact_notes,legacy_sys_key,mainframe_acct_no,conversion_batch_no,flag_01,flag_02,flag_03,flag_04,flag_05,flag_06,flag_07,flag_08,flag_09,flag_10,flag_11,flag_12,flag_13,flag_14,flag_15,flag_16,flag_17,flag_18,flag_19,flag_20,udf_01,udf_02,udf_03,udf_04,udf_05,udf_06,udf_07,udf_08,udf_09,udf_10,udf_11,udf_12,udf_13,udf_14,udf_15,udf_16,udf_17,udf_18,udf_19,udf_20,udf_21,udf_22,udf_23,udf_24,udf_25,udf_26,udf_27,udf_28,udf_29,udf_30,udf_31,udf_32,udf_33,udf_34,udf_35,udf_36,udf_37,udf_38,udf_39,udf_40,udf_amt_01,udf_amt_02,udf_amt_03,udf_amt_04,udf_amt_05,udf_amt_06,udf_amt_07,udf_amt_08,udf_amt_09,udf_amt_10,udf_dt_01,udf_dt_02,udf_dt_03,udf_dt_04,udf_dt_05,udf_dt_06,udf_dt_07,udf_dt_08,udf_dt_09,udf_dt_10,created_by,created_dt,updated_by,updated_dt,row_version_no
) VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12,:13,:14,:15,:16,:17,:18,:19,:20,:21,:22,:23,:24,:25,:26,:27,:28,:29,:30,:31,:32,:33,:34,:35,:36,:37,:38,:39,:40,:41,:42,:43,:44,:45,:46,:47,:48,:49,:50,:51,:52,:53,:54,:55,:56,:57,:58,:59,:60,:61,:62,:63,:64,:65,:66,:67,:68,:69,:70,:71,:72,:73,:74,:75,:76,:77,:78,:79,:80,:81,:82,:83,:84,:85,:86,:87,:88,:89,:90,:91,:92,:93,:94,:95,:96,:97,:98,:99,:100,:101,:102,:103,:104,:105,:106,:107,:108,:109,:110,:111,:112,:113,:114,:115,:116,:117,:118,:119,:120,:121,:122,:123,:124,:125,:126,:127,:128,:129,:130,:131,:132,:133,:134,:135,:136,:137,:138,:139,:140,:141,:142,:143,:144,:145,:146,:147,:148,:149,:150,:151,:152,:153,:154,:155,:156,:157,:158)"""
    for i in range(N_CUSTOMERS):
        cur.execute(cm_sql, _cust_row(i))
    for i in range(N_HIST):
        cur.execute(hm_sql, _hist_row(i))
    for i in range(N_EAV_CUSTOMER + N_EAV_OTHER):
        r = _eav_row(i)
        cur.execute(
            "INSERT INTO entity_attr_value (eav_id,entity_type,entity_id,"
            "attr_name,attr_value,attr_type,created_dt) VALUES "
            "(:1,:2,:3,:4,:5,:6,:7)", r)
    conn.commit()
    cur.close()


def _counts(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM customer_master")
    cm = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM customer_master_hist")
    hm = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM entity_attr_value")
    ev = cur.fetchone()[0]
    cur.close()
    return {"CUSTOMER_MASTER": cm, "CUSTOMER_MASTER_HIST": hm,
            "ENTITY_ATTR_VALUE": ev}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=None,
                    help="override the dsn field of ORACLE_FIXTURE_DSN "
                         "(spell the fixture host out, e.g. 127.0.0.1:1521/FREEPDB1)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--inject-orphan-eav", action="store_true",
                   help="plant one CUSTOMER-type EAV row whose ENTITY_ID "
                        "matches no customer (fault injection)")
    g.add_argument("--remove-orphan-eav", action="store_true")
    args = ap.parse_args()
    connection(os.environ.get(
        "MONGO_LOCAL_URI", "mongodb://127.0.0.1:27017/ow_billing_offline"))
    conn = _connect(args.dsn)
    cur = conn.cursor()
    if args.inject_orphan_eav:
        cur.execute(
            "INSERT INTO entity_attr_value (eav_id,entity_type,entity_id,"
            "attr_name,attr_value,attr_type,created_dt) VALUES "
            "(:1,'CUSTOMER',:2,'ORPHAN_PROBE','x','STR','01-JAN-26')",
            (ORPHAN_EAV_ID, ORPHAN_ENTITY_ID))
        conn.commit()
        print(f"injected orphan CUSTOMER EAV (eav_id band {EAV_ID_BASE}+)")
        return 0
    if args.remove_orphan_eav:
        cur.execute("DELETE FROM entity_attr_value WHERE eav_id = :1",
                    (ORPHAN_EAV_ID,))
        conn.commit()
        print("removed orphan CUSTOMER EAV")
        return 0
    _seed(conn)
    counts = _counts(conn)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "source": "oracle fixture FIXTURE@FREEPDB1 built from services/legacy-billing/db/oracle DDL",
        "method": "synthetic",
        "masked_columns": [],
        "produced_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "produced_by": "migration/mongo/fixtures/seed_customers.py",
        "row_counts": counts,
    }, indent=2) + "\n")
    print(f"customers: seeded {N_CUSTOMERS} customers, {N_HIST} hist, "
          f"{N_EAV_CUSTOMER + N_EAV_OTHER} eav (table counts {counts})")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
