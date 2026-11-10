"""Session/workflow log writers and the REP_SESS_LOG run-history export."""

from __future__ import annotations

import csv
import datetime as dt
import os

REP_SESS_LOG_COLUMNS = [
    "SUBJECT_AREA", "WORKFLOW_NAME", "WORKFLOW_RUN_ID", "SESSION_NAME", "SESSION_INSTANCE_NAME",
    "MAPPING_NAME", "ACTUAL_START", "SESSION_TIMESTAMP", "RUN_STATUS_CODE", "RUN_STATUS",
    "SUCCESSFUL_SOURCE_ROWS", "FAILED_SOURCE_ROWS", "SUCCESSFUL_ROWS", "FAILED_ROWS",
    "FIRST_ERROR_CODE", "FIRST_ERROR_MSG", "SESSION_LOG_FILE",
]
STATUS_CODES = {"SUCCEEDED": 1, "DISABLED": 2, "FAILED": 3, "STOPPED": 4, "ABORTED": 5}


def ts(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")


def pc_ts(d: dt.datetime) -> str:
    return d.strftime("%a %b %d %H:%M:%S %Y")


class Log:
    """PowerCenter-style message log: '<time> : <SEV> : (<pid> | <thread>) : (<IS>) : node01 : <CODE> : <msg>'."""

    def __init__(self, path, service="IS_SFX_D1110", node="node01_sfx", pid=0, clock=None, echo=None):
        self.path = path
        self.service, self.node, self.pid = service, node, pid or os.getpid()
        self.clock = clock or (lambda: dt.datetime.now().replace(microsecond=0))
        self.echo = echo
        self.lines: list = []
        self.thread = "MANAGER"

    def _w(self, sev, code, msg, thread=None):
        line = f"{ts(self.clock())} : {sev} : ({self.pid} | {thread or self.thread}) : ({self.service}) : {self.node} : {code} : {msg}"
        self.lines.append(line)
        if self.echo:
            self.echo(line)

    def info(self, code, msg, thread=None):
        self._w("INFO", code, msg, thread)

    def warn(self, code, msg, thread=None):
        self._w("WARNING", code, msg, thread)

    def error(self, code, msg, thread=None):
        self._w("ERROR", code, msg, thread)

    def flush(self, append=True):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a" if append else "w", encoding="utf-8") as fh:
            fh.write("\n".join(self.lines) + "\n\n")
        self.lines = []


def session_summary(log, session, mapping, start, end, status, stats):
    """The load summary block every session log ends with."""
    log.info("TM_6014", f"Initializing session [{session}] at [{pc_ts(start)}].")
    log.info("TM_6683", f"Repository Name: [REP_SFX_PROD]")
    log.info("TM_6686", f"Folder: [{stats.get('folder', '')}]")
    log.info("TM_6685", f"Workflow: [{stats.get('workflow', '')}] Run Instance Name: [] Run Id: [{stats.get('run_id', 0)}]")
    log.info("TM_6101", f"Mapping name: {mapping}.")


def write_load_summary(log, sources, targets, thread="WRITER_1_*_1"):
    log.info("PETL_24031", "***** RUN INFO FOR TGT LOAD ORDER GROUP [1], CONCURRENT SET [1] *****")
    for name, rows in sources.items():
        log.info("PETL_24032", f"SQ Instance [SQ_{name}] SQL Instance [{name}]: Output Rows [{rows}], Affected Rows [{rows}], Applied Rows [{rows}], Rejected Rows [0]", "READER_1_1_1")
    for t in targets:
        log.info("WRT_8036", f"Target: {t['table']} (Instance Name: [{t['instance']}])", thread)
        log.info("WRT_8038", f"Inserted rows - Requested: {t['inserted'] + t['ins_rej']} Applied: {t['inserted']} Rejected: {t['ins_rej']} Affected: {t['inserted']}", thread)
        if t["updated"] or t["upd_rej"]:
            log.info("WRT_8041", f"Updated rows - Requested: {t['updated'] + t['upd_rej']} Applied: {t['updated']} Rejected: {t['upd_rej']} Affected: {t['updated']}", thread)
        if t["deleted"] or t["del_rej"]:
            log.info("WRT_8040", f"Deleted rows - Requested: {t['deleted'] + t['del_rej']} Applied: {t['deleted']} Rejected: {t['del_rej']} Affected: {t['deleted']}", thread)
        if t["rejected"]:
            log.info("WRT_8350", f"Rejected rows (DD_REJECT/not permitted) written to reject file: {t['rejected']}", thread)


def append_rep_sess_log(path, record):
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REP_SESS_LOG_COLUMNS, delimiter="|", lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow({k: record.get(k, "") for k in REP_SESS_LOG_COLUMNS})
