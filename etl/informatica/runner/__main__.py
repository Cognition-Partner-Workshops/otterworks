"""pmcmd-style command line for the emulated Integration Service.

    python -m runner startworkflow -f <folder> [-paramfile <file>] [-wait] <workflow>
    python -m runner startsession  -f <folder> -w <workflow> <session>
    python -m runner listobjects   [-f <folder>]
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

from .repo import Repository
from .workflow import ESTATE, Integration


def _parser():
    p = argparse.ArgumentParser(prog="pmcmd", description="Emulated PowerCenter pmcmd")
    p.add_argument("--repository", default=os.environ.get("INFA_REPOSITORY_DIR", os.path.join(ESTATE, "repository")))
    p.add_argument("--connections", default=os.environ.get("INFA_CONNECTIONS", os.path.join(ESTATE, "config", "connections.yaml")))
    p.add_argument("--pmrootdir", default=os.environ.get("PMROOTDIR"))
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        for flag in ("-sv", "-d", "-u", "-p", "-usd", "-pv"):
            sp.add_argument(flag, default=None, help=argparse.SUPPRESS)
        sp.add_argument("-f", "--folder", required=True)
        sp.add_argument("-paramfile", action="append", default=None)
        sp.add_argument("-wait", action="store_true")
        sp.add_argument("-nowait", action="store_true")

    sw = sub.add_parser("startworkflow")
    common(sw)
    sw.add_argument("workflow")
    ss = sub.add_parser("startsession")
    common(ss)
    ss.add_argument("-w", "--workflow", required=True)
    ss.add_argument("session")
    lo = sub.add_parser("listobjects")
    lo.add_argument("-f", "--folder", default=None)
    return p


def default_param_files():
    return sorted(glob.glob(os.path.join(ESTATE, "params", "*.par")))


def main(argv=None):
    args = _parser().parse_args(argv)
    repo = Repository(args.repository)
    if args.command == "listobjects":
        for (folder, name), wf in sorted(repo.workflows.items()):
            if args.folder and folder != args.folder:
                continue
            print(f"workflow {folder}/{name}")
            for t in wf.tasks.values():
                if t.tasktype == "Session":
                    s = repo.sessions[(folder, t.taskname)]
                    print(f"  session {t.name} -> mapping {s.mapping}{'' if t.enabled else ' (disabled)'}")
        return 0
    param_files = default_param_files() + (args.paramfile or [])
    svc = Integration(repo, param_files, args.connections, args.pmrootdir, echo=print)
    if args.command == "startworkflow":
        if (args.folder, args.workflow) not in repo.workflows:
            print(f"ERROR: Workflow [{args.folder}:{args.workflow}] not found in repository.", file=sys.stderr)
            return 3
        status, results = svc.run_workflow(args.folder, args.workflow)
        print(f"Workflow {args.workflow} completed with status [{status}] "
              f"({sum(1 for r in results.values() if r['RUN_STATUS'] == 'SUCCEEDED')}/{len(results)} sessions succeeded).")
        return 0 if status == "SUCCEEDED" else 1
    status, rec, _ = svc.run_session(args.folder, args.workflow, args.session, svc._next_run_id())
    print(f"Session {args.session}: {status} read={rec['SUCCESSFUL_SOURCE_ROWS']} written={rec['SUCCESSFUL_ROWS']} rejected={rec['FAILED_ROWS']}")
    return 0 if status == "SUCCEEDED" else 1


if __name__ == "__main__":
    sys.exit(main())
