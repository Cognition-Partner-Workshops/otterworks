"""Execute one warehouse-local training, evaluation and scoring run."""

import argparse
from pathlib import Path

from snowflake.snowpark import Session
from snowflake.snowpark.types import StringType

from workloads.churn_model.provision import EP, service_connection, sf


def handler(session, run_id, commit, fallback):
    from warehouse import run
    return run(session, run_id, commit, fallback)


def documents_handler(session, run_id, commit, evaluation_run_id):
    from warehouse import documents_only
    return documents_only(session, run_id, commit, evaluation_run_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-only", action="store_true")
    parser.add_argument("--evaluation-run-id")
    args = parser.parse_args()
    if args.documents_only != bool(args.evaluation_run_id):
        parser.error("--documents-only and --evaluation-run-id must be supplied together")
    run_id, commit = sf.make_run_id(EP.workload, "dev"), sf.resolve_commit()
    with service_connection(run_id, commit) as conn:
        session = Session.builder.configs({"connection": conn}).create()
        try:
            options = dict(return_type=StringType(), input_types=[StringType()] * 3, is_permanent=False, execute_as="caller",
                           comment=sf.external_comment(workload=EP.workload, csid=EP.csid),
                           imports=[str(Path(__file__).with_name(name)) for name in ("model.py", "warehouse.py")])
            if args.documents_only:
                procedure = session.sproc.register(documents_handler, packages=["snowflake-snowpark-python", "pandas", "pyarrow"], **options)
                print(procedure(run_id, commit, args.evaluation_run_id))
                return
            try:
                procedure = session.sproc.register(handler, packages=["snowflake-snowpark-python", "pandas", "pyarrow", "scikit-learn"], **options)
                fallback = ""
            except Exception as error:
                if not any(word in str(error).lower() for word in ("anaconda", "package", "scikit-learn")):
                    raise
                procedure = session.sproc.register(handler, packages=["snowflake-snowpark-python", "pandas", "pyarrow"], **options)
                fallback = "native"
            print(procedure(run_id, commit, fallback))
        finally:
            session.close()


if __name__ == "__main__":
    main()
