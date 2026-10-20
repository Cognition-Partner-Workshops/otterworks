-- Stand-in for ClaimsCore's dbo.usp_GetAdjusterRoster, the procedure behind sp_ClaimsDb_RosterQuery_WcfSql.
-- One snapshot of a region's roster per as-of date; the seed loads corpus/stubs/roster, each stub dated
-- with the RequestedDt of the request it answers.
CREATE TABLE adjuster_roster (
    as_of_dt     date    NOT NULL,
    adjuster_id  text    NOT NULL,
    name         text    NOT NULL,
    email        text    NOT NULL,
    region       text    NOT NULL,
    skills       text    NOT NULL,
    open_claims  integer NOT NULL,
    max_claims   integer NOT NULL,
    available    boolean NOT NULL,
    PRIMARY KEY (as_of_dt, adjuster_id)
);

-- The region's latest snapshot on or before the as-of date. p_skill is part of the typed procedure's
-- signature, but the stubs answer with the whole regional roster (adjusters without the skill included),
-- so eligibility on skill stays where BizTalk had it: in Roster_AssignmentRequest_to_Notice.
CREATE FUNCTION usp_get_adjuster_roster(p_region text, p_skill text, p_as_of date)
RETURNS TABLE (adjuster_id text, name text, email text, region text, skills text,
               open_claims integer, max_claims integer, available boolean)
LANGUAGE sql STABLE AS $$
    SELECT r.adjuster_id, r.name, r.email, r.region, r.skills, r.open_claims, r.max_claims, r.available
      FROM adjuster_roster r
     WHERE r.region = p_region
       AND r.as_of_dt = (SELECT max(s.as_of_dt) FROM adjuster_roster s
                          WHERE s.region = p_region AND s.as_of_dt <= p_as_of)
     ORDER BY r.adjuster_id
$$;
