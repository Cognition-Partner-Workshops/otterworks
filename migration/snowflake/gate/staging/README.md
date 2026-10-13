# Staging parity for the SSIS packages

The manifest gate (`gate/parity.py`) compares the 25 procedures. The twelve SSIS packages sit
in front of them: each one reads a flat file from `source/build/extracts/`, runs its Derived
Column, Lookup and Script Task steps, and lands rows in a `stg.stg_*` table. This folder holds
one spec per package that says how the package's SQL Server staging table lines up with the
dbt staging model that replaces it.

## The loop for one package

```
make sfm-up                                              # SQL Server, extracts, nightly replay
make sfm-ssis-replay PKG=pkg_files DATE=2026-09-30       # re-run the package on its own
make sfm-load-extracts RUN=$UBW_RUN PY=$PY               # flat files -> RAW.EXT_<file>, all VARCHAR
make sfm-procs RUN=$UBW_RUN PY=$PY                       # Snowpark procedures (Script Task packages)
UBW_RUN=$UBW_RUN $PY target/python/dbt_env.py -- build --select path:models/staging/pkg_files --vars '{business_date: 2026-09-30}'
make sfm-staging-gate RUN=$UBW_RUN PKG=pkg_files PY=$PY  # writes gate/out/staging/pkg_files.{json,md}
```

## Where a package's work lives

Every file a package needs is its own, so the twelve packages never edit the same file:

| What | Path |
| --- | --- |
| dbt source over `RAW.EXT_<file>` (source name = package name) | `target/dbt/models/staging/<package>/_<package>__sources.yml` |
| Staging model(s) and their tests | `target/dbt/models/staging/<package>/` |
| Snowpark procedure for a Script Task | `target/snowpark/procs/<package>.py` |
| Staging parity spec | `gate/staging/<package>.yaml` |
| Staging parity result and explanation | `gate/out/staging/<package>.md` |

A package that lands several tables lists them under `destinations:` in its spec (one unit
`ssis:<package>:<table>` each). Business decisions go under a `### Business decisions` heading
at the end of the md; the gate keeps that section when it rewrites the file.

`RAW.EXT_<file>` is the flat file verbatim: every column is `VARCHAR`, empty fields stay
empty strings, nothing is trimmed. The staging model owns every conversion the package made.

## Divergence

A `DIVERGE` needs an `Explanation:` line in `gate/out/staging/<package>.md`; it carries
forward on the next run. When the package does something that reads as a data-quality
decision the business made (a default, a filter, a rounding, a lookup that drops rows), the
staging model keeps the legacy behaviour so the row matches, and the explanation says so in
plain words: what the package does, which rows it touches, and what the alternative would be.
