"""Workflow scheduling: task ordering, link conditions, session execution and logging."""

from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from . import expr as X
from .db import Connection, load_connections
from .engine import MappingRun, SessionFailed
from .params import resolve
from .sesslog import Log, append_rep_sess_log, pc_ts, write_load_summary

HERE = os.path.dirname(os.path.abspath(__file__))
ESTATE = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(ESTATE))


def process_variables(root=None):
    root = root or os.environ.get("PMROOTDIR") or os.path.join(ESTATE, "infa_shared")
    landing = os.environ.get("LANDING_DIR") or os.path.join(REPO_ROOT, "warehouse", "landing")
    pv = {
        "$PMRootDir": root,
        "$PMSourceFileDir": landing,
        "$PMTargetFileDir": os.path.join(root, "TgtFiles"),
        "$PMBadFileDir": os.path.join(root, "BadFiles"),
        "$PMSessionLogDir": os.path.join(root, "SessLogs"),
        "$PMWorkflowLogDir": os.path.join(root, "WorkflowLogs"),
        "$PMCacheDir": os.path.join(root, "Cache"),
        "$PMStorageDir": os.path.join(root, "Storage"),
        "$PMTempDir": os.path.join(root, "Temp"),
    }
    return pv


def listed_sessions(repo, folder, flow, prefix="", enabled=True):
    """(instance path, session, enabled) in task order with worklets expanded: the order listobjects prints."""
    for t in flow.tasks.values():
        on = enabled and t.enabled
        if t.tasktype == "Session":
            yield prefix + t.name, repo.sessions[(folder, t.taskname)], on
        elif t.tasktype == "Worklet":
            yield from listed_sessions(repo, folder, repo.worklets[(folder, t.taskname)], f"{prefix}{t.name}.", on)


def workflow_mappings(repo, folder, flow, enabled_only=False):
    """Mapping names a workflow or worklet runs, in listobjects order; disabled tasks only when enabled_only is false."""
    return [s.mapping for _, s, on in listed_sessions(repo, folder, flow) if on or not enabled_only]


def select_mappings(repo, spec):
    """MAPPINGS selection: empty/'all', a count N (first N mappings in listobjects order) or comma-separated names/globs."""
    spec = (spec or "").strip()
    if not spec or spec.lower() == "all":
        return None
    ordered = []
    for (folder, _), wf in sorted(repo.workflows.items()):
        for m in workflow_mappings(repo, folder, wf):
            if m not in ordered:
                ordered.append(m)
    if spec.isdigit():
        n = int(spec)
        return None if n >= len(ordered) else set(ordered[:n])
    picked = set()
    for pat in [p.strip() for p in spec.split(",") if p.strip()]:
        hits = [m for m in ordered if fnmatch.fnmatchcase(m, pat) or fnmatch.fnmatchcase(m, "m_" + pat)]
        if not hits:
            raise ValueError(f"MAPPINGS: no mapping matches [{pat}]")
        picked.update(hits)
    return picked


def target_summary(targets):
    """Per physical table: (line, appended) where appended means rows were added on top of prior data."""
    by_table: dict = {}
    for tg in targets:
        agg = by_table.setdefault(tg["table"], {"before": tg["before"], "after": 0, "inserted": 0, "updated": 0, "rejected": 0, "instances": [], "cleared": False})
        agg["cleared"] = agg["cleared"] or tg.get("cleared", False)
        agg["after"] = tg["after"]
        for k in ("inserted", "updated", "rejected"):
            agg[k] += tg[k]
        agg["instances"].append(tg["instance"])
    out = []
    for table, a in by_table.items():
        line = (f"  target [{table}] ({', '.join(a['instances'])}): rows before [{a['before']}] after [{a['after']}]"
                f" (inserted {a['inserted']}, updated {a['updated']}, rejected {a['rejected']})")
        out.append((line, not a["cleared"] and a["before"] > 0 and a["updated"] == 0 and a["inserted"] >= a["before"]
                    and a["after"] >= a["before"] + a["inserted"]))
    return out


