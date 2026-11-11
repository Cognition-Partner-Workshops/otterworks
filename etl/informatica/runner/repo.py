"""Reads PowerCenter repository exports (POWERMART XML) into plain objects."""

from __future__ import annotations

import glob
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class Field:
    name: str
    datatype: str
    precision: int = 0
    scale: int = 0
    nullable: bool = True
    keytype: str = "NOT A KEY"
    porttype: str = ""
    expression: str = ""
    expressiontype: str = ""
    group: str = ""
    ref_field: str = ""
    default: str = ""
    attrs: dict = field(default_factory=dict)

    @property
    def is_input(self):
        return "INPUT" in self.porttype

    @property
    def is_output(self):
        return "OUTPUT" in self.porttype

    @property
    def is_variable(self):
        return self.porttype == "LOCAL VARIABLE" or self.porttype == "VARIABLE"

    @property
    def is_lookup(self):
        return "LOOKUP" in self.porttype

    @property
    def is_return(self):
        return "RETURN" in self.porttype


@dataclass
class Source:
    name: str
    dbdname: str
    databasetype: str
    owner: str
    fields: list
    flatfile: dict = field(default_factory=dict)

    @property
    def is_flatfile(self):
        return self.databasetype == "Flat File"


@dataclass
class Target:
    name: str
    databasetype: str
    fields: list

    @property
    def keys(self):
        return [f.name for f in self.fields if "PRIMARY" in f.keytype]


@dataclass
class Transformation:
    name: str
    type: str
    fields: list
    attrs: dict
    groups: list = field(default_factory=list)

    def attr(self, name, default=""):
        return self.attrs.get(name, default)


@dataclass
class Instance:
    name: str
    transformation_name: str
    transformation_type: str
    type: str
    associated_sources: list = field(default_factory=list)


@dataclass
class Connector:
    from_instance: str
    from_field: str
    to_instance: str
    to_field: str


@dataclass
class Mapping:
    name: str
    folder: str
    transformations: dict
    instances: dict
    connectors: list
    variables: dict
    load_order: list
    sources: dict
    targets: dict
    path: str = ""


@dataclass
class SessionExtension:
    sinstance: str
    type: str
    subtype: str
    attrs: dict
    connection_variable: str = ""
    connection_name: str = ""


@dataclass
class Session:
    name: str
    mapping: str
    folder: str
    attrs: dict
    extensions: list

    def ext_for(self, instance, kind=None):
        for e in self.extensions:
            if e.sinstance == instance and (kind is None or e.type == kind):
                return e
        return None


@dataclass
class TaskInstance:
    name: str
    taskname: str
    tasktype: str
    enabled: bool
    fail_parent: bool
    treat_input_as_and: bool
    attrs: dict = field(default_factory=dict)


@dataclass
class Link:
    from_task: str
    to_task: str
    condition: str


@dataclass
class Workflow:
    name: str
    folder: str
    tasks: dict
    links: list
    attrs: dict
    server: str = ""


def _attrs(el, tag="ATTRIBUTE"):
    return {a.get("NAME"): a.get("VALUE", "") for a in el.findall(tag)}


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _field(el):
    return Field(
        name=el.get("NAME"),
        datatype=(el.get("DATATYPE") or "").lower(),
        precision=_int(el.get("PRECISION")),
        scale=_int(el.get("SCALE")),
        nullable=el.get("NULLABLE", "NULL") != "NOTNULL",
        keytype=el.get("KEYTYPE", "NOT A KEY"),
        porttype=el.get("PORTTYPE", ""),
        expression=el.get("EXPRESSION", ""),
        expressiontype=el.get("EXPRESSIONTYPE", ""),
        group=el.get("GROUP", ""),
        ref_field=el.get("REF_FIELD", ""),
        default=el.get("DEFAULTVALUE", ""),
        attrs=_attrs(el, "FIELDATTRIBUTE"),
    )


def _transformation(el):
    return Transformation(
        name=el.get("NAME"),
        type=el.get("TYPE"),
        fields=[_field(f) for f in el.findall("TRANSFORMFIELD")],
        attrs=_attrs(el, "TABLEATTRIBUTE"),
        groups=[dict(g.attrib) for g in el.findall("GROUP")],
    )


