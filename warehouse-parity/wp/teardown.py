"""Drop every Snowflake object named after a run token, then prove nothing remains."""
import os

from .engines import ident

KINDS = [("WAREHOUSES", "WAREHOUSE"), ("DATABASES", "DATABASE"), ("USERS", "USER"),
         ("ROLES", "ROLE"), ("RESOURCE MONITORS", "RESOURCE MONITOR")]


def admin():
    """Connection for teardown. Objects owned by an admin role need WP_SF_ADMIN_USER and WP_SF_ADMIN_TOKEN (a PAT)."""
    import snowflake.connector
    from .engines import Snowflake
    if not os.environ.get("WP_SF_ADMIN_TOKEN"):
        return Snowflake()
    sf = Snowflake.__new__(Snowflake)
    sf.conn = snowflake.connector.connect(
        account=os.environ["WP_SF_ACCOUNT"], user=os.environ["WP_SF_ADMIN_USER"],
        password=os.environ["WP_SF_ADMIN_TOKEN"], role=os.environ.get("WP_SF_ADMIN_ROLE", "ACCOUNTADMIN"),
        session_parameters={"QUERY_TAG": "warehouse-parity-teardown"})
    return sf


def find(sf, token):
    ident(token)
    found = []
    for show, kind in KINDS:
        cols, rows = sf.query(f"SHOW {show} LIKE '{token}%'")
        for r in rows:
            rec = dict(zip(cols, r))
            found.append((kind, rec["name"], rec.get("state")))
    return found


def run(sf, token, yes=False):
    before = find(sf, token)
    for kind, name, state in before:
        print(f"{'DROP' if yes else 'would drop'} {kind} {name}" + (f" (state {state})" if state else ""))
    if not yes:
        return {"token": token, "found": len(before), "dropped": 0, "remaining": len(before)}
    for kind, name, _ in before:
        if kind == "WAREHOUSE":
            sf.execute(f"ALTER WAREHOUSE IF EXISTS {ident(name)} SUSPEND")
        sf.execute(f"DROP {kind} IF EXISTS {ident(name)}")
    after = find(sf, token)
    _, whs = sf.query("SHOW WAREHOUSES")
    running = [r for r in whs if str(r[1]).upper() == "STARTED" and str(r[0]).upper().startswith(token.upper())]
    for kind, name, _ in after:
        print(f"STILL PRESENT {kind} {name}")
    print(f"remaining objects named {token}*: {len(after)}; running {token} warehouses: {len(running)}")
    return {"token": token, "found": len(before), "dropped": len(before) - len(after), "remaining": len(after),
            "running_warehouses": len(running)}