class Integration:
    """A single-node Integration Service bound to one exported repository."""

    def __init__(self, repo, param_files=(), connections_file=None, pmrootdir=None, echo=None, mappings=None):
        self.repo = repo
        self.mappings = mappings
        self.param_files = list(param_files)
        self.connections_spec = load_connections(connections_file or os.path.join(ESTATE, "config", "connections.yaml"))
        self.pvars = process_variables(pmrootdir)
        self.echo = echo
        for d in self.pvars.values():
            if d.startswith(self.pvars["$PMRootDir"]):
                os.makedirs(d, exist_ok=True)

    def _next_run_id(self):
        path = os.path.join(self.pvars["$PMStorageDir"], "run_ids.json")
        state = {"workflow_run_id": 100000}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                state = json.load(fh)
        state["workflow_run_id"] += 1
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        return state["workflow_run_id"]

    def _connections(self):
        return {name: Connection(name, spec) for name, spec in self.connections_spec.items()}

    # -- sessions ---------------------------------------------------------

    def run_session(self, folder, workflow, session_name, run_id, instance_name=None):
        session = self.repo.sessions[(folder, session_name)]
        params = resolve(self.param_files, folder, workflow, session_name)
        params["__WORKFLOW__"] = workflow
        log_path = os.path.join(self.pvars["$PMSessionLogDir"], f"{session_name}.log")
        log = Log(log_path, echo=None)
        start = dt.datetime.now().replace(microsecond=0)
        log.info("TM_6014", f"Initializing session [{session_name}] at [{pc_ts(start)}].")
        log.info("TM_6683", f"Repository Name: [{self.repo.repository_name}]")
        log.info("TM_6686", f"Folder: [{folder}]")
        log.info("TM_6685", f"Workflow: [{workflow}] Run Instance Name: [] Run Id: [{run_id}]")
        log.info("TM_6101", f"Mapping name: {session.mapping}.")
        for k in sorted(p for p in params if p.startswith("$") and p != "__WORKFLOW__"):
            log.info("VAR_27028", f"Use override value [{params[k]}] for user-defined workflow/worklet variable:[{k}].")
        conns = self._connections()
        status, stats, err = "SUCCEEDED", None, ("", "")
        t0 = time.monotonic()
        run = None
        try:
            run = MappingRun(self.repo, session, params, self.pvars, conns, log)
            log.info("TM_6007", f"DTM initialized successfully for session [{session_name}]")
            stats = run.run()
            for c in conns.values():
                c.close(commit=True)
            err = stats.first_error
        except SessionFailed as e:
            status, err = "FAILED", (e.code, e.msg)
            log.error(e.code, e.msg)
        except (X.ExpressionError, X.AbortSession, LookupError) as e:
            status, err = "FAILED", ("TE_7022", str(e))
            log.error("TE_7022", f"TShmWriter: Initialized with error: {e}")
        except Exception as e:  # noqa: BLE001 - surfaced as a failed session like the DTM would
            status, err = "FAILED", ("TM_6292", f"{type(e).__name__}: {e}")
            log.error("TM_6292", f"Session run terminated with fatal error: {e}")
            for line in traceback.format_exc().splitlines():
                log.error("TM_6292", line)
        finally:
            if status != "SUCCEEDED":
                for c in conns.values():
                    c.close(commit=False)
        stats = stats or (run.stats if run else None)
        end = dt.datetime.now().replace(microsecond=0)
        if stats is not None:
            write_load_summary(log, stats.sources, [
                {"instance": t.instance, "table": t.table, "inserted": t.inserted, "updated": t.updated, "deleted": t.deleted,
                 "ins_rej": t.ins_rej, "upd_rej": t.upd_rej, "del_rej": t.del_rej, "rejected": t.rejected}
                for t in stats.targets.values()
            ])
        read = stats.rows_read if stats else 0
        written = stats.rows_written if stats and status == "SUCCEEDED" else 0
        rejected = stats.rows_rejected if stats else 0
        log.info("TM_6020", f"Session [{session_name}] completed at [{pc_ts(end)}].")
        log.flush(append=False)
        record = {
            "SUBJECT_AREA": folder, "WORKFLOW_NAME": workflow, "WORKFLOW_RUN_ID": run_id,
            "SESSION_NAME": session_name, "SESSION_INSTANCE_NAME": instance_name or session_name,
            "MAPPING_NAME": session.mapping, "ACTUAL_START": start.strftime("%Y-%m-%d %H:%M:%S"),
            "SESSION_TIMESTAMP": end.strftime("%Y-%m-%d %H:%M:%S"),
            "RUN_STATUS_CODE": 1 if status == "SUCCEEDED" else 3, "RUN_STATUS": status,
            "SUCCESSFUL_SOURCE_ROWS": read, "FAILED_SOURCE_ROWS": stats.transformation_errors if stats else 0,
            "SUCCESSFUL_ROWS": written, "FAILED_ROWS": rejected,
            "FIRST_ERROR_CODE": err[0], "FIRST_ERROR_MSG": err[1][:200], "SESSION_LOG_FILE": log_path,
        }
        append_rep_sess_log(os.path.join(self.pvars["$PMRootDir"], "REP_SESS_LOG.psv"), record)
        record["elapsed"] = round(time.monotonic() - t0, 2)
        record["targets"] = [
            {"instance": t.instance, "table": t.table, "before": t.rows_before, "after": t.rows_after, "cleared": t.cleared,
             "inserted": t.inserted, "updated": t.updated, "rejected": t.failed}
            for t in (stats.targets.values() if stats else [])
        ]
        return status, record, stats

    # -- workflows --------------------------------------------------------

    def run_workflow(self, folder, workflow_name):
        wf = self.repo.workflows[(folder, workflow_name)]
        run_id = self._next_run_id()
        wlog = Log(os.path.join(self.pvars["$PMWorkflowLogDir"], f"{workflow_name}.log"), echo=self.echo)
        wlog.thread = "WRITER"
        wlog.info("LM_36435", f"Starting execution of workflow [{workflow_name}] in folder [{folder}] last saved by user [etl_admin].")
        wlog.info("LM_36330", f"Workflow [{workflow_name}]: Run Id [{run_id}] started.")
        results: dict = {}
        ok = self._run_flow(folder, workflow_name, wf, run_id, wlog, results)
        status = "SUCCEEDED" if ok else "FAILED"
        wlog.info("LM_36385", f"Workflow [{workflow_name}]: Execution {status.lower()}.")
        wlog.flush()
        return status, results

    def _run_flow(self, folder, workflow_name, flow, run_id, wlog, results, scope=""):
        incoming: dict = {n: [] for n in flow.tasks}
        for lk in flow.links:
            incoming[lk.to_task].append(lk)
        state: dict = {}
        pending = list(flow.tasks)
        failed = False
        workers = max(1, int(os.environ.get("INFA_MAX_SESSIONS", "4")))
        while pending:
            ready = [n for n in pending if all(lk.from_task in state for lk in incoming[n])]
            if not ready:
                raise RuntimeError(f"{flow.name} has unreachable tasks: {pending}")
            sessions = []
            for name in ready:
                pending.remove(name)
                task = flow.tasks[name]
                links = incoming[name]
                fired = [self._eval(lk.condition, state, lk.from_task) for lk in links]
                if links and not (all(fired) if task.treat_input_as_and else any(fired)):
                    state[name] = {"Status": "NOTSTARTED"}
                    wlog.info("LM_36320", f"{task.tasktype} task instance [{scope}{name}]: Execution skipped, link conditions not satisfied.")
                    continue
                if task.tasktype == "Start":
                    state[name] = {"Status": "SUCCEEDED"}
                    continue
                if not task.enabled:
                    state[name] = {"Status": "DISABLED"}
                    wlog.info("LM_36317", f"{task.tasktype} task instance [{scope}{name}]: Disabled; skipped.")
                    continue
                if task.tasktype == "Session" and self.mappings is not None \
                        and self.repo.sessions[(folder, task.taskname)].mapping not in self.mappings:
                    state[name] = {"Status": "SUCCEEDED", "PrevTaskStatus": "SUCCEEDED", "SrcSuccessRows": 0,
                                   "TgtSuccessRows": 0, "TgtFailedRows": 0, "ErrorCode": 0}
                    wlog.info("LM_36317", f"Session task instance [{scope}{name}]: mapping not selected by MAPPINGS; skipped.")
                elif task.tasktype == "Session":
                    sessions.append(task)
                elif task.tasktype == "Worklet":
                    wl = self.repo.worklets[(folder, task.taskname)]
                    wlog.info("LM_36322", f"Starting execution of worklet instance [{scope}{name}].")
                    ok = self._run_flow(folder, workflow_name, wl, run_id, wlog, results, scope=f"{scope}{name}.")
                    st = "SUCCEEDED" if ok else "FAILED"
                    state[name] = {"Status": st, "PrevTaskStatus": st}
                    wlog.info("LM_36318" if ok else "LM_36320", f"Worklet task instance [{scope}{name}] {st.lower()}.")
                    if not ok and task.fail_parent:
                        failed = True
                elif task.tasktype == "Decision":
                    cond = task.attrs.get("Decision Condition", "")
                    val = 1 if self._eval(cond, state, None) else 0
                    state[name] = {"Status": "SUCCEEDED", "Condition": val}
                    wlog.info("LM_36325", f"Decision task instance [{scope}{name}]: condition [{cond}] evaluated to [{val}].")
                elif task.tasktype == "Email":
                    state[name] = {"Status": "SUCCEEDED"}
                    wlog.info("EM_1028", f"Email task instance [{scope}{name}]: message [{task.attrs.get('Email Subject', '')}] "
                                         f"queued for [{task.attrs.get('Email User Name', '')}].")
                else:
                    state[name] = {"Status": "SUCCEEDED"}
            if sessions:
                for t in sessions:
                    wlog.info("LM_36322", f"Starting execution of session instance [{scope}{t.name}].")
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futs = {t.name: pool.submit(self.run_session, folder, workflow_name, t.taskname, run_id, t.name) for t in sessions}
                for t in sessions:
                    status, rec, _ = futs[t.name].result()
                    results[f"{scope}{t.name}"] = rec
                    state[t.name] = {
                        "Status": status, "PrevTaskStatus": status,
                        "SrcSuccessRows": rec["SUCCESSFUL_SOURCE_ROWS"], "TgtSuccessRows": rec["SUCCESSFUL_ROWS"],
                        "TgtFailedRows": rec["FAILED_ROWS"], "ErrorCode": rec["FIRST_ERROR_CODE"] or 0,
                    }
                    msg = (f"Session task instance [{scope}{t.name}] {status.lower()}: read [{rec['SUCCESSFUL_SOURCE_ROWS']}] "
                           f"written [{rec['SUCCESSFUL_ROWS']}] rejected [{rec['FAILED_ROWS']}] in [{rec['elapsed']}s]")
                    if status == "SUCCEEDED":
                        wlog.info("LM_36318", msg)
                    else:
                        wlog.error("LM_36320", msg + f" : {rec['FIRST_ERROR_CODE']} {rec['FIRST_ERROR_MSG']}")
                        if t.fail_parent:
                            failed = True
                    for line, appended in target_summary(rec.get("targets", [])):
                        if appended:
                            wlog.warn("WRT_8170", line + " - every row was appended to existing data; nothing was updated")
                        else:
                            wlog.info("WRT_8168", line)
        return not failed

    @staticmethod
    def _eval(cond, state, from_task):
        cond = (cond or "").strip()
        if not cond:
            return from_task is None or state[from_task].get("Status") not in ("NOTSTARTED",)

        def var(m):
            v = state.get(m.group(1), {}).get(m.group(2), None)
            if v is None:
                return "NULL"
            return f"'{v}'" if isinstance(v, str) else str(v)

        text = re.sub(r"\$(\w+)\.(\w+)", var, cond)
        text = re.sub(r"(?<!')\b(SUCCEEDED|FAILED|STOPPED|ABORTED|DISABLED|NOTSTARTED)\b(?!')", r"'\1'", text)
        return X.truthy(X.compile_expr(text)({}))
