"""Replaces the Spark lake output users/team_graph_components."""


def run(session):
    database = session.get_current_database()
    function = f'{database}."MART_SPARK"."TEAM_GRAPH_COMPONENTS_LABELS"'
    session.sql("""
        create or replace temporary function {function}(team_id number, user_id number)
        returns table(USER_ID number, COMPONENT_ID number)
        language python
        runtime_version = '3.10'
        handler = 'TeamGraphComponents'
        as $$
class TeamGraphComponents:
    def __init__(self):
        self.teams = {}

    def process(self, team_id, user_id):
        team = 0 if team_id is None else team_id
        user = 0 if user_id is None else user_id
        self.teams.setdefault(team, set()).add(user)

    def end_partition(self):
        edges = {(a, b) for users in self.teams.values()
                 for a in users for b in users if a != b}
        labels = {a: a for a, _ in edges}
        for _ in range(6):
            next_labels = dict(labels)
            for a, v in edges:
                next_labels[v] = min(next_labels[v], labels[a])
            labels = next_labels
        yield from labels.items()
$$
    """.replace("{function}", function)).collect()
    result = session.sql(f"""
        select labels.USER_ID::number(38,0) as USER_ID,
               labels.COMPONENT_ID::number(38,0) as COMPONENT_ID
        from {database}."SPARK_RAW_USERS"."TEAM_MEMBER" members,
             table({function}(members.TEAM_ID, members.USER_ID)
                   over (partition by 1)) labels
    """)
    result.write.save_as_table(
        [database, "MART_SPARK", "TEAM_GRAPH_COMPONENTS"],
        mode="overwrite",
        comment="sfx-d1110 Replaces the Spark lake output users/team_graph_components.",
    )
