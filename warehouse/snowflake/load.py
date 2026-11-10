"""Upload pipe-delimited landing files and invoke the COPY loaders."""
import argparse
import json
from pathlib import Path
import re

import yaml

from sfx_conn import ROOT, connect

SPEC = yaml.safe_load((ROOT / "landing_columns.yml").read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", choices=["all", *SPEC], default="all")
    parser.add_argument("--landing-dir", type=Path)
    parser.add_argument("--date")
    args = parser.parse_args()
    if args.date is not None and not re.fullmatch(r"[0-9]{8}", args.date):
        parser.error("--date must be yyyymmdd")
    default = ROOT.parent / "landing"
    landing = args.landing_dir or (default if default.exists() else ROOT / "fixtures/landing")
    areas = SPEC if args.area == "all" else [args.area]
    with connect("load", "copy") as conn:
        with conn.cursor() as cur:
            for area in areas:
                for table in SPEC[area]:
                    files = sorted((landing / area / table).glob(
                        f"{args.date}.psv" if args.date else "*.psv"
                    ))
                    if not files:
                        raise FileNotFoundError(f"No landing files for {area}/{table}")
                    for path in files:
                        uri = path.resolve().as_uri().replace("'", "''")
                        cur.execute(
                            f"PUT '{uri}' @LANDING.LANDING_STAGE/{area}/{table}/ "
                            "AUTO_COMPRESS=FALSE OVERWRITE=FALSE"
                        )
                cur.execute(f"CALL RAW_{area.upper()}.LOAD_{area.upper()}(%s)", (args.date,))
                result = json.loads(cur.fetchone()[0])
                if isinstance(result, dict) and "error" in result:
                    raise RuntimeError(result["error"])
                for row in result:
                    print(f"{area}.{row['table']}: {row['rows_loaded']} rows loaded")


if __name__ == "__main__":
    main()