class Repository:
    """All folders found under a repository export directory."""

    def __init__(self, root):
        self.root = root
        self.sources: dict = {}
        self.targets: dict = {}
        self.transformations: dict = {}
        self.mappings: dict = {}
        self.sessions: dict = {}
        self.workflows: dict = {}
        self.worklets: dict = {}
        self.repository_name = ""
        files = sorted(glob.glob(os.path.join(root, "**", "*.XML"), recursive=True))
        files += sorted(glob.glob(os.path.join(root, "**", "*.xml"), recursive=True))
        for path in dict.fromkeys(files):
            self._load(path)

    def _load(self, path):
        tree = ET.parse(path)
        pm = tree.getroot()
        for rep in pm.findall("REPOSITORY"):
            self.repository_name = rep.get("NAME", "")
            for folder in rep.findall("FOLDER"):
                self._load_folder(folder, path)

    def _load_folder(self, fel, path):
        fname = fel.get("NAME")
        for s in fel.findall("SOURCE"):
            ff = s.find("FLATFILE")
            src = Source(
                name=s.get("NAME"),
                dbdname=s.get("DBDNAME", ""),
                databasetype=s.get("DATABASETYPE", ""),
                owner=s.get("OWNERNAME", ""),
                fields=[_field(f) for f in s.findall("SOURCEFIELD")],
                flatfile=dict(ff.attrib) if ff is not None else {},
            )
            self.sources[(fname, src.name)] = src
        for t in fel.findall("TARGET"):
            tgt = Target(t.get("NAME"), t.get("DATABASETYPE", ""), [_field(f) for f in t.findall("TARGETFIELD")])
            self.targets[(fname, tgt.name)] = tgt
        for t in fel.findall("TRANSFORMATION"):
            tr = _transformation(t)
            self.transformations[(fname, tr.name)] = tr
        for m in fel.findall("MAPPING"):
            self.mappings[(fname, m.get("NAME"))] = self._mapping(fname, m, path)
        for s in fel.findall("SESSION"):
            exts = []
            for e in s.findall("SESSIONEXTENSION"):
                cref = e.find("CONNECTIONREFERENCE")
                exts.append(SessionExtension(
                    sinstance=e.get("SINSTANCENAME", ""),
                    type=e.get("TYPE", ""),
                    subtype=e.get("SUBTYPE", ""),
                    attrs=_attrs(e),
                    connection_variable=cref.get("VARIABLE", "") if cref is not None else "",
                    connection_name=cref.get("CONNECTIONNAME", "") if cref is not None else "",
                ))
            self.sessions[(fname, s.get("NAME"))] = Session(s.get("NAME"), s.get("MAPPINGNAME"), fname, _attrs(s), exts)
        for w in fel.findall("WORKLET"):
            self.worklets[(fname, w.get("NAME"))] = self._flow(fname, w)
        for w in fel.findall("WORKFLOW"):
            self.workflows[(fname, w.get("NAME"))] = self._flow(fname, w)

    def _flow(self, fname, w):
        tasks = {}
        defs = {t.get("NAME"): (t.get("TYPE"), _attrs(t)) for t in w.findall("TASK")}
        for ti in w.findall("TASKINSTANCE"):
            tasks[ti.get("NAME")] = TaskInstance(
                name=ti.get("NAME"),
                taskname=ti.get("TASKNAME"),
                tasktype=ti.get("TASKTYPE"),
                enabled=ti.get("ISENABLED", "YES") == "YES",
                fail_parent=ti.get("FAIL_PARENT_IF_INSTANCE_FAILS", "NO") == "YES",
                treat_input_as_and=ti.get("TREAT_INPUTLINK_AS_AND", "YES") == "YES",
                attrs=defs.get(ti.get("TASKNAME"), ("", {}))[1],
            )
        links = [Link(lk.get("FROMTASK"), lk.get("TOTASK"), lk.get("CONDITION", "")) for lk in w.findall("WORKFLOWLINK")]
        return Workflow(w.get("NAME"), fname, tasks, links, _attrs(w), w.get("SERVERNAME", ""))

    def _mapping(self, fname, m, path):
        trans = {}
        for t in m.findall("TRANSFORMATION"):
            tr = _transformation(t)
            trans[tr.name] = tr
        instances = {}
        for i in m.findall("INSTANCE"):
            instances[i.get("NAME")] = Instance(
                name=i.get("NAME"),
                transformation_name=i.get("TRANSFORMATION_NAME"),
                transformation_type=i.get("TRANSFORMATION_TYPE"),
                type=i.get("TYPE"),
                associated_sources=[a.get("NAME") for a in i.findall("ASSOCIATED_SOURCE_INSTANCE")],
            )
        connectors = [
            Connector(c.get("FROMINSTANCE"), c.get("FROMFIELD"), c.get("TOINSTANCE"), c.get("TOFIELD"))
            for c in m.findall("CONNECTOR")
        ]
        variables = {v.get("NAME"): dict(v.attrib) for v in m.findall("MAPPINGVARIABLE")}
        load_order = [t.get("TARGETINSTANCE") for t in sorted(m.findall("TARGETLOADORDER"), key=lambda e: _int(e.get("ORDER")))]
        return Mapping(m.get("NAME"), fname, trans, instances, connectors, variables, load_order, {}, {}, path)

    # -- resolution helpers -------------------------------------------------

    def mapping(self, folder, name):
        mp = self.mappings[(folder, name)]
        for inst in mp.instances.values():
            if inst.type == "SOURCE":
                mp.sources[inst.name] = self.sources[(folder, inst.transformation_name)]
            elif inst.type == "TARGET":
                mp.targets[inst.name] = self.targets[(folder, inst.transformation_name)]
            elif inst.type == "TRANSFORMATION" and inst.transformation_name not in mp.transformations:
                mp.transformations[inst.transformation_name] = self.transformations[(folder, inst.transformation_name)]
        return mp

    def folders(self):
        return sorted({k[0] for k in list(self.mappings) + list(self.workflows)})
