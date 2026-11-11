"""Dependencies observed in successful svc_bi_semantic DBQL reads."""

USER_OBJECTS = ("users__v_team_members", "users__team", "users__team_member", "users__app_user")
RED_REASON = (
    "svc_bi_semantic successfully reads SFX_USERS.V_TEAM_MEMBERS (134 DBQL runs), "
    "with TEAM, TEAM_MEMBER and APP_USER dependencies. dbx_d1111_after has no "
    "users__v_team_members, users__team or users__team_member. Build the shared "
    "users targets or retire the read with the owner before cutover."
)


def inspect_users(transport):
    result = transport.execute_with_id(
        "SHOW TABLES IN cpw.dbx_d1111_after LIKE 'users__*'", step="dependency-check"
    )
    index = result["columns"].index("TABLENAME")
    found = {str(row[index]).lower() for row in result["rows"]}
    return {"required": list(USER_OBJECTS), "missing": sorted(set(USER_OBJECTS) - found),
            "statement_id": result["statement_id"]}
