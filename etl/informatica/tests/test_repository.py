import csv
import datetime as dt
import os
from collections import Counter

import yaml

from runner.params import resolve
from runner.repo import Repository
from runner.workflow import select_mappings

ESTATE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = Repository(os.path.join(ESTATE, "repository"))
TYPES = {"Source Qualifier", "Expression", "Filter", "Lookup Procedure", "Aggregator", "Router", "Update Strategy", "Sequence"}


def test_export_inventory():
    assert len(REPO.mappings) == 20
    assert len(REPO.workflows) == 3
    assert REPO.repository_name == "REP_SFX_PROD"
    folders = Counter(f for f, _ in REPO.mappings)
    assert folders["SFX_BILLING"] >= 6
    for key in REPO.mappings:
        m = REPO.mapping(*key)
        assert m.sources and m.targets, key
        assert (key[0], f"s_{key[1]}") in REPO.sessions


def test_all_transformation_types_are_used():
    used = {t.type for m in REPO.mappings.values() for t in m.transformations.values()}
    assert TYPES <= used


def test_lookup_policies_and_router_defaults():
    policies = {t.attr("Lookup policy on multiple match") for m in REPO.mappings.values()
                for t in m.transformations.values() if t.type == "Lookup Procedure"}
    assert "Use First Value" in policies
    for m in REPO.mappings.values():
        for t in m.transformations.values():
            if t.type == "Router":
                assert any(g["TYPE"] == "OUTPUT/DEFAULT" for g in t.groups)


def test_workflow_links_reference_tasks():
    for wf in list(REPO.workflows.values()) + list(REPO.worklets.values()):
        for lk in wf.links:
            assert lk.from_task in wf.tasks and lk.to_task in wf.tasks
        for t in wf.tasks.values():
            if t.tasktype == "Session":
                assert (wf.folder, t.taskname) in REPO.sessions
            if t.tasktype == "Worklet":
                assert (wf.folder, t.taskname) in REPO.worklets
    billing = REPO.workflows[("SFX_BILLING", "wf_SFX_BILLING_DAILY")]
    assert {t.tasktype for t in billing.tasks.values()} >= {"Start", "Worklet", "Session", "Decision", "Email"}


def test_parameter_resolution():
    files = [os.path.join(ESTATE, "params", "sfx_d1110_daily.par")]
    p = resolve(files, "SFX_AUDIT", "wf_SFX_AUDIT_DAILY", "s_m_SFX_AUDIT_EVENT_ARCHIVE")
    assert p["$$ARCHIVE_DAYS"] == "2555"
    assert resolve(files, "SFX_AUDIT", "wf_SFX_AUDIT_DAILY")["$$ARCHIVE_DAYS"] == "730"
    assert p["$DBConnection_TGT"] == "TD_SFX_EDW"


def test_run_history_window():
    with open(os.path.join(ESTATE, "logs", "REP_SESS_LOG.psv"), encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="|"))
    starts = [dt.datetime.fromisoformat(r["ACTUAL_START"]) for r in rows]
    assert (max(starts) - min(starts)).days >= 115
    last = {}
    for r, s in zip(rows, starts):
        last[(r["SUBJECT_AREA"], r["MAPPING_NAME"])] = max(s, last.get((r["SUBJECT_AREA"], r["MAPPING_NAME"]), s))
    assert set(last) == set(REPO.mappings)
    cutoff = dt.datetime(2026, 11, 10) - dt.timedelta(days=90)
    assert len([k for k, v in last.items() if v < cutoff]) == 2


def test_licence_covers_every_mapping():
    with open(os.path.join(ESTATE, "licence.yaml"), encoding="utf-8") as fh:
        lic = yaml.safe_load(fh)
    listed = {(f, m) for f, ms in lic["mapping_features"].items() for m in ms}
    assert listed == set(REPO.mappings)
    for ms in lic["mapping_features"].values():
        for feats in ms.values():
            assert set(feats) <= set(lic["features"])


def test_workflow_exports_are_self_contained():
    import glob
    import xml.etree.ElementTree as ET

    files = sorted(glob.glob(os.path.join(ESTATE, "repository", "*", "wf_*.XML")))
    assert len(files) == 3
    for path in files:
        folder = ET.parse(path).getroot().find("REPOSITORY/FOLDER")
        assert len(folder.findall("WORKFLOW")) == 1, path
        mappings = {m.get("NAME") for m in folder.findall("MAPPING")}
        assert {s.get("MAPPINGNAME") for s in folder.findall("SESSION")} == mappings, path


def test_mapping_selection():
    assert select_mappings(REPO, "") is None
    assert select_mappings(REPO, "all") is None
    assert select_mappings(REPO, "20") is None
    assert len(select_mappings(REPO, "3")) == 3
    assert select_mappings(REPO, "m_SFX_GL_JOURNAL_LINE") == {"m_SFX_GL_JOURNAL_LINE"}
    assert select_mappings(REPO, "SFX_PAYMENT, m_SFX_*INVOICE*") == {
        "m_SFX_PAYMENT", "m_SFX_STG_INVOICE_HDR", "m_SFX_INVOICE_HDR", "m_SFX_INVOICE_LINE"}
    try:
        select_mappings(REPO, "m_NOPE")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown mapping accepted")
