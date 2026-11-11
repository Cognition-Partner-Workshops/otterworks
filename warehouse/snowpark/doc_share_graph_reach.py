"""Replaces the Spark lake output documents/doc_share_graph_reach."""


def run(session):
    database = session.get_current_database()
    function = f'{database}."MART_SPARK"."DOC_SHARE_GRAPH_REACH_WALK"'
    session.sql("""
        create or replace temporary function {function}(
            owner_user_id number, shared_with_user_id number, is_edge boolean)
        returns table(USER_ID number, DISTANCE number)
        language python
        runtime_version = '3.10'
        handler = 'DocShareGraphReach'
        as $$
class DocShareGraphReach:
    def __init__(self):
        self.edges = {}

    def process(self, owner_user_id, shared_with_user_id, is_edge):
        if is_edge:
            self.edges.setdefault(owner_user_id, []).append(shared_with_user_id)

    def end_partition(self):
        visited = {1: 0}
        frontier = {1}
        for depth in range(1, 5):
            frontier = {neighbor for owner in frontier
                        for neighbor in self.edges.get(owner, [])} - visited.keys()
            for user in frontier:
                visited[user] = depth
        yield from visited.items()
$$
    """.replace("{function}", function)).collect()
    result = session.sql(f"""
        with edges as (
            select OWNER_USER_ID, SHARED_WITH_USER_ID, true as IS_EDGE
            from {database}."SPARK_RAW_DOCUMENTS"."DOC_SHARE"
            union all
            select null::number, null::number, false
        )
        select reach.USER_ID::number(38,0) as USER_ID,
               reach.DISTANCE::number(38,0) as DISTANCE
        from edges,
             table({function}(edges.OWNER_USER_ID, edges.SHARED_WITH_USER_ID, edges.IS_EDGE)
                   over (partition by 1)) reach
    """)
    result.write.save_as_table(
        [database, "MART_SPARK", "DOC_SHARE_GRAPH_REACH"],
        mode="overwrite",
        comment="sfx-d1110 Replaces the Spark lake output documents/doc_share_graph_reach.",
    )
