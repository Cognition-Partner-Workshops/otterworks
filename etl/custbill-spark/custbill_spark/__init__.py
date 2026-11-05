"""Local Spark replacement for the CUSTBILL batch chain (etl/legacy-extra/).

One job per legacy stage, byte-identical outputs, no hostname branching, real
locks, surfaced errors. The legacy scripts stay in place as the parity reference.
"""
