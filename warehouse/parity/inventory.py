"""Read the exported estate without modifying the repository exports."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[2]
ESTATE = ROOT / "etl/informatica"
BOOTSTRAP = ESTATE / "tests/fixture/bootstrap.sql"


def table_definitions():
    return {f"{schema}.{table}": body.strip() for schema, table, body in re.findall(
        r"CREATE TABLE IF NOT EXISTS (\w+)\.(\w+)\s*\((.*?)\);",
        BOOTSTRAP.read_text(), re.S)}


def target_relation(name):
    matches = [table for table in table_definitions() if table.split('.')[1] == name]
    if len(matches) != 1:
        raise ValueError(f'No unique bootstrap target: {name}')
    return matches[0]


def inventory(repository=None, overrides=None):
    repository = repository or ESTATE / "repository"
    overrides = overrides or Path(__file__).parent / "mappings"
    definitions = table_definitions()
    result = []
    for folder in sorted(repository.iterdir()):
        if not folder.is_dir():
            continue
        sessions = {}
        for path in sorted(folder.glob("wf_*.XML")):
            doc = ET.parse(path)
            workflow = doc.find(".//WORKFLOW").get("NAME")
            for session in doc.findall(".//SESSION"):
                sessions[session.get("MAPPINGNAME")] = (session.get("NAME"), workflow)
        config_path = overrides / (folder.name.lower() + ".yml")
        config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
        config = config or {}
        if not isinstance(config, dict):
            raise ValueError(f"Expected mapping-name dictionary in {config_path}")
        for path in sorted((folder / "mappings").glob("*.XML")):
            doc = ET.parse(path)
            mapping = doc.find(".//MAPPING").get("NAME")
            target = doc.find(".//TARGET")
            name = target.get("NAME")
            keys = [f.get("NAME") for f in target.findall("TARGETFIELD")
                    if f.get("KEYTYPE") == "PRIMARY KEY"]
            if not keys:
                body = definitions[target_relation(name)]
                keys = re.findall(r"(\w+)\s+[^,\n]*PRIMARY KEY", body)
            session, workflow = sessions[mapping]
            area = folder.name.removeprefix("SFX_")
            sources = sorted({(s.get("OWNERNAME") + "." if s.get("OWNERNAME") else "")
                              + s.get("NAME") for s in doc.findall(".//SOURCE")}
                             | {a.get("VALUE") for a in doc.findall(".//TABLEATTRIBUTE")
                                if a.get("NAME") == "Lookup table name" and a.get("VALUE")})
            row = dict(folder=folder.name, mapping=mapping, workflow=workflow,
                       session=session, source_objects=sources, target_table=name,
                       dbt_model=f"pc_{area.lower()}__{name.lower()}",
                       after_table=f"PC_{area}.{name}", before_table=f"PC_BEFORE.{name}",
                       key_columns=keys, exclude_columns={},
                       patterns=sorted({t.get("TYPE") for t in doc.findall(".//TRANSFORMATION")}))
            changes = config.get(mapping, {})
            allowed = {"key_columns", "exclude_columns", "dbt_model", "after_table",
                       "before_table", "session", "workflow", "patterns"}
            if not isinstance(changes, dict) or set(changes) - allowed:
                raise ValueError(f"Invalid overrides for {mapping}")
            row.update(changes)
            excluded = row["exclude_columns"]
            if not isinstance(excluded, dict) or any(not isinstance(v, str) or not v.strip()
                                                     for v in excluded.values()):
                raise ValueError(f"Exclusions require explicit reasons: {mapping}")
            result.append(row)
        unknown = set(config) - {r["mapping"] for r in result if r["folder"] == folder.name}
        if unknown:
            raise ValueError(f"Unknown mappings in {config_path}: {sorted(unknown)}")
    return result


def landing_sources():
    sources = {}
    for path in sorted((ESTATE / "repository").glob("*/wf_*.XML")):
        for ext in ET.parse(path).findall(".//SESSIONEXTENSION"):
            attrs = {a.get("NAME"): a.get("VALUE") for a in ext.findall("ATTRIBUTE")}
            directory = attrs.get("Source file directory")
            if directory:
                relative = directory.removeprefix("$PMSourceFileDir/").strip("/")
                area, table = relative.split("/")
                sources[table] = (area, relative + "/20261109.psv")
    return sources
