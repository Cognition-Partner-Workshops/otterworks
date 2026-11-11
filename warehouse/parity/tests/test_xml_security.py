"""Export files are data: entity declarations must never be expanded."""
import importlib

import pytest
from defusedxml.common import EntitiesForbidden

inventory_module = importlib.import_module("parity.inventory")

WORKFLOW = '''<POWERMART><WORKFLOW NAME="wf_demo">
<SESSION NAME="s_demo" MAPPINGNAME="m_demo"/>
<SESSIONEXTENSION><ATTRIBUTE NAME="Source file directory"
VALUE="$PMSourceFileDir/billing/payment"/></SESSIONEXTENSION>
</WORKFLOW></POWERMART>'''
MAPPING = '''<POWERMART><MAPPING NAME="m_demo">
<TARGET NAME="PAYMENT"><TARGETFIELD NAME="PAYMENT_ID" KEYTYPE="PRIMARY KEY"/>
</TARGET><SOURCE NAME="PAYMENT"/></MAPPING></POWERMART>'''


@pytest.fixture
def exports(tmp_path, monkeypatch):
    folder = tmp_path / "repository" / "SFX_BILLING"
    (folder / "mappings").mkdir(parents=True)
    workflow = folder / "wf_demo.XML"
    mapping = folder / "mappings" / "m_demo.XML"
    workflow.write_text(WORKFLOW)
    mapping.write_text(MAPPING)
    monkeypatch.setattr(inventory_module, "ESTATE", tmp_path)
    return tmp_path, workflow, mapping


@pytest.mark.parametrize("entry,document", [
    ("inventory", "workflow"), ("inventory", "mapping"),
    ("landing_sources", "workflow"),
])
def test_export_entities_are_rejected(exports, entry, document):
    root, workflow, mapping = exports
    path = workflow if document == "workflow" else mapping
    # A small internal entity proves the boundary without allocating a bomb.
    prefix = '<!DOCTYPE POWERMART [<!ENTITY audit "expanded">]>'
    path.write_text(prefix + path.read_text().replace(
        "</POWERMART>", "<DESCRIPTION>&audit;</DESCRIPTION></POWERMART>"))
    with pytest.raises(EntitiesForbidden):
        if entry == "inventory":
            inventory_module.inventory(repository=root / "repository")
        else:
            inventory_module.landing_sources()


def test_normal_exports_and_external_doctype_still_work(exports):
    root, workflow, mapping = exports
    # PowerCenter exports commonly name a DTD; it must not be fetched.
    doctype = '<!DOCTYPE POWERMART SYSTEM "file:///nonexistent/pmrep.dtd">'
    for path in (workflow, mapping):
        path.write_text(doctype + path.read_text())
    overrides = root / "overrides"
    overrides.mkdir()
    rows = inventory_module.inventory(repository=root / "repository", overrides=overrides)
    assert [row["mapping"] for row in rows] == ["m_demo"]
    assert inventory_module.landing_sources() == {"payment": ("billing", "billing/payment/20261109.psv")}
