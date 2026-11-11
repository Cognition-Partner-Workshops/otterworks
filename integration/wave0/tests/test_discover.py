import hashlib
import json

import pytest
import yaml

from integration.wave0.discover import discover, main


@pytest.fixture
def package(tmp_path):
    target, corpus = tmp_path / "target", tmp_path / "corpus"
    module = target / "fees-billing"
    verification = module / "verification"
    verification.mkdir(parents=True)
    faults = module / "src/test/resources/packages/fees/faults"
    faults.mkdir(parents=True)
    source = corpus / "fees-billing.fee-posting/flow.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"inputs": {}, "expected": {}}')
    definitions = faults / "supplemental.yaml"
    definitions.write_text(yaml.safe_dump({"version": 1, "flows": {
        "fees-billing.fee-posting": {
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "faults": {"broker-kill": {"after_message": 1, "identity_header": "requestId"}}
        }}}))
    lock = faults / "sha256.json"
    lock.write_text(json.dumps({"supplemental.yaml":
                               hashlib.sha256(definitions.read_bytes()).hexdigest()}))
    manifest = verification / "fees.yaml"
    doc = {"version": 1, "package": "fees", "module": "fees-billing",
           "flows": [{"id": "fees-billing.fee-posting", "status": "matched-required",
                      "evidence": ["source concrete queue starter"]}],
           "faults": {"definitions": "supplemental.yaml", "lock": "sha256.json"}}
    manifest.write_text(yaml.safe_dump(doc))
    return target, corpus, manifest, doc, definitions, lock


def test_empty(tmp_path, capsys):
    assert main(["--target", str(tmp_path), "--corpus", str(tmp_path)]) == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == {"include": []}
    assert "no packages selected" in out.err


def test_selected(package):
    target, corpus, *_ = package
    result = discover(target, corpus)
    assert result[0]["flows"] == ["fees-billing.fee-posting"]
    assert result[0]["module"] == "fees-billing"


@pytest.mark.parametrize("status", ["held", "amber"])
def test_status(package, status):
    target, corpus, manifest, doc, *_ = package
    doc["flows"][0]["status"] = status
    manifest.write_text(yaml.safe_dump(doc))
    result = discover(target, corpus)[0]
    assert result["flows"] == ([] if status == "held" else ["fees-billing.fee-posting"])


@pytest.mark.parametrize("mutation", ["module", "status", "evidence", "unknown", "duplicate",
                                    "escape", "hash", "source", "fields"])
def test_invalid(package, mutation):
    target, corpus, manifest, doc, definitions, lock = package
    if mutation == "module":
        doc["module"] = "payments"
    elif mutation == "status":
        doc["flows"][0]["status"] = "skip"
    elif mutation == "evidence":
        doc["flows"][0]["evidence"] = []
    elif mutation == "unknown":
        doc["flows"][0]["id"] = "fees-billing.nonexistent"
    elif mutation == "duplicate":
        doc["flows"].append(doc["flows"][0])
    elif mutation == "escape":
        doc["faults"]["definitions"] = "../outside.yaml"
    elif mutation == "hash":
        definitions.write_text("tampered")
    elif mutation == "source":
        (corpus / "fees-billing.fee-posting/flow.json").write_text("changed")
    else:
        doc["unexpected"] = True
    manifest.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError):
        discover(target, corpus)


def test_cli_failure(package, capsys):
    target, corpus, _, _, _, lock = package
    lock.write_text("{}")
    assert main(["--target", str(target), "--corpus", str(corpus)]) == 1
    assert "discovery failed" in capsys.readouterr().err


@pytest.mark.parametrize("path", ["absolute", "traversal"])
def test_nonrelative_paths(package, path):
    target, corpus, manifest, doc, definitions, _ = package
    doc["faults"]["definitions"] = (str(definitions) if path == "absolute"
                                      else "../faults/supplemental.yaml")
    manifest.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError, match="package-relative"):
        discover(target, corpus)


def test_missing_roots(tmp_path):
    with pytest.raises(ValueError, match="directories must exist"):
        discover(tmp_path / "missing", tmp_path)
